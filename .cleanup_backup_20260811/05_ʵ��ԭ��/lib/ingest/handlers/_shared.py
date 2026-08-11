# -*- coding: utf-8 -*-
"""
_shared.py  -  4 个 file handler 共用的内部工具函数（v0.21.5）

职责
----
1. ``format_context``   把 retriever.search() 返回的 chunk 列表格式化为 prompt 中
                        的 ``{context}`` 占位内容（带【文件名 + 段号】定位）。
2. ``collect_filenames``  从 chunks 里聚合去重后的文件名，给 ``{filename}`` 占位符。
3. ``guess_topic``       从 query 中粗略提取关键词话题，给 ``{topic}`` 占位符。
4. ``safe_chat``         统一 LLM 调用入口 ——
                          * 若 llm 有 ``chat(system, messages, max_tokens)`` 则走它
                          * 若 llm 不支持 chat 或抛异常，返回 ``""``（handler 兜底）
                        所有 4 个 handler 都不会让 LLM 失败冒泡到 server。
5. ``chunks_to_text``   LLM 失败时把 chunks 拼成可读的兜底文本。

内部模块，不在 __all__ 中暴露给调用方。
"""
from __future__ import annotations

from typing import Iterable, List


# ---------------------------------------------------------------------------
# 占位符格式化
# ---------------------------------------------------------------------------
def format_context(retrieved_chunks: Iterable[dict]) -> str:
    """把 retriever 返回的 chunk 列表格式化成 prompt 中的 {context} 字符串。

    每个 chunk 渲染为：
        - 《filename》第 N 段 (score=0.123)
        text
        （空行分隔）

    空列表 / 无 text → 返回一个明确"未检索到"的标记文本。
    """
    lines: List[str] = []
    n = 0
    for ck in retrieved_chunks or []:
        if not isinstance(ck, dict):
            continue
        text = (ck.get("text") or "").strip()
        if not text:
            continue
        n += 1
        name = ck.get("doc_name") or ck.get("name") or "未知文件"
        idx = ck.get("chunk_index", 0)
        score = ck.get("score")
        head = f"- 《{name}》第 {idx} 段"
        if isinstance(score, (int, float)):
            head += f" (score={score:.3f})"
        lines.append(head)
        lines.append(text)
        lines.append("")  # 空行分隔

    if n == 0:
        return "（未检索到任何文件片段）"
    return "\n".join(lines).rstrip()


def collect_filenames(retrieved_chunks: Iterable[dict]) -> str:
    """从 chunks 里聚合并去重文件名，给 {filename} 占位符。

    返回值：
        * 单文件  → "《foo.md》"
        * 多文件  → "《a.md》、《b.docx》"
        * 空      → "未上传文件"
    """
    seen: List[str] = []
    seen_lower: set = set()
    for ck in retrieved_chunks or []:
        if not isinstance(ck, dict):
            continue
        name = (ck.get("doc_name") or ck.get("name") or "").strip()
        if not name:
            continue
        lname = name.lower()
        if lname not in seen_lower:
            seen_lower.add(lname)
            seen.append(name)
    if not seen:
        return "未上传文件"
    return "、《".join(f"《{n}》" for n in seen)


def guess_topic(query: str) -> str:
    """从用户 query 中粗略提取关键词话题，给 {topic} 占位符。

    策略：
            * 去掉句末标点
            * 截断到前 40 个字符（够用即可，避免 user prompt 被超长 query 撑爆）
            * 空 / 全空白 → "(未指定)"
    """
    if not query:
        return "(未指定)"
    q = query.strip()
    if not q:
        return "(未指定)"
    # 去掉中文全角句末标点 + 英文句末标点
    for tail in ("。", "！", "？", ".", "!", "?", "；", ";", "\n"):
        if q.endswith(tail):
            q = q[: -len(tail)].rstrip()
    if not q:
        return "(未指定)"
    return q[:40]


