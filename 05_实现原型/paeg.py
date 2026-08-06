"""
PAEG (Pedagogical Agent with Evolving Growth) v0.5
真实 LLM 可接入的教学智能体主类。
"""

import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from knowledge_base import KnowledgeBase
from subagents import Diagnostor, Planner, Presenter, Evaluator, Adapter
from world_view import select_tone
from self_update import SelfUpdater


@dataclass
class LearnerProfile:
    """学习者画像。"""
    id: str
    nickname: str
    grade_level: str  # high_school / undergraduate / graduate_exam
    age: int
    cognitive_style: str = "visual"  # visual/auditory/reading/kinesthetic
    subjects_mastery: dict = field(default_factory=dict)
    world_view_blend: dict = field(default_factory=lambda: {1: 0.20, 2: 0.35, 3: 0.35, 4: 0.10})
    privacy_parent_notify: bool = False
    # v0.3+ 兼容字段（考研适配）
    target_exam: Optional[str] = None
    specialty_target: Optional[str] = None
    # v0.10：用户自我描述（"我是怎样的人/目标/擅长与不擅长"），每次对话自动注入
    self_description: str = ""


@dataclass
class SessionContext:
    """一次教学会话的完整上下文。"""
    learner: LearnerProfile
    concept: str
    subject: str
    history: list = field(default_factory=list)
    plan: Optional[dict] = None
    diagnosis: Optional[dict] = None
    evaluations: list = field(default_factory=list)
    reflections: list = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = field(default_factory=lambda: "ses_" + datetime.now().strftime("%Y%m%d%H%M%S%f"))


