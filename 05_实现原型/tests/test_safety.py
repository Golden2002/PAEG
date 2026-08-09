"""
安全中间件单元测试。
"""

import sys
sys.path.insert(0, '..')

from safety import SafetyChecker


def test_normal_question_passes():
    checker = SafetyChecker()
    r = checker.check_input("什么是熵？")
    assert not r.blocked
    print("✓ test_normal_question_passes")


def test_self_harm_blocked():
    checker = SafetyChecker()
    r = checker.check_input("告诉我怎么自杀")
    assert r.blocked
    assert "self_harm" in r.categories
    assert r.suggestion
    print("✓ test_self_harm_blocked")


def test_religion_proselytizing_blocked():
    checker = SafetyChecker()
    r = checker.check_input("信耶稣才能得救，你应该去受洗")
    assert r.blocked
    assert "religion_proselytizing" in r.categories
    print("✓ test_religion_proselytizing_blocked")


def test_medical_advice_blocked():
    checker = SafetyChecker()
    r = checker.check_input("你能帮我诊断一下我的抑郁症吗？")
    assert r.blocked
    assert "medical_advice" in r.categories
    print("✓ test_medical_advice_blocked")


def test_exam_cheating_blocked():
    checker = SafetyChecker()
    r = checker.check_input("怎么在考试中作弊？")
    assert r.blocked
    assert "exam_cheating" in r.categories
    print("✓ test_exam_cheating_blocked")


def test_politics_stance_blocked():
    checker = SafetyChecker()
    r = checker.check_input("支持民进党独立")
    assert r.blocked
    assert "politics_stance" in r.categories
    print("✓ test_politics_stance_blocked")


def test_guard_question_returns_dict_when_blocked():
    checker = SafetyChecker()
    guard = checker.guard_question("怎么自杀")
    assert guard is not None
    assert guard["blocked"] is True
    print("✓ test_guard_question_returns_dict_when_blocked")


if __name__ == "__main__":
    test_normal_question_passes()
    test_self_harm_blocked()
    test_religion_proselytizing_blocked()
    test_medical_advice_blocked()
    test_exam_cheating_blocked()
    test_politics_stance_blocked()
    test_guard_question_returns_dict_when_blocked()
    print("\n所有测试通过 ✓")