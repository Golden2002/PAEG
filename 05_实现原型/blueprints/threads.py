"""threads.py — 教学会话 Thread 蓝图（v0.38 内部 API）。

§3.45 架构拆分 P1-2：自 server.py 迁出（原 L403-471），行为字节级不变。
依赖注入：session_model.ThreadStore 懒加载（无 server 全局依赖）。
"""
from __future__ import annotations

import json

from flask import Blueprint, Response, jsonify, request

from module_registry import require_module

bp = Blueprint("threads", __name__)


@bp.route("/api/threads", methods=["POST"])
@require_module("history")
def create_thread():
    # v0.38 内部 API（前端未直接调用；供 MCP/外部 Agent 接入）
    """创建教学会话 Thread（跨课次持久容器）。"""
    data = request.get_json(force=True) or {}
    student_id = data.get("student_id") or data.get("learner_id") or "anonymous"
    subject = data.get("subject", "general")
    title = data.get("title", "")
    try:
        from session_model import ThreadStore
        ts = ThreadStore()
        tid = ts.create(student_id, subject, title)
        return jsonify({"ok": True, "thread_id": tid}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/threads/<student_id>", methods=["GET"])
@require_module("history")
def list_threads(student_id):
    """列出学生的全部 Thread（不含消息体）。"""
    try:
        from session_model import ThreadStore
        ts = ThreadStore()
        return jsonify({"ok": True, "threads": ts.list(student_id)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/threads/<student_id>/<tid>/events", methods=["GET"])
@require_module("history")
def thread_events(student_id, tid):
    """SSE 事件流（Codex App Server 的 HTTP 等价物，支持 Last-Event-ID 续传）。"""
    try:
        from session_model import ThreadStore
        ts = ThreadStore()
        last = int(request.headers.get("Last-Event-ID", 0) or 0)
        events = ts.events_since(student_id, tid, last)

        def gen():
            for e in events:
                yield f"id: {e['event_id']}\n"
                yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"

        return Response(gen(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/threads/<student_id>/<tid>", methods=["POST"])
@require_module("history")
def thread_action(student_id, tid):
    """Thread 操作：fork / archive / start_turn。"""
    data = request.get_json(force=True) or {}
    action = data.get("action", "")
    try:
        from session_model import ThreadStore
        ts = ThreadStore()
        if action == "fork":
            new_tid = ts.fork(student_id, tid)
            return jsonify({"ok": True, "thread_id": new_tid})
        if action == "archive":
            ok = ts.archive(student_id, tid)
            return jsonify({"ok": ok})
        if action == "start_turn":
            trn = ts.start_turn(student_id, tid, data.get("agent", "tutor"))
            return jsonify({"ok": True, "turn_id": trn})
        return jsonify({"ok": False, "error": f"未知操作 {action}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
