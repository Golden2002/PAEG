# -*- coding: utf-8 -*-
"""
file_qa.py  -  文件问答 handler（v0.21.5）

职责
----
处理 ``Intent.FILE_QA``：用户问"我的笔记里 X 怎么说的？"。

调用方（T9 server 接入）已经把 query 通过 retriever 检索成 retrieved_chunks，
本模块只负责：

1. 组装 system prompt（PROMPT_TEMPLATES[FILE_QA] + chunk 文本）
2. 调用 ``llm.chat(system, messages, max_tokens)`` 拿回答
3. LLM 失败/空回 → 返回 chunks 原文拼接的兜底
4. chunks 为空 → 返回"在你的上传资料中未找到相关内容"

设计原则
--------
* 不依赖 LLM 可用性 —— 没 LLM 也能基于 chunks 给基础回答。
* 不抛异常 —— 任何错误都被降级为兜底文本。
"""
from __future__ import annotations

from typing import List

from ..intents import Intent, PROMPT_TEMPLATES
from ._shared import (
    chunks_to_text,
    collect_filenames,
    format_context,
    guess_topic,
    safe_chat,
)


# chunks 为空时返回的统一提示（任务规约）
_NO_CHUNK_MSG = "在你的上传资料中未找到相关内容"


def handle(learner_id: str, query: str, retrieved_chunks: List[dict], llm) -> str:
    """文件问答 — 4 个 handler 之一，统一接口。

    Parameters
    ----------
    learner_id : str
        当前学生标识；本 handler 不直接使用（retriever 已按 learner 检索），
        但保留参数以便将来按 learner 注入上下文（如学段、学科）。
    query : str
        用户原始问题。
    retrieved_chunks : list of dict
        由调用方（T9 server）通过 retriever.search(query, top_k) 检索得到；
        每项 ``{doc_name, chunk_index, text, score}``。
    llm :
        PAEG 的 LLM 对象（AdapterLLM 或 MockModelAPI），
        必须有 ``chat(system, messages, max_tokens)`` 方法。

    Returns
    -------
    str
        最终回答；任何情况下都不抛异常、不返回 None。
    """
    # ---- 1. 空 chunks 直接返回规约文案 ----
    if not retrieved_chunks:
        return _NO_CHUNK_MSG

    # ---- 2. 组装 prompt ----
    tpl = PROMPT_TEMPLATES[Intent.FILE_QA]
    context = format_context(retrieved_chunks)
    filename = collect_filenames(retrieved_chunks)
    topic = guess_topic(query)
    system = tpl["system"]
    user = tpl["user"].format(
        filename=filename, topic=topic, query=query or "(未提供问题)", context=context
    )

    # ---- 3. 调 LLM ----
    reply = safe_chat(llm, system=system, user=user, max_tokens=800)

    # ---- 4. 兜底：LLM 失败 / 返回空 → 拼 chunks 原文 ----
    if not reply:
        fallback = chunks_to_text(retrieved_chunks, max_chars=500)
        if not fallback or fallback == "（暂无文件片段可显示）":
            return _NO_CHUNK_MSG
        return f"（LLM 暂不可用，以下为检索到的原文片段供参考）\n\n{fallback}"
    return reply


__all__ = ["handle"]