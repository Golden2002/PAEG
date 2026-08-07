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
        # v0.24 ⭐ 适配决策注入槽——PAEG 可在调用 run() 前设置、consume 一次性应用。
        # 仅用于让上一轮 Adapter.switch_style/reinforce 真正影响本次讲解。
        self._pending_style_override = None
        self._pending_reinforce_note = None
        self._individuality_control = None
        self._individuality_profile_prompt = ""

    def set_pending_overrides(self, style_override: dict = None,
                              reinforce_note: str = None,
                              individuality_control: dict = None,
                              individuality_profile_prompt: str = None):
        """PAEG 调用：在 Presenter.run() 之前把上游决策推进槽里。"""
        if style_override is not None:
            self._pending_style_override = style_override
        if reinforce_note is not None:
            self._pending_reinforce_note = reinforce_note
        if individuality_control is not None:
            self._individuality_control = individuality_control
        if individuality_profile_prompt is not None:
            self._individuality_profile_prompt = individuality_profile_prompt

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

        # v0.24 ⭐ 消费上游注入（一次性，仅供本次讲解）。
        # 这些来自 PAEG 在 run() 前调 set_pending_overrides(...) 推入。
        style_override = getattr(self, "_pending_style_override", None)
        reinforce_note = getattr(self, "_pending_reinforce_note", None)
        ind_control = getattr(self, "_individuality_control", None) or {}
        ind_profile = getattr(self, "_individuality_profile_prompt", "") or ""
        # 用后即清（一次性）
        self._pending_style_override = None
        self._pending_reinforce_note = None

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
            # v0.24 ⭐ 把上游注入的真接到 system（让 LLM 真正按上游决策改写）
            if ind_profile:
                system = system + "\n\n## 个体化学生画像（v0.24）\n" + ind_profile
            if ind_control.get("style"):
                system = system + f"\n- 讲解方式：{ind_control['style']}"
            if ind_control.get("depth"):
                system = system + f"\n- 讲解深度：{ind_control['depth']}"
            if ind_control.get("rhythm"):
                system = system + f"\n- 节奏：{ind_control['rhythm']}"
            if ind_control.get("emotion_sensitive") == "是":
                system = system + "\n- 情绪敏感：学生在情绪较脆弱时，教学时更温和、多确认、避免施压。"
            if style_override and style_override.get("override_system_line"):
                # v0.24 ★ 关键：Adapter.switch_style 决策真正改变本次讲解
                system = system + (
                    f"\n\n## v0.24 适配决策注入（来自上一轮 Adapter 反馈，必须遵守）\n"
                    f"{style_override.get('override_system_line')}\n"
                    f"（本轮教学策略被 Adapter 调整为：{style_override.get('new_style', 'analogy')}）"
                )
            if reinforce_note:
                # v0.24 ★ 关键：Adapter.reinforce 决策真正追加补例子
                system = system + (
                    "\n\n## v0.24 适配决策注入（必须遵守）\n"
                    f"{reinforce_note}\n"
                    "请给出一个与之前不同角度的例子，让学生从例子反推概念。"
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

        # 规则回退模板（v0.24 ⭐ 适配决策也应用在规则回退里 —— 让端到端测试可观测风格变化）
        if kb_node:
            base = (kb_node.get("intuition") or kb_node.get("definition") or "关于该主题的讲解")
        else:
            base = f"关于 '{topic}' 的讲解"
        # v0.24：在规则回退里也体现风格切换/强化决策（可观测）
        appendix = ""
        style_label = tone
        if style_override and style_override.get("new_style"):
            style_label = f"{tone}+adapted({style_override['new_style']})"
            appendix = f"\n\n[v0.24 适配决策：switch_style→{style_override['new_style']}] {style_override.get('override_system_line','')}"
        elif reinforce_note:
            appendix = f"\n\n[v0.24 适配决策：reinforce 追加补例子] {reinforce_note[:120]}"
        if appendix:
            base = base + appendix
        return {
            "content": f"[{style_label}] {base}",
            "visual_description": "（v0.1 无图像）",
            "tone_used": style_label,
            "worldview_ratio": wv_ratio,
            "llm_generated": False,
            "kb_node_id": kb_node.get("id") if kb_node else None,
            # v0.24：把注入额外交付到返回里，供上层审计 / 端到端测试断言
            "_injected": {
                "style_override": style_override,
                "reinforce_note": reinforce_note,
                "individuality_control": ind_control,
                "had_individuality_profile": bool(ind_profile),
            },
        }


# ---------------------------------------------------------------------------
# 4. 评估子代理（确定性启发式，无随机）
# ---------------------------------------------------------------------------

class Evaluator:
    """评估子代理（v0.24 ⭐ 区分讲解质量与学生状态）。

    设计核心：避免"评讲 AI 自己的讲解"造成闭环虚假信号——
    最终合成 ``score = 0.6 * presentation_quality + 0.4 * learner_state``
    （讲解质量为主，学生状态为重要修正）。
    ``ready_to_advance`` 优先看 student_state；若 student_state 缺失（无学生数据）
    则保守返回 False，并在 reason 注明。
    """

    def __init__(self, model, kb):
        self.model = model
        self.kb = kb

    # ────────────────────────────────────────────────
    # 学生状态信号提取（v0.24 新增）
    # ────────────────────────────────────────────────

    @staticmethod
    def _extract_student_text(learner, step: dict, presentation: dict) -> str:
        """从 learner / step / presentation 中找学生输入文本。

        优先级：step["student_reply"] > presentation["student_reply"] >
        learner._last_student_reply。无则返回 ""——表示无学生数据可评。
        """
        for src in (step, presentation):
            if isinstance(src, dict):
                v = src.get("student_reply")
                if isinstance(v, str) and v.strip():
                    return v
        try:
            v = getattr(learner, "_last_student_reply", None)
            if isinstance(v, str) and v.strip():
                return v
        except Exception:
            pass
        return ""

    @staticmethod
    def _student_signal(student_text: str) -> dict:
        """对一段学生输入做确定性浅层语义分析。

        返回：
          - understanding: 0~1（理解度信号：含肯定词、会解释、举例 → 高）
          - confusion:    0~1（困惑信号：含困惑词、反问、否定 → 高）
          - engagement:   0~1（参与信号：长度 + 问号密度）
          - emotion:      "neutral"/"curious"/"frustrated"/"engaged"
          - quality:      "none"（无学生数据时）/ "low"（短/含糊）/ "normal"
        """
        if not student_text:
            return {
                "understanding": 0.0, "confusion": 0.0, "engagement": 0.0,
                "emotion": "neutral", "quality": "none",
            }
        t = student_text.strip()
        n = len(t)
        # 参与度：长度归一 + 问号密度
        engagement = min(1.0, n / 200.0 + (0.15 if "？" in t or "?" in t else 0.0))
        # 肯定词（理解）
        pos_kw = ("明白了", "懂了", "理解了", "原来如此", "所以是", "got it", "我懂了",
                  "i see", "这样啊", "原来是这样", "知道为什么")
        # 困惑词
        neg_kw = ("不懂", "为什么", "怎么会", "什么意思", "听不懂", "没听懂",
                  "太难了", "为什么是", "怎么会呢", "don", "confused",
                  "不明白", "搞不清楚")
        pos_hits = sum(1 for k in pos_kw if k in t.lower() if isinstance(k, str))
        neg_hits = sum(1 for k in neg_kw if k in t.lower() if isinstance(k, str))
        # 倾向：肯定 vs 困惑
        understanding = min(1.0, 0.5 + 0.2 * pos_hits - 0.15 * neg_hits)
        confusion = min(1.0, 0.1 * neg_hits + 0.05 * (1 if "?" in t or "？" in t else 0))
        if n < 6:
            quality = "low"
        elif n < 30:
            quality = "normal"
        else:
            quality = "normal"
        # 情绪
        if neg_hits >= 2:
            emotion = "frustrated"
        elif neg_hits >= 1 or ("?" in t or "？" in t) and pos_hits == 0 and n >= 12:
            emotion = "curious"
        elif pos_hits >= 1:
            emotion = "engaged"
        else:
            emotion = "neutral"
        return {
            "understanding": round(understanding, 3),
            "confusion": round(confusion, 3),
            "engagement": round(engagement, 3),
            "emotion": emotion,
            "quality": quality,
        }

    @staticmethod
    def _learner_state_summary(learner) -> dict:
        """从 LearnerProfile + learner 上的动态属性拼学生状态。"""
        sm = getattr(learner, "subjects_mastery", None)
        mastery = None
        subj = getattr(learner, "_current_subject", None) or getattr(learner, "subjects_mastery", None)
        if isinstance(sm, dict):
            for k, v in sm.items():
                # 取一个整数 level（不强求 current_subject）
                lvl = v.get("level") if isinstance(v, dict) else None
                if isinstance(lvl, (int, float)):
                    mastery = (k, float(lvl))
                    break
        trait = getattr(learner, "_individuality_trait", None) or {}
        emo = trait.get("emotional_tendency") or ""
        ls = trait.get("learning_style") or ""
        ks = trait.get("knowledge_gaps") or []
        return {
            "mastery": mastery,
            "emotional_tendency": emo,
            "learning_style": ls,
            "knowledge_gaps": list(ks) if isinstance(ks, list) else [],
        }

    # ────────────────────────────────────────────────

    def run(self, step: dict, learner, presentation: dict) -> dict:
        """评分：区分讲解质量（presentation_quality）与学生状态（learner_state）。

        返回：
          score / sub_scores (clarity / completeness) / ready_to_advance /
          emotion_signal / evaluated_by（保留兼容）+ presentation_quality
          / learner_state / has_student_data / score_composition / reason
        """
        content = str(presentation.get("content", ""))
        length = len(content)

        # ── 1. presentation_quality（讲解质量分，0~0.95）──
        # 长度分（0~0.35）：>=200 字满分，不足按比例
        length_score = min(0.35, length / 600.0)
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
        # 思考性问题（0~0.05）：讲解中含有引导思考的问句
        inquiry_score = 0.05 if ("?" in content or "？" in content) else 0.0

        presentation_quality = round(
            min(0.95, max(0.4, 0.4 + length_score + structure_score + tone_score + kb_score + inquiry_score)),
            3,
        )

        # ── 2. learner_state（学生状态分，0~0.95）──
        student_text = self._extract_student_text(learner, step, presentation)
        sig = self._student_signal(student_text)
        lstate = self._learner_state_summary(learner)

        has_student_data = bool(student_text.strip()) or bool(lstate.get("mastery")) \
            or bool(lstate.get("emotional_tendency")) or bool(lstate.get("learning_style")) \
            or bool(lstate.get("knowledge_gaps"))

        # 计算 student_state_score
        if not has_student_data:
            student_state_score = 0.5  # 默认中性（无数据时给中性，不给高分）
            student_data_quality = "none"
        else:
            base = 0.5 + 0.3 * sig["understanding"] - 0.2 * sig["confusion"] + 0.1 * sig["engagement"]
            # 若 learner 该学科 mastery 极低（<0.4），扣分（前置不足）
            mastery_penalty = 0.0
            if lstate.get("mastery"):
                m_level = lstate["mastery"][1]
                if m_level < 0.4:
                    mastery_penalty = 0.1
            student_state_score = round(
                min(0.95, max(0.2, base - mastery_penalty)), 3,
            )
            student_data_quality = sig["quality"] if student_text else "metadata_only"

        # ── 3. 合成最终 score（讲解 0.6 + 学生状态 0.4）──
        # 若有学生数据，按合成；若完全无学生数据，降权讲解为主
        if student_data_quality == "none":
            score = round(presentation_quality * 0.95 + student_state_score * 0.05, 3)
            reason = "no_student_data"
        else:
            score = round(presentation_quality * 0.6 + student_state_score * 0.4, 3)
            reason = "ok"

        # ── 4. ready_to_advance：基于 student_state 为主 ──
        # 旧版用讲解分数 ≥ 0.7 推进；新版保守：用学生状态分 ≥ 0.55（情绪 + 理解）
        # 学生困惑或缺数据 → 拒绝推进，等修复 2 的 Adapter 干预
        if not has_student_data:
            ready_to_advance = False
            reason = "no_student_data"
        elif sig["confusion"] >= 0.2 or student_state_score < 0.55:
            ready_to_advance = False
            reason = "learner_state_low"
        elif score < 0.7:  # 综合分仍不达标也暂缓
            ready_to_advance = False
            reason = "composite_low"
        else:
            ready_to_advance = True
            reason = "ok"

        # ── 5. 情绪信号（确定性）──
        # 优先级：学生情绪 > 讲解语气推断
        if has_student_data and sig["emotion"] != "neutral":
            emotion_signal = sig["emotion"]
        elif "？" in content or "?" in content:
            emotion_signal = "curious"
        elif any(m in content for m in tone_markers.get(tone_used, ())):
            emotion_signal = "engaged"
        else:
            emotion_signal = "neutral"

        return {
            "score": score,
            "sub_scores": {
                "clarity": round(min(1.0, 0.5 + length_score + 0.1 * (1 if structure_score > 0 else 0)), 3),
                "completeness": round(structure_score / 0.3 if structure_score else 0.5, 3),
            },
            "ready_to_advance": ready_to_advance,
            "emotion_signal": emotion_signal,
            "evaluated_by": "heuristic_v024",
            # ── v0.24 新增字段（不删除既有）──
            "presentation_quality": presentation_quality,
            "learner_state": {
                "student_state_score": student_state_score,
                "has_student_data": has_student_data,
                "data_quality": student_data_quality,
                "understanding": sig["understanding"],
                "confusion": sig["confusion"],
                "engagement": sig["engagement"],
                "emotion": sig["emotion"],
                "quality": sig["quality"],
                "student_text_len": len(student_text) if student_text else 0,
                "profile_summary": lstate,
            },
            "score_composition": {
                "presentation_weight": 0.6 if has_student_data else 0.95,
                "learner_state_weight": 0.4 if has_student_data else 0.05,
            },
            "reason": reason,
        }


# ---------------------------------------------------------------------------
# 5. 调整子代理（v0.24 ⭐ 决策真正可执行化）
# ---------------------------------------------------------------------------

class Adapter:
    """调整子代理（v0.24 ⭐ 决策携带可执行细节）。

    输出 decision + 可执行参数（含原因/风格建议/强化内容示例），
    供 PAEG 主循环根据 decision 真正干预下一次 Presenter 调用。
    """

    # 风格映射：switch_style 给 Presenter 一份明确的讲解风格 override
    STYLE_OPTIONS = {
        "analogy": "请用日常生活的类比讲这个概念，避免抽象公式（学生当前理解度低）。",
        "example_first": "请先给一个具体例子，让学生从例子反推概念，再讲抽象定义。",
        "socratic": "请连续提问 2-3 个引导性问题让学生自己推导出结论，不要直接给答案。",
        "visual": "请重点描述可视化（图形/流程图/类比图像），帮助学生先建立画面感。",
        "step_by_step": "请把这一步拆成 3-4 个小步，每步举一个数字例子，每步结束停顿让 ta 跟上。",
        "minimal": "把讲解精简到最核心的一句话 + 一个例子，不扩展、不补充、不举例超过 1 个。",
    }

    def __init__(self, model, kb):
        self.model = model
        self.kb = kb

    def run(self, evaluation: dict, learner, step: dict) -> dict:
        """确定性决策：根据最终 score / student_state 输出可执行调整指令。

        决策维度：
          - score < 0.55 或 learner_state.confusion 高 → switch_style
          - 0.55 <= score < 0.7  → reinforce（仍可附带小风格调整）
          - 0.7 <= score         → continue
        """
        score = evaluation.get("score", 1.0)
        ls = evaluation.get("learner_state") or {}
        confused = bool(ls.get("confusion", 0) >= 0.2)
        mastery_penalty = (ls.get("profile_summary") or {}).get("mastery")
        mastery_low = bool(isinstance(mastery_penalty, tuple) and mastery_penalty[1] < 0.4)

        style_hint = "analogy"
        if mastery_low:
            style_hint = "step_by_step"
        elif confused:
            style_hint = "example_first"

        if score < 0.55 or confused and mastery_low:
            return {
                "decision": "switch_style",
                "action": {
                    "type": "switch_style",
                    "details": f"换 {style_hint} 讲法：{self.STYLE_OPTIONS[style_hint]}",
                    "parameters": {
                        "difficulty_delta": -1,
                        "new_style": style_hint,
                        "override_system_line": self.STYLE_OPTIONS[style_hint],
                    },
                },
                "score": score,
                "learner_state": ls,
            }
        if score < 0.7:
            return {
                "decision": "reinforce",
                "action": {
                    "type": "reinforce",
                    "details": f"补一个例子/换一个角度再讲：{self.STYLE_OPTIONS.get('example_first', '')}",
                    "parameters": {
                        "difficulty_delta": 0,
                        "reinforce_mode": "extra_example",
                        "override_system_line": self.STYLE_OPTIONS.get("example_first", ""),
                    },
                },
                "score": score,
                "learner_state": ls,
            }
        return {
            "decision": "continue",
            "action": {"type": "continue",
                       "details": "学生状态良好，按计划继续",
                       "parameters": {"difficulty_delta": 0}},
            "score": score,
            "learner_state": ls,
        }


# ---------------------------------------------------------------------------
# 6. 答案子代理（v0.19.14 ⭐）
# ---------------------------------------------------------------------------

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
        v0.22.2：危机协议——自伤/自杀信号走 SafetyChecker 识别。
        v0.22.3：**无论何种情况，先基于用户说的话回复**——危机信号不直接短路成预制回复，
        而是注入危机指引让 LLM 融入生成，仅当 LLM 失败时才用预制回复兜底。
        """
        # v0.22.2/3：危机识别（不短路，只注入指引）
        _crisis_context = None
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
                    _crisis_context = "opt_out"
                else:
                    _crisis_context = "active"
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
            "## 你的底层世界观（v0.22.2 ⭐ 从薇依原著提炼，一切情绪支持策略之基）\n"
            "1. **最重要的事**：先回应学生此刻的需求、帮他疏导情绪；再在理性上帮他认知**世界的真实**。\n"
            "2. **世界的真实是唯一被看重的**：不美化、不粉饰、不虚构安慰。学生被'价值颠倒的迷雾'包裹时，\n"
            "   温柔地帮他拨开——'我做错了一件事'不是'我一无是处'，'这件事暂时失败'不是'世界永远如此'。\n"
            "3. **真实中，罪恶无法消除，善也无法被罪恶消除**：不要许诺'消除痛苦'的虚假解法，也不要让学生\n"
            "   认定'我坏透了/世界坏透了'（那是取消善的绝望）。帮他看见那被严格限制、艰难获得、掺杂恶的善——\n"
            "   它小，但真实存在。这正是为什么要坚持陪下去。\n"
            "4. **一切属世之物皆有条件；有条件即矛盾；矛盾的张力构成真实**：学生说'又想放弃又不想放弃'，\n"
            "   这不是混乱，是属世之物的条件性。不要急着替他'解决矛盾'——帮他看见矛盾、住进矛盾，\n"
            "   矛盾的张力正是真实所在，也是他做出自由选择的空间。\n"
            "5. **情绪支持 = 疏导情绪 + 认知真实**：先接住情绪（命名/验证/陪伴），再温和帮他对自己的\n"
            "   价值判断（是否苛刻）和对世界的理解（是否失真）做现象学式的检视。\n\n"
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
        # v0.22.3：危机指引注入（不短路——LLM 先回应用户内容，再自然融入关怀）
        if _crisis_context == "active":
            system = system + (
                "\n\n## 危机响应指引（v0.22.3 ⭐ 学生表达了自伤/自杀信号）\n"
                "学生这段话里有'想死/不想活/自杀'等信号。**请务必：**\n"
                "1. **先完整回应用户说的话**——他具体说了什么、在经历什么，先让他感到被真正听见；\n"
                "   不要跳过他的内容直接给热线。\n"
                "2. 在回应中温和地关切这份痛苦，不评判、不惊慌、不空洞安慰。\n"
                "3. 结尾自然提到：如果痛苦难以独自承受，可以联系信任的成年人、家长或心理援助热线 12356；\n"
                "   同时补充——'你还可以继续和我聊天，也可以去现实里找一个真实的、信得过的人陪在身边，"
                "你不需要一个人面对。'\n"
                "4. 语气平稳、克制、真实（薇依式），不煽情。"
            )
        elif _crisis_context == "opt_out":
            system = system + (
                "\n\n## 危机拒绝指引（v0.22.3）\n"
                "学生此前明确表示不需要热线/咨询/专业服务。**请：**\n"
                "1. 先回应用户此刻说的话；\n"
                "2. **不再重复提示任何热线或专业服务**（你已经提示过了，尊重他的选择）；\n"
                "3. 转而表达陪伴：'你不需要一个人扛着这些，可以继续和我说，也可以找一个信得过的真实的人，"
                "把这份重量分一点出去。那也是一种勇气。'"
            )
        # v0.20.2：若有历史，传真 messages（多轮连贯性）
        # v0.24 ⭐ 健壮性：与 SelfUpdateAgent 1029-1031 同等标准——
        # isinstance(h, dict) 守护 + h.get("role")/h.get("content")，
        # 跳过缺 key / 非字典条目，不再因下标访问而崩溃。
        if history:
            msgs = []
            for h in history[-10:]:
                if not isinstance(h, dict):
                    continue
                role = h.get("role")
                content_h = h.get("content", "")
                if role in ("user", "assistant"):
                    msgs.append({"role": role, "content": content_h})
                else:
                    # 角色未知条目降级为 user（保留上下文，但不假设方向）
                    msgs.append({"role": "user", "content": content_h})
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
            # v0.22.3：LLM 失败时按危机状态兜底（正常/危机/拒绝）
            if _crisis_context == "active":
                reply = (
                    "我听见你说的了，也听出了这句话里的重量。你刚才说的这些，我都在认真看。\n"
                    "如果你或身边的人有自伤想法，请立刻联系信任的成年人、家长或心理援助热线 12356。\n"
                    "除了热线，你还有很多其他的方法：你可以继续和我聊天，也可以去现实生活中找一个真实的、"
                    "你信得过的、能陪伴在你身边的人。你不需要一个人面对这些。")
            elif _crisis_context == "opt_out":
                reply = (
                    "我听见你了。我知道你不想听那些热线的事——我不再提了。\n"
                    "但我想让你知道：你不需要一个人扛着这些。你可以继续和我说，任何时刻都行；"
                    "也可以去找一个你信得过的、真实的人，把这份重量分一点出去。那也是一种勇气。")
            else:
                reply = ("我听见你说的了。我不急着给你一个答案或者一条建议——"
                         "如果你愿意，可以多跟我说一些具体的事情，我在这儿陪着你。")
        return {"content": reply, "mode": "affection", "crisis": bool(_crisis_context)}

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

# ---------------------------------------------------------------------------
# 9. 个体化子代理（v0.22.3 ⭐ Individuality）
# ---------------------------------------------------------------------------


class Individuality:
    """个体化（第 9 个 subagent）：连通上游用户建模信息 → 下游对 LLM 的控制。

    上游输入（建模）：
      - 对话历史（history）：extract_user_facts 提取个人事实
      - 用户自我陈述（learner.self_description）
      - 16 维正交画像（StudentTrait.from_learner，含母语）
    下游输出（对 LLM 的控制）：
      - 回复语言（native_language——英语/法语用户用母语学习）
      - 教学风格（认知通道 cognitive_style 适配）
      - 讲解深度（学段 + 知识掌握度）
      - 节奏适配（学习节奏/时段偏好）
      - 情绪敏感度（情感状态——教学时避免触发焦虑）
    核心：个别地对待每一个学生，尊重个体特征，因材施教。

    v0.23.0 ⭐ 持久化闭环：
    - run() 现在读取 ``learner._individuality_trait`` 已有画像（若有），让
      LLM 增量建模——只输出"新增或变化"的信息，避免每轮覆盖旧画像。
    - 新增 ``apply_modeled_to_learner(learner)``：把建模结果写回 learner
      动态属性，供下次 run() 读取（增量继承）。
    - 新增 ``persist(learner, user_id)``：把 self._llm_modeled 合并进
      learner 持久化画像，再调 ``user_store.save_learner`` 落盘。
    """

    def __init__(self):
        # v0.23.0：实例属性兜底（防止无 run() 调用时 AttributeError）
        self._llm_modeled = {}
        self._existing_modeled = {}

    def run(self, model=None, learner=None, history: list = None,
            subject: str = "general") -> dict:
        """聚合上游建模信息 + 指挥 LLM 补充建模，产出下游 LLM 控制指令。

        v0.23.0 增量建模（升级自 v0.22.3）：
        - 上游：规则提取 16 维画像 + 个人事实；若提供 model，则指挥 LLM 从
          对话历史 + 自我陈述中**增量**提取结构化建模信息——结合已有
          ``learner._individuality_trait`` 已有画像，只输出"新增或变化"，
          避免覆盖旧画像。
        - 下游：产出 profile_prompt + control（语言/风格/深度/节奏/情绪敏感），
          供调用方注入对话 system prompt 指挥 LLM 个性化输出。

        返回：{"profile_prompt": str, "trait": dict, "native_language": str,
               "control": {"language", "style", "depth", "rhythm", "emotion_sensitive"},
               "facts": list, "llm_modeled": bool,
               "existing_modeled": dict（增量前画像，供调试/审计）}
        """
        # v0.23.0：实例属性兜底
        if not hasattr(self, "_llm_modeled") or self._llm_modeled is None:
            self._llm_modeled = {}
        if not hasattr(self, "_existing_modeled") or self._existing_modeled is None:
            self._existing_modeled = {}

        # v0.23.0：读取 learner 上已有的建模结果（增量基础）
        existing = {}
        if learner is not None:
            existing = dict(getattr(learner, "_individuality_trait", {}) or {})
        self._existing_modeled = dict(existing)  # 留底（供 audit/debug）

        llm_modeled = False
        # v0.22.3→v0.23.0：上游 LLM 建模——指挥 LLM 增量提取
        if model is not None:
            try:
                _hist_src = ""
                if history:
                    _hist_src = "\n".join(
                        f"{'学生' if h.get('role')=='user' else '老师'}: {str(h.get('content',''))[:200]}"
                        for h in history[-8:])
                _desc = getattr(learner, "self_description", "") if learner else ""
                if _hist_src or _desc:
                    # v0.23.0：增量指令——只有当已有画像时才告诉 LLM "已有画像"
                    _existing_str = ""
                    _incremental_mode = bool(existing)
                    if existing:
                        # 已有内容简明展示，避免 LLM 把已有信息当新增报
                        _parts = []
                        for k in ("learning_style", "emotional_tendency", "motivation"):
                            if existing.get(k):
                                _parts.append(f"{k}={existing[k]}")
                        for k in ("knowledge_strengths", "knowledge_gaps", "interests"):
                            v = existing.get(k) or []
                            if v:
                                _parts.append(f"{k}={','.join(v[:5])}")
                        if _parts:
                            _existing_str = "\n（学生已有画像：{0} ——请勿重复，只输出本轮新增或变化的信息；无新增则输出空 JSON {{}}）".format(
                                "; ".join(_parts))
                    _sys = (
                        "你是个体化建模助手。从学生的对话历史与自我陈述中，提取 6 类结构化信息："
                        "1) learning_style（学习方式偏好） 2) knowledge_strengths（已掌握） "
                        "3) knowledge_gaps（薄弱点） 4) emotional_tendency（情绪倾向） "
                        "5) motivation（学习动机） 6) interests（兴趣）\n"
                        + (
                            "结合学生已有画像，只输出本轮新增或变化的信息——"
                            "没有变化就输出空 JSON {}，不要重复已有内容。\n"
                            if _incremental_mode else
                            "请根据本轮对话/自我陈述输出完整提取（首次建模）。\n"
                        )
                        + '输出 JSON 格式：{"learning_style":"...","knowledge_strengths":[...],'
                        '"knowledge_gaps":[...],"emotional_tendency":"...",'
                        '"motivation":"...","interests":[...]}'
                    )
                    _usr = (
                        f"对话历史：\n{_hist_src}\n自我陈述：{_desc}"
                        f"{_existing_str}"
                    )
                    _llm_out = _safe_chat(model, _sys, _usr, max_tokens=400)
                    if _llm_out:
                        import json as _json
                        import re as _re
                        _m = _re.search(r"\{.*\}", _llm_out, _re.S)
                        if _m:
                            try:
                                _delta = _json.loads(_m.group(0))
                            except Exception:
                                _delta = None
                            if isinstance(_delta, dict):
                                # v0.23.0：合并增量——已有键若 _delta 给出新值则覆盖；
                                # list 类键做并集（避免重复）；标量键（learning_style
                                # / emotional_tendency / motivation）若 _delta 为空则
                                # 不覆盖已有。
                                merged = dict(existing)  # copy
                                for k, v in _delta.items():
                                    if k in ("knowledge_strengths", "knowledge_gaps",
                                             "interests"):
                                        if isinstance(v, list):
                                            base = list(merged.get(k, []) or [])
                                            for item in v:
                                                if isinstance(item, str):
                                                    key = item.strip().lower()
                                                    if key and key not in {
                                                        str(x).strip().lower() for x in base
                                                        if isinstance(x, str)
                                                    }:
                                                        base.append(item.strip())
                                            merged[k] = base
                                        # v 为 None / 非 list：忽略
                                    elif k in ("learning_style", "emotional_tendency",
                                               "motivation"):
                                        if isinstance(v, str) and v.strip() and \
                                                v.strip().lower() not in ("unknown", ""):
                                            merged[k] = v.strip()
                                # 清理空字符串键
                                merged = {k: v for k, v in merged.items() if v}
                                self._llm_modeled = merged
                                llm_modeled = True
                                # v0.23.0：把建模结果写回 learner（动态属性，
                                # 不破坏 LearnerProfile dataclass）
                                if learner is not None:
                                    try:
                                        object.__setattr__(
                                            learner, "_individuality_trait", merged)
                                    except Exception:
                                        try:
                                            learner.__dict__["_individuality_trait"] = merged
                                        except Exception:
                                            pass
            except Exception:
                pass
        # 规则聚合（原有逻辑）
        trait = {}
        profile_prompt = ""
        native_language = "zh"
        facts = []
        try:
            # 1. 上游：16 维画像（含母语）
            from student_trait import StudentTrait
            if learner is not None:
                t = StudentTrait.from_learner(
                    learner,
                    user_model=getattr(learner, "_user_model", None),
                )
                # v0.23.0：把增量建模结果写入 trait（覆盖默认 unknown 项）
                _modeled_now = getattr(self, "_llm_modeled", {}) or {}
                if _modeled_now:
                    t.update_from_dialogue(_modeled_now)
                # v0.23.0：把已有 facts 写入 trait（personal_facts）
                try:
                    if facts:
                        t.update_from_facts(facts)
                except Exception:
                    pass
                native_language = getattr(t, "native_language", None) or "zh"
                # v0.22.3：直接从 learner 兜底读母语（即使 StudentTrait 未设）
                if native_language == "zh" and learner is not None:
                    _nl2 = getattr(learner, "native_language", None)
                    if _nl2 and _nl2 != "zh":
                        native_language = _nl2 if isinstance(_nl2, str) else "zh"
                trait = t.to_dict() if hasattr(t, "to_dict") else {}
                profile_prompt = t.to_prompt(levels=[1, 2])
                # v0.23.0：把 t 也存到 learner（供下次 run 读取）
                try:
                    object.__setattr__(learner, "_individuality_trait_obj", t)
                except Exception:
                    try:
                        learner.__dict__["_individuality_trait_obj"] = t
                    except Exception:
                        pass
            # 2. 上游：对话历史 → 个人事实
            try:
                from context_bundle import extract_user_facts
                facts = extract_user_facts(history or [])
            except Exception:
                pass
            if facts:
                facts_str = "\n".join(f"- {f}" for f in facts[:8])
                profile_prompt = profile_prompt + f"\n- 个人事实（记忆锚点）：\n{facts_str}"
            # 3. v0.22.3：LLM 建模结果并入 profile_prompt
            if llm_modeled and hasattr(self, "_llm_modeled"):
                _md = self._llm_modeled
                _add = []
                if _md.get("learning_style"):
                    _add.append(f"- 学习方式（LLM 建模）：{_md['learning_style']}")
                if _md.get("knowledge_gaps"):
                    _add.append(f"- 薄弱点（LLM 建模）：{', '.join(_md['knowledge_gaps'][:3])}")
                if _md.get("emotional_tendency"):
                    _add.append(f"- 情绪倾向（LLM 建模）：{_md['emotional_tendency']}")
                if _md.get("interests"):
                    _add.append(f"- 兴趣（LLM 建模）：{', '.join(_md['interests'][:3])}")
                if _add:
                    profile_prompt = profile_prompt + "\n" + "\n".join(_add)
        except Exception:
            pass

        # 4. 下游：对 LLM 的控制指令
        control = {
            "language": native_language,
            "style": self._derive_style(trait),
            "depth": self._derive_depth(trait, subject),
            "rhythm": self._derive_rhythm(trait),
            "emotion_sensitive": self._derive_emotion(trait),
        }
        return {
            "profile_prompt": profile_prompt,
            "trait": trait,
            "native_language": native_language,
            "control": control,
            "facts": facts,
            "llm_modeled": llm_modeled,
            "existing_modeled": self._existing_modeled,
            "mode": "individuality",
        }

    def apply_modeled_to_learner(self, learner) -> bool:
        """v0.23.0 ⭐ 把建模结果写回 learner 动态属性。

        把 ``self._llm_modeled`` 合并进 learner 的：
        - ``learner._individuality_trait``（dict，供下次 run() 增量继承）
        - ``learner._individuality_trait_obj``（StudentTrait 实例，供调试）

        同时把 knowledge_gaps / knowledge_strengths / interests 也同步到
        ``learner.subjects_mastery`` / ``learner.interests``（若这些字段存在），
        让下游（如 context_bundle / expert_guard）也能读到。

        learner 为 None 时返回 False；写回失败返回 False；成功 True。
        """
        if learner is None:
            return False
        if not hasattr(self, "_llm_modeled") or not self._llm_modeled:
            return False
        try:
            modeled = dict(self._llm_modeled)
            # 1) dict 形式——供下次 run() 增量
            try:
                object.__setattr__(learner, "_individuality_trait", modeled)
            except Exception:
                learner.__dict__["_individuality_trait"] = modeled
            # 2) StudentTrait 实例——供 to_prompt
            try:
                from student_trait import StudentTrait
                t = StudentTrait.from_learner(learner)
                t.update_from_dialogue(modeled)
                try:
                    object.__setattr__(learner, "_individuality_trait_obj", t)
                except Exception:
                    learner.__dict__["_individuality_trait_obj"] = t
                # 3) 同步到 LearnerProfile 原生字段（如有）
                # subjects_mastery：knowledge_strengths → evidence_pos；
                # knowledge_gaps → evidence_neg
                if hasattr(learner, "subjects_mastery") and isinstance(
                        getattr(learner, "subjects_mastery", None), dict):
                    sm = dict(learner.subjects_mastery or {})
                    for subj in modeled.get("knowledge_strengths") or []:
                        if not isinstance(subj, str) or not subj.strip():
                            continue
                        m = sm.setdefault(subj, {
                            "level": 0.7, "evidence_pos": [],
                            "evidence_neg": [], "recency": "",
                        })
                        ep = m.get("evidence_pos") or []
                        if "individuality_LLM" not in ep:
                            ep.append("individuality_LLM")
                        m["evidence_pos"] = ep
                    for subj in modeled.get("knowledge_gaps") or []:
                        if not isinstance(subj, str) or not subj.strip():
                            continue
                        m = sm.setdefault(subj, {
                            "level": 0.3, "evidence_pos": [],
                            "evidence_neg": [], "recency": "",
                        })
                        en = m.get("evidence_neg") or []
                        if "individuality_LLM" not in en:
                            en.append("individuality_LLM")
                        m["evidence_neg"] = en
                        m["level"] = min(m.get("level", 0.5), 0.3)
                    learner.subjects_mastery = sm
                # interests：写入 learner.interests（若有；动态属性）
                if modeled.get("interests"):
                    try:
                        cur = list(getattr(learner, "interests", []) or [])
                        seen = {str(x).strip().lower() for x in cur if x}
                        for it in modeled["interests"]:
                            if isinstance(it, str):
                                k = it.strip().lower()
                                if k and k not in seen:
                                    cur.append(it.strip())
                                    seen.add(k)
                        try:
                            object.__setattr__(learner, "interests", cur)
                        except Exception:
                            learner.__dict__["interests"] = cur
                    except Exception:
                        pass
            except Exception:
                pass
            return True
        except Exception:
            return False

    def persist(self, learner, user_id: str = "") -> bool:
        """v0.23.0 � 把建模结果持久化到 learner + 落盘。

        流程：
        1. ``apply_modeled_to_learner(learner)``——把 self._llm_modeled 写回 learner
        2. 若 ``user_id`` 形如 ``u<digit>...``（注册用户），调
           ``user_store.save_learner(user_id, learner)`` 落盘到 users.json +
           users_data/<uid>/profile.json。
        3. 匿名 ``web_xxx`` 用户：仅写 learner 内存，不落盘（每次刷新会丢，
           但保持 web 用户画像轻量——避免污染 users.json 持久层）。

        返回 True 表示成功持久化；False 表示匿名用户或失败。
        """
        if learner is None:
            return False
        # 1) 写回 learner 动态属性
        self.apply_modeled_to_learner(learner)
        # 2) 仅注册用户（u 前缀 + 数字后缀）落盘
        if not user_id or not (
                isinstance(user_id, str) and user_id.startswith("u")
                and user_id[1:].isdigit()):
            return False
        try:
            from user_store import UserStore
            store = UserStore()
            # v0.23.0 ⭐ 直接覆盖 users.json[user].learner——
            # 不用 store.save_learner（asdict 漏动态字段），而是手动序列化
            # learner 全 __dict__（含 _individuality_trait 等）
            try:
                from dataclasses import asdict as _asdict
                ld = _asdict(learner)
                # 合并动态属性（含 _individuality_trait / _individuality_trait_obj
                # / interests / personal_facts 等运行时字段）
                for k, v in getattr(learner, "__dict__", {}).items():
                    if k not in ld:
                        ld[k] = v
                # _individuality_trait_obj：StudentTrait 实例 → dict
                if hasattr(learner, "_individuality_trait_obj"):
                    _t = getattr(learner, "_individuality_trait_obj")
                    try:
                        ld["_individuality_trait_obj"] = _t.to_dict()
                    except Exception:
                        ld["_individuality_trait_obj"] = None
                # 写入 users.json[user].learner
                for u in store._data["users"].values():
                    if u["user_id"] == user_id:
                        u["learner"] = ld
                        store._save()
                        break
            except Exception:
                # 兜底：原 store.save_learner（漏动态字段但至少不丢原生字段）
                store.save_learner(user_id, learner)
            # 同步：写一份到 users_data/<uid>/profile.json（确保 v0.15 user_dir
            # 初始化时拿到的 profile.json 也是最新的）
            try:
                udir = store.user_dir(user_id)
                if udir:
                    import json as _json
                    with open(
                            udir.rstrip("/").rstrip("\\") + "/profile.json",
                            "w", encoding="utf-8") as f:
                        _json.dump(ld, f, ensure_ascii=False, indent=1)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def inject_control(self, system: str, control: dict = None) -> str:
        """v0.22.3 下游：把个体化控制指令追加到对话 system prompt。

        指挥 LLM 以学生母语回复 + 按认知通道/学段/节奏/情绪适配输出。
        """
        ctl = control or {}
        _lang = ctl.get("language") or "zh"
        if _lang != "zh":
            system = system + f"\n\n## 个体化语言指令（v0.22.3 必须遵守）\n请用学生的母语回复（学生母语：{_lang}）。"
        _style = ctl.get("style")
        if _style:
            system = system + f"\n- 讲解方式：{_style}"
        _depth = ctl.get("depth")
        if _depth:
            system = system + f"\n- 讲解深度：{_depth}"
        if ctl.get("emotion_sensitive") == "是":
            system = system + "\n- 情绪敏感：学生当前情绪较脆弱，教学时更温和、多确认、避免施压。"
        return system

    @staticmethod
    def _derive_style(trait: dict) -> str:
        cog = (trait.get("cognitive_style") or "unknown")
        return {
            "visual": "多用图示/比喻/可视化", "auditory": "多用讲解/口头复述/讨论",
            "reading": "多用文字/阅读材料/笔记", "kinesthetic": "多用动手/例题/练习",
        }.get(cog, "均衡使用多种方式")

    @staticmethod
    def _derive_depth(trait: dict, subject: str) -> str:
        ident = trait.get("identity") or {}
        grade = ident.get("grade_level") or "high_school"
        return {
            "middle_school": "直观例子为主，避免抽象术语",
            "high_school": "直觉之上引入公式与概念",
            "undergraduate": "体系化讲解，重推导与证明",
            "graduate_exam": "考点导向，重答题策略",
        }.get(grade, "平衡直观与严谨")

    @staticmethod
    def _derive_rhythm(trait: dict) -> str:
        rhythm = trait.get("learning_rhythm") or "unknown"
        return {"short": "每段讲短一些，多停顿确认", "medium": "保持常规节奏",
                "long": "可以深入展开，分块推进"}.get(rhythm, "按需调节节奏")

    @staticmethod
    def _derive_emotion(trait: dict) -> str:
        emo = trait.get("emotion") or "neutral"
        return "是" if emo in ("anxious", "withdrawn") else "否"
