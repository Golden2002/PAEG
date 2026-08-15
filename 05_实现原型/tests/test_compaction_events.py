# -*- coding: utf-8 -*-
"""test_compaction_events.py —— §3.42 W6 ⭐ compaction 4-event 可观测测试

需求（§3.38.2 新模块：context_bundle 压缩生命周期发 4 事件）：
- compaction/start：压缩开始（含 bytes_before + strategy）
- compaction/measure：测量（ratio + pruned_chars）
- compaction/apply：应用压缩（bytes_after + method）
- compaction/end：压缩完成（duration_ms + turns_kept）
- 全部事件带 trace_id（§3.42 W2 trace 全链路）
- 无可压缩内容时静默（不发 4 事件，避免日志噪声）
"""
from __future__ import annotations

import json
import os

import pytest


def _read_events():
    """读 events.jsonl（与 test_trace_id 一致的兼容读取）。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "events.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


@pytest.fixture(autouse=True)
def _clean_events():
    """每个测试前后清理 events.jsonl，避免跨测试污染。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ev_path = os.path.join(base, "events.jsonl")
    backup = None
    if os.path.exists(ev_path):
        with open(ev_path, encoding="utf-8") as f:
            backup = f.read()
        os.remove(ev_path)
    yield
    if backup is not None:
        with open(ev_path, "w", encoding="utf-8") as f:
            f.write(backup)


def _make_history(n_pairs: int) -> list:
    """构造 n_pairs 对 user/assistant 交替历史。"""
    out = []
    for i in range(n_pairs):
        out.append({"role": "user", "content": f"学生问题 {i}: 请讲概念 {i * 7 % 100}"})
        out.append({"role": "assistant", "content": f"讲解 {i}: 概念 {i * 7 % 100} 的定义与例子（较长内容）" * 3})
    return out


# ────────────────────────────────────────────────────────────
# 测试 1：压缩开始事件
# ────────────────────────────────────────────────────────────
def test_compaction_start_emitted():
    """压缩触发时，发 compaction/start（含 bytes_before + strategy）。"""
    from compaction import maybe_compact

    history = _make_history(15)  # 超过 max_pairs=10 触发压缩
    assert len(history) > 20, "需要足够历史触发压缩"
    before_bytes = sum(len(str(m.get("content", ""))) for m in history)

    # 在有 trace 的上下文中执行
    from obs_trace import begin_trace, end_trace
    tid = begin_trace("compaction_test_start")
    try:
        result = maybe_compact(history, llm=None)
    finally:
        end_trace()

    # 验证确实执行了压缩（长度变小）
    assert len(result) < len(history), "应触发压缩"

    # 读事件流验证 compaction/start 出现
    events = _read_events()
    starts = [e for e in events if e.get("type") == "compaction/start"]
    assert starts, "应发射 compaction/start 事件"
    data = starts[-1].get("data", {})
    assert "bytes_before" in data, f"start 应带 bytes_before，实际 {data}"
    assert data["bytes_before"] >= before_bytes, f"bytes_before={data['bytes_before']} 应≥{before_bytes}"
    assert "strategy" in data, f"start 应带 strategy，实际 {data}"


# ────────────────────────────────────────────────────────────
# 测试 2：压缩应用事件
# ────────────────────────────────────────────────────────────
def test_compaction_apply_emitted():
    """应用压缩后，发 compaction/apply（含 bytes_after + ratio）。"""
    from compaction import maybe_compact

    history = _make_history(15)
    before_bytes = sum(len(str(m.get("content", ""))) for m in history)

    from obs_trace import begin_trace, end_trace
    tid = begin_trace("compaction_test_apply")
    try:
        result = maybe_compact(history, llm=None)
    finally:
        end_trace()

    after_bytes = sum(len(str(m.get("content", ""))) for m in result)

    events = _read_events()
    applies = [e for e in events if e.get("type") == "compaction/apply"]
    assert applies, "应发射 compaction/apply 事件"
    data = applies[-1].get("data", {})
    assert "bytes_after" in data, f"apply 应带 bytes_after，实际 {data}"
    assert "ratio" in data, f"apply 应带 ratio，实际 {data}"
    assert data["bytes_after"] <= after_bytes + 200, f"bytes_after={data['bytes_after']} 应≤{after_bytes + 200}"
    # ratio = bytes_after / bytes_before
    if data.get("bytes_before"):
        assert abs(data["ratio"] - data["bytes_after"] / data["bytes_before"]) < 0.01, \
            f"ratio={data['ratio']} 应≈bytes_after/bytes_before"


# ────────────────────────────────────────────────────────────
# 测试 3：压缩结束事件
# ────────────────────────────────────────────────────────────
def test_compaction_end_emitted():
    """压缩完成时，发 compaction/end（含 duration_ms + turns_kept）。"""
    from compaction import maybe_compact

    history = _make_history(15)

    from obs_trace import begin_trace, end_trace
    tid = begin_trace("compaction_test_end")
    try:
        result = maybe_compact(history, llm=None)
    finally:
        end_trace()

    events = _read_events()
    ends = [e for e in events if e.get("type") == "compaction/end"]
    assert ends, "应发射 compaction/end 事件"
    data = ends[-1].get("data", {})
    assert "duration_ms" in data, f"end 应带 duration_ms，实际 {data}"
    assert isinstance(data["duration_ms"], (int, float)), "duration_ms 应为数值"
    assert data["duration_ms"] >= 0, f"duration_ms 应≥0，实际 {data['duration_ms']}"
    assert "turns_kept" in data, f"end 应带 turns_kept，实际 {data}"
    assert data["turns_kept"] >= 0, f"turns_kept 应≥0，实际 {data['turns_kept']}"


# ────────────────────────────────────────────────────────────
# 测试 4：事件携带 trace_id
# ────────────────────────────────────────────────────────────
def test_compaction_events_have_trace_id():
    """压缩 4 事件都带 trace_id（与 begin_trace 关联）。"""
    from compaction import maybe_compact

    history = _make_history(15)

    from obs_trace import begin_trace, end_trace
    tid = begin_trace("compaction_test_trace")
    try:
        result = maybe_compact(history, llm=None)
    finally:
        end_trace()

    events = _read_events()
    compaction_events = [e for e in events if (e.get("type") or "").startswith("compaction/")]
    assert compaction_events, "应有 compaction/* 事件"
    for ev in compaction_events:
        ev_tid = ev.get("data", {}).get("trace_id")
        assert ev_tid == tid, \
            f"{ev.get('type')} 应带 trace_id={tid}，实际 {ev_tid}"


# ────────────────────────────────────────────────────────────
# 测试 5：无压缩时静默（不发 4 事件，避免日志噪声）
# ────────────────────────────────────────────────────────────
def test_no_compaction_no_events():
    """历史不超过阈值时，不发 4 事件（避免日志噪声）。"""
    from compaction import maybe_compact

    # max_pairs=10 → 20 条历史未超阈值，不压缩
    history = _make_history(5)  # 10 条

    from obs_trace import begin_trace, end_trace
    tid = begin_trace("compaction_test_no_op")
    try:
        result = maybe_compact(history, llm=None)
    finally:
        end_trace()

    # 不压缩时应保持原历史（恒等返回）
    assert result == history, "未触发压缩时应原样返回"

    events = _read_events()
    compaction_events = [e for e in events if (e.get("type") or "").startswith("compaction/")]
    assert not compaction_events, \
        f"未压缩时不应发 compaction/* 事件，实际发了 {len(compaction_events)} 条: {[e.get('type') for e in compaction_events]}"