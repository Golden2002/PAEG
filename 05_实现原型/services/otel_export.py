# -*- coding: utf-8 -*-
"""services/otel_export.py —— §3.82 B3 ⭐ OTel 导出（trace 全链路 + 失败分类）

现状：trace_id 已贯穿 observability（L162-181），但无导出端点/失败分类统计。
本模块：
  - export_telemetry()：聚合 events.jsonl 的 trace 事件 → 按 trace_id 归组（全链路）
  - failure_classification()：按错误类型统计（协议错 vs 业务错 vs 环境）
  - otlp_json_export()：输出 OTLP 兼容 JSON（可接入标准看板/收集器）

设计原则：只读聚合（不埋新点）；防御式（文件缺失 → 空）；无外部依赖（纯 JSON）。
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVENTS_FILE = os.path.join(_PROJ, "events.jsonl")


def _read_events(limit: int = 5000) -> List[Dict[str, Any]]:
    rows = []
    try:
        if not os.path.isfile(_EVENTS_FILE):
            return rows
        with open(_EVENTS_FILE, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return rows[-limit:]


def export_telemetry(limit: int = 5000) -> Dict[str, Any]:
    """OTel 导出：trace 全链路聚合（按 trace_id 归组）+ 服务统计。

    Returns:
        {"traces": N, "events": N, "trace_summary": {trace_id: {events, first_ts, last_ts}},
         "event_types": {type: count}, "services": ["paeg-server"]}
    """
    events = _read_events(limit)
    trace_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"events": 0, "first_ts": None, "last_ts": None})
    event_types: Counter = Counter()
    for ev in events:
        tid = str(ev.get("trace_id") or "")
        etype = str(ev.get("type") or "unknown")
        ts = ev.get("ts")
        event_types[etype] += 1
        if tid:
            t = trace_map[tid]
            t["events"] += 1
            if t["first_ts"] is None or (ts is not None and ts < t["first_ts"]):
                t["first_ts"] = ts
            if t["last_ts"] is None or (ts is not None and ts > t["last_ts"]):
                t["last_ts"] = ts
    return {
        "traces": len(trace_map),
        "events": len(events),
        "trace_summary": dict(trace_map),
        "event_types": dict(event_types.most_common(20)),
        "services": ["paeg-server"],
        "export_format": "otlp-json-1.0-compatible",
    }


def failure_classification(limit: int = 5000) -> Dict[str, Any]:
    """失败分类统计：协议错 vs 业务错 vs 环境噪声。

    按 events.jsonl 中的 error/异常 事件归类：
      - protocol_error：HTTP/网络/序列化（协议层）
      - business_error：业务逻辑异常（LLM 返回空/校验失败/评分失败）
      - environment_noise：限流/超时/依赖缺失（环境）
      - unknown：无法归类
    """
    events = _read_events(limit)
    classes: Dict[str, int] = Counter()
    samples: Dict[str, List[str]] = defaultdict(list)
    _ERR_KEYWORDS = {
        "protocol_error": ["500", "connection", "socket", "http", "parse", "json decode", "reset"],
        "business_error": ["校验失败", "评分失败", "返回空", "无返回", "非 json", "非JSON", "not json", "schema", "失败"],
        "environment_noise": ["rate limit", "限流", "429", "timeout", "超时", "dependency", "依赖"],
    }
    for ev in events:
        etype = str(ev.get("type") or "")
        data = ev.get("data") or {}
        text = f"{etype} {json.dumps(data, ensure_ascii=False)[:300]}"
        if "error" not in etype.lower() and "exception" not in etype.lower() and "失败" not in text and "Error" not in text:
            continue
        cls = "unknown"
        for c, kws in _ERR_KEYWORDS.items():
            if any(k.lower() in text.lower() for k in kws):
                cls = c
                break
        classes[cls] += 1
        if len(samples[cls]) < 3:
            samples[cls].append(text[:150])
    return {
        "total_error_events": sum(classes.values()),
        "classification": dict(classes),
        "samples": dict(samples),
    }


def otlp_json_export(limit: int = 5000) -> Dict[str, Any]:
    """OTLP 兼容导出（resource + scope + metrics 摘要）。"""
    tel = export_telemetry(limit)
    fail = failure_classification(limit)
    return {
        "resource": {
            "attributes": [{"key": "service.name", "value": {"stringValue": "paeg-server"}}],
        },
        "scope_metrics": [{
            "scope": {"name": "paeg.observability"},
            "metrics": [
                {"name": "paeg.traces.total", "data": {"asInt": tel["traces"]}},
                {"name": "paeg.events.total", "data": {"asInt": tel["events"]}},
                {"name": "paeg.errors.protocol", "data": {"asInt": fail["classification"].get("protocol_error", 0)}},
                {"name": "paeg.errors.business", "data": {"asInt": fail["classification"].get("business_error", 0)}},
                {"name": "paeg.errors.environment", "data": {"asInt": fail["classification"].get("environment_noise", 0)}},
            ],
        }],
        "trace_summary": tel["trace_summary"],
        "failure": fail,
    }


if __name__ == "__main__":
    import io as _io
    _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import sys
    print(json.dumps(export_telemetry(limit=200), ensure_ascii=False)[:500])
