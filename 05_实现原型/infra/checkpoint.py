# -*- coding: utf-8 -*-
"""infra/checkpoint.py —— §3.42 W9 ⭐ session-checkpoint-policy（v1.x.x）

借鉴 deepseek-harness session-checkpoint-policy（packages/core/session/src/checkpoint.ts）：

策略分层 4 模式（互斥）：
- auto    —— 每 N 个事件触发一次 checkpoint（N = max_events）
- manual  —— 仅显式调用 trigger_manual() 触发
- time    —— 每 T 秒触发一次（T = interval_sec）
- hybrid  —— 时间 OR 事件数 任一触发（默认生产模式）

设计要点：
1. **判定与副作用分离**：`should_checkpoint()` / `_should_checkpoint_internal()` 是纯判定，
   不修改状态；`record_event()` / `trigger_manual()` 是带副作用的入口。
2. **失败可观测**：落盘失败发 checkpoint/failed 事件（含 error/retryable 字段），
   业务层可据此决定是否重试；落盘成功发 checkpoint/saved 事件（含 bytes_written）。
3. **可恢复**：每个 session_id 对应一个 JSON checkpoint 文件，
   进程崩溃后调用 recover(session_id) 即可还原 payload。
4. **配置可注入**：默认从 config/checkpoint.json 加载；可通过构造参数覆盖
   （便于测试和热更新）。
5. **时钟可注入**：`_time_fn` 默认 time.time，测试可注入假时钟。

ratchet：infra/event_types.py 加 3 个 PLUGIN_EVENT_TYPES；不改 event_types 行为。
"""
from __future__ import annotations

import json
import os
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional


class PolicyMode(str, Enum):
    """checkpoint 策略模式（str 混入便于 JSON 序列化）。"""
    AUTO = "auto"          # 每 max_events 个事件
    MANUAL = "manual"      # 仅显式 API
    TIME = "time"          # 每 interval_sec 秒
    HYBRID = "hybrid"      # 时间 OR 事件数


# ────────────────────────────────────────────────────────────
#  配置加载（从 config/checkpoint.json，可被构造参数覆盖）
# ────────────────────────────────────────────────────────────
def _load_config_defaults() -> Dict[str, Any]:
    """加载 config/checkpoint.json 默认值；缺失字段用兜底默认。"""
    defaults: Dict[str, Any] = {
        "mode": "hybrid",
        "max_events": 10,
        "interval_sec": 60,
        "max_retries": 3,
        "base_dir": "users_data/checkpoints",
        "enabled": True,
    }
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        _cfg_path = os.path.normpath(
            os.path.join(_here, "..", "config", "checkpoint.json"))
        if os.path.isfile(_cfg_path):
            with open(_cfg_path, encoding="utf-8") as _f:
                _cfg = json.load(_f)
            if isinstance(_cfg, dict):
                defaults.update({k: v for k, v in _cfg.items() if v is not None})
    except Exception:
        # 配置加载失败不影响默认行为
        pass
    return defaults


# 模块级默认配置（懒加载）
_DEFAULTS: Optional[Dict[str, Any]] = None


def _get_defaults() -> Dict[str, Any]:
    global _DEFAULTS
    if _DEFAULTS is None:
        _DEFAULTS = _load_config_defaults()
    return _DEFAULTS


# ────────────────────────────────────────────────────────────
#  落盘根目录（测试可 monkeypatch 覆盖）
# ────────────────────────────────────────────────────────────
CHECKPOINT_BASE_DIR: Optional[str] = None  # 测试可重置为 tmp 目录


def _resolve_base_dir() -> str:
    """解析落盘根目录：模块级 CHECKPOINT_BASE_DIR > config base_dir > 兜底"""
    global CHECKPOINT_BASE_DIR
    if CHECKPOINT_BASE_DIR:
        return CHECKPOINT_BASE_DIR
    cfg = _get_defaults()
    base = cfg.get("base_dir") or "users_data/checkpoints"
    if not os.path.isabs(base):
        # 相对路径相对项目根（05_实现原型）
        _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base = os.path.join(_here, base)
    return base


