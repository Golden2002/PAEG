# -*- coding: utf-8 -*-
"""services/tool_observability.py —— §3.44 PTC-3 ⭐ 工具调用全貌可观测（v1.1.5）

借鉴 dsh"每次调用过程全在 log 里清清楚楚（用了哪些工具/缓存命中率）"：
- record_call：记录每次工具调用（工具名/参数摘要/耗时/缓存命中/结果摘要）
- recent_calls(limit)：最近调用（倒序）
- cache_hit_ratio()：缓存命中率
- summary()：按工具聚合统计
- 内存环形缓冲（上限 500 条），可扩展为落盘
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional


class ToolObservability:
    """工具调用全貌观测器。"""

    def __init__(self, max_entries: int = 500):
        self._lock = threading.RLock()
        self._calls: Deque[dict] = deque(maxlen=max_entries)

    def record_call(self, tool: str, arguments: dict, *,
                    duration_ms: float = 0.0,
                    cache_hit: bool = False,
                    result_summary: str = "") -> None:
        """记录一次工具调用。

        Args:
            tool: 工具名
            arguments: 参数 dict（记录摘要，防敏感信息）
            duration_ms: 耗时
            cache_hit: 是否缓存命中
            result_summary: 结果摘要（截断）
        """
        entry = {
            "tool": tool,
            "args_summary": str(arguments)[:120],
            "duration_ms": round(duration_ms, 1),
            "cache_hit": bool(cache_hit),
            "result_summary": str(result_summary)[:100],
            "ts": time.time(),
        }
        with self._lock:
            self._calls.append(entry)

    def recent_calls(self, limit: int = 20) -> List[dict]:
        """最近调用（新→旧）。"""
        with self._lock:
            return list(self._calls)[-limit:][::-1]

    def cache_hit_ratio(self) -> float:
        """缓存命中率（无调用 → 0.0）。"""
        with self._lock:
            if not self._calls:
                return 0.0
            hits = sum(1 for c in self._calls if c["cache_hit"])
            return round(hits / len(self._calls), 2)

    def summary(self) -> Dict[str, dict]:
        """按工具聚合统计：count/avg_ms/max_ms/hit_rate。"""
        with self._lock:
            agg: Dict[str, dict] = {}
            for c in self._calls:
                t = c["tool"]
                a = agg.setdefault(t, {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "hits": 0})
                a["count"] += 1
                a["total_ms"] += c["duration_ms"]
                a["max_ms"] = max(a["max_ms"], c["duration_ms"])
                if c["cache_hit"]:
                    a["hits"] += 1
            out = {}
            for t, a in agg.items():
                out[t] = {
                    "count": a["count"],
                    "avg_ms": round(a["total_ms"] / a["count"], 1),
                    "max_ms": round(a["max_ms"], 1),
                    "hit_rate": round(a["hits"] / a["count"], 2),
                }
            return out

    def clear(self) -> None:
        with self._lock:
            self._calls.clear()


# ─── 全局单例 ───
_obs: Optional[ToolObservability] = None
_obs_lock = threading.Lock()


def get_tool_observability() -> ToolObservability:
    """全局单例。"""
    global _obs
    with _obs_lock:
        if _obs is None:
            _obs = ToolObservability()
        return _obs


__all__ = ["ToolObservability", "get_tool_observability"]
