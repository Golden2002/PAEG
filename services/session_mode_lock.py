# -*- coding: utf-8 -*-
"""services/session_mode_lock.py —— §3.44 PTC-2 ⭐ 模式决定工具集 + 会话级锁定（v1.1.5）

借鉴 dsh"模式决定工具集，会话一旦开始就不能切模式"（模式决定工具集，
中途换会导致新工具看不懂历史里的旧调用）。

设计：
- bind_session(sid, preset)：会话绑定模式
- switch_preset(sid, preset)：未活动可切换；活动后锁定返回 False
- mark_active(sid)：标记会话开始活动（教学/对话产生后）
- get_preset(sid)：当前会话模式（默认 standard）
- 与 tool_registry PERMISSION_PRESETS 联动（exam 锁写工具）
"""
from __future__ import annotations

import threading
from typing import Dict, Optional


class SessionModeLock:
    """会话级模式锁定：模式决定工具集，活动后不可切换。"""

    def __init__(self):
        self._lock = threading.RLock()
        # session_id -> {"preset": str, "active": bool}
        self._sessions: Dict[str, dict] = {}

    def bind_session(self, session_id: str, preset: str = "standard") -> None:
        """绑定会话模式（幂等：已绑定则保持）。"""
        with self._lock:
            self._sessions.setdefault(str(session_id), {"preset": preset, "active": False})

    def get_preset(self, session_id: str) -> str:
        """当前会话模式（未绑定 → standard）。"""
        with self._lock:
            s = self._sessions.get(str(session_id))
            return s["preset"] if s else "standard"

    def mark_active(self, session_id: str) -> None:
        """标记会话开始活动（教学/对话产生后调用——此后锁定模式）。"""
        with self._lock:
            sid = str(session_id)
            if sid not in self._sessions:
                self._sessions[sid] = {"preset": "standard", "active": False}
            self._sessions[sid]["active"] = True

    def is_active(self, session_id: str) -> bool:
        """会话是否已活动（锁定状态）。"""
        with self._lock:
            s = self._sessions.get(str(session_id))
            return bool(s and s["active"])

    def switch_preset(self, session_id: str, preset: str) -> bool:
        """切换会话模式。

        - 未活动：允许切换，返回 True
        - 已活动：锁定，返回 False（模式决定工具集，中途切换会导致
          新工具看不懂历史里的旧调用——dsh 语义）
        """
        with self._lock:
            sid = str(session_id)
            s = self._sessions.setdefault(sid, {"preset": "standard", "active": False})
            if s["active"]:
                return False
            s["preset"] = preset
            return True

    def switch_preset_with_msg(self, session_id: str, preset: str) -> str:
        """切换并返回消息（成功/锁定提示）。"""
        if self.switch_preset(session_id, preset):
            return f"模式已切换为 {preset}"
        return f"会话 {session_id} 已锁定（活动开始后不能切换模式，因模式决定工具集）"


__all__ = ["SessionModeLock"]
