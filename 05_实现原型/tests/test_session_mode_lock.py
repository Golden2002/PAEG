# -*- coding: utf-8 -*-
"""test_session_mode_lock.py —— §3.44 PTC-2 ⭐ 模式决定工具集 + 会话级锁定测试

需求（§3.44 PTC-2，借鉴 dsh"模式决定工具集，会话开始后不能切模式"）：
- 每会话绑定 preset（模式）
- 会话一旦开始（有 tool_call 记录）→ 锁定 preset，不能切换
- 未开始会话 → 可切换 preset
- 锁定后切模式返回 False + 提示
"""
from __future__ import annotations

import pytest


@pytest.fixture
def lock():
    from services.session_mode_lock import SessionModeLock
    return SessionModeLock()


def test_session_binds_preset(lock):
    """会话绑定 preset。"""
    lock.bind_session("ses_1", "exam")
    assert lock.get_preset("ses_1") == "exam"
    # 默认 standard
    assert lock.get_preset("ses_new") == "standard"


def test_switch_before_start_ok(lock):
    """会话未开始 → 可切换 preset。"""
    lock.bind_session("ses_2", "standard")
    assert lock.switch_preset("ses_2", "exam") is True, "未开始会话应可切换"
    assert lock.get_preset("ses_2") == "exam"


def test_lock_after_activity(lock):
    """会话开始（有活动）→ 锁定，不能切换。"""
    lock.bind_session("ses_3", "standard")
    lock.mark_active("ses_3")  # 开始活动
    assert lock.switch_preset("ses_3", "exam") is False, "活动后应锁定"
    assert lock.get_preset("ses_3") == "standard", "锁定后 preset 不变"


def test_lock_blocks_tool_switch(lock):
    """锁定后切模式返回 False（阻止）。"""
    lock.bind_session("ses_4", "exam")
    lock.mark_active("ses_4")
    assert lock.switch_preset("ses_4", "full") is False
    # 返回提示信息
    blocked = lock.switch_preset_with_msg("ses_4", "full")
    assert "锁定" in blocked or "不能切换" in blocked, f"应返回锁定提示: {blocked}"


def test_integration_tool_registry():
    """集成：会话模式决定工具集（exam 锁写工具）。"""
    import tool_registry
    from services.session_mode_lock import SessionModeLock
    lock = SessionModeLock()
    lock.bind_session("ses_5", "exam")
    # exam 模式：写工具被锁
    tool_registry.set_permission_preset("exam")
    assert not tool_registry.is_tool_allowed_by_preset("generate_handout"), "exam 应锁写工具"
    # 恢复
    tool_registry.set_permission_preset("standard")
