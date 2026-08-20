# -*- coding: utf-8 -*-
"""services/effect_metrics.py —— §3.79 ⭐ 效果指标测量管道（总需求 E1 TOP-1 落地）

设计指标（04_最终设计/PAEG最终设计_v3.1 §10 长期指标）：
  学习者坚持率（30 天）≥ 0.7 / 知识保留率（30 天）≥ 0.6 /
  元认知准确率 ≥ 0.7 / 自我更新采纳率 ≥ 0.5

管道：数据文件（transcripts / users_data / evolve_data / memory）→ 聚合（本模块）
      → 端点 /api/metrics/effects → 月报导出 data/effects/effect_report_YYYY-MM.{json,md}

原则：
  1. 只读聚合——不依赖新埋点即可产出（埋点增强为下轮：采纳事件/自我评估事件）
  2. 数据不足的指标返回 None + reason（诚实标注，不编造达标）
  3. 全部防御式（文件缺失/损坏 → 跳过不抛）
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────
# 路径与工具
# ─────────────────────────────────────
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _p(*parts: str) -> str:
    return os.path.join(_PROJ, *parts)


def _now_ts() -> float:
    return time.time()


def _list_transcripts(window_days: int) -> List[Dict[str, Any]]:
    """读取窗口内的 transcript 文件（防御式：损坏行跳过）。

    返回 [{path, session_id, ts, evals: [score,...], lines}]
    """
    _dir = _p("transcripts")
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(_dir):
        return out
    _cutoff = _now_ts() - window_days * 86400
    try:
        _files = [f for f in os.listdir(_dir) if f.endswith(".jsonl")]
    except Exception:
        return out
    for _f in _files[:2000]:  # 上限 2000 文件，防超大目录卡死
        _fp = os.path.join(_dir, _f)
        try:
            _mtime = os.path.getmtime(_fp)
        except Exception:
            continue
        if _mtime < _cutoff:
            continue
        _evals: List[float] = []
        _session = ""
        try:
            with open(_fp, "r", encoding="utf-8", errors="ignore") as _fh:
                for _line in _fh:
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _rec = json.loads(_line)
                    except Exception:
                        continue
                    if _rec.get("item_type") == "evaluation":
                        try:
                            _evals.append(float(_rec.get("score") or 0))
                        except Exception:
                            pass
                    if not _session and _rec.get("session_id"):
                        _session = str(_rec.get("session_id"))
        except Exception:
            continue
        if _evals:
            out.append({
                "path": _fp, "session_id": _session, "ts": _mtime,
                "evals": _evals, "n": len(_evals),
            })
    return out


# ─────────────────────────────────────
# 1. 知识保留率（intra-session 代理）
# ─────────────────────────────────────
def compute_retention_rate(window_days: int = 30) -> Dict[str, Any]:
    """知识保留率（30 天）。

    数据：transcripts evaluation score 序列。
    算法（代理口径，诚实标注）：会话内"末次评估 >= 首次评估"占比——
    反映单次教学的知识保持/提升；跨会话 30 天保留需学习者关联埋点（下轮）。

    Returns: {value, status, target, note, eligible_sessions, retained_sessions}
    """
    _sessions = _list_transcripts(window_days)
    _eligible = [s for s in _sessions if s["n"] >= 2]
    if not _eligible:
        return {
            "value": None, "status": "no_data",
            "target": 0.6,
            "note": "窗口内无 >=2 次评估的会话，无法计算（数据积累中）",
            "eligible_sessions": 0, "retained_sessions": 0,
        }
    _retained = sum(
        1 for s in _eligible if s["evals"][-1] >= s["evals"][0]
    )
    return {
        "value": round(_retained / len(_eligible), 3),
        "status": "proxy_intra_session",
        "target": 0.6,
        "note": "代理口径：会话内末次评估>=首次评估占比（跨会话保留需埋点，下轮增强）",
        "eligible_sessions": len(_eligible),
        "retained_sessions": _retained,
        "sessions_total": len(_sessions),
    }


# ─────────────────────────────────────
# 2. 学习者坚持率（30 天）
# ─────────────────────────────────────
def compute_persistence_rate(window_days: int = 30) -> Dict[str, Any]:
    """学习者坚持率（30 天）。

    数据：users_data/*/profile.json 的 mtime（画像更新 = 活跃信号）。
    代理口径（单点 mtime 限制）：窗口内活跃画像中，"后 14 天仍活跃"的占比——
    反映"持续使用"而非严格队列保留；严格队列（首段活跃∩末段仍活跃）
    需多时间点活跃历史（history.jsonl 首末消息时间），下轮增强。

    Returns: {value, status, target, note, window_active, recent_active}
    """
    _dir = _p("users_data")
    if not os.path.isdir(_dir):
        return {"value": None, "status": "no_data", "target": 0.7,
                "note": "users_data 不存在", "window_active": 0, "recent_active": 0}
    _now = _now_ts()
    _window_start = _now - window_days * 86400
    _mid = _now - (window_days // 2) * 86400
    _window_active: List[str] = []
    _recent_active: List[str] = []
    try:
        for _root, _dirs, _files in os.walk(_dir):
            for _f in _files:
                if _f != "profile.json":
                    continue
                _fp = os.path.join(_root, _f)
                try:
                    _mt = os.path.getmtime(_fp)
                except Exception:
                    continue
                if _mt >= _window_start:
                    _window_active.append(_fp)
                    if _mt >= _mid:
                        _recent_active.append(_fp)
    except Exception:
        pass
    if not _window_active:
        return {
            "value": None, "status": "no_data", "target": 0.7,
            "note": f"窗口 {window_days} 天无活跃画像，无法计算（数据积累中）",
            "window_active": 0, "recent_active": 0,
        }
    return {
        "value": round(len(_recent_active) / len(_window_active), 3),
        "status": "proxy_recent_activity",
        "target": 0.7,
        "note": "代理口径：窗口内活跃画像中后 14 天仍活跃占比（严格队列需多时间点历史，下轮增强）",
        "window_active": len(_window_active),
        "recent_active": len(_recent_active),
    }


# ─────────────────────────────────────
# 3. 元认知准确率
# ─────────────────────────────────────
def compute_metacognition_accuracy() -> Dict[str, Any]:
    """元认知准确率。

    数据：evolve_data/reflection_log.json（student_id/subject/ema_delta/reflection）。
    现状：reflection 无结构化自我评估字段 → 无法计算（诚实标注）。
    下轮增强：反思记录时补 self_assessed vs actual score 事件后启用。

    Returns: {value, status, target, note, entries}
    """
    _fp = _p("evolve_data", "reflection_log.json")
    _n = 0
    _has_self = False
    if os.path.isfile(_fp):
        try:
            with open(_fp, "r", encoding="utf-8", errors="ignore") as _fh:
                _data = json.load(_fh)
            if isinstance(_data, list):
                _n = len(_data)
                for _r in _data[:50]:
                    _refl = _r.get("reflection") or ""
                    if isinstance(_refl, str) and ("self" in _refl or "预测" in _refl
                                                   or "assessed" in _refl):
                        _has_self = True
                        break
        except Exception:
            _n = 0
    return {
        "value": None,
        "status": "no_self_assessment_data",
        "target": 0.7,
        "note": "reflection_log 暂无结构化自我评估字段（" +
               ("含自我评估痕迹" if _has_self else "无") +
               f"；共 {_n} 条反思）；下轮在反思记录点补 self_assessed 事件后启用",
        "entries": _n,
    }


# ─────────────────────────────────────
# 4. 自我更新采纳率
# ─────────────────────────────────────
def compute_self_update_acceptance() -> Dict[str, Any]:
    """自我更新采纳率。

    数据：
      - 提议数：memory/self_update_suggestions.jsonl（每行 suggestions 数组长度之和）
      - 采纳痕迹（代理）：evolve_data/insights.json 条目数 + memory/subject_patches.md 条目数
    现状：无"采纳/拒绝"事件埋点 → 采纳率不可精确计算（诚实标注）；
    报告提议数与采纳痕迹计数。下轮：self_update 采纳处补 feedback/record 事件。

    Returns: {value, status, target, note, proposals, adopted_traces}
    """
    _sf = _p("memory", "self_update_suggestions.jsonl")
    _proposals = 0
    if os.path.isfile(_sf):
        try:
            with open(_sf, "r", encoding="utf-8", errors="ignore") as _fh:
                for _line in _fh:
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _rec = json.loads(_line)
                    except Exception:
                        continue
                    _sugs = _rec.get("suggestions") or []
                    if isinstance(_sugs, list):
                        _proposals += len(_sugs)
        except Exception:
            _proposals = 0
    _traces = 0
    _if = _p("evolve_data", "insights.json")
    if os.path.isfile(_if):
        try:
            with open(_if, "r", encoding="utf-8", errors="ignore") as _fh:
                _ins = json.load(_fh)
            if isinstance(_ins, list):
                _traces += len(_ins)
        except Exception:
            pass
    _pf = _p("memory", "subject_patches.md")
    if os.path.isfile(_pf):
        try:
            with open(_pf, "r", encoding="utf-8", errors="ignore") as _fh:
                _traces += sum(1 for _l in _fh if _l.strip() and not _l.strip().startswith("#"))
        except Exception:
            pass
    return {
        "value": None,
        "status": "needs_adoption_event",
        "target": 0.5,
        "note": "无采纳/拒绝事件埋点，采纳率不可精确计算；"
               f"提议建议 {_proposals} 条、采纳痕迹 {_traces} 条（insights+patches 代理）；"
               "下轮在 self_update 采纳处补 feedback/record 事件后启用",
        "proposals": _proposals,
        "adopted_traces": _traces,
    }


# ─────────────────────────────────────
# 汇总 + 月报导出
# ─────────────────────────────────────
def compute_effect_metrics(window_days: int = 30) -> Dict[str, Any]:
    """四指标汇总（端点 /api/metrics/effects 数据源）。"""
    return {
        "metrics": {
            "persistence_rate": compute_persistence_rate(window_days),
            "retention_rate": compute_retention_rate(window_days),
            "metacognition_accuracy": compute_metacognition_accuracy(),
            "self_update_acceptance": compute_self_update_acceptance(),
        },
        "window_days": window_days,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "note": "代理口径如实标注；无数据指标为 None（不编造达标）；埋点增强见各指标 note",
    }


def export_monthly_report(window_days: int = 30) -> Dict[str, Any]:
    """导出月报到 data/effects/effect_report_YYYY-MM.{json,md}。

    Returns: {ok, path_json, path_md, metrics}
    """
    _res = compute_effect_metrics(window_days)
    _out_dir = _p("data", "effects")
    try:
        os.makedirs(_out_dir, exist_ok=True)
    except Exception:
        _out_dir = _p("data")
    _ym = datetime.now().strftime("%Y-%m")
    _json_path = os.path.join(_out_dir, f"effect_report_{_ym}.json")
    _md_path = os.path.join(_out_dir, f"effect_report_{_ym}.md")
    _ok = True
    try:
        with open(_json_path, "w", encoding="utf-8") as _fh:
            json.dump(_res, _fh, ensure_ascii=False, indent=1)
    except Exception:
        _ok = False
    # Markdown 月报
    _lines = [
        f"# PAEG 效果指标月报（{_ym}）",
        "",
        f"> 生成时间：{_res['computed_at']} · 窗口：{window_days} 天",
        f"> 口径说明：{_res['note']}",
        "",
        "| 指标 | 目标 | 当前值 | 状态 | 说明 |",
        "|---|---|---|---|---|",
    ]
    for _k, _m in _res["metrics"].items():
        _v = _m.get("value")
        _v_s = "—（无数据）" if _v is None else f"{_v}"
        _lines.append(
            f"| {_k} | ≥{_m.get('target', '?')} | {_v_s} | {_m.get('status', '')} | {_m.get('note', '')} |"
        )
    _lines += ["", "> 达标判定：以本管道数据为准；无数据指标不计入达标。"]
    try:
        with open(_md_path, "w", encoding="utf-8") as _fh:
            _fh.write("\n".join(_lines) + "\n")
    except Exception:
        _ok = False
    return {"ok": _ok, "path_json": _json_path, "path_md": _md_path, **{k: v for k, v in _res.items() if k != "metrics"}}


__all__ = [
    "compute_effect_metrics", "export_monthly_report",
    "compute_persistence_rate", "compute_retention_rate",
    "compute_metacognition_accuracy", "compute_self_update_acceptance",
]