# ---------------------------------------------------------------------------
# LLM 调用：统一 try/except，永不抛
# ---------------------------------------------------------------------------
def safe_chat(llm, system: str, user: str, max_tokens: int = 800) -> str:
    """调用 llm.chat()，失败返回空串（让 handler 走兜底）。

    设计原则：
        * **绝不抛异常** — LLM 调用失败 / 超时 / 接口不存在都返回 ``""``，
          handler 看到空串会自己拼接 chunks 兜底文本。
        * 支持 ``llm.chat(system, messages=[...], max_tokens=...)`` 标准接口；
          若 llm 缺 chat 属性则直接返回空串。
    """
    if llm is None:
        return ""
    chat_fn = getattr(llm, "chat", None)
    if chat_fn is None or not callable(chat_fn):
        return ""
    try:
        reply = chat_fn(
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
        )
    except Exception:
        return ""
    # LLM 可能返回 None（如 _safe_chat 风格），统一空串
    if reply is None:
        return ""
    return str(reply).strip()


# ---------------------------------------------------------------------------
# LLM 失败兜底：直接拼 chunks 文本
# ---------------------------------------------------------------------------
def chunks_to_text(retrieved_chunks: Iterable[dict], max_chars: int = 500) -> str:
    """把 chunks 拼成兜底文本，最多 max_chars 字符。

    用于 ``file_qa`` / ``file_restructure`` / ``file_explain`` 在 LLM 失败时
    仍然能返回基于文件原文的内容。
    """
    buf: List[str] = []
    total = 0
    for ck in retrieved_chunks or []:
        if not isinstance(ck, dict):
            continue
        text = (ck.get("text") or "").strip()
        if not text:
            continue
        name = ck.get("doc_name") or ck.get("name") or "未知文件"
        idx = ck.get("chunk_index", 0)
        piece = f"《{name}》第 {idx} 段：{text}"
        if total + len(piece) > max_chars and buf:
            break
        buf.append(piece)
        total += len(piece)
    if not buf:
        return "（暂无文件片段可显示）"
    return "\n\n".join(buf)


# ---------------------------------------------------------------------------
# quote 专用：按 query 关键词从 chunks 里筛包含 query 关键词的 chunk
# ---------------------------------------------------------------------------
def filter_chunks_by_query(retrieved_chunks: Iterable[dict], query: str) -> List[dict]:
    """从 chunks 里过滤出包含 query 中任意**子串**的 chunk。

    设计：
        * 不做 jieba 分词（保持轻量），直接用 query 子串匹配 chunk.text。
        * 如果 query 为空或一个 chunk 都没匹配上，返回空列表（caller 决定 fallback）。
        * 匹配大小写不敏感；中英文混排都安全。
    """
    if not query or not (query := query.strip()):
        return []
    q_lower = query.lower()
    # 拆词：中文按 2-gram + 整词，英文按空格切
    needles = {q_lower}
    # 中文 2-gram 拆分（保证 "导数" 命中 "瞬时变化率导数"）
    if any("\u4e00" <= ch <= "\u9fff" for ch in q_lower):
        cleaned = "".join(ch for ch in q_lower if not ch.isspace())
        for i in range(len(cleaned) - 1):
            needles.add(cleaned[i : i + 2])
    out: List[dict] = []
    for ck in retrieved_chunks or []:
        if not isinstance(ck, dict):
            continue
        text = (ck.get("text") or "")
        text_lower = text.lower()
        if any(n in text_lower for n in needles if n):
            out.append(ck)
    return out


def quote_render(chunks: List[dict]) -> str:
    """把过滤后的 chunks 渲染为带文件名+段号的原文摘录字符串。"""
    if not chunks:
        return ""
    out: List[str] = []
    for ck in chunks:
        name = ck.get("doc_name") or ck.get("name") or "未知文件"
        idx = ck.get("chunk_index", 0)
        text = (ck.get("text") or "").strip()
        if not text:
            continue
        out.append(f"《{name}》第 {idx} 段：\n{text}")
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# 仅供内部使用，不导出
# ---------------------------------------------------------------------------
__all__ = [
    "format_context",
    "collect_filenames",
    "guess_topic",
    "safe_chat",
    "chunks_to_text",
    "filter_chunks_by_query",
    "quote_render",
]