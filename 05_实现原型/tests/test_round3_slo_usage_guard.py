# -*- coding: utf-8 -*-
"""§3.79 D1/C5/E1 第 3 轮测试（2026-08-20 目标模式 Round 3）。

覆盖：
  D1 SLO 分模式指标（services/slo_metrics.py + /api/metrics slo 字段）
  C5 每日使用限制（services/usage_guard.py）+ 家长视图端点
  E1 采纳事件（effect_metrics 读 feedback/record adopted → 采纳率）
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import services.effect_metrics as em
import services.slo_metrics as slo
import services.usage_guard as ug


# ────────────────────────────────────────────
# D1 SLO 分模式指标
# ────────────────────────────────────────────
def test_slo_record_and_summary():
    slo.reset_for_test()
    slo.record_request("teach", 100.0, ok=True)
    slo.record_request("teach", 300.0, ok=True)
    slo.record_request("teach", 500.0, ok=True)
    slo.record_request("teach", 900.0, ok=False)  # 错误
    s = slo.slo_summary()
    assert s["teach"]["count"] == 4
    assert s["teach"]["error_rate"] == 0.25
    assert s["teach"]["p95_ms"] == 900.0  # 4 条 → idx=int(3.8)=3 → 900
    assert s["total"]["count"] == 4
    assert s["total"]["error_rate"] == 0.25
    slo.reset_for_test()


def test_slo_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(slo, "_SLO_FILE", str(tmp_path / "slo.json"))
    slo.reset_for_test()
    slo.record_request("chat", 50.0, ok=True)
    assert slo.persist() is True
    assert (tmp_path / "slo.json").exists()
    slo.reset_for_test()


def test_api_metrics_includes_slo():
    """/api/metrics 含 slo 分模式摘要。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.get_json()
    assert "slo" in body
    assert "total" in body["slo"]


# ────────────────────────────────────────────
# C5 每日使用限制
# ────────────────────────────────────────────
def test_usage_guard_register_and_limit():
    _sess = {}
    assert ug.is_over_limit(_sess, "u_c5") is False
    for _ in range(ug._DEFAULT_LIMIT):
        ug.register_usage(_sess, "u_c5")
    assert ug.is_over_limit(_sess, "u_c5") is True
    _sum = ug.usage_summary(_sess, "u_c5")
    assert _sum["sessions"] == ug._DEFAULT_LIMIT
    assert _sum["over"] is True


def test_usage_guard_custom_limit():
    _sess = {}
    ug.register_usage(_sess, "u_c5b")
    ug.register_usage(_sess, "u_c5b")
    assert ug.is_over_limit(_sess, "u_c5b", limit_sessions=2) is True
    assert ug.is_over_limit(_sess, "u_c5b", limit_sessions=5) is False


def test_usage_guard_day_rollover():
    """跨天自动轮换（同 uid 第二天键不同）。"""
    _sess = {}
    ug.register_usage(_sess, "u_c5c")
    assert ug.usage_summary(_sess, "u_c5c")["sessions"] == 1
    # 模拟次日：手工改键日期
    _k = ug.usage_key("u_c5c")
    _old = _sess[_k]
    _sess[_k.replace(_old["date"], "1999-01-01")] = {"date": "1999-01-01", "sessions": 99}
    assert ug.usage_summary(_sess, "u_c5c")["sessions"] == 1  # 新的一天归零


def test_parent_conversations_endpoint():
    """/api/parent/conversations/<uid> 返回 usage + conversations。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/parent/conversations/u_c5_parent_view")
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    body = r.get_json()
    assert "usage" in body
    assert "conversations" in body
    assert body["usage"]["sessions"] >= 0


def test_parent_conversations_full_preview():
    """/api/parent/conversations/<uid>?full=1 返回消息预览（家长视图）。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/parent/conversations/u_c5_parent_view?full=1")
    assert r.status_code == 200
    body = r.get_json()
    assert "message_preview" in body


# ────────────────────────────────────────────
# E1 采纳事件 → 采纳率
# ────────────────────────────────────────────
def test_self_update_acceptance_with_adopted_events(tmp_path, monkeypatch):
    """有 feedback/record(adopted) 事件 → 采纳率 = adopted/proposals。"""
    monkeypatch.setattr(em, "_PROJ", str(tmp_path))
    _mem = tmp_path / "memory"
    _mem.mkdir(parents=True)
    # 提议：2 条建议
    (_mem / "self_update_suggestions.jsonl").write_text(
        json.dumps({"suggestions": [{"category": "prompt_update"}, {"category": "knowledge_update"}]}) + "\n",
        encoding="utf-8")
    # 采纳事件：1 条 adopted
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"type": "feedback/record", "data": {"kind": "adopted", "target": "knowledge"}}) + "\n",
        encoding="utf-8")
    r = em.compute_self_update_acceptance()
    assert r["proposals"] == 2
    assert r["adopted_events"] == 1
    assert r["value"] == 0.5
    assert r["status"] == "adopted_events"


def test_self_update_acceptance_no_events(tmp_path, monkeypatch):
    """无采纳事件 → None（诚实标注）。"""
    monkeypatch.setattr(em, "_PROJ", str(tmp_path))
    r = em.compute_self_update_acceptance()
    assert r["value"] is None
    assert r["status"] == "needs_adoption_event"
