"""
呈现子代理的单元测试。
"""

import sys
sys.path.insert(0, '..')

from paeg import LearnerProfile
from knowledge_base import KnowledgeBase
from subagents import Presenter


class MockModel:
    def messages_create(self, **kwargs):
        return {"content": [{"text": "ok"}]}


def test_presenter_physics_rigorous():
    """物理主题：呈现使用 rigorous_cold 语气。"""
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    kb = KnowledgeBase()
    presenter = Presenter(MockModel(), kb)

    step = {"type": "present", "topic": "熵", "worldview": "rigorous_cold"}
    result = presenter.run(step, learner, [])

    assert result["tone_used"] == "rigorous_cold"
    assert "content" in result
    print("✓ test_presenter_physics_rigorous")


def test_presenter_literature_contemplative():
    """文学主题：呈现使用 contemplative 语气。"""
    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    kb = KnowledgeBase()
    presenter = Presenter(MockModel(), kb)

    step = {"type": "present", "topic": "特洛伊", "worldview": "contemplative"}
    result = presenter.run(step, learner, [])

    assert result["tone_used"] == "contemplative"
    print("✓ test_presenter_literature_contemplative")


if __name__ == "__main__":
    test_presenter_physics_rigorous()
    test_presenter_literature_contemplative()
    print("\n所有测试通过 ✓")
