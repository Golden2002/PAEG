"""
PAEG AI 味检测器（v0.13）

基于 2024-2026 实证信号（eyesift/writehybrid/TextSight/Originality.ai）：
- 句长变异度（burstiness）：AI 句子长度均匀（CV<0.35），人类长短交替（CV>0.45）
- 过渡词密度：AI 密集使用 furthermore/moreover/in conclusion 等
- 三段式清单：AI 偏爱"三个要点"，人类（尤其薇依）用二/四/七
- 破折号滥用：AI 连用多个 em-dash
- 段落对称性：AI 段落等长，人类参差

用法：
    from ai_taste_detector import detect_ai_taste, AITasteSignals
    signals = detect_ai_taste(text)
    if signals.ai_likelihood > 0.5:  # 需要改写
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, asdict
from typing import List


# 常见 AI 痕迹信号词（来自实证清单）
AI_MARKERS = {
    "furthermore", "moreover", "additionally", "in addition",
    "it is worth noting", "it is important to note", "notably",
    "it should be noted", "it is essential to",
    "in conclusion", "to summarize", "in summary", "in essence",
    "leverage", "delve", "navigate", "utilize", "commence",
    "seamlessly", "cutting-edge", "transformative", "multifaceted",
    "robust", "comprehensive", "paramount",
    "it is clear that", "undoubtedly", "studies show that",
    "tapestry", "journey", "embark", "paradigm", "in the realm of",
    "when it comes to", "ultimately",
    # 中文 AI 痕迹
    "总的来说", "综上所述", "值得注意的是", "不难发现", "众所周知",
    "让我们", "让我们一起", "首先", "其次", "最后", "总而言之",
    "的海洋中", "点亮", "赋能", "拥抱", "精彩纷呈", "无限可能",
    # v0.16：AI 味形容词（"稳了"类——过度自信的口语化断言）
    "稳了", "拿捏了", "拿捏", "妥了", "没跑了", "就完事了", "妥妥的",
    "稳稳的", "完全没问题", "绝对没问题", "轻松拿下", "稳了稳了",
    "真的绝了", "绝了", "天秀", "神了", "牛", "牛啊", "绝绝子",
    "yyds", "YYDS", "秒懂", "狠狠", "狠狠拿捏",
    "非常棒", "棒极了", "太给力了", "给力",
    # AI 喜欢的高大上形容词
    "深刻", "全面", "系统", "本质", "本质地", "深远", "独到",
}


@dataclass
class AITasteSignals:
    burstiness_cv: float          # 句长变异系数
    marker_density: float         # 过渡词密度（每千字）
    three_list_count: int         # 三段式清单出现次数
    em_dash_count: int            # 破折号数量
    paragraph_cv: float           # 段落长度变异
    ai_likelihood: float          # 综合 AI 概率 0-1
    verdict: str                  # AI / Mixed / Human

    def as_dict(self):
        return asdict(self)


def _word_count(s: str) -> int:
    return len(re.findall(r"[\w\u4e00-\u9fff]+", s))


def _sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    # 按中英文句号、问号、感叹号分割
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def measure_burstiness(text: str) -> float:
    """句长变异系数：AI<0.35，人类>0.45。"""
    lengths = [_word_count(s) for s in _sentences(text)]
    if len(lengths) < 3:
        return 0.5
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.5
    return statistics.pstdev(lengths) / mean


def measure_marker_density(text: str) -> float:
    """过渡词密度（每千字）。AI>5，人类<1.5。"""
    words = max(_word_count(text), 1)
    lower = text.lower()
    hits = sum(lower.count(m) for m in AI_MARKERS)
    return (hits / words) * 1000.0


def count_three_lists(text: str) -> int:
    """三段式清单：'三个要点/三步/三种' 或 'firstly, secondly, thirdly'。"""
    patterns = [
        r"三个", r"三步", r"三种", r"三点", r"three (?:key|main|steps|reasons|benefits)",
        r"firstly.*secondly.*thirdly",
        r"一、.*二、.*三、",
    ]
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, text, re.I))
    return count


def count_em_dashes(text: str) -> int:
    """破折号数量（AI 偏爱多连用）。"""
    return len(re.findall(r"—", text)) + len(re.findall(r"——", text))


def measure_paragraph_symmetry(text: str) -> float:
    """段落长度变异：AI 段落等长（低 CV）。"""
    paras = _paragraphs(text)
    if len(paras) < 3:
        return 0.5
    lens = [_word_count(p) for p in paras]
    mean = statistics.mean(lens)
    if mean == 0:
        return 0.5
    return statistics.pstdev(lens) / mean


def detect_ai_taste(text: str) -> AITasteSignals:
    """综合检测。返回各信号 + 综合 AI 概率。"""
    # 短文本也检查词库（v0.16：确保"稳了"等词即使短文本也触发）
    if not text or not text.strip():
        return AITasteSignals(0.5, 0, 0, 0, 0.5, 0.3, "Human")

    cv = measure_burstiness(text)
    marker_density = measure_marker_density(text)
    three_lists = count_three_lists(text)
    em_dashes = count_em_dashes(text)
    para_cv = measure_paragraph_symmetry(text)

    # 短文本（<30字）：只靠词库信号判断（句子变异/段落无法可靠测量）
    if len(text) < 30:
        marker_ai = max(0.0, min(1.0, marker_density / 8.0))
        composite = 0.6 * marker_ai + 0.4 * min(1.0, three_lists / 2.0)
        verdict = "AI" if composite >= 0.5 else ("Mixed" if composite >= 0.3 else "Human")
        return AITasteSignals(
            burstiness_cv=round(cv, 3), marker_density=round(marker_density, 2),
            three_list_count=three_lists, em_dash_count=em_dashes,
            paragraph_cv=round(para_cv, 3), ai_likelihood=round(composite, 3), verdict=verdict,
        )

    # 各信号 → AI 概率（0=人类，1=AI）
    burst_ai = max(0.0, min(1.0, (0.45 - cv) / 0.30))
    # 过渡词密度：指数式放大（>5 已经很明显，>10 极强信号）
    marker_ai = max(0.0, min(1.0, marker_density / 8.0))
    three_ai = min(1.0, three_lists / 3.0)
    dash_ai = min(1.0, max(0, em_dashes - 2) / 4.0)
    para_ai = max(0.0, min(1.0, (0.40 - para_cv) / 0.30))

    # 加权综合（结构>词汇>模式）
    composite = (
        0.20 * burst_ai
        + 0.40 * marker_ai
        + 0.20 * three_ai
        + 0.10 * dash_ai
        + 0.10 * para_ai
    )

    if composite >= 0.5:
        verdict = "AI"
    elif composite >= 0.3:
        verdict = "Mixed"
    else:
        verdict = "Human"

    return AITasteSignals(
        burstiness_cv=round(cv, 3),
        marker_density=round(marker_density, 2),
        three_list_count=three_lists,
        em_dash_count=em_dashes,
        paragraph_cv=round(para_cv, 3),
        ai_likelihood=round(composite, 3),
        verdict=verdict,
    )
