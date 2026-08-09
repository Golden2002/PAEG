# -*- coding: utf-8 -*-
"""
PAEG 自我改进闭环（v0.19）

P2-8：对标 Reflexion（verbal reinforcement learning）+ 失败案例学习：
1. 每次对话后反思：这次回答是否有效（针对问题/深入/准确）
2. 记录案例（成功/失败）到 cases.jsonl
3. 定期分析失败案例的共性 → 生成改进建议（改进提示词/技能描述）
4. 改进建议写入 memory/improvements.md，可在 system prompt 中注入

用法：
    improver = SelfImprover(llm, user_id)
    improver.record(question, answer, meta)     # 对话后记录
    improver.reflect_and_learn()                # 定期：分析失败案例生成改进
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class SelfImprover:
    """自我改进：反思 + 失败案例库 + 改进建议。"""

    def __init__(self, llm=None, base_dir: Optional[str] = None):
        base = base_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'memory')
        os.makedirs(base, exist_ok=True)
        self.cases_path = os.path.join(base, 'cases.jsonl')
        self.improvements_path = os.path.join(base, 'improvements.md')
        self.llm = llm

    # ─── 反思与记录 ───
    def record(self, question: str, answer: str, meta: Optional[Dict] = None) -> Dict:
        """对话后记录案例，并做一次快速反思。"""
        verdict = self._reflect(question, answer)
        case = {
            "ts": time.time(),
            "question": question[:300],
            "answer": answer[:800],
            "verdict": verdict,
            "meta": meta or {},
        }
        try:
            with open(self.cases_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(case, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return verdict

    def _reflect(self, question: str, answer: str) -> Dict[str, Any]:
        """快速反思：回答是否针对问题/充分。"""
        if self.llm is None:
            return {"good": True, "note": ""}
        try:
            from subagents import _safe_chat
            r = _safe_chat(
                self.llm,
                "你是 PAEG 的教学质量反思器。判断这次回答是否："
                "1) 针对了学生的问题 2) 有实质内容 3) 无明显错误。\n"
                "只输出 JSON：{\"good\": bool, \"note\": \"问题描述或空\"}",
                f"问题：{question}\n回答：{answer[:600]}",
                max_tokens=200)
            import re
            m = re.search(r'\{.*\}', r, re.S)
            if m:
                return json.loads(m.group(0))
        except Exception:
            pass
        return {"good": True, "note": ""}

    # ─── 失败案例分析（定期调用） ───
    def analyze_failures(self, limit: int = 50) -> List[str]:
        """分析最近失败案例，生成改进建议。"""
        cases = self._load_cases(limit)
        bad = [c for c in cases if not c.get("verdict", {}).get("good", True)]
        if len(bad) < 3 or self.llm is None:
            return []
        try:
            from subagents import _safe_chat
            sample = "\n".join(
                f"Q: {c['question'][:100]}\nA: {c['answer'][:150]}\n问题: {c['verdict'].get('note','')}"
                for c in bad[-8:])
            r = _safe_chat(
                self.llm,
                "你是 PAEG 的改进分析师。分析这些失败教学案例的共性，"
                "给出 2-3 条可操作的改进建议（改进提示词/教学方法）。"
                "每条以 '- ' 开头。只输出建议。",
                f"失败案例：\n{sample}", max_tokens=400)
            if r:
                suggestions = [l.strip() for l in r.splitlines() if l.strip().startswith('-')]
                self._save_improvements(suggestions)
                return suggestions
        except Exception:
            pass
        return []

    def _load_cases(self, limit: int) -> List[dict]:
        cases = []
        try:
            with open(self.cases_path, encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        cases.append(json.loads(line))
        except Exception:
            pass
        return cases[-limit:]

    def _save_improvements(self, suggestions: List[str]):
        """把改进建议写入 improvements.md（可注入 system prompt）。"""
        try:
            existing = ""
            if os.path.exists(self.improvements_path):
                with open(self.improvements_path, encoding='utf-8') as f:
                    existing = f.read()
            new = "\n".join(suggestions)
            with open(self.improvements_path, 'a', encoding='utf-8') as f:
                f.write(f"\n## {time.strftime('%Y-%m-%d')}\n{new}\n")
        except Exception:
            pass

    def get_improvements(self) -> str:
        """读取改进建议（注入 system prompt）。"""
        try:
            with open(self.improvements_path, encoding='utf-8') as f:
                return f.read()[-1000:]  # 最近部分
        except Exception:
            return ""

    def stats(self) -> dict:
        cases = self._load_cases(10000)
        bad = [c for c in cases if not c.get("verdict", {}).get("good", True)]
        return {"total_cases": len(cases), "failure_cases": len(bad),
                "failure_rate": round(len(bad) / max(len(cases), 1), 2)}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    imp = SelfImprover(llm=None)
    imp.record("什么是熵", "熵就是混乱度。", {"subject": "physics"})
    imp.record("求导", "答案是 x。", {"subject": "math"})
    print("案例统计:", imp.stats())
    print("改进建议文件:", os.path.exists(imp.improvements_path))
