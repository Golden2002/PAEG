# -*- coding: utf-8 -*-
"""§3.58 教学主题栈（LRU，max=5）——通用栈操作，与具体主题解耦。

Oracle 方案：detour 入栈、revisit 恢复（移 cursor 不删）、off_topic 不入栈。
SESSIONS 存 concept_history 列表 + topic_stack_cursor；本模块提供纯函数操作。
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

MAX_STACK = 5  # 主题栈上限（防 prompt token 爆炸）


def make_entry(concept: str, subject: str = "", intent: str = "",
               summary: str = "") -> Dict[str, Any]:
    """新建栈项。"""
    return {
        "concept_id": str(uuid.uuid4()),
        "concept": concept,
        "subject": subject,
        "intent": intent,
        "summary": summary[:30],  # 防 token 爆炸
        "ts": 0.0,  # 由调用方写实际时间戳（保持纯函数）
    }


def push(history: List[dict], entry: dict) -> List[dict]:
    """detour 入栈：新主题推到栈顶；同 concept 更新不重复。超限丢最旧。"""
    h = list(history)
    for i, e in enumerate(h):
        if e.get("concept") == entry.get("concept"):
            h.pop(i)
            break
    h.append(entry)
    return h[-MAX_STACK:]


def find(history: List[dict], concept: str) -> Optional[dict]:
    """按 concept 名查找（revisit 用）。"""
    for e in reversed(history):
        if e.get("concept") and concept and e["concept"] in concept:
            return e
        if e.get("concept") and concept and concept in e["concept"]:
            return e
    return None


def recover(history: List[dict], concept: str) -> List[dict]:
    """revisit 恢复：把命中的主题移到栈顶（cursor 语义），不删除。"""
    e = find(history, concept)
    if e is None:
        return list(history)
    h = [x for x in history if x["concept_id"] != e["concept_id"]]
    h.append(e)
    return h


def summarize(entry: dict, fallback: str = "") -> str:
    """栈项摘要（≤30 字，保留 concept 名供绕回识别）。"""
    return entry.get("summary") or fallback or entry.get("concept", "")
