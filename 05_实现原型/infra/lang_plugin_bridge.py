# -*- coding: utf-8 -*-
"""infra/lang_plugin_bridge.py — PAEG ↔ paeg-lang-style 插件唯一适配层（Oracle R18/R20）。

设计目标（R18）：PAEG 主项目与语言规范插件之间的**唯一适配层**——
主项目所有语言规范调用（gate_content / gate_short / fix_known_gaffes /
get_style_prompt / make_refiner / detect_ai_taste / check_ellipsis）统一走本桥。

设计目标（R20）：插件未挂载（import 失败）时**静默回退到 PAEG 原实现**
（services/lang_gate.py / language_refiner.py / prompts.LANGUAGE_STYLE 三处原文件
永不删除——"千万不要破坏代码和文件"铁律的工程化兑现）。

加载策略：
1. 优先尝试 import paeg_lang_style（插件包）
2. 失败 → 回退原 PAEG 实现（lazy import，与原行为 100% 等价）
3. 所有异常静默吞掉，不阻塞生成链路

用法（PAEG 内各调用点改造示例）：
    # 原：from services.lang_gate import lang_gate_content
    from infra.lang_plugin_bridge import gate_content as lang_gate_content

    # 原：from prompts import LANGUAGE_STYLE
    from infra.lang_plugin_bridge import get_style_prompt as LANGUAGE_STYLE_builder
"""
from __future__ import annotations

from typing import Optional

# 插件可用标记（模块级缓存，避免每次调用重复尝试 import）
_plugin = None
_plugin_ready = False
_tried = False


def _load_plugin():
    """尝试加载插件包；失败 → None（静默回退）。"""
    global _plugin, _plugin_ready, _tried
    if _tried:
        return _plugin if _plugin_ready else None
    _tried = True
    try:
        import paeg_lang_style as _p
        _plugin = _p
        _plugin_ready = True
        return _plugin
    except Exception:
        _plugin = None
        _plugin_ready = False
        return None


def plugin_active() -> bool:
    """插件是否已挂载（供日志/观测用）。"""
    return _load_plugin() is not None


# ─────────────────────────────────────
# 对外 API（与 PAEG 原调用点签名对齐）
# ─────────────────────────────────────

def gate_content(text: str, context: str = "", apply_l2: bool = True,
                 refiner=None, polish_fn=None) -> str:
    """生成内容语言规范守门（L0+L2）。插件可用 → 插件实现；否则 → 原 services/lang_gate。"""
    if not text or not text.strip():
        return text
    p = _load_plugin()
    if p is not None:
        return p.gate_content(text, context=context, apply_l2=apply_l2,
                              refiner=refiner, polish_fn=polish_fn)
    # ── 回退：PAEG 原实现（services/lang_gate.py）──
    try:
        from services.lang_gate import lang_gate_content
        return lang_gate_content(text, context=context, apply_l2=apply_l2)
    except Exception:
        return text


def gate_short(text: str, context: str = "", refiner=None, polish_fn=None) -> str:
    """短文本语言守门（仅 L0 快路径）。"""
    if not text or not text.strip():
        return text
    p = _load_plugin()
    if p is not None:
        return p.gate_short(text, context=context, refiner=refiner, polish_fn=polish_fn)
    try:
        from services.lang_gate import lang_gate_short
        return lang_gate_short(text, context=context)
    except Exception:
        return text


def fix_known_gaffes(text: str) -> str:
    """病句确定性修正（规则兜底）。"""
    p = _load_plugin()
    if p is not None:
        return p.fix_known_gaffes(text)
    try:
        from language_refiner import fix_known_gaffes as _f
        return _f(text)
    except Exception:
        return text


def check_ellipsis(text: str) -> list:
    """语法检查（省略句/动宾/介词/复合句）。"""
    p = _load_plugin()
    if p is not None:
        return p.check_ellipsis(text)
    return []


def get_style_prompt(section: str = "all") -> str:
    """获取语言风格系统提示词（替代 prompts.LANGUAGE_STYLE）。"""
    p = _load_plugin()
    if p is not None:
        return p.get_style_prompt(section)
    try:
        from prompts import LANGUAGE_STYLE
        return LANGUAGE_STYLE
    except Exception:
        return ""


def make_refiner(*, chat_fn=None, llm=None, corpus_path=None):
    """工厂：注入 chat_fn 创建 LanguageRefiner。

    插件可用 → 插件 refiner；否则 → PAEG 原 LanguageRefiner（chat_fn 缺省走 _safe_chat）。
    """
    p = _load_plugin()
    if p is not None:
        if chat_fn is None:
            raise TypeError("paeg-lang-style 插件要求注入 chat_fn")
        return p.make_refiner(chat_fn=chat_fn, llm=llm, corpus_path=corpus_path)
    try:
        from language_refiner import LanguageRefiner
        return LanguageRefiner(llm=llm, corpus_path=corpus_path, chat_fn=chat_fn)
    except Exception:
        return None


def detect_ai_taste(text: str):
    """AI 味检测。"""
    p = _load_plugin()
    if p is not None:
        return p.detect_ai_taste(text)
    try:
        from ai_taste_detector import detect_ai_taste as _d
        return _d(text)
    except Exception:
        return None


def forbidden_words_detect(text: str) -> list:
    """违禁词检测（插件专属能力；回退时用 AI_TELLS 列表）。"""
    p = _load_plugin()
    if p is not None:
        return p.ForbiddenWords().detect(text)
    try:
        from language_refiner import AI_TELLS
        return [w for w in AI_TELLS if w in text]
    except Exception:
        return []
