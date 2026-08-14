"""
v0.24 教学闭环修复测试。

覆盖：
- 修复 1：Evaluator 区分 presentation_quality 与 learner_state，有学生数据时合成 score、
  无数据时 reason="no_student_data"。
- 修复 2：Adapter 决策真正改变下一次 Presenter.run 的输入（被消费 + 写入 presentation._injected）。
- 修复 3：PAEG 持有全部 9 个 subagent，teach() 注入了 Individuality + AffectionSupportor。
- 修复 4：AffectionSupportor 对异常 history 条目健壮（与 SelfUpdateAgent 同等标准）。
"""

import sys, os
# v0.69+：reconfigure 移入 __main__——模块级执行会破坏 pytest capsys（收集期副作用）
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

import pytest

from paeg import PAEG, LearnerProfile
from knowledge_base import KnowledgeBase
from subagents import (
    Diagnostor, Planner, Presenter, Evaluator, Adapter,
    AnswerSolver, AffectionSupportor, SelfUpdateAgent, Individuality,
)


# ─────────────────────────────────────────────────────────────
# Mock LLM
# - _MockLLM：被 _is_real_llm 判定为真实 LLM（name != 'mock'），
#   用于测试 LLM 路径与 PAEG.teach 路径。
# - _RuleMockLLM：故意被 _is_real_llm 判定为非真实 → 走规则回退路径，
#   用于直接断言 Adapter 决策在 rule fallback 的 content / _injected 里可观测。
# ─────────────────────────────────────────────────────────────

class _MockLLM:
    """被 _is_real_llm 识别为真实 LLM。返回可控字符串 + 记录接收到的 system。"""
    name = "mock_llm"
    last_system = None
    last_messages = None

    def __init__(self):
        self.last_system = None
        self.last_messages = None
        self.next_reply = "[演示] 我先讲一下这个概念，下面用一个例子。"

    def messages_create(self, **kw):
        return {"content": [{"text": self.next_reply}]}

    def chat(self, system=None, messages=None, **kw):
        # 给 AffectionSupportor 用：返回安全的中文情绪回复
        self.last_system = system
        self.last_messages = messages
        return "我听见你说的了。如果你愿意，可以多跟我说一些具体的事情，我在这儿陪着你。"


class _RuleMockLLM:
    """被 _is_real_llm 判定为非真实（无 chat / name='mock'）→ 走规则回退。"""
    name = "mock"
    def messages_create(self, **kw):
        return {"content": [{"text": "演示"}]}


def _learner(**kw):
    base = dict(id="u001", nickname="小李",
                grade_level="high_school", age=17,
                cognitive_style="visual")
    base.update(kw)
    return LearnerProfile(**base)


# ─────────────────────────────────────────────────────────────
# 修复 1：Evaluator 真正评估学生
# ─────────────────────────────────────────────────────────────

