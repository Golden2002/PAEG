"""conversations.py — 对话历史蓝图（v0.18 持久化 API）。

§3.45 架构拆分 P1-4：自 server.py 迁出（原 L4295-4307 / L4556-4601），行为字节级不变。
依赖注入：get_conv_store()（infra.runtime 懒加载单例，与 server.CONV_STORE 同引用）、
_is_registered（services._learner_session，§3.45 迁入）。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from infra.runtime import get_conv_store
from module_registry import require_module
from services._learner_session import _is_registered

bp = Blueprint("conversations", __name__)


@bp.route("/api/conversations/<learner_id>", methods=["GET"])
@require_module("history")
def list_conversations(learner_id):
    """列出用户全部会话（不含消息体，倒序）。"""
    if not _is_registered(learner_id):
        return jsonify({"conversations": []})
    try:
        if get_conv_store() is None:
            return jsonify({"conversations": []})
        convs = get_conv_store().list_conversations(learner_id)
        return jsonify({"conversations": convs})
    except Exception as e:
        return jsonify({"conversations": [], "error": str(e)}), 500


@bp.route("/api/conversations/<learner_id>/<conv_id>", methods=["GET"])
@require_module("history")
def get_conversation(learner_id, conv_id):
    """读取某会话完整消息。"""
    if not _is_registered(learner_id):
        return jsonify({"error": "请先登录"}), 401
    try:
        conv = get_conv_store().get_conversation(learner_id, conv_id)
        if not conv:
            return jsonify({"error": "会话不存在"}), 404
        return jsonify(conv)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/conversations/<learner_id>/<conv_id>", methods=["DELETE"])
@require_module("history")
def delete_conversation(learner_id, conv_id):
    """用户删除单个会话。"""
    if not _is_registered(learner_id):
        return jsonify({"error": "请先登录"}), 401
    try:
        ok = get_conv_store().delete_conversation(learner_id, conv_id)
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/conversations/<learner_id>", methods=["DELETE"])
@require_module("history")
def clear_conversations(learner_id):
    """用户清空全部会话。"""
    if not _is_registered(learner_id):
        return jsonify({"error": "请先登录"}), 401
    try:
        ok = get_conv_store().clear_all(learner_id)
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/conversations/cleanup", methods=["POST"])
@require_module("history")
def cleanup_conversations():
    """定期清理超期会话（可被定时任务调用）。"""
    if get_conv_store() is None:
        return jsonify({"ok": False, "error": "存储未初始化"}), 500
    removed = get_conv_store().cleanup()
    return jsonify({"ok": True, "removed": removed})
