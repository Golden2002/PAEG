# -*- coding: utf-8 -*-
"""test_invariants.py —— §3.42 W10 ⭐ runtime-diagnostics invariants 测试

需求（§3.38.2 runtime-diagnostics invariants，借鉴 deepseek-harness）：
- 4 条运行时不变式：no_orphan_trace（无孤儿 trace）/ permission_boundary_intact
  （权限边界完好）/ config_reload_succeeded（配置重载成功）/ subagent_provider_registered
  （subagent provider 已注册）
- 违规 → 发 audit.violation 事件 + metric 计数
"""
from __future__ import annotations

import json
import os

import pytest


def _read_events():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "events.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


@pytest.fixture(autouse=True)
def _clean_events(tmp_path):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ev_path = os.path.join(base, "events.jsonl")
    backup = None
    if os.path.exists(ev_path):
        with open(ev_path, encoding="utf-8") as f:
            backup = f.read()
        os.remove(ev_path)
    yield
    if backup is not None:
        with open(ev_path, "w", encoding="utf-8") as f:
            f.write(backup)


def test_no_orphan_trace_invariant():
    """无孤儿 trace：每事件 trace_id 要么存在要么全缺（不混用）。"""
    from obs_invariants import check_no_orphan_trace
    # 正常场景（有 trace）→ 通过
    from obs_trace import begin_trace, end_trace
    from observability import emit_event_typed
    tid = begin_trace("test")
    try:
        emit_event_typed("turn/start", data={"turn": 1})
    finally:
        end_trace()
    events = _read_events()
    ok, detail = check_no_orphan_trace(events)
    assert ok is True, f"有 trace 的事件不应判孤儿: {detail}"


def test_permission_boundary_intact():
    """权限边界完好：exam 模式写工具被锁。"""
    from obs_invariants import check_permission_boundary
    import tool_registry
    tool_registry.set_permission_preset("exam")
    try:
        ok = check_permission_boundary()
        assert ok is True, "exam 模式写工具应被锁（边界完好）"
    finally:
        tool_registry.set_permission_preset("standard")


def test_subagent_provider_registered():
    """subagent provider 已注册（9 个核心都存在）。"""
    from obs_invariants import check_subagent_registered
    ok, missing = check_subagent_registered()
    assert ok is True, f"应有 9 个核心 subagent，缺失: {missing}"


def test_violation_emits_audit_event():
    """违规 → 发 audit.violation 事件。"""
    from obs_invariants import report_violation
    report_violation("test_invariant", "演示违规")
    events = _read_events()
    viol = [e for e in events if e.get("type") == "audit/violation"]
    assert viol, "应发 audit/violation 事件"
