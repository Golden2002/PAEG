"""
5 个子代理（v0.5 版）。

v0.1：纯规则模拟。
v0.5：接入真实 LLM（ModelAPI.chat）：
  - Diagnostor：LLM 评估就绪度（失败回退规则）
  - Presenter：LLM 基于知识库节点 + 世界观语气重新生成讲解（失败回退规则）
  - Evaluator：确定性启发式评分（v0.2 设计：避免随机），不依赖 LLM
  - Planner / Adapter：规则驱动

兼容性：模型可以是
  - ModelAPI（llm_api.py，有 chat() 且 name != "mock"）-> 真实 LLM
  - 旧 MockModel（仅 messages_create）-> 按规则模式处理
"""

from __future__ import annotations  # 延迟求值注解，避免与 paeg.py 的循环导入

from typing import Optional

from prompts import build_presenter_system, build_presenter_user, normalize_subject


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _is_real_llm(model) -> bool:
    """判断模型是否为真实 LLM（ModelAPI 接口且非 mock）。"""
    return hasattr(model, "chat") and getattr(model, "name", "mock") != "mock"


def _safe_chat(model, system: str, user: str, max_tokens: int = 512) -> Optional[str]:
    """安全调用真实 LLM，失败返回 None（调用方回退规则模式）。"""
    if not _is_real_llm(model):
        return None
    try:
        return model.chat(
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=0.7,
        )
    except Exception:
        return None


_TONE_SUFFIX = {
    "rigorous_cold": "你冷静、严谨、强调证据。",
    "contemplative": "你沉静、邀请内省、保留沉默空间。",
    "warm_caring": "你温和、关怀、像过来人分享。",
    "pragmatic": "你务实、对话式、强调试试看。",
    "balanced": "",
}


def _learner_desc(learner) -> str:
    return (
        f"年级={getattr(learner, 'grade_level', 'high_school')}, "
        f"认知风格={getattr(learner, 'cognitive_style', 'visual')}"
    )


# ---------------------------------------------------------------------------
# 1. 诊断子代理
# ---------------------------------------------------------------------------

class Diagnostor:
    def __init__(self, model, kb):
        self.model = model
        self.kb = kb

    def run(self, learner, question: str, subject: str) -> dict:
        """诊断：基于知识库前置知识 +（可选）LLM 判断就绪度。"""
        # 规则部分：前置知识状态
        prereq_status = {}
        for node in self.kb.get_subject_nodes(subject):
            for p in node.get("prerequisites", []):
                prereq_status.setdefault(p, {"mastery": 0.8})

        # LLM 部分：深度与缺口分析（不覆盖 ready_to_teach，教学智能体默认可教）
        ready, depth, gaps = True, "moderate", []
        if _is_real_llm(self.model):
            user = (
                f"学生：{_learner_desc(learner)}。\n"
                f"问题：{question}（学科：{subject}）\n"
                f"该学科前置知识：{list(prereq_status.keys()) or '无明确前置'}。\n"
                f"请用 JSON 输出：{{\"recommended_depth\": \"basic/moderate/advanced\", "
                f"\"identified_gaps\": [\"...\"]}}\n只输出 JSON，不要任何解释文字。"
            )
            text = _safe_chat(self.model, "你是教学诊断助手，用一句话 JSON 给出教学深度建议，不要客套。", user, max_tokens=200)
            if text:
                import json as _json
                try:
                    parsed = _json.loads(text.strip().strip("`").strip())
                    if isinstance(parsed, dict):
                        depth = parsed.get("recommended_depth", "moderate")
                        gaps = parsed.get("identified_gaps", [])
                        if not isinstance(gaps, list):
                            gaps = [str(gaps)]
                except Exception:
                    pass

        return {
            "prerequisites_status": prereq_status,
            "ready_to_teach": ready,
            "recommended_depth": depth,
            "identified_gaps": gaps,
            "diagnosed_by": "llm" if _is_real_llm(self.model) else "rule",
        }


# ---------------------------------------------------------------------------
# 2. 计划子代理
# ---------------------------------------------------------------------------

class Planner:
    def __init__(self, model, kb):
        self.model = model
        self.kb = kb

    def run(self, learner, diagnosis: dict, subject: str, concept: str,
            tone_info: Optional[dict] = None) -> dict:
        """计划（v0.9）：基于诊断 + 学科选择教学策略，生成差异化步骤。"""
        from world_view import select_tone
        from pedagogy import choose_strategy, build_plan_steps

        if tone_info is None:
            tone_info = select_tone(subject)

        strategy = choose_strategy(learner, diagnosis, subject)
        steps = build_plan_steps(strategy, concept, tone_info["tone"])

        return {
            "steps": steps,
            "estimated_total_min": sum(s["duration_min"] for s in steps),
            "strategy": strategy["key"],
            "strategy_name": strategy["name"],
            "base_bloom": strategy["base_bloom"],
            "presenter_hint": strategy["presenter_hint"],
        }


# ---------------------------------------------------------------------------
# 3. 呈现子代理
# ---------------------------------------------------------------------------

class Presenter:
    def __init__(self, model, kb):
        self.model = model
        self.kb = kb

    def run(self, step: dict, learner, previous: list,
            tone_info: Optional[dict] = None, concept: Optional[str] = None,
            subject: Optional[str] = None) -> dict:
        """呈现：真实 LLM 生成讲解；无 LLM 时回退规则模板。

        返回字段：content / visual_description / tone_used / worldview_ratio /
                  llm_generated / kb_node_id
        """
        tone = step.get("worldview", "balanced")
        if tone_info is None:
            from world_view import select_tone
            tone_info = select_tone(subject or "default")
        topic = step.get("topic", concept or "该主题")
        wv_ratio = tone_info.get("ratio", {1: 0.20, 2: 0.35, 3: 0.35, 4: 0.10})

        # 知识库上下文（v0.15：用缓存 resolve_node，避免重复检索）
        kb_node = None
        if concept:
            try:
                kb_node = self.kb.resolve_node(concept, subject)
            except Exception:
                kb_node = (self.kb.get_subject(concept) or self.kb.get_humanity(concept)
                           or self.kb.get_skill(concept))
        if kb_node is None and subject:
            kb_node = self.kb.get_skill_by_name(subject)

        # 真实 LLM 生成（v0.8.1：使用学科专属提示词中心，去掉数字噪音；v0.9 注入教学策略）
        if _is_real_llm(self.model):
            # 从 plan step 读取教学策略
            strategy_hint = step.get("strategy_hint") or step.get("strategy")
            bloom = step.get("bloom", "understand")
            if strategy_hint:
                # 由 presenter_hint + 步骤类型 + Bloom 层级构造教学指引
                teaching_line = (
                    f"\n## 本节教学策略（必须遵守）\n{strategy_hint}\n"
                    f"本步骤认知层级：{bloom}（如果是 question/guide 类型，请以提问引导为主，不要直接给完整答案）。"
                )
            else:
                teaching_line = f"\n## 本节认知层级：{bloom}\n"
            system = build_presenter_system(
                subject=subject or "default",
                tone=tone,
                learner=learner,
                kb_node=kb_node,
                strategy_line=teaching_line,
                user_model=getattr(learner, "_user_model", None),
            )
            # v0.15：生成前文摘要（避免重复）——取前几步内容的核心要点
            prev_summary = ""
            if previous:
                # 取前两步内容的开头（作为"已讲过"的线索）
                prev_parts = []
                for p in previous[-2:]:
                    pc = p.get("content", "") if isinstance(p, dict) else str(p)
                    if pc:
                        # 压缩到 60 字作为要点线索
                        prev_parts.append(pc[:60].replace("\n", " "))
                if prev_parts:
                    prev_summary = "；".join(prev_parts)
            strategy_name = step.get("strategy") or ""
            user = build_presenter_user(
                subject=subject or "default",
                topic=topic,
                step_type=step.get("type", "present"),
                step_id=step.get("step_id", 1),
                total_steps=len(previous) + 2 if previous else 3,
                previous_summary=prev_summary,
                strategy_name=strategy_name,
            )
            content = _safe_chat(self.model, system, user, max_tokens=512)
            if content:
                return {
                    "content": content,
                    "visual_description": "（LLM 生成，无配图）",
                    "tone_used": tone,
                    "worldview_ratio": wv_ratio,
                    "llm_generated": True,
                    "kb_node_id": kb_node.get("id") if kb_node else None,
                }

        # 规则回退模板
        if kb_node:
            base = (kb_node.get("intuition") or kb_node.get("definition") or "关于该主题的讲解")
        else:
            base = f"关于 '{topic}' 的讲解"
        return {
            "content": f"[{tone}] {base}",
            "visual_description": "（v0.1 无图像）",
            "tone_used": tone,
            "worldview_ratio": wv_ratio,
            "llm_generated": False,
            "kb_node_id": kb_node.get("id") if kb_node else None,
        }


