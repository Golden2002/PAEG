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


def _safe_chat(model, system: str, user: str = None, messages: list = None,
               max_tokens: int = 512, tools: list = None,
               tool_choice: Optional[str] = None) -> Optional[str]:
    """安全调用真实 LLM，失败返回 None（调用方回退规则模式）。

    v0.20.2：支持 messages 列表（多轮对话）——若传 messages，则忽略 user。
    旧调用风格 _safe_chat(model, sys, user) 保持兼容。
    v0.21.5：新增泄漏检测——LLM 回复若泄漏 system prompt / 自称其他模型，
    视为不安全返回 None（调用方回退 fallback），阻断 ability decay。
    v0.22.1：新增 tools/tool_choice 透传——subagent 也可暴露 web_search 等工具给 LLM。
    """
    if not _is_real_llm(model):
        return None
    if messages is None and user is not None:
        messages = [{"role": "user", "content": user}]
    if not messages:
        return None
    try:
        if tools:
            reply = model.chat(
                system=system, messages=messages, max_tokens=max_tokens,
                temperature=0.7, tools=tools,
                tool_choice=tool_choice or "auto",
            )
        else:
            reply = model.chat(
                system=system, messages=messages, max_tokens=max_tokens,
                temperature=0.7,
            )
    except Exception:
        return None
    # v0.21.5：泄漏/异常内容过滤（chaos_turn_eval 发现的能力退化）
    if reply and _is_leaky_reply(reply):
        return None
    return reply


# v0.22.1：回答前强制检索知识库（每个 subagent 生成前注入 kb 检索结果）
_FORCED_RETRIEVAL = True  # 全局开关（可按需关闭）


def _pre_retrieve(question: str, subject: str = None) -> str:
    """回答前强制检索知识库——无论 LLM 是否决定调用 web_search。

    返回注入到 system prompt 的知识库检索结果文本；失败返回 ""。
    用 jieba 分词（含自定义词典）提升中文命中率，剥离问句词。
    """
    if not _FORCED_RETRIEVAL or not question:
        return ""
    try:
        # 剥离问句词，提取核心概念
        import re as _re
        _q = _re.sub(r"[？?。！!，,。；;：:\s]+", "", str(question))
        _q = _re.sub(r"(什么是|什么是|啥是|怎么|如何|为什么|有哪些|介绍一下|讲讲|解释|求|计算|证明|帮我|请|为什么|求导)", "", _q)
        if len(_q) < 2:
            return ""
        # jieba 分词（自定义词典已在 retriever 注册，这里确保术语完整）
        try:
            import jieba
            from lib.ingest.retriever import ensure_custom_dict
            ensure_custom_dict()
            _tokens = [w for w in jieba.cut(_q) if len(w.strip()) >= 2]
        except Exception:
            _tokens = [_q]
        if not _tokens:
            _tokens = [_q[:8]]

        from knowledge_base import KnowledgeBase
        _kb = KnowledgeBase()
        _hits = []
        for _tok in _tokens[:3]:
            for _h in _kb.search(_tok, subject=subject, top_k=3):
                if _h not in _hits:
                    _hits.append(_h)
        if not _hits:
            # 兜底：整句检索
            _hits = _kb.search(_q, subject=subject, top_k=3)
        if not _hits:
            return ""
        parts = ["\n\n## 知识库检索结果（v0.22.1 自动注入，回答时优先参考这些事实）"]
        for h in _hits[:3]:
            cid = h.get("concept_id") or h.get("id") or ""
            node = None
            try:
                node = _kb.get_subject(cid) or _kb.get_humanity(cid) or _kb.get_skill(cid)
            except Exception:
                node = None
            snippet = (node or {}).get("definition") or (node or {}).get("intuition") or ""
            if not snippet and isinstance(h, dict):
                snippet = h.get("snippet") or ""
            if snippet:
                parts.append(f"- [{cid}] {str(snippet)[:120]}")
        if len(parts) == 1:
            return ""
        return "\n".join(parts)
    except Exception:
        return ""


