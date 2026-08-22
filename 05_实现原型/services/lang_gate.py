# -*- coding: utf-8 -*-
"""语言规范守门（v0.66 ⭐ L0+L1+L2 三层接入生成链路）。

用户要求：讲义/讲稿/视频/PPT 等**生成内容**也要过语言规范处理，用最规范的语言。
- L0：polish_text（AI 味/省略句/动宾搭配修正，规则+refine）
- L1：提示词层语言规范约束（LANGUAGE_STYLE 注入，由各生成函数自行拼入）
- L2：refiner.refine 深度矫正（薇依语料多轮 Self-Refine）

本模块提供统一入口：生成内容产出后调 gate_content() 做 L0+L2 双层修正。
"""
from __future__ import annotations

from typing import Optional


def lang_gate_content(text: str, context: str = "", apply_l2: bool = True) -> str:
    """生成内容语言规范守门（L0 + L2）。

    - L0 polish：AI 味检测 + 省略句 + 动宾搭配 → 触发 refine
    - L2 refine：AI 味信号强时，用薇依语料多轮 Self-Refine 深度矫正
    任一层异常 → 静默回退原文（不阻塞生成）。
    """
    if not text or not text.strip():
        return text
    _out = text
    # ── L0-0：病句确定性修正（v0.71 ⭐ 规则兜底，不依赖 AI 味检测）──
    try:
        from language_refiner import fix_known_gaffes
        _out = fix_known_gaffes(_out)
    except Exception:
        pass
    # ── L0：基础语言修正 ──
    try:
        from services.polish import polish_text
        _out = polish_text(_out, context=context)
    except Exception:
        pass
    # ── L2：AI 味深度矫正（仅当仍有明显信号）──
    if apply_l2:
        try:
            from infra.runtime import get_paeg
            from ai_taste_detector import detect_ai_taste
            _paeg = get_paeg()
            if _paeg is not None and _paeg.refiner is not None:
                try:
                    _sig = detect_ai_taste(_out)
                    if getattr(_sig, 'ai_likelihood', 0) >= 0.45:
                        _refined = _paeg.refiner.refine(_out, context=context, max_rounds=1)
                        if _refined:
                            _out = _refined
                except Exception:
                    pass
        except Exception:
            pass
    # ── 最终收口：病句规则再跑一遍（refine 改写可能重新引入悬空'听着你'）──
    try:
        from language_refiner import fix_known_gaffes
        _out = fix_known_gaffes(_out)
    except Exception:
        pass
    return _out


def lang_gate_short(text: str, context: str = "") -> str:
    """短文本语言守门（讲稿单段/要点）：仅 L0，快路径。"""
    if not text or not text.strip():
        return text
    try:
        from language_refiner import fix_known_gaffes
        text = fix_known_gaffes(text)
    except Exception:
        pass
    try:
        from services.polish import polish_text
        _out = polish_text(text, context=context)
    except Exception:
        return text
    # 最终收口：polish/refine 改写后规则再跑一遍（保证'听着你'不变量）
    try:
        from language_refiner import fix_known_gaffes
        return fix_known_gaffes(_out)
    except Exception:
        return _out
