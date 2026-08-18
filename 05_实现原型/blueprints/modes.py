"""modes.py — 独立对话类型蓝图（method/knowledge/affection，v0.19.25+）。

§3.46.2 Phase 2（W9）拆分：自 server.py 迁出（原 L4029-4221），行为字节级不变。
依赖注入：SESSIONS/CONV_STORE（infra.runtime + infra.sessions 同引用）、
ensure_learner_session/_is_registered（services/_learner_session）、
server 内部辅助函数（_mode_auto_correct/_set_constraint_flags/_append_chat_hist/
_handle_method_advice/_handle_knowledge_query/_polish_text/_hydrate_learner）经
services 层懒加载引用（避免蓝图反向依赖入口模块造成循环导入）。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from infra.runtime import get_conv_store, get_llm
from infra.sessions import SESSIONS
from module_registry import require_module
from services._learner_session import _is_registered, ensure_learner_session
from utils import _anon_learner_id, _hydrate_learner

bp = Blueprint("modes", __name__)


@bp.route("/api/method", methods=["POST"])
@require_module("method")
def method_advice():
    """学科学习方法咨询（独立对话类型）。

    与 teach 模式内置拦截不同：这是用户显式选择"学习方法"模式时的端点，
    无论输入什么（不必命中 is_method_advice 模式），都走学习方法指导。
    """
    data = request.get_json(force=True)
    learner_id = data.get("learner_id") or _anon_learner_id(data)
    # v0.42 ⭐ 重构提取至 services/_learner_session.py（等价原内联 — 无 elif、无 target_exam）
    learner = ensure_learner_session(learner_id, data, SESSIONS)
    _hydrate_learner(learner, data)  # v0.32 ⭐ 每次请求同步学段（修复缓存陈旧）
    # v0.43 ⭐ P0 修复：method 端点设置约束掩码（与其他模式对齐）
    from services.session_helpers import _set_constraint_flags
    _set_constraint_flags(learner, data.get("concept") or data.get("text") or "", "method")
    concept = data.get("concept") or data.get("text") or ""
    subject = data.get("subject", "general")
    # v0.68 ⭐ 学习计划：可选 deadline（"3个月内"），传给 handler 供计划周期计算
    deadline = data.get("deadline") or ""
    if not concept:
        return jsonify({"error": "concept is required"}), 400
    # v0.20.3：模式自动纠正——选错模式时后端兜底
    try:
        from services.routing import _mode_auto_correct
        _correct = _mode_auto_correct(concept, "method", learner, learner_id, subject)
        if _correct is not None:
            return _correct
    except Exception as _e:
        print(f"[PAEG][server.py] method_advice 异常忽略: {_e}")
        pass
    from services.handlers.method import _handle_method_advice
    result = _handle_method_advice(learner, concept, subject, deadline=deadline)
    # v0.21.7：保存会话到 CONV_STORE（前端历史会话可恢复）
    # v0.32 ⭐ 匿名对话落盘：放宽为 _is_registered（允许 web_ 前缀）
    try:
        if _is_registered(learner_id):
            cid = SESSIONS.get(f"conv_method_{learner_id}")
            _content = ""
            if isinstance(result, dict):
                _content = (result.get("presentations") or [{}])[0].get("content", "")
            elif hasattr(result, "get_json"):
                _rd = result.get_json()
                _content = (_rd.get("presentations") or [{}])[0].get("content", "")
            _conv = get_conv_store()
            cid = _conv.add_message(learner_id, "method", concept[:30], "user", concept, conv_id=cid)
            cid = _conv.add_message(learner_id, "method", concept[:30], "assistant", _content, conv_id=cid)
            SESSIONS[f"conv_method_{learner_id}"] = cid
    except Exception as _e:
        print(f"[PAEG] method 保存会话失败: {_e}")
    # v0.42.3 ⭐ P0 修复：method 写回 chat_hist（统一 helper）
    _m_content = ""
    if isinstance(result, dict):
        _m_content = (result.get("presentations") or [{}])[0].get("content", "")
    elif hasattr(result, "get_json"):
        _rd = result.get_json()
        _m_content = (_rd.get("presentations") or [{}])[0].get("content", "")
    from services.session_helpers import _append_chat_hist
    _append_chat_hist(learner_id, concept, _m_content)
    return result


@bp.route("/api/knowledge", methods=["POST"])
@require_module("knowledge")
def knowledge_query():
    """知识库查询（独立对话类型）。

    用户显式选择"知识库"模式时的端点：清点 Library 已收录资料 + 提示上传。
    """
    data = request.get_json(force=True)
    learner_id = data.get("learner_id") or _anon_learner_id(data)
    # v0.42 ⭐ 重构提取至 services/_learner_session.py（等价原内联 — 无 elif、无 target_exam）
    learner = ensure_learner_session(learner_id, data, SESSIONS)
    _hydrate_learner(learner, data)  # v0.32 ⭐ 每次请求同步学段（修复缓存陈旧）
    # v0.43 ⭐ P0 修复：knowledge 端点设置约束掩码（与其他模式对齐）
    from services.session_helpers import _set_constraint_flags
    _set_constraint_flags(learner, data.get("text") or data.get("concept") or "", "knowledge")
    subject = data.get("subject", "general")
    # v0.20.3：知识库模式若用户实际在倾诉/问方法，自动纠正
    try:
        _q = data.get("text") or data.get("concept") or ""
        if _q:
            from services.routing import _mode_auto_correct
            _correct = _mode_auto_correct(_q, "knowledge", learner, learner_id, subject)
            if _correct is not None:
                return _correct
    except Exception as _e:
        print(f"[PAEG][server.py] knowledge_query 异常忽略: {_e}")
        pass
    # v6.0 ⭐ P0 修复：知识库模式下自我指涉问题（"你有哪些功能/你是谁"）应走
    # 确定性模板而非库清点——与 teach/chat 端点对齐（Cascade 规则优先）
    try:
        from self_referential import is_interface_query, handle_interface_query
        if _q and is_interface_query(_q):
            _ui_reply = handle_interface_query(_q, learner)
            return jsonify({
                "presentations": [{"step_id": 1, "content": _ui_reply, "step_type": "interface"}],
                "mode": "knowledge",
                "ok": True,
            })
    except Exception as _e:
        print(f"[PAEG][server.py] knowledge interface 拦截异常忽略: {_e}")
        pass
    # v6.0 ⭐ 乱码/无意义输入快速兜底（测试发现 zzz 触发 78s LLM 推理）
    try:
        from utils.gibberish import is_gibberish
        if _q and is_gibberish(_q):
            _gib_reply = ("好的，我收到你的输入了。刚才那串内容我没能识别成具体的问题——"
                          "可能是手滑或乱码。你可以重新说一遍想问的，比如「查一下什么是导数」"
                          "或者「你的知识库里有什么」。我会一直在这儿。")
            return jsonify({
                "presentations": [{"step_id": 1, "content": _gib_reply, "step_type": "chat"}],
                "mode": "knowledge",
                "ok": True,
            })
    except Exception as _e:
        print(f"[PAEG][server.py] knowledge gibberish 兜底异常忽略: {_e}")
        pass
    from services.handlers.knowledge import _handle_knowledge_query
    result = _handle_knowledge_query(learner, subject)
    # v0.21.7：保存会话到 CONV_STORE（前端历史会话可恢复）
    # v0.32 ⭐ 匿名对话落盘：放宽为 _is_registered（允许 web_ 前缀）
    try:
        if _is_registered(learner_id):
            _q = data.get("text") or data.get("concept") or "知识库"
            cid = SESSIONS.get(f"conv_knowledge_{learner_id}")
            _content = (result.get("presentations") or [{}])[0].get("content", "") \
                if isinstance(result, dict) else ""
            _conv = get_conv_store()
            cid = _conv.add_message(learner_id, "knowledge", _q[:30], "user", _q, conv_id=cid)
            cid = _conv.add_message(learner_id, "knowledge", _q[:30], "assistant", _content, conv_id=cid)
            SESSIONS[f"conv_knowledge_{learner_id}"] = cid
    except Exception as _e:
        print(f"[PAEG] knowledge 保存会话失败: {_e}")
    # v0.42.3 ⭐ P0 修复：knowledge 写回 chat_hist（统一 helper）
    _kq = data.get("text") or data.get("concept") or "知识库"
    _k_content = (result.get("presentations") or [{}])[0].get("content", "") \
        if isinstance(result, dict) else ""
    from services.session_helpers import _append_chat_hist
    _append_chat_hist(learner_id, _kq, _k_content)
    return jsonify(result)


@bp.route("/api/affection", methods=["POST"])
@require_module("affection")
def affection_support():
    """情绪与心理支持（独立对话类型 v0.19.29）。

    用户显式选择"倾诉"模式时的端点：走 AffectionSupportor 子代理，
    以注意力陪伴（胡塞尔悬置 + 薇依注意力 + 尼采自我克服），不教不答不解决。
    """
    data = request.get_json(force=True)
    learner_id = data.get("learner_id") or _anon_learner_id(data)
    # v0.42 ⭐ 重构提取至 services/_learner_session.py（等价原内联 — 无 elif、无 target_exam）
    learner = ensure_learner_session(learner_id, data, SESSIONS)
    _hydrate_learner(learner, data)  # v0.32 ⭐ 每次请求同步学段（修复缓存陈旧）
    # v0.43 ⭐ P0 修复：affection 端点设置约束掩码（affection 模式本身即情绪信号 → 组B）
    from services.session_helpers import _set_constraint_flags
    _set_constraint_flags(learner, data.get("text") or data.get("concept") or "", "affection", affection=True)
    text = data.get("text") or data.get("concept") or ""
    if not text:
        return jsonify({"error": "text is required"}), 400
    # v0.20.3：模式自动纠正——倾诉模式下若明显是知识/方法/出题，纠正（情绪输入保留）
    try:
        from services.routing import _mode_auto_correct
        _correct = _mode_auto_correct(text, "affection", learner, learner_id, "general")
        if _correct is not None:
            return _correct
    except Exception as _e:
        print(f"[PAEG][server.py] affection_support 异常忽略: {_e}")
        pass
    from subagents import AffectionSupportor
    _emo = AffectionSupportor()
    _chat_hist = SESSIONS.get(f"chat_hist_{learner_id}", [])
    _llm = get_llm()
    _emo_result = _emo.run(_llm, text, learner, history=_chat_hist)
    from services.lang_gate import lang_gate_content as _polish_text
    _emo_content = _polish_text(_emo_result.get("content", ""), context=f"affection:{text[:30]}")
    # v0.21.7：保存会话到 CONV_STORE（前端历史会话可恢复）
    # v0.32 ⭐ 匿名对话落盘：放宽为 _is_registered（允许 web_ 前缀）
    try:
        if _is_registered(learner_id):
            cid = SESSIONS.get(f"conv_affection_{learner_id}")
            _conv = get_conv_store()
            cid = _conv.add_message(learner_id, "affection", text[:30], "user", text, conv_id=cid)
            cid = _conv.add_message(learner_id, "affection", text[:30], "assistant", _emo_content, conv_id=cid)
            SESSIONS[f"conv_affection_{learner_id}"] = cid
    except Exception as _e:
        print(f"[PAEG] affection 保存会话失败: {_e}")
    # v0.42.3 ⭐ P0 修复：affection 写回 chat_hist（统一 helper）——
    # 此前只读不写，第二句倾诉看不到第一句，情绪陪伴连贯性断裂。
    from services.session_helpers import _append_chat_hist
    _append_chat_hist(learner_id, text, _emo_content)
    return jsonify({
        "session_id": f"affection_{learner_id}",
        "summary": {"avg_score": 0},
        "worldview_used": "weil",
        "tone_ratio": 0,
        "presentations": [
            {"step_id": 1, "content": _emo_content,
             "step_type": "affection"}
        ],
        "evaluations": [], "diagnosis": {}, "plan": {"steps": []},
        "reflections": [],
        "learner": {
            "id": learner.id, "nickname": learner.nickname,
            "grade_level": learner.grade_level,
            "subjects_mastery": learner.subjects_mastery,
        },
        "mode": "affection",
    })