# ────────────────────────────────────────────────────────────
#  事件发射（带降级：observability 不可用时静默）
# ────────────────────────────────────────────────────────────
def _emit_event(event_type: str, data: Dict[str, Any]) -> None:
    """发 checkpoint/* 类型化事件（§3.42 W2 trace 自动挂载）。"""
    try:
        from observability import emit_event_typed
        emit_event_typed(event_type, data=data)
    except Exception:
        # 可观测性是辅助层；checkpoint 主流程不因事件失败中断
        pass


# ────────────────────────────────────────────────────────────
#  落盘 IO（可被测试 monkeypatch 覆盖注入失败）
# ────────────────────────────────────────────────────────────
def _save_payload(session_id: str, payload: Dict[str, Any]) -> int:
    """把 checkpoint payload 写到 <base_dir>/<session_id>.json（原子写入）。

    Returns:
        bytes_written（写入字节数）

    Raises:
        OSError / IOError：磁盘/权限错误（被外层捕获并发 checkpoint/failed）
    """
    base = _resolve_base_dir()
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, f"{session_id}.json")
    tmp = path + ".tmp"
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
        bytes_written = f.tell()
    os.replace(tmp, path)  # 原子替换（避免半成品文件）
    return bytes_written


def _load_payload(session_id: str) -> Optional[Dict[str, Any]]:
    """从 <base_dir>/<session_id>.json 读取 payload；不存在/损坏返回 None。"""
    base = _resolve_base_dir()
    path = os.path.join(base, f"{session_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ────────────────────────────────────────────────────────────
#  CheckpointPolicy：策略 + 状态 + 落盘
# ────────────────────────────────────────────────────────────
class CheckpointPolicy:
    """会话 checkpoint 策略器（4 模式 + 落盘 + 恢复）。

    用法：
        policy = CheckpointPolicy(mode="hybrid", max_events=10, interval_sec=60)
        # 喂事件（业务侧调用——例如每条会话消息/每 turn 完结）
        triggered = policy.record_event(session_id, payload={"state": ...})
        # manual 模式强制触发
        policy.trigger_manual(session_id, payload={"state": ...})
        # 进程崩溃后恢复
        recovered = policy.recover(session_id)
    """

    def __init__(
        self,
        mode: str = "hybrid",
        max_events: int = 10,
        interval_sec: float = 60.0,
        max_retries: int = 3,
        base_dir: Optional[str] = None,
        _time_fn: Optional[Callable[[], float]] = None,
    ):
        cfg = _get_defaults()
        self.mode = mode if mode in {m.value for m in PolicyMode} else cfg["mode"]
        self.max_events = max_events or cfg["max_events"]
        self.interval_sec = interval_sec or cfg["interval_sec"]
        self.max_retries = max_retries or cfg["max_retries"]
        # base_dir 仅在显式传入时覆盖（不写模块全局——避免污染其他实例）
        if base_dir:
            self._local_base_dir = base_dir
        else:
            self._local_base_dir = None
        # 时间函数（可注入）
        self._time_fn = _time_fn or time.time
        # session_id → 状态（thread-safe 用 RLock）
        self._states: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    # ───── 纯判定（不修改状态）─────
    def _should_checkpoint_internal(self, session_id: str) -> bool:
        """判定是否应触发 checkpoint（**纯函数**——不修改 _states）。"""
        with self._lock:
            state = self._states.get(session_id)
            if state is None:
                # 未初始化：第一次 record_event 前不应触发
                return False
        mode = self.mode
        if mode == PolicyMode.MANUAL.value:
            return False
        if mode == PolicyMode.AUTO.value:
            return state["events"] >= self.max_events
        if mode == PolicyMode.TIME.value:
            return (self._time_fn() - state["last_ts"]) >= self.interval_sec
        if mode == PolicyMode.HYBRID.value:
            if state["events"] >= self.max_events:
                return True
            return (self._time_fn() - state["last_ts"]) >= self.interval_sec
        return False

    # ───── 带副作用入口 ─────
    def record_event(
        self,
        session_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """记录一个事件并判定是否触发 checkpoint（副作用：增加计数）。

        Args:
            session_id: 会话 ID
            payload:  本次事件的增量状态（与 last_payload 合并；触发时一并落盘）

        Returns:
            bool: True 表示本次触发了 checkpoint（含落盘）
        """
        with self._lock:
            state = self._states.setdefault(
                session_id,
                {"events": 0, "last_ts": self._time_fn(), "last_checkpoint": None,
                 "last_payload": {}},
            )
            state["events"] += 1
            # 合并最新 payload（增量更新——保留之前 payload 的字段）
            if payload:
                merged = dict(state.get("last_payload") or {})
                merged.update(payload)
                state["last_payload"] = merged
            should_trigger = self._should_checkpoint_internal(session_id)
            if should_trigger:
                # 重置计数 + 时间戳
                state["events"] = 0
                state["last_ts"] = self._time_fn()
                state["last_checkpoint"] = self._time_fn()
                _payload = dict(state["last_payload"])  # 拷贝
                state["last_payload"] = {}  # 清空（避免 stale）
            else:
                _payload = None

        if should_trigger and _payload is not None:
            self._save_with_retry(session_id, _payload)
            return True
        return False

    def trigger_manual(
        self,
        session_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """manual 模式强制触发 checkpoint（任何模式都可调）。

        - 用于：关键节点（turn 完成、用户登出等）
        - 返回 True 表示"已尝试触发"（落盘结果由 _save_with_retry 内部事件表达）
        - payload 缺失时也会触发，但跳过磁盘写入（避免覆盖现有 checkpoint 为空）
        """
        with self._lock:
            state = self._states.setdefault(
                session_id,
                {"events": 0, "last_ts": self._time_fn(), "last_checkpoint": None,
                 "last_payload": {}},
            )
            if payload:
                merged = dict(state.get("last_payload") or {})
                merged.update(payload)
                state["last_payload"] = merged
            _payload = state.get("last_payload") or {}
            state["events"] = 0
            state["last_ts"] = self._time_fn()
            state["last_checkpoint"] = self._time_fn()

        if not _payload:
            # 空 payload：只发 saved 标记事件（不写磁盘避免覆盖现有 checkpoint）
            _emit_event("checkpoint/saved", {
                "session_id": session_id,
                "bytes_written": 0,
                "mode": self.mode,
                "empty": True,
            })
            return True
        self._save_with_retry(session_id, _payload)
        return True

    # ───── 落盘（带重试 + 失败事件）─────
    def _save_with_retry(
        self,
        session_id: str,
        payload: Dict[str, Any],
    ) -> bool:
        """带重试的落盘。失败发 checkpoint/failed，成功发 checkpoint/saved。"""
        attempt = 0
        last_err: Optional[BaseException] = None
        while attempt <= self.max_retries:
            try:
                if self._local_base_dir:
                    global CHECKPOINT_BASE_DIR
                    # 局部覆盖：用 context manager-like 的方式临时改全局
                    # （简单实现：直接调 _save_payload 的副本逻辑）
                    bytes_written = self._save_to(self._local_base_dir, session_id, payload)
                else:
                    bytes_written = _save_payload(session_id, payload)
                # 成功 → 发 checkpoint/saved 事件
                _emit_event("checkpoint/saved", {
                    "session_id": session_id,
                    "bytes_written": bytes_written,
                    "mode": self.mode,
                    "attempt": attempt,
                })
                return True
            except Exception as e:  # noqa: BLE001 — checkpoint 容错边界
                last_err = e
                attempt += 1
                if attempt > self.max_retries:
                    break
                # 短暂退避（指数退避 50ms / 100ms / 200ms）
                time.sleep(0.05 * (2 ** (attempt - 1)))

        # 重试耗尽 → 发 checkpoint/failed 事件
        _emit_event("checkpoint/failed", {
            "session_id": session_id,
            "error": str(last_err)[:300] if last_err else "unknown",
            "error_type": type(last_err).__name__ if last_err else "Unknown",
            "retryable": True,
            "attempts": attempt,
            "max_retries": self.max_retries,
            "mode": self.mode,
        })
        return False

    def _save_to(self, base_dir: str, session_id: str, payload: Dict[str, Any]) -> int:
        """落盘到指定 base_dir（用于 _local_base_dir 覆盖场景）。"""
        os.makedirs(base_dir, exist_ok=True)
        path = os.path.join(base_dir, f"{session_id}.json")
        tmp = path + ".tmp"
        body = json.dumps(payload, ensure_ascii=False, indent=1)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(body)
            bytes_written = f.tell()
        os.replace(tmp, path)
        return bytes_written

    # ───── 恢复 ─────
    def recover(self, session_id: str) -> Optional[Dict[str, Any]]:
        """从磁盘恢复 checkpoint payload（进程崩溃后调用）。

        - 找到 <base_dir>/<session_id>.json 并读取
        - 发 checkpoint/recovered 事件（成功/失败都发）
        - 返回 payload（dict）；失败返回 None
        """
        try:
            payload = _load_payload(session_id) if not self._local_base_dir else \
                self._load_from(self._local_base_dir, session_id)
            ok = payload is not None
            _emit_event("checkpoint/recovered", {
                "session_id": session_id,
                "ok": ok,
                "bytes_read": len(json.dumps(payload)) if payload else 0,
                "mode": self.mode,
            })
            return payload
        except Exception as e:  # noqa: BLE001 — recover 必须容错
            _emit_event("checkpoint/recovered", {
                "session_id": session_id,
                "ok": False,
                "error": str(e)[:300],
                "mode": self.mode,
            })
            return None

    def _load_from(self, base_dir: str, session_id: str) -> Optional[Dict[str, Any]]:
        """从指定 base_dir 读取（用于 _local_base_dir 场景）。"""
        path = os.path.join(base_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ───── 辅助查询 ─────
    def stats(self) -> Dict[str, Any]:
        """返回当前策略状态（用于可观测性/调试）。"""
        with self._lock:
            return {
                "mode": self.mode,
                "max_events": self.max_events,
                "interval_sec": self.interval_sec,
                "active_sessions": len(self._states),
                "sessions": {
                    sid: {
                        "events": s["events"],
                        "last_checkpoint": s["last_checkpoint"],
                    }
                    for sid, s in self._states.items()
                },
            }


# ────────────────────────────────────────────────────────────
#  会话接入辅助（教学会话关键节点触发 checkpoint）
# ────────────────────────────────────────────────────────────
# 全局默认 policy（懒加载）
_DEFAULT_POLICY: Optional[CheckpointPolicy] = None


def get_default_policy() -> CheckpointPolicy:
    """获取全局默认 CheckpointPolicy（单例，按 config/checkpoint.json 初始化）。"""
    global _DEFAULT_POLICY
    if _DEFAULT_POLICY is None:
        cfg = _get_defaults()
        _DEFAULT_POLICY = CheckpointPolicy(
            mode=cfg.get("mode", "hybrid"),
            max_events=cfg.get("max_events", 10),
            interval_sec=cfg.get("interval_sec", 60),
            max_retries=cfg.get("max_retries", 3),
        )
    return _DEFAULT_POLICY


def checkpoint_session(
    session_id: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    mode: Optional[str] = None,
) -> bool:
    """便捷函数：用默认 policy 记录一次事件 + 触发判定。

    由 session_model.py 在 turn 完成/thread 创建等关键节点调用。
    """
    policy = get_default_policy()
    if mode:
        # 临时切换模式（不影响其他会话）
        old_mode = policy.mode
        policy.mode = mode
        try:
            return policy.record_event(session_id, payload=payload)
        finally:
            policy.mode = old_mode
    return policy.record_event(session_id, payload=payload)


def recover_session(session_id: str) -> Optional[Dict[str, Any]]:
    """便捷函数：从默认 policy 恢复。"""
    return get_default_policy().recover(session_id)


__all__ = [
    "PolicyMode", "CheckpointPolicy",
    "CHECKPOINT_BASE_DIR",
    "checkpoint_session", "recover_session", "get_default_policy",
]
