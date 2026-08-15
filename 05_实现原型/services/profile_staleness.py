# -*- coding: utf-8 -*-
"""services/profile_staleness.py —— §3.12 ⭐ 画像陈旧轻量诊断（v1.1.5）

需求（2026-08-15 核实：全项目 0 命中 stale 触发，是 §3.12 真实缺口）：
- profile.json 有 updated_at 字段但无"陈旧检测"逻辑
- 实现：画像 updated_at > N 天（默认 30）→ 触发轻量诊断
  （跳过全量 Individuality.run LLM 调用，用确定性规则刷新关键维度）
  + 发射 profile/stale-refreshed 事件（可观测）

设计：
- is_profile_stale(ts, max_age_days)：陈旧判定（无时间戳保守为 True）
- refresh_learner_profile(learner)：轻量刷新（不调 LLM——确定性规则补全缺失维度）
- check_and_refresh(learner, last_profile_update)：入口——陈旧则刷新 + 发事件
- 接入点：_learner_session.get_or_create_learner（画像加载时检查）
"""
from __future__ import annotations

import time
from typing import Optional

# 默认阈值：30 天未更新视为陈旧
DEFAULT_MAX_AGE_DAYS = int(
    __import__("os").environ.get("PAEG_PROFILE_MAX_AGE_DAYS", "30"))


def is_profile_stale(last_profile_update: Optional[float], max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> bool:
    """画像是否陈旧。

    - 无时间戳 → 保守判定为 True（触发一次诊断刷新）
    - 有时间戳 → 距今 > max_age_days 天 → True
    """
    if last_profile_update is None:
        return True
    age_days = (time.time() - last_profile_update) / 86400
    return age_days > max_age_days


def refresh_learner_profile(learner) -> bool:
    """轻量刷新画像（确定性规则，不调 LLM）。

    与全量 Individuality.run（LLM 建模）的区别：这里只做**确定性兜底**——
    补全缺失的问卷维度（cognitive_style/grade_level），不重新建模。
    返回是否做了实质刷新。
    """
    changed = False
    try:
        # 1. cognitive_style 兜底（问卷答案缺失时用默认）
        qa = getattr(learner, "questionnaire_answers", None) or {}
        q_style = qa.get("学习风格") or qa.get("cognitive_style") or qa.get("learning_style")
        if q_style and getattr(learner, "cognitive_style", None) in (None, "", "unknown"):
            learner.cognitive_style = q_style
            changed = True
        # 2. grade_level 兜底
        q_grade = qa.get("学段") or qa.get("grade_level")
        if q_grade and getattr(learner, "grade_level", None) in (None, "", "unknown"):
            learner.grade_level = q_grade
            changed = True
        # 3. self_description 兜底（问卷"自我描述"）
        q_desc = qa.get("自我描述") or qa.get("self_description")
        if q_desc and not getattr(learner, "self_description", ""):
            learner.self_description = q_desc
            changed = True
    except Exception:
        pass
    return changed


def check_and_refresh(learner, last_profile_update: Optional[float],
                      max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> bool:
    """入口：画像陈旧 → 轻量刷新 + 发事件。

    Returns:
        True 表示触发了刷新（陈旧）；False 表示新鲜（无需刷新）
    """
    if not is_profile_stale(last_profile_update, max_age_days):
        return False
    refresh_learner_profile(learner)
    # 发射事件（可观测性；失败静默不阻塞）
    try:
        from observability import emit_event_typed
        emit_event_typed("profile/stale-refreshed",
                         learner_id=str(getattr(learner, "id", "anon")),
                         age_days=round((time.time() - (last_profile_update or time.time())) / 86400, 1),
                         refresh_mode="deterministic")
    except Exception:
        pass
    return True


__all__ = ["is_profile_stale", "refresh_learner_profile", "check_and_refresh",
           "DEFAULT_MAX_AGE_DAYS"]
