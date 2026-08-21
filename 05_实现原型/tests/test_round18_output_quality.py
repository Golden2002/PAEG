# -*- coding: utf-8 -*-
"""Round 11 ⭐ 教学输出质量强化测试（test_round18_output_quality.py）。

守护：
1. GRADE_OUTPUT_QUALITY 4 学段指令齐全（lecture 式/高屋建瓴/举一反三/考点套路）
2. inject_grade_profiles 注入质量指令（大学本科命中 lecture 式）
3. SUBJECT_GRADE_DEPTH_EXT 扩展学科覆盖（英语/计算机/经济/法学/哲学 × 大学/考研）
4. 幂等：重复注入不叠加
5. 与 grade_quality_gate 输出侧守门互补（守门特征仍全）
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.grade_subject_profiles import (
    GRADE_OUTPUT_QUALITY, SUBJECT_GRADE_DEPTH_EXT, inject_grade_profiles,
)


class TestGradeOutputQuality:
    def test_four_grades_covered(self):
        assert set(GRADE_OUTPUT_QUALITY.keys()) == {
            "middle_school", "high_school", "undergraduate", "graduate_exam"}

    def test_undergraduate_lecture_style(self):
        t = GRADE_OUTPUT_QUALITY["undergraduate"]
        assert "lecture" in t or "讲义" in t, "大学缺 lecture 式指令"
        assert "高屋建瓴" in t, "大学缺高屋建瓴（学科定位/核心思想）"
        assert "举一反三" in t, "大学缺举一反三变式"

    def test_high_school_example_and_pitfall(self):
        t = GRADE_OUTPUT_QUALITY["high_school"]
        assert "例题" in t, "高中缺例题示范"
        assert "误区" in t or "易错" in t, "高中缺误区提醒"

    def test_graduate_exam_kaodian(self):
        t = GRADE_OUTPUT_QUALITY["graduate_exam"]
        assert "考点" in t and "题型" in t and "易错" in t, "考研缺考点/题型/易错"

    def test_middle_school_life_style(self):
        t = GRADE_OUTPUT_QUALITY["middle_school"]
        assert "生活化" in t, "初中缺生活化"


class TestInjection:
    def test_inject_undergraduate_quality(self):
        sys0 = "## 系统\n你是教学 Agent。"
        out = inject_grade_profiles(sys0, subject="math", grade="undergraduate")
        assert "输出质量·大学本科" in out, "未注入大学质量指令"
        assert "高屋建瓴" in out, "未注入高屋建瓴"
        assert "学段学科深度 math/undergraduate" in out, "未注入深度阶梯"

    def test_inject_graduate_quality(self):
        out = inject_grade_profiles("sys", subject="math", grade="graduate_exam")
        assert "输出质量·考研" in out and "考点" in out

    def test_idempotent(self):
        sys0 = "## 系统\n你是教学 Agent。"
        once = inject_grade_profiles(sys0, subject="math", grade="undergraduate")
        twice = inject_grade_profiles(once, subject="math", grade="undergraduate")
        assert once == twice, "重复注入非幂等"

    def test_no_hit_returns_unchanged(self):
        sys0 = "plain system"
        assert inject_grade_profiles(sys0, subject="", grade="") == sys0


class TestDepthExt:
    def test_ext_subjects_covered(self):
        subs = {k[0] for k in SUBJECT_GRADE_DEPTH_EXT}
        assert {"college_english", "computer", "economics", "law", "philosophy"} <= subs

    def test_ext_grades_covered(self):
        for sub in ("college_english", "computer", "economics", "law", "philosophy"):
            assert (sub, "undergraduate") in SUBJECT_GRADE_DEPTH_EXT, sub
            assert (sub, "graduate_exam") in SUBJECT_GRADE_DEPTH_EXT, sub

    def test_ext_injects(self):
        out = inject_grade_profiles("sys", subject="computer", grade="undergraduate")
        assert "计算机科学基础" in out, "计算机大学深度阶梯未注入"
        out2 = inject_grade_profiles("sys", subject="law", grade="graduate_exam")
        assert "考点" in out2, "法学考研阶梯未注入"


class TestGateComplementarity:
    """与 grade_quality_gate 输出守门互补（守门特征表完整）。"""

    def test_gate_features_intact(self):
        from services.grade_quality_gate import _GRADE_FEATURES
        assert set(_GRADE_FEATURES.keys()) == {
            "middle_school", "high_school", "undergraduate", "graduate_exam"}
        ug = _GRADE_FEATURES["undergraduate"]
        assert {"严格定义", "定理证明", "应用", "学科视野"} <= set(ug.keys())
        ge = _GRADE_FEATURES["graduate_exam"]
        assert {"考点定位", "题型套路", "真题示范", "易错得分"} <= set(ge.keys())
