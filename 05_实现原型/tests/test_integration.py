"""
端到端测试：5 个学科完整教学流程。
"""

import sys
sys.path.insert(0, '..')

from paeg import PAEG, LearnerProfile
from knowledge_base import KnowledgeBase


class MockModel:
    def messages_create(self, **kwargs):
        return {"content": [{"text": "[演示]"}]}


def test_e2e_physics():
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg = PAEG(MockModel(), KnowledgeBase())
    result = paeg.teach(learner, "什么是熵？", "physics")
    assert result["summary"]["avg_score"] > 0
    print("✓ test_e2e_physics")


def test_e2e_literature():
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg = PAEG(MockModel(), KnowledgeBase())
    result = paeg.teach(learner, "为什么特洛伊战争持续十年？", "literature")
    assert result["summary"]["avg_score"] > 0
    print("✓ test_e2e_literature")


def test_e2e_ethics():
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg = PAEG(MockModel(), KnowledgeBase())
    result = paeg.teach(learner, "电车难题该拉开关吗？", "ethics")
    assert result["summary"]["avg_score"] > 0
    print("✓ test_e2e_ethics")


def test_e2e_math():
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg = PAEG(MockModel(), KnowledgeBase())
    result = paeg.teach(learner, "为什么负负得正？", "math")
    assert result["summary"]["avg_score"] > 0
    print("✓ test_e2e_math")


def test_e2e_phenomenology():
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg = PAEG(MockModel(), KnowledgeBase())
    result = paeg.teach(learner, "为什么人会感到孤独？", "phenomenology")
    assert result["summary"]["avg_score"] > 0
    print("✓ test_e2e_phenomenology")


def test_all_subjects_with_world_view_blend():
    """验证：每个学科的呈现都使用了对应的世界观比例。"""
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg = PAEG(MockModel(), KnowledgeBase())

    expected = {
        "physics": "rigorous_cold",
        "math": "rigorous_cold",
        "literature": "contemplative",
        "ethics": "warm_caring",
        "phenomenology": "contemplative"
    }

    for subject, expected_tone in expected.items():
        question = "示例问题"
        if subject == "physics": question = "什么是熵？"
        elif subject == "math": question = "为什么负负得正？"
        elif subject == "literature": question = "为什么特洛伊战争持续十年？"
        elif subject == "ethics": question = "电车难题该拉开关吗？"
        elif subject == "phenomenology": question = "为什么人会感到孤独？"

        result = paeg.teach(learner, question, subject)
        # 检查 history 第一个呈现的语气
        if result["session"].history:
            actual_tone = result["session"].history[0].get("tone_used", "unknown")
            assert actual_tone == expected_tone, f"{subject}: expected {expected_tone}, got {actual_tone}"

    print("✓ test_all_subjects_with_world_view_blend")


if __name__ == "__main__":
    test_e2e_physics()
    test_e2e_literature()
    test_e2e_ethics()
    test_e2e_math()
    test_e2e_phenomenology()
    test_all_subjects_with_world_view_blend()
    print("\n所有测试通过 ✓")