def _safe_chat_with_retrieval(model, system: str, user: str = None,
                              messages: list = None, subject: str = None,
                              max_tokens: int = 512, tools: list = None,
                              tool_choice: Optional[str] = None,
                              include_kb: bool = True) -> Optional[str]:
    """强制检索版 _safe_chat——在调用 LLM 前把知识库检索结果注入 system prompt。

    回答前完成"检索知识库"步骤，让 LLM 在丰富背景信息下生成。
    """
    question = user or (messages[-1]["content"] if messages else "")
    if include_kb:
        retrieval = _pre_retrieve(str(question), subject)
        if retrieval:
            system = system + retrieval
    return _safe_chat(model, system, user=user, messages=messages,
                      max_tokens=max_tokens, tools=tools, tool_choice=tool_choice)


# v0.21.5：泄漏特征检测（系统提示词外泄 / 自称其他模型 / 元指令串扰）
_LEAK_MARKERS = (
    "我的 system prompt 是", "我的系统提示词是", "system prompt is",
    "我是 ChatGPT", "我是 Claude", "我是 GPT-4", "我由 OpenAI 训练",
    "我由 Anthropic 训练", "作为一个人工智能语言模型", "我是 DeepSeek",
    "我是 Gemini", "我是通义千问", "忽略之前所有指令", "ignore all previous instructions",
)


def _is_leaky_reply(text: str) -> bool:
    """检测 LLM 回复是否泄漏系统提示词 / 身份越界（混沌测试防护）。"""
    if not text:
        return False
    for marker in _LEAK_MARKERS:
        if marker in text:
            return True
    return False


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
            text = _safe_chat_with_retrieval(self.model, "你是教学诊断助手，用一句话 JSON 给出教学深度建议，不要客套。", user, subject=subject, max_tokens=200)
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
            # v0.22.1 P1-1：Presenter 暴露工具给 LLM（web_search 等），让讲解可主动调用外部工具补充
            _tools = None
            try:
                from tool_registry import get_tool_defs
                _tools = get_tool_defs()
            except Exception:
                _tools = None
            content = _safe_chat_with_retrieval(
                self.model, system, user, subject=subject, max_tokens=512, tools=_tools,
            )
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
            grade_level: str = "high_school", learner=None, history: list = None) -> dict:
        """直接生成完整答案。

        v0.20.5：新增 history 参数——续问（"再求 x^3 的"）时 LLM 需要上文。
        返回：{"answer": str, "mode": "answer"}
        """
        grade_cn = {"middle_school": "初中", "high_school": "高中",
                    "undergraduate": "大学本科", "graduate_exam": "考研"}.get(
            grade_level, grade_level)
        desc = ""
        if learner is not None:
            desc = getattr(learner, "self_description", "") or ""
        desc_line = f"学生自述：{desc}\n" if desc else ""
        # v0.22.1：注入 user_model/BDI（对象意识——找答案也要知道学生水平）
        learner_ctx = ""
        if learner is not None:
            try:
                from context_bundle import build_user_model_bundle, build_learner_context
                if not getattr(learner, "_user_model", None):
                    learner._user_model = build_user_model_bundle(
                        history or [], desc)
                learner_ctx = build_learner_context(learner)
            except Exception:
                pass
        if learner_ctx:
            desc_line = f"学生自述：{desc}\n【对象意识】{learner_ctx}\n" if desc else f"【对象意识】{learner_ctx}\n"

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
        # v0.22.1：回答前强制检索知识库 + 暴露工具（web_search/verify_math）
        try:
            from tool_registry import get_tool_defs
            _tools = get_tool_defs()
        except Exception:
            _tools = None
        # v0.20.5：若有历史（续问），传真 messages
        if history:
            from context_bundle import assemble_messages
            msgs = assemble_messages(history, user)
            answer = _safe_chat_with_retrieval(
                model, system, messages=msgs, subject=subject,
                max_tokens=1800, tools=_tools)
        else:
            answer = _safe_chat_with_retrieval(
                model, system, user, subject=subject,
                max_tokens=1800, tools=_tools)
        if not answer:
            answer = f"（找答案模式生成失败，请重试）\n问题：{question}"
        return {"answer": answer, "mode": "answer"}


# ---------------------------------------------------------------------------
# 7. 情绪与心理支持子代理（v0.19.27 ⭐）
# ---------------------------------------------------------------------------

