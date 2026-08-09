"""
pytest 测试用例集 v0.2（真实可运行）

≥ 20 个测试用例。
运行：cd 14_教育者Agent项目/05_实现原型/ ; python -m pytest tests/ -v
"""
from __future__ import annotations

import os
import sys

# 让 pytest 能找到 05_实现原型/ 下的模块
_PROTOTYPE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "05_实现原型")
)
if _PROTOTYPE_DIR not in sys.path:
    sys.path.insert(0, _PROTOTYPE_DIR)

from paeg import LearnerProfile, MockModel, PAEG, SessionContext  # noqa: E402
from knowledge_base import KnowledgeBase  # noqa: E402
from subagents import Adapter, Diagnostor, Evaluator, Planner, Presenter  # noqa: E402
from self_update import SelfUpdater  # noqa: E402
from world_view import THEME_TONE_MAP, select_tone  # noqa: E402


# ─────────────────────────────────────
# 共享 fixtures
# ─────────────────────────────────────


def make_paeg(enable_self_update: bool = True) -> PAEG:
    """创建一个测试用 PAEG。"""
    model = MockModel()
    kb = KnowledgeBase()
    return PAEG(model, kb, enable_self_update=enable_self_update)


def make_learner(
    id: str = "test_001",
    nickname: str = "测试生",
    grade_level: str = "high_school",
    age: int = 17,
) -> LearnerProfile:
    """创建一个测试用学习者。"""
    return LearnerProfile(
        id=id,
        nickname=nickname,
        grade_level=grade_level,
        age=age,
    )


# ─────────────────────────────────────
# Diagnostor 测试
# ─────────────────────────────────────


def test_diagnostor_basic():
    """基本诊断：返回学习状态。"""
    diagnostor = Diagnostor(MockModel(), KnowledgeBase())
    learner = make_learner()
    result = diagnostor.run(learner, "什么是熵？", "physics")
    assert "prerequisites_status" in result
    assert "ready_to_teach" in result


def test_diagnostor_returns_prerequisites_dict():
    """诊断返回前置知识状态是 dict。"""
    diagnostor = Diagnostor(MockModel(), KnowledgeBase())
    learner = make_learner()
    result = diagnostor.run(learner, "什么是熵？", "physics")
    assert isinstance(result["prerequisites_status"], dict)


def test_diagnostor_for_kaoyan():
    """考研诊断：返回考研学科。"""
    diagnostor = Diagnostor(MockModel(), KnowledgeBase())
    learner = make_learner(grade_level="graduate_exam")
    result = diagnostor.run(learner, "极限的 ε-δ 定义", "kaoyan_math")
    assert result["subject"] == "kaoyan_math"


# ─────────────────────────────────────
# Planner 测试
# ─────────────────────────────────────


def test_planner_basic():
    """基本计划：返回步骤序列。"""
    planner = Planner(MockModel(), KnowledgeBase())
    learner = make_learner()
    tone_info = select_tone("physics")
    diagnosis = {"ready_to_teach": True}
    plan = planner.run(learner, diagnosis, "physics", "熵", tone_info)
    assert "steps" in plan
    assert len(plan["steps"]) >= 1
    assert "estimated_total_min" in plan


def test_planner_remedial_path():
    """诊断未通过时计划只有 1 步。"""
    planner = Planner(MockModel(), KnowledgeBase())
    learner = make_learner()
    tone_info = select_tone("physics")
    diagnosis = {"ready_to_teach": False, "prerequisites_status": {"x": {"mastery": 0.2}}}
    plan = planner.run(learner, diagnosis, "physics", "熵", tone_info)
    assert len(plan["steps"]) == 1


# ─────────────────────────────────────
# Presenter 测试
# ─────────────────────────────────────


def test_presenter_uses_worldview_tone():
    """呈现使用正确的语气。"""
    presenter = Presenter(MockModel(), KnowledgeBase())
    learner = make_learner()
    step = {"type": "present", "topic": "什么是熵", "worldview": "rigorous_cold"}
    tone_info = select_tone("physics")
    result = presenter.run(step, learner, [], tone_info)
    assert result["tone_used"] == "rigorous_cold"


