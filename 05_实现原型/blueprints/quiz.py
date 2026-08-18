"""quiz.py — 交互式教学选择题蓝图（v0.67）。

§3.45 架构拆分 P1-6：自 server.py 迁出（原 L1060-1092），行为字节级不变。
依赖注入：SESSIONS（infra.sessions 同引用）、_anon_learner_id（utils）、
ensure_learner_session（services._learner_session）、quiz_service 懒加载。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from infra.sessions import SESSIONS
from services._learner_session import ensure_learner_session
from utils import _anon_learner_id

bp = Blueprint("quiz", __name__)


@bp.route("/api/teach/quiz/next", methods=["POST"])
def teach_quiz_next():
    """v0.67 交互式教学选择题：出题。{learner_id, concept, subject, difficulty}"""
    data = request.get_json(force=True) or {}
    learner_id = data.get("learner_id") or _anon_learner_id(data)
    learner = ensure_learner_session(learner_id, data, SESSIONS)
    concept = (data.get("concept") or "").strip() or "当前知识点"
    subject = data.get("subject") or ""
    difficulty = int(data.get("difficulty", 1) or 1)
    try:
        from services.quiz_service import generate_choice
        result = generate_choice(learner, subject, concept, difficulty)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": "出题失败: %s" % e}), 500


@bp.route("/api/teach/quiz/answer", methods=["POST"])
def teach_quiz_answer():
    """v0.67 交互式教学选择题：判题 + 掌握度更新。{learner_id, quiz_id, selected_idx}"""
    data = request.get_json(force=True) or {}
    learner_id = data.get("learner_id") or _anon_learner_id(data)
    learner = ensure_learner_session(learner_id, data, SESSIONS)
    quiz_id = (data.get("quiz_id") or "").strip()
    selected_idx = data.get("selected_idx")
    if not quiz_id or selected_idx is None:
        return jsonify({"error": "quiz_id and selected_idx required"}), 400
    try:
        from services.quiz_service import grade_answer
        result = grade_answer(learner, quiz_id, int(selected_idx))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": "判题失败: %s" % e}), 500
