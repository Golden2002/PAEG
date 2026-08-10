# -*- coding: utf-8 -*-
"""v0.43 ⭐ 输出效果约束 · 3 位掩码信号采集（创新设计 v2）

从用户维度正交提取 3 个约束掩码位：
- 位0（组A=直接性）：用户明确要快/直接/给答案 → 取消风格组
- 位1（组B=情绪）：用户不耐烦/烦躁/要讲重点 → 取消温度组
- 位2（组C=深度）：用户要简洁/只讲定义 → 取消深度组

调用方：context_bundle 打包时 / 各模式端点构建 system 前。
"""
from __future__ import annotations

from typing import Tuple

# 组 A 信号词（用户要直接给答案/赶时间/别铺垫）
_A_KEYWORDS = (
    "直接", "别绕", "答案", "公式", "结论", "快说", "马上要",
    "告诉我", "给我", "怎么算", "定义", "是什么意思", "别铺垫", "要点",
)

# 组 B 信号词（用户不耐烦/烦躁/要讲重点——减少温度性表达）
_B_KEYWORDS = (
    "别安慰", "别啰嗦", "讲重点", "我懂", "别废话", "烦", "别哄我",
    "说重点", "直接说结果", "不用安慰",
)

# 组 C 信号词（用户要简洁/只讲定义/不要深入）
_C_KEYWORDS = (
    "简短", "简洁", "少说", "概括", "一句话", "只讲", "不要深入",
    "表面理解", "定义即可", "大概", "浅一点",
)


def detect_constraint_flags(
    user_text: str = "",
    key_need: str = "",
    mode: str = "",
    profile: dict | None = None,
    affection_signal: bool = False,
) -> Tuple[str, ...]:
    """从 4 类信号源正交提取 3 个掩码位。

    Args:
        user_text: 用户本轮输入
        key_need: 意图路由的 key_need（如 DIRECT_ANSWER / EMOTION_FIRST）
        mode: 当前对话模式
        profile: 用户画像（含 questionnaire_answers）
        affection_signal: 情绪拦截是否触发

    Returns:
        命中的位名元组（排序去重），如 ("A",) 或 ("A","C")。
        对应 _build_constraint_layers 的 constraint_flags。
    """
    flags = set()
    t = (user_text or "").strip()

    # ---- 组 A（直接性）：用户明确要直接答案 ----
    if key_need in ("DIRECT_ANSWER", "answer", "find_answer", "solve"):
        flags.add("A")
    if any(kw in t for kw in _A_KEYWORDS):
        flags.add("A")

    # ---- 组 B（情绪）：用户不耐烦/要讲重点 ----
    if any(kw in t for kw in _B_KEYWORDS):
        flags.add("B")

    # ---- 组 C（深度）：用户要简洁/只讲定义 ----
    try:
        _qa = (profile or {}).get("questionnaire_answers") or {}
        _depth = _qa.get("depth_pref") or ""
        if _depth == "basic":
            flags.add("C")
    except Exception:
        pass
    if any(kw in t for kw in _C_KEYWORDS):
        flags.add("C")

    return tuple(sorted(flags))


if __name__ == "__main__":
    # 自检
    print(detect_constraint_flags("直接告诉我答案，别铺垫"))
    print(detect_constraint_flags("你好"))
    print(detect_constraint_flags("别安慰我，讲重点"))
    print(detect_constraint_flags("简短点，只讲定义"))
    print(detect_constraint_flags(profile={'questionnaire_answers': {'depth_pref': 'basic'}}))