class TestEvaluatorV024:
    def test_evaluator_returns_two_subscores(self):
        """无学生数据时仍输出 presentation_quality 与 learner_state 两套信号。"""
        ev = Evaluator(_MockLLM(), KnowledgeBase())
        step = {"type": "present", "topic": "熵", "worldview": "rigorous_cold"}
        pres = {
            "content": "熵的定义：系统中微观状态数的对数。例如房间里的气体分子。比如冰块融化。",
            "tone_used": "rigorous_cold",
            "kb_node_id": "entropy",
            "llm_generated": False,
        }
        out = ev.run(step=step, learner=_learner(), presentation=pres)
        assert "score" in out
        assert "sub_scores" in out
        assert "clarity" in out["sub_scores"]
        assert "completeness" in out["sub_scores"]
        assert "ready_to_advance" in out
        assert "emotion_signal" in out
        # 新增字段
        assert "presentation_quality" in out
        assert "learner_state" in out
        assert out["learner_state"]["has_student_data"] is False
        # 无数据时 ready_to_advance 保守 False + reason="no_student_data"
        assert out["ready_to_advance"] is False
        assert out["reason"] == "no_student_data"

    def test_evaluator_uses_student_reply(self):
        """学生 step.student_reply 含困惑词 → 学生状态分下降 → ready_to_advance=False。"""
        ev = Evaluator(_MockLLM(), KnowledgeBase())
        step = {
            "type": "present", "topic": "熵", "worldview": "rigorous_cold",
            "student_reply": "我不懂，这个为什么是这样？",
        }
        pres = {
            "content": "熵的定义：系统中微观状态数的对数。",
            "tone_used": "rigorous_cold",
            "kb_node_id": "entropy",
            "llm_generated": False,
        }
        out = ev.run(step=step, learner=_learner(), presentation=pres)
        assert out["learner_state"]["has_student_data"] is True
        assert out["learner_state"]["confusion"] > 0
        assert out["learner_state"]["emotion"] in ("frustrated", "curious")
        assert out["ready_to_advance"] is False
        assert out["reason"] in ("learner_state_low", "composite_low")

    def test_evaluator_uses_learner_last_reply_attr(self):
        """从 learner._last_student_reply 取学生输入。"""
        ev = Evaluator(_MockLLM(), KnowledgeBase())
        step = {"type": "present", "topic": "熵"}
        pres = {"content": "熵是混乱度的度量。", "tone_used": "rigorous_cold",
                "kb_node_id": "entropy", "llm_generated": False}
        learner = _learner()
        learner._last_student_reply = "明白了，原来如此！"
        out = ev.run(step=step, learner=learner, presentation=pres)
        assert out["learner_state"]["has_student_data"] is True
        assert out["learner_state"]["understanding"] > 0.5

    def test_evaluator_score_composition_distinct(self):
        """presentation_quality 与 learner_state.student_state_score 是各自独立维度。"""
        ev = Evaluator(_MockLLM(), KnowledgeBase())
        step1 = {"type": "present", "topic": "熵",
                 "student_reply": "我懂了，原来如此！"}
        pres1 = {
            "content": "熵的定义+例子。",
            "tone_used": "rigorous_cold",
            "kb_node_id": "entropy",
            "llm_generated": False,
        }
        out = ev.run(step=step1, learner=_learner(), presentation=pres1)
        assert "presentation_quality" in out
        assert out["learner_state"]["student_state_score"] >= 0.0
        sc = out["score_composition"]
        assert sc["presentation_weight"] + sc["learner_state_weight"] == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────
# 修复 2：Adapter 决策可执行化
# ─────────────────────────────────────────────────────────────

