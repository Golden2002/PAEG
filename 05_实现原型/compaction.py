# -*- coding: utf-8 -*-
"""v0.69+ §3.22 ⭐ compaction 上下文压缩守卫（借鉴 deepseek-harness compaction）。

语义：当对话历史/上下文超过阈值时，将较早范围压缩为摘要（保留最近原文），
防止 LLM 上下文窗口被历史撑爆（长会话痛点）。

与 memory_system 摘要压缩的区别：compaction 是"注入前强制守卫"（每次组上下文时检查），
memory_system 是"会话内自动压缩"（超阈值触发）。

§3.42 W6 ⭐ 4-event 可观测：compaction 生命周期发 4 事件
- compaction/start    {bytes_before, strategy}
- compaction/measure  {ratio, pruned_chars}
- compaction/apply    {bytes_after, method}
- compaction/end      {duration_ms, turns_kept}
全部事件通过 emit_event_typed 自动挂 trace_id（§3.42 W2 全链路）。
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

# 阈值：超过则压缩（消息对条数）
MAX_HISTORY_PAIRS = 10
# 保留最近原文条数
KEEP_RECENT = 6


def _emit(event_type: str, data: Dict[str, Any]) -> None:
    """类型化事件发射（§3.42 W2 trace 自动挂载；失败静默，不影响压缩主流程）。"""
    try:
        from observability import emit_event_typed
        emit_event_typed(event_type, data=data)
    except Exception:
        # 可观测性是辅助；压缩主流程绝不能因事件失败而中断
        pass


def _bytes_of(messages: list) -> int:
    """计算 messages 的总字符数（bytes 的代理，避免误以为精确字节数）。"""
    return sum(len(str(m.get("content", ""))) for m in messages)


def maybe_compact(history: list, llm=None, max_pairs: int = MAX_HISTORY_PAIRS,
                  keep_recent: int = KEEP_RECENT) -> list:
    """对对话历史做注入前压缩守卫。

    history: list[dict]（role/content 消息对，可能含 user/assistant 交替）
    超过 max_pairs 对时：早期消息用 LLM（或规则）压缩为摘要，保留最近 keep_recent 条原文。
    返回压缩后的历史（始终含最近原文 + 可选的早期摘要）。

    §3.42 W6：压缩执行时发 4 事件（start → measure → apply → end），全程 trace_id 关联。
    """
    if not history or len(history) <= max_pairs * 2:
        return history

    # §3.42 W6 ⭐ 4-event lifecycle
    _t0 = time.time()
    bytes_before = _bytes_of(history)
    _emit("compaction/start", {
        "bytes_before": bytes_before,
        "strategy": "summary+keep_recent",
        "max_pairs": max_pairs,
        "keep_recent": keep_recent,
        "input_turns": len(history),
    })

    try:
        _early = history[:-(keep_recent * 2)]
        _recent = history[-(keep_recent * 2):]
        early_bytes = _bytes_of(_early)
        _summary = _summarize(_early, llm)
        pruned_chars = early_bytes - len(_summary or "")

        # compaction/measure（早期 vs 摘要 的压缩比）
        ratio = round(len(_summary or "") / max(early_bytes, 1), 4)
        _emit("compaction/measure", {
            "ratio": ratio,
            "pruned_chars": max(pruned_chars, 0),
            "early_bytes": early_bytes,
            "summary_len": len(_summary or ""),
        })

        if _summary:
            result = [{"role": "system", "content": f"【早期对话摘要（compaction）】{_summary}"}] + _recent
            method = "summary_with_recent"
        else:
            result = _recent  # 摘要失败则只保留最近（安全降级）
            method = "fallback_recent_only"

        bytes_after = _bytes_of(result)
        # compaction/apply
        _emit("compaction/apply", {
            "bytes_after": bytes_after,
            "ratio": round(bytes_after / max(bytes_before, 1), 4),
            "method": method,
            "summary_ok": bool(_summary),
        })

        # compaction/end
        _emit("compaction/end", {
            "duration_ms": round((time.time() - _t0) * 1000, 2),
            "turns_kept": len(_recent),
            "input_turns": len(history),
            "output_turns": len(result),
            "bytes_before": bytes_before,
            "bytes_after": bytes_after,
        })
        return result
    except Exception:
        # §3.42 W6：异常时仍发 end（标记失败），主路径安全降级
        _emit("compaction/end", {
            "duration_ms": round((time.time() - _t0) * 1000, 2),
            "turns_kept": min(keep_recent * 2, len(history)),
            "input_turns": len(history),
            "output_turns": len(history[-keep_recent * 2:]),
            "error": True,
        })
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