"""routing.py — 模式自动纠正（Mode Auto-Correct）。

v0.43 提取自 server.py（v0.40.4 L280-331 原 _mode_auto_correct）。

职责
----
用户在独立端点（method/knowledge/affection/answer）但输入其实属于
其他模式时，后端自动纠正到正确模式并标注 `was_redirected=True`。

优先级（按语义严肃性）
---------------------
情绪 > 知识库 > 学习方法 > 出题

依赖
----
- `meta_router.is_affection_expression / is_knowledge_query / is_method_advice /
  is_problem_request`（函数体内 import）
- `subagents.AffectionSupportor`（函数体内 import）
- `infra.sessions.SESSIONS`（函数体内 import）
- `services.polish._polish_text`（函数体内 import）
- `server._handle_knowledge_query / _handle_method_advice / _handle_problem_request`
  （函数体内 import，server.py 是中央枢纽）
- `flask.jsonify`（函数体内 import）

行为
----
与 v0.40.4 内联实现 100% 等价：
- text 为空 → return None
- 任一异常 → 静默忽略 + return None
- 优先级匹配 → 返回 jsonify 响应
- 无匹配 → return None（走本模式默认逻辑）
"""
from __future__ import annotations

from typing import Any, Optional


def _mode_auto_correct(
    text: str,
    requested_mode: str,
    learner: Any,
    learner_id: str,
    subject: str = "default",
) -> Optional[Any]:
    """模式自动纠正（v0.20.3 ⭐）：用户在独立端点（method/knowledge/affection/answer）
    但输入其实属于其他模式时，后端自动纠正到正确模式。

    返回纠正后的 jsonify 响应（或 None——无需纠正，走本模式默认逻辑）。
    """
    if not text or not text.strip():
        return None
    try:
        from meta_router import is_affection_expression, is_knowledge_query, is_method_advice, is_problem_request

        # 优先级：情绪 > 知识库 > 学习方法 > 出题（按语义严肃性）
        if requested_mode != "affection" and is_affection_expression(text):
            from subagents import AffectionSupportor
            from infra.sessions import SESSIONS
            from services.polish import _polish_text
            from infra.runtime import get_llm
            _emo = AffectionSupportor()
            _hist = SESSIONS.get(f"chat_hist_{learner_id}", [])
            _llm = get_llm()
            _res = _emo.run(_llm, text, learner, history=_hist)
            _emo_content = _polish_text(_res.get("content", ""), context=f"affection:{text[:30]}")
            from flask import jsonify
            # v0.43 ⭐ P0 修复：模式纠正分支写回 chat_hist（此前纠正后对话不持久化，
            # 连续纠正对话丢上下文——与 method/knowledge/affection/answer 写回对齐）
            try:
                from infra.sessions import append_chat_hist as _append_chat_hist
                _append_chat_hist(learner_id, text, _emo_content)
            except Exception:
                pass
            return jsonify({
                "session_id": f"affection_{learner_id}",
                "summary": {"avg_score": 0}, "worldview_used": "weil", "tone_ratio": 0,
                "presentations": [{"step_id": 1, "content": _emo_content, "step_type": "affection"}],
                "evaluations": [], "diagnosis": {}, "plan": {"steps": []}, "reflections": [],
                "learner": {"id": learner.id, "nickname": learner.nickname,
                            "grade_level": learner.grade_level, "subjects_mastery": learner.subjects_mastery},
                "actual_mode": "affection", "requested_mode": requested_mode, "was_redirected": True,
            })
        if requested_mode != "knowledge" and is_knowledge_query(text):
            # v0.41.9 ⭐ 修复：直接导入 services.handlers（此前 from server import
            # → 循环依赖 server→services/routing→server；handler 已迁出）
            from services.handlers.knowledge import _handle_knowledge_query
            from flask import jsonify
            _kb = _handle_knowledge_query(learner, subject)
            _kb["actual_mode"] = "knowledge"
            _kb["requested_mode"] = requested_mode
            _kb["was_redirected"] = True
            # v0.43 ⭐ P0 修复：纠正分支写回 chat_hist（连续纠正对话不丢上下文）
            try:
                from infra.sessions import append_chat_hist as _append_chat_hist
                _kbc = (_kb.get("presentations") or [{}])[0].get("content", "")
                _append_chat_hist(learner_id, text, _kbc)
            except Exception:
                pass
            return jsonify(_kb)
        if requested_mode not in ("method", "affection") and is_method_advice(text):
            from services.handlers.method import _handle_method_advice
            from flask import jsonify
            _ma = _handle_method_advice(learner, text, subject)
            _ma_data = _ma.get_json()
            _ma_data["actual_mode"] = "method"
            _ma_data["requested_mode"] = requested_mode
            _ma_data["was_redirected"] = True
            # v0.43 ⭐ P0 修复：纠正分支写回 chat_hist
            try:
                from infra.sessions import append_chat_hist as _append_chat_hist
                _mac = (_ma_data.get("presentations") or [{}])[0].get("content", "")
                _append_chat_hist(learner_id, text, _mac)
            except Exception:
                pass
            return jsonify(_ma_data)
        if requested_mode not in ("answer", "problem") and is_problem_request(text):
            from services.handlers.problem import _handle_problem_request
            from flask import jsonify
            _pr = _handle_problem_request(learner, text, subject)
            _pr_data = _pr.get_json()
            _pr_data["actual_mode"] = "problem"
            _pr_data["requested_mode"] = requested_mode
            _pr_data["was_redirected"] = True
            # v0.43 ⭐ P0 修复：纠正分支写回 chat_hist
            try:
                from infra.sessions import append_chat_hist as _append_chat_hist
                _prc = (_pr_data.get("presentations") or [{}])[0].get("content", "")
                _append_chat_hist(learner_id, text, _prc)
            except Exception:
                pass
            return jsonify(_pr_data)
    except Exception as _e:
        print(f"[PAEG][services.routing] _mode_auto_correct 异常忽略: {_e}")
        pass
        pass
    return None


# ─────────────────────────────────────
# v0.43 兼容别名：保持原 server.py 中调用点不变。
# server.py 改用 `from services.routing import _mode_auto_correct`。
# ─────────────────────────────────────
