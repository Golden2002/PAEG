"""
自我更新机制的单元测试。
"""

import sys
sys.path.insert(0, '..')

from paeg import PAEG, LearnerProfile
from knowledge_base import KnowledgeBase
from self_update import SelfUpdater


class MockModel:
    def messages_create(self, **kwargs):
        return {"content": [{"text": "ok"}]}


def test_incremental_update_records_reflection():
    """增量更新：记录反思。"""
    paeg = PAEG(MockModel(), KnowledgeBase())

    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg.teach(learner, "什么是熵？", "physics")

    assert len(paeg.self_updater.history) > 0
    print("✓ test_incremental_update_records_reflection")


def test_profile_mastery_updates():
    """增量更新：学生掌握度更新。"""
    paeg = PAEG(MockModel(), KnowledgeBase())

    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg.teach(learner, "什么是熵？", "physics")

    assert "physics" in learner.subjects_mastery
    assert 0 <= learner.subjects_mastery["physics"]["mastery"] <= 1
    print("✓ test_profile_mastery_updates")


def test_batch_update_summarizes():
    """批处理：汇总历史。"""
    paeg = PAEG(MockModel(), KnowledgeBase())

    learner = LearnerProfile(id="001", nickname="小李", grade_level="high_school", age=17)
    paeg.teach(learner, "什么是熵？", "physics")

    batch = paeg.self_updater.batch_update()
    assert "total_sessions" in batch
    print("✓ test_batch_update_summarizes")


if __name__ == "__main__":
    test_incremental_update_records_reflection()
    test_profile_mastery_updates()
    test_batch_update_summarizes()
    print("\n所有测试通过 ✓")
