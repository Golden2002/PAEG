# -*- coding: utf-8 -*-
"""§3.81 P2-② Manim 教学叙事复核测试。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.manim_judge import DIMS, judge_manim_narrative


class FakeLLM:
    name = "test_llm"

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kw):
        return ('{"dims": {"clarity": 4, "pedagogy": 5, "correctness": 4, "focus": 5}, '
                '"verdict": "pass"}')


class BadLLM:
    name = "test_llm"

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kw):
        return "不是 JSON"


def test_dims_defined():
    """S1：4 维评分定义完整。"""
    assert set(DIMS) == {"clarity", "pedagogy", "correctness", "focus"}


def test_judge_no_llm():
    """S2 边界：llm=None → 不评审（checked=False）。"""
    r = judge_manim_narrative("导数", "math", "class M(Scene): pass", "/tmp/x.mp4", None)
    assert r["checked"] is False
    assert r["reason"]


def test_judge_empty_code():
    """S3 边界：空代码 → reason=空代码。"""
    r = judge_manim_narrative("导数", "math", "", "/tmp/x.mp4", FakeLLM())
    assert r["reason"] == "空代码"


def test_judge_llm_success(monkeypatch):
    """S4 主路径：LLM 评审成功 → 4 维评分 + verdict。"""
    import subagents
    monkeypatch.setattr(subagents, "_safe_chat", lambda *a, **k: FakeLLM().chat())
    r = judge_manim_narrative("导数", "math", "class M(Scene): pass", "/tmp/x.mp4", FakeLLM())
    assert r["checked"] is True
    assert r["dims"]["clarity"] == 4
    assert r["dims"]["pedagogy"] == 5
    assert r["overall"] == pytest.approx(4.5, abs=0.01)
    assert r["verdict"] == "pass"


def test_judge_llm_bad_json(monkeypatch):
    """S5 防御：LLM 返回非 JSON → 降级（不崩）。"""
    import subagents
    monkeypatch.setattr(subagents, "_safe_chat", lambda *a, **k: BadLLM().chat())
    r = judge_manim_narrative("导数", "math", "class M(Scene): pass", "/tmp/x.mp4", BadLLM())
    assert r["checked"] is False
    assert "非 JSON" in r["reason"] or "异常" in r["reason"]


def test_judge_llm_exception(monkeypatch):
    """S6 防御：LLM 抛异常 → 降级不崩。"""
    import subagents

    def _boom(*a, **k):
        raise RuntimeError("LLM 挂了")

    monkeypatch.setattr(subagents, "_safe_chat", _boom)
    r = judge_manim_narrative("导数", "math", "class M(Scene): pass", "/tmp/x.mp4", FakeLLM())
    assert r["checked"] is False
    assert "异常" in r["reason"]
