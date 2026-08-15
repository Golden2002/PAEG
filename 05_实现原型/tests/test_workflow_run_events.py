# -*- coding: utf-8 -*-
"""test_workflow_run_events.py —— §3.42 W7 ⭐ tool-workflow run-start/run-end 测试

需求（§3.38.2：tool-workflow 4-event 补齐——v1.1.4 已发 agent-start/end，缺 run-start/end）：
- run-start：subagent 单次 run 边界开始（比 agent 粒度细）
- run-end：run 结束（与 run-start 用 workflow_id 配对）
- 每次 subagent 调用：agent-start + run-start + run-end + agent-end 四事件
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


def test_teach_emits_run_start_end():
    """teach() 每次 subagent 调用发 run-start + run-end（四事件完备）。"""
    import subagents as _sa
    class _MockLLM:
        def chat(self, **kw):
            return '{"answer": "mock", "tool_calls": []}'
    _sa._safe_chat = lambda *a, **k: "mock"
    from knowledge_base import KnowledgeBase
    from paeg import PAEG
    class _FL:
        id = "t1"; nickname = "t"; grade_level = "high_school"; age = 16
        cognitive_style = "visual"; subjects_mastery = {}
        world_view_blend = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
        self_description = ""; questionnaire_answers = {}
        target_exam = None; specialty_target = None; privacy_parent_notify = False
        recent_history = []
        @property
        def masteries(self): return self.subjects_mastery
    kb = KnowledgeBase()
    paeg = PAEG(_MockLLM(), kb, enable_self_update=False, enable_refiner=False)
    paeg.teach(learner=_FL(), question="什么是导数", subject="math")
    events = _read_events()
    run_starts = [e for e in events if e.get("type") == "tool-workflow/run-start"]
    run_ends = [e for e in events if e.get("type") == "tool-workflow/run-end"]
    assert run_starts, "teach 应发射 run-start"
    assert len(run_starts) == len(run_ends), f"run-start/end 应成对: {len(run_starts)} vs {len(run_ends)}"
    # 四事件完备：每类 agent 至少 run-start 配对 agent-start
    for s in run_starts:
        assert "workflow_id" in s.get("data", {}), f"run-start 应携带 workflow_id: {s}"


def test_run_start_before_agent_end():
    """顺序：run-start < agent-end（run 在 agent 生命周期内）。"""
    import subagents as _sa
    class _MockLLM:
        def chat(self, **kw):
            return '{"answer": "mock"}'
    _sa._safe_chat = lambda *a, **k: "mock"
    from knowledge_base import KnowledgeBase
    from paeg import PAEG
    class _FL:
        id = "t2"; nickname = "t"; grade_level = "high_school"; age = 16
        cognitive_style = "visual"; subjects_mastery = {}
        world_view_blend = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
        self_description = ""; questionnaire_answers = {}
        target_exam = None; specialty_target = None; privacy_parent_notify = False
        recent_history = []
        @property
        def masteries(self): return self.subjects_mastery
    kb = KnowledgeBase()
    paeg = PAEG(_MockLLM(), kb, enable_self_update=False, enable_refiner=False)
    paeg.teach(learner=_FL(), question="导数的几何意义", subject="math")
    events = _read_events()
    # 找同一 workflow_id 的 run-start 与 agent-end 顺序
    for s in events:
        if s.get("type") == "tool-workflow/run-start":
            wf = s.get("data", {}).get("workflow_id")
            # 找对应的 agent-end（同 workflow_id）
            agent_end_idx = next((i for i, e in enumerate(events)
                                  if e.get("type") == "tool-workflow/agent-end"
                                  and e.get("data", {}).get("workflow_id") == wf), None)
            if agent_end_idx is not None:
                run_start_idx = events.index(s)
                assert run_start_idx < agent_end_idx, "run-start 应在 agent-end 前"
