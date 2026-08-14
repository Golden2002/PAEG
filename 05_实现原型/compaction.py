# -*- coding: utf-8 -*-
"""v0.69+ §3.22 ⭐ compaction 上下文压缩守卫（借鉴 deepseek-harness compaction）。

语义：当对话历史/上下文超过阈值时，将较早范围压缩为摘要（保留最近原文），
防止 LLM 上下文窗口被历史撑爆（长会话痛点）。

与 memory_system 摘要压缩的区别：compaction 是"注入前强制守卫"（每次组上下文时检查），
memory_system 是"会话内自动压缩"（超阈值触发）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# 阈值：超过则压缩（消息对条数）
MAX_HISTORY_PAIRS = 10
# 保留最近原文条数
KEEP_RECENT = 6


def maybe_compact(history: list, llm=None, max_pairs: int = MAX_HISTORY_PAIRS,
                  keep_recent: int = KEEP_RECENT) -> list:
    """对对话历史做注入前压缩守卫。

    history: list[dict]（role/content 消息对，可能含 user/assistant 交替）
    超过 max_pairs 对时：早期消息用 LLM（或规则）压缩为摘要，保留最近 keep_recent 条原文。
    返回压缩后的历史（始终含最近原文 + 可选的早期摘要）。
    """
    if not history or len(history) <= max_pairs * 2:
        return history
    try:
        _early = history[:-(keep_recent * 2)]
        _recent = history[-(keep_recent * 2):]
        _summary = _summarize(_early, llm)
        if _summary:
            return [{"role": "system", "content": f"【早期对话摘要（compaction）】{_summary}"}] + _recent
        return _recent  # 摘要失败则只保留最近（安全降级）
    except Exception:
        return history[-keep_recent * 2:]


def _summarize(messages: list, llm=None) -> str:
    """早期消息 → 摘要（LLM 优先，失败用规则提取关键点）。"""
    _text = "\n".join(f"{m.get('role','?')}: {str(m.get('content',''))[:80]}" for m in messages[-30:])
    if llm is not None:
        try:
            from subagents import _safe_chat
            _sys = "你是对话摘要器。把下面的早期教学/对话压缩为 2-3 句摘要（保留：已讲概念、学生掌握情况、待办事项）。不要编造。"
            _r = _safe_chat(llm, _sys, f"对话片段：\n{_text[:1500]}", max_tokens=150)
            if _r and len(_r.strip()) >= 10:
                return _r.strip()[:300]
        except Exception:
            pass
    # 规则兜底：提取关键句（含概念词/问句）
    _kws = [l for l in _text.splitlines() if any(k in l for k in ("讲了", "概念", "定义", "？", "?", "掌握", "下一步"))][:5]
    return "；".join(l[:50] for l in _kws) or "（早期对话已压缩）"
