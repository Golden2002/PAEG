# -*- coding: utf-8 -*-
"""§3.79 Round 9 学段特征输出守门测试（services/grade_quality_gate + paeg 接线）。

覆盖：
  check_grade_features：
    - 4 学段特征表齐全
    - 考研输出缺考点/题型 → missing 检出
    - 含特征 → passed
    - 未知学段 → 归一 high_school（容错）
  build_refine_prompt / refine_for_grade：
    - 缺特征时生成补充提示词（含缺失项）
    - refine 失败（mock LLM 抛错）→ ""（静默降级）
    - 无缺失 → 不调用
  paeg 接线点存在（subagents/paeg 源码含 学段特征补充 标记）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.grade_quality_gate import (
    check_grade_features, build_refine_prompt, refine_for_grade,
    _GRADE_FEATURES,
)


# ────────────────────────────────────────────
# check_grade_features
# ────────────────────────────────────────────
def test_feature_tables_complete():
    for _g in ("middle_school", "high_school", "undergraduate", "graduate_exam"):
        assert len(_GRADE_FEATURES[_g]) >= 3, f"{_g} 特征表过薄"


def test_graduate_exam_missing_detected():
    """考研输出缺考点/题型/真题/易错 → missing 全部检出。"""
    content = "二重积分是多元积分的核心。我们来讲讲它的定义和计算步骤。"
    r = check_grade_features(content, "graduate_exam")
    assert r["grade"] == "graduate_exam"
    assert r["passed"] is False
    assert "考点定位" in r["missing"]
    assert "真题示范" in r["missing"]
    assert "易错得分" in r["missing"]


def test_graduate_exam_pass_with_features():
    content = ("考点定位：二重积分近十年考了 6 次。题型套路：先换序再算。"
               "真题示范：【2021】计算 ∫∫D。易错得分：注意积分次序。")
    r = check_grade_features(content, "graduate_exam")
    assert r["passed"] is True


def test_undergraduate_lecture_features():
    content = ("严格定义：若极限存在则称可积。定理证明：由定义直接推得。"
               "推导：分部积分。应用：物理中的质心。学科视野：黎曼的贡献。")
    r = check_grade_features(content, "undergraduate")
    assert r["passed"] is True


def test_unknown_grade_falls_back():
    r = check_grade_features("内容", "no_such_grade")
    assert r["grade"] == "high_school"


# ────────────────────────────────────────────
# refine_for_grade
# ────────────────────────────────────────────
def test_build_refine_prompt_contains_missing():
    p = build_refine_prompt("原内容", "graduate_exam",
                            ["考点定位", "真题示范"], subject="math", concept="二重积分")
    assert "考点定位" in p and "真题示范" in p
    assert "考研" in p


def test_refine_no_missing_returns_empty():
    assert refine_for_grade(None, "内容", "graduate_exam", []) == ""


def test_refine_failure_degrades():
    class _BadLLM:
        def chat(self, *a, **k):
            raise RuntimeError("LLM 失败")

    _r = refine_for_grade(_BadLLM(), "内容", "graduate_exam", ["考点定位"])
    assert _r == ""  # 静默降级


def test_refine_success_appends():
    class _GoodLLM:
        name = "test_llm"  # _safe_chat 的 _is_real_llm 判定需要非 mock

        def chat(self, system=None, user=None, messages=None, max_tokens=512, **k):
            return "补充：考点定位——本题为高频考点；真题示范：【2022】类似题。"

    _r = refine_for_grade(_GoodLLM(), "原内容", "graduate_exam", ["考点定位", "真题示范"])
    assert _r.startswith("\n\n")
    assert "考点定位" in _r


def test_paeg_wiring_marker_exists():
    """paeg.py 含学段守门接线标记。"""
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "paeg.py")
    src = open(_p, encoding="utf-8").read()
    assert "学段特征输出守门" in src
    assert "grade_refined" in src


# ────────────────────────────────────────────
# §3.79 Round 11 内容深度四要素守门
# ────────────────────────────────────────────
from services.grade_quality_gate import (
    check_content_depth, refine_content_depth,
)


def test_content_depth_missing_detected():
    """缺机制/例子/小结 → missing 检出、passed False。"""
    r = check_content_depth("导数是函数的变化率。", "high_school")
    assert r["passed"] is False
    assert "例子" in r["missing"]


def test_content_depth_pass():
    r = check_content_depth(
        "导数是指函数在某一点的瞬时变化率。为什么这样定义？因为要描述变化的快慢。"
        "比如汽车速度表。所以导数是微积分的核心概念。", "undergraduate")
    assert r["passed"] is True


def test_content_depth_refine_degrades():
    class _BadLLM:
        def chat(self, *a, **k):
            raise RuntimeError("fail")

    assert refine_content_depth(_BadLLM(), "内容", ["例子", "小结"]) == ""


def test_content_depth_refine_no_missing():
    assert refine_content_depth(None, "内容", []) == ""

