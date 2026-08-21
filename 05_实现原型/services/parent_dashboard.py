# -*- coding: utf-8 -*-
"""services/parent_dashboard.py —— §3.82 C5 ⭐ 家长学情看板聚合

现状：parent_conversations（会话列表+每日摘要）已有，但缺学情聚合看板。
本模块：聚合会话/反思/掌握度 → 家长可读的学情统计 + 干预建议。

  - build_dashboard(child_uid, conv_store)：会话数/学科分布/近7日趋势/掌握度/反思 + 干预建议
  - 防御式：数据缺失 → 空统计（不抛）；PII 已在端点层脱敏

干预建议规则（教育合规友好）：
  - 近 7 日无学习 → "建议关注孩子近一周学习状态"
  - 单学科占比 >60% → "建议拓展其他学科"
  - 掌握度 <0.4 → "建议回顾薄弱环节"
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def build_dashboard(child_uid: str, conv_store=None,
                    profile=None, reflections=None) -> Dict[str, Any]:
    """聚合家长看板：学情统计 + 趋势 + 干预建议。

    Args:
        child_uid: 孩子用户 ID
        conv_store: 会话存储（get_conversations 接口）
        profile: 学生画像 dict（可选，含掌握度）
        reflections: 反思记录 list（可选）

    Returns: {child_uid, conversations_count, subject_distribution,
              daily_trend(近7日), mastery, reflections_count, suggestions[]}
    """
    out: Dict[str, Any] = {
        "child_uid": child_uid,
        "conversations_count": 0,
        "subject_distribution": {},
        "daily_trend": [],
        "mastery": None,
        "reflections_count": 0,
        "suggestions": [],
    }

    # 1. 会话统计 + 学科分布 + 近 7 日趋势
    convs = []
    if conv_store is not None:
        convs = _safe(lambda: conv_store.list_conversations(str(child_uid)) or [], [])
    if not isinstance(convs, list):
        convs = []
    out["conversations_count"] = len(convs)

    subjects: Counter = Counter()
    daily: Counter = Counter()
    for c in convs:
        if not isinstance(c, dict):
            continue
        subj = str(c.get("subject") or c.get("mode") or "other")
        subjects[subj] += 1
        ts = str(c.get("created") or c.get("ts") or "")
        if ts and len(ts) >= 10:
            daily[ts[:10]] += 1
    out["subject_distribution"] = dict(subjects.most_common(8))
    # 近 7 日趋势
    try:
        import datetime as _dt
        today = _dt.date.today()
        trend = []
        for i in range(6, -1, -1):
            d = (today - _dt.timedelta(days=i)).isoformat()
            trend.append({"date": d, "count": daily.get(d, 0)})
        out["daily_trend"] = trend
    except Exception:
        out["daily_trend"] = []

    # 2. 掌握度（画像）
    if isinstance(profile, dict):
        mastery = profile.get("mastery")
        if mastery is None:
            mastery = profile.get("mastery_avg")
        if isinstance(mastery, (int, float)):
            out["mastery"] = round(float(mastery), 2)

    # 3. 反思记录
    if isinstance(reflections, list):
        out["reflections_count"] = len(reflections)

    # 4. 干预建议（教育合规友好规则）
    s = out["suggestions"]
    total_7d = sum(x["count"] for x in out["daily_trend"])
    if total_7d == 0:
        s.append({"type": "inactive", "severity": "warn",
                  "text": "近 7 日无学习活动，建议关注孩子学习状态"})
    if out["subject_distribution"]:
        top_subj, top_cnt = list(out["subject_distribution"].items())[0]
        if top_cnt >= 3 and top_cnt / max(1, out["conversations_count"]) > 0.6:
            s.append({"type": "narrow_focus", "severity": "info",
                      "text": f"学科集中在「{top_subj}」（{top_cnt}/{out['conversations_count']}），建议拓展其他学科"})
    if isinstance(out["mastery"], float) and out["mastery"] < 0.4:
        s.append({"type": "low_mastery", "severity": "warn",
                  "text": f"掌握度 {out['mastery']} 偏低，建议复习薄弱环节"})
    return out


if __name__ == "__main__":
    import io as _io
    _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import sys
    print(json.dumps(build_dashboard("u1"), ensure_ascii=False))
