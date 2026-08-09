# -*- coding: utf-8 -*-
"""
handlers  -  PAEG 文件操作 4 个能力处理器（v0.21.5）

4 个 handler 暴露统一接口::

    def handle(learner_id: str, query: str, retrieved_chunks: list, llm) -> str

调用方（T9 server）负责：
    1. 用 ``intent_router.route_intent(query)`` 选定意图
    2. 用 ``retriever.search(query, top_k)`` 拿到 retrieved_chunks
    3. 调 ``handlers.file_xxx.handle(learner_id, query, chunks, llm)`` 拿字符串

本包内的 4 个 handler:
    * ``file_qa``            — 文件问答
    * ``file_explain``       — 基于文件的讲解
    * ``file_quote``         — 原文摘录（**不依赖 LLM**，直接从 chunks 提取）
    * ``file_restructure``   — 结构重组（大纲/表格/思维导图）
"""
from __future__ import annotations

from . import file_qa, file_explain, file_quote, file_restructure


__all__ = ["file_qa", "file_explain", "file_quote", "file_restructure"]