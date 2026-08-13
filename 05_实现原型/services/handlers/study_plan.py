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
    # v0.68+ ⭐ 根治：附录段（### 推荐学习资料）是确定性渲染的元数据，
    # polish 的 refiner LLM 改写可能误删——先提取附录，polish 正文，再拼回附录。
    _summary_full = _plan.summary_md
    _appendix = ""
    _marker = "### 推荐学习资料"
    if _marker in _summary_full:
        _idx = _summary_full.find(_marker)
        _appendix = _summary_full[_idx:]          # 提取附录段（含标题）
        _summary_body = _summary_full[:_idx].rstrip()  # 正文（阶段内容）
    else:
        _summary_body = _summary_full
    try:
        from services.polish import _polish_text
        _summary = _polish_text(_summary_body, context=f"study_plan:{_plan.topic[:30]}")
    except Exception:
        _summary = _summary_body
    if _appendix:
        _summary = _summary.rstrip() + "\n\n" + _appendix  # 拼回附录（永不被 polish 误删）

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

    # v0.68+ ⭐ 推荐资料附录：从 _plan._raw_blk 提取 4 路（供前端卡片渲染）
    _resources = _extract_resources(getattr(_plan, "_raw_blk", None))

    return {
        "plan_id": _plan.plan_id,
        "topic": _plan.topic,
        "subject": _plan.subject,
        "total_weeks": _plan.total_weeks,
        "weekly_hours": _plan.weekly_hours,
        "deadline": _plan.deadline,
        "phases": [__phase_to_dict(p) for p in _plan.phases],
        "personalization_notes": _plan.personalization_notes,
        "resources": _resources,       # v0.68+ ⭐ 推荐学习资料（4 路）
        "summary_md": _summary,
        "created_at": _plan.created_at,
        "actions": _actions,
    }


def _extract_resources(raw_blk) -> list:
    """从 collect_all_resources 原始块提取 4 路推荐资料（确定性，不调 LLM）。"""
    _blk = raw_blk or {}
    _out = []
    _sections = [
        ("user_library", "📁 你的资料库", "user_assets"),
        ("kb", "📘 知识库", "kb_hits"),
        ("facts", "📄 事实资料", "facts"),
        ("web", "🌐 网络检索", "web_hits"),
    ]
    for _src, _label, _key in _sections:
        _txt = str(_blk.get(_key) or "").strip()
        if not _txt:
            continue
        _out.append({
            "source": _src,
            "label": _label,
            "title": _txt[:200],
            "snippet": _txt[:200] + ("…" if len(_txt) > 200 else ""),
        })
    return _out


def __phase_to_dict(phase):
    from dataclasses import asdict
    _d = asdict(phase)
    return _d


__all__ = ["_handle_study_plan_request"]
