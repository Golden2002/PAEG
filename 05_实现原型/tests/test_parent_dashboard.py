# -*- coding: utf-8 -*-
"""§3.82 C5 家长学情看板测试。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.parent_dashboard import build_dashboard


class FakeConvStore:
    def __init__(self, convs):
        self._convs = convs

    def list_conversations(self, uid):
        return self._convs


def _conv(created, subject="math", mode="teach"):
    return {"id": f"c_{created}", "subject": subject, "mode": mode,
            "created": created, "title": "学习记录"}


def test_dashboard_empty():
    """S1 边界：无数据 → 空统计 + 近 7 日零基线 + 无活动建议。"""
    d = build_dashboard("u1", conv_store=None)
    assert d["conversations_count"] == 0
    assert len(d["daily_trend"]) == 7  # 7 日零基线
    assert all(x["count"] == 0 for x in d["daily_trend"])
    assert any(s["type"] == "inactive" for s in d["suggestions"])


def test_dashboard_with_conversations():
    """S2 主路径：有会话 → 统计 + 学科分布 + 趋势正确。"""
    convs = [
        _conv("2026-08-19T10:00:00", subject="math"),
        _conv("2026-08-19T11:00:00", subject="math"),
        _conv("2026-08-20T09:00:00", subject="physics"),
    ]
    d = build_dashboard("u1", conv_store=FakeConvStore(convs))
    assert d["conversations_count"] == 3
    assert d["subject_distribution"]["math"] == 2
    assert d["subject_distribution"]["physics"] == 1
    # 近 7 日趋势含 2026-08-19/20（假设今天 8-21）
    dates = [x["date"] for x in d["daily_trend"]]
    assert len(dates) == 7
    # 学科集中建议（math 2/3 > 60% 但需 >=3 次）
    assert not any(s["type"] == "narrow_focus" for s in d["suggestions"])


def test_dashboard_narrow_focus():
    """S3 主路径：学科集中 → 拓展建议。"""
    convs = [_conv(f"2026-08-{d:02d}T10:00:00", subject="math") for d in range(15, 21)]
    convs.append(_conv("2026-08-20T11:00:00", subject="physics"))
    d = build_dashboard("u1", conv_store=FakeConvStore(convs))
    # math 6/7 > 60% 且 >=3 → 触发
    assert any(s["type"] == "narrow_focus" for s in d["suggestions"])


def test_dashboard_mastery_low():
    """S4 主路径：掌握度低 → 复习建议。"""
    d = build_dashboard("u1", conv_store=None, profile={"mastery": 0.3})
    assert d["mastery"] == 0.3
    assert any(s["type"] == "low_mastery" for s in d["suggestions"])


def test_dashboard_mastery_ok():
    """S5 边界：掌握度正常 → 无复习建议。"""
    d = build_dashboard("u1", conv_store=None, profile={"mastery": 0.8})
    assert d["mastery"] == 0.8
    assert not any(s["type"] == "low_mastery" for s in d["suggestions"])


def test_dashboard_reflections():
    """S6 主路径：反思数统计。"""
    d = build_dashboard("u1", conv_store=None, reflections=[{"id": 1}, {"id": 2}])
    assert d["reflections_count"] == 2
