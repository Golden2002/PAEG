"""进程内学习会话存储。"""
from __future__ import annotations

from typing import Any, Dict


SESSIONS: Dict[str, Any] = {}


def get_learner(learner_id: str) -> Any:
    """返回学习者会话画像；不存在时返回 None。"""
    return SESSIONS.get(f"learner_{learner_id}")


def get_chat_hist(learner_id: str) -> Any:
    """返回学习者聊天历史；不存在时返回空列表。"""
    return SESSIONS.get(f"chat_hist_{learner_id}", [])
