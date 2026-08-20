# -*- coding: utf-8 -*-
"""services/srs_service.py —— §3.79 ⭐ 间隔重复复习计划接线（孤儿 srs_sm2 → 教学闭环）

把纯函数 `services/srs_sm2.sm2_review`（SM-2 算法，原孤儿模块）接入教学闭环：

  - add_card(uid, concept, subject, quality)：教学评估达标（ready_to_advance）后
    将概念加入/更新 SRS 复习卡（SM-2 调度 interval/repetition/easiness + due 日期）
  - due_cards(uid, today=None)：到期待复习卡（due <= today）
  - review_card(uid, concept, quality)：学生复习反馈 → SM-2 更新 → 下次 due
  - all_cards(uid) / card(uid, concept)

持久化：users_data/<uid>/srs.json（原子写 tmp+os.replace，与 profile 同目录规范）。
防御式：文件缺失/损坏 → 空；写失败不抛（不影响教学主流程）。
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

# 教学评估达标 → 新卡初始质量（SM-2 q=5 完全回忆起点；后续按学生复习反馈更新）
_DEFAULT_QUALITY = 5


def _srs_path(uid: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "users_data", str(uid), "srs.json")


def _load_cards(uid: str) -> Dict[str, Any]:
    _p = _srs_path(uid)
    if not os.path.isfile(_p):
        return {}
    try:
        with open(_p, "r", encoding="utf-8") as _fh:
            _data = json.load(_fh)
        if isinstance(_data, dict) and isinstance(_data.get("cards"), dict):
            return _data["cards"]
    except Exception:
        pass
    return {}


def _save_cards(uid: str, cards: Dict[str, Any]) -> bool:
    try:
        _p = _srs_path(uid)
        os.makedirs(os.path.dirname(_p), exist_ok=True)
        _tmp = _p + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as _fh:
            json.dump({"version": 1, "cards": cards}, _fh,
                      ensure_ascii=False, indent=1)
        os.replace(_tmp, _p)
        return True
    except Exception:
        return False


def _next_due(state: Dict[str, Any], today: date) -> str:
    """按 SM-2 interval 计算下次到期日。"""
    _iv = max(1, int(state.get("interval") or 0))
    return (today + timedelta(days=_iv)).isoformat()


def add_card(uid: str, concept: str, subject: str = "",
             quality: int = _DEFAULT_QUALITY) -> Optional[Dict[str, Any]]:
    """教学评估达标后加入/更新复习卡（SM-2 调度）。

    Returns:
        更新后的卡 dict（写失败/参数异常返回 None）。
    """
    if not uid or not concept:
        return None
    try:
        from services.srs_sm2 import sm2_review
        _cards = _load_cards(uid)
        _key = str(concept).strip()[:120]
        _old = _cards.get(_key) or {}
        _state = sm2_review({
            "interval": _old.get("interval", 0),
            "repetition": _old.get("repetition", 0),
            "easiness": _old.get("easiness", 2.5),
        }, int(quality))
        _today = date.today()
        _card = {
            "concept": _key,
            "subject": str(subject or _old.get("subject", "")),
            "interval": _state["interval"],
            "repetition": _state["repetition"],
            "easiness": round(_state["easiness"], 3),
            "due": _next_due(_state, _today),
            "added": _old.get("added", _today.isoformat()),
            "reviews": int(_old.get("reviews") or 0) + 1,
        }
        _cards[_key] = _card
        if _save_cards(uid, _cards):
            return _card
        return None
    except Exception:
        return None


def card(uid: str, concept: str) -> Optional[Dict[str, Any]]:
    _cards = _load_cards(uid)
    return _cards.get(str(concept).strip()[:120])


def all_cards(uid: str) -> List[Dict[str, Any]]:
    _cards = _load_cards(uid)
    return [dict(v) for v in _cards.values()]


def due_cards(uid: str, today: Optional[str] = None) -> List[Dict[str, Any]]:
    """到期待复习卡（due <= today，按 due 升序）。"""
    _today = today or date.today().isoformat()
    _out = []
    for _c in all_cards(uid):
        if _c.get("due", "") <= _today:
            _out.append(_c)
    _out.sort(key=lambda c: c.get("due", ""))
    return _out


def review_card(uid: str, concept: str, quality: int) -> Optional[Dict[str, Any]]:
    """学生复习反馈（SM-2 更新）。

    Args:
        quality: 0-5（5=完全回忆；<3 重置间隔）
    """
    _key = str(concept).strip()[:120]
    _cards = _load_cards(uid)
    if _key not in _cards:
        return None
    try:
        from services.srs_sm2 import sm2_review
        _old = _cards[_key]
        _state = sm2_review({
            "interval": _old.get("interval", 0),
            "repetition": _old.get("repetition", 0),
            "easiness": _old.get("easiness", 2.5),
        }, int(quality))
        _cards[_key].update({
            "interval": _state["interval"],
            "repetition": _state["repetition"],
            "easiness": round(_state["easiness"], 3),
            "due": _next_due(_state, date.today()),
            "reviews": int(_old.get("reviews") or 0) + 1,
            "last_quality": int(quality),
        })
        if _save_cards(uid, _cards):
            return _cards[_key]
        return None
    except Exception:
        return None


__all__ = ["add_card", "card", "all_cards", "due_cards", "review_card"]
