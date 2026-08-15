# -*- coding: utf-8 -*-
"""test_permission_presets.py —— §3.37 #18 ⭐ Permission Presets 双开关强化测试

Harness 模式（packages/interaction/permission-presets，commit 47f9438）：
- 三个 knob event：permission/preset（意图，log-only）+ sandbox/mode（执行）+ approval/policy（审批）
- 预设 = sandbox + approval 命名组合（一个选择器管两个开关）
- custom 是衍生状态不可作目标；切换写 permission/preset log-only 事件可回放
"""
from __future__ import annotations

import pytest


@pytest.fixture
def perm():
    from services.permission import PermissionService
    return PermissionService()


def test_preset_maps_to_two_knobs(perm):
    """预设 → sandbox + approval 双开关（一个选择器管两个开关）。"""
    assert perm.resolve("standard") == {"sandbox": "workspace-write", "approval": "ask"}
    assert perm.resolve("exam") == {"sandbox": "read-only", "approval": "never"}
    assert perm.resolve("full") == {"sandbox": "danger-full-access", "approval": "never"}


def test_apply_preset_writes_intent_event(perm):
    """切换预设 → 记录 permission/preset 意图事件（log-only，可回放）。"""
    perm.apply("exam", session="s1")
    events = perm.get_events("s1")
    assert any(e["type"] == "permission/preset" and e["data"]["preset"] == "exam"
               for e in events), "切换预设应记录 permission/preset 意图事件"
    assert any(e["type"] == "sandbox/mode" for e in events), "应记录 sandbox/mode knob"
    assert any(e["type"] == "approval/policy" for e in events), "应记录 approval/policy knob"


def test_effective_knobs_after_apply(perm):
    """应用预设后 → effective knobs 反映双开关状态。"""
    perm.apply("exam", session="s2")
    knobs = perm.get_effective_knobs("s2")
    assert knobs["sandbox"] == "read-only"
    assert knobs["approval"] == "never"


def test_custom_derived_state(perm):
    """knob 组合与所有预设不匹配 → custom 派生状态（不可作目标）。"""
    perm.apply("full", session="s3")
    # 手动改 sandbox（模拟外部 setter）→ 组合偏离 full 预设
    perm.set_sandbox("s3", "workspace-write")  # full 的 sandbox 是 danger-full-access
    current = perm.current_preset("s3")
    assert current == "custom", f"偏离预设组合应显示 custom，实际: {current}"


def test_custom_not_usable_as_target(perm):
    """custom 是衍生状态：不能作为切换目标。"""
    with pytest.raises(ValueError):
        perm.apply("custom", session="s4")


def test_preset_switch_replayable(perm):
    """permission/preset 事件可回放：重建状态与实时一致。"""
    perm.apply("standard", session="s5")
    perm.apply("exam", session="s5")
    events = perm.get_events("s5")
    # 重放：最后一条 preset 意图决定最终状态
    last_preset = [e for e in events if e["type"] == "permission/preset"][-1]
    final = perm.replay(session="s5", events=events)
    assert final == perm.get_effective_knobs("s5"), "重放状态应与实时状态一致"
    assert last_preset["data"]["preset"] == "exam"
