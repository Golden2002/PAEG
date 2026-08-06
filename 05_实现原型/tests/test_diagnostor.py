"""
诊断子代理的单元测试。
"""

import sys
sys.path.insert(0, '..')

from paeg import LearnerProfile
from knowledge_base import KnowledgeBase
from subagents import Diagnostor


class MockModel:
    def messages_create(self, **kwargs):
        return {"content": [{"text": "ok"}]}


def test_diagnostor_basic():
    """基本诊断：能返回学习状态。"""
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    kb = KnowledgeBase()
    diagnostor = Diagnostor(MockModel(), kb)

    result = diagnostor.run(learner, "什么是熵？", "physics")

    assert "prerequisites_status" in result
    assert "ready_to_teach" in result
    print("✓ test_diagnostor_basic")


def test_diagnostor_returns_prerequisites():
    """诊断返回前置知识状态。"""
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    kb = KnowledgeBase()
    diagnostor = Diagnostor(MockModel(), kb)

    result = diagnostor.run(learner, "什么是熵？", "physics")

    assert isinstance(result["prerequisites_status"], dict)
    print("✓ test_diagnostor_returns_prerequisites")


if __name__ == "__main__":
    test_diagnostor_basic()
    test_diagnostor_returns_prerequisites()
    print("\n所有测试通过 ✓")