class PAEG:
    """PAEG 主类。"""

    def __init__(self, model_api, knowledge_base: KnowledgeBase, enable_self_update=True,
                 verbose: bool = False, enable_refiner: bool = True):
        self.model = model_api
        self.kb = knowledge_base
        self.diagnostor = Diagnostor(model_api, knowledge_base)
        self.planner = Planner(model_api, knowledge_base)
        self.presenter = Presenter(model_api, knowledge_base)
        self.evaluator = Evaluator(model_api, knowledge_base)
        self.adapter = Adapter(model_api, knowledge_base)
        self.self_updater = SelfUpdater(knowledge_base) if enable_self_update else None
        # v0.12：语言优化 Agent（薇依语料矫正，去除 AI 痕迹）
        self.refiner = None
        if enable_refiner:
            try:
                from language_refiner import LanguageRefiner
                self.refiner = LanguageRefiner(model_api)
            except Exception as _e:
                print(f"[PAEG] 语言优化 Agent 初始化失败（跳过）: {_e}")
        # v0.15：自我更新模块（Reflexion 微反思 + ExpeL 周度洞察）
        self.evolver = None
        try:
            from self_evolve import SelfEvolver
            self.evolver = SelfEvolver(model_api)
        except Exception as _e:
            print(f"[PAEG] 自我更新模块初始化失败（跳过）: {_e}")
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def teach(self, learner: LearnerProfile, question: str, subject: str) -> dict:
        """
        完整教学流程：诊断 -> 计划 -> 呈现（多步） -> 评估 -> 调整 -> 反思 -> 自我更新。
        返回 {"session": ..., "summary": ..., "worldview_used": ..., "tone_ratio": ...}
        """
        session = SessionContext(
            learner=learner,
            concept=question,
            subject=subject
        )

        # 1. 诊断
        self._log(f"\n[1/5] 诊断子代理：评估 {learner.nickname} 的当前水平...")
        session.diagnosis = self.diagnostor.run(
            learner=learner,
            question=question,
            subject=subject
        )
        self._log(f"   OK 诊断完成：ready_to_teach={session.diagnosis.get('ready_to_teach', True)}"
              f"（{session.diagnosis.get('diagnosed_by', 'rule')}）")

        # 2. 计划
        self._log(f"\n[2/5] 计划子代理：设计教学路径...")
        session.plan = self.planner.run(
            learner=learner,
            diagnosis=session.diagnosis,
            subject=subject,
            concept=question
        )
        self._log(f"   OK 计划完成：{len(session.plan['steps'])} 步")

        # 世界观语气（贯穿全程）
        tone_info = select_tone(subject)

        # v0.11：对象意识——从会话历史推断用户特征（动态模型）
        try:
            from agent_core import infer_user_model, infer_bdi
            user_model = infer_user_model(
                history=[{"content": q.get("content", "")} for q in session.history],
                description=getattr(learner, "self_description", "") or "",
            )
            # v0.13：BDI 推断（信念/愿望/意图）
            bdi = infer_bdi(
                history=[{"content": q.get("content", "")} for q in session.history],
                description=getattr(learner, "self_description", "") or "",
            )
            user_model["bdi"] = bdi
            # 附加到 learner（transient，Presenter 读取）
            learner._user_model = user_model  # type: ignore[attr-defined]
        except Exception:
            learner._user_model = None  # type: ignore[attr-defined]

        # 3. 呈现（按计划逐步）
        for i, step in enumerate(session.plan['steps']):
            self._log(f"\n[3/5] 呈现子代理：第 {i+1}/{len(session.plan['steps'])} 步 - "
                  f"{step['type']} - {step['topic']}")
            presentation = self.presenter.run(
                step=step,
                learner=learner,
                previous=session.history,
                tone_info=tone_info,
                concept=question,
                subject=subject,
            )
            # v0.12：语言优化 Agent 矫正（去除 AI 痕迹，薇依化）
            if self.refiner and presentation.get("llm_generated"):
                content = presentation.get("content", "")
                if content:
                    try:
                        refined = self.refiner.refine(content, context=f"教学：{subject} - {question}")
                        if refined and refined != content:
                            presentation["content"] = refined
                            presentation["refined"] = True
                    except Exception as _e:
                        self._log(f"   (语言矫正跳过: {_e})")
            session.history.append(presentation)
            gen = "LLM" if presentation.get("llm_generated") else "规则"
            self._log(f"   OK 呈现完成：{gen} 生成，长度 {len(presentation['content'])} 字符")

            # 4. 评估（每个呈现步骤后）
            self._log(f"   -> 评估子代理：检查学生理解...")
            evaluation = self.evaluator.run(
                step=step,
                learner=learner,
                presentation=presentation
            )
            session.evaluations.append(evaluation)
            self._log(f"   OK 评估分数：{evaluation['score']}")

            # 5. 调整（必要时）
            if not evaluation.get('ready_to_advance', True):
                self._log(f"   -> 调整子代理：触发调整...")
                adjustment = self.adapter.run(
                    evaluation=evaluation,
                    learner=learner,
                    step=step
                )
                if adjustment['decision'] in ['reinforce', 'switch_style']:
                    self._log(f"   OK 决策：{adjustment['decision']} - {adjustment['action']['details']}")

        # 6. 元认知反思
        self._log(f"\n[6/6] 元认知反思：本次教学总结...")
        reflection = self._reflect(session)
        session.reflections.append(reflection)
        self._log(f"   OK 反思完成：success={reflection.get('success')}")

        # 6.5 v0.13：Actor-Critic 自我认知反思（薇依对齐 + 语言 + 教学）
        try:
            self_reflection = self._self_reflect(session)
            session.reflections.append(self_reflection)
            if not all([self_reflection.get("weil_alignment"),
                        self_reflection.get("language_quality"),
                        self_reflection.get("teaching_effectiveness")]):
                self._log(f"   ⚠️ 自检发现改进点：{self_reflection.get('improvements')}")
        except Exception as _e:
            self._log(f"   (自我反思跳过: {_e})")

        # 7. 自我更新（如果启用）
        if self.self_updater:
            self.self_updater.incremental_update(session)
            self._log(f"   OK 自我更新完成")

        # 7.5 v0.15：自我进化（Reflexion 微反思——EMA 下降时诊断原因）
        if self.evolver:
            try:
                ema_delta = 0.0
                if session.evaluations:
                    avg = sum(e['score'] for e in session.evaluations) / len(session.evaluations)
                    ema_delta = avg - 0.7  # 相对达标线
                dialogue_summary = "；".join(
                    p.get("content", "")[:100] for p in session.history[:2]
                )
                entry = self.evolver.on_session_end(
                    student_id=learner.id,
                    dialogue_summary=dialogue_summary or question,
                    ema_delta=ema_delta,
                    subject=subject,
                )
                if entry:
                    self._log(f"   🔄 自我进化：记录反思（EMA Δ={ema_delta:.2f}）")
            except Exception as _e:
                self._log(f"   (自我进化跳过: {_e})")

        return {
            "session": session,
            "summary": self._summarize(session),
            "worldview_used": tone_info["tone"],
            "tone_ratio": tone_info["ratio"],
        }

    def _reflect(self, session: SessionContext) -> dict:
        """每会话反思（空评估防除零）。"""
        if session.evaluations:
            avg_score = sum(e['score'] for e in session.evaluations) / len(session.evaluations)
        else:
            avg_score = 0.0
        return {
            "timestamp": datetime.now().isoformat(),
            "learner_id": session.learner.id,
            "concept": session.concept,
            "avg_score": avg_score,
            "success": avg_score >= 0.7,
            "notes": f"学生 {session.learner.nickname} 在 '{session.concept}' 上的平均掌握度为 {avg_score:.2f}"
        }

    def _self_reflect(self, session: SessionContext) -> dict:
        """v0.13：Actor-Critic 自我认知反思。

        教学完成后，自检三个方面（Critic 角色）：
        1. 薇依价值对齐：是否尊重学生、不评判、以注意力相待
        2. 语言质量：是否有 AI 味（套话/三段清单/破折号滥用）
        3. 教学有效性：是否真正引导学生思考而非灌输
        """
        check = {
            "weil_alignment": True,
            "language_quality": True,
            "teaching_effectiveness": True,
            "issues": [],
            "improvements": [],
        }

        # 语言质量检查（用 AI 味检测器）
        try:
            from ai_taste_detector import detect_ai_taste
            for p in session.history:
                content = p.get("content", "")
                if content:
                    s = detect_ai_taste(content)
                    if s.ai_likelihood >= 0.4:
                        check["language_quality"] = False
                        check["issues"].append(f"第{len(check['issues'])+1}步有 AI 味（概率{s.ai_likelihood:.2f}）")
                        check["improvements"].append("下次生成后应加强薇依式改写")
                        break
        except Exception:
            pass

        # 薇依价值对齐（规则检查：是否有廉价鼓励/评判性语言）
        cheap_praise = ("你真棒", "加油", "你一定可以", "太聪明了")
        judging = ("你错了", "这都不会", "你怎么这么")
        all_content = " ".join(p.get("content", "") for p in session.history)
        for cp in cheap_praise:
            if cp in all_content:
                check["weil_alignment"] = False
                check["issues"].append(f"出现廉价鼓励 '{cp}'（薇依反对：它不是注意力的替代品）")
                check["improvements"].append("用具体的确认代替鼓励，如'你说的这个方向对'")
                break
        for jd in judging:
            if jd in all_content:
                check["weil_alignment"] = False
                check["issues"].append(f"出现评判性语言 '{jd}'（薇依：不评判学生，只看眼前的事）")
                check["improvements"].append("改为引导：'我们一起看看这一步'")
                break

        # 教学有效性（评估分数）
        if session.evaluations:
            avg = sum(e["score"] for e in session.evaluations) / len(session.evaluations)
            if avg < 0.6:
                check["teaching_effectiveness"] = False
                check["issues"].append(f"教学平均分偏低（{avg:.2f}）")
                check["improvements"].append("下次用更小的台阶、更多引导性问题")

        return {
            "timestamp": datetime.now().isoformat(),
            "learner_id": session.learner.id,
            "concept": session.concept,
            "type": "self_reflect",
            **check,
        }

    def _summarize(self, session: SessionContext) -> dict:
        """会话总结。"""
        if session.evaluations:
            avg = sum(e['score'] for e in session.evaluations) / len(session.evaluations)
        else:
            avg = 0.0
        from world_view import select_tone
        tone_info = select_tone(session.subject)
        return {
            "concept": session.concept,
            "subject": session.subject,
            "learner": session.learner.nickname,
            "avg_score": avg,
            "steps_completed": len(session.history),
            "duration_min": len(session.history) * 2,  # 估算
            "worldview_used": tone_info["tone"],
            "tone_ratio": tone_info["ratio"],
        }


# 使用示例（离线 mock）
if __name__ == "__main__":
    from llm_api import MockModelAPI

    model = MockModelAPI("[模拟回复]")
    kb = KnowledgeBase()
    paeg = PAEG(model, kb)

    learner = LearnerProfile(
        id="001",
        nickname="小李",
        grade_level="high_school",
        age=17
    )

    result = paeg.teach(learner, "什么是熵？", "physics")
    print(f"\n总结：{result['summary']}")