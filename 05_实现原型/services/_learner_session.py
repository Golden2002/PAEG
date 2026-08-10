"""_learner_session.py — PAEG server 中获取/创建 LearnerProfile 的单一来源。

v0.42 重构提取：原 server.py 中 13 处完全相同的内联实现合并到
`ensure_learner_session`，调用点变为单行，行为 100% 等价。

原 13 处位置（v0.41.6 行号，仅作 history 追溯参考）:
    L738  /api/teach           (elif self_description 更新 + target_exam/specialty_target)
    L1091 /api/teach_stream    (无 elif)
    L2013 /api/profile GET     (持久化字典源 + subjects_mastery)
    L2044 /api/profile GET     (完全硬编码默认 — fallback 路径)
    L2084 /api/profile PUT     (默认昵称"学习者")
    L2582 /api/generate        (无 elif)
    L2711 /api/generate        (省略 cognitive_style kwarg → 用 LearnerProfile 默认 'visual')
    L2821 /api/chat_stream     (elif self_description 更新)
    L3324 /api/chat            (elif self_description 更新)
    L4007 /api/method          (无 elif)
    L4062 /api/knowledge       (无 elif)
    L4114 /api/affection       (无 elif)

调用点差异由 kwargs 显式表达，不靠隐式默认 → 静态阅读即知行为。
"""
from __future__ import annotations

from typing import Any, Optional


def ensure_learner_session(
    learner_id: str,
    data: dict,
    SESSIONS: dict,
    *,
    from_persistent_dict: Optional[dict] = None,
    default_nickname: str = "学生",
    with_target_exam: bool = False,
    with_subjects_mastery: bool = False,
    update_self_description_if_present: bool = False,
) -> Any:
    """获取或创建 `LearnerProfile`，缓存进 `SESSIONS`，按需同步 self_description。

    行为完全等价原 v0.41.6 内联 13 处。

    参数
    ----
    learner_id : str
        学习者 ID（u_ 实名 / web_ 匿名 都接受）。
    data : dict
        当前 HTTP 请求 JSON（`request.get_json(force=True)`）。作为字段源。
        也用于 `update_self_description_if_present=True` 时的 self_description 同步。
    SESSIONS : dict
        模块级 SESSIONS 单例（避免本函数对全局变量隐式依赖）。
    from_persistent_dict : dict | None
        持久化画像字典（GET /api/profile 用）。提供时作为字段源
        覆盖 `data`；其余字段仍回退硬编码默认。
    default_nickname : str
        缺省昵称。profile_update 默认 "学习者"，其余 12 处均 "学生"。
    with_target_exam : bool
        是否注入 target_exam / specialty_target。L738(=True) + 持久化路径。
        L2013 持久化路径靠 `from_persistent_dict` 已经隐式支持
        (src.get("target_exam") 仍然会拿到值) — 实际上 L2013 也
        设 True 才与原代码 100% 一致 (见下方注释)。
    with_subjects_mastery : bool
        是否注入 subjects_mastery。仅 L2013 持久化路径。
    update_self_description_if_present : bool
        若 learner 已存在于 SESSIONS，是否在 `data` 提供 self_description
        时同步覆盖。L738/L2821/L3324 显式有此 elif 分支 → True。

    返回
    ----
    LearnerProfile 实例（已写入 SESSIONS）。
    """
    # 懒加载：与原内联 `from paeg import LearnerProfile` 时机一致，
    # 避免 paeg 包冷启动开销。
    from paeg import LearnerProfile

    # 字段源优先序：persistent > data > 硬编码默认。
    # 注意：`from_persistent_dict` 优先于 `data`，对应 L2013 的用法：
    # 该处从 USER_STORE 加载持久画像，不读 HTTP body。
    src = from_persistent_dict if from_persistent_dict is not None else (data or {})

    cache_key = f"learner_{learner_id}"
    learner = SESSIONS.get(cache_key)
    if not learner:
        # v0.41.7 ⭐ 稳定性根治：请求未带 nickname 时，注册用户（u+数字）
        # 从 USER_STORE 根昵称兜底，而不是落到默认"学生"——防止 SESSIONS
        # 重建时用默认值覆盖用户真实昵称（曾导致 u106 画像回退"学生"）。
        _nickname = src.get("nickname") or ""
        if not _nickname and str(learner_id)[:1] == "u" and str(learner_id)[1:].isdigit():
            try:
                from infra.runtime import get_user_store
                _us = get_user_store()
                _u = _us.get_user(learner_id) if _us is not None else None
                if _u:
                    _nickname = (_u.get("nickname") or "").strip()
            except Exception:
                _nickname = ""
        # === 13 处共有字段 ===
        # cognitive_style 显式传 "visual" 默认（= LearnerProfile 内部默认）
        # 与 L2711 原代码省略 kwarg 行为完全等价（默认值一样）。
        kwargs = dict(
            id=src.get("id", learner_id),
            nickname=_nickname or src.get("nickname", default_nickname),
            grade_level=src.get("grade_level", "high_school"),
            age=src.get("age", 17),
            cognitive_style=src.get("cognitive_style", "visual"),
            self_description=src.get("self_description", ""),
        )
        if with_target_exam:
            # L738 / PUT 路径用：data 提供时再传。
            kwargs["target_exam"] = src.get("target_exam")
            kwargs["specialty_target"] = src.get("specialty_target")
        if with_subjects_mastery:
            # L2013 持久化用：缺省 {}。
            kwargs["subjects_mastery"] = src.get("subjects_mastery") or {}
        learner = LearnerProfile(**kwargs)
        SESSIONS[cache_key] = learner
    elif update_self_description_if_present:
        # 对应 L738 / L2821 / L3324 三处的 elif 分支。
        if data.get("self_description") is not None:
            learner.self_description = data["self_description"]
    return learner
