# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ services/handlers/problem.py

出题请求处理（v0.19 从 server.py 迁出）。

用户说"给我一道经典题/出题/练习"时调用，避免被当概念教学。结合学段/学科/画像
生成经典题目。
"""
from __future__ import annotations


def _handle_problem_request(learner, concept, subject):
    """v0.19：出题请求处理——结合学段/学科/画像生成经典题目。"""
    from flask import jsonify
    from prompts import build_general_chat_user, get_style
    from subagents import _safe_chat
    from infra.runtime import get_llm
    from utils import _build_learner_ctx_str

    llm = get_llm()
    # 学段中文
    grade = getattr(learner, "grade_level", "high_school")
    grade_cn = {"middle_school": "初中", "high_school": "高中/高考",
                "undergraduate": "大学本科", "graduate_exam": "考研"}.get(grade, grade)
    # 学科中文
    try:
        subject_cn = get_style(subject)["label"]
    except Exception:
        subject_cn = subject
    # 画像（薄弱点/目标等）
    desc = getattr(learner, "self_description", "") or ""
    desc_line = f"学生自述：{desc.strip()}\n" if desc.strip() else ""
    # v0.36：补 BDI/user_model/完整画像段注入（出题时知学生薄弱点）
    _learner_ctx = _build_learner_ctx_str(learner)

    system = (
        "你是一位有多年命题经验、深知考试评分标准的{grade}{subject}老师（Émile Novis）。\n"
        "学生要求你给出一道经典题目。请：\n"
        "1. 出 1 道**经典、有代表性**的{subject}题（难度贴合{grade}考试要求）\n"
        "2. 题目要规范：条件清楚、目标明确、是真题或经典题的变式\n"
        "3. 给出完整解答（作为可对照的标准答案，分步、严谨、用 LaTeX 公式）\n"
        "4. 最后点出这道题考查的知识点和易错点\n"
        "5. 如果学生自述了薄弱点，优先出一道针对薄弱点的题\n"
        "语言朴素准确，不用'步骤1/2/3'，用自然段落。公式用 $...$ 或 $$...$$。"
    ).format(grade=grade_cn, subject=subject_cn)
    if _learner_ctx:
        system = f"【学生画像与对象意识】\n{_learner_ctx}\n\n" + system
    # v0.43 ⭐ 注册问卷固定提示词（用户专属教学指令，所有模式共用）
    try:
        from prompts import _build_questionnaire_block
        _qq = _build_questionnaire_block(learner)
        if _qq:
            system = f"{_qq}\n\n" + system
    except Exception:
        pass
    # v0.43 ⭐ P1 修复：problem 消费约束掩码（此前 handler 不读）
    try:
        from prompts import _build_constraint_layers
        _cf = getattr(learner, "_constraint_flags", ()) or ()
        if _cf:
            system = f"{_build_constraint_layers(_cf)}\n\n" + system
    except Exception:
        pass
    # v0.66 ⭐ B7 连通性：找答案注入统一资源门面（知识库+Library+联网）
    try:
        from services.library import collect_all_resources
        _uid = str(getattr(learner, "id", "") or "")
        _res = collect_all_resources(_uid, concept, llm=llm, subject=subject,
                                     include_web=True)
        if _res.get("has_any"):
            system += "\n\n【可用资料（解答应基于这些事实）】\n" + _res["block"] + "\n"
    except Exception:
        pass

    user = (
        f"请给我一道{grade_cn}{subject_cn}经典题目。\n"
        + desc_line
        + f"（用户原话：{concept}）"
    )
    answer = _safe_chat(llm, system, user, max_tokens=1500)
    if not answer:
        answer = (f"好，这是一道{grade_cn}{subject_cn}经典题：\n"
                  f"【题目】请证明/求解以下问题（{concept}）……\n"
                  f"（生成失败，请重试）")
    # v0.43 ⭐ P1 修复：problem 语言规范收口 + 问卷注入对齐（此前未过 polish）
    try:
        from services.lang_gate import lang_gate_content as _polish_text  # v0.70+ §3.28 统一入口 L0+L2
        answer = _polish_text(answer, context=f"problem:{concept[:30]}")
    except Exception:
        pass

    return jsonify({
        "session_id": f"prob_{learner.id}",
        "summary": {"avg_score": 0},
        "worldview_used": "weil",
        "tone_ratio": 0,
        "presentations": [
            {"step_id": 1, "content": answer, "step_type": "practice"}
        ],
        "evaluations": [],
        "diagnosis": {},
        "plan": {"steps": [{"type": "practice"}]},
        "reflections": [],
        "learner": {
            "id": learner.id,
            "nickname": learner.nickname,
            "grade_level": learner.grade_level,
            "subjects_mastery": learner.subjects_mastery,
        },
    })
