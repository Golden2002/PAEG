# -*- coding: utf-8 -*-
"""services/slo_metrics.py —— §3.79 D1 ⭐ SLO 分模式指标（P95 延迟/错误率/token 成本）

总需求 D1：商业化 SLO 四指标基础（P95 延迟 / 错误率 / token 成本 / eval pass rate）。
本模块负责**请求级**分模式指标（教学/对话/知识/倾诉/查资料/备课等模式）：

  - record_request(mode, duration_ms, ok, tokens)：记录一次请求
  - slo_summary()：按模式聚合 count/avg/P95/error_rate/tokens + 总体
  - persist()：落盘 data/slo.json（保留最近记录，运维可查）

与 observability.record_metric（工具级指标）互补：本模块是**端点级** SLO 视图。
接线：server.py before_request/after_request（§3.79）。
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from typing import Any, Dict, List

_SLO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_SLO_FILE = os.path.join(_SLO_DIR, "slo.json")

# mode → 累计
_SLO: Dict[str, dict] = defaultdict(lambda: {
    "count": 0, "durations_ms": [], "errors": 0, "tokens": 0,
})


def record_request(mode: str, duration_ms: float, ok: bool = True,
                   tokens: int = 0) -> None:
    """记录一次请求（防御式：异常不抛）。

    Args:
        mode: 教学/对话/知识/倾诉等模式名（server 按 path 归并）
        duration_ms: 请求耗时（毫秒）
        ok: 是否成功（HTTP < 500 视为成功）
        tokens: 本次请求 LLM token 消耗（暂无埋点传 0，LLM 适配器埋点为下轮）
    """
    try:
        _m = _SLO[str(mode or "other")]
        _m["count"] += 1
        _m["durations_ms"].append(max(0.0, float(duration_ms)))
        _m["durations_ms"] = _m["durations_ms"][-2000:]  # 内存上限（滚动窗口）
        if not ok:
            _m["errors"] += 1
        _m["tokens"] += int(tokens or 0)
    except Exception:
        pass


def _p95(vals: List[float]) -> float:
    if not vals:
        return 0.0
    _s = sorted(vals)
    _idx = min(len(_s) - 1, int(len(_s) * 0.95))
    return round(_s[_idx], 1)


def slo_summary() -> Dict[str, Any]:
    """按模式聚合 SLO 摘要（/api/metrics 扩展数据源）。"""
    _out: Dict[str, Any] = {}
    _total = {"count": 0, "durations_ms": [], "errors": 0, "tokens": 0}
    for _mode, _m in sorted(_SLO.items()):
        _err_rate = round(_m["errors"] / max(1, _m["count"]), 4)
        _out[_mode] = {
            "count": _m["count"],
            "avg_ms": round(sum(_m["durations_ms"]) / max(1, len(_m["durations_ms"])), 1),
            "p95_ms": _p95(_m["durations_ms"]),
            "error_rate": _err_rate,
            "tokens": _m["tokens"],
        }
        _total["count"] += _m["count"]
        _total["durations_ms"].extend(_m["durations_ms"])
        _total["errors"] += _m["errors"]
        _total["tokens"] += _m["tokens"]
    _out["total"] = {
        "count": _total["count"],
        "avg_ms": round(sum(_total["durations_ms"]) / max(1, len(_total["durations_ms"])), 1),
        "p95_ms": _p95(_total["durations_ms"]),
        "error_rate": round(_total["errors"] / max(1, _total["count"]), 4),
        "tokens": _total["tokens"],
    }
    # §3.79 D1 ⭐ token 成本：LLM 适配器 record_metric("paeg.llm.tokens") 汇总
    # （适配器无 mode 上下文，token 按总量计入 total；分模式 token 归因为下轮）
    try:
        from observability import _metrics as _obs_metrics
        _tok_list = _obs_metrics.get("paeg.llm.tokens") or []
        _tok_sum = int(sum(float(m.get("value") or 0) for m in _tok_list))
        _out["total"]["tokens"] = _tok_sum
        _out["total"]["llm_calls"] = len(_tok_list)
    except Exception:
        pass
    return _out


def persist() -> bool:
    """落盘 data/slo.json（保留模式摘要 + 时间戳）。"""
    try:
        os.makedirs(_SLO_DIR, exist_ok=True)
        with open(_SLO_FILE, "w", encoding="utf-8") as _fh:
            json.dump({"summary": slo_summary(), "ts": time.time()},
                      _fh, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def reset_for_test() -> None:
    """测试隔离：清空内存指标。"""
    _SLO.clear()


__all__ = ["record_request", "slo_summary", "persist", "reset_for_test"]
