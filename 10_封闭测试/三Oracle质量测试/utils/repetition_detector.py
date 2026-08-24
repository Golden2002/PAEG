# -*- coding: utf-8 -*-
"""复读机检测器 —— 倾诉模块核心（用户要求：不能反反复复说同一个问题绕来绕去）。

三层检测（Oracle 2 方案）：
  1. 相邻相似度：相邻回复向量余弦（去停用词）
  2. 窗口重复：连续 3 轮中任意两轮高相似
  3. 关键短语重复：高频模板（"我理解你的感受""这很正常"等万能句）出现次数
输出：repetition_rate + 风险轮次 + 重复短语清单
"""
from __future__ import annotations

import re
from typing import Dict, List

# 万能句/套话模板（出现多次 = 复读信号）
CLICHE_PATTERNS = [
    r"我(能)?理解你的感受",
    r"这(很|是)?正常",
    r"听起来你(很|非常|特别)",
    r"你(一定|应该)很难过",
    r"不要(太)?难过",
    r"一切都会好",
    r"你要(坚强|加油|振作)",
    r"我(很|非常)理解",
    r"你(可以|不妨)试试",
    r"你要相信自己",
]

# 简单停用词（中文）
STOPWORDS = set("的了在是我有和就不人都一个上也去会要这那对与他她它等吗呢吧啊".split())


def _tokenize(text: str) -> List[str]:
    """简易分词：提取中文词 + 英文词。"""
    text = text.lower()
    # 英文词
    en = re.findall(r"[a-z]{2,}", text)
    # 中文双字词
    cn = [text[i:i+2] for i in range(len(text) - 1)
          if "\u4e00" <= text[i] <= "\u9fff" and "\u4e00" <= text[i+1] <= "\u9fff"]
    tokens = [t for t in en + cn if t not in STOPWORDS and len(t) >= 2]
    return tokens


def _jaccard_sim(a: List[str], b: List[str]) -> float:
    """Jaccard 相似度（token 集合）。"""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(1, len(sa | sb))


def _phrase_sim(a: str, b: str) -> float:
    """基于公共 4-gram 的相似度（捕捉短语级重复）。"""
    a4 = {a[i:i+4] for i in range(max(0, len(a) - 3))}
    b4 = {b[i:i+4] for i in range(max(0, len(b) - 3))}
    if not a4 or not b4:
        return 0.0
    return len(a4 & b4) / max(1, len(a4 | b4))


class RepetitionDetector:
    """复读机检测器：对倾诉回复序列检测重复。"""

    def __init__(self, sim_threshold: float = 0.55, window: int = 3,
                 cliche_count: int = 2):
        self.sim_threshold = sim_threshold  # Jaccard 相似度阈值
        self.window = window                # 滑动窗口（连续 N 轮）
        self.cliche_count = cliche_count    # 套话出现次数阈值

    def detect(self, replies: List[str]) -> Dict:
        """检测回复序列的重复情况。

        Returns:
            {"repetition_rate": float, "adjacent_high_sim": [(i, sim)],
             "window_violations": [(rounds)], "cliches": {phrase: count},
             "repetition_risk": bool}
        """
        n = len(replies)
        if n < 2:
            return {"repetition_rate": 0.0, "adjacent_high_sim": [],
                    "window_violations": [], "cliches": {}, "repetition_risk": False}

        # 1. 相邻相似度（Jaccard + 短语双信号）
        adj_high = []
        for i in range(n - 1):
            jac = _jaccard_sim(_tokenize(replies[i]), _tokenize(replies[i+1]))
            phr = _phrase_sim(replies[i], replies[i+1])
            sim = max(jac, phr)
            if sim > self.sim_threshold:
                adj_high.append((i, round(sim, 3), round(jac, 2), round(phr, 2)))

        # 2. 窗口重复（连续 window 轮内两两高相似）
        window_violations = []
        for i in range(max(0, n - self.window + 1)):
            window_replies = replies[i:i+self.window]
            for x in range(len(window_replies)):
                for y in range(x + 1, len(window_replies)):
                    sim = _jaccard_sim(_tokenize(window_replies[x]),
                                       _tokenize(window_replies[y]))
                    if sim > self.sim_threshold + 0.1:  # 窗口阈值更严
                        window_violations.append((i + x, i + y, round(sim, 3)))

        # 3. 套话检测
        cliches = {}
        for pat in CLICHE_PATTERNS:
            cnt = 0
            for r in replies:
                if re.search(pat, r):
                    cnt += 1
            if cnt >= self.cliche_count:
                cliches[pat] = cnt

        # 4. 综合：复读率 = max(相邻重复率, 套话占比)
        cliche_ratio = min(1.0, sum(cliches.values()) / max(1, n)) if cliches else 0.0
        repetition_rate = max(len(adj_high) / max(1, n - 1), cliche_ratio)
        repetition_risk = (
            repetition_rate > 0.15              # >15% 重复
            or len(window_violations) > 0        # 有窗口违规
            or len(cliches) > 0                  # 有套话高频
        )
        return {
            "repetition_rate": round(repetition_rate, 3),
            "adjacent_high_sim": adj_high,
            "window_violations": window_violations,
            "cliches": cliches,
            "cliche_ratio": round(cliche_ratio, 3),
            "repetition_risk": repetition_risk,
        }


if __name__ == "__main__":
    # 自测
    d = RepetitionDetector()
    # 正常对话（多样）
    good = [
        "我能感觉到你今天很累，愿意和我说说发生了什么吗？",
        "考试失利确实让人沮丧，特别是你已经很努力了。",
        "你提到和同桌的关系变化，这让你很困扰是吗？",
        "睡不着的时候，脑子里会想些什么呢？",
        "听起来你希望被理解，但又害怕被评判。",
        "你刚才说的那些，让你最难受的是哪一部分？",
    ]
    # 复读机对话（重复）
    bad = [
        "我理解你的感受。",
        "这很正常。",
        "我理解你的感受。",
        "不要难过。",
        "这很正常。",
        "我理解你的感受。",
    ]
    r_good = d.detect(good)
    r_bad = d.detect(bad)
    print("=== 正常对话 ===")
    print(f"  复读率: {r_good['repetition_rate']} | 风险: {r_good['repetition_risk']}")
    print(f"  套话: {r_good['cliches']}")
    print("=== 复读机对话 ===")
    print(f"  复读率: {r_bad['repetition_rate']} | 风险: {r_bad['repetition_risk']}")
    print(f"  套话: {r_bad['cliches']}")
    print(f"  相邻高相似: {r_bad['adjacent_high_sim']}")
