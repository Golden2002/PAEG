"""
PAEG v0.38 端到端测试：5 个学科的完整 demo。
"""

from paeg import PAEG, LearnerProfile
from knowledge_base import KnowledgeBase


class MockModel:
    """模拟模型 API（v0.38 不接真实 LLM）。"""
    def messages_create(self, **kwargs):
        return {"content": [{"text": "[模拟回复]"}]}


def run_subject_demo(paeg: PAEG, subject: str, question: str, learner: LearnerProfile):
    """运行一个学科 demo。"""
    print(f"\n{'='*60}")
    print(f"Demo：{subject} - {question}")
    print(f"学习者：{learner.nickname} ({learner.grade_level})")
    print(f"{'='*60}")

    result = paeg.teach(learner, question, subject)

    print(f"\n--- 总结 ---")
    print(f"概念：{result['summary']['concept']}")
    print(f"学生：{result['summary']['learner']}")
    print(f"平均分：{result['summary']['avg_score']:.2f}")
    print(f"完成步骤：{result['summary']['steps_completed']}")

    return result


def main():
    model = MockModel()
    kb = KnowledgeBase()
    paeg = PAEG(model, kb)

    learner = LearnerProfile(
        id="001",
        nickname="小李",
        grade_level="high_school",
        age=17,
        cognitive_style="visual"
    )

    # 5 个学科 demo
    demos = [
        ("physics", "什么是熵？"),
        ("math", "为什么负负得正？"),
        ("literature", "为什么特洛伊战争持续十年？"),
        ("ethics", "电车难题该拉开关吗？"),
        ("phenomenology", "为什么人会感到孤独？")
    ]

    for subject, question in demos:
        run_subject_demo(paeg, subject, question, learner)

    # 显示自我更新结果
    print(f"\n{'='*60}")
    print(f"自我更新结果")
    print(f"{'='*60}")
    print(f"反思历史：{len(paeg.self_updater.history)} 条")
    print(f"发现策略：{len(paeg.self_updater.strategies_discovered)} 个")
    print(f"学生掌握度：{learner.subjects_mastery}")

    # 批处理
    batch = paeg.self_updater.batch_update()
    print(f"\n批处理结果：{batch}")


if __name__ == "__main__":
    main()
