# -*- coding: utf-8 -*-
"""test_permission_custom_state.py — #20 Custom 衍生状态测试（Harness 30 项 P2）

覆盖：临时切换显示"自定义"（custom 衍生状态，不可作为目标保存）。
dsh Harness 借鉴（current() 返回 custom，commit 47f9438）：
custom 是衍生状态（临时组合），不是可保存的目标预设。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_custom_is_derived_state():
    """custom 是衍生状态：从标准切换派生，标记为自定义。"""
    from tool_registry import set_permission_preset, get_permission_preset
    set_permission_preset("standard")
    ok = set_permission_preset("custom")
    assert ok is True
    assert get_permission_preset() == "custom"


def test_custom_restores_all_tools():
    """custom 状态按 standard 语义（全工具，不锁写）——临时宽松组合。"""
    from tool_registry import is_tool_allowed_by_preset, set_permission_preset
    set_permission_preset("custom")
    # custom 临时组合 = standard 宽松语义（写工具允许）
    assert is_tool_allowed_by_preset("save_document") is True


def test_custom_cannot_be_target_in_presets():
    """custom 不在 PERMISSION_PRESETS 可保存目标中（衍生状态不可持久化目标）。"""
    from tool_registry import PERMISSION_PRESETS, set_permission_preset
    # custom 不是预设定义（是运行时衍生）
    assert "custom" not in PERMISSION_PRESETS


def test_switch_from_custom_back_to_real():
    """从 custom 切回真实预设（standard）正常。"""
    from tool_registry import set_permission_preset, get_permission_preset
    set_permission_preset("custom")
    ok = set_permission_preset("exam")
    assert ok is True
    assert get_permission_preset() == "exam"
    # exam 锁写（真实预设语义恢复）
    from tool_registry import is_tool_allowed_by_preset
    assert is_tool_allowed_by_preset("save_document") is False
