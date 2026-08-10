# -*- coding: utf-8 -*-
"""v0.41.9 ⭐ 组合矩阵测试（学段 × 学科 × 模式 × 检索）

针对 v0.41.9 教训：考研+法语误判等 bug 未被发现，因为测试是"手工挑选样本点"，
不是"组合矩阵全覆盖"——graduate_exam × french 这类角落组合从未被测试。

本测试用 pytest parametrize 穷举组合，验证"任何学段 + 任何学科"的学段-学科
联动正确性（不依赖 LLM，直接测 subject_available_for_grade 纯函数）。

用法：python -m pytest tests/test_grade_matrix.py -q
"""
import pytest

from prompts import subject_available_for_grade, SUBJECT_GRADES, SUBJECT_MIN_GRADE

# 全部学段（含考研）
GRADES = ["middle_school", "high_school", "undergraduate", "graduate_exam"]
# 代表性学科（语言类 + 基础 + 高阶 + 通识 + 大学）
SUBJECTS = ["math", "physics", "french", "german", "japanese", "english",
            "linguistics", "philosophy", "coding", "phenomenology",
            "atmospheric_science", "chemistry", "history", "literature"]


def _expected_available(subject: str, grade: str) -> bool:
    """期望值：学科在学段是否可用（按 SUBJECT_GRADES/MIN_GRADE 语义）。"""
    grades = SUBJECT_GRADES.get(subject)
    if grades:
        if "all_grades" in grades:
            return True
        return grade in grades
    min_g = SUBJECT_MIN_GRADE.get(subject)
    if not min_g or min_g == "graduate_exam":
        return grade == "graduate_exam" or min_g == grade
    order = {"middle_school": 0, "high_school": 1, "undergraduate": 2,
             "graduate_exam": 3}.get(grade, 1)
    min_order = {"middle_school": 0, "high_school": 1, "undergraduate": 2,
                 "graduate_exam": 3}.get(min_g, 1)
    return order >= min_order


# ── 组合矩阵：全部 学段×学科 ─────────────────────────────
@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("grade", GRADES)
def test_grade_subject_matrix(subject, grade):
    """性质：subject_available_for_grade 与语义期望一致（4 学段 × 14 学科 = 56 组合）。"""
    actual = subject_available_for_grade(subject, grade)
    expected = _expected_available(subject, grade)
    assert actual == expected, (
        f"{subject} @ {grade}: 实际={actual} 期望={expected} "
        f"(SUBJECT_GRADES={SUBJECT_GRADES.get(subject)}, "
        f"MIN={SUBJECT_MIN_GRADE.get(subject)})")


# ── 关键回归：语言类学科考研档（v0.41.9 bug）───────────────
@pytest.mark.parametrize("lang", ["french", "german", "japanese", "english", "linguistics"])
def test_language_available_for_graduate(lang):
    """性质：语言类学科必须支持考研档（考研生学外语合理，曾误判"需初中"）。"""
    assert subject_available_for_grade(lang, "graduate_exam"), \
        f"{lang} @ graduate_exam 不可用（v0.41.9 bug 回归！）"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
