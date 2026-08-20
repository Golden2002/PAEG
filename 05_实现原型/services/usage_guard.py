# -*- coding: utf-8 -*-
"""services/usage_guard.py —— §3.79 C5 ⭐ 每日使用限制（家长/教师合规，教育特有标准）

memo/013 教育特有优秀线："使用时长：每日额度 + 长会话提示休息"。
实现（纯函数、SESSIONS 注入、可测）：

  - usage_key(uid) / _today()：会话键 = usage_{today}_{uid}
  - register_usage(sessions, uid)：记录一次使用（教学会话完成时）
  - usage_summary(sessions, uid)：{date, sessions, limit_sessions, over, minutes_estimate}
  - is_over_limit(sessions, uid, limit_sessions=20)：入口检查（超限拒绝）

口径：按"每日教学会话次数"为额度（时长累计需会话起止埋点，为下轮增强）；
默认每日上限 20 次教学会话（config 可经 paeg_modules.json 或环境变量调整）。
"""
from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict, Optional

_DEFAULT_LIMIT = int(os.environ.get("PAEG_DAILY_SESSION_LIMIT", "20"))


def _today() -> str:
    return date.today().isoformat()


def usage_key(uid: str) -> str:
    """SESSIONS 键（每日粒度，自动轮换）。"""
    return f"usage_{_today()}_{uid}"


def _sessions_map(sessions: dict, uid: str) -> Dict[str, Any]:
    _k = usage_key(uid)
    _cur = sessions.get(_k)
    if not isinstance(_cur, dict):
        _cur = {"date": _today(), "sessions": 0}
        sessions[_k] = _cur
    if _cur.get("date") != _today():
        _cur = {"date": _today(), "sessions": 0}
        sessions[_k] = _cur
    return _cur


def register_usage(sessions: dict, uid: str) -> int:
    """记录一次使用，返回今日累计次数。"""
    _m = _sessions_map(sessions, uid)
    _m["sessions"] = int(_m.get("sessions") or 0) + 1
    return _m["sessions"]


def usage_summary(sessions: dict, uid: str,
                  limit_sessions: Optional[int] = None) -> Dict[str, Any]:
    """今日使用摘要（家长/教师面板数据源）。"""
    _limit = limit_sessions if limit_sessions is not None else _DEFAULT_LIMIT
    _k = usage_key(uid)
    _m = sessions.get(_k)
    _n = int(_m.get("sessions") or 0) if isinstance(_m, dict) else 0
    return {
        "date": _today(),
        "sessions": _n,
        "limit_sessions": _limit,
        "over": _n >= _limit,
    }


def is_over_limit(sessions: dict, uid: str,
                  limit_sessions: Optional[int] = None) -> bool:
    """入口检查：今日已超限 → True（调用方应拒绝/提示）。"""
    _limit = limit_sessions if limit_sessions is not None else _DEFAULT_LIMIT
    _k = usage_key(uid)
    _m = sessions.get(_k)
    _n = int(_m.get("sessions") or 0) if isinstance(_m, dict) else 0
    return _n >= _limit


__all__ = ["register_usage", "usage_summary", "is_over_limit", "usage_key",
           "_DEFAULT_LIMIT"]
