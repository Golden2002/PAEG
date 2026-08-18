# -*- coding: utf-8 -*-
"""test_permission_session_log.py — #19 Permission 事件入 Session Log 测试（Harness 30 项 P1）

覆盖：set_permission_preset 切换后向 session_log 发射 permission/preset 事件（可回放）。
dsh Harness 借鉴（permission/preset log-only 事件，commit 47f9438）：
权限切换写入会话日志，可回放审计。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_permission_switch_emits_event():
    """切换权限档 → session_log 出现 permission/preset 事件（可回放）。"""
    # 用 get_session_log() 单例——set_permission_preset 写入的正是此单例（缓存一致）
    from infra.session_log import get_session_log
    from tool_registry import set_permission_preset, get_permission_preset

    log = get_session_log()
    before = log.count()

    ok = set_permission_preset("exam")
    assert ok is True
    assert get_permission_preset() == "exam"

    # session_log 新增事件
    events = log.events(since_seq=before)
    perm_events = [e for e in events if e.get("type") == "permission/preset"]
    assert len(perm_events) >= 1, f"应有 permission/preset 事件，实际 {events}"
    # 事件数据含新 preset 与时间
    assert perm_events[-1]["data"]["preset"] == "exam"


def test_permission_event_records_previous_preset():
    """事件记录切换前 preset（回放审计需要 from→to）。"""
    from infra.session_log import get_session_log
    from tool_registry import set_permission_preset, get_permission_preset

    log = get_session_log()
    set_permission_preset("full")  # 建立基线
    before = log.count()
    set_permission_preset("read_only")
    events = log.events(since_seq=before)
    perm_events = [e for e in events if e.get("type") == "permission/preset"]
    assert len(perm_events) >= 1
    data = perm_events[-1]["data"]
    assert data["from"] == "full"
    assert data["to"] == "read_only"


def test_invalid_preset_no_event():
    """无效 preset 切换失败 → 不发射事件。"""
    from infra.session_log import get_session_log
    from tool_registry import set_permission_preset, get_permission_preset

    log = get_session_log()
    before = log.count()
    ok = set_permission_preset("no_such_preset")
    assert ok is False
    events = log.events(since_seq=before)
    perm_events = [e for e in events if e.get("type") == "permission/preset"]
    assert len(perm_events) == 0, "无效切换不应发射事件"
