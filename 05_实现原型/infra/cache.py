# -*- coding: utf-8 -*-
"""infra/cache.py —— §3.42 W12 ⭐ 性能/缓存层（LRU + TTL）

需求：
- LRU（容量驱逐）+ TTL（时间过期）
- get/set/invalidate 接口 + 命中率统计
- 装饰器 ``@cached(ttl=..., namespace=...)`` 给函数加缓存（行为透明）
- 全局 ``CacheRegistry`` 按 namespace 管理多个 LRUCache（reload_all 时按 ns 失效）
- 容量 / 默认 TTL 可从 config_loader 读，无配置时用内置默认

设计原则：
- **ratchet**：对调用方行为透明（相同 args 始终返回相同结果，无副作用）
- **线程安全**：RLock 包裹所有读写
- **失败不入缓存**：异常结果不缓存（避免错误永久化）
- **可观测**：stats() 返回 hits/misses/evictions/expired_evictions/size/hit_rate

典型用法：
    from infra.cache import cached, get_cache_registry

    @cached(namespace="profile_bundle", ttl=300)
    def get_effective_config(profile_name: str = "standard") -> dict:
        ...

    # 配置热重载时清掉所有受影响的 namespace
    get_cache_registry().invalidate_namespace("profile_bundle")
"""
from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple


# ────────────────────────────────────────────────────────────
#  默认参数（可被 config_loader 覆盖）
# ────────────────────────────────────────────────────────────
DEFAULT_CAPACITY = 128
DEFAULT_TTL = 300.0  # 5 分钟


def _load_cache_config() -> Tuple[int, float]:
    """从 config_loader 读 cache 配置（带异常兜底）。

    返回 (capacity, default_ttl)。config_loader 不可用时返回内置默认。
    """
    try:
        from config_loader import load_agents_config
        cfg = load_agents_config()
        cache_cfg = (cfg or {}).get("cache", {}) or {}
        cap = int(cache_cfg.get("capacity", DEFAULT_CAPACITY))
        ttl = float(cache_cfg.get("default_ttl", DEFAULT_TTL))
        if cap < 1:
            cap = DEFAULT_CAPACITY
        if ttl <= 0:
            ttl = DEFAULT_TTL
        return cap, ttl
    except Exception:
        return DEFAULT_CAPACITY, DEFAULT_TTL


# ────────────────────────────────────────────────────────────
#  缓存条目
# ────────────────────────────────────────────────────────────
class _CacheEntry:
    __slots__ = ("value", "expire_at")

    def __init__(self, value: Any, ttl_s: float, now: Optional[float] = None):
        self.value = value
        # 使用 monotonic 时钟（不受系统时间跳变影响）
        self.expire_at = (now if now is not None else time.monotonic()) + ttl_s

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.monotonic()) > self.expire_at


