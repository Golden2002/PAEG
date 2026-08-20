# -*- coding: utf-8 -*-
"""_score_12_hard_checks 12 条硬性检查确定性判定测试面（无 LLM）。

来源：LESSON_PLANNER_QUALITY_CRITERIA['hard_checks'] 12 条

分类：
  - 7 条确定性自动判定（三级结构 / 元指引 / 节末总结 / 核心拓展分流 /
    启发式思考题 / 公式前直觉 / 易混对比表）
  - 5 条 LLM 评审标记 "unverified"（人物绑定 / 第一手文献 / 跨学科连接 /
    真实数据场景 / 类比隐喻）

返回结构：
  {
    "hard_checks": [{"name": str, "status": "pass"|"unverified"|"fail"} ... 12],
    "hard_checks_pass": int,    # status == "pass" 的条目数
    "hard_checks_total": 12,    # 永远是 12
  }

判定准则（正则/结构）：
  - 三级结构      plan['sections'] 非空
  - 元指引        plan['student_analysis'] 与 plan['objectives_3d'] 均非空
  - 节末总结      sections 任一含 '小结' 或 handout 含 '小结'
  - 核心拓展分流  sections 任一含 '拓展' 或 ppt 任一项文本含 '*'
  - 启发式思考题  handout 含 '思考题' 或 '探究'
  - 公式前直觉    sections+handout+ppt 合并文本含 '直观' 或 '直觉' 或 '类比'
  - 易混对比表    handout 含 '对比' 或 '区别'
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from subagents import _score_12_hard_checks


# -------- 辅助构造 --------

def _section(name, duration_min=10, **extras):
    """构造一节教学环节（plan['sections'][i]）。"""
    base = {"name": name, "duration_min": duration_min}
    base.update(extras)
    return base


def _plan_full(sections=None, student_analysis="学生已掌握初中函数基础",
               objectives_3d=None, **extras):
    """构造一个合格 plan（含 sections + student_analysis + objectives_3d）。"""
    return {
        "sections": sections if sections is not None else [
            _section("导入"),
            _section("新授"),
            _section("探究"),
            _section("巩固"),
            _section("小结"),
            _section("作业"),
        ],
        "student_analysis": student_analysis,
        "objectives_3d": objectives_3d if objectives_3d is not None else {
            "knowledge": ["理解导数的几何意义"],
            "skill": ["能求简单函数的导数"],
            "literacy": ["体会极限思想"],
        },
        **extras,
    }


def _ppt_outline(titles=None, points_list=None):
    """构造 ppt 列表（_score_12_hard_checks 仅看文本字段，不计分页）。"""
    titles = titles or [f"第{i+1}节 主题" for i in range(5)]
    out = []
    for i, t in enumerate(titles):
        pts = (points_list[i] if points_list else [f"要点 {j}" for j in range(3)])
        out.append({"page": i + 1, "title": t, "points": pts, "layout": "左→右"})
    return out


# -------- 1. 三级结构 --------

def test_three_level_structure():
    """plan 含 sections → 三级结构 PASS；空 plan → FAIL。

    三级层次结构（总章/节/小节）——用 plan['sections'] 非空做存在性判定。
    """
    plan = _plan_full()
    r = _score_12_hard_checks(plan, "", _ppt_outline())
    by_name = {c["name"]: c["status"] for c in r["hard_checks"]}
    assert by_name["三级层次结构（总章/节/小节）清晰"] == "pass", (
        f"非空 plan 应通过三级结构，实际 {by_name}"
    )

    # 空 plan：sections 不存在或为 []
    r_empty = _score_12_hard_checks({}, "", _ppt_outline())
    by_name_empty = {c["name"]: c["status"] for c in r_empty["hard_checks"]}
    assert by_name_empty["三级层次结构（总章/节/小节）清晰"] == "fail", (
        f"空 plan 应未通过三级结构，实际 {by_name_empty}"
    )


# -------- 2. 元指引 --------

def test_meta_guidance():
    """plan 含 student_analysis + objectives_3d → 元指引 PASS；缺一 → FAIL。"""
    plan = _plan_full()
    r = _score_12_hard_checks(plan, "", _ppt_outline())
    by_name = {c["name"]: c["status"] for c in r["hard_checks"]}
    assert by_name["元学习指引（前置知识/学习目标/难度评级）"] == "pass"

    # 缺 student_analysis
    plan_no_sa = _plan_full(student_analysis="")
    r2 = _score_12_hard_checks(plan_no_sa, "", _ppt_outline())
    by2 = {c["name"]: c["status"] for c in r2["hard_checks"]}
    assert by2["元学习指引（前置知识/学习目标/难度评级）"] == "fail", (
        f"缺 student_analysis 应未通过元指引，实际 {by2}"
    )


# -------- 3. 节末总结 --------

def test_section_summary():
    """sections 含 '小结' 节 或 handout 含 '小结' → 节末总结 PASS。"""
    plan = _plan_full(sections=[_section("导入"), _section("新授"),
                                 _section("探究"), _section("巩固"),
                                 _section("小结"), _section("作业")])
    r1 = _score_12_hard_checks(plan, "", _ppt_outline())
    by1 = {c["name"]: c["status"] for c in r1["hard_checks"]}
    assert by1["节末有3-5行总结"] == "pass", (
        f"sections 含'小结'应通过，实际 {by1}"
    )

    # sections 无 '小结' 但 handout 含 '小结'
    plan_no_summary = _plan_full(sections=[_section("导入"), _section("新授")])
    handout_with_summary = "本节课小结：理解导数定义，掌握求导法则。"
    r2 = _score_12_hard_checks(plan_no_summary, handout_with_summary, _ppt_outline())
    by2 = {c["name"]: c["status"] for c in r2["hard_checks"]}
    assert by2["节末有3-5行总结"] == "pass", (
        f"handout 含'小结'应通过，实际 {by2}"
    )

    # 既无 sections 小结也无 handout 小结
    r3 = _score_12_hard_checks(plan_no_summary, "本节课无总结", _ppt_outline())
    by3 = {c["name"]: c["status"] for c in r3["hard_checks"]}
    assert by3["节末有3-5行总结"] == "fail"


# -------- 4. 核心拓展分流 --------

def test_branching():
    """text 含 '拓展' 或 '*' → 分流 PASS。"""
    plan = _plan_full(sections=[_section("导入"), _section("新授"),
                                 _section("拓展：竞赛"), _section("巩固"),
                                 _section("小结"), _section("作业")])
    r1 = _score_12_hard_checks(plan, "", _ppt_outline())
    by1 = {c["name"]: c["status"] for c in r1["hard_checks"]}
    assert by1["核心/拓展内容显式分流（*号或标注）"] == "pass"

    # sections 无拓展，但 ppt 含 '*'
    plan_no_ext = _plan_full(sections=[_section("导入"), _section("新授")])
    ppt_star = _ppt_outline(
        titles=["基础定义", "求导 *竞赛拓展", "几何意义", "例题", "小结"],
    )
    r2 = _score_12_hard_checks(plan_no_ext, "", ppt_star)
    by2 = {c["name"]: c["status"] for c in r2["hard_checks"]}
    assert by2["核心/拓展内容显式分流（*号或标注）"] == "pass", (
        f"ppt 含 '*' 应通过分流，实际 {by2}"
    )

    # 都无
    r3 = _score_12_hard_checks(plan_no_ext, "", _ppt_outline())
    by3 = {c["name"]: c["status"] for c in r3["hard_checks"]}
    assert by3["核心/拓展内容显式分流（*号或标注）"] == "fail"


# -------- 5. 启发式思考题 --------

def test_think_question():
    """handout 含 '思考题' 或 '探究' → 思考题 PASS。"""
    plan = _plan_full()
    handout = "## 思考题\n1. 为什么导数定义用极限？"
    r = _score_12_hard_checks(plan, handout, _ppt_outline())
    by = {c["name"]: c["status"] for c in r["hard_checks"]}
    assert by["每节≥1个启发式思考题"] == "pass"

    # '探究' 关键词
    handout_probe = "## 探究活动\n分小组讨论导数的几何意义。"
    r2 = _score_12_hard_checks(plan, handout_probe, _ppt_outline())
    by2 = {c["name"]: c["status"] for c in r2["hard_checks"]}
    assert by2["每节≥1个启发式思考题"] == "pass"

    # 都无
    r3 = _score_12_hard_checks(plan, "本节课无作业", _ppt_outline())
    by3 = {c["name"]: c["status"] for c in r3["hard_checks"]}
    assert by3["每节≥1个启发式思考题"] == "fail"


# -------- 6. 公式前直觉 --------

def test_formula_intuition():
    """text 含 '直观' 或 '直觉' 或 '类比' → 公式前直觉 PASS。"""
    plan = _plan_full()
    handout = "## 直觉解释\n导数是切线斜率，可类比为汽车瞬时速度。"
    r1 = _score_12_hard_checks(plan, handout, _ppt_outline())
    by1 = {c["name"]: c["status"] for c in r1["hard_checks"]}
    assert by1["公式出现前先给直觉解释"] == "pass", (
        f"含 '直观/类比' 应通过，实际 {by1}"
    )

    # handout 无直觉词，但 sections 有
    plan_sec = _plan_full(sections=[_section("导入：直观感受斜率"),
                                     _section("新授"), _section("小结")])
    r2 = _score_12_hard_checks(plan_sec, "", _ppt_outline())
    by2 = {c["name"]: c["status"] for c in r2["hard_checks"]}
    assert by2["公式出现前先给直觉解释"] == "pass"

    # 全无
    plan_none = _plan_full(sections=[_section("导入"), _section("新授")])
    r3 = _score_12_hard_checks(plan_none, "纯定义与公式", _ppt_outline())
    by3 = {c["name"]: c["status"] for c in r3["hard_checks"]}
    assert by3["公式出现前先给直觉解释"] == "fail"


# -------- 7. 易混对比表 --------

def test_compare_table():
    """handout 含 '对比' 或 '区别' → 对比表 PASS。"""
    plan = _plan_full()
    handout = "## 对比表\n| 导数 | 积分 |\n| 瞬时变化率 | 累积量 |"
    r1 = _score_12_hard_checks(plan, handout, _ppt_outline())
    by1 = {c["name"]: c["status"] for c in r1["hard_checks"]}
    assert by1["易混概念配对比表"] == "pass"

    # '区别' 关键词
    handout_diff = "## 区别\n导数与导函数的区别在于..."
    r2 = _score_12_hard_checks(plan, handout_diff, _ppt_outline())
    by2 = {c["name"]: c["status"] for c in r2["hard_checks"]}
    assert by2["易混概念配对比表"] == "pass"

    # 都无（注意：必须避开 '对比' / '区别' 子串）
    r3 = _score_12_hard_checks(plan, "本节课只有例题和公式。", _ppt_outline())
    by3 = {c["name"]: c["status"] for c in r3["hard_checks"]}
    assert by3["易混概念配对比表"] == "fail"


# -------- 8. 5 条 LLM 评审标记 unverified --------

def test_llm_marked_unverified():
    """5 条语义判定项恒为 'unverified'：人物 / 文献 / 跨学科 / 真实数据 / 类比。"""
    plan = _plan_full()
    r = _score_12_hard_checks(plan, "", _ppt_outline())
    by = {c["name"]: c["status"] for c in r["hard_checks"]}
    llm_names = [
        "每核心概念绑定≥1位历史人物",
        "≥1处第一手文献引用",
        "≥1处跨学科连接",
        "例题用真实数据场景（非虚构数字）",
        "抽象概念配类比/隐喻",
    ]
    for n in llm_names:
        assert by[n] == "unverified", (
            f"LLM 评审项 '{n}' 应为 unverified，实际 {by[n]}（所有项：{by}）"
        )


# -------- 9. 总数 + 计数 --------

def test_unverified_count():
    """hard_checks_total == 12；pass + unverified + fail 计数正确。

    满分配置：7 条 auto 全 pass + 5 条 unverified = pass=7, total=12。
    """
    # 满分场景：plan 完整 + handout 含关键证据
    plan = _plan_full(
        sections=[
            _section("导入：直观感受斜率"),
            _section("新授"),
            _section("探究"),
            _section("巩固"),
            _section("拓展：竞赛"),
            _section("小结"),
        ],
    )
    handout = (
        "## 直觉解释\n导数可类比为瞬时速度。\n"
        "## 思考题\n1. 为什么用极限？\n"
        "## 对比表\n| 导数 | 积分 |\n"
        "## 区别\n两者定义不同。\n"
        "## 小结\n本节总结。"
    )
    ppt = _ppt_outline(titles=["基础*", "求导", "几何", "例题", "小结"])
    r = _score_12_hard_checks(plan, handout, ppt)

    assert r["hard_checks_total"] == 12, (
        f"hard_checks_total 应恒为 12，实际 {r['hard_checks_total']}"
    )
    assert len(r["hard_checks"]) == 12, (
        f"hard_checks 列表长度应 12，实际 {len(r['hard_checks'])}"
    )
    statuses = [c["status"] for c in r["hard_checks"]]
    assert statuses.count("pass") == r["hard_checks_pass"], (
        f"pass 计数 {statuses.count('pass')} 与 hard_checks_pass {r['hard_checks_pass']} 不一致"
    )
    assert statuses.count("unverified") == 5, (
        f"unverified 应为 5 条，实际 {statuses.count('unverified')}"
    )
    # 满分配景：7 auto 全 pass + 5 unverified = 7 pass
    assert r["hard_checks_pass"] == 7, (
        f"满分场景 hard_checks_pass 应为 7，实际 {r['hard_checks_pass']}（状态：{statuses}）"
    )

    # 空 plan → 三级结构 fail，其余 6 auto fail（无 handout/ppt 证据），LLM 5 条 unverified
    r_empty = _score_12_hard_checks({}, "", [])
    statuses_empty = [c["status"] for c in r_empty["hard_checks"]]
    assert r_empty["hard_checks_total"] == 12
    assert statuses_empty.count("unverified") == 5
    assert r_empty["hard_checks_pass"] == 0