"""
4 种世界观的自动切换。
"""

THEME_TONE_MAP = {
    # 理科：严谨
    "physics": ("rigorous_cold", {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15}, 2),
    "math": ("rigorous_cold", {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15}, 2),
    "chemistry": ("rigorous_cold", {1: 0.10, 2: 0.60, 3: 0.15, 4: 0.15}, 2),
    "biology": ("balanced", {1: 0.15, 2: 0.45, 3: 0.25, 4: 0.15}, 2),
    "geography": ("balanced", {1: 0.15, 2: 0.40, 3: 0.30, 4: 0.15}, 2),
    "logic": ("rigorous_cold", {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15}, 2),
    "cs": ("rigorous_cold", {1: 0.10, 2: 0.55, 3: 0.15, 4: 0.20}, 2),
    # 文科/人文：沉思
    "literature": ("contemplative", {1: 0.20, 2: 0.10, 3: 0.60, 4: 0.10}, 3),
    "chinese": ("contemplative", {1: 0.15, 2: 0.20, 3: 0.50, 4: 0.15}, 3),
    "history": ("contemplative", {1: 0.15, 2: 0.30, 3: 0.40, 4: 0.15}, 3),
    "aesthetics": ("contemplative", {1: 0.20, 2: 0.10, 3: 0.60, 4: 0.10}, 3),
    "phenomenology": ("contemplative", {1: 0.20, 2: 0.10, 3: 0.60, 4: 0.10}, 3),
    "philosophy": ("contemplative", {1: 0.25, 2: 0.20, 3: 0.45, 4: 0.10}, 3),
    # 伦理/关系：关怀
    "ethics": ("warm_caring", {1: 0.50, 2: 0.20, 3: 0.20, 4: 0.10}, 1),
    "relationship": ("warm_caring", {1: 0.50, 2: 0.20, 3: 0.20, 4: 0.10}, 1),
    "character": ("warm_caring", {1: 0.50, 2: 0.20, 3: 0.20, 4: 0.10}, 1),
    "politics": ("balanced", {1: 0.20, 2: 0.40, 3: 0.25, 4: 0.15}, 2),
    # 语言学习：务实
    "english": ("pragmatic", {1: 0.10, 2: 0.30, 3: 0.15, 4: 0.45}, 4),
    "french": ("pragmatic", {1: 0.10, 2: 0.30, 3: 0.15, 4: 0.45}, 4),
    "german": ("pragmatic", {1: 0.10, 2: 0.35, 3: 0.15, 4: 0.40}, 4),
    "japanese": ("pragmatic", {1: 0.10, 2: 0.30, 3: 0.15, 4: 0.45}, 4),
    # 职业/技能
    "career": ("pragmatic", {1: 0.10, 2: 0.20, 3: 0.10, 4: 0.60}, 4),
    "skill": ("pragmatic", {1: 0.10, 2: 0.20, 3: 0.10, 4: 0.60}, 4),
    "application": ("pragmatic", {1: 0.10, 2: 0.20, 3: 0.10, 4: 0.60}, 4),
    "default": ("balanced", {1: 0.20, 2: 0.35, 3: 0.35, 4: 0.10}, None)
}


def select_tone(theme: str) -> dict:
    """根据主题选择教学语气。

    返回的 system_suffix 为可读教学风格描述（供参考）；真正的提示词由 prompts.py 提供。
    """
    if theme in THEME_TONE_MAP:
        tone, ratio, dominant = THEME_TONE_MAP[theme]
    else:
        tone, ratio, dominant = THEME_TONE_MAP["default"]

    suffix = {
        "rigorous_cold": "说话严谨、直白，重证据和逻辑，但不冰冷、不端着。",
        "contemplative": "语气沉静，多引导对方自己体会，留出思考空间。",
        "warm_caring": "语气温和、像朋友一样关心，但不肉麻、不过度安慰。",
        "pragmatic": "语气务实，像教练下指令，直接说'你这样做'。",
        "balanced": "语气自然、平实，怎么顺怎么讲。"
    }.get(tone, "")

    return {
        "tone": tone,
        "ratio": ratio,
        "dominant_worldview": dominant,
        "system_suffix": suffix
    }
