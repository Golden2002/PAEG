# -*- coding: utf-8 -*-
"""test_session_log.py — H-1 SessionEventLog 存储层测试（§3.46.2 H-1）

覆盖：seq 连续性 / derive_messages 增量投影 / envelope 序列化 / 持久化。
类型层（infra/event_types.make_event）与发射层（observability.emit_event_typed）
已存在（§3.37 完成），本测试验证缺失的存储层（infra/session_log.py）。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def log_path(tmp_path):
    return tmp_path / "session_log.jsonl"


@pytest.fixture
def event_log(log_path):
    from infra.session_log import SessionEventLog
    return SessionEventLog(path=str(log_path))


def test_append_creates_sequential_events(event_log):
    """seq 必须连续递增 1,2,3。"""
    s1 = event_log.append("user/message", {"content": "你好"}, surface_op="append")
    s2 = event_log.append("assistant/message", {"content": "你好，同学"}, surface_op="append")
    s3 = event_log.append("tool/call", {"name": "kb_search"})
    assert s1 == 1
    assert s2 == 2
    assert s3 == 3


def test_append_envelope_shape(event_log):
    """envelope 必须含 {seq, type, time, data}，surface 事件带 surfaceOp。"""
    event_log.append("user/message", {"content": "x"}, surface_op="append")
    ev = event_log.events()[-1]
    assert ev["seq"] == 1
    assert ev["type"] == "user/message"
    assert ev["data"]["content"] == "x"
    assert ev["surfaceOp"] == "append"
    assert "time" in ev


def test_derive_messages_incremental(event_log):
    """增量投影：先 2 条 derive → 再 2 条 derive，仅返回新节点。"""
    event_log.append("user/message", {"content": "a"}, surface_op="append")
    event_log.append("assistant/message", {"content": "b"}, surface_op="append")
    first = event_log.derive_messages()  # 全量
    assert len(first) == 2
    assert first[0]["seq"] == 1
    assert first[1]["seq"] == 2
    event_log.append("user/message", {"content": "c"}, surface_op="append")
    event_log.append("assistant/message", {"content": "d"}, surface_op="append")
    incr = event_log.derive_messages(since_seq=2)  # 仅新 2 条
    assert len(incr) == 2
    assert [e["seq"] for e in incr] == [3, 4]
    # 再次增量（无新事件）→ 空
    assert event_log.derive_messages(since_seq=4) == []


def test_events_since_seq(event_log):
    """events(since_seq) 只返回指定 seq 之后的事件。"""
    event_log.append("user/message", {"content": "1"}, surface_op="append")
    event_log.append("user/message", {"content": "2"}, surface_op="append")
    event_log.append("tool/call", {"name": "x"})
    assert len(event_log.events(since_seq=1)) == 2
    assert [e["seq"] for e in event_log.events(since_seq=1)] == [2, 3]


def test_session_log_persists_to_file(event_log, log_path):
    """append → flush → 新实例读回一致（JSONL 持久化）。"""
    event_log.append("user/message", {"content": "你好"}, surface_op="append")
    event_log.append("tool/call", {"name": "kb_search"})
    # 文件已写（append 即落盘）
    assert log_path.exists()
    from infra.session_log import SessionEventLog
    reloaded = SessionEventLog(path=str(log_path))
    evs = reloaded.events()
    assert len(evs) == 2
    assert evs[0]["seq"] == 1
    assert evs[0]["type"] == "user/message"
    assert evs[1]["seq"] == 2
    # seq 续接：新实例 append 从 3 开始
    s3 = reloaded.append("tool/call", {"name": "other"})
    assert s3 == 3


def test_append_rejects_unknown_type(event_log):
    """未知事件类型必须抛 ValueError（对齐 make_event 早失败语义）。"""
    with pytest.raises(ValueError):
        event_log.append("unknown/event", {"x": 1})


def test_surface_event_requires_surface_op(event_log):
    """surface 事件缺 surfaceOp 必须抛 ValueError。"""
    with pytest.raises(ValueError):
        event_log.append("user/message", {"content": "x"})


def test_load_malformed_line_skipped(event_log, log_path):
    """损坏的行跳过不崩（容错）。"""
    event_log.append("user/message", {"content": "ok"}, surface_op="append")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("{this is not json}\n")
    event_log.append("tool/call", {"name": "y"})
    from infra.session_log import SessionEventLog
    reloaded = SessionEventLog(path=str(log_path))
    assert len(reloaded.events()) == 2  # 1 条有效 + 新 1 条，坏行跳过
