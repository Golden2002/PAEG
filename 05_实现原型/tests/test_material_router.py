# -*- coding: utf-8 -*-
"""§3.91 sse_presenter 单测：断言 SSE 事件字节级匹配现有契约（Oracle Step2）。"""
import io
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from sse_presenter import fmt_presentation, fmt_done, fmt_progress, fmt_error
from material_router import (ROUTER, is_material_intent, extract_topic,
                             route_material, MaterialRoute)


# ═══════════════════════════════════════════════════════════
# sse_presenter：字节级契约
# ═══════════════════════════════════════════════════════════
def test_presentation_event_format():
    """R1：presentation 事件格式 = 现 L1115 字串结构。"""
    s = fmt_presentation(1, "内容", "ppt")
    assert s.startswith("event: presentation\n")
    assert s.endswith("\n\n")
    d = json.loads(s.split("data: ", 1)[1].strip())
    assert d == {"step_id": 1, "content": "内容", "step_type": "ppt"}


def test_presentation_unicode_preserved():
    """R2：中文内容 ensure_ascii=False（不转义，前端可读）。"""
    s = fmt_presentation(1, "光合作用", "handout")
    assert "光合作用" in s
    assert "\\u" not in s


def test_done_event_format():
    """R3：done 事件含 status/mode/url 三字段。"""
    s = fmt_done("ppt", "/api/download/ppt/x.pptx")
    d = json.loads(s.split("data: ", 1)[1].strip())
    assert d == {"status": "completed", "mode": "ppt", "url": "/api/download/ppt/x.pptx"}


def test_done_no_url_default():
    """R4：done 无 url → 空串（与现 handout/video/mindmap/script 一致）。"""
    s = fmt_done("handout")
    d = json.loads(s.split("data: ", 1)[1].strip())
    assert d["url"] == ""


def test_progress_event():
    """R5：progress 事件 percent 四舍五入 + message。"""
    s = fmt_progress(50.25, "渲染中")
    d = json.loads(s.split("data: ", 1)[1].strip())
    assert d["percent"] in (50.2, 50.3)  # Python 银行家舍入 50.25→50.2
    assert d["message"] == "渲染中"
    s2 = fmt_progress(87.6, "")
    d2 = json.loads(s2.split("data: ", 1)[1].strip())
    assert d2["percent"] == 87.6


def test_error_event_is_done_channel():
    """R6：error 走 done 通道（前端统一处理），status=error。"""
    s = fmt_error("渲染失败")
    assert s.startswith("event: done\n")
    d = json.loads(s.split("data: ", 1)[1].strip())
    assert d["status"] == "error"


# ═══════════════════════════════════════════════════════════
# material_router：路由表 + 意图判定 + topic 提取
# ═══════════════════════════════════════════════════════════
def test_router_has_six_materials():
    """R7：ROUTER 表含 6 类物料（intent/step_type 一一对应）。"""
    assert set(ROUTER.keys()) == {"ppt", "handout", "video", "manim", "mindmap", "script"}
    for intent, route in ROUTER.items():
        assert route.intent == intent
        assert route.step_type == intent  # 契约：step_type = intent


def test_router_timeout_manim_longest():
    """R8：manim 超时最长（300s，渲染 2-5min），其他 ≤60s。"""
    assert ROUTER["manim"].timeout_sec == 300
    for intent, route in ROUTER.items():
        if intent != "manim":
            assert route.timeout_sec <= 60


def test_router_manim_uses_pipeline():
    """R9：仅 manim 走 MaterialPipeline（use_pipeline=True）。"""
    assert ROUTER["manim"].use_pipeline is True
    for intent, route in ROUTER.items():
        if intent != "manim":
            assert route.use_pipeline is False


def test_is_material_intent_whitelist():
    """R10：意图白名单判定。"""
    assert is_material_intent({"intent": "ppt"}) is True
    assert is_material_intent({"intent": "manim"}) is True
    assert is_material_intent({"intent": "lesson_prep"}) is False
    assert is_material_intent(None) is False
    assert is_material_intent({}) is False


def test_extract_topic_prefix_stripped():
    """R11：topic 提取剥离 '生成X：' 前缀（与旧 L1056 等价）。"""
    assert extract_topic({"matched_text": "生成PPT：光合作用"}, "") == "光合作用"
    assert extract_topic({"matched_text": "生成讲义：光合作用"}, "") == "光合作用"
    assert extract_topic({"matched_text": "生成数学动画：导数"}, "") == "导数"
    assert extract_topic({"matched_text": "生成思维导图：函数"}, "") == "函数"
    assert extract_topic({"matched_text": "生成讲稿：物理"}, "") == "物理"
    assert extract_topic({"matched_text": "生成教学视频：化学"}, "") == "化学"


def test_extract_topic_fallback():
    """R12：空 topic → fallback concept[:60]。"""
    assert extract_topic({"matched_text": "生成PPT："}, "光合作用") == "光合作用"
    long_concept = "光合作用" * 40
    assert len(extract_topic({"matched_text": ""}, long_concept)) <= 60


# ═══════════════════════════════════════════════════════════
# route_material：SSE 事件流完整性
# ═══════════════════════════════════════════════════════════
def test_route_material_yields_presentation_and_done():
    """R13：route_material 产出 presentation + done 两事件（契约）。"""
    magic = {"intent": "script", "reason": "magic:script",
             "matched_text": "生成讲稿：光合作用"}
    events = list(route_material(magic, llm=None, subject="生物",
                                 learner_id="test", concept="生成讲稿：光合作用"))
    assert len(events) == 2
    assert events[0].startswith("event: presentation\n")
    assert events[1].startswith("event: done\n")
    # done 的 mode = script
    d = json.loads(events[1].split("data: ", 1)[1].strip())
    assert d["mode"] == "script"


def test_route_material_unknown_intent():
    """R14：未知意图 → 只发 done（不崩）。"""
    events = list(route_material({"intent": "nope"}, llm=None, subject="x",
                                 learner_id="t", concept="x"))
    assert len(events) == 1
    assert events[0].startswith("event: done\n")
