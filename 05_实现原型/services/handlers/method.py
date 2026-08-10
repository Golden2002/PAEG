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

    user = f"学生问：{concept}\n{desc_line}请给出{subject_cn}的学习方法建议。"
    answer = _safe_chat(llm, system, user, max_tokens=1400)
    if not answer:
        answer = (f"关于怎么学{subject_cn}，我的建议是：先从最基础的概念建立直觉，"
                  f"再通过做典型例题巩固，最后用错题复盘查漏补缺。具体方法我可以展开讲。")

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
