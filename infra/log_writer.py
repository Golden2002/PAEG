# -*- coding: utf-8 -*-
"""infra/log_writer.py —— §3.42 W8 ⭐ 长流式会话日志 chunk-rows 压缩（v1.1.5）

需求（§3.42 W8，借鉴 deepseek-harness packages/core/session/src/chunk-rows.ts）：
- 长流式教学会话日志用**分块批处理**替代逐事件写行
- 同类事件（同 session_id + 同 event_type）连续 → 合并为单行 chunk row
- 压缩目标：~56x（deepseek-harness 实测）
- 默认关闭（opt-in 通过 PAEG_LOG_CHUNK_ROWS=1）
- 读侧 decode_storage_records() 自动展开 chunk 行 → 原始事件序列（行级兼容）
- 崩溃中断：已 flush 的 chunk rows 仍可在磁盘上解码；未 flush 的 buffer 自然丢失

设计要点：
- **ratchet**：默认不启用（PAEG_LOG_CHUNK_ROWS 未设）→ observability.emit_event 走原 verbatim 路径
- **按 (session_id, event_type) 分组**：每组一个 in-memory buffer
- **MIN_RUN = 3**：低于此值不打包（envelope 与原始相当，无收益）
- **MAX_RUN = 1000**：单 chunk 最多 1000 事件（dt 数组可控 / 崩溃损失有界）
- **时间窗口 boundary**：相邻事件 > 60s 视为新 run（防止 buffer 跨长会话无限增长）
- **flush() 强制 pack**：剩余 buffer 立即落盘（close() 自动调用）
- **线程安全**：RLock 守护 buffer + 文件写入
- **逐行 atomic**：每条 JSONL 行独立写入；半行 chunk row 不存在（解码安全）
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict
from typing import Dict, Iterator, List, Optional, Tuple


# ────────────────────────────────────────────────────────────────
# 常量
# ────────────────────────────────────────────────────────────────

# 至少 N 个连续同类事件才打包（低于此值 envelope 与 N 行原始相当，无收益）
MIN_RUN: int = 3

# 单 chunk 最多 N 个事件（dt 数组长度上限 = N-1）
MAX_RUN: int = 1000

# 时间窗口 boundary（秒）：相邻事件跨度 > 此值视为新 run
TIME_BOUNDARY_S: float = 60.0

# 默认 anon session bucket（事件无 session_id 时归入此组）
_ANON_SESSION: str = "_anon"


# ────────────────────────────────────────────────────────────────
# session_id 提取（兼容多种 PAEG 事件形态）
# ────────────────────────────────────────────────────────────────


def _extract_session_id(event: dict) -> str:
    """从事件 dict 提取 session_id（用于 chunk 分组键）。

    优先级：
    1. event["session_id"]（顶层）
    2. event["data"]["session_id"]
    3. event["data"]["workflow_id"]（PAEG 命名 ses_xxx-yyy 模式）
    4. event["data"]["learner_id"]（兜底，标 learner: 前缀防混淆）
    5. _ANON_SESSION（最终兜底）
    """
    sid = event.get("session_id")
    if sid:
        return str(sid)
    data = event.get("data")
    if isinstance(data, dict):
        sid = data.get("session_id")
        if sid:
            return str(sid)
        wid = data.get("workflow_id")
        if wid and isinstance(wid, str) and wid.startswith("ses"):
            return wid
        lid = data.get("learner_id")
        if lid:
            return f"learner:{lid}"
    return _ANON_SESSION


# ────────────────────────────────────────────────────────────────
# ChunkRow 构造 & 展开
# ────────────────────────────────────────────────────────────────


def _build_chunk_row(key: Tuple[str, str], events: List[dict]) -> dict:
    """把 ≥ MIN_RUN 个同类事件打包为一个 chunk row（storage record）。

    Schema:
        _chunk: True                      # chunk row 标记（读侧 discriminator）
        session_id: str                   # 分组键 1
        event_type: str                   # 分组键 2
        seq0: int                         # 首个事件 seq
        ts0: float                        # 首个事件 ts（epoch 秒）
        count: int                        # 事件总数
        first_seq: int                    # = seq0
        last_seq: int                     # 末事件 seq
        start_ts: float                   # = ts0（边界 marker）
        end_ts: float                     # 末事件 ts（边界 marker）
        dt: List[float]                   # 相邻 ts 间隔（len = count-1）
        data0: dict                       # 首事件 data（边界）
        data_last: dict                   # 末事件 data（边界）
        ts_written: float                 # 落盘时刻（epoch 秒）
    """
    session_id, event_type = key
    first = events[0]
    last = events[-1]
    ts0 = float(first.get("ts", 0.0))
    end_ts = float(last.get("ts", ts0))
    seq0 = int(first.get("seq", 0))
    last_seq = int(last.get("seq", seq0 + len(events) - 1))
    dt: List[float] = []
    for i in range(1, len(events)):
        prev_ts = float(events[i - 1].get("ts", ts0))
        cur_ts = float(events[i].get("ts", ts0))
        dt.append(cur_ts - prev_ts)
    return {
        "_chunk": True,
        "session_id": session_id,
        "event_type": event_type,
        "seq0": seq0,
        "ts0": ts0,
        "count": len(events),
        "first_seq": seq0,
        "last_seq": last_seq,
        "start_ts": ts0,
        "end_ts": end_ts,
        "dt": dt,
        "data0": first.get("data", {}) or {},
        "data_last": last.get("data", {}) or {},
        "ts_written": time.time(),
    }


def _expand_chunk_row(row: dict) -> Iterator[dict]:
    """把 chunk row 展开为原始事件序列（按 log 顺序）。

    设计：
    - 每个事件保留 type / ts / seq（构造或从边界推）
    - 每个事件的 data 携带 session_id（保证按 session_id 查询可用）
    - 首/末事件保留完整 data（data0 / data_last）；中间事件 data 只含 session_id
      （足够按 session_id 查询；详细 payload 不重要时此压缩损失可接受）
    """
    session_id = row["session_id"]
    event_type = row["event_type"]
    seq0 = int(row["seq0"])
    ts0 = float(row["ts0"])
    count = int(row["count"])
    dt: List[float] = list(row.get("dt", []))
    data0 = row.get("data0", {}) or {}
    data_last = row.get("data_last", {}) or {}

    cur_ts = ts0
    cur_seq = seq0
    for k in range(count):
        if k > 0:
            cur_ts = cur_ts + dt[k - 1]
            cur_seq = cur_seq + 1
        if k == 0:
            data = dict(data0)
            data.setdefault("session_id", session_id)
        elif k == count - 1:
            data = dict(data_last)
            data.setdefault("session_id", session_id)
        else:
            # 中间事件：data 只含 session_id（按组查询足够）
            data = {"session_id": session_id}
        yield {
            "ts": cur_ts,
            "type": event_type,
            "seq": cur_seq,
            "data": data,
        }


# ────────────────────────────────────────────────────────────────
# 解码器（公开 API：读侧兼容）
# ────────────────────────────────────────────────────────────────


def decode_storage_records(lines) -> Iterator[dict]:
    """把混合的 JSONL 行（chunk rows + verbatim events）展开为原始事件流。

    Args:
        lines: iterable of JSONL 行字符串（已 strip 换行符或未 strip 均可）

    Yields:
        原始事件 dict（无 _chunk 标记）。chunk rows 已被展开成 N 个事件。
    """
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            # 坏行：跳过（与 observability.transcript_replay 兼容）
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("_chunk") is True:
            try:
                yield from _expand_chunk_row(rec)
            except Exception:
                # chunk row 解码失败：跳过（不破坏整文件）
                continue
        else:
            yield rec


# ────────────────────────────────────────────────────────────────
# ChunkWriter（公开 API：写侧）
# ────────────────────────────────────────────────────────────────


class ChunkWriter:
    """§3.42 W8 ⭐ 长流式会话日志分块批写入器。

    Usage:
        cw = ChunkWriter("/path/to/events.jsonl")
        cw.append_event({"ts": ..., "type": "tool/call", "seq": 0,
                         "data": {"session_id": "ses_1", ...}})
        ...
        cw.close()  # flush + close

    设计要点（与 deepseek-harness chunk-rows.ts 对齐 + 适配 PAEG）：
    - 按 (session_id, event_type) 分组缓冲
    - MIN_RUN 以下逐条 verbatim 落盘（保证小流量也可见）
    - MIN_RUN..MAX_RUN 之间：留 buffer 等 flush()/close() / boundary 触发 pack
    - MAX_RUN 处：强制 pack（防止 buffer 无限增长）
    - 时间跨度 > TIME_BOUNDARY_S：视为新 run，先 flush 旧的
    - close() 强制 flush 全部 buffer
    - 线程安全：RLock 守护 buffer + 文件写入
    """

    def __init__(self, path: str, *,
                 min_run: int = MIN_RUN,
                 max_run: int = MAX_RUN,
                 time_boundary_s: float = TIME_BOUNDARY_S):
        if min_run < 1:
            raise ValueError(f"min_run 必须 >= 1，实际 {min_run}")
        if max_run < min_run:
            raise ValueError(f"max_run ({max_run}) 必须 >= min_run ({min_run})")
        self.path = path
        self.min_run = min_run
        self.max_run = max_run
        self.time_boundary_s = time_boundary_s
        self._lock = threading.RLock()
        # 按 (session_id, event_type) 分组 buffer
        self._buffers: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
        self._file = None
        self.records_written: int = 0  # 测试用：累计落盘行数
        self.events_buffered: int = 0  # 测试用：累计入队事件数

    # ─── 内部：文件 & flush ───

    def _open(self) -> None:
        """惰性打开追加文件（RLock 内调用）。"""
        if self._file is None:
            # 确保父目录存在
            parent = os.path.dirname(os.path.abspath(self.path))
            if parent and not os.path.exists(parent):
                try:
                    os.makedirs(parent, exist_ok=True)
                except Exception:
                    pass
            self._file = open(self.path, "a", encoding="utf-8")

    def _flush_key_unlocked(self, key: Tuple[str, str]) -> None:
        """flush 一个分组的 buffer（RLock 内调用）。

        - buffer < min_run → 逐条 verbatim 落盘（保证小流量可见）
        - buffer >= min_run → 打包为单行 chunk row 落盘
        """
        buf = self._buffers.get(key)
        if not buf:
            return
        if len(buf) < self.min_run:
            # 不打包：逐条 verbatim
            for ev in buf:
                self._file.write(json.dumps(ev, ensure_ascii=False) + "\n")
                self.records_written += 1
        else:
            # 打包为 chunk row
            row = _build_chunk_row(key, buf)
            self._file.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.records_written += 1
        self._buffers[key] = []

    def _flush_all_unlocked(self) -> None:
        """flush 所有分组 buffer（RLock 内调用）。"""
        # 用 list() 防止迭代中字典被修改
        for key in list(self._buffers.keys()):
            self._flush_key_unlocked(key)

    # ─── 公开 API ───

    def append_event(self, event: dict) -> None:
        """入队一个事件字典（{ts, type, seq, data, ...}）。

        - 触发 boundary（与上一个同 key 事件时间跨度 > time_boundary_s）→ flush 旧 buffer
        - buffer >= max_run → 强制 pack
        - 否则：留 buffer 等 flush()/close()
        """
        if not isinstance(event, dict):
            raise TypeError(f"event 必须是 dict，实际 {type(event).__name__}")
        with self._lock:
            self._open()
            session_id = _extract_session_id(event)
            event_type = event.get("type", "")
            key = (session_id, event_type)
            # Boundary check：与上一个同 key 事件时间跨度
            buf = self._buffers.get(key)
            if buf:
                last_ts = float(buf[-1].get("ts", 0.0))
                new_ts = float(event.get("ts", last_ts))
                if (new_ts - last_ts) > self.time_boundary_s:
                    self._flush_key_unlocked(key)
                    buf = None
            buf = self._buffers.setdefault(key, [])
            buf.append(event)
            self.events_buffered += 1
            # 触发 pack：buffer 满 → 立即 flush
            if len(buf) >= self.max_run:
                self._flush_key_unlocked(key)

    def flush(self) -> int:
        """把所有未 pack 的 buffer 强制 flush 到磁盘。返回 flush 的行数。"""
        with self._lock:
            if self._file is None and not self._buffers:
                return 0
            self._open()
            before = self.records_written
            self._flush_all_unlocked()
            try:
                self._file.flush()
            except Exception:
                pass
            return self.records_written - before

    def close(self) -> None:
        """flush 所有 buffer + 关闭文件句柄。"""
        with self._lock:
            try:
                if self._file is not None or self._buffers:
                    self._open()
                    self._flush_all_unlocked()
                    try:
                        self._file.flush()
                    except Exception:
                        pass
            finally:
                if self._file is not None:
                    try:
                        self._file.close()
                    except Exception:
                        pass
                    self._file = None

    # ─── 上下文管理器 ───

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ─── 统计 / 调试 ───

    def stats(self) -> dict:
        """返回当前 writer 状态（用于 debug / 健康检查）。"""
        with self._lock:
            buffered_by_key = {
                f"{sid}|{et}": len(buf) for (sid, et), buf in self._buffers.items()
            }
            return {
                "records_written": self.records_written,
                "events_buffered": self.events_buffered,
                "buffered_groups": len(self._buffers),
                "buffered_by_key": buffered_by_key,
                "path": self.path,
            }


__all__ = [
    "ChunkWriter",
    "decode_storage_records",
    "MIN_RUN", "MAX_RUN", "TIME_BOUNDARY_S",
    "_extract_session_id", "_build_chunk_row", "_expand_chunk_row",
]