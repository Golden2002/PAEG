# -*- coding: utf-8 -*-
"""
PAEG 可观测性（v0.21 ⭐ Observability）

借鉴 opencode telemetry + Codex 事件流：
- 结构化日志（key=value，grep-friendly）
- 核心指标（工具耗时/会话 token/成本）
- 事件流（JSONL，供测试契约）

用法：
    from observability import get_logger, record_metric
    log = get_logger("server")
    log.info("tool.execute.after", tool="web_search", duration_ms=120)
    record_metric("paeg.tool.duration", 120, {"tool": "web_search"})
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from typing import Any, Dict, Optional


class PaegLogger:
    """结构化日志（key=value，无敏感信息）。"""

    def __init__(self, name: str):
        self.name = name

    def _emit(self, level: str, event: str, **kv):
        parts = [f"level={level}", f"event={event}", f"logger={self.name}"]
        for k, v in kv.items():
            parts.append(f"{k}={v}")
        print(f"[PAEG] {' '.join(parts)}")

    def info(self, event: str, **kv):
        self._emit("INFO", event, **kv)

    def debug(self, event: str, **kv):
        self._emit("DEBUG", event, **kv)

    def warn(self, event: str, **kv):
        self._emit("WARN", event, **kv)

    def error(self, event: str, **kv):
        self._emit("ERROR", event, **kv)


_loggers: Dict[str, PaegLogger] = {}


def get_logger(name: str) -> PaegLogger:
    if name not in _loggers:
        _loggers[name] = PaegLogger(name)
    return _loggers[name]


# ─── 指标（轻量内存计数器 + 落盘 JSON） ───

_metrics: Dict[str, list] = defaultdict(list)
_METRICS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'metrics.json')


def record_metric(name: str, value: float, labels: Optional[Dict[str, Any]] = None):
    """记录一条指标（带时间戳和标签）。"""
    _metrics[name].append({
        "value": value,
        "ts": time.time(),
        "labels": labels or {},
    })
    # 每 100 条落盘一次
    if len(_metrics[name]) >= 100:
        _flush_metrics()


def _flush_metrics():
    try:
        with open(_METRICS_FILE, 'w', encoding='utf-8') as f:
            json.dump({k: v[-100:] for k, v in _metrics.items()}, f,
                      ensure_ascii=False, indent=1)
    except Exception:
        pass


def metric_stats(name: str) -> Dict[str, float]:
    """指标统计（count/avg/max）。"""
    vals = [m["value"] for m in _metrics.get(name, [])]
    if not vals:
        return {"count": 0}
    return {"count": len(vals), "avg": round(sum(vals) / len(vals), 2), "max": max(vals)}


def all_metric_stats() -> Dict[str, Dict[str, float]]:
    return {k: metric_stats(k) for k in _metrics}


# ─── 事件流（JSONL，供测试契约） ───

_EVENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events.jsonl')


def emit_event(event_type: str, **payload):
    """写 JSONL 事件（thread/turn/item/tool 等，供测试契约）。"""
    entry = {"ts": time.time(), "type": event_type, **payload}
    try:
        with open(_EVENTS_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    log = get_logger("test")
    log.info("self.check", ok=True)
    record_metric("paeg.tool.duration", 123, {"tool": "web_search"})
    emit_event("thread.started", thread_id="thr_test")
    print("可观测性模块自检 OK")
