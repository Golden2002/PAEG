# -*- coding: utf-8 -*-
"""test_trace_id.py —— §3.42 W2 ⭐ observability trace_id 全链路测试

需求（§二 Step 1.5 P1-4 trace_id）：
- SessionEvent envelope 加 trace_id（chat 入口生成 UUID）
- contextvars 跨层传播（子 span 嵌套：chat → turn → span）
- 并发请求独立 trace（无串扰）
- events.jsonl 中 trace_id 出现率 >= 80%
"""
from __future__ import annotations

import json
import os
import threading

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


def test_trace_id_generated_on_request():
    """chat 入口生成 trace_id，事件携带。"""
    from obs_trace import begin_trace, get_trace_id, end_trace
    from observability import emit_event_typed
    tid = begin_trace("chat")
    try:
        assert tid is not None, "begin_trace 应生成 trace_id"
        assert get_trace_id() == tid, "get_trace_id 应返回当前 trace"
        emit_event_typed("turn/start", data={"turn": 1})
    finally:
        end_trace()
    events = _read_events()
    assert events, "应发射事件"
    assert events[0].get("data", {}).get("trace_id") == tid, "事件应携带 trace_id"


def test_child_span_nested():
    """子 span 嵌套：parent_id 关联。"""
    from obs_trace import begin_trace, begin_span, end_span, end_trace, get_trace_id
    tid = begin_trace("teach")
    try:
        span = begin_span("diagnostor")
        assert span is not None
        assert get_trace_id() == tid, "子 span 内 trace_id 不变"
        end_span(span)
    finally:
        end_trace()


def test_thread_isolation():
    """并发线程独立 trace（无串扰）。"""
    from obs_trace import begin_trace, end_trace, get_trace_id
    results = {}

    def worker(name):
        tid = begin_trace(name)
        try:
            results[name] = get_trace_id()
        finally:
            end_trace()

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert results["A"] != results["B"], "不同线程 trace_id 应独立"
    assert results["A"] and results["B"]


def test_trace_id_in_events_high_coverage():
    """真实教学场景：trace_id 出现率 >= 80%。"""
    import subagents as _sa
    class _MockLLM:
        def chat(self, **kw):
            return '{"answer": "mock"}'
    _sa._safe_chat = lambda *a, **k: "mock"
    from obs_trace import begin_trace, end_trace
    from knowledge_base import KnowledgeBase
    from paeg import PAEG
    class _FL:
        id = "t3"; nickname = "t"; grade_level = "high_school"; age = 16
        cognitive_style = "visual"; subjects_mastery = {}
        world_view_blend = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
        self_description = ""; questionnaire_answers = {}
        target_exam = None; specialty_target = None; privacy_parent_notify = False
        recent_history = []
        @property
        def masteries(self): return self.subjects_mastery
    kb = KnowledgeBase()
    tid = begin_trace("teach_e2e")
    try:
        paeg = PAEG(_MockLLM(), kb, enable_self_update=False, enable_refiner=False)
        paeg.teach(learner=_FL(), question="牛顿第二定律", subject="physics")
    finally:
        end_trace()
    events = _read_events()
    assert len(events) > 5, f"应有足够事件，实际 {len(events)}"
    with_trace = [e for e in events if e.get("data", {}).get("trace_id")]
    ratio = len(with_trace) / len(events)
    assert ratio >= 0.8, f"trace_id 覆盖率应 >= 80%，实际 {ratio:.0%}"