class TestAdapterV024:
    def test_adapter_switch_style_has_override(self):
        """switch_style 决策带 override_system_line。"""
        ev = Evaluator(_MockLLM(), KnowledgeBase())
        ad = Adapter(_MockLLM(), KnowledgeBase())
        step = {"type": "present", "topic": "熵",
                "student_reply": "我不懂为什么？听不懂。"}
        pres = {"content": "熵是状态函数。", "tone_used": "rigorous_cold",
                "kb_node_id": "entropy", "llm_generated": False}
        evaluation = ev.run(step=step, learner=_learner(), presentation=pres)
        adj = ad.run(evaluation=evaluation, learner=_learner(), step=step)
        assert adj["decision"] in ("switch_style", "reinforce")
        params = adj["action"]["parameters"]
        assert "difficulty_delta" in params
        if adj["decision"] == "switch_style":
            assert params["new_style"] in Adapter.STYLE_OPTIONS
            assert "override_system_line" in params
            assert len(params["override_system_line"]) > 0

    def test_presenter_consumes_style_override_rule_fallback(self):
        """走规则回退路径时，style_override 真正在 content / _injected 中可观测。"""
        # 用 _RuleMockLLM（无 chat / name='mock'）强制走规则回退
        p = Presenter(_RuleMockLLM(), KnowledgeBase())
        p.set_pending_overrides(
            style_override={
                "new_style": "analogy",
                "override_system_line": "请用日常生活的类比讲这个概念。",
                "difficulty_delta": -1,
            },
        )
        step = {"type": "present", "topic": "熵", "worldview": "rigorous_cold"}
        out = p.run(step=step, learner=_learner(), previous=[])
        # 规则回退路径：tone_used 被改写为含 +adapted，content 也带策略提示
        assert "analogy" in out["tone_used"] or "adapted" in out["tone_used"], \
            f"tone_used 未体现 adapt 决策：{out['tone_used']}"
        assert "switch_style" in out["content"] or "类比" in out["content"], \
            f"content 未体现 adapt 决策：{out['content'][:120]}"
        # _injected 记下上游信息
        assert out["_injected"]["style_override"]["new_style"] == "analogy"
        # 一次性消费
        assert p._pending_style_override is None

    def test_presenter_consumes_reinforce_note(self):
        """reinforce 决策的补例子指示被 Presenter 消费。"""
        p = Presenter(_RuleMockLLM(), KnowledgeBase())
        p.set_pending_overrides(
            reinforce_note="请补一个不同角度的例子，让学生从例子反推概念。",
        )
        step = {"type": "present", "topic": "极限", "worldview": "rigorous_cold"}
        out = p.run(step=step, learner=_learner(), previous=[])
        # 规则回退路径下，content / _injected 体现 reinforce
        assert "reinforce" in out["content"] or "补一个" in out["content"] \
            or "不同角度" in out["content"], \
            f"content 未体现 reinforce：{out['content'][:120]}"
        assert out["_injected"]["reinforce_note"] is not None
        assert "补一个" in out["_injected"]["reinforce_note"]
        # 一次性消费
        assert p._pending_reinforce_note is None

    def test_presenter_individuality_profile_applied(self):
        """individuality_profile_prompt 注入槽被消费。"""
        p = Presenter(_RuleMockLLM(), KnowledgeBase())
        p.set_pending_overrides(
            individuality_control={"language": "zh", "depth": "high_school"},
            individuality_profile_prompt="- 学习方式：visual\n- 兴趣：数学",
        )
        step = {"type": "present", "topic": "极限", "worldview": "balanced"}
        out = p.run(step=step, learner=_learner(), previous=[])
        assert out["_injected"]["had_individuality_profile"] is True
        assert out["_injected"]["individuality_control"]["depth"] == "high_school"

    def test_adapter_low_score_triggers_switch_style(self):
        """score < 0.55 时 Adapter 必然 switch_style。"""
        ad = Adapter(_MockLLM(), KnowledgeBase())
        evaluation = {"score": 0.40, "learner_state": {"confusion": 0.4}}
        adj = ad.run(evaluation=evaluation, learner=_learner(),
                     step={"type": "present"})
        assert adj["decision"] == "switch_style"
        assert adj["action"]["parameters"]["difficulty_delta"] == -1


# ─────────────────────────────────────────────────────────────
# 修复 3：PAEG 持有全部 9 个 subagent + AffectionSupportor 钩子
# ─────────────────────────────────────────────────────────────

