# -*- coding: utf-8 -*-
"""test_tool_observability.py —— §3.44 PTC-3 ⭐ 工具调用全貌可观测测试

需求（§3.44 PTC-3，借鉴 dsh"每次调用过程全在 log 里清清楚楚"）：
- 每次工具调用记录：工具名/参数摘要/耗时/缓存命中/结果摘要
- 查询最近 N 次调用全貌
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture
def obs():
    from services.tool_observability import ToolObservability
    return ToolObservability()


def test_record_tool_call(obs):
    """记录工具调用：含工具名/耗时/命中。"""
    obs.record_call("web_search", {"query": "导数"}, duration_ms=120, cache_hit=False)
    calls = obs.recent_calls(limit=10)
    assert len(calls) == 1
    assert calls[0]["tool"] == "web_search"
    assert calls[0]["duration_ms"] == 120
    assert calls[0]["cache_hit"] is False


def test_recent_calls_order(obs):
    """最近调用按时间倒序。"""
    obs.record_call("get_time", {}, duration_ms=5, cache_hit=True)
    time.sleep(0.01)
    obs.record_call("verify_math", {"expr": "x**2"}, duration_ms=80, cache_hit=False)
    calls = obs.recent_calls(limit=5)
    assert calls[0]["tool"] == "verify_math", "最新调用应在最前"


def test_cache_hit_ratio(obs):
    """缓存命中率计算。"""
    for _ in range(3):
        obs.record_call("daily_quote", {}, duration_ms=2, cache_hit=True)
    for _ in range(1):
        obs.record_call("web_search", {"query": "x"}, duration_ms=100, cache_hit=False)
    ratio = obs.cache_hit_ratio()
    assert ratio == 0.75, f"3/4 命中应 75%，实际 {ratio}"


def test_limit_applied(obs):
    """limit 限制返回条数。"""
    for i in range(20):
        obs.record_call("get_time", {}, duration_ms=1, cache_hit=True)
    calls = obs.recent_calls(limit=5)
    assert len(calls) == 5


def test_summary_view(obs):
    """全貌视图：按工具聚合统计。"""
    obs.record_call("web_search", {"query": "a"}, duration_ms=100, cache_hit=False)
    obs.record_call("web_search", {"query": "b"}, duration_ms=200, cache_hit=False)
    summary = obs.summary()
    assert "web_search" in summary, "summary 应含 web_search"
    assert summary["web_search"]["count"] == 2
    assert summary["web_search"]["avg_ms"] == 150
