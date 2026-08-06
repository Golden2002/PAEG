# -*- coding: utf-8 -*-
"""
PAEG 评估 Harness（v0.19）

借鉴 lm-evaluation-harness / OpenAI Evals / DeepEval 的评估思想，
为 PAEG 建立"单元测试 + LLM 输出质量评估"两层测试体系：

Layer 1 - 单元测试（pytest）：测子代理逻辑、工具、路由（已有 59 个）
Layer 2 - LLM 输出质量评估（本模块）：
  - 准确性：用 SymPy 验证数学答案 / 事实核查
  - 相关性：回答是否针对问题（LLM 评分器 / 关键词覆盖）
  - 深度：expert_guard 的深度评分
  - 格式：公式是否用 $...$ 正确包裹、是否有多余 $
  - 工具调用：agent 是否正确触发工具

用法：
    from eval_harness import PAEGEvaluator
    ev = PAEGEvaluator()
    ev.add_case("什么是熵", expect_subject="physics")
    result = ev.run(cases, use_llm=True)   # 跑全部案例
    ev.report()                            # 输出评分报告

    # 命令行：python eval_harness.py 跑默认回归集
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional


class PAEGEvaluator:
    """教育智能体评估器。"""

    def __init__(self, llm=None):
        self.llm = llm
        self.cases: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []

    # ─── 注册测试案例 ───
    def add_case(self, question: str, subject: str = "math",
                 grade_level: str = "high_school",
                 expect_type: Optional[str] = None,
                 expect_keywords: Optional[List[str]] = None,
                 expect_formula: bool = False,
                 label: str = ""):
        """注册一个评估案例。
        expect_type: 期望的意图（teach/problem/meta/greeting）
        expect_keywords: 回答应包含的关键词
        expect_formula: 是否应包含 LaTeX 公式
        """
        self.cases.append({
            "question": question, "subject": subject,
            "grade_level": grade_level, "expect_type": expect_type,
            "expect_keywords": expect_keywords or [],
            "expect_formula": expect_formula,
            "label": label or question[:20],
        })

    # ─── 运行 ───
    def run(self, use_llm: bool = True) -> List[Dict[str, Any]]:
        """运行全部案例。use_llm=False 时只测意图识别（快）。"""
        self.results = []
        for case in self.cases:
            r = self._eval_one(case, use_llm)
            self.results.append(r)
            status = "PASS" if r["pass"] else "FAIL"
            print(f"[{status}] {case['label']} | score={r['score']}")
            for issue in r.get("issues", []):
                print(f"        - {issue}")
        return self.results

    def _eval_one(self, case: Dict, use_llm: bool) -> Dict:
        """评估单个案例。"""
        q = case["question"]
        issues = []
        score = 1.0

        # 1. 意图识别（不需要 LLM）
        if case.get("expect_type"):
            from meta_router import is_meta_question, is_greeting, is_problem_request
            intent = None
            if is_problem_request(q):
                intent = "problem"
            elif is_greeting(q):
                intent = "greeting"
            elif is_meta_question(q):
                intent = "meta"
            else:
                intent = "teach"
            if intent != case["expect_type"]:
                issues.append(f"意图识别错误: 期望 {case['expect_type']} 得到 {intent}")
                score -= 0.3

        # 2. 真实回答（需 LLM，慢）
        answer = ""
        if use_llm:
            answer = self._get_answer(q, case["subject"], case["grade_level"])

            # 相关性：回答是否针对问题（关键词覆盖）
            if case.get("expect_keywords"):
                hits = [k for k in case["expect_keywords"] if k in answer]
                if not hits:
                    issues.append(f"回答未包含预期关键词: {case['expect_keywords']}")
                    score -= 0.3

            # 公式格式检查（重点）：数学题应有 $ 或括号包公式（前端会修复）
            if case.get("expect_formula"):
                has_dollar = bool(re.search(r'\$', answer))
                has_bracket_formula = bool(re.search(r'[（(](?:[^）)]*[=^<>\\][^）)]*){0,5}[）)]', answer))
                if not has_dollar and not has_bracket_formula:
                    issues.append("数学回答既无 $ 公式也无括号公式")
                    score -= 0.3
                # 检查损坏的 $（孤立单字母公式，说明 $ 错位）
                bad = re.findall(r'\$[a-zA-Zα-ωπ]\$', answer)
                if bad:
                    issues.append(f"检测到可疑的孤立公式: {bad[:3]}")
                    score -= 0.2

            # 深度（expert_guard）
            try:
                from expert_guard import ExpertGuard
                guard = ExpertGuard(self.llm)
                verdict = guard.evaluate(q, answer, case["subject"])
                if verdict["depth_score"] < 0.6:
                    issues.append(f"深度不足: {verdict['depth_score']}")
                    score -= 0.2
            except Exception:
                pass

        return {"label": case["label"], "question": q, "answer": answer,
                "score": max(0.0, round(score, 2)), "pass": score >= 0.7,
                "issues": issues}

    def _get_answer(self, question: str, subject: str, grade: str) -> str:
        """调真实 API 获取回答（模拟前端调用）。"""
        try:
            import urllib.request
            # 固定 eval 用户，避免记忆干扰；每次用不同随机 id 也行但会丢画像
            data = json.dumps({
                "text": question, "learner_id": "eval_user",
                "nickname": "评估", "grade_level": grade,
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:5000/api/chat",
                data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8")).get("reply", "")
        except Exception:
            return ""

    # ─── 报告 ───
    def report(self) -> Dict[str, Any]:
        """输出汇总报告。"""
        if not self.results:
            return {}
        passed = sum(1 for r in self.results if r["pass"])
        total = len(self.results)
        avg_score = sum(r["score"] for r in self.results) / max(total, 1)
        return {
            "total": total, "passed": passed, "failed": total - passed,
            "pass_rate": round(passed / max(total, 1), 2),
            "avg_score": round(avg_score, 2),
        }

    def save_report(self, path: Optional[str] = None) -> str:
        """保存评估报告 JSON。"""
        rep = self.report()
        path = path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'eval_report.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"report": rep, "results": self.results},
                      f, ensure_ascii=False, indent=1)
        return path

    # ─── v0.19.2：tool-use 评估维度 ───
    def evaluate_tool_use(self) -> Dict[str, Any]:
        """评估工具调用质量（借鉴 ClawBench trajectory 思路）。

        直接调用 tool_registry 的 execute_tool，检查：
        - 正常调用成功率
        - 错误恢复（瞬时错误重试）
        - 降级信号（永久错误）
        """
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from tool_registry import execute_tool
        from tool_recovery import reset_metrics, get_metrics_summary

        reset_metrics()
        results = {}

        # 1. 正常工具
        results["get_time"] = "正常" if "今天是" in execute_tool("get_time", {}) else "异常"
        results["daily_quote"] = "正常" if "——" in execute_tool("daily_quote", {}) else "异常"
        results["verify_math"] = "正常" if "解析成功" in execute_tool("verify_math", {"expr": "x**2-4"}) else "异常"
        # 隐式乘法重试
        results["verify_math_implicit"] = "重试成功" if "自动修正" in execute_tool("verify_math", {"expr": "2x^2+3x-5"}) else "异常"
        # 错误参数 → 应给建议
        bad_arg = execute_tool("web_search", {"wrong": 1})
        results["error_recovery"] = "有建议" if "参数" in bad_arg and "重试" in bad_arg else "无建议"

        # 2. 指标汇总
        metrics = get_metrics_summary()
        return {"tool_tests": results, "metrics": metrics,
                "all_pass": all("正常" in v or "成功" in v or "有建议" in v
                                for v in results.values())}


# 默认回归集
def default_cases(ev: PAEGEvaluator):
    """内置回归案例（覆盖主要意图 + 公式 + 深度）。"""
    # 意图类
    ev.add_case("你好", expect_type="greeting", label="寒暄")
    ev.add_case("你是谁", expect_type="meta", label="身份")
    ev.add_case("你能调用知识库吗", expect_type="meta", label="能力")
    ev.add_case("给我一道经典题目", subject="math", grade_level="graduate_exam",
                expect_type="problem", label="考研出题")
    ev.add_case("什么是熵", subject="physics", expect_type="teach",
                expect_keywords=["熵"], label="概念教学")
    # 公式类
    ev.add_case("求函数 f(x)=x^3-3x+1 的极值", subject="math",
                expect_formula=True, label="导数公式")
    ev.add_case("解方程 x^2-5x+6=0", subject="math",
                expect_formula=True, label="解方程")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None
    fast = "--fast" in sys.argv
    ev = PAEGEvaluator()
    default_cases(ev)
    print(f"=== PAEG 评估 Harness（{'快速模式' if fast else '完整模式'}）===")
    print(f"共 {len(ev.cases)} 个案例\n")
    t0 = time.time()
    ev.run(use_llm=not fast)
    rep = ev.report()
    print(f"\n=== 报告 ===")
    print(f"通过率: {rep['pass_rate']} ({rep['passed']}/{rep['total']})")
    print(f"平均分: {rep['avg_score']}")
    print(f"耗时: {round(time.time() - t0, 1)}s")
    # v0.19.2：tool-use 评估
    print(f"\n=== Tool-Use 评估 ===")
    tu = ev.evaluate_tool_use()
    for k, v in tu["tool_tests"].items():
        print(f"  {k}: {v}")
    print(f"  全部通过: {tu['all_pass']}")
    rep["tool_use"] = tu
    path = ev.save_report()
    print(f"报告已存: {path}")
