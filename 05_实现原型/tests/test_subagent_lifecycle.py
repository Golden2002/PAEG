# -*- coding: utf-8 -*-
"""test_subagent_lifecycle.py —— §3.38 A2 ⭐ H-4 subagent 生命周期事件测试

Harness 模式（core/session known-event-types + tool-workflow，commit 47f9438）：
- subagent/descriptor：构造时发射（name/model/kb_ref）
- tool-workflow/agent-start + agent-end：每个 subagent .run() 前后成对发射（runId UUID 配对）
- hook/invoked + hook/result：hooks_hub.run_hook() 前后发射
- 事件必须通过 infra.event_types.make_event() 校验（未知类型拒绝）

当前（v1.1.3）缺陷：事件类型已定义（infra/event_types.py L45-47）但零发射。
"""
from __future__ import annotations

import json
import os
import uuid

import pytest


def _read_events():
    """读取 events.jsonl（observability 事件流）。"""
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
def _clean_events(tmp_path, monkeypatch):
    """隔离事件文件：测试前备份原 events.jsonl，测试后还原。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "events.jsonl")
    backup = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            backup = f.read()
    # 清空事件文件（隔离测试）
    if os.path.exists(path):
        os.remove(path)
    yield
    # 还原
    if backup is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(backup)


def _make_paeg(monkeypatch, tmp_path):
    """构造一个最小 PAEG 实例（mock LLM，避免真实调用）。"""
    import subagents as _sa
    from knowledge_base import KnowledgeBase

    class _MockLLM:
        def chat(self, **kw):
            return json.dumps({"answer": "mock 回答", "tool_calls": []})

    monkeypatch.setattr(_sa, "_safe_chat", lambda *a, **k: "mock")
    kb = KnowledgeBase()
    from paeg import PAEG
    paeg = PAEG(_MockLLM(), kb, enable_self_update=False, enable_refiner=False)
    return paeg


def test_subagent_descriptor_on_construction(monkeypatch, tmp_path):
    """PAEG 构造时应对每个 subagent 发射 subagent/descriptor 事件。"""
    paeg = _make_paeg(monkeypatch, tmp_path)
    events = _read_events()
    descriptors = [e for e in events if e.get("type") == "subagent/descriptor"]
    assert len(descriptors) >= 8, f"应至少 8 个 subagent/descriptor 事件，实际 {len(descriptors)}"
    names = {d.get("data", {}).get("name") for d in descriptors}
    assert "diagnostor" in names and "presenter" in names, f"应含关键 subagent，实际: {names}"


def test_teach_emits_agent_start_end(monkeypatch, tmp_path):
    """teach() 对每个调用的 subagent 发射 agent-start → agent-end 对。"""
    # 清空事件文件（防测试间污染——teach 构造可能触发其他事件）
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ev_path = os.path.join(base, "events.jsonl")
    if os.path.exists(ev_path):
        os.remove(ev_path)
    paeg = _make_paeg(monkeypatch, tmp_path)
    # 触发一次教学（mock LLM 返回）
    paeg.teach(learner=_FakeLearner(), question="什么是导数", subject="math")
    events = _read_events()
    starts = [e for e in events if e.get("type") == "tool-workflow/agent-start"]
    ends = [e for e in events if e.get("type") == "tool-workflow/agent-end"]
    assert starts, "teach 应发射 agent-start 事件"
    # 关键教学 agent（diagnostor/planner/presenter/evaluator）至少各一对
    start_agents = {e.get("data", {}).get("agent") for e in starts}
    for key_agent in ("diagnostor", "planner", "presenter", "evaluator"):
        assert key_agent in start_agents, f"关键 agent {key_agent} 应有 start 事件"
        a_start = [e for e in starts if e.get("data", {}).get("agent") == key_agent]
        a_end = [e for e in ends if e.get("data", {}).get("agent") == key_agent]
        assert a_start, f"{key_agent} 应有 start"
        assert len(a_start) == len(a_end), f"{key_agent} start/end 应成对: {len(a_start)} vs {len(a_end)}"


def test_workflow_subagent_emits_start_end(monkeypatch, tmp_path):
    """workflows_hub._run_subagent 发射 agent-start/end。"""
    from workflows_hub import WorkflowsHub, WorkflowStep

    class _FakeSub:
        def run(self, llm, inp, **kw):
            return {"content": "mock"}

    class _FakePaeg:
        presenter = _FakeSub()

    monkeypatch.setattr("infra.runtime.get_paeg", lambda: _FakePaeg())
    monkeypatch.setattr("infra.runtime.get_llm", lambda: object())
    hub = WorkflowsHub()
    st = WorkflowStep(step_id="s1", step_type="subagent", agent="presenter", config={})
    try:
        hub._run_subagent(st, {"topic": "x", "subject": "math"}, {})
    except Exception as e:
        print(f"  (调用异常但事件应已发射: {e})")
    events = _read_events()
    starts = [e for e in events if e.get("type") == "tool-workflow/agent-start"]
    ends = [e for e in events if e.get("type") == "tool-workflow/agent-end"]
    assert starts, "_run_subagent 应发射 agent-start"
    assert ends, "_run_subagent 应发射 agent-end"


def test_hooks_hub_emits_invoked_result(monkeypatch, tmp_path):
    """hooks_hub.run_hook 发射 hook/invoked → hook/result。"""
    from hooks_hub import HooksHub
    hub = HooksHub()
    # 注册一个简单 hook（用内置 log_hook）
    hub.add_hook({"event": "tool.before", "module": "hooks_hub", "function": "log_hook", "id": "t1"})
    hub.run_hook("tool.before", {"tool": "web_search"})
    events = _read_events()
    invoked = [e for e in events if e.get("type") == "hook/invoked"]
    results = [e for e in events if e.get("type") == "hook/result"]
    assert invoked, "run_hook 应发射 hook/invoked"
    assert results, "run_hook 应发射 hook/result"


def test_event_seq_monotonic(monkeypatch, tmp_path):
    """同一教学会话内事件 seq 严格递增。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ev_path = os.path.join(base, "events.jsonl")
    if os.path.exists(ev_path):
        os.remove(ev_path)
    paeg = _make_paeg(monkeypatch, tmp_path)
    paeg.teach(learner=_FakeLearner(), question="牛顿第二定律是什么", subject="physics")
    events = _read_events()
    seqs = [e.get("seq", -1) for e in events]
    assert len(seqs) > 0
    assert all(b >= a for a, b in zip(seqs, seqs[1:])), "seq 应单调不减"


def test_agent_start_payload_has_run_id(monkeypatch, tmp_path):
    """tool-workflow/agent-start 携带 run_id（UUID 配对 start/end）。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ev_path = os.path.join(base, "events.jsonl")
    if os.path.exists(ev_path):
        os.remove(ev_path)
    paeg = _make_paeg(monkeypatch, tmp_path)
    paeg.teach(learner=_FakeLearner(), question="什么是导数", subject="math")
    events = _read_events()
    starts = [e for e in events if e.get("type") == "tool-workflow/agent-start"]
    assert starts, "应有 agent-start 事件"
    for s in starts:
        rid = s.get("data", {}).get("run_id")
        assert rid, f"agent-start 应携带 run_id: {s}"


class _FakeLearner:
    """最小学习者（测试用）。"""
    id = "test_learner"
    nickname = "测试"
    grade_level = "high_school"
    age = 16
    cognitive_style = "visual"
    subjects_mastery = {}
    world_view_blend = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
    self_description = ""
    questionnaire_answers = {}
    target_exam = None
    specialty_target = None
    privacy_parent_notify = False

    @property
    def masteries(self):
        return self.subjects_mastery
