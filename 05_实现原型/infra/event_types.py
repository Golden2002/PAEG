# -*- coding: utf-8 -*-
"""infra/event_types.py —— §3.37 H-1/H-12 ⭐ Session Event Log 类型化（v1.1.1）

Harness 模式（packages/core/session/src/types.ts + known-event-types.ts，commit 47f9438）：
- SessionEvent envelope：{type, seq, time, data, ignorable?, surfaceOp?, sourceEventSeqs?}
- seq = 事件日志长度（连续性契约）
- 类型化：type 必须是 KNOWN_EVENT_TYPES 之一（discriminated union over Literal）
- surface 事件（user/message、assistant/message、tool/result）必须带 surfaceOp：
  'append' | {op:'replace', start, end}（compaction 用）
- ignorable: true 标记未知插件事件可安全跳过

与 observability.emit_event 兼容：本模块提供类型化的 emit_event_typed()。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional, Union


# ─────────────────────────────────────
# 事件类型表（对齐 Harness KNOWN_SESSION_EVENT_TYPES 43 项，取 PAEG 相关子集）
# ─────────────────────────────────────

# 核心事件（13）
CORE_EVENT_TYPES = frozenset({
    "turn/start", "turn/end",
    "step/start", "step/end",
    "user/message", "assistant/chunk", "assistant/message",
    "tool/call", "tool/result",
    "todo/write", "request/header", "request/context",
    "session/end-seed",
})

# 插件事件（Harness 28 项中 PAEG 已引入的）
PLUGIN_EVENT_TYPES = frozenset({
    "agent-preset/selected", "agent/inbox/spliced",
    "approval/asked", "approval/decided", "approval/policy",
    "command/done", "command/run",
    "compaction/start", "compaction/measure", "compaction/apply",
    "compaction/end", "compaction/summary", "compaction/prune",
    "feedback/record", "goal/change",
    "hook/invoked", "hook/result",
    "llm/retry", "llm/retry-started",
    "permission/preset", "plan/mode", "sandbox/mode", "schedule/change",
    "session/title", "session/title-llm-request",
    "subagent/descriptor",
    "tool-workflow/agent-end", "tool-workflow/agent-start",
    "tool-workflow/run-end", "tool-workflow/run-start",
    "tool/code-dispatch", "tool/code-dispatch-start",
})

# PAEG 自有事件（教学闭环）
PAEG_EVENT_TYPES = frozenset({
    "teach/diagnosis", "teach/plan", "teach/presentation",
    "teach/evaluation", "teach/adaptation", "teach/reflection",
    "material/handout", "material/script", "material/ppt", "material/mindmap",
    "self/evolve", "self/distill", "self/tool-lesson",
    "profile/stale-refreshed",  # §3.12 ⭐ 画像陈旧轻量诊断触发
})

KNOWN_EVENT_TYPES = CORE_EVENT_TYPES | PLUGIN_EVENT_TYPES | PAEG_EVENT_TYPES

# surface 事件（必须带 surfaceOp）
SURFACE_EVENT_TYPES = frozenset({"user/message", "assistant/message", "tool/result"})

# 事件类型 Literal（供类型提示）
EventType = Literal[tuple(sorted(KNOWN_EVENT_TYPES))]  # type: ignore[valid-type]

# SurfaceOp：'append' | {op:'replace', start, end}
SurfaceOp = Union[Literal["append"], Dict[str, Any]]

# SessionEvent envelope
SessionEvent = Dict[str, Any]


# ─────────────────────────────────────
# 构造与校验
# ─────────────────────────────────────

def is_known_event_type(event_type: str) -> bool:
    return event_type in KNOWN_EVENT_TYPES


def make_event(event_type: str, data: dict, *,
               seq: Optional[int] = None,
               surface_op: Optional[SurfaceOp] = None,
               ignorable: bool = False,
               source_event_seqs: Optional[List[int]] = None,
               _now: Optional[float] = None) -> SessionEvent:
    """构造带校验的 SessionEvent envelope（对齐 Harness append 校验语义）。

    Raises:
        ValueError: 未知事件类型 / surface 事件缺 surfaceOp / 非 surface 事件带 surfaceOp
    """
    if not is_known_event_type(event_type):
        raise ValueError(
            f"未知事件类型: {event_type!r}（可用类型见 KNOWN_EVENT_TYPES，"
            f"共 {len(KNOWN_EVENT_TYPES)} 个）")
    if event_type in SURFACE_EVENT_TYPES:
        if surface_op is None:
            raise ValueError(f"surface 事件 {event_type} 必须带 surfaceOp（append 或 replace）")
        if isinstance(surface_op, dict) and surface_op.get("op") not in ("replace",):
            raise ValueError(f"surfaceOp 非法: {surface_op}（仅支持 append 或 {{op:replace,...}}）")
    elif surface_op is not None:
        raise ValueError(f"非 surface 事件 {event_type} 不允许带 surfaceOp")

    ev: SessionEvent = {
        "type": event_type,
        "seq": seq if seq is not None else -1,  # 调用方负责分配（seq=log.length）
        "time": int((_now if _now is not None else time.time()) * 1000),
        "data": data or {},
    }
    if surface_op is not None:
        ev["surfaceOp"] = surface_op
    if ignorable:
        ev["ignorable"] = True
    if source_event_seqs:
        ev["sourceEventSeqs"] = source_event_seqs
    return ev


def is_surface_event(event_type: str) -> bool:
    return event_type in SURFACE_EVENT_TYPES


__all__ = [
    "KNOWN_EVENT_TYPES", "CORE_EVENT_TYPES", "PLUGIN_EVENT_TYPES",
    "PAEG_EVENT_TYPES", "SURFACE_EVENT_TYPES", "EventType", "SurfaceOp",
    "SessionEvent", "is_known_event_type", "make_event", "is_surface_event",
]
