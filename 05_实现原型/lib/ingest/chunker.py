"""
chunker.py — 文本分块器（v0.21.5）

职责：把 readers 抽出来的完整文本切成 ≤max_chars 的块，相邻块重叠 overlap 字符；
      中文优先按句号/感叹号/问号切句，再按 max_chars 兜底切。

设计要点：
1. 段落优先：用 \\n\\n / \\n 分隔出"自然段"，对每段按句子窗口打包
2. 中文按句切：。！？视为句号位置（中文里标点后通常直接接下一句，无空格）
3. 英文按句切：. ! ? 后跟空白视为句号位置
4. 每块硬上限 max_chars；最后一块可以小于上限
5. 块间重叠 overlap 字符（从上一块尾部复制前缀到下一块开头）
6. 空文本 / max_chars<=0 返回 []，不抛异常
7. chunk_documents 接收 readers.read_corpus_full 的输出，附加元数据
"""
from __future__ import annotations

import re
from typing import List

# 任意空白
_WS = re.compile(r"\s+")

# 中文句末标点：。！？ 全角；（含句末并存的 ！！。 等）
# 用 finditer 扫描（而不是 split+lookahead），因为中文标点后通常无空白，直接切更稳
_CN_PUNCT = re.compile(r"[。！？!?]+\s*")
# 英文句末标点：. ! ? 后跟空白（避免误切小数点/缩写）
_EN_PUNCT = re.compile(r"[.!?]+\s+")


def _split_sentences(paragraph: str) -> List[str]:
    """把一段文本按中英文句末切句。

    中文标点直接切（标点后通常无空白）；英文标点要求后跟空白才切。
    切完后把标点保留在原句尾部。
    """
    if not paragraph or not paragraph.strip():
        return []

    # 先按中文标点切：先 findall 标点位置，再按位置切片
    sentences: List[str] = []
    buf = ""
    i = 0
    text = paragraph
    n = len(text)
    while i < n:
        ch = text[i]
        buf += ch
        # 是中文句末标点？
        if ch in "。！？":
            # 吞掉可能的尾部空白（含半角/全角空格/换行）
            j = i + 1
            while j < n and text[j] in (" ", "　", "\t", "\n", "\r"):
                buf += text[j]
                j += 1
            sentences.append(buf.strip())
            buf = ""
            i = j
            continue
        # 是英文句末标点且后面是空白？
        if ch in ".!?" and i + 1 < n and text[i + 1].isspace():
            buf += text[i + 1]
            i += 2
            sentences.append(buf.strip())
            buf = ""
            continue
        i += 1
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


def _pack_sentences_into_chunks(sentences: List[str], max_chars: int) -> List[str]:
    """贪心打包：把句子塞进当前块，直到加上下一句会超 max_chars 才换块。"""
    chunks: List[str] = []
    buf: List[str] = []
    cur_len = 0
    for s in sentences:
        s_len = len(s)
        # 单句本身就超过 max_chars → 单独成块（硬切备用，但实际不应发生）
        if s_len >= max_chars:
            if buf:
                chunks.append("".join(buf))
                buf = []
                cur_len = 0
            chunks.append(s[:max_chars])
            continue
        # 加上下句就超 → 先 flush 当前块
        if cur_len + s_len > max_chars and buf:
            chunks.append("".join(buf))
            buf = []
            cur_len = 0
        buf.append(s)
        cur_len += s_len
    if buf:
        chunks.append("".join(buf))
    return chunks


def _add_overlap(chunks: List[str], overlap: int) -> List[str]:
    """在块与块之间复制 overlap 字符前缀（从上一块尾部）。"""
    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    out: List[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        if len(prev) > overlap:
            tail = prev[-overlap:]
        else:
            tail = prev
        out.append(tail + chunks[i])
    return out


def chunk_text(text: str, max_chars: int = 400, overlap: int = 50) -> List[str]:
    """把一整段文本切成 ≤max_chars 的块，相邻块重叠 overlap 字符。

    切分策略：
    1. 按 \\n\\n 或 \\n 分段
    2. 每段按中英文句末切句（中文标点直接切，英文标点后跟空白才切）
    3. 贪心打包句子成块（每块 ≤max_chars）
    4. 块间重叠 overlap 字符

    返回：list[str]；空文本返回 []
    """
    if not text or not text.strip():
        return []
    if max_chars <= 0:
        max_chars = 400
    overlap = max(0, overlap)

    # 段落切分（支持连续换行作段分隔）
    paragraphs = re.split(r"\n\s*\n", text)
    all_sentences: List[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # 段落内的多余空白折叠成单空格
        para = _WS.sub(" ", para)
        sents = _split_sentences(para)
        all_sentences.extend(sents)

    if not all_sentences:
        return []

    base_chunks = _pack_sentences_into_chunks(all_sentences, max_chars)
    if overlap > 0 and len(base_chunks) > 1:
        return _add_overlap(base_chunks, overlap)
    return base_chunks


def chunk_documents(
    docs: List[dict],
    max_chars: int = 400,
    overlap: int = 50,
) -> List[dict]:
    """批量分块：把 readers.read_corpus_full 输出（[{path,name,type,text,ok,chars}, ...]）
    切成带元数据的块列表 [{doc_name, doc_path, doc_type, chunk_index, total_chunks, text, chars}, ...]。

    行为约定：
    - 只处理 ok=True 的文档；ok=False 跳过
    - 空文档跳过
    - 每个文档独立 chunk_index，从 0 开始
    """
    out: List[dict] = []
    for doc in docs or []:
        if not isinstance(doc, dict):
            continue
        if not doc.get("ok"):
            continue
        text = doc.get("text") or ""
        if not text.strip():
            continue
        chunks = chunk_text(text, max_chars=max_chars, overlap=overlap)
        total = len(chunks)
        for idx, ck in enumerate(chunks):
            out.append({
                "doc_name": doc.get("name", ""),
                "doc_path": doc.get("path", ""),
                "doc_type": doc.get("type", "other"),
                "chunk_index": idx,
                "total_chunks": total,
                "text": ck,
                "chars": len(ck),
            })
    return out


__all__ = ["chunk_text", "chunk_documents"]