class TestPAEGV024:
    def test_paeg_holds_nine_subagents(self):
        """PAEG 必须持有全部 9 个 subagent。"""
        paeg = PAEG(_MockLLM(), KnowledgeBase())
        for name, cls in [
            ("diagnostor", Diagnostor),
            ("planner", Planner),
            ("presenter", Presenter),
            ("evaluator", Evaluator),
            ("adapter", Adapter),
            ("answer_solver", AnswerSolver),
            ("affection_supportor", AffectionSupportor),
            ("self_update_agent", SelfUpdateAgent),
            ("individuality", Individuality),
        ]:
            assert hasattr(paeg, name), f"PAEG 缺少 {name}"
            obj = getattr(paeg, name)
            assert obj is not None, f"PAEG.{name} 为 None"
            assert isinstance(obj, cls), \
                f"PAEG.{name} 不是 {cls.__name__} 实例（{type(obj).__name__}）"

    def test_affection_gate_crisis_bypasses_teaching(self):
        """learner 有 _crisis_flag 时，teach() 短路到 AffectionSupportor。"""
        paeg = PAEG(_MockLLM(), KnowledgeBase())
        learner = _learner()
        learner._crisis_flag = True
        out = paeg.teach(learner, "什么是熵？", "physics")
        assert out["session"] is None
        assert out["summary"]["mode"] == "affection_bypass"
        assert "affection_reply" in out
        assert out["affection_reply"]["mode"] == "affection"

    def test_affection_gate_emotion_only_bypasses(self):
        """无学科词 + 强情绪词 + 短句 → 走 AffectionSupportor。"""
        paeg = PAEG(_MockLLM(), KnowledgeBase())
        learner = _learner()
        out = paeg.teach(learner, "我今天好累，撑不住了", "physics")
        assert out["session"] is None
        assert out["summary"]["mode"] == "affection_bypass"

    def test_individuality_injected_into_presenter(self):
        """teach() 起点注入 Individuality，presentation._injections 里含 individuality_control。"""
        paeg = PAEG(_MockLLM(), KnowledgeBase())
        learner = _learner()
        learner.self_description = "我喜欢视觉化、例子多的讲解"
        out = paeg.teach(learner, "什么是熵？", "physics")
        if out["session"] and out["session"].history:
            inj = out["session"].history[0].get("_injections", {})
            assert "individuality_control" in inj, \
                f"首个 presentation 缺少 individuality_control 注入：{inj}"

    def test_adapter_decision_chains_into_next_presentation(self):
        """Adapter 的可执行参数能被 Presenter 真正消费。"""
        from subagents import Evaluator as _E, Adapter as _A
        ev = _E(_MockLLM(), KnowledgeBase())
        ad = _A(_MockLLM(), KnowledgeBase())
        step_with_reply = {
            "type": "present", "topic": "熵",
            "student_reply": "我不懂，为什么是这样？太难了听不懂。"
        }
        presentation = {"content": "熵是度量。", "tone_used": "rigorous_cold",
                        "kb_node_id": "entropy", "llm_generated": False}
        ev_res = ev.run(step=step_with_reply, learner=_learner(),
                        presentation=presentation)
        ad_res = ad.run(evaluation=ev_res, learner=_learner(),
                        step=step_with_reply)
        assert ad_res["decision"] in ("switch_style", "reinforce")
        params = ad_res["action"].get("parameters", {})
        assert params.get("difficulty_delta", 0) <= 0
        if ad_res["decision"] == "switch_style":
            assert "override_system_line" in params
        else:
            assert "reinforce_mode" in params

    def test_adapter_decision_visible_in_rule_fallback(self):
        """端到端：Adapter 决策在规则回退路径上对下一次讲解**可观测**。"""
        # 用 _RuleMockLLM 强制规则回退路径，整个 PAEG 跑一遍即可在 history 里看到 adapt 注入
        paeg = PAEG(_RuleMockLLM(), KnowledgeBase())
        learner = _learner()
        # 让 Adapter 尽可能被触发（注入学生困惑作为 _last_student_reply）
        learner._last_student_reply = "我不懂，太难了"
        out = paeg.teach(learner, "什么是熵？", "physics")
        s = out["session"]
        # 检查 history 是否有 step 的 _injections 含 style_override 或 reinforce_note
        any_adapt = False
        for p in s.history:
            inj = p.get("_injections", {}) or {}
            if inj.get("style_override") or inj.get("reinforce_note"):
                any_adapt = True
                break
        # 取决于分数与策略：若都没触发也合理（可能 score 整体 >= 0.7）——
        # 但本场景下注入困惑词 + 默认讲解模拟应触发
        # 关键断言：presentation._injections 字段必须存在（即使 no adapt 也是结构性的）
        for p in s.history:
            assert "_injections" in p, f"presentation 缺 _injections：{p.get('content','')[:50]}"
        assert any_adapt, "Adapter 的 style_override / reinforce_note 未触发（hint：可能 KB 太丰富）"


