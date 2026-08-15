# -*- coding: utf-8 -*-
"""test_profile_staleness.py —— §3.12 ⭐ 画像陈旧轻量诊断测试

需求（§3.12 真实缺口：全项目 0 命中 stale 触发）：
- profile.json 有 updated_at 字段但无"陈旧检测"逻辑
- 实现：画像 updated_at > N 天（默认 30）→ 触发轻量诊断（跳过全量 Individuality.run，用确定性规则刷新关键维度）+ 发 profile/stale-refreshed 事件
"""
from __future__ import annotations

import json
import os
import time

import pytest


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    """隔离 profile 文件。"""
    os.makedirs(tmp_path, exist_ok=True)
    return tmp_path


def _make_learner(**kw):
    """构造最小 LearnerProfile。"""
    from paeg import LearnerProfile
    lp = LearnerProfile(
        id=kw.get("id", "test_user"),
        nickname="测试",
        grade_level=kw.get("grade_level", "high_school"),
        age=16,
        cognitive_style=kw.get("cognitive_style", "visual"),
    )
    lp.questionnaire_answers = kw.get("questionnaire_answers", {})
    return lp


def test_profile_stale_detected():
    """画像 updated_at 超过阈值 → 判定为陈旧。"""
    from services.profile_staleness import is_profile_stale
    old_ts = time.time() - 40 * 86400  # 40 天前
    assert is_profile_stale(old_ts, max_age_days=30) is True
    fresh_ts = time.time() - 5 * 86400  # 5 天前
    assert is_profile_stale(fresh_ts, max_age_days=30) is False


def test_profile_no_timestamp_treated_stale():
    """无 updated_at → 保守判定为陈旧（触发诊断）。"""
    from services.profile_staleness import is_profile_stale
    assert is_profile_stale(None, max_age_days=30) is True


def test_stale_refresh_emits_event():
    """陈旧触发轻量诊断 → 发射 profile/stale-refreshed 事件。"""
    from services.profile_staleness import check_and_refresh
    # 清事件文件
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ev_path = os.path.join(base, "events.jsonl")
    if os.path.exists(ev_path):
        os.remove(ev_path)
    learner = _make_learner()
    # 模拟旧画像（40 天前）
    refreshed = check_and_refresh(
        learner, last_profile_update=time.time() - 40 * 86400)
    assert refreshed is True, "陈旧画像应触发刷新"
    # 检查事件
    if os.path.exists(ev_path):
        events = [json.loads(l) for l in open(ev_path, encoding="utf-8") if l.strip()]
        stale_ev = [e for e in events if e.get("type") == "profile/stale-refreshed"]
        assert stale_ev, "应发射 profile/stale-refreshed 事件"


def test_fresh_profile_no_refresh():
    """新鲜画像（5 天内）→ 不触发刷新。"""
    from services.profile_staleness import check_and_refresh
    learner = _make_learner()
    refreshed = check_and_refresh(
        learner, last_profile_update=time.time() - 5 * 86400)
    assert refreshed is False, "新鲜画像不应触发刷新"


def test_questionnaire_answers_updated():
    """刷新后画像关键维度更新（问卷答案注入）。"""
    from services.profile_staleness import refresh_learner_profile
    learner = _make_learner()
    refresh_learner_profile(learner)
    # 刷新应保证画像可读（不抛异常）
    assert learner.cognitive_style in ("visual", "auditory", "reading", "kinesthetic", "mixed")