# ────────────────────────────────────────────────────────────
#  LRU + TTL 缓存
# ────────────────────────────────────────────────────────────
class LRUCache:
    """线程安全的 LRU + TTL 缓存。

    - capacity: 最大条目数（LRU 驱逐最久未使用）
    - default_ttl: 默认过期时间（秒）；set() 可单独覆盖
    - stats: 命中 / 未命中 / 写入 / LRU 驱逐 / TTL 过期计数
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY, default_ttl: float = DEFAULT_TTL,
                 name: Optional[str] = None):
        if capacity < 1:
            capacity = 1
        if default_ttl <= 0:
            default_ttl = DEFAULT_TTL
        self._capacity = capacity
        self._default_ttl = default_ttl
        self._name = name or "unnamed"
        # OrderedDict 维持插入顺序；move_to_end 实现 LRU 触达
        self._data: "OrderedDict[str, _CacheEntry]" = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "evictions": 0,            # LRU 容量驱逐
            "expired_evictions": 0,    # TTL 过期失效
        }

    # ─── 属性 ───
    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def default_ttl(self) -> float:
        return self._default_ttl

    # ─── 核心 ───
    def get(self, key: str, default: Any = None) -> Any:
        """读取 key。命中且未过期 → 返回 value；否则返回 default。

        注意：value=None 不被缓存（视作 miss）—— 见 set()。如果需要缓存 None
        作为合法值，用 ``fetch()`` 区分 hit / miss。
        """
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return default
            if entry.is_expired():
                # 过期视为 miss + 删除
                del self._data[key]
                self._stats["expired_evictions"] += 1
                self._stats["misses"] += 1
                return default
            # 命中 → LRU 触达（move_to_end）
            self._data.move_to_end(key)
            self._stats["hits"] += 1
            return entry.value

    def fetch(self, key: str) -> Tuple[bool, Any]:
        """读取 key，返回 (hit, value)。

        与 get() 的区别：可以区分"未命中"与"命中且 value=None"。
        """
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return False, None
            if entry.is_expired():
                del self._data[key]
                self._stats["expired_evictions"] += 1
                self._stats["misses"] += 1
                return False, None
            self._data.move_to_end(key)
            self._stats["hits"] += 1
            return True, entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """写入 key（value 为 None 或 Exception 时不缓存）。

        如需缓存 None 作为合法值，用 ``set_force()``。
        """
        if value is None or isinstance(value, BaseException):
            return
        self._write(key, value, ttl)

    def set_force(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """强制写入（即使 value=None / Exception 也写入；Exception 仍不入缓存）。"""
        if isinstance(value, BaseException):
            return
        self._write(key, value, ttl)

    def _write(self, key: str, value: Any, ttl: Optional[float]) -> None:
        """内部写入（不加 value 校验）。"""
        ttl_s = ttl if ttl is not None else self._default_ttl
        if ttl_s <= 0:
            return
        with self._lock:
            # 已存在 → 更新 + LRU 触达
            if key in self._data:
                self._data[key] = _CacheEntry(value, ttl_s)
                self._data.move_to_end(key)
                self._stats["writes"] += 1
                return
            # 新增 → 检查容量
            while len(self._data) >= self._capacity:
                # 弹出最久未使用（OrderedDict 第一项）
                self._data.popitem(last=False)
                self._stats["evictions"] += 1
            self._data[key] = _CacheEntry(value, ttl_s)
            self._stats["writes"] += 1

    def invalidate(self, key: Optional[str] = None) -> int:
        """失效缓存。key=None 清空全部；否则只删该 key。返回失效条目数。"""
        with self._lock:
            if key is None:
                n = len(self._data)
                self._data.clear()
                return n
            if key in self._data:
                del self._data[key]
                return 1
            return 0

    def keys(self) -> list:
        with self._lock:
            return list(self._data.keys())

    def stats(self) -> dict:
        with self._lock:
            hits = self._stats["hits"]
            misses = self._stats["misses"]
            total = hits + misses
            return {
                **self._stats,
                "size": len(self._data),
                "hit_rate": round(hits / total, 4) if total > 0 else 0.0,
                "capacity": self._capacity,
                "default_ttl": self._default_ttl,
                "name": self._name,
            }

    def reset_stats(self) -> None:
        with self._lock:
            for k in self._stats:
                self._stats[k] = 0


# ────────────────────────────────────────────────────────────
#  全局 Cache Registry（按 namespace 管理多个 LRUCache）
# ────────────────────────────────────────────────────────────
class CacheRegistry:
    """进程级缓存注册表：按 namespace 持有 LRUCache 实例。"""

    def __init__(self):
        self._caches: Dict[str, LRUCache] = {}
        self._lock = threading.RLock()

    def get_or_create(self, namespace: str, capacity: Optional[int] = None,
                      default_ttl: Optional[float] = None) -> LRUCache:
        """获取或创建 namespace 对应的 LRUCache。"""
        with self._lock:
            cache = self._caches.get(namespace)
            if cache is not None:
                return cache
            cfg_cap, cfg_ttl = _load_cache_config()
            cache = LRUCache(
                capacity=capacity if capacity is not None else cfg_cap,
                default_ttl=default_ttl if default_ttl is not None else cfg_ttl,
                name=namespace,
            )
            self._caches[namespace] = cache
            return cache

    def get(self, namespace: str) -> Optional[LRUCache]:
        with self._lock:
            return self._caches.get(namespace)

    def namespaces(self) -> list:
        with self._lock:
            return list(self._caches.keys())

    def invalidate_namespace(self, namespace: str) -> int:
        """失效指定 namespace 的全部缓存条目（不删除实例）。"""
        with self._lock:
            cache = self._caches.get(namespace)
            if cache is None:
                return 0
            return cache.invalidate()

    def invalidate_all(self) -> int:
        """失效所有 namespace 的全部缓存条目。"""
        total = 0
        with self._lock:
            for cache in self._caches.values():
                total += cache.invalidate()
        return total

    def stats_all(self) -> dict:
        """汇总所有 namespace 的 stats。"""
        out = {}
        with self._lock:
            for ns, cache in self._caches.items():
                out[ns] = cache.stats()
        return out


# 全局单例
_global_registry: Optional[CacheRegistry] = None
_global_registry_lock = threading.Lock()


def get_cache_registry() -> CacheRegistry:
    """获取全局 CacheRegistry 单例。"""
    global _global_registry
    with _global_registry_lock:
        if _global_registry is None:
            _global_registry = CacheRegistry()
        return _global_registry


# ────────────────────────────────────────────────────────────
#  key 构造（args + kwargs → canonical 字符串）
# ────────────────────────────────────────────────────────────
def _make_cache_key(args: tuple, kwargs: dict) -> str:
    """把 (args, kwargs) 转成 canonical 字符串（dict 按 key 排序）。"""
    try:
        canonical_args = json.dumps(args, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        canonical_args = repr(args)
    try:
        canonical_kwargs = json.dumps(kwargs, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        canonical_kwargs = repr(kwargs)
    return f"args={canonical_args}|kwargs={canonical_kwargs}"


# ────────────────────────────────────────────────────────────
#  cached 装饰器
# ────────────────────────────────────────────────────────────
def cached(
    namespace: str,
    ttl: Optional[float] = None,
    capacity: Optional[int] = None,
    key_fn: Optional[Callable[..., str]] = None,
):
    """函数缓存装饰器：LRU + TTL + 命名空间隔离。

    Args:
        namespace: 缓存命名空间（reload_all 时按 ns 失效）
        ttl: 过期秒数（None → 从 config / 默认）
        capacity: 缓存容量（None → 从 config / 默认）
        key_fn: 自定义 key 函数（接收 *args, **kwargs → str）；None 用默认 canonical

    行为：
        - 命中：直接返回缓存值（不调用原函数）
        - 未命中：调用原函数 → 缓存返回值（异常不缓存）
        - 函数本身新增 ``.cache`` 属性指向所属 LRUCache

    Raises:
        透传原函数抛出的异常（不吞）
    """
    def decorator(fn: Callable) -> Callable:
        cache = get_cache_registry().get_or_create(
            namespace, capacity=capacity,
            default_ttl=ttl if ttl is not None else None,
        )

        def wrapper(*args, **kwargs):
            # 构造 key
            if key_fn is not None:
                k = key_fn(*args, **kwargs)
            else:
                k = _make_cache_key(args, kwargs)
            # 查缓存
            hit = cache.get(k)
            if hit is not None:
                return hit
            # 未命中 → 调用原函数
            result = fn(*args, **kwargs)
            # 缓存（异常不入缓存）
            if result is None or isinstance(result, BaseException):
                return result
            cache.set(k, result)
            return result

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        wrapper.cache = cache     # type: ignore[attr-defined]
        wrapper.__name__ = getattr(fn, "__name__", "cached_fn")
        wrapper.__doc__ = getattr(fn, "__doc__", None)
        return wrapper

    return decorator


# ────────────────────────────────────────────────────────────
#  公开 API
# ────────────────────────────────────────────────────────────
__all__ = [
    "LRUCache",
    "CacheRegistry",
    "cached",
    "get_cache_registry",
    "DEFAULT_CAPACITY",
    "DEFAULT_TTL",
]


if __name__ == "__main__":
    # 自测
    c = LRUCache(capacity=3, default_ttl=60.0, name="demo")
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    print("a:", c.get("a"))   # 1
    c.set("d", 4)             # 驱逐 b（LRU）
    print("a:", c.get("a"))   # 1
    print("b:", c.get("b"))   # None
    print("stats:", c.stats())