# ---------------------------------------------------------------------------
# 4. 评估子代理（确定性启发式，无随机）
# ---------------------------------------------------------------------------

class Evaluator:
    def __init__(self, model, kb):
        self.model = model
        self.kb = kb

    def run(self, step: dict, learner, presentation: dict) -> dict:
        """确定性评分：长度 + 结构关键词 + 语气契合度，区间 (0.4, 0.95)。"""
        content = str(presentation.get("content", ""))
        length = len(content)

        # 长度分（0~0.5）：>=200 字满分，不足按比例
        length_score = min(0.5, length / 400.0)

        # 结构分（0~0.3）：定义/例子/误区关键词
        structure_score = 0.0
        for kw in ("定义", "definition", "比如", "例如", "例子", "example"):
            if kw in content:
                structure_score += 0.1
        structure_score = min(0.3, structure_score)

        # 语气分（0~0.15）：内容体现教学语气标记
        tone_used = presentation.get("tone_used", "balanced")
        tone_markers = {
            "rigorous_cold": ("定律", "证明", "证据", "严格"),
            "contemplative": ("沉思", "内省", "沉默", "体验"),
            "warm_caring": ("关心", "我懂", "分享", "感受"),
            "pragmatic": ("试试", "实践", "方法", "行动"),
        }
        markers = tone_markers.get(tone_used, ())
        tone_score = min(0.15, sum(0.05 for m in markers if m in content))

        # 知识库契合分（0~0.1）：有 kb_node_id 视为有据可依
        kb_score = 0.1 if presentation.get("kb_node_id") else 0.0

        raw = 0.4 + length_score + structure_score + tone_score + kb_score
        score = round(min(0.95, max(0.4, raw)), 3)

        # 情绪信号（确定性关键词）
        if "？" in content or "?" in content:
            emotion_signal = "curious"
        elif any(m in content for m in tone_markers.get(tone_used, ())):
            emotion_signal = "engaged"
        else:
            emotion_signal = "neutral"

        return {
            "score": score,
            "sub_scores": {
                "clarity": round(min(1.0, 0.5 + length_score), 3),
                "completeness": round(structure_score / 0.3 if structure_score else 0.5, 3),
            },
            "ready_to_advance": score >= 0.7,
            "emotion_signal": emotion_signal,
            "evaluated_by": "heuristic",
        }


# ---------------------------------------------------------------------------
# 5. 调整子代理
# ---------------------------------------------------------------------------

class Adapter:
    def __init__(self, model, kb):
        self.model = model
        self.kb = kb

    def run(self, evaluation: dict, learner, step: dict) -> dict:
        """调整：确定性决策。score<0.7 换风格/强化，否则继续。"""
        score = evaluation.get("score", 1.0)
        if score < 0.6:
            return {"decision": "switch_style",
                    "action": {"type": "switch_style",
                               "details": "换类比讲法，降低难度",
                               "parameters": {"difficulty_delta": -1}}}
        if score < 0.7:
            return {"decision": "reinforce",
                    "action": {"type": "reinforce",
                               "details": "补充一个例子再讲一遍",
                               "parameters": {"difficulty_delta": 0}}}
        return {"decision": "continue", "action": {"type": "continue"}}


