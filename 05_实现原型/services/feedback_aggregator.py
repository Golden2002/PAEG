# -*- coding: utf-8 -*-
"""services/feedback_aggregator.py —— §3.81 P1-② ⭐ 备课反馈聚合面板

质量盲区③：`/api/lesson_prep/feedback` 写入 jsonl 即止，用户评分从未回流——
本模块把 jsonl 从"垃圾桶"变"仪表盘"，并支持反哺到 prompt 补丁。

  - aggregate_feedback()：读 memory/lesson_prep_feedback.jsonl → 聚合
      {total, avg_by_dim, low_score_topics, notes_keywords, trend}
  - aggregate_material_judge()：读 evolve_data/material_judge.jsonl → 聚合
      {total, avg_dims, avg_overall, deep_pass_rate}（复用 material_judge.aggregate_judges）
  - feedback_to_prompt_patch()：低分维度/关键词 → 结构化建议（反哺 self_evolution）

防御式：文件缺失/损坏 → 空结构（不抛）；无反馈 → 明确标注"暂无数据"。
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List

# ── 路径 ──
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FEEDBACK_LOG = os.path.join(_PROJ, "memory", "lesson_prep_feedback.jsonl")

# 反馈维度（与 submit_lesson_prep_feedback 契约一致）
DIMS = ("lesson_plan", "handout", "video_script", "ppt_outline", "hard_checks")

# 低分阈值（<3 视为需改进）
_LOW_THRESHOLD = 3


def _read_jsonl(path: str, limit: int = 500) -> List[Dict[str, Any]]:
    """读 jsonl（防御式：损坏行跳过）。"""
    rows = []
    try:
        if not os.path.isfile(path):
            return rows
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return rows[-limit:]


def aggregate_feedback(limit: int = 500) -> Dict[str, Any]:
    """聚合备课人工反馈：维度均分 / 低分主题 / 关键词 / 趋势。"""
    rows = _read_jsonl(_FEEDBACK_LOG, limit)
    if not rows:
        return {"total": 0, "avg_by_dim": {}, "overall": 0.0,
                "low_score_topics": [], "notes_keywords": {}, "trend": []}

    dim_sums: Dict[str, float] = defaultdict(float)
    dim_cnt: Dict[str, int] = defaultdict(int)
    low_topics: List[Dict[str, Any]] = []
    notes_all: List[str] = []
    trend: Dict[str, int] = defaultdict(int)

    for row in rows:
        scores = row.get("scores") or {}
        notes = str(row.get("notes") or "")
        ts = str(row.get("ts") or "")
        date_key = ts[:10] if ts else "unknown"
        trend[date_key] += 1
        if notes:
            notes_all.append(notes)
        row_avg = []
        for dim in DIMS:
            v = scores.get(dim)
            if isinstance(v, (int, float)):
                dim_sums[dim] += float(v)
                dim_cnt[dim] += 1
                row_avg.append(float(v))
        # 低分主题（run_id 级）：任一维度 < 阈值 即标记（不被其他高分稀释）
        _low_dims = {k: v for k, v in scores.items()
                     if isinstance(v, (int, float)) and float(v) < _LOW_THRESHOLD}
        if _low_dims:
            low_topics.append({
                "run_id": row.get("run_id") or "",
                "low_dims": {k: round(float(v), 2) for k, v in _low_dims.items()},
                "scores": {k: v for k, v in scores.items() if isinstance(v, (int, float))},
                "notes": notes[:200],
            })

    avg_by_dim = {d: round(dim_sums[d] / dim_cnt[d], 2) for d in dim_sums if dim_cnt[d]}
    overall = round(sum(dim_sums.values()) / sum(dim_cnt.values()), 2) if dim_cnt else 0.0

    # 关键词提取（简单高频词：中文 2-4 字词频）
    kw_counter: Counter = Counter()
    for n in notes_all:
        # 按常见分隔切分后取 2-4 字片段
        for token in n.replace("，", " ").replace("。", " ").replace("！", " ").split():
            if 2 <= len(token) <= 12 and token not in ("觉得", "感觉", "希望", "有点", "比较"):
                kw_counter[token] += 1
    top_kw = {k: v for k, v in kw_counter.most_common(20) if v >= 1}

    return {
        "total": len(rows),
        "avg_by_dim": avg_by_dim,
        "overall": overall,
        "low_score_topics": low_topics[:10],
        "notes_keywords": top_kw,
        "trend": [{"date": k, "count": v} for k, v in sorted(trend.items())],
    }


def feedback_to_prompt_patch(limit: int = 500) -> Dict[str, Any]:
    """低分反馈 → 结构化 prompt 补丁建议（反哺 self_evolution）。

    输出：{"patches": [{dim, issue, suggestion}], "summary": str}
    """
    agg = aggregate_feedback(limit)
    patches = []
    if not agg["total"]:
        return {"patches": [], "summary": "暂无反馈数据"}

    # 低分维度（均分 <3.5）→ 建议
    for dim, avg in agg["avg_by_dim"].items():
        if avg < 3.5:
            patches.append({
                "dim": dim,
                "avg": avg,
                "issue": f"{dim} 维度均分 {avg}（<3.5）",
                "suggestion": f"在备课 {dim} 生成时强化质量约束（见 §3.81 方案 P0-② 深检）",
            })
    # 高频负面关键词 → 建议
    for kw, cnt in (agg["notes_keywords"] or {}).items():
        if cnt >= 2 and kw in ("慢", "乱", "错", "简单", "重复", "啰嗦"):
            patches.append({
                "dim": "notes",
                "issue": f"反馈关键词「{kw}」出现 {cnt} 次",
                "suggestion": f"检查备课输出是否与「{kw}」相关（低分主题 {len(agg['low_score_topics'])} 个）",
            })
    return {
        "patches": patches[:10],
        "summary": f"{agg['total']} 条反馈，{len(patches)} 条改进建议（overall {agg['overall']}）",
    }


if __name__ == "__main__":
    import io as _io
    _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import sys
    a = aggregate_feedback()
    print("aggregate:", json.dumps(a, ensure_ascii=False)[:400])
