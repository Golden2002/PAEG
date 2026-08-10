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


def append_chat_hist(learner_id: str, user_content: str, assistant_content: str = "") -> None:
    """v0.43 ⭐ 统一对话历史写回（各端点/routing 纠正分支共用）。

    - 此前 server.py 的 _append_chat_hist 只服务端用；routing.py（模式纠正分支）
      曾依赖 server 模块导致 services→server 反向依赖（已修复）。
    - 移到 infra.sessions（routing 已依赖本模块），server.py 保留薄封装。
    - 统一窗口 20 条（10 轮），与 teach/chat/answer 对齐。
    """
    try:
        _ch = SESSIONS.setdefault(f"chat_hist_{learner_id}", [])
        if isinstance(_ch, list):
            _ch.append({"role": "user", "content": user_content})
            if assistant_content:
                _ch.append({"role": "assistant", "content": assistant_content})
            SESSIONS[f"chat_hist_{learner_id}"] = _ch[-20:]
    except Exception as _che:
        print(f"[PAEG] {learner_id} 写回 chat_hist 失败: {_che}")