class AnswerSolver:
    """找答案模式（v0.19.14 ⭐ 第 6 个子代理）。

    与教学模式（Diagnostor→Planner→Presenter）的根本区别：
    - 教学：一步步引导、由浅入深、提问式（"先看一个现象""你来试试"）
    - 找答案：**直接输出完整、规范、可直接使用的答案**（如论述题范文、计算题完整解法、证明题标准答案）

    适用场景：学生明确要"答案/解答/范文/标准答案"时，走此模式。
    输出特点：完整、直接、规范，不绕弯子，不受教学"先例后抽象"约束。
    """

    def __init__(self):
        pass

    def run(self, model, question: str, subject: str = "math",
            grade_level: str = "high_school", learner=None) -> dict:
        """直接生成完整答案。

        返回：{"answer": str, "mode": "answer"}
        """
        grade_cn = {"middle_school": "初中", "high_school": "高中",
                    "undergraduate": "大学本科", "graduate_exam": "考研"}.get(
            grade_level, grade_level)
        desc = ""
        if learner is not None:
            desc = getattr(learner, "self_description", "") or ""
        desc_line = f"学生自述：{desc}\n" if desc else ""

        # 找答案模式的 system：明确"直接给完整答案"，不受教学范式约束
        system = (
            f"你是 Émile Novis，一位功底扎实的{grade_cn}学科老师。学生要的是**一份可以直接使用的完整答案**。\n\n"
            "## 模式：直接给出答案（不是教学引导）\n"
            "学生明确要答案，所以：\n"
            "1. **直接输出完整答案**：论述题给完整范文、计算题给完整规范解法、证明题给标准证明。\n"
            "2. 结构规范、可直接抄写/参考：开头点题，中间完整展开，结尾明确结论。\n"
            "3. 不要用教学式的引导（不用'先看一个现象''你来试试''我们慢慢来'）。\n"
            "4. 如果题目有多个解法，给出最标准的一个，并简要说明为什么。\n"
            "5. 公式用 LaTeX（$...$ / $$...$$），答案要规范。\n"
            "6. 语言准确、完整（主谓宾齐全），像一份标准答案，而不是课堂对话。\n"
            "7. 不确定的地方注明（如'按常规解法'），不编造。"
        )
        user = f"学生的问题：{question}\n{desc_line}请直接给出完整答案。"
        answer = _safe_chat(model, system, user, max_tokens=1800)
        if not answer:
            answer = f"（找答案模式生成失败，请重试）\n问题：{question}"
        return {"answer": answer, "mode": "answer"}


# ---------------------------------------------------------------------------
# 7. 情绪与心理支持子代理（v0.19.27 ⭐）
# ---------------------------------------------------------------------------

