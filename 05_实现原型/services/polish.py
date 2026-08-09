"""polish.py — 全局语言质量修正（LanguageRefiner 守门）。

v0.43 提取自 server.py（v0.40.4 L329-362 原 _polish_text）。

职责
----
所有输出端点统一过 `LanguageRefiner`：
- AI 味检测（ai_taste_detector.detect_ai_taste）
- 省略句检查（paeg.refiner._check_ellipsis）
- 满足触发条件时调用 `paeg.refiner.refine` 重写

依赖
----
- `infra.runtime.get_paeg`（函数体内懒加载）
- `ai_taste_detector.detect_ai_taste`（函数体内 import）

行为
----
与 v0.40.4 内联实现 100% 等价：
- 文本为空 → 直接返回原文
- paeg 不可用或 refiner 不可用 → 直接返回原文
- AI 概率 < 0.4 且无省略句问题 → 直接返回原文（成本考虑）
- 触发重写 → 返回 refined；refined 为空仍回退原文
- 任何异常 → 静默忽略 + 返回原文
"""
from __future__ import annotations

from typing import Optional


def polish_text(text: str, context: str = "") -> str:
    """全局语言质量修正（v0.20）：所有输出端点统一过 LanguageRefiner。

    修正：无主语短语（不催你/先不急）、动宾搭配不当（带着重量）、
    AI 腔、省略句——保持风格的最小改动。
    纯规则生成/预存文本跳过 LLM 改写（成本考虑）。
    """
    if not text or not text.strip():
        return text
    try:
        from infra.runtime import get_paeg
        paeg = get_paeg()
        if paeg is not None and paeg.refiner is not None:
            # 仅对可能有问题的文本触发（AI 味 or 省略句 or 动宾搭配）
            from ai_taste_detector import detect_ai_taste
            try:
                sig = detect_ai_taste(text)
                ai_prob = sig.ai_likelihood
            except Exception:
                ai_prob = 0.2
            has_issues = False
            try:
                has_issues = len(paeg.refiner._check_ellipsis(text)) > 0
            except Exception as _e:
                print(f"[PAEG][services.polish] polish_text 异常忽略: {_e}")
                pass
                pass
            if ai_prob >= 0.4 or has_issues:
                refined = paeg.refiner.refine(text, context=context)
                if refined:
                    return refined
    except Exception as _e:
        print(f"[PAEG][services.polish] polish_text 异常忽略: {_e}")
        pass
        pass
    return text


# ─────────────────────────────────────
# v0.43 � 兼容别名：原 server.py 中 `_polish_text` 名称保持不变。
# server.py 改用 `from services.polish import polish_text, _polish_text`
# 其中 _polish_text = polish_text（仅为了不改调用点）。
# ─────────────────────────────────────
_polish_text = polish_text
