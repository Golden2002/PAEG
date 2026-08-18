# -*- coding: utf-8 -*-
"""test_cache_layer.py —— §3.42 W12 ⭐ 性能/缓存层（LRU+TTL 缓存 + 热重载失效）

需求（W12）：
- Profile Bundle 解析 / 知识图查询 / 配置查找走 LRU+TTL 缓存
- 配置热重载（reload_all）→ 缓存失效
- 缓存命中率 > 80%
- Profile Bundle 路径 ≥ 3× 加速

TDD 铁律：先 RED 后 GREEN。本文件 5 个测试先全部失败（infra.cache 不存在 / 模块未接入）。
"""
from __future__ import annotations

import time

import pytest


# ────────────────────────────────────────────────────────────
#  测试 1：LRU 基本命中 / 未命中
# ────────────────────────────────────────────────────────────
def test_cache_lru_basic():
    """LRU：基本 hit / miss + 容量驱逐（最久未使用）。"""
    from infra.cache import LRUCache

    # 容量 3：填入 a/b/c，访问 b 让其变为最近使用，再写 d 驱逐 LRU (c)
    c = LRUCache(capacity=3, default_ttl=60.0)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    # 基本 hit
    assert c.get("a") == 1, "a 应命中"
    # 标记 b 为最近使用（get 顺序：b → c → a）
    assert c.get("b") == 2
    assert c.get("c") == 3
    assert c.get("a") == 1
    # 写 d 应驱逐 LRU（b 已被访问过 → LRU 为 b）
    c.set("d", 4)
    assert c.get("a") == 1, "a 不应被驱逐（刚被访问）"
    assert c.get("c") == 3, "c 不应被驱逐"
    assert c.get("b") is None, "b 应是 LRU，被新键 d 驱逐"
    assert c.get("d") == 4, "d 应能命中"

    # 基本 miss：未写入的 key 返回 None
    assert c.get("never_set") is None, "未写入的 key 应返回 None"


# ────────────────────────────────────────────────────────────
#  测试 2：TTL 过期后重新计算
# ────────────────────────────────────────────────────────────
def test_cache_ttl_expiry():
    """TTL：过期后视为 miss，下次 set 写入新值。"""
    from infra.cache import LRUCache

    c = LRUCache(capacity=10, default_ttl=0.1)  # 100ms TTL
    c.set("k", "v1")
    assert c.get("k") == "v1", "写入后立即读应命中"
    # 等待过期（200ms > 100ms TTL）
    time.sleep(0.2)
    assert c.get("k") is None, "TTL=100ms 过期后应 miss"
    # 重新写入
    c.set("k", "v2")
    assert c.get("k") == "v2", "过期后重写应命中"

    # 显式 ttl 覆盖默认 ttl
    c2 = LRUCache(capacity=10, default_ttl=60.0)
    c2.set("long", "x", ttl=10.0)
    assert c2.get("long") == "x"
    c2.set("short", "y", ttl=0.05)
    assert c2.get("short") == "y"
    time.sleep(0.1)
    assert c2.get("short") is None, "显式短 TTL 应过期"
    assert c2.get("long") == "x", "显式长 TTL 不应过期"


# ────────────────────────────────────────────────────────────
#  测试 3：重复查询命中率 > 80%
# ────────────────────────────────────────────────────────────
def test_cache_hit_ratio():
    """重复查询同一组 key：命中率应 > 80%。"""
    from infra.cache import cached, get_cache_registry

    # 干净起点：清掉 namespace
    reg = get_cache_registry()
    reg.invalidate_namespace("hit_ratio_test")

    actual_calls = {"n": 0}

    @cached(namespace="hit_ratio_test", ttl=60)
    def expensive_query(x):
        """模拟昂贵查询（实际不做任何事，仅计数）。"""
        actual_calls["n"] += 1
        return x * 2

    # 阶段 1：冷启动 10 个 key（10 次 miss）
    for i in range(10):
        expensive_query(i)
    # 阶段 2：重复 90 次同组 key（应全 hit）
    for _ in range(9):
        for i in range(10):
            expensive_query(i)
    # 总查询：100，实际函数调用：10（命中率 = 90/100 = 0.9）
    assert actual_calls["n"] == 10, \
        f"10 个独立 key 应只触发 10 次实际计算，实际 {actual_calls['n']}"

    cache = reg.get("hit_ratio_test")
    assert cache is not None, "registry 应能取到 hit_ratio_test 缓存"
    stats = cache.stats()
    total = stats["hits"] + stats["misses"]
    assert total == 100, f"总访问应为 100，实际 {total}"
    assert stats["hits"] == 90, f"命中应为 90，实际 {stats['hits']}"
    assert stats["hit_rate"] > 0.8, f"命中率应 > 0.8，实际 {stats['hit_rate']}"