def test_presenter_literature_uses_contemplative():
    """文学主题：使用 contemplative 语气。"""
    presenter = Presenter(MockModel(), KnowledgeBase())
    learner = make_learner()
    step = {"type": "present", "topic": "特洛伊", "worldview": "contemplative"}
    tone_info = select_tone("literature")
    result = presenter.run(step, learner, [], tone_info)
    assert result["tone_used"] == "contemplative"


# ─────────────────────────────────────
# Evaluator 测试
# ─────────────────────────────────────


def test_evaluator_returns_score_in_range():
    """评估分数在 [0, 1]。"""
    evaluator = Evaluator(MockModel(), KnowledgeBase())
    learner = make_learner()
    step = {"type": "evaluate", "topic": "test", "worldview": "balanced"}
    presentation = {"content": "...", "tone_used": "balanced"}
    result = evaluator.run(step, learner, presentation)
    assert 0 <= result["score"] <= 1


def test_evaluator_returns_ready_to_advance():
    """评估返回 ready_to_advance 字段。"""
    evaluator = Evaluator(MockModel(), KnowledgeBase())
    learner = make_learner()
    step = {"type": "evaluate", "topic": "test", "worldview": "balanced"}
    presentation = {"content": "...", "tone_used": "balanced"}
    result = evaluator.run(step, learner, presentation)
    assert "ready_to_advance" in result


# ─────────────────────────────────────
# Adapter 测试
# ─────────────────────────────────────


def test_adapter_low_score_switches_style():
    """评估低分：调整到 switch_style。"""
    adapter = Adapter(MockModel(), KnowledgeBase())
    learner = make_learner()
    step = {"type": "evaluate", "topic": "test", "worldview": "balanced"}
    evaluation = {"score": 0.3, "ready_to_advance": False}
    result = adapter.run(evaluation, learner, step)
    assert result["decision"] in {"switch_style", "reinforce"}


def test_adapter_high_score_skips():
    """评估高分：调整到 skip（基础已掌握，进入拔高）。"""
    adapter = Adapter(MockModel(), KnowledgeBase())
    learner = make_learner()
    step = {"type": "evaluate", "topic": "test", "worldview": "balanced"}
    evaluation = {"score": 0.95, "ready_to_advance": True}
    result = adapter.run(evaluation, learner, step)
    assert result["decision"] == "skip"


# ─────────────────────────────────────
# WorldView 测试
# ─────────────────────────────────────


def test_worldview_physics_tone():
    assert select_tone("physics")["tone"] == "rigorous_cold"


def test_worldview_math_tone():
    assert select_tone("math")["tone"] == "rigorous_cold"


def test_worldview_literature_tone():
    assert select_tone("literature")["tone"] == "contemplative"


def test_worldview_ethics_tone():
    assert select_tone("ethics")["tone"] == "warm_caring"


def test_worldview_career_tone():
    assert select_tone("career")["tone"] == "pragmatic"


def test_worldview_kaoyan_politics_tone():
    """考研政治默认 rigorous_cold。"""
    assert select_tone("kaoyan_politics")["tone"] == "rigorous_cold"


def test_worldview_kaoyan_politics_maoyuan_tone():
    """考研政治-马原：rigorous_cold（更重）。"""
    assert select_tone("kaoyan_politics_maoyuan")["tone"] == "rigorous_cold"


def test_worldview_kaoyan_politics_sixiang_tone():
    """考研政治-思修：warm_caring（关怀式）。"""
    assert select_tone("kaoyan_politics_sixiang")["tone"] == "warm_caring"


def test_worldview_unknown_tone():
    """未知主题：默认 balanced。"""
    assert select_tone("unknown_topic_xyz")["tone"] == "balanced"


def test_worldview_ratio_sums_to_one():
    """所有主题的比例和为 1。"""
    for theme, (tone, ratio, _) in THEME_TONE_MAP.items():
        total = sum(ratio.values())
        assert abs(total - 1.0) < 0.01, f"{theme} ratio sums to {total}"


# ─────────────────────────────────────
# SelfUpdate 测试
# ─────────────────────────────────────


def test_self_update_incremental_records_reflection():
    """增量更新：记录反思。"""
    paeg = make_paeg()
    learner = make_learner()
    paeg.teach(learner, "什么是熵？", "physics")
    assert len(paeg.self_updater.history) > 0


