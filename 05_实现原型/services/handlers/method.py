# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ services/handlers/method.py

学习方法咨询（v0.19.7 从 server.py 迁出）。

"如何学习X/怎么复习"走学习指导而非教学/出题——结合学段/学科/用户画像，
给出针对性的学习方法建议（像一位有经验的老师在谈怎么学这门课）。
"""
from __future__ import annotations


def _handle_method_advice(learner, concept, subject):
    """v0.19.7：学习方法咨询。

    依赖全部函数体内 import（避免循环）；llm 从 infra.runtime 懒加载。
    """
    from flask import jsonify
    from prompts import build_general_chat_system, build_general_chat_user
    from subagents import _safe_chat
    from infra.runtime import get_llm
    from utils import _build_learner_ctx_str

    llm = get_llm()
    grade = getattr(learner, "grade_level", "high_school")
    grade_cn = {"middle_school": "初中", "high_school": "高中/高考",
                "undergraduate": "大学本科", "graduate_exam": "考研"}.get(grade, grade)
    from prompts import get_style
    try:
        subject_cn = get_style(subject)["label"]
    except Exception:
        subject_cn = subject
    desc = getattr(learner, "self_description", "") or ""
    desc_line = f"学生的自述：{desc.strip()}\n" if desc.strip() else ""
    # v0.36 ⭐ P0-08 ContextBundle 接线：补 BDI/user_model/完整画像段注入
    _learner_ctx = _build_learner_ctx_str(learner)

    system = (
        "你是 Émile Novis，一位既懂学科又懂学习的老师。学生问的是'如何学习{subject}'这类方法问题。\n"
        "请给出一份**具体、可执行的学习方法建议**，而不是讲学科概念，更不是出题考他。\n"
        "要点：\n"
        "1. 先理解 ta 的处境（{grade}学生）和基础\n"
        "2. 给出学习路径：入门→进阶→强化，每阶段该做什么\n"
        "3. 推荐具体方法（如：先建立直觉再用工具、做例题找规律、错题复盘）\n"
        "4. 结合这门学科的特点（{subject}该怎么学才有感觉）\n"
        "5. 语气像一位耐心的老师，不列'步骤1/2/3'，用自然的讲义式叙述\n"
        "不需要出题，不需要讲具体知识点，就谈'怎么学'。"
    ).format(subject=subject_cn, grade=grade_cn)
    if _learner_ctx:
        system = f"【学生画像与对象意识】\n{_learner_ctx}\n\n" + system
    # v0.42.3 ⭐ P1 修复：method 接入语言规范层（LANGUAGE_STYLE）——
    # 此前 system 完全手搓无语言规范约束，输出风格不受薇依式朴素语言约束。
    try:
        from prompts import LANGUAGE_STYLE
        system = f"{LANGUAGE_STYLE}\n\n" + system
    except Exception:
        pass
    # v0.43 ⭐ 注册问卷固定提示词（用户专属教学指令，所有模式共用）
    try:
        from prompts import _build_questionnaire_block
        _qq = _build_questionnaire_block(learner)
        if _qq:
            system = f"{_qq}\n\n" + system
    except Exception:
        pass
    # v0.43 ⭐ P1 修复：method 消费约束掩码（此前 _set_constraint_flags 设置了但 handler 不读）
    try:
        from prompts import _build_constraint_layers
        _cf = getattr(learner, "_constraint_flags", ()) or ()
        if _cf:
            system = f"{_build_constraint_layers(_cf)}\n\n" + system
    except Exception:
        pass
    # v0.42.3 ⭐ P1 修复：method 注入对话历史 + 用户事实（共享记忆能力）——
    # 此前 handler 完全不看历史，连问两次"怎么学数学"第二次无上文。
    try:
        from infra.sessions import SESSIONS
        _hist = SESSIONS.get(f"chat_hist_{getattr(learner, 'id', '')}", [])
        if _hist:
            _hl = []
            for _m in _hist[-20:]:
                _rc = "学生" if _m.get("role") == "user" else "Émile"
                _cc = str(_m.get("content") or "")[:300]
                if _cc.strip():
                    _hl.append(f"{_rc}: {_cc}")
            if _hl:
                system = system + "\n\n## 对话历史\n" + "\n".join(_hl)
        from context_bundle import extract_user_facts
        _facts = extract_user_facts(_hist)
        if _facts:
            _facts_str = "\n".join(f"- {f}" for f in _facts)
            system = system + "\n\n## 用户说过的事实\n" + _facts_str
    except Exception:
        pass

    user = f"学生问：{concept}\n{desc_line}请给出{subject_cn}的学习方法建议。"
    # v0.42.3 ⭐ P1 修复：method 接入检索（KB+Library 三线）——此前完全裸调
    # _safe_chat 无任何检索，学习方法建议全靠 LLM 训练知识（可能过时/泛泛）。
    # 换 _safe_chat_with_retrieval（内部 _pre_retrieve 检索 KB+Library+用户资料）。
    try:
        from subagents import _safe_chat_with_retrieval
        # v0.44 ⭐ 修复：传 tools（含 web_search）——此前未传 → LLM 无联网工具，
        # 学习方法建议全靠训练知识。现 LLM 可主动联网检索最新学习方法/资料。
        from tool_registry import get_tool_defs
        answer = _safe_chat_with_retrieval(
            llm, system, user=user, subject=subject,
            max_tokens=1400, learner=learner, llm=llm,
            tools=get_tool_defs())
    except Exception:
        answer = _safe_chat(llm, system, user, max_tokens=1400)
    if not answer:
        answer = (f"关于怎么学{subject_cn}，我的建议是：先从最基础的概念建立直觉，"
                  f"再通过做典型例题巩固，最后用错题复盘查漏补缺。具体方法我可以展开讲。")
    # v0.42.3 ⭐ P1 修复：method 语言规范收口（L2/L3）——对齐 affection 接入范式
    try:
        from services.polish import _polish_text
        answer = _polish_text(answer, context=f"method:{concept[:30]}")
    except Exception:
        pass

    return jsonify({
        "session_id": f"method_{learner.id}",
        "summary": {"avg_score": 0},
        "worldview_used": "weil",
        "tone_ratio": 0,
        "presentations": [
            {"step_id": 1, "content": answer, "step_type": "method"}
        ],
        "evaluations": [],
        "diagnosis": {},
        "plan": {"steps": [{"type": "method"}]},
        "reflections": [],
        "learner": {
            "id": learner.id,
            "nickname": learner.nickname,
            "grade_level": learner.grade_level,
            "subjects_mastery": learner.subjects_mastery,
        },
    })
