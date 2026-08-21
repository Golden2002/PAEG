# -*- coding: utf-8 -*-
"""services/adoption_tracker.py —— §3.82 E1 ⭐ 自我更新采纳事件埋点

盲区（effect_metrics 明确注释）：无"采纳/拒绝"事件埋点 → 采纳率不可精确计算。
本模块：promote_to_insights（沙盒转正=采纳）处记录 adoption 事件 → 精确计算采纳率。

设计原则：
  1. append-only 落盘 evolve_data/adoption_events.jsonl（每事件 {ts, source, adopted, content_hash}）
  2. 防御式：写失败不抛（不影响自我进化主流程）
  3. compute_acceptance()：读事件 → 精确采纳率（替代 effect_metrics 的"代理估算"）
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVENTS_LOG = os.path.join(_PROJ, "evolve_data", "adoption_events.jsonl")


def record_adoption(source: str, adopted: bool, content: Optional[str] = None,
                    suggestion_id: Optional[str] = None) -> bool:
    """记录一次自我更新采纳/拒绝事件（append-only）。

    Args:
        source: 事件来源（quality_gate.promote / periodic.weekly / feedback）
        adopted: True=采纳（转正/应用），False=拒绝/弃用
        content: 建议内容（用于 hash 去重，可选）
        suggestion_id: 建议 ID（可选）

    Returns: 是否写入成功
    """
    try:
        import hashlib
        import datetime
        os.makedirs(os.path.dirname(_EVENTS_LOG), exist_ok=True)
        event = {
            "ts": datetime.datetime.now().isoformat(),
            "source": str(source),
            "adopted": bool(adopted),
            "content_hash": hashlib.sha1(str(content or "").encode("utf-8")).hexdigest()[:16]
            if content else "",
            "suggestion_id": str(suggestion_id) if suggestion_id else "",
        }
        with open(_EVENTS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def compute_acceptance(window_days: Optional[int] = None) -> Dict[str, Any]:
    """精确计算自我更新采纳率（读 adoption_events.jsonl）。

    Returns:
        {"total": N, "adopted": N, "rejected": N,
         "acceptance_rate": float|None, "by_source": {...}, "note": str}
    """
    rows: List[Dict[str, Any]] = []
    try:
        if os.path.isfile(_EVENTS_LOG):
            import datetime as _dt
            cutoff = None
            if window_days:
                cutoff = (_dt.datetime.now() - _dt.timedelta(days=window_days)).isoformat()
            with open(_EVENTS_LOG, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if cutoff and str(r.get("ts", "")) < cutoff:
                        continue
                    rows.append(r)
    except Exception:
        pass

    if not rows:
        return {"total": 0, "adopted": 0, "rejected": 0,
                "acceptance_rate": None, "by_source": {}, "note": "暂无采纳事件（需运行自我更新）"}

    adopted = sum(1 for r in rows if r.get("adopted"))
    rejected = len(rows) - adopted
    by_source: Dict[str, Dict[str, int]] = {}
    for r in rows:
        src = str(r.get("source") or "unknown")
        s = by_source.setdefault(src, {"total": 0, "adopted": 0})
        s["total"] += 1
        if r.get("adopted"):
            s["adopted"] += 1

    return {
        "total": len(rows),
        "adopted": adopted,
        "rejected": rejected,
        "acceptance_rate": round(adopted / len(rows), 2) if rows else None,
        "by_source": by_source,
        "note": "精确事件计数（§3.82 E1 埋点）",
    }


if __name__ == "__main__":
    import io as _io
    _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import sys
    ok = record_adoption("quality_gate.promote", True, "测试洞察")
    print("record_adoption:", ok)
    print("compute_acceptance:", compute_acceptance())
