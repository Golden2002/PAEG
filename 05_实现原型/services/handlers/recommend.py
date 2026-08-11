# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ services/handlers/recommend.py

推荐类问题（v0.35 从 server.py 迁出）。

"有什么推荐/推荐几本/哪个软件好"——必须基于外部真实信息（web_search 检索结果），
不能凭 LLM 训练知识编造。返回**纯 dict**（不 jsonify），调用方自行决定序列化方式
（生成器/SSE 流里没有 Flask app context，不能调 jsonify）。
"""
from __future__ import annotations


def _handle_recommend_query(learner, question, subject, llm_arg):
    """v0.35：推荐类问题——联网检索真实推荐 + 组织回答。

    返回纯 dict（不 jsonify），调用方自行序列化。
    """
    # 1) 联网检索：拿真实推荐信息
    results_text = ""
    web_ok = False
    try:
        # v0.45 ⭐ 修复：单查询 → 多查询词检索（RRF 融合，结果更丰富）
        from web_search_tool import web_search_multi
        _q = f"{question} 推荐 排名 对比"
        _items = web_search_multi(_q, llm=None, subject=subject or "",
                                  n_queries=3, per_query=5, max_total=10)
        if _items:
            results_text = "\n\n".join(
                f"[来源 {i+1}] {it['title']}\nURL: {it['url']}\n{it['content']}"
                for i, it in enumerate(_items))
            web_ok = True
    except Exception:
        results_text, web_ok = "", False

    # 2) LLM 基于检索结果组织回答
    answer = ""
    try:
        from subagents import _safe_chat
        sys_prompt = (
            "你是一位熟悉多语言学习产品的老师。学生问推荐类问题，请结合检索到的真实信息回答。\n"
            "要求：\n"
            "1. 先给出 2-4 个具体推荐（名称+一句话理由），优先用检索到的真实产品\n"
            "2. 每个推荐说明适合什么水平/目标（如零基础/进阶/备考）\n"
            "3. 若无检索结果，诚实说明'我查到的信息有限'，给通用建议但标注不确定性\n"
            "4. 用中文回答，语气亲切实用\n\n"
            f"检索到的资料：\n{results_text[:3000] if results_text else '（无检索结果）'}"
        )
        # v0.43 ⭐ P0 修复：recommend 注入注册问卷（此前缺失，与其他模式对齐）
        try:
            from prompts import _build_questionnaire_block
            _qq = _build_questionnaire_block(learner)
            if _qq:
                sys_prompt = f"{_qq}\n\n" + sys_prompt
        except Exception:
            pass
        # v0.43 ⭐ P1 修复：recommend 消费约束掩码
        try:
            from prompts import _build_constraint_layers
            _cf = getattr(learner, "_constraint_flags", ()) or ()
            if _cf:
                sys_prompt = f"{_build_constraint_layers(_cf)}\n\n" + sys_prompt
        except Exception:
            pass
        user_msg = f"学生问：{question}"
        answer = _safe_chat(llm_arg, sys_prompt, user_msg, max_tokens=900) or ""
    except Exception:
        answer = ""
    if not answer:
        answer = (
            "关于推荐，我帮你查了一些资料，但信息有限。"
            "你可以告诉我你的具体水平和目标，我帮你更精准地推荐。"
        )
    # v0.43 ⭐ P1 修复：recommend 语言规范收口（此前未过 polish）
    try:
        from services.polish import _polish_text
        answer = _polish_text(answer, context=f"recommend:{question[:30]}")
    except Exception:
        pass

    return {
        "session_id": f"rec_{learner.id}",
        "summary": {"avg_score": 0},
        "worldview_used": "weil",
        "tone_ratio": 0,
        "presentations": [
            {"step_id": 1, "content": answer, "step_type": "recommend"}
        ],
        "evaluations": [],
        "diagnosis": {},
        "plan": {"steps": [{"type": "recommend"}]},
        "reflections": [],
        "learner": {
            "id": learner.id,
            "nickname": learner.nickname,
            "grade_level": learner.grade_level,
            "subjects_mastery": learner.subjects_mastery,
        },
        "web_searched": web_ok,  # v0.35：告知调用方是否真做了网络检索（前端 badge 用）
    }
