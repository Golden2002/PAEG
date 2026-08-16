# -*- coding: utf-8 -*-
"""test_srs_sm2.py — C1 间隔重复 SRS（SM-2 算法）测试。

覆盖：Anki SM-2 核心调度——质量评分 q(0-5) 驱动间隔/重复次数/熟练度更新。
场景：①新卡片首次复习 q=5 → 间隔 1 天 ②答错 q<3 → 重置重复次数 ③连续正确 → 间隔指数增长。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.srs_sm2 import sm2_review


def test_new_card_first_success():
    """新卡片 q=5 → 间隔 1 天，重复 1，easiness 上升。"""
    state = {"interval": 0, "repetition": 0, "easiness": 2.5}
    new = sm2_review(state, 5)
    assert new["interval"] == 1  # 首次成功 → 1 天
    assert new["repetition"] == 1
    assert new["easiness"] > 2.5  # EF 微升


def test_failed_resets_repetition():
    """答错 q<3 → repetition 归零，interval 归 0（重新开始），EF 下调。"""
    state = {"interval": 10, "repetition": 5, "easiness": 2.5}
    new = sm2_review(state, 1)
    assert new["repetition"] == 0
    assert new["interval"] == 0
    assert new["easiness"] < 2.5  # EF 下调


def test_interval_exponential_growth():
    """连续正确 → interval 按 EF 指数增长（1→6→EF*6...）。"""
    state = {"interval": 1, "repetition": 1, "easiness": 2.5}
    new = sm2_review(state, 5)
    assert new["interval"] == 6  # 第二次成功 → 6 天
    assert new["repetition"] == 2
    new2 = sm2_review(new, 5)
    assert new2["interval"] == round(6 * new["easiness"])  # 第三次 → EF*6
    assert new2["repetition"] == 3


def test_easiness_floor():
    """EF 有下限 1.3（Anki 标准）。"""
    state = {"interval": 1, "repetition": 5, "easiness": 1.3}
    new = sm2_review(state, 1)
    assert new["easiness"] >= 1.3


def test_q5_easiness_formula():
    """Anki SM-2 公式：EF' = EF + (0.1 - (5-q)*(0.08+(5-q)*0.02))。"""
    state = {"interval": 0, "repetition": 0, "easiness": 2.5}
    new = sm2_review(state, 5)
    # q=5: EF' = 2.5 + 0.1 = 2.6
    assert abs(new["easiness"] - 2.6) < 1e-9