def test_self_update_profile_mastery_ema():
    """增量更新：学生掌握度通过 EMA 更新。"""
    paeg = make_paeg()
    learner = make_learner()
    paeg.teach(learner, "什么是熵？", "physics")
    assert "physics" in learner.subjects_mastery
    assert 0 <= learner.subjects_mastery["physics"]["mastery"] <= 1


def test_self_update_ema_alpha_0_3():
    """EMA α = 0.3：单次会话对初始 0.5 的影响幅度约为 0.15。"""
    paeg = make_paeg()
    learner = make_learner()
    paeg.teach(learner, "什么是熵？", "physics")
    # 期望：new ≈ 0.5 + 0.3 * (avg_score - 0.5)
    # avg_score 通常在 0.7-0.85，所以 mastery 应在 0.55-0.605
    assert 0.5 < learner.subjects_mastery["physics"]["mastery"] < 0.7


def test_self_update_batch_returns_six_keys():
    """批处理：返回 6 个关键字段。"""
    paeg = make_paeg()
    learner = make_learner()
    paeg.teach(learner, "什么是熵？", "physics")
    batch = paeg.self_updater.batch_update()
    assert "recurring_concepts" in batch
    assert "candidate_strategies" in batch
    assert "adopted_strategies" in batch
    assert "total_sessions" in batch
    assert "rollback_required" in batch
    assert "version_log_size" in batch


def test_self_update_min_evidence_threshold_3():
    """保守阈值：MIN_EVIDENCE_FOR_STRATEGY = 3。"""
    updater = SelfUpdater(KnowledgeBase())
    assert updater.MIN_EVIDENCE_FOR_STRATEGY == 3


def test_self_update_min_confidence_threshold_0_8():
    """保守阈值：MIN_CONFIDENCE_FOR_KNOWLEDGE = 0.8。"""
    updater = SelfUpdater(KnowledgeBase())
    assert updater.MIN_CONFIDENCE_FOR_KNOWLEDGE == 0.8


def test_self_update_profile_ema_alpha_0_3():
    """保守阈值：PROFILE_EMA_ALPHA = 0.3。"""
    updater = SelfUpdater(KnowledgeBase())
    assert updater.PROFILE_EMA_ALPHA == 0.3


# ─────────────────────────────────────
# KnowledgeBase 测试
# ─────────────────────────────────────


def test_kb_has_subjects():
    """知识库至少有高中+考研的学科节点。"""
    kb = KnowledgeBase()
    assert "physics.thermodynamics.entropy" in kb.subjects
    assert "kaoyan.politics.dialectics" in kb.subjects
    assert "kaoyan.math.limits" in kb.subjects


def test_kb_has_humanities():
    """知识库有素养节点。"""
    kb = KnowledgeBase()
    assert "literature.epic.iliad" in kb.humanities
    assert "ethics.dilemma.trolley" in kb.humanities
    assert "phenomenology.loneliness" in kb.humanities


def test_kb_has_strategies():
    """知识库有教学策略。"""
    kb = KnowledgeBase()
    assert "socratic_dialogue" in kb.strategies
    assert "scaffolding" in kb.strategies


def test_kb_search_subjects():
    """学科搜索：能查到熵。"""
    kb = KnowledgeBase()
    results = kb.search_subjects("熵")
    assert len(results) > 0


def test_kb_search_subjects_filter():
    """学科搜索：按 subject 过滤。"""
    kb = KnowledgeBase()
    results = kb.search_subjects("极限", subject="kaoyan_math")
    assert len(results) > 0


def test_kb_add_knowledge_rejects_low_confidence():
    """新知识入库：可信度 <0.8 被拒绝（保守）。"""
    updater = SelfUpdater(KnowledgeBase())
    try:
        updater.add_knowledge(
            node={"id": "test.bad", "subject": "physics", "level": "high_school"},
            source="test",
            confidence=0.5,  # < 0.8
        )
        assert False, "应该抛错"
    except ValueError:
        pass  # 期望行为


