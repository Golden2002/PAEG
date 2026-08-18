# -*- coding: utf-8 -*-
"""obs_trace.py —— §3.42 W2 ⭐ observability trace_id 全链路（v1.1.5）

需求（§二 Step 1.5 P1-4 trace_id，借鉴 deepseek-harness session log）：
- begin_trace(name)：chat/teach 入口生成 trace_id（UUID）
- begin_span(name)/end_span(span)：子 span 嵌套（turn/span 粒度）
- get_trace_id()：当前线程的 trace_id（contextvars 线程隔离）
- 事件发射时自动附加 trace_id（emit_event_typed 集成）

ContextVar 保证：跨线程独立、async 任务继承、子 span 嵌套。
"""
from __future__ import annotations

import contextvars
import threading
import uuid
from typing import Optional

# 当前 trace 上下文（线程隔离）
_trace_var: contextvars.ContextVar = contextvars.ContextVar("paeg_trace", default=None)
_lock = threading.Lock()


class _Trace:
    """一次请求/教学会话的追踪上下文。"""

    def __init__(self, name: str):
        self.trace_id: str = f"trc_{uuid.uuid4().hex[:16]}"
        self.name = name
        self.spans: list = []


def begin_trace(name: str) -> str:
    """开启新 trace（chat/teach 入口调用），返回 trace_id。"""
    _t = _Trace(name)
    _trace_var.set(_t)
    return _t.trace_id


def end_trace() -> Optional[str]:
    """结束当前 trace，返回 trace_id（无则 None）。"""
    _t = _trace_var.get()
    if _t is None:
        return None
    _trace_var.set(None)
    return _t.trace_id


def get_trace() -> Optional[_Trace]:
    """返回当前 trace 对象（无则 None）。"""
    return _trace_var.get()


def get_trace_id() -> Optional[str]:
    """返回当前线程 trace_id（无则 None）。"""
    _t = _trace_var.get()
    return _t.trace_id if _t else None


def begin_span(name: str) -> Optional[dict]:
    """开启子 span（turn/agent 粒度），返回 span 对象。"""
    _t = _trace_var.get()
    if _t is None:
        return None
    _span = {
        "span_id": f"spn_{uuid.uuid4().hex[:12]}",
        "parent_id": _t.spans[-1]["span_id"] if _t.spans else None,
        "name": name,
        "trace_id": _t.trace_id,
    }
    _t.spans.append(_span)
    return _span


def end_span(span: Optional[dict]) -> None:
    """结束子 span（从栈中弹出）。"""
    if span is None:
        return
    _t = _trace_var.get()
    if _t is not None and _t.spans:
        _t.spans = [s for s in _t.spans if s.get("span_id") != span.get("span_id")]


__all__ = ["begin_trace", "end_trace", "get_trace", "get_trace_id",
           "begin_span", "end_span"]
