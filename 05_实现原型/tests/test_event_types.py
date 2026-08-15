# -*- coding: utf-8 -*-
"""test_event_types.py —— §3.37 H-1/H-12 ⭐ Session Event Log 类型化测试

Harness 模式（packages/core/session，commit 47f9438）：
- SessionEvent envelope：{type, seq, time, data, ignorable?, surfaceOp?}，seq=log.length
- 类型化：type 必须是已知 event type 之一（discriminated union over Literal）
- surface 事件（user/message、assistant/message、tool/result）必须带 surfaceOp
- 未知类型 → 拒绝（抛 ValueError）或 ignorable 跳过
"""
from __future__ import annotations

import pytest


def test_known_event_types_registered():
    """事件类型表已注册核心 + 插件事件。"""
    from infra.event_types import KNOWN_EVENT_TYPES
    assert "user/message" in KNOWN_EVENT_TYPES
    assert "assistant/message" in KNOWN_EVENT_TYPES
    assert "tool/result" in KNOWN_EVENT_TYPES
    assert "turn/start" in KNOWN_EVENT_TYPES
    assert "permission/preset" in KNOWN_EVENT_TYPES  # 插件事件
    assert "sandbox/mode" in KNOWN_EVENT_TYPES
    assert "approval/policy" in KNOWN_EVENT_TYPES


def test_make_event_envelope():
    """构造带 seq/time/data 的 event envelope。"""
    from infra.event_types import make_event
    ev = make_event("turn/start", {"turn": 1}, seq=0)
    assert ev["type"] == "turn/start"
    assert ev["seq"] == 0
    assert "time" in ev
    assert ev["data"] == {"turn": 1}


def test_surface_event_requires_surface_op():
    """surface 事件（user/message 等）必须带 surfaceOp，否则拒绝。"""
    from infra.event_types import make_event, SURFACE_EVENT_TYPES
    assert "user/message" in SURFACE_EVENT_TYPES
    with pytest.raises(ValueError):
        make_event("user/message", {"message": "hi"}, seq=1)  # 缺 surfaceOp
    ev = make_event("user/message", {"message": "hi"}, seq=1, surface_op="append")
    assert ev["surfaceOp"] == "append"


def test_unknown_event_type_rejected():
    """未知事件类型 → ValueError。"""
    from infra.event_types import make_event
    with pytest.raises(ValueError):
        make_event("no/such/event", {}, seq=0)


def test_emit_event_typed():
    """observability.emit_event 接入类型校验（非法类型拒绝）。"""
    from observability import emit_event_typed
    with pytest.raises(ValueError):
        emit_event_typed("bogus/event", seq=0, data={})
    # 合法类型可发
    emit_event_typed("turn/start", seq=1, data={"turn": 2})