def test_kb_add_knowledge_rejects_no_source():
    """新知识入库：无 source 被拒绝。"""
    updater = SelfUpdater(KnowledgeBase())
    try:
        updater.add_knowledge(
            node={"id": "test.bad", "subject": "physics", "level": "high_school"},
            source="",
            confidence=1.0,
        )
        assert False, "应该抛错"
    except ValueError:
        pass  # 期望行为


# ─────────────────────────────────────
# PAEG 端到端测试
# ─────────────────────────────────────


def test_e2e_physics():
    """端到端：物理教学。"""
    paeg = make_paeg()
    learner = make_learner()
    result = paeg.teach(learner, "什么是熵？", "physics")
    assert result["summary"]["avg_score"] > 0


def test_e2e_math():
    """端到端：数学教学。"""
    paeg = make_paeg()
    learner = make_learner()
    result = paeg.teach(learner, "为什么负负得正？", "math")
    assert result["summary"]["avg_score"] > 0


def test_e2e_literature():
    """端到端：文学教学。"""
    paeg = make_paeg()
    learner = make_learner()
    result = paeg.teach(learner, "为什么特洛伊战争持续十年？", "literature")
    assert result["summary"]["avg_score"] > 0


def test_e2e_ethics():
    """端到端：道德教学。"""
    paeg = make_paeg()
    learner = make_learner()
    result = paeg.teach(learner, "电车难题该拉开关吗？", "ethics")
    assert result["summary"]["avg_score"] > 0


def test_e2e_phenomenology():
    """端到端：生命现象学。"""
    paeg = make_paeg()
    learner = make_learner()
    result = paeg.teach(learner, "为什么人会感到孤独？", "phenomenology")
    assert result["summary"]["avg_score"] > 0


def test_e2e_kaoyan_politics():
    """端到端：考研政治-马原。"""
    paeg = make_paeg()
    learner = make_learner(grade_level="graduate_exam")
    result = paeg.teach(learner, "如何理解对立统一规律？", "kaoyan_politics_maoyuan")
    assert result["summary"]["avg_score"] > 0
    assert result["worldview_used"] == "rigorous_cold"


def test_e2e_kaoyan_math():
    """端到端：考研数学-极限。"""
    paeg = make_paeg()
    learner = make_learner(grade_level="graduate_exam")
    result = paeg.teach(learner, "极限的 ε-δ 定义是什么？", "kaoyan_math")
    assert result["summary"]["avg_score"] > 0


def test_e2e_all_subjects_use_correct_tone():
    """所有学科的呈现都使用对应语气。"""
    expected = {
        "physics": "rigorous_cold",
        "math": "rigorous_cold",
        "literature": "contemplative",
        "ethics": "warm_caring",
        "phenomenology": "contemplative",
        "kaoyan_politics_maoyuan": "rigorous_cold",
        "kaoyan_math": "rigorous_cold",
    }
    learner = make_learner()
    for subject, expected_tone in expected.items():
        paeg = make_paeg()
        result = paeg.teach(learner, "示例问题", subject)
        assert result["worldview_used"] == expected_tone, (
            f"{subject}: expected {expected_tone}, got {result['worldview_used']}"
        )


def test_e2e_self_update_records_history():
    """端到端：自我更新记录历史。"""
    paeg = make_paeg()
    learner = make_learner()
    paeg.teach(learner, "什么是熵？", "physics")
    assert len(paeg.self_updater.history) >= 1


def test_e2e_session_has_unique_id():
    """端到端：每个会话有唯一 ID。"""
    paeg = make_paeg()
    learner = make_learner()
    r1 = paeg.teach(learner, "什么是熵？", "physics")
    r2 = paeg.teach(learner, "为什么负负得正？", "math")
    assert r1["session"].session_id != r2["session"].session_id


# ─────────────────────────────────────
# 工具：pytest 主入口
# ─────────────────────────────────────


if __name__ == "__main__":
    # 直接运行：列出所有测试函数
    import inspect

    current_module = sys.modules[__name__]
    tests = [
        (name, fn)
        for name, fn in inspect.getmembers(current_module, inspect.isfunction)
        if name.startswith("test_")
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {name}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"总计：{passed + failed} | 通过：{passed} | 失败：{failed}")
    print(f"{'='*60}")
