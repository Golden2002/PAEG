# -*- coding: utf-8 -*-
"""test_log_writer.py —— §3.42 W8 ⭐ 长流式会话日志 chunk-rows 压缩测试

需求（§3.42 W8，借鉴 deepseek-harness packages/core/session/src/chunk-rows.ts）：
- 长流式教学会话日志用分块批处理替代逐事件写行
- 同类事件（同 session_id + 同 event_type）连续 → 合并为单行 chunk row
- 压缩目标 ~56x（deepseek-harness 实测）
- 默认关闭（opt-in 通过 PAEG_LOG_CHUNK_ROWS=1），启用后 events.jsonl 落盘采用 chunked 编码
- 读侧 decode_storage_records() 自动展开 chunk 行 → 原始事件序列（行级兼容）
- 崩溃中断：已 flush 的 chunk rows 仍可在磁盘上解码；未 flush 的 buffer 自然丢失（不破坏已落盘数据）

TDD：先写 RED，本文件应全部失败（infra.log_writer 模块尚未存在）。
"""
from __future__ import annotations

import json
import os
import time

import pytest


# ─────────────────────────────────────────────────────────────────
# 共用 fixture：每个测试拿独立 tmp_path（不污染 events.jsonl）
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
def log_path(tmp_path):
    """返回 tmp 下的 JSONL 文件路径（每个测试独立）。"""
    return str(tmp_path / "events.jsonl")


