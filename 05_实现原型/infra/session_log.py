# -*- coding: utf-8 -*-
"""infra/session_log.py —— H-1 ⭐ SessionEventLog 存储层（§3.46.2 H-1，2026-08-16）

dsh Harness 借鉴（packages/core/session，commit 47f9438）：
- SessionEvent 追加式 JSONL 日志（envelope 由 infra/event_types.make_event 构造）
- seq = 日志长度（连续性契约：append 分配 = 文件已有最大 seq + 1）
- deriveMessages 投影：O(new nodes) 增量折叠（since_seq 参数返回新节点）

分层（§3.37 已完成类型层 + 发射层，本模块补存储层）：
- infra/event_types.py    → SessionEvent envelope + make_event 校验（已存在）
- observability.emit_event_typed → 类型化发射 + trace_id 注入 + JSONL 落盘（已存在）
- infra/session_log.py    → SessionEventLog 类：seq 分配 + events() + derive_messages() + 持久化（本模块）

"模型可见⟺已记录"铁律：模型可见的输入（user/assistant message、tool 调用）
必须经 emit_event_typed 落盘；derive_messages 从日志投影，保证可审计可回放。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from infra.event_types import make_event, SurfaceOp


class SessionEventLog:
    """追加式会话事件日志（JSONL 持久化 + seq 连续性 + 增量投影）。

    线程安全（append/events 均持锁）。seq 从文件已有最大续接，
    支持进程内多次实例化共享同一日志（重启续接）。
    """

    def __init__(self, path: Optional[str] = None):
        if path is None:
            base = Path(__file__).resolve().parent.parent
            path = str(base / "data" / "session_log.jsonl")
        self.path = path
        self._lock = threading.RLock()
        self._seq: int = 0
        self._cache: List[Dict[str, Any]] = []
        self._load()

    # ─────────────────────────────────────
    # 内部：加载 / 落盘
    # ─────────────────────────────────────
    def _load(self) -> None:
        """读取已有 JSONL（容错跳过坏行），初始化 _seq 与 _cache。"""
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        if not os.path.isfile(self.path):
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue  # 坏行跳过（容错）
                if isinstance(ev, dict) and isinstance(ev.get("seq"), int):
                    self._cache.append(ev)
                    if ev["seq"] > self._seq:
                        self._seq = ev["seq"]

    def _append_line(self, ev: Dict[str, Any]) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # ─────────────────────────────────────
    # 核心 API
    # ─────────────────────────────────────
    def append(self, event_type: str, data: dict, *,
               surface_op: Optional[SurfaceOp] = None,
               ignorable: bool = False,
               source_event_seqs: Optional[List[int]] = None) -> int:
        """追加一条事件，返回分配的 seq（= 当前日志长度 + 1）。

        复用 infra/event_types.make_event 校验（未知类型/缺 surfaceOp 抛 ValueError）。
        """
        with self._lock:
            self._seq += 1
            ev = make_event(
                event_type, data,
                seq=self._seq,
                surface_op=surface_op,
                ignorable=ignorable,
                source_event_seqs=source_event_seqs,
            )
            self._cache.append(ev)
            self._append_line(ev)
            return self._seq

    def events(self, since_seq: int = 0) -> List[Dict[str, Any]]:
        """返回 seq > since_seq 的全部事件（按 seq 升序）。"""
        with self._lock:
            return [ev for ev in self._cache if ev.get("seq", 0) > since_seq]

    def derive_messages(self, since_seq: int = 0) -> List[Dict[str, Any]]:
        """投影：返回 since_seq 之后的全部事件（增量折叠）。

        对齐 Harness deriveMessages 语义——模型可见的输入从日志派生，
        保证"模型可见⟺已记录"；调用方用返回的 events 组装上下文。
        """
        return self.events(since_seq=since_seq)

    def count(self) -> int:
        with self._lock:
            return len(self._cache)

    def current_seq(self) -> int:
        with self._lock:
            return self._seq

    def clear(self) -> None:
        """清空日志（测试用；生产路径不调用）。"""
        with self._lock:
            self._cache = []
            self._seq = 0
            if os.path.isfile(self.path):
                try:
                    os.remove(self.path)
                except OSError:
                    pass


# 模块级懒加载单例（infra/runtime.get_session_log 也可用）
_log: Optional[SessionEventLog] = None
_log_lock = threading.Lock()


def get_session_log() -> SessionEventLog:
    """全局懒加载单例（与 infra/runtime 其他单例同模式）。"""
    global _log
    if _log is None:
        with _log_lock:
            if _log is None:
                _log = SessionEventLog()
    return _log


def reset_session_log() -> None:
    """重置单例（测试用）。"""
    global _log
    with _log_lock:
        _log = None


__all__ = ["SessionEventLog", "get_session_log", "reset_session_log"]
