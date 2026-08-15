# -*- coding: utf-8 -*-
"""services/file_operation.py —— 用户文件 4 能力统一入口（§3.46.2 Phase 3 拆分）

从 server.py 迁出（原 L289-355）：
- _try_file_operation：用户输入含"我的资料/上传的文件/讲义/笔记/文件里/原文"等
  文件操作信号 → 意图路由 → BM25 检索用户文件 → 对应 handler → SSE 流式返回。

迁移理由：chat_stream 蓝图需要该函数，但蓝图禁止反向依赖入口模块（audit L521），
故下沉到 services/；server.py 顶部 re-export 保既有符号（teach_stream 仍引用）。
"""
from __future__ import annotations

import json

from flask import Response

from infra.runtime import get_conv_store
from infra.sessions import SESSIONS
from services._learner_session import _is_registered

import logging
logger = logging.getLogger("paeg")


def _try_file_operation(learner_id: str, text: str, llm):
    """v0.43 ⭐ P0-D 修复：用户文件 4 能力统一入口（chat/teach 等端点复用）。

    触发：用户输入含"我的资料/上传的文件/讲义/笔记/文件里/原文"等文件操作信号。
    流程：意图路由 → BM25 检索用户文件 → 对应 handler → SSE 流式返回。
    返回：SSE Response（命中文件操作时）或 None（普通对话，调用方继续正常流程）。
    """
    try:
        from lib.ingest.intent_router import is_file_operation, route_intent, extract_filename
        if not is_file_operation(text):
            return None
        from lib.ingest.readers import read_corpus_full
        from lib.ingest.chunker import chunk_documents
        from lib.ingest.retriever import make_retriever
        from lib.ingest import handlers as _fh
        _docs = read_corpus_full(learner_id)
        if not _docs:
            return None
        _chunks = chunk_documents(_docs, max_chars=400, overlap=50)
        _retriever, _mode = make_retriever(_chunks)
        _intent = route_intent(text)
        _fname = extract_filename(text)
        _candidates = [c for c in _chunks if (not _fname) or (_fname.lower() in c.get("doc_name", "").lower())] \
            if _fname else _chunks
        _hits = _retriever.search(text, top_k=4) if _candidates else []
        _hit_chunks = []
        _hit_keys = set()
        for h in _hits:
            _key = (h.get("doc_name"), h.get("chunk_index"))
            if _key not in _hit_keys:
                _hit_keys.add(_key)
                _hit_chunks.append(h)
        if not _hit_chunks and _candidates:
            _hit_chunks = _candidates[:2]  # 检索无命中 → 用候选块前 2 个兜底
        _handler = {
            "file_qa": _fh.file_qa, "file_explain": _fh.file_explain,
            "file_quote": _fh.file_quote, "file_restructure": _fh.file_restructure,
        }.get(_intent.value, _fh.file_qa)
        _reply = _handler.handle(learner_id, text, _hit_chunks, llm)

        def gen_file_op():
            # v0.36.2 ⭐ 早退分支补保存（文件操作提前 return，主流程保存不执行）
            try:
                _conv = get_conv_store()
                if _conv is not None and _is_registered(learner_id):
                    _fcid = SESSIONS.get(f"conv_{learner_id}")
                    _fcid = _conv.add_message(
                        learner_id, "chat", str(text)[:60], "user", text, conv_id=_fcid)
                    _frep = str(_reply or "").strip()[:2000] or f"（文件操作：{_intent.value}）"
                    _fcid = _conv.add_message(
                        learner_id, "chat", _frep[:30], "assistant", _frep, conv_id=_fcid)
                    SESSIONS[f"conv_{learner_id}"] = _fcid
            except Exception as _fe2:
                logger.warning("文件操作保存会话失败: %s", _fe2)
            yield f"event: presentation\ndata: {json.dumps({'step_id': 1, 'content': _reply, 'step_type': 'file_' + _intent.value}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'status': 'completed', 'file_op': _intent.value, 'retriever': _mode}, ensure_ascii=False)}\n\n"
        return Response(gen_file_op(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    except Exception as _fe:
        logger.warning("文件操作处理失败（降级普通对话）: %s", _fe)
        return None


__all__ = ["_try_file_operation"]
