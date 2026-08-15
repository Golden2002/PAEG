"""proactive.py — 定时主动问候蓝图（v0.67）。

§3.46.2 Phase 2（W9）拆分：自 server.py 迁出（原 L478-547），行为字节级不变。
依赖注入：SESSIONS（infra.sessions 同引用）、_anon_learner_id（utils）、
proactive_templates 懒加载；无 server 模块级全局依赖。
"""
from __future__ import annotations

import time
from datetime import datetime

from flask import Blueprint, jsonify, request

from infra.sessions import SESSIONS
from utils import _anon_learner_id

bp = Blueprint("proactive", __name__)

import logging
logger = logging.getLogger("paeg")


@bp.route("/agent/proactive_greet", methods=["POST"])
def proactive_greet():
    """v0.67 ⭐ 定时主动问候：前端 idle 5-10min 无操作时触发。
    频率限制：每会话 1 次 + 每日 3 次 + 最短间隔 30min。
    返回 {ok, content, proactive: True}——前端 addMsg 渲染（老师主动开口）。
    """
    data = request.get_json(force=True) or {}
    uid = data.get("uid") or data.get("learner_id") or _anon_learner_id(data)
    session_id = data.get("session_id") or uid
    idle_ms = int(data.get("idle_ms", 0) or 0)

    # 1) 频率限制（SESSIONS 内存计数）
    try:
        meta = SESSIONS.setdefault("proactive_meta", {})
        today = datetime.now().strftime("%Y%m%d")
        u_meta = meta.setdefault(uid, {"count": 0, "date": today, "last_at": 0})
        if u_meta.get("date") != today:
            u_meta["count"] = 0
            u_meta["date"] = today
        if u_meta.get("count", 0) >= 3:
            return jsonify({"ok": False, "error": "daily_limit"}), 429
        if time.time() - u_meta.get("last_at", 0) < 30 * 60:
            return jsonify({"ok": False, "error": "too_frequent"}), 429
    except Exception:
        logger.warning(f"[server] proactive_greet 静默异常已记录 (L548)")
        pass

    # 2) 学科推断（从最近 chat_hist 提取）
    subject = "通用"
    try:
        hist = SESSIONS.get(f"chat_hist_{uid}", [])
        if hist:
            _last = ""
            for h in reversed(hist[-5:]):
                if isinstance(h, dict) and h.get("role") == "user":
                    _last = str(h.get("content", ""))
                    break
            for _s in ("数学", "物理", "语文", "英语", "化学", "生物", "历史"):
                if _s in _last:
                    subject = _s
                    break
    except Exception:
        logger.warning(f"[server] proactive_greet 静默异常已记录 (L565)")
        pass

    # 3) 选模板 + 写 chat_hist + 计数
    try:
        from proactive_templates import pick_template
        content = pick_template(subject, idle_ms, session_id=session_id)
    except Exception:
        content = "在忙什么呀？有问题随时告诉我。"
    try:
        hist = SESSIONS.setdefault(f"chat_hist_{uid}", [])
        hist.append({"role": "assistant", "content": content, "proactive": True})
        if len(hist) > 60:
            SESSIONS[f"chat_hist_{uid}"] = hist[-60:]
    except Exception:
        logger.warning(f"[server] proactive_greet 静默异常已记录 (L579)")
        pass
    try:
        meta = SESSIONS.setdefault("proactive_meta", {})
        u_meta = meta.setdefault(uid, {"count": 0, "date": datetime.now().strftime("%Y%m%d"), "last_at": 0})
        u_meta["count"] = u_meta.get("count", 0) + 1
        u_meta["last_at"] = time.time()
    except Exception:
        logger.warning(f"[server] proactive_greet 静默异常已记录 (L586)")
        pass

    return jsonify({"ok": True, "content": content, "proactive": True, "subject": subject})
