# -*- coding: utf-8 -*-
"""
file_restructure.py  -  文件结构重组 handler（v0.21.5）

职责
----
处理 ``Intent.FILE_RESTRUCTURE``：用户要把"笔记/讲义"重新组织成
"大纲 / 表格 / 思维导图式层级 / 概念卡片"等更清晰的结构。

要求（PROMPT_TEMPLATES 已规约）
------------------------------
1. 以文件原内容为唯一素材，不得引入文件外内容。
2. **保留全部要点**（关键定义 / 公式 / 举例 / 引用都不能丢）。
3. 优先 Markdown 层级标题 + 表格 + 要点列表。
4. 末尾可附【原文出处】。

兜底
----
LLM 失败 → 用 chunks 拼一个简易 Markdown 大纲骨架（"## 主题 / - 要点"）。
chunks 为空 → 返回明确的"未检索到可重组内容"提示。
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


_NO_CHUNK_MSG = "在你的上传资料中未找到可重组的内容"


def handle(learner_id: str, query: str, retrieved_chunks: List[dict], llm) -> str:
    """文件结构重组 — 4 个 handler 之一，统一接口。

    Parameters
    ----------
    learner_id : str
        当前学生标识；本 handler 不使用。
    query : str
        用户原始请求（可能含"大纲""表格""思维导图"等关键词）。
    retrieved_chunks : list of dict
        调用方通过 retriever.search(query, top_k) 检索得到。
    llm :
        PAEG LLM 对象。

    Returns
    -------
    str
        重组后的结构化文本（Markdown 优先）；任何情况下都不抛异常、不返回 None。
    """
    if not retrieved_chunks:
        return _NO_CHUNK_MSG

    tpl = PROMPT_TEMPLATES[Intent.FILE_RESTRUCTURE]
    context = format_context(retrieved_chunks)
    filename = collect_filenames(retrieved_chunks)
    topic = guess_topic(query)
    system = tpl["system"]
    user = tpl["user"].format(
        filename=filename, topic=topic, query=query or "(未指定)", context=context
    )

    reply = safe_chat(llm, system=system, user=user, max_tokens=1200)

    if not reply:
        # 兜底：把 chunks 拼成简易 Markdown 骨架
        fallback = chunks_to_text(retrieved_chunks, max_chars=800)
        if not fallback or fallback == "（暂无文件片段可显示）":
            return _NO_CHUNK_MSG
        return (
            "（LLM 暂不可用，以下为基于检索片段的简易骨架）\n\n"
            f"# {topic}\n\n"
            "## 要点（来自检索片段）\n\n"
            f"{fallback}\n\n"
            "## 说明\n\n"
            "如需更系统的层级 / 表格 / 思维导图，请稍后再试（依赖 LLM）。"
        )
    return reply


__all__ = ["handle"]