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

# §3.42 W8 ⭐ 长流式会话日志分块批写入（opt-in）
# 默认关闭：PAEG_LOG_CHUNK_ROWS 未设 → 走原 verbatim 路径（ratchet 兼容）
# 启用方式：export PAEG_LOG_CHUNK_ROWS=1（chunk 编码 + 56x 压缩）
# 读侧：infra.log_writer.decode_storage_records() 自动展开 chunk 行
_CHUNK_WRITER = None  # 单例：模块级缓存，避免每次 emit_event 重建
_CHUNK_WRITER_LOAD_FAILED = False  # 单次加载失败后短路，防每次调用都 import 失败


def _chunk_writer_enabled() -> bool:
    """§3.42 W8：检查是否启用 chunk-rows 压缩（默认 False，ratchet 兼容）。"""
    return os.environ.get("PAEG_LOG_CHUNK_ROWS") == "1"


def _get_chunk_writer():
    """懒加载 ChunkWriter 单例（仅启用时构造）。失败一次后短路。"""
    global _CHUNK_WRITER, _CHUNK_WRITER_LOAD_FAILED
    if not _chunk_writer_enabled():
        return None
    if _CHUNK_WRITER is not None:
        return _CHUNK_WRITER
    if _CHUNK_WRITER_LOAD_FAILED:
        return None
    try:
        from infra.log_writer import ChunkWriter
        _CHUNK_WRITER = ChunkWriter(_EVENTS_FILE)
        return _CHUNK_WRITER
    except Exception:
        # 加载失败：记标志位，后续直接走 verbatim（不抛错影响主流程）
        _CHUNK_WRITER_LOAD_FAILED = True
        return None


def emit_event(event_type: str, **payload):
    """写 JSONL 事件（thread/turn/item/tool 等，供测试契约）。

    §3.42 W8 ⭐：当 PAEG_LOG_CHUNK_ROWS=1 时走 ChunkWriter 压缩路径；
    默认关闭时保持原 verbatim 行为（行级兼容）。
    """
    entry = {"ts": time.time(), "type": event_type, **payload}
    # §3.42 W8：chunk-rows 压缩路径（opt-in）
    cw = _get_chunk_writer()
    if cw is not None:
        try:
            cw.append_event(entry)
        except Exception:
            pass
        return
    # 原 verbatim 路径（ratchet：默认行为不变）
    try:
        with open(_EVENTS_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def emit_event_typed(event_type: str, **payload):
    """§3.37 H-1/H-12 ⭐ 类型化事件发射（对齐 Harness SessionEvent envelope）。

    - event_type 必须在 KNOWN_EVENT_TYPES（非法 → ValueError，早失败）
    - surface 事件需带 surface_op='append'
    - §3.42 W2 ⭐ 自动附加当前 trace_id（obs_trace contextvars；无 trace 则为 None）
    - 与 emit_event 同 JSONL 落盘（兼容既有消费方）

    Raises:
        ValueError: 未知事件类型 / surface 事件缺 surface_op
    """
    from infra.event_types import make_event, is_surface_event
    seq = payload.pop("seq", None)
    surface_op = payload.pop("surface_op", None)
    data = payload.pop("data", {})
    if data is None:
        data = {}
    data = dict(data)
    data.update({k: v for k, v in payload.items() if v is not None})
    # §3.42 W2 ⭐ trace_id 注入
    try:
        from obs_trace import get_trace_id
        _tid = get_trace_id()
        if _tid:
            data.setdefault("trace_id", _tid)
    except Exception:
        pass
    ev = make_event(event_type, data, seq=seq, surface_op=surface_op)
    emit_event(ev["type"], seq=ev["seq"], ts=ev["time"] / 1000.0, data=ev["data"])


# ─── v0.26 D1 ⭐ SessionTranscript：课堂记录可回放（学自 Codex JSONL Transcript） ───

_TRANSCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcripts')


def _transcript_path(session_id: str) -> str:
    os.makedirs(_TRANSCRIPT_DIR, exist_ok=True)
    return os.path.join(_TRANSCRIPT_DIR, f"{session_id}.jsonl")


def transcript_append(session_id: str, item_type: str, **payload):
    """写入一条课堂记录（append-only JSONL，grep 友好、可回放）。

    item_type: user_input / diagnosis / plan / presentation / evaluation /
               adaptation / reflection / summary / done / retry(Verify Gate)
    供：学生/教师回看整堂课；debug 按 turn 定位；审计链路真实联通。
    """
    try:
        entry = {
            "ts": time.time(),
            "session_id": session_id,
            "item_type": item_type,
            **payload,
        }
        with open(_transcript_path(session_id), 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def transcript_replay(session_id: str, item_type: Optional[str] = None):
    """回放课堂记录（可过滤 item_type）。"""
    try:
        path = _transcript_path(session_id)
        if not os.path.exists(path):
            return []
        out = []
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if item_type and entry.get("item_type") != item_type:
                    continue
                out.append(entry)
        return out
    except Exception:
        return []


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    log = get_logger("test")
    log.info("self.check", ok=True)
    record_metric("paeg.tool.duration", 123, {"tool": "web_search"})
    emit_event("thread.started", thread_id="thr_test")
    transcript_append("ses_test", "user_input", text="什么是熵？")
    transcript_append("ses_test", "presentation", step_id=1, content="熵是系统混乱度的度量…")
    items = transcript_replay("ses_test")
    print(f"可观测性模块自检 OK（transcript {len(items)} 条）")