# ────────────────────────────────────────────────────────────
#  测试 4：配置重载 → 缓存失效
# ────────────────────────────────────────────────────────────
def test_cache_invalidate_on_reload(monkeypatch):
    """config_hub.reload_all() 应清空 profile_bundle / knowledge_base 命名空间缓存。

    验证语义：配置变更后再次 get_effective_config 应拿到最新值（缓存已被清掉）。
    """
    from infra.cache import get_cache_registry
    from config_hub import get_hub
    import services.profile_bundle as pb

    # 1) 缓存预热：触发一次 get_effective_config 让缓存有数据
    reg = get_cache_registry()
    reg.invalidate_namespace("profile_bundle")  # 清掉旧值（避免其他测试污染）
    cfg_before = pb.get_effective_config("standard")
    cache = reg.get("profile_bundle")
    assert cache is not None, "get_effective_config 应已注册到 profile_bundle namespace"
    # 此时缓存里应有 standard profile 的条目
    assert cache.stats()["size"] >= 1, \
        f"缓存预热后 size 应 >= 1，实际 {cache.stats()['size']}"

    # 2) 触发配置重载
    get_hub().reload_all()

    # 3) 缓存应被清空（namespace 失效）
    assert cache.stats()["size"] == 0, \
        f"reload_all 后缓存应被清空，实际 size={cache.stats()['size']}"

    # 4) 知识图查询也应被 reload_all 触发失效（即使 namespace 不同，至少
    #    knowledge_base namespace 缓存若存在则应被清掉；这里只验证 reload_all
    #    调用本身无异常 + 缓存大小为 0 即可）


# ────────────────────────────────────────────────────────────
#  测试 5：Profile Bundle 路径 ≥ 3× 加速（对比无缓存）
# ────────────────────────────────────────────────────────────
def test_cache_speedup(monkeypatch):
    """Profile Bundle 解析：缓存命中后比未命中快 ≥ 3 倍。

    方法：在 get_effective_config 内层函数 compose_profile 上注入固定 sleep，
    模拟 I/O 开销。冷调用耗时含 sleep；热调用直接拿缓存。比较两者比值 ≥ 3。
    """
    import services.profile_bundle as pb
    from infra.cache import get_cache_registry

    # 1) 给 compose_profile 注入 50ms 模拟开销（仅本次测试生效，monkeypatch 自动还原）
    original_compose = pb.compose_profile

    def slow_compose(*args, **kwargs):
        time.sleep(0.05)  # 50ms
        return original_compose(*args, **kwargs)

    monkeypatch.setattr(pb, "compose_profile", slow_compose)

    # 2) 清掉 profile_bundle 缓存，确保冷启动
    reg = get_cache_registry()
    reg.invalidate_namespace("profile_bundle")

    # 3) 冷调用（首次，未命中）
    t0 = time.perf_counter()
    cfg1 = pb.get_effective_config("standard")
    cold_dt = time.perf_counter() - t0
    assert cold_dt >= 0.04, f"冷调用应至少 50ms（模拟 I/O），实际 {cold_dt*1000:.1f}ms"

    # 4) 热调用（重复 10 次，全部命中）
    warm_dts = []
    for _ in range(10):
        t = time.perf_counter()
        cfg2 = pb.get_effective_config("standard")
        warm_dts.append(time.perf_counter() - t)
    warm_avg = sum(warm_dts) / len(warm_dts)
    assert cfg1 == cfg2, "缓存命中结果应与冷调用一致"

    # 5) 加速比
    speedup = cold_dt / max(warm_avg, 1e-6)
    assert speedup >= 3.0, \
        f"Profile Bundle 路径加速比应 ≥ 3×，实际 {speedup:.2f}×（冷 {cold_dt*1000:.1f}ms / 热 {warm_avg*1000:.1f}ms）"


# ────────────────────────────────────────────────────────────
#  附加测试：装饰器无关性（缓存透明——相同入参返回相同结果）
# ────────────────────────────────────────────────────────────
def test_decorator_is_transparent():
    """cached 装饰器对函数行为透明：相同 args → 相同结果，无副作用干扰。"""
    from infra.cache import cached, get_cache_registry

    reg = get_cache_registry()
    reg.invalidate_namespace("transparent_test")

    call_log = []

    @cached(namespace="transparent_test", ttl=60)
    def add(a, b):
        call_log.append((a, b))
        return a + b

    r1 = add(2, 3)
    r2 = add(2, 3)
    r3 = add(2, 3)
    assert r1 == r2 == r3 == 5, "cached 行为应透明（值一致）"
    assert len(call_log) == 1, f"3 次相同调用应只触发 1 次实际计算，实际 {len(call_log)}"