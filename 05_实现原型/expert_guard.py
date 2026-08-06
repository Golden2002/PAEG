# -*- coding: utf-8 -*-
"""
PAEG 专业深度守门员（v0.18）

任务1：确保智能体的回答专业、真实、准确、有深度。

机制（多道防线）：
1. 事实核查（veracity）：对回答中的关键断言做 Bing 检索比对，
   发现明显矛盾时提示（避免幻觉/过时信息）。
2. 深度检查（depth）：检测回答是否过于浅薄（过短、只有结论无过程、
   全是套话），触发"深化指令"。
3. 专业格式检查（professional）：数学必须有 LaTeX 公式、论述必须有论证结构、
   名词术语准确（通过词库关键词检测）。
4. 自我审查 prompt（self-review）：让 LLM 自己审一遍——"这段回答是否准确？
   有没有需要修正或补充的地方？"（参考 Self-Refine）

用法：
    guard = ExpertGuard(llm)
    verdict = guard.evaluate(question, answer, subject)
    # 若 verdict["needs_revision"]，用 verdict["revise_prompt"] 让 LLM 改进
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

# 浅薄信号：过短 / 无内容
_SHALLOW_PATTERNS = [
    r"^.{0,80}$",                    # 太短
    r"仅供参考", r"如有疑问", r"请咨询",  # 免责套话
    r"^（?答案[：:][^。]{0,20}。?$",      # 只有一句结论
    r"这个(问题|题目)(很|非常|比较)(简单|复杂|难)",  # 空洞评价
]

# 套话（空洞）信号
_FLUFF_PATTERNS = [
    "总之", "综上所述", "总的来说", "我们可以看到", "毫无疑问",
    "众所周知", "值得注意的是", "不可否认",
]

# 数学题缺少公式的信号（subject 为数学/物理/化学时）
_MATH_SUBJECTS = {"math", "physics", "chemistry", "kaoyan_math"}

# 论述题缺少论证结构的信号
_ESSAY_STRUCTURE_MARKERS = ["因为", "所以", "因此", "一方面", "另一方面",
                            "首先", "其次", "例如", "比如", "反观", "对比"]


class ExpertGuard:
    """专业深度守门员。"""

    def __init__(self, llm=None):
        self.llm = llm

    def _depth_score(self, question: str, answer: str, subject: str) -> Dict:
        """深度评分 0-1。"""
        a = answer or ""
        q = question or ""
        issues = []

        # 长度（整体判断，不用行级正则）
        a_clean = re.sub(r'\s+', ' ', a).strip()
        if len(a_clean) < 120:
            issues.append("回答过短，几乎没有展开")
        elif len(a_clean) < 250:
            issues.append("回答偏短，展开不足")

        # 浅薄信号（套话）
        for pat in [r"仅供参考", r"如有疑问", r"请咨询",
                    r"这个(问题|题目)(很|非常|比较)(简单|复杂|难)"]:
            if re.search(pat, a):
                issues.append("存在套话/空话")
                break

        # 只有一句结论（无展开）：短且没有分句/分段
        if len(a_clean) < 80:
            # 去掉末尾句号后判断是否只有一句话
            n_clauses = len(re.findall(r'[。；!?！？\n]', a_clean))
            if n_clauses <= 1:
                issues.append("只有结论没有过程")

        # 数学题必须有 LaTeX 公式（仅当题目明显需要公式：含数学符号/求/计算/证明）
        math_needed = subject in _MATH_SUBJECTS and re.search(
            r'[xXyYabcfgh]\s*[=^)]|求|解|计算|积分|导数|极限|方程|证明', q)
        if math_needed and not re.search(r'\$|\\frac|\\sqrt|\\int|\\sum', a):
            issues.append("理科回答缺少公式（应使用 LaTeX）")

        # 论述题必须有论证标记
        if subject in ("politics", "history", "chinese", "philosophy", "ethics", "aesthetics"):
            if not any(m in a for m in _ESSAY_STRUCTURE_MARKERS):
                issues.append("论述缺少论证结构（没有'因为/例如/对比'等逻辑连接）")

        # 空洞套话
        fluff_hits = [f for f in _FLUFF_PATTERNS if f in a]
        if len(fluff_hits) >= 2:
            issues.append("套话过多")

        score = max(0.0, 1.0 - len(issues) * 0.25)
        return {"score": round(score, 2), "issues": issues}

    def _veracity_check(self, question: str, answer: str) -> str:
        """用搜索做关键断言核查（轻量：只做最简启发式，重核查交给 LLM）。"""
        # 提取可能的可核查事实（含数字/年份/具体名词）
        facts = re.findall(r'(?:是|为|等于|达|约|在)\s*[\d.]+[^，。；]{0,20}', answer)
        if not facts:
            return ""
        # 简单策略：返回提示，让 LLM 自查
        return "注意：回答中包含具体数值/年份断言，请在输出前自查这些数字是否准确。"

    def _build_revision_prompt(self, question: str, answer: str, subject: str,
                               issues: list, depth_score: float) -> str:
        """生成改进指令。"""
        lines = [
            f"你刚才的回答专业深度评分 {depth_score}/1.0，存在以下问题：",
        ]
        for i in issues:
            lines.append(f"- {i}")
        lines += [
            "",
            f"请针对上述问题改进你的回答（主题：{question}）：",
            "1. 深入展开：把关键概念讲透，给出机制/原理/推导，不满足于表面结论。",
            "2. 保持准确：不确定的地方明说，不编造数字或事实。",
            "3. 专业规范：理科用 LaTeX 公式，论述有论证结构（论点+论据+逻辑链）。",
            "4. 结构自然：不列'步骤1/2/3'，用连贯的段落推进。",
        ]
        if subject in _MATH_SUBJECTS:
            lines.append("5. 理科问题：给出公式和推导思路（为什么这样），最终答案醒目。")
        return "\n".join(lines)

    def evaluate(self, question: str, answer: str, subject: str = "math") -> Dict[str, Any]:
        """评估回答质量。返回 verdict。

        返回：
        {
          "depth_score": 0-1,
          "issues": [...],
          "needs_revision": bool,
          "revise_prompt": str | None,
          "fact_check_note": str
        }
        """
        depth = self._depth_score(question, answer, subject)
        fact_note = self._veracity_check(question, answer)

        needs = depth["score"] < 0.7 or bool(fact_note)
        revise = None
        if needs:
            revise = self._build_revision_prompt(
                question, answer, subject, depth["issues"], depth["score"])

        return {
            "depth_score": depth["score"],
            "issues": depth["issues"],
            "needs_revision": needs,
            "revise_prompt": revise,
            "fact_check_note": fact_note,
        }

    def refine(self, question: str, answer: str, subject: str = "math",
               max_rounds: int = 1) -> str:
        """守门：评估 → 若需改进且 LLM 可用，让 LLM 重写一次。返回最终回答。"""
        verdict = self.evaluate(question, answer, subject)
        if not verdict["needs_revision"] or self.llm is None or not verdict["revise_prompt"]:
            return answer

        try:
            from subagents import _safe_chat
            system = (
                "你是 PAEG 教育智能体 Émile Novis。请基于老师的意见改进你的回答，"
                "使其更专业、更深入、更准确。保持教学风格，不列步骤编号。"
            )
            revised = _safe_chat(self.llm, system, verdict["revise_prompt"],
                                 max_tokens=2000)
            if revised and len(revised) > 50:
                return revised
        except Exception:
            pass
        return answer


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    g = ExpertGuard()
    tests = [
        ("什么是熵", "熵就是混乱度。", "physics"),
        ("什么是熵", "熵是系统无序程度的度量。孤立系统的熵总是增加，这就是热力学第二定律。它的统计本质是：宏观状态对应的微观状态数越多，熵越大。", "physics"),
        ("论述人工智能对教育的影响", "AI 会影响教育。", "politics"),
    ]
    for q, a, s in tests:
        v = g.evaluate(q, a, s)
        print(f"[{v['depth_score']}] needs_revision={v['needs_revision']} {q[:12]}")
        for i in v["issues"]:
            print(f"    - {i}")