def _read_lines(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.strip():
                out.append(line)
    return out


# ─────────────────────────────────────────────────────────────────
# T1: 同类连续事件 → 合并为单行（chunk）
# ─────────────────────────────────────────────────────────────────


def test_chunk_writer_batches(log_path):
    """§3.42 W8 T1：连续同类事件 → flush 后合并为单行 chunk row。

    RED 断言：
    - 写入 3 个 (session_id='ses_1', event_type='tool-workflow/run-start') 事件
    - flush() 后磁盘上恰好 1 行
    - 该行是 chunk row（_chunk=True, count=3, 含 data0/data_last 边界）
    """
    from infra.log_writer import ChunkWriter

    cw = ChunkWriter(log_path)
    try:
        cw.append_event({"ts": 1000.0, "type": "tool-workflow/run-start",
                         "seq": 0, "data": {"session_id": "ses_1", "agent": "planner"}})
        cw.append_event({"ts": 1000.1, "type": "tool-workflow/run-start",
                         "seq": 1, "data": {"session_id": "ses_1", "agent": "diagnostor"}})
        cw.append_event({"ts": 1000.2, "type": "tool-workflow/run-start",
                         "seq": 2, "data": {"session_id": "ses_1", "agent": "evaluator"}})
        cw.flush()
    finally:
        cw.close()

    lines = _read_lines(log_path)
    assert len(lines) == 1, f"期望 1 行 chunk row，实际 {len(lines)} 行"
    rec = json.loads(lines[0])
    assert rec.get("_chunk") is True, "应标记为 chunk row"
    assert rec["session_id"] == "ses_1"
    assert rec["event_type"] == "tool-workflow/run-start"
    assert rec["count"] == 3, f"期望 count=3，实际 {rec['count']}"
    # 边界：首/末事件 data 应保留（replay/查询用）
    assert rec["data0"]["agent"] == "planner"
    assert rec["data_last"]["agent"] == "evaluator"
    # 时间窗口：start_ts / end_ts
    assert rec["start_ts"] == 1000.0
    assert rec["end_ts"] == 1000.2


# ─────────────────────────────────────────────────────────────────
# T2: 10 万条同类事件流 → 行数 ≤ 1/56 原量
# ─────────────────────────────────────────────────────────────────


def test_chunk_writer_compression_ratio(log_path):
    """§3.42 W8 T2：10 万条同类合成事件 → 磁盘行数 ≤ 100000 / 56 ≈ 1786 行。

    100000 个 (ses_big, assistant/chunk) 事件：
    - 全同类连续 → 应 pack 成 MAX_RUN 大小的块
    - 期望行数：100000 / MAX_RUN ≤ 1786
    - 强约束：实际行数 ≤ 2000（证明压缩生效）
    """
    from infra.log_writer import ChunkWriter

    cw = ChunkWriter(log_path)
    try:
        for i in range(100_000):
            cw.append_event({
                "ts": 1000.0 + i * 0.001,  # 1ms 步进
                "type": "assistant/chunk",
                "seq": i,
                "data": {"session_id": "ses_big", "text": f"t{i}"},
            })
    finally:
        cw.close()  # close 内含 flush

    line_count = len(_read_lines(log_path))
    target = 100_000 / 56  # = 1785.71...
    # 主断言：≤ 1/56
    assert line_count <= target, (
        f"压缩率不足：期望 ≤ {target:.0f} 行，实际 {line_count} 行 "
        f"（压缩比 {100000 / line_count:.1f}x，目标 ≥ 56x）"
    )
    # 强约束：实际确实压缩（防 off-by-one / 没启用的退化情形）
    assert line_count <= 2000, f"强压缩断言失败：{line_count} 行（应 ≤ 2000）"

    # 验证 chunk row 内容确实保留了 count
    rec = json.loads(_read_lines(log_path)[0])
    assert rec.get("_chunk") is True
    assert rec["count"] > 1, "chunk 应含多个（验证 pack 生效）"


# ─────────────────────────────────────────────────────────────────
# T3: 崩溃中断后可重放
# ─────────────────────────────────────────────────────────────────


def test_chunk_writer_replayable(log_path):
    """§3.42 W8 T3：崩溃中断后可重放（已 flush 的 chunk rows 在磁盘上可解码）。

    模拟崩溃：
    1. 写入 1000 个同类事件
    2. flush() 落盘部分 chunk rows
    3. 不 close()，丢弃剩余 buffer（模拟进程崩溃）
    4. 重新读取 events.jsonl：已 flush 的 chunk rows 必须能 100% 解码为原始事件
    5. 解码出的事件数量 ≥ 已 flush 的 chunk rows 总 count
    """
    from infra.log_writer import ChunkWriter, decode_storage_records

    cw = ChunkWriter(log_path)
    # 写 1000 个事件（MAX_RUN=1000 时整个 buffer 会 pack 成 1 chunk row）
    for i in range(1000):
        cw.append_event({
            "ts": 2000.0 + i * 0.001,
            "type": "assistant/chunk",
            "seq": i,
            "data": {"session_id": "ses_r", "text": str(i)},
        })
    # flush（落盘 1 个 chunk row，含 1000 个事件）
    cw.flush()
    # 不 close() — 模拟崩溃（in-memory 部分自然丢失）

    # 重新读取 + 解码
    events = list(decode_storage_records(open(log_path, encoding="utf-8")))
    # 所有解码出的事件都不应再有 _chunk 标记（已被展开）
    assert all(not e.get("_chunk") for e in events), (
        "decoder 应展开 chunk rows，不应残留 _chunk 标记"
    )
    # 已 flush 的 1000 个事件应能完整解码
    assert len(events) == 1000, (
        f"已 flush 的 1000 个事件应全部可解码，实际 {len(events)} 个"
    )
    # 验证首末事件边界
    assert events[0]["seq"] == 0
    assert events[-1]["seq"] == 999
    assert events[0]["data"]["text"] == "0"
    assert events[-1]["data"]["text"] == "999"


# ─────────────────────────────────────────────────────────────────
# T4: 按 session_id 查询结果不变
# ─────────────────────────────────────────────────────────────────


def test_chunk_writer_query_preserved(log_path):
    """§3.42 W8 T4：按 session_id 查询结果不变（decode 展开后过滤语义不变）。

    写入两个 session 的混合事件流（各 200 条同类连续事件），展开后按
    session_id 过滤应得到与原始序列等长、seq 单调的结果。
    """
    from infra.log_writer import ChunkWriter, decode_storage_records

    cw = ChunkWriter(log_path)
    try:
        # session A: 200 条同类连续事件
        for i in range(200):
            cw.append_event({
                "ts": 3000.0 + i * 0.001,
                "type": "tool/call",
                "seq": i,
                "data": {"session_id": "ses_A", "tool": "planner", "n": i},
            })
        # session B: 200 条同类连续事件
        for i in range(200):
            cw.append_event({
                "ts": 4000.0 + i * 0.001,
                "type": "tool/call",
                "seq": i,
                "data": {"session_id": "ses_B", "tool": "evaluator", "n": i},
            })
    finally:
        cw.close()

    # 展开后过滤
    events = list(decode_storage_records(open(log_path, encoding="utf-8")))
    ses_a = [e for e in events if e.get("data", {}).get("session_id") == "ses_A"]
    ses_b = [e for e in events if e.get("data", {}).get("session_id") == "ses_B"]

    assert len(ses_a) == 200, f"ses_A 应有 200 条，实际 {len(ses_a)}"
    assert len(ses_b) == 200, f"ses_B 应有 200 条，实际 {len(ses_b)}"

    # seq 应分别单调递增
    seqs_a = [e["seq"] for e in ses_a]
    seqs_b = [e["seq"] for e in ses_b]
    assert seqs_a == list(range(200)), f"ses_A seq 应为 0..199，实际 {seqs_a[:5]}...{seqs_a[-5:]}"
    assert seqs_b == list(range(200)), f"ses_B seq 应为 0..199，实际 {seqs_b[:5]}...{seqs_b[-5:]}"

    # ts 单调递增（A 的 ts < B 的 ts）
    assert ses_a[0]["ts"] < ses_b[0]["ts"], "A 应早于 B"


# ─────────────────────────────────────────────────────────────────
# 辅助测试：MIN_RUN 边界（< MIN_RUN 时 verbatim 落盘）
# ─────────────────────────────────────────────────────────────────


def test_chunk_writer_min_run_boundary(log_path):
    """MIN_RUN 以下的事件不被 pack，逐条 verbatim 落盘（保证可见性）。

    ratchet 设计：少于 3 个事件不打包（envelope 大小与原始相当，无收益）。
    """
    from infra.log_writer import ChunkWriter

    cw = ChunkWriter(log_path)
    try:
        # 只写 2 个事件（< MIN_RUN=3）
        cw.append_event({"ts": 5000.0, "type": "tool/call", "seq": 0,
                         "data": {"session_id": "ses_x", "tool": "web"}})
        cw.append_event({"ts": 5000.1, "type": "tool/call", "seq": 1,
                         "data": {"session_id": "ses_x", "tool": "kb"}})
    finally:
        cw.close()

    lines = _read_lines(log_path)
    assert len(lines) == 2, f"MIN_RUN 以下应 verbatim（2 行），实际 {len(lines)} 行"
    for ln in lines:
        rec = json.loads(ln)
        assert "_chunk" not in rec, "verbatim 事件不应含 _chunk 标记"


# ─────────────────────────────────────────────────────────────────
# 辅助测试：默认关闭（PAEG_LOG_CHUNK_ROWS 未设）时 observability 走原逻辑
# ─────────────────────────────────────────────────────────────────


def test_chunk_writer_disabled_by_default(monkeypatch, tmp_path):
    """ratchet 铁律：默认不启用压缩（events.jsonl 行为不变）。

    monkeypatch 隔离环境变量，确保 emit_event 默认走 verbatim 路径。
    """
    monkeypatch.delenv("PAEG_LOG_CHUNK_ROWS", raising=False)

    # 把 observability 内部的 _EVENTS_FILE 重定向到 tmp（不动项目原文件）
    monkeypatch.setattr("observability._EVENTS_FILE", str(tmp_path / "events.jsonl"))
    # 也清掉 singleton chunk writer（防顺序依赖）
    monkeypatch.setattr("observability._CHUNK_WRITER", None)

    from observability import emit_event

    emit_event("turn/start", seq=1, data={"session_id": "ses_d", "x": 1})
    emit_event("turn/start", seq=2, data={"session_id": "ses_d", "x": 2})
    emit_event("turn/start", seq=3, data={"session_id": "ses_d", "x": 3})

    lines = _read_lines(str(tmp_path / "events.jsonl"))
    assert len(lines) == 3, f"默认应 verbatim（3 行），实际 {len(lines)} 行"
    for ln in lines:
        rec = json.loads(ln)
        assert "_chunk" not in rec, "默认关闭时不应出现 chunk row"