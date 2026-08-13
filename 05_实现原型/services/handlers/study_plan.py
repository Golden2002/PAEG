# -*- coding: utf-8 -*-
"""v0.68 ⭐ services/handlers/study_plan.py —— 学习计划端点处理器

method 模式的"制定学习计划"子流程。is_study_plan_intent 命中时，
由 method.py 分流到本处理器：调用 services/planner.py 工作流生成学习计划，
包装为 method 标准响应（presentations + study_plan 结构化字段 + actions 按钮）。

范式对齐 method.py：函数体内 import（避免循环）、返回 dict、语言规范收口。
"""
from __future__ import annotations


def _handle_study_plan_request(learner, topic: str, subject: str = "",
                               deadline: str = "", llm=None) -> dict:
    """生成学习计划。返回 dict（供 method.py 合并进标准响应）。

    参数：
      learner   — LearnerProfile（画像：学段/掌握度/自述/问卷）
      topic     — 用户输入（如"我想学习生命现象学，该怎么样入门"）
      subject   — 学科
      deadline  — 可选截止日期（原始字符串，planner 内部解析）
    """
    from services.planner import build_study_plan
    from infra.runtime import get_llm

    _llm = llm or get_llm()
    # 合并 deadline 到输入（若用户在请求中给了期限）
    _text = topic or ""
    if deadline and deadline.strip():
        _text = f"{_text}，{deadline.strip()}内完成"

    _plan = build_study_plan(_text, learner, subject=subject, llm=_llm)

    # 语言规范收口（复用现有 L2/L3）
    _summary = _plan.summary_md
    try:
        from services.polish import _polish_text
        _summary = _polish_text(_summary, context=f"study_plan:{_plan.topic[:30]}")
    except Exception:
        pass

    # actions：前端可点按钮（开始学习 → teach 模式）
    _actions = []
    if _plan.phases:
        _first_m = _plan.phases[0].milestones[0] if _plan.phases[0].milestones else None
        if _first_m:
            _actions.append({
                "label": f"开始阶段 1 学习：{_first_m.title}",
                "kind": "teach",
                "payload": {"concept": _first_m.title, "subject": _plan.subject,
                            "milestone_id": _first_m.id},
            })
    _actions.append({"label": "保存到我的计划", "kind": "save_plan",
                     "payload": {"plan_id": _plan.plan_id}})

    return {
        "plan_id": _plan.plan_id,
        "topic": _plan.topic,
        "subject": _plan.subject,
        "total_weeks": _plan.total_weeks,
        "weekly_hours": _plan.weekly_hours,
        "deadline": _plan.deadline,
        "phases": [__phase_to_dict(p) for p in _plan.phases],
        "personalization_notes": _plan.personalization_notes,
        "summary_md": _summary,
        "created_at": _plan.created_at,
        "actions": _actions,
    }


def __phase_to_dict(phase):
    from dataclasses import asdict
    _d = asdict(phase)
    return _d


__all__ = ["_handle_study_plan_request"]
