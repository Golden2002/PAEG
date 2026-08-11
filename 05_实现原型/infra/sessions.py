"""进程内学习会话存储。

v0.43 ⭐ P0 修复：SESSIONS 加 threading.RLock——并发写 chat_hist race 修复
（多 SSE 流/多线程同时 append 同一用户 chat_hist 时 list resize race，偶发 IndexError/丢消息）。
"""
from __future__ import annotations

import threading
from typing import Any, Dict

SESSIONS: Dict[str, Any] = {}
_LOCK = threading.RLock()  # v0.43 ⭐ 并发写守卫（RLock 可重入，防同线程递归死锁）


def get_learner(learner_id: str) -> Any:
    """返回学习者会话画像；不存在时返回 None。"""
    with _LOCK:
        return SESSIONS.get(f"learner_{learner_id}")


def get_chat_hist(learner_id: str) -> Any:
    """返回学习者聊天历史；不存在时返回空列表。"""
    with _LOCK:
        return list(SESSIONS.get(f"chat_hist_{learner_id}", []))


def append_chat_hist(learner_id: str, user_content: str, assistant_content: str = "") -> None:
    """v0.43 ⭐ 统一对话历史写回（各端点/routing 纠正分支共用）。

    - 此前 server.py 的 _append_chat_hist 只服务端用；routing.py（模式纠正分支）
      曾依赖 server 模块导致 services→server 反向依赖（已修复）。
    - 移到 infra.sessions（routing 已依赖本模块），server.py 保留薄封装。
    - 统一窗口 20 条（10 轮），与 teach/chat/answer 对齐。
    - v0.43 ⭐ P0：全程持锁（setdefault→append→截断→回写），并发安全。
    """
    try:
        with _LOCK:
            _ch = SESSIONS.setdefault(f"chat_hist_{learner_id}", [])
            if isinstance(_ch, list):
                _ch.append({"role": "user", "content": user_content})
                if assistant_content:
                    _ch.append({"role": "assistant", "content": assistant_content})
                SESSIONS[f"chat_hist_{learner_id}"] = _ch[-20:]
    except Exception as _che:
        print(f"[PAEG] {learner_id} 写回 chat_hist 失败: {_che}")


# ═══════════════════════════════════════════════════════════
# v0.51 ⭐ P0-2（Oracle）：SESSIONS 惰性 TTL 清理——防内存无限增长
# ═══════════════════════════════════════════════════════════
import time as _time

SESSIONS_TS: Dict[str, float] = {}
SESSIONS_TTL = 7200  # 2 小时滑动过期
_LAST_CLEAN = [0.0]
_CLEAN_INTERVAL = 300  # 每 5 分钟最多全扫一次


def session_touch(key: str) -> None:
    """记录键最近访问时间（滑动 TTL）。"""
    with _LOCK:
        SESSIONS_TS[key] = _time.time()


def session_cleanup(force: bool = False) -> int:
    """惰性清理过期会话键（超过 TTL 未访问的删除）。返回清理数。

    - 由 server.py before_request 每请求调用（内部限频 5 分钟一次全扫）
    - chat_hist 已有 LRU 20 条截断，此处清理的是 current_intent/conv_/constraint 等杂键
    """
    global _LAST_CLEAN
    _now = _time.time()
    if not force and _now - _LAST_CLEAN[0] < _CLEAN_INTERVAL:
        return 0
    _LAST_CLEAN[0] = _now
    removed = 0
    with _LOCK:
        _expired = [k for k, ts in SESSIONS_TS.items()
                    if _now - ts > SESSIONS_TTL]
        for k in _expired:
            SESSIONS.pop(k, None)
            SESSIONS_TS.pop(k, None)
            removed += 1
    return removed
