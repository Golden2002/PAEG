# -*- coding: utf-8 -*-
"""§3.79 Round 4 ⭐ 学习方法咨询/学习计划鲁棒性修复回归测试。

find_fault_e2e 真实运行日志暴露：`[PAEG][method.py] 学习计划分流异常，
走普通方法咨询: unsupported format string passed to dict.__format__`
——planner.design_phases 对 subjects_mastery 的值做 `f"{v:.2f}"`，
但画像掌握度数据结构不统一（有的学科是 float，有的是嵌套 dict），
dict 值触发 format 异常 → 学习计划整条链路静默回退。

守卫：
  - _fmt_mastery：float/dict/str/None 四种值均不抛异常
  - design_phases 在 mastery 含 dict 值时仍能构造 system（不异常）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_fmt_mastery_float():
    from services.planner import _fmt_mastery
    assert _fmt_mastery(0.8) == "0.80"
    assert _fmt_mastery(0) == "0.00"


def test_fmt_mastery_dict():
    """dict 值（嵌套结构）必须鲁棒格式化（Round 4 修复的核心场景）。"""
    from services.planner import _fmt_mastery
    assert _fmt_mastery({"level": 0.8}) == "0.80"
    assert _fmt_mastery({"level": "0.6"}) != "?"  # 字符串 level 兜底为 str 而非异常


def test_fmt_mastery_str_and_none():
    from services.planner import _fmt_mastery
    assert _fmt_mastery("中") == "中"
    assert _fmt_mastery(None) == "None" or isinstance(_fmt_mastery(None), str)
    # 不抛异常即可
    _ = _fmt_mastery(None)
    _ = _fmt_mastery([])
    _ = _fmt_mastery(object())


def test_design_phases_with_dict_mastery():
    """mastery 含 dict 值时 design_phases 不抛 format 异常（此前整链路回退）。"""
    from services.planner import extract_plan_inputs, design_phases, PlanInputs
    from paeg import LearnerProfile

    learner = LearnerProfile(id="u_t", nickname="测试", grade_level="high_school", age=17)
    # 构造混合结构掌握度：float + dict
    learner.subjects_mastery = {"math": 0.8, "german": {"level": 0.5, "trend": "up"}}

    inputs = extract_plan_inputs("考研德语二外怎么准备", learner, subject="德语")
    assert isinstance(inputs.weekly_hours, float)

    # design_phases 构造 system 阶段不抛异常（LLM 为 None 时回退确定性模板）
    phases = design_phases(inputs, [], learner, llm=None)
    assert isinstance(phases, list) and phases  # 确定性模板兜底非空
