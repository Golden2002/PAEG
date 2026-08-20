# -*- coding: utf-8 -*-
"""§3.79 Round 10 教学意图解读增强测试（detour 绕出 / revisit 绕回 约束注入）。

覆盖：
  topic_stack：detour 入栈带 summary → revisit 恢复可接续
  Presenter：learner._detour_note / _revisit_note 注入 system（LLM 知道会话路径），用后即清
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services import topic_stack


# ────────────────────────────────────────────
# topic_stack：detour 入栈 summary / revisit 恢复
# ────────────────────────────────────────────
def test_detour_push_keeps_summary():
    _h = []
    _h = topic_stack.push(_h, {"concept": "导数", "subject": "math", "intent": "teach",
                               "summary": "导数是瞬时变化率", "ts": 1.0})
    assert len(_h) == 1
    assert _h[0]["summary"] == "导数是瞬时变化率"


def test_revisit_recover_brings_summary_back():
    _h = []
    _h = topic_stack.push(_h, {"concept": "导数", "summary": "导数是瞬时变化率", "ts": 1.0})
    _h = topic_stack.push(_h, {"concept": "极限", "summary": "极限是趋近过程", "ts": 2.0})
    # 绕回"导数"→ 移到栈顶
    _h = topic_stack.recover(_h, "导数")
    assert _h[-1]["concept"] == "导数"
    assert _h[-1]["summary"] == "导数是瞬时变化率"
    _hit = topic_stack.find(_h, "导数")
    assert _hit is not None and _hit["summary"]


def test_detour_dedup_same_concept():
    _h = []
    _h = topic_stack.push(_h, {"concept": "导数", "summary": "s1", "ts": 1.0})
    _h = topic_stack.push(_h, {"concept": "极限", "summary": "s2", "ts": 2.0})
    _h = topic_stack.push(_h, {"concept": "导数", "summary": "s3", "ts": 3.0})
    assert len(_h) == 2  # 导数去重更新
    assert _h[-1]["concept"] == "导数"
    assert _h[-1]["summary"] == "s3"


# ────────────────────────────────────────────
# Presenter：detour/revisit 约束注入 system
# ────────────────────────────────────────────
def _make_presenter(captured: dict):
    from subagents import Presenter

    class _MockLLM:
        name = "test_llm"

        def chat(self, system=None, user=None, messages=None, max_tokens=512, **k):
            captured["system"] = system or ""
            captured["user"] = (messages[-1].get("content", "") if messages else "") or str(user or "")
            return "讲解内容"

    class _MockKB:
        def resolve_node(self, *a, **k):
            return None

        def get_subject(self, *a, **k):
            return None

        def get_humanity(self, *a, **k):
            return None

        def get_skill(self, *a, **k):
            return None

        def get_skill_by_name(self, *a, **k):
            return None

    return Presenter(model=_MockLLM(), kb=_MockKB())


class _Learner:
    grade_level = "high_school"
    nickname = "测试"
    _user_model = None
    _constraint_flags = ()
    _detour_note = ""
    _revisit_note = ""


def test_presenter_detour_note_injected():
    captured = {}
    p = _make_presenter(captured)
    _l = _Learner()
    _l._detour_note = "学生从「导数」暂时绕到当前话题：先完整回应新话题。"
    p.run({"topic": "什么是极限", "type": "present", "bloom": "understand"},
          _l, [], None, "什么是极限", "math")
    assert "detour 绕出" in captured["system"]
    assert "暂时绕到" in captured["system"]
    # 用后即清
    assert getattr(_l, "_detour_note", "") == ""


def test_presenter_revisit_note_injected():
    captured = {}
    p = _make_presenter(captured)
    _l = _Learner()
    _l._revisit_note = "学生绕回之前学的「导数」：先简要衔接上次内容，再继续推进。"
    p.run({"topic": "导数的应用", "type": "present", "bloom": "understand"},
          _l, [], None, "导数的应用", "math")
    assert "revisit 绕回" in captured["system"]
    assert "衔接上次内容" in captured["system"]
    assert getattr(_l, "_revisit_note", "") == ""


def test_presenter_no_notes_unchanged():
    captured = {}
    p = _make_presenter(captured)
    p.run({"topic": "什么是导数", "type": "present", "bloom": "understand"},
          _Learner(), [], None, "什么是导数", "math")
    assert "detour 绕出" not in captured["system"]
    assert "revisit 绕回" not in captured["system"]
    assert "认知层级" in captured["system"]


def test_detour_note_flexible_guidance_strategy():
    """§3.79 Round 11/12 策略：不强制拉回、柔性引导；问句成分完整（去 AI 味）。"""
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "server.py")
    src = open(_p, encoding="utf-8").read()
    # 柔性引导：提醒主线"随时告诉我" + 主动询问选择
    assert "柔性引导" in src
    # 完整句式（主语+状语+修饰语，用户示例风格），非省略句
    assert "我们接下来是继续学习这个新话题，还是回去接着刚才的内容学习？" in src
    assert "你随时告诉我你的想法就可以" in src
    # 不强制：明确"把选择权交给学生，不强迫"
    assert "不强迫" in src
    assert "不打断" in src
