# -*- coding: utf-8 -*-
"""§3.82 B3 OTel 导出测试。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.otel_export import export_telemetry, failure_classification, otlp_json_export


def test_export_empty(monkeypatch):
    """S1 边界：无事件 → 空结构（不崩）。"""
    import services.otel_export as oe
    oe._EVENTS_FILE = "/nonexistent/events.jsonl"
    e = export_telemetry()
    assert e["traces"] == 0
    assert e["events"] == 0


def test_export_traces(monkeypatch):
    """S2 主路径：trace 归组正确。"""
    import services.otel_export as oe
    import tempfile
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "events.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"ts": 1.0, "type": "hook/invoked", "trace_id": "trc_abc"}\n')
        f.write('{"ts": 1.5, "type": "hook/result", "trace_id": "trc_abc"}\n')
        f.write('{"ts": 2.0, "type": "hook/invoked", "trace_id": "trc_def"}\n')
    oe._EVENTS_FILE = p
    e = export_telemetry()
    assert e["traces"] == 2
    assert e["events"] == 3
    assert e["trace_summary"]["trc_abc"]["events"] == 2
    assert e["event_types"]["hook/invoked"] == 2


def test_failure_classification(monkeypatch):
    """S3 主路径：失败分类正确（协议/业务/环境）。"""
    import services.otel_export as oe
    import tempfile
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "events.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"ts": 1, "type": "error", "data": {"msg": "HTTP 500 connection reset"}}\n')
        f.write('{"ts": 2, "type": "error", "data": {"msg": "LLM 返回非 JSON"}}\n')
        f.write('{"ts": 3, "type": "error", "data": {"msg": "rate limit 429 限流"}}\n')
        f.write('{"ts": 4, "type": "hook/invoked", "trace_id": "trc_x"}\n')
    oe._EVENTS_FILE = p
    f = failure_classification()
    assert f["total_error_events"] == 3
    assert f["classification"]["protocol_error"] >= 1
    assert f["classification"]["business_error"] >= 1
    assert f["classification"]["environment_noise"] >= 1


def test_otlp_export(monkeypatch):
    """S4 主路径：OTLP 兼容 JSON 结构。"""
    import services.otel_export as oe
    oe._EVENTS_FILE = "/nonexistent/events.jsonl"
    o = otlp_json_export()
    assert o["resource"]["attributes"][0]["key"] == "service.name"
    assert "scope_metrics" in o
    assert o["failure"]["total_error_events"] == 0
