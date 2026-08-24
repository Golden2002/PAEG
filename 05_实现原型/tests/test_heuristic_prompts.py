# -*- coding: utf-8 -*-
"""§3.106 heuristic_prompts 测试：7 情景 L1 沉思引导。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from heuristic_prompts import (HEURISTIC_PROMPTS, get_heuristic,
                               prepend_heuristic)


def test_seven_scenarios_registered():
    """H1：7 情景全部注册。"""
    assert set(HEURISTIC_PROMPTS.keys()) == {
        "teaching", "confide", "material", "answer", "method", "chat", "knowledge"}


def test_teaching_contains_5e():
    """H2：teaching L1 含 5E 阶段识别 + 苏格拉底。"""
    t = HEURISTIC_PROMPTS["teaching"]
    assert "5E" in t
    assert "苏格拉底" in t or "提问" in t


def test_confide_contains_eva():
    """H3：confide L1 含情绪验证分层（EVA）+ 避免过早建议。"""
    c = HEURISTIC_PROMPTS["confide"]
    assert "验证" in c
    assert "避免" in c and ("建议" in c or "解决方案" in c)


def test_material_contains_concept_analysis():
    """H4：material L1 含概念五问（是什么/不是什么/机制/例子/展示）。"""
    m = HEURISTIC_PROMPTS["material"]
    assert "不是" in m
    assert "核心机制" in m
    assert "展示" in m


def test_prepend_heuristic_idempotent():
    """H5：prepend 幂等（重复调用不叠加）。"""
    sys_p = "原 system"
    r1 = prepend_heuristic(sys_p, "teaching")
    r2 = prepend_heuristic(r1, "teaching")
    assert r1 == r2
    assert "先静下来沉思" in r1


def test_prepend_unknown_scenario():
    """H6：未知情景 → 原样返回。"""
    assert prepend_heuristic("原", "nope") == "原"
    assert get_heuristic("nope") == ""
