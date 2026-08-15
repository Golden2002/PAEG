# -*- coding: utf-8 -*-
"""test_grade_subject_profiles.py —— §3.44 PTC + §3.43 P0 ⭐ 学段学科 profile 模块测试

覆盖 P0-2/P0-3/P0-4（独立模块实现，避免 prompts.py 大文件低效编辑）：
- P0-2：考研学科分键（politics_exam/math_exam 别名 + 考点解剖风格）
- P0-3：收尾问题模板（4 学段 closing_questions）
- P0-4：SUBJECT_GRADE_DEPTH 二维阶梯（5 学科 × 4 学段 = 20 条 + 注入）
"""
from __future__ import annotations

import pytest


def test_korean_exam_subject_profiles():
    """考研学科 profile：politics_exam/math_exam 有考点解剖风格。"""
    from services.grade_subject_profiles import KOREAN_EXAM_STYLES
    assert "politics_exam" in KOREAN_EXAM_STYLES, "考研政治应有考点解剖风格"
    assert "math_exam" in KOREAN_EXAM_STYLES, "考研数学应有考点解剖风格"
    for key, style in KOREAN_EXAM_STYLES.items():
        assert "考点" in style or "套路" in style, f"{key} 应为考研考点风格"


def test_korean_exam_alias():
    """考研学科别名映射。"""
    from services.grade_subject_profiles import KOREAN_EXAM_ALIASES
    assert KOREAN_EXAM_ALIASES.get("考研政治") == "politics_exam"
    assert KOREAN_EXAM_ALIASES.get("考研数学") == "math_exam"


def test_closing_question_templates_all_grades():
    """收尾问题模板：4 学段都有，且不同学段不同。"""
    from services.grade_subject_profiles import CLOSING_QUESTIONS
    for grade in ("middle_school", "high_school", "undergraduate", "graduate_exam"):
        assert grade in CLOSING_QUESTIONS, f"{grade} 缺收尾模板"
        assert len(CLOSING_QUESTIONS[grade]) >= 2, f"{grade} 至少 2 个模板"
    # 不同学段模板不同
    all_q = set()
    for qs in CLOSING_QUESTIONS.values():
        all_q.update(qs)
    assert len(all_q) >= 8, "4 学段应共至少 8 个不同模板"


def test_grade_depth_20_entries():
    """SUBJECT_GRADE_DEPTH：5 学科 × 4 学段 = 20 条。"""
    from services.grade_subject_profiles import SUBJECT_GRADE_DEPTH
    subjects = ("physics", "math", "chemistry", "biology", "chinese")
    grades = ("middle_school", "high_school", "undergraduate", "graduate_exam")
    count = 0
    for s in subjects:
        for g in grades:
            entry = SUBJECT_GRADE_DEPTH.get((s, g))
            assert entry is not None, f"({s},{g}) 缺深度配置"
            assert "scope" in entry, f"({s},{g}) 缺 scope"
            count += 1
    assert count == 20


def test_grade_depth_varied_by_grade():
    """深度阶梯：同一学科不同学段避免/必含术语不同（非复制）。"""
    from services.grade_subject_profiles import SUBJECT_GRADE_DEPTH
    mid = SUBJECT_GRADE_DEPTH[("physics", "middle_school")]
    und = SUBJECT_GRADE_DEPTH[("physics", "undergraduate")]
    assert mid["avoid_terms"], "初中物理应有避免术语"
    assert "麦克斯韦" in mid["avoid_terms"] or "梯度" in mid["avoid_terms"], "初中应避免高深术语"
    assert "守恒律" in und["must_terms"] or "严格定义" in und["must_terms"], "大学应必含严格概念"


def test_inject_grade_profile_into_system():
    """注入 build_presenter_system：深度阶梯 + 收尾模板进入 system。"""
    from services.grade_subject_profiles import inject_grade_profiles
    system = "你是数学老师。"
    injected = inject_grade_profiles(system, subject="physics", grade="middle_school")
    assert system in injected, "注入应保留原 system"
    if injected != system:
        assert "避免" in injected or "必须" in injected or "收尾" in injected, "注入应含教学指引"