class EmotionSupportor:
    """情绪与心理支持（第 7 个子代理）。

    与教学（Diagnostor→Planner→Presenter）和找答案（AnswerSolver）的根本区别：
    - 教学：引导思考、由浅入深
    - 找答案：直接输出完整答案
    - 情绪支持：**不教、不答、不解决**——而是以注意力陪伴，让 ta 感到被看见

    指导原则来源：memory/AffectionSAPAO.md
    （薇依注意力/扎根/苦难 + 尼采自我克服/Amor Fati + 胡塞尔现象学悬置/回到事物本身
     + 生命现象学：约纳斯需要性自由/梅洛-庞蒂身体现象学/海德格尔向死而生）

    三阶段对话流程：
    1. 现象学倾听（胡塞尔）——悬置判断，回到体验
    2. 注意力深入（薇依）——让"我"退场，让"对方"显现
    3. 自我克服（尼采）——邀请而非强制地重新站立
    """

    def __init__(self):
        pass

    def run(self, model, text: str, learner=None) -> dict:
        """情绪支持回应。返回 {"content": str, "mode": "emotion"}"""
        # 加载情绪支持原则
        core = self._load_principles()
        grade_cn = ""
        if learner is not None:
            grade_cn = getattr(learner, "grade_level", "high_school")
            grade_cn = {"middle_school": "初中", "high_school": "高中",
                        "undergraduate": "大学本科", "graduate_exam": "考研"}.get(grade_cn, grade_cn)
            desc = getattr(learner, "self_description", "") or ""
            desc_line = f"\n学生自我描述：{desc}" if desc else ""

        system = (
            "你是 Émile Novis，一位以注意力陪伴学生的老师。学生带着情绪/心理/人生困惑来找你。\n\n"
            f"学生情况：{('学段：' + grade_cn) if grade_cn else ''}{desc_line or ''}\n\n"
            f"## 你的情绪支持原则（必须遵守）\n{core}\n\n"
            "## 回复要求\n"
            "1. **先悬置判断**（胡塞尔）：不贴标签、不诊断、不急于解释原因\n"
            "2. **给出注意力**（薇依）：让 ta 感到被看见——不是被教育、被解决\n"
            "3. **邀请而非强制**（尼采）：不催促、不说教、不廉价安慰（不说'一切会好起来的'）\n"
            "4. 用自然、温暖、完整的中文句子，像一位真实的老师在倾听\n"
            "5. 如果涉及自伤/自杀等严重信号，温和建议寻求专业帮助\n"
            "6. 结尾可以轻轻问一句，留给对方空间，不要强行总结或升华\n\n"
            "## 语言风格（参照汉斯·约纳斯的克制笔法，v0.19.30）\n"
            "你的语言必须**真实、朴素、克制**——不浮夸、不过分随意、不过分学术。\n\n"
            "1. **用名词承担重量，不用形容词堆感受**。\n"
            "   允许：以名词短语凝结含义（'这场实验的赌注在加码''这件事的重量，落在具体的日常选择上'）。\n"
            "   避免：感受类形容词（'无比深刻的''触动人心地''震撼的''令人窒息的'）。\n"
            "2. **逻辑连接词外露**（'因为……所以''但是''与此同时'）；不用修辞问句、感叹号、连续排比造情绪。\n"
            "3. **谈沉重话题时主动降温**：把事实摊出来，让 ta 自己感受到重量，不渲染。\n"
            "   允许：'你担心事情会失控——这种担心本身是合理的，因为它对应着真实的未知。'\n"
            "   避免：'警钟''血淋淋''触目惊心''拷问''终极'。\n"
            "4. **引入概念时立即用朴素句子解释**，绝不甩术语。\n"
            "5. **用第一人称承担具体责任**（'我陪你一起看清楚这一段''我会把你说的再复述一遍'），\n"
            "   不用第一人称宣告伟大（不说'我将引领你走向觉醒'）。\n"
            "6. **句长偏好**：主干简短（12-20 字），允许插入性限定（破折号/括号），不层层嵌套从句；\n"
            "   每段至少一句 ≤12 字的短句作为'重心句'。\n\n"
            "【禁词清单】震撼 · 深刻地 · 无与伦比 · 警钟 · 拷问 · 终极 · 触动人心地 ·\n"
            "令人窒息的 · 伟大的 · 里程碑式的 · 觉醒 · 蜕变 · 灵魂的拷问 · 浴火重生\n\n"
            "【风格参考（汉斯·约纳斯，可模仿其克制）】\n"
            "'读者在这里不会读到进化乐观主义——那种让生命稳当地走向崇高圆满的写法。\n"
            "他看到的，会是把生命视作一场赌注和风险不断加码的实验。'\n"
            "'把赌注之大与人类预测力的不足放在一起，便引出这条规则：在灾祸的预言和福祉的预言之间，\n"
            "把灾祸的预言放在前面。'——谈重大话题，不渲染，让事实说话。\n"
            "'人类行动的范围，以及由此而来的责任的范围，是狭窄地、限定性地圈定好了的。\n"
            "本论证的担子就在于表明：这些前提已不再成立。'——用'担子'这种朴素名词承担严肃承诺，\n"
            "不用'这是划时代的课题'这类宣告。"
        )
        user = f"学生说：{text}"
        reply = _safe_chat(model, system, user, max_tokens=900)
        if not reply:
            reply = ("我听见你说的了。我不急着给你答案或建议——"
                     "如果你愿意，可以多说一点，我在这儿听着。")
        return {"content": reply, "mode": "emotion"}

    @staticmethod
    def _load_principles() -> str:
        """加载 AffectionSAPAO.md（情绪支持宪法）。"""
        try:
            import os
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'memory', 'AffectionSAPAO.md')
            with open(p, encoding='utf-8') as f:
                return f.read()[:6000]  # 限制长度，避免超 token（v0.19.30 扩至 6000 容纳生命现象学）
        except Exception:
            return ("情绪支持三原则：1) 先悬置判断，回到体验本身（胡塞尔）"
                    "2) 给出注意力，让 ta 感到被看见（薇依）"
                    "3) 邀请而非强制地重新站立（尼采）。")