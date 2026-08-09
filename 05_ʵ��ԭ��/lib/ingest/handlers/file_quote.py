# -*- coding: utf-8 -*-
"""
file_quote.py  -  原文摘录 handler（v0.21.5）

职责
----
处理 ``Intent.FILE_QUOTE``：用户要"原文"。

**关键设计：不依赖 LLM 生成**
---------------------------------
按任务规约，``file_quote`` **必须**优先从 ``retrieved_chunks`` 直接提取原文，
逐字返回（标注文件名+块号），而**不**走 LLM 生成。

原因：
1. LLM 生成可能改写 / 合并 / 补全标点 — 违反"严格逐字"。
2. 用户要的是原文，自己检索的 chunks 才是最权威的"原文"。
3. 没有 LLM 也能工作。

策略：
    * ``retrieved_chunks`` 为空 → 返回"未找到相关原文"
    * 用 ``filter_chunks_by_query`` 按 query 关键词过滤 chunks；
      **若过滤结果为空**，则退而求其次，**返回所有 retrieved_chunks 的原文**
      （因为既然检索器都返回了，至少是相关的；比空字符串有用）。
    * 把过滤后的 chunks 渲染为带【文件名 + 段号】的原文。
"""
from __future__ import annotations

from typing import List

from ._shared import filter_chunks_by_query, quote_render


_NO_HIT_MSG = "未找到相关原文"


def handle(learner_id: str, query: str, retrieved_chunks: List[dict], llm=None) -> str:
    """原文摘录 — 4 个 handler 之一，统一接口。

    Parameters
    ----------
    learner_id : str
        当前学生标识；本 handler 不使用。
    query : str
        用户原始请求（用于按关键词过滤 chunks）。
    retrieved_chunks : list of dict
        调用方通过 retriever.search(query, top_k) 检索得到；
        每项 ``{doc_name, chunk_index, text, ...}``。
    llm : optional
        **保留参数以保持统一接口**；本 handler 不调用 LLM。

    Returns
    -------
    str
        带【文件名 + 段号】的原文摘录；找不到则返回规约文案。
        不抛异常、不返回 None。
    """
    # ---- 1. 无 chunks ----
    if not retrieved_chunks:
        return _NO_HIT_MSG

    # ---- 2. 按 query 关键词过滤 ----
    matched = filter_chunks_by_query(retrieved_chunks, query)

    # ---- 3. 过滤结果为空 → 退而求其次返回所有 chunks 原文 ----
    #   (retriever 已经筛过相关性，整段原文至少是相关的)
    if not matched:
        rendered = quote_render(list(retrieved_chunks))
        if not rendered:
            return _NO_HIT_MSG
        return (
            "（未严格匹配关键词，按检索器返回的相关片段逐字列出供参考）\n\n"
            f"{rendered}"
        )

    # ---- 4. 渲染带定位的原文 ----
    return quote_render(matched)


__all__ = ["handle"]