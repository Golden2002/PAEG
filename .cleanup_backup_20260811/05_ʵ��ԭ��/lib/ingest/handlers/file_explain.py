# -*- coding: utf-8 -*-
"""
file_explain.py  -  文件讲解 handler（v0.21.5）

职责
----
处理 ``Intent.FILE_EXPLAIN``：用户说"按我上传的讲义讲 X"。

要求（系统提示词侧已规约）
------------------------
1. 区分两层内容：【原文】逐条引用文件原句；【讲解】给出通俗解释/背景/类比。
2. 任何扩展必须明确标注为"【讲解·扩展】"，不得冒充原文。
3. 鼓励 1-2 个贴近学生生活的例子。
4. 文件中确实没有的部分可坦诚说明。

失败兜底
--------
LLM 失败 → 用 chunks 原文拼一个简易讲解模板（带【原文】标签）。
chunks 为空 → 返回明确的"未检索到讲解素材"提示。
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


_NO_CHUNK_MSG = "在你的上传资料中未找到相关内容，无法讲解"


def handle(learner_id: str, query: str, retrieved_chunks: List[dict], llm) -> str:
    """文件讲解 — 4 个 handler 之一，统一接口。

    Parameters
    ----------
    learner_id : str
        当前学生标识；保留以便按 learner 注入上下文。
    query : str
        用户原始请求（可能含讲解主题 + 学生上下文）。
    retrieved_chunks : list of dict
        调用方通过 retriever.search(query, top_k) 检索得到。
    llm :
        PAEG LLM 对象（AdapterLLM 或 MockModelAPI）。

    Returns
    -------
    str
        最终讲解文本；任何情况下都不抛异常、不返回 None。
    """
    if not retrieved_chunks:
        return _NO_CHUNK_MSG

    tpl = PROMPT_TEMPLATES[Intent.FILE_EXPLAIN]
    context = format_context(retrieved_chunks)
    filename = collect_filenames(retrieved_chunks)
    topic = guess_topic(query)
    system = tpl["system"]
    user = tpl["user"].format(
        filename=filename, topic=topic, query=query or "(未提供主题)", context=context
    )

    reply = safe_chat(llm, system=system, user=user, max_tokens=1200)

    if not reply:
        # 兜底：把 chunks 用【原文】标签拼起来，再加一句"讲解待补"
        fallback = chunks_to_text(retrieved_chunks, max_chars=600)
        if not fallback or fallback == "（暂无文件片段可显示）":
            return _NO_CHUNK_MSG
        return (
            "（LLM 暂不可用，先给你看原文片段）\n\n"
            "【原文】\n"
            f"{fallback}\n\n"
            "【讲解】\n"
            "（讲解部分需要 LLM 支持；建议你参考以上原文，或稍后再试。）"
        )
    return reply


__all__ = ["handle"]