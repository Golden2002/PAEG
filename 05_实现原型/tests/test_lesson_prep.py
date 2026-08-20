# -*- coding: utf-8 -*-
"""§3.69 备课 subagent（LessonPrep）测试面。

覆盖：类存在 / 质量标准形状 / 系统提示词 / 输入校验 / 魔法词 /
路由意图 / registry 10 subagent / 主类持有 / token 预算 / run 键集 /
无 LLM 兜底 / SSE 路由链路。
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from subagents import LessonPrep, LessonPlanInput
from prompts import (
    LESSON_PLANNER_QUALITY_CRITERIA,
    build_lesson_planner_system,
    is_lesson_plan_input_valid,
)
from magic_intent import match_magic
from meta_router import VALID_INTENTS, rule_fallback_intent
from infra.subagent_registry import get_default_registry


class MockLLM:
    """模拟真实 LLM（name 非 'mock'，chat 返回固定 JSON/Markdown）。"""

    name = "test_llm"

    def __init__(self, respond_json=True):
        self._respond_json = respond_json

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kwargs):
        u = ""
        if messages:
            u = messages[-1].get("content", "") if isinstance(messages[-1], dict) else str(messages[-1])
        elif user:
            u = str(user)
        if "教学骨架" in u or "教案" in u or "完整教案" in u:
            return json.dumps({
                "framework": "5E",
                "objectives_3d": {"knowledge": ["能列举"], "ability": ["能分析"], "literacy": ["能设计"]},
                "key_points": [{"point": "k1", "reason": "r1"}, {"point": "k2", "reason": "r2"}],
                "difficult_points": [{"point": "d1", "reason": "dr1", "breakthrough": "b1"}],
                "sections": [{"name": "导入", "teacher_activity": "t", "student_activity": "s",
                              "design_intent": "i", "duration": "5min"}] * 5,
                "blackboard": {"main": "主区", "aux": "辅区"},
                "reflection": ["改进1", "改进2", "改进3"],
            }, ensure_ascii=False)
        if "PPT" in u or "课件" in u or "ppt" in u:
            return json.dumps([{"page": 1, "title": "t", "key_points": ["a"],
                                "visual_focus": "图", "layout": "左→右"}], ensure_ascii=False)
        return "这是讲义内容。" if self._respond_json else "讲义兜底"


class MockKB:
    pass


@pytest.fixture
def lesson_prep():
    return LessonPrep(model=MockLLM(), kb=MockKB())


def test_lesson_prep_class_exists():
    lp = LessonPrep(model=None, kb=None)
    assert lp is not None
    inp = LessonPlanInput(topic="光合作用")
    assert inp.topic == "光合作用"
    assert inp.progressive is True
    assert inp.duration_min == 45


def test_lesson_planner_quality_criteria_shape():
    assert "lesson_plan" in LESSON_PLANNER_QUALITY_CRITERIA
    assert "slides" in LESSON_PLANNER_QUALITY_CRITERIA
    assert "video_script" in LESSON_PLANNER_QUALITY_CRITERIA
    assert "hard_checks" in LESSON_PLANNER_QUALITY_CRITERIA
    assert len(LESSON_PLANNER_QUALITY_CRITERIA["hard_checks"]) == 15


def test_lesson_planner_system_prompt():
    s = build_lesson_planner_system("光合作用", "biology", "high_school")
    assert isinstance(s, str) and len(s) > 200
    assert "备课" in s or "光合作用" in s


def test_lesson_plan_input_valid():
    assert is_lesson_plan_input_valid({"topic": "光合作用", "subject": "biology",
                                       "grade": "high_school"}) == []
    errs = is_lesson_plan_input_valid({"topic": "", "subject": "biology", "grade": "high_school"})
    assert any("topic" in e for e in errs)


def test_magic_intent_lesson_prep():
    r = match_magic("我要备课")
    assert r is not None and r["intent"] == "lesson_prep"
    r2 = match_magic("我要备课：光合作用")
    assert r2 is not None and r2["intent"] == "lesson_prep"
    assert match_magic("你好") is None
    assert match_magic("什么是导数") is None
    # §3.73 ⭐ 独立激活词：变体不匹配（用户要求只认"我要备课"）
    assert match_magic("帮我备课") is None


def test_meta_router_lesson_prep_intent():
    assert "lesson_prep" in VALID_INTENTS
    r = rule_fallback_intent("我要备课")
    assert r is not None and r.get("intent") == "lesson_prep"
    # §3.73 ⭐ 独立激活词：变体不再触发 lesson_prep
    r2 = rule_fallback_intent("帮我备一下高中物理导数课")
    assert r2 is None or r2.get("intent") != "lesson_prep"


def test_registry_lists_10_subagents():
    reg = get_default_registry()
    names = reg.list()
    assert "lesson_prep" in names
    assert len(names) == 10


def test_paeg_holds_lesson_prep():
    from unittest.mock import MagicMock
    from paeg import PAEG
    from knowledge_base import KnowledgeBase
    p = PAEG(MagicMock(), KnowledgeBase(), enable_self_update=False, enable_refiner=False)
    assert p.lesson_prep is not None


def test_lesson_prep_run_token_budget():
    from subagents import _LESSON_PLAN_BUDGET_MAX
    assert _LESSON_PLAN_BUDGET_MAX == 25000


def test_lesson_prep_run_returns_keys(lesson_prep):
    inp = LessonPlanInput(topic="光合作用", subject="biology", grade="high_school")
    res = lesson_prep.run(inp)
    for k in ("lesson_plan", "handout", "script", "ppt_outline",
              "video_script", "mindmap", "quality_report", "token_used", "mode"):
        assert k in res, f"缺少键 {k}"
    assert res["mode"] == "lesson_prep"


def test_lesson_prep_run_fallback_no_llm():
    lp = LessonPrep(model=type("M", (), {"name": "mock"})(), kb=MockKB())
    inp = LessonPlanInput(topic="光合作用")
    res = lp.run(inp)
    # 兜底路径核心：无论 LLM 是否可用，返回结构完整（含全部键）
    for k in ("lesson_plan", "handout", "script", "ppt_outline",
              "video_script", "mindmap", "quality_report", "token_used", "mode"):
        assert k in res
    assert res["mode"] == "lesson_prep"


def test_lesson_prep_run_quality_report(lesson_prep):
    inp = LessonPlanInput(topic="光合作用")
    res = lesson_prep.run(inp)
    qr = res["quality_report"]
    assert isinstance(qr, dict)
    assert "overall" in qr or "lesson_plan_score" in qr


def test_magic_intent_lesson_prep_independent_activation():
    """§3.73 ⭐ '我要备课'独立激活词（ULW 风格）——只认该词，不做变体匹配。"""
    cases = [
        ("我要备课", True),                # 纯词 → 引导
        ("我要备课：光合作用", True),       # 带需求 → 直接生成
        ("我要备课 高中数学函数单调性45分钟", True),
        ("帮我备课", False),                # 变体不匹配
        ("备课：导数", False),               # 变体不匹配
        ("备一下课", False),
        ("你好", False),
        ("我要备课：", False),              # 退化：空后缀
    ]
    for text, expect_hit in cases:
        r = match_magic(text)
        assert (r is not None) == expect_hit, f"{text!r}: 期望命中={expect_hit}, 实际 {r}"
        if expect_hit:
            assert r["intent"] == "lesson_prep"

