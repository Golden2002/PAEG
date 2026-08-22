# -*- coding: utf-8 -*-
"""services/idempotency.py —— §3.79 Round 12 ⭐ Attempt Token 幂等护栏（Codex Harness 借鉴 A11）

背景（OpenAI Codex Harness 2026-08-21 开源借鉴）：agent 执行应带 attempt token——
重复提交（网络重试/前端连点/超时重发）不重复扣费、不重复写、不重复触发副作用。

PAEG 场景：teach_stream/chat_stream/answer 等写操作端点，同 (learner_id, attempt_token)
在短窗口内重复请求 → 返回"处理中/已完成"提示，不重新生成（省 LLM 调用、防重复落盘）。

设计：
- 内存滑动窗口（线程安全），默认 TTL 90s（一次教学流的合理窗口）
- 客户端携带 X-Attempt-Token 头（或请求体 attempt_token 字段）；不携带则跳过（向后兼容）
- 首次请求：记录 attempt_token -> (status="processing", ts)
- 重复请求：若仍在窗口内 → 返回 already_processing（不执行）
- TTL 过期后自动清理（惰性）
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional

_ATTEMPTS: Dict[str, Dict] = {}
_LOCK = threading.Lock()
_TTL = 90.0  # 秒（一次教学流窗口）


def _key(learner_id: str, token: str) -> str:
    return f"{learner_id}::{token}"


def begin_attempt(learner_id: str, token: str, ttl: float = _TTL) -> bool:
    """尝试登记 attempt。返回 True=首次（允许执行）；False=窗口内重复（应短路）。

    Codex Harness 借鉴：attempt token 幂等——重复提交不重复执行。
    """
    if not token:
        return True  # 无 token → 不参与幂等（向后兼容）
    now = time.time()
    with _LOCK:
        _cleanup_locked(now)
        k = _key(learner_id, token)
        if k in _ATTEMPTS and now - _ATTEMPTS[k]["ts"] < ttl:
            return False  # 重复
        _ATTEMPTS[k] = {"ts": now, "status": "processing"}
        return True


def finish_attempt(learner_id: str, token: str) -> None:
    """attempt 完成后标记完成（窗口内再查可提示'已完成'）。"""
    if not token:
        return
    with _LOCK:
        k = _key(learner_id, token)
        if k in _ATTEMPTS:
            _ATTEMPTS[k]["status"] = "completed"


def attempt_status(learner_id: str, token: str) -> Optional[str]:
    """查询 attempt 状态（processing/completed/None）。"""
    if not token:
        return None
    with _LOCK:
        _cleanup_locked(time.time())
        _a = _ATTEMPTS.get(_key(learner_id, token))
        return (_a or {}).get("status")


def _cleanup_locked(now: float) -> None:
    """惰性清理过期 attempt（持锁调用）。"""
    _expired = [k for k, v in _ATTEMPTS.items() if now - v["ts"] > _TTL]
    for k in _expired:
        _ATTEMPTS.pop(k, None)


__all__ = ["begin_attempt", "finish_attempt", "attempt_status", "_TTL"]