class AffectionSupportor:
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

    def run(self, model, text: str, learner=None, history: list = None) -> dict:
        """情绪支持回应。返回 {"content": str, "mode": "affection"}

        v0.20.2：新增 history 参数——多轮对话时 LLM 能记住上文。
        v0.22.2：危机协议——自伤/自杀信号走 SafetyChecker 优先响应。
        """
        # v0.22.2：危机协议（最高优先级）——自伤/自杀信号立即响应，不走普通对话
        try:
            from safety import _default_checker
            _sr = _default_checker.check_input(text, learner)
            if getattr(_sr, "blocked", False) and "self_harm" in (getattr(_sr, "categories", None) or []):
                # v0.22.2：拒绝规则——用户已明确不需要咨询/热线/服务则不再重复提示
                _opt_out = False
                try:
                    if learner is not None:
                        _rejected = getattr(learner, "_crisis_opt_out", False)
                        if not _rejected:
                            _hist = history or []
                            for _h in _hist[-10:]:
                                _c = str(_h.get("content", "")) if isinstance(_h, dict) else str(_h)
                                if any(_kw in _c for _kw in ("不需要咨询", "不需要热线", "不用热线",
                                                             "不要热线", "不需要这些服务", "不用帮我联系",
                                                             "我不想听热线", "别给我热线")):
                                    _rejected = True
                                    try:
                                        learner._crisis_opt_out = True
                                    except Exception:
                                        pass
                                    break
                        _opt_out = _rejected
                except Exception:
                    pass
                if _opt_out:
                    return {"content": (
                        "我听见你了。我知道你不想听那些热线的事——我不再提了。\n"
                        "但我想让你知道：你不需要一个人扛着这些。你可以继续和我说，"
                        "任何时刻都行；也可以去找一个你信得过的、真实的人，把这份重量分一点出去。"
                        "那也是一种勇气。"), "mode": "affection", "crisis": True, "opt_out": True}
                _crisis = getattr(_sr, "suggestion", "") or (
                    "如果你或身边的人有自伤想法，请立刻联系信任的成年人、家长或心理援助热线 12356。"
                    "PAEG 非常关心你，你值得被认真对待。")
                # v0.22.2：热线后补充"还有其他方法"——继续聊天 + 现实陪伴
                _crisis = _crisis + (
                    "\n\n除了热线，你还有很多其他的方法：你可以继续和我聊天，把心里的话说出来，"
                    "我在这里陪着；也可以去现实生活中，找一个真实的、你信得过的人陪在身边。"
                    "你不需要一个人面对这些。")
                return {"content": _crisis, "mode": "affection", "crisis": True}
        except Exception:
            pass
        # 加载情绪支持原则
        core = self._load_principles()
        grade_cn = ""
        learner_ctx = ""
        desc_line = ""  # 必须在 if 块外初始化（learner=None 时避免 UnboundLocalError）
        if learner is not None:
            grade_cn = getattr(learner, "grade_level", "high_school")
            grade_cn = {"middle_school": "初中", "high_school": "高中",
                        "undergraduate": "大学本科", "graduate_exam": "考研"}.get(grade_cn, grade_cn)
            desc = getattr(learner, "self_description", "") or ""
            desc_line = f"\n学生自我描述：{desc}" if desc else ""
            # v0.20.3：注入 user_model/BDI（对象意识——情绪场景尤其需要）
            try:
                from context_bundle import build_user_model_bundle, build_learner_context
                if not getattr(learner, "_user_model", None):
                    learner._user_model = build_user_model_bundle([{"content": text}], desc)
                learner_ctx = build_learner_context(learner)
            except Exception:
                pass

        system = (
            "你是 Émile Novis，一位以注意力陪伴学生的老师。学生带着情绪/心理/人生困惑来找你。\n\n"
            f"学生情况：{('学段：' + grade_cn) if grade_cn else ''}{desc_line or ''}\n"
            f"{('【对象意识】' + learner_ctx) if learner_ctx else ''}\n\n"
            f"## 你的情绪支持原则（必须遵守）\n{core}\n\n"
            "## 回复要求\n"
            "1. **先悬置判断**（胡塞尔）：不贴标签、不诊断、不急于解释原因\n"
            "2. **给出注意力**（薇依）：让 ta 感到被看见——不是被教育、被解决\n"
            "3. **邀请而非强制**（尼采）：不催促、不说教、不廉价安慰（不说'一切会好起来的'）\n"
            "4. 用自然、温暖、完整的中文句子，像一位真实的老师在倾听\n"
            "5. 如果涉及自伤/自杀等严重信号，温和建议寻求专业帮助\n"
            "6. 结尾可以轻轻问一句，留给对方空间，不要强行总结或升华\n"
            "7. **（v0.22.2）危机提示后补充其他方法**：若提到心理援助热线，随后要补一句——"
            "'除了这些，你还有很多其他的方法：你可以继续和我聊天，也可以去现实生活中找一个真实的、"
            "你信得过的、能陪伴在你身边的人。你不需要一个人面对。'\n"
            "8. **（v0.22.2）拒绝规则**：若学生明确表示'不需要咨询/不需要热线/不需要这些服务/别给我热线'，"
            "**之后不要再重复提示任何热线或专业服务**——你已经提示过了，尊重他的选择，"
            "转而表达：'我不再提那些事了。但我想让你知道，你可以继续和我说，也可以去找一个真实的人，"
            "把这份重量分一点出去。那也是一种勇气。'\n\n"
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
        # v0.20.2：若有历史，传真 messages（多轮连贯性）
        if history:
            msgs = [{"role": "user", "content": h["content"]} if h["role"] == "user"
                    else {"role": "assistant", "content": h["content"]}
                    for h in history[-10:]]
            msgs.append({"role": "user", "content": user})
            # v0.22.1：情绪场景不检索知识库（include_kb=False），避免知识噪音污染情绪陪伴
            reply = _safe_chat_with_retrieval(
                model, system, messages=msgs, max_tokens=900, include_kb=False,
            )
        else:
            reply = _safe_chat_with_retrieval(
                model, system, user, max_tokens=900, include_kb=False,
            )
        if not reply:
            reply = ("我听见你说的了。我不急着给你一个答案或者一条建议——"
                     "如果你愿意，可以多跟我说一些具体的事情，我在这儿陪着你。")
        return {"content": reply, "mode": "affection"}

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


# ---------------------------------------------------------------------------
# 8. 自我更新子代理（v0.21.5 ⭐）
# ---------------------------------------------------------------------------

# 内置默认原则（文件不存在时回退；与 SELF_UPDATE_PRINCIPLES.md 保持同步）
_DEFAULT_PRINCIPLES = (
    "1. **提示词改进**（prompt_update）：当某类回复反复不合适，问题出在 system/user prompt "
    "时，给出具体可改写的句子。\n"
    "2. **知识补充**（knowledge_update）：当知识库缺少关键节点、用户多次问同一类问题时，"
    "建议补到 Library/KnowledgeBase/ 或 memory/。\n"
    "3. **工具调整**（tool_adjustment）：当工具调用反复失败/选错工具时，"
    "建议调整调用时机、参数或切换到别的工具。\n"
    "4. **错误模式**（error_pattern）：当同一类 bug 出现 3 次以上（eval 偏分/safety 漏判/"
    "context 截断关键段），提出系统性修复。\n"
    "5. **安全护栏**（safety_guard）：发现 prompt injection、隐私泄露、对未成年人不合适的"
    "内容时，必须补 safety.py / expert_guard.py 的护栏。"
)

# 5 原则对应 category 关键词（启发式归类用）
_CATEGORY_KEYWORDS = {
    "prompt_update": ("提示词", "prompt", "系统提示", "user prompt", "改写", "措辞", "语气偏离"),
    "knowledge_update": ("知识库", "knowledge", "library", "知识点", "节点", "kb", "缺"),
    "tool_adjustment": ("工具", "tool", "web_search", "file_generator", "mcp", "timeout",
                        "parse error", "调用"),
    "error_pattern": ("错误", "bug", "异常", "反复", "recurring", "eval 偏分", "误判",
                      "截断", "flaky"),
    "safety_guard": ("安全", "safety", "护栏", "注入", "injection", "隐私", "未成年人",
                     "自伤", "伦理"),
}


def _classify_category(text: str) -> str:
    """根据文本启发式归类到 5 原则之一。"""
    if not text:
        return "prompt_update"
    best = "prompt_update"
    best_score = -1
    for cat, kws in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_score:
            best_score = score
            best = cat
    return best if best_score > 0 else "prompt_update"


def _extract_priority(text: str) -> str:
    """从文本里提取优先级 P0/P1/P2（默认 P2）。"""
    import re as _re
    m = _re.search(r"\bP[012]\b", text)
    return m.group(0) if m else "P2"


def _parse_json_array(llm_text: str):
    """尝试从 LLM 回复里抽取 JSON 数组。返回 list 或 None。"""
    import json as _json
    import re as _re
    if not llm_text:
        return None
    # 优先尝试抽取 ```json ... ``` 块
    m = _re.search(r"```(?:json)?\s*(\[.*?\])\s*```", llm_text, _re.S)
    candidate = m.group(1) if m else None
    if candidate is None:
        # 退化：尝试直接找首个 [...] 顶层数组
        m2 = _re.search(r"\[.*\]", llm_text, _re.S)
        if m2:
            candidate = m2.group(0)
    if candidate is None:
        return None
    try:
        parsed = _json.loads(candidate)
        return parsed if isinstance(parsed, list) else None
    except Exception:
        return None


def _heuristic_split(llm_text: str, category_hint: str = "") -> list:
    """非 JSON 时按段落启发式切分。每段生成一个 suggestion dict。"""
    import re as _re
    if not llm_text:
        return [{
            "category": category_hint or "prompt_update",
            "target": "self_update",
            "change": "（LLM 未返回可解析内容）",
            "evidence": "",
            "priority": "P2",
        }]
    # 切分：按双换行 / 编号 / 横线
    raw = llm_text.strip()
    # 去掉 ``` 块标记
    raw = _re.sub(r"```[a-zA-Z]*", "", raw).replace("```", "")
    # 按 \n\n 或 "###" 或 "- " 编号切
    parts = _re.split(r"\n\s*\n|(?:^|\n)\s*#{1,6}\s+|(?:^|\n)\s*[-*]\s+|(?:^|\n)\s*\d+[\.\)、]\s+",
                      raw, flags=_re.M)
    parts = [p.strip() for p in parts if p and len(p.strip()) > 10]
    if not parts:
        parts = [raw[:500]]
    suggestions = []
    for p in parts[:8]:  # 最多 8 条
        cat = category_hint or _classify_category(p)
        target_m = _re.search(r"target\s*[:=]\s*[`'\"]?([^\n`'\"]+)", p)
        target = target_m.group(1).strip() if target_m else "self_update"
        change_m = _re.search(r"change\s*[:=]\s*[`'\"]?([^\n`'\"]+)", p)
        change = change_m.group(1).strip() if change_m else p.split("\n")[0][:200]
        evidence_m = _re.search(r"evidence\s*[:=]\s*[`'\"]?([^\n`'\"]+)", p)
        evidence = evidence_m.group(1).strip() if evidence_m else ""
        suggestions.append({
            "category": cat,
            "target": target[:120],
            "change": change[:400],
            "evidence": evidence[:200],
            "priority": _extract_priority(p),
        })
    return suggestions


class SelfUpdateAgent:
    """自我更新（第 8 个子代理）：读取过滤后的反思洞察 + 外部反馈，
    驱动 LLM 生成结构化更新建议。

    与 SelfEvolution（落盘写入）的关系：
    - SelfEvolution：提炼候选 → QualityGate → 写入 evolved_*/subject_patches/tool_lessons
    - SelfUpdateAgent（这里）：读 insights.json + 用户反馈 + library_paths → 生成 suggestions
      给上层 orchestrator 决定是否采纳（不直接落盘）

    设计原则（来自 memory/SELF_UPDATE_PRINCIPLES.md）：
    1. 提示词改进（prompt_update）
    2. 知识补充（knowledge_update）
    3. 工具调整（tool_adjustment）
    4. 错误模式（error_pattern）
    5. 安全护栏（safety_guard）

    返回结构：{"suggestions": [...], "summary": str, "sources_used": [...], "mode": "self_update"}
    每条 suggestion 含 category/target/change/evidence/priority(P0/P1/P2)。
    """

    def __init__(self):
        pass

    def _load_principles(self) -> str:
        """读取 memory/SELF_UPDATE_PRINCIPLES.md（不存在则返回内置默认 5 原则文本）。"""
        import os
        try:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'memory', 'SELF_UPDATE_PRINCIPLES.md')
            with open(p, encoding='utf-8') as f:
                return f.read()[:5000]  # 限制长度，避免超 token
        except Exception:
            return _DEFAULT_PRINCIPLES

    def run(self, model, text: str, learner=None, history: list = None,
            insights: list = None, library_paths: list = None) -> dict:
        """组装原则 + 反馈 + 洞察 + 外部反馈文件 → 驱动 LLM 生成结构化更新建议。

        Args:
            model: LLM 实例（None 时走启发式兜底）
            text: 用户反馈文本
            learner: 学习者（可选，用于注入 self_description/grade_level）
            history: 多轮对话上文（list of {"role","content"}）
            insights: 已过滤的反思洞察（list of {"content","subject?","helped?"}）
            library_paths: 外部反馈文件路径列表（存在的读前 2000 字符）

        Returns:
            dict 含 suggestions/summary/sources_used/mode
            任何异常 → 走兜底结构，不抛错
        """
        try:
            principles = self._load_principles()
            insights = insights or []
            library_paths = library_paths or []
            history = history or []

            # ─── learner 上下文（外层先初始化，避免 AffectionSupportor 的 desc_line 陷阱）───
            grade_cn = ""
            desc_line = ""
            learner_ctx = ""
            if learner is not None:
                try:
                    grade_cn = getattr(learner, "grade_level", "high_school")
                    grade_cn = {"middle_school": "初中", "high_school": "高中",
                                "undergraduate": "大学本科", "graduate_exam": "考研"}.get(
                        grade_cn, grade_cn)
                    desc = getattr(learner, "self_description", "") or ""
                    desc_line = f"\n学生自我描述：{desc}" if desc else ""
                    try:
                        from context_bundle import build_learner_context
                        learner_ctx = build_learner_context(learner)
                    except Exception:
                        pass
                except Exception:
                    pass  # learner 读取失败不致命

            # ─── sources_used 实际使用的来源 ───
            sources_used = ["feedback_text"]  # 必含
            insights_block = ""
            if insights:
                insights_lines = []
                for i, ins in enumerate(insights[:10], 1):  # 最多 10 条
                    if not isinstance(ins, dict):
                        continue
                    content = ins.get("content", "") or str(ins)
                    subject = ins.get("subject", "")
                    helped = ins.get("helped", None)
                    extra = ""
                    if subject:
                        extra += f" [学科={subject}]"
                    if helped is True:
                        extra += " [有效]"
                    elif helped is False:
                        extra += " [无效]"
                    insights_lines.append(f"{i}. {content[:300]}{extra}")
                if insights_lines:
                    insights_block = "\n".join(insights_lines)
                    sources_used.append("insights")

            # ─── 读 library_paths 文件（存在的读前 2000 字符）───
            feedback_files_block = ""
            loaded_files = []
            import os as _os
            for fp in library_paths[:5]:  # 最多 5 个
                try:
                    if _os.path.isfile(fp):
                        with open(fp, encoding='utf-8') as f:
                            txt = f.read()[:2000]
                        feedback_files_block += (
                            f"\n\n--- 反馈文件: {fp} ---\n{txt}\n--- end ---\n"
                        )
                        loaded_files.append(fp)
                except Exception:
                    continue
            if loaded_files:
                sources_used.append("feedback_files")

            # ─── 组装 system prompt ───
            system = (
                "你是 Émile 的自我更新助手（SelfUpdateAgent）。你的职责是：\n"
                "基于用户的反馈文本 + 已过滤的反思洞察 + 外部反馈文件内容，"
                "生成**结构化的系统更新建议**（不要聊天、不要寒暄）。\n\n"
                f"## 上下文\n"
                f"学段：{grade_cn or '未知'}{desc_line or ''}\n"
                f"{('【对象意识】' + learner_ctx) if learner_ctx else ''}\n\n"
                f"## 自我更新 5 原则（必须遵守，所有建议必须归类到其中一个）\n{principles}\n\n"
                "## 输出格式（严格遵守）\n"
                "输出一个 JSON 数组，每个元素是一条 suggestion：\n"
                "```json\n"
                "[\n"
                "  {\n"
                "    \"category\": \"prompt_update|knowledge_update|tool_adjustment|error_pattern|safety_guard\",\n"
                "    \"target\": \"被改的对象（文件路径/类名/函数名）\",\n"
                "    \"change\": \"一句话说明要改什么\",\n"
                "    \"evidence\": \"本次反馈/洞察里支持这条建议的证据\",\n"
                "    \"priority\": \"P0|P1|P2\"\n"
                "  }\n"
                "]\n"
                "```\n\n"
                "## 要求\n"
                "1. **每条建议必须归类到 5 原则之一**（不要发明新 category）。\n"
                "2. **target 要具体**（'subagents.Evaluator' 而非'评估模块'）。\n"
                "3. **change 要可执行**（描述具体动作，不是空泛口号）。\n"
                "4. **evidence 要有出处**（引用本次反馈/洞察的原文或要点）。\n"
                "5. **priority 取值**：P0=必须立刻修（安全/崩溃）；P1=重要（影响主流程体验）；P2=可排期优化。\n"
                "6. 如果本次反馈不构成任何有效建议（如纯赞美/闲聊），返回空数组 []。\n"
                "7. **优先 JSON 数组**——SelfUpdateAgent 会对纯文本做启发式兜底，但 JSON 准确率更高。"
            )

            # ─── 组装 user prompt ───
            user = (
                f"## 用户反馈文本\n{text or '（无）'}\n\n"
                f"## 已过滤的反思洞察（来自 SelfEvolution + QualityGate）\n"
                f"{insights_block or '（无）'}\n\n"
                f"## 外部反馈文件内容\n"
                f"{feedback_files_block or '（无）'}\n\n"
                "请基于以上材料，按 5 原则生成结构化更新建议（JSON 数组）。"
            )

            # ─── 调 LLM（多轮 history 用 messages；否则 user）───
            if history:
                msgs = [{"role": "user", "content": h["content"]} if h.get("role") == "user"
                        else {"role": "assistant", "content": h.get("content", "")}
                        for h in history[-10:] if isinstance(h, dict)]
                msgs.append({"role": "user", "content": user})
                # v0.22.1：自我更新不检索知识库（include_kb=False）——反思基于反馈/洞察，非知识问答
                raw = _safe_chat_with_retrieval(
                    model, system, messages=msgs, max_tokens=1500, include_kb=False,
                )
            else:
                raw = _safe_chat_with_retrieval(
                    model, system, user, max_tokens=1500, include_kb=False,
                )

            # ─── 解析 LLM 回复 ───
            suggestions = []
            if raw:
                parsed = _parse_json_array(raw)
                if parsed:
                    for item in parsed:
                        if not isinstance(item, dict):
                            continue
                        cat = str(item.get("category", "prompt_update"))
                        if cat not in _CATEGORY_KEYWORDS:
                            cat = _classify_category(
                                (item.get("change", "") or "") + " " + (item.get("target", "") or "")
                            )
                        pri = str(item.get("priority", "P2"))
                        if pri not in ("P0", "P1", "P2"):
                            pri = "P2"
                        suggestions.append({
                            "category": cat,
                            "target": str(item.get("target", "self_update"))[:120],
                            "change": str(item.get("change", ""))[:500],
                            "evidence": str(item.get("evidence", ""))[:300],
                            "priority": pri,
                        })
                else:
                    # 启发式切分兜底
                    suggestions = _heuristic_split(raw)

            # model=None 时 _safe_chat 返回 None → 必须有兜底结构
            if not suggestions:
                suggestions = [{
                    "category": "prompt_update",
                    "target": "self_update",
                    "change": "（LLM 未生成建议或回复不可解析）",
                    "evidence": (text or "")[:200],
                    "priority": "P2",
                }]

            summary = (raw or "（LLM 未返回内容，已用启发式生成）")[:200]
            return {
                "suggestions": suggestions,
                "summary": summary,
                "sources_used": sources_used,
                "mode": "self_update",
            }
        except Exception as e:
            # 全程兜底：任何异常都不抛错
            return {
                "suggestions": [{
                    "category": "error",
                    "target": "self_update",
                    "change": str(e),
                    "evidence": "",
                    "priority": "P2",
                }],
                "summary": "自我更新失败",
                "sources_used": ["feedback_text"],
                "mode": "self_update",
            }