# -*- coding: utf-8 -*-
"""§3.81 P0-① 物料内容准确性评审门测试。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.material_judge import (
    DIMS, DEEP_CHECKS, judge_material, aggregate_judges,
)


class FakeLLM:
    name = "test_llm"

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kw):
        return ('{"dims": {"factuality": 5, "correctness": 4, "completeness": 4, '
                '"relevance": 5, "pedagogy": 4}, '
                '"deep_checks": {"person_binding": true, "literature": false, '
                '"cross_subject": true, "real_data": true, "analogy": true}}')


class BadLLM:
    name = "test_llm"

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kw):
        return "这不是 JSON"


def test_dims_and_deep_checks_defined():
    """S1：5 维评分 + 5 条深检定义完整。"""
    assert set(DIMS) == {"factuality", "correctness", "completeness", "relevance", "pedagogy"}
    assert set(DEEP_CHECKS) == {"person_binding", "literature", "cross_subject",
                                "real_data", "analogy"}


def test_judge_material_no_llm():
    """S2 边界：llm=None → 不评审但返回结构完整（不阻塞主流程）。"""
    r = judge_material("导数定义内容", "math", "高中", "lesson_plan", None)
    assert r["checked"] is False
    assert r["reason"]
    assert "dims" in r and "deep_checks" in r


def test_judge_material_empty():
    """S3 边界：空内容 → reason=空内容。"""
    r = judge_material("", "math", "高中", "lesson_plan", FakeLLM())
    assert r["reason"] == "空内容"


def test_judge_material_llm_success(monkeypatch):
    """S4 主路径：LLM 评审成功 → 5 维评分 + 深检解析正确。"""
    import subagents
    monkeypatch.setattr(subagents, "_safe_chat", lambda *a, **k: FakeLLM().chat())
    r = judge_material("导数定义：f'(x0)=lim...", "math", "高中", "lesson_plan", FakeLLM())
    assert r["checked"] is True
    assert r["dims"]["factuality"] == 5
    assert r["dims"]["correctness"] == 4
    assert r["deep_checks"]["person_binding"] is True
    assert r["deep_checks"]["literature"] is False
    assert r["overall"] == pytest.approx(4.4, abs=0.01)


def test_judge_material_llm_bad_json(monkeypatch):
    """S5 防御：LLM 返回非 JSON → 降级（不抛异常，reason 标注）。"""
    import subagents
    monkeypatch.setattr(subagents, "_safe_chat", lambda *a, **k: BadLLM().chat())
    r = judge_material("导数定义内容", "math", "高中", "lesson_plan", BadLLM())
    assert r["checked"] is False
    assert "非 JSON" in r["reason"] or "异常" in r["reason"]


def test_judge_material_llm_exception(monkeypatch):
    """S6 防御：LLM 抛异常 → 降级不崩。"""
    import subagents

    def _boom(*a, **k):
        raise RuntimeError("LLM 挂了")

    monkeypatch.setattr(subagents, "_safe_chat", _boom)
    r = judge_material("导数定义内容", "math", "高中", "lesson_plan", FakeLLM())
    assert r["checked"] is False
    assert "异常" in r["reason"]


def test_aggregate_judges_empty():
    """S7 聚合：无日志 → 空结构（不崩）。"""
    a = aggregate_judges()
    assert "total" in a
