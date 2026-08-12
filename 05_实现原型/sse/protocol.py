# -*- coding: utf-8 -*-
"""SSE 协议层（v0.49 ⭐ SSE 重构 P1）。

职责：事件序列化（纯函数，零副作用，字节级向后兼容）。
目标：让 teach_stream 的事件产出可独立测试、可复用、可扩展——
后续阶段处理器（P2）与编排器（P4）都基于本层，事件名/data schema 不变。

兼容性铁律（重构 P0 基线验证）：
- 事件行格式：`event: <name>\n`
- 数据行格式：`data: <json.dumps(payload, ensure_ascii=False)>\n\n`
- 与 server.py 既有 yield 输出逐字节一致（前端 SSE 消费契约）
"""
from __future__ import annotations

import json
from typing import Any, Dict


def serialize_event(event_type: str, data: Dict[str, Any]) -> str:
    """序列化一个 SSE 事件（event + data 两行 + 空行）。

    行为与 server.py 既有 `yield f"event: X\\ndata: {json.dumps(d, ensure_ascii=False)}\\n\\n"`
    完全一致（字节级）。data 必须可 JSON 序列化。

    >>> serialize_event("step", {"step_id": 1, "status": "presenting"})
    'event: step\\ndata: {"step_id": 1, "status": "presenting"}\\n\\n'
    """
    return "event: %s\ndata: %s\n\n" % (event_type, json.dumps(data, ensure_ascii=False))


def chunk_content(content: str, size: int = 60) -> list:
    """分片内容（与 server.py 既有 presentation 分片 yield 行为一致）。

    教学讲解按 60 字符分片推送，前端逐步渲染。
    """
    return [content[i:i + size] for i in range(0, len(content), size)] if content else []