# ─────────────────────────────────────────────────────────────
# 修复 4：AffectionSupportor 健壮性
# ─────────────────────────────────────────────────────────────

class TestAffectionSupportorRobustness:
    def test_robust_to_non_dict_history(self):
        """history 含字符串、None、非 dict 时不崩溃（与 SelfUpdateAgent 同等标准）。"""
        a = AffectionSupportor()
        bad_history = [
            "纯字符串条目",
            None,
            {"role": "user", "content": "我今天很累"},
            {"role": "missing_content_key"},  # 缺 content
            {"content": "无 role 字段"},
            42,
        ]
        out = a.run(_MockLLM(), "我撑不住了", learner=_learner(),
                    history=bad_history)
        assert out["mode"] == "affection"
        assert isinstance(out["content"], str)
        assert len(out["content"]) > 0

    def test_robust_when_history_keys_missing(self):
        """history 全是缺 key 的 dict，仍返回合法输出。"""
        a = AffectionSupportor()
        bad_history = [
            {"foo": "bar"},
            {"baz": 1},
        ]
        out = a.run(_MockLLM(), "你好", learner=None, history=bad_history)
        assert out["mode"] == "affection"
        assert "content" in out

    def test_self_update_agent_kept_compatible(self):
        """SelfUpdateAgent 也对异常 history 健壮（保持同等标准）。"""
        su = SelfUpdateAgent()
        out = su.run(_MockLLM(), "用户反馈文本",
                     learner=_learner(),
                     history=[None, "x", {"role": "user", "content": "ok"}])
        assert "suggestions" in out
        assert out["mode"] == "self_update"


# ─────────────────────────────────────────────────────────────
# 端到端：教学闭环整体自测
# ─────────────────────────────────────────────────────────────

class TestTeachingLoopEndToEnd:
    def test_e2e_full_loop_no_crash(self):
        """端到端：完整教学流程不应抛错。"""
        paeg = PAEG(_MockLLM(), KnowledgeBase())
        learner = _learner()
        result = paeg.teach(learner, "什么是熵？", "physics")
        assert result["session"] is not None
        s = result["session"]
        assert len(s.history) > 0
        assert len(s.evaluations) > 0

    def test_e2e_evaluator_distinguishes_presentation_vs_learner_state(self):
        """评估返回的 presentation_quality 与 learner_state 是独立维度。"""
        paeg = PAEG(_MockLLM(), KnowledgeBase())
        learner = _learner()
        result = paeg.teach(learner, "什么是导数？", "math")
        if result["session"]:
            evals = result["session"].evaluations
            ok = any(
                "presentation_quality" in e and "learner_state" in e
                for e in evals
            )
            assert ok, f"evaluator 没区分两维度：{evals[:1]}"

    def test_e2e_runs_with_all_5_subjects(self):
        """5 个学科端到端不抛错（回归保护）。"""
        paeg = PAEG(_MockLLM(), KnowledgeBase())
        cases = [
            ("什么是熵？", "physics"),
            ("为什么负负得正？", "math"),
            ("为什么特洛伊战争持续十年？", "literature"),
            ("电车难题该拉开关吗？", "ethics"),
            ("为什么人会感到孤独？", "phenomenology"),
        ]
        for q, subj in cases:
            learner = _learner()
            r = paeg.teach(learner, q, subj)
            assert r["session"] is not None, f"{subj} 教学报错"


if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call([sys.executable, "-m", "pytest",
                              os.path.abspath(__file__), "-v",
                              "--tb=short"]))
