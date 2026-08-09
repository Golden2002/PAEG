# -*- coding: utf-8 -*-
"""
PAEG Agent 主循环引擎（v0.19）

P2-7：Plan → Act → Observe → Reflect 显式循环（对标 ReAct / Reflexion / Claude Code）：
1. Plan    : 让 LLM 先给出执行计划（是否需要工具、用什么工具、回答策略）
2. Act     : 执行工具调用（或直接回答）
3. Observe : 记录工具结果
4. Reflect : 判断是否完成；失败则 replan（最多 replan_limit 次）

特性：
- 最大迭代保护（防止死循环）
- 中途重新规划（replanning）
- 完整 trace 日志（可调试 / 前端可视化）

用法：
    from agent_engine import run_agent
    result = run_agent(llm, system, question)
    # {"answer", "plan", "trace": [{phase, ...}], "iterations"}
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# 每个子代理用的 max_tokens（规划/反思简短，回答长些）
PLAN_MAX_TOKENS = 300
REFLECT_MAX_TOKENS = 300
ANSWER_MAX_TOKENS = 1500


class AgentEngine:
    """Plan-Act-Observe-Reflect 循环引擎。"""

    def __init__(self, llm, max_iterations: int = 5, replan_limit: int = 2):
        self.llm = llm
        self.max_iterations = max_iterations
        self.replan_limit = replan_limit

    def _safe_chat(self, system: str, user: str, max_tokens: int) -> Optional[str]:
        try:
            from subagents import _safe_chat
            return _safe_chat(self.llm, system, user, max_tokens=max_tokens)
        except Exception:
            return None

    # ─── Plan 阶段 ───
    def _plan(self, question: str) -> Dict[str, Any]:
        """让 LLM 决定执行计划。返回 {"needs_tools", "plan_text", "tool_hint"}"""
        sys = (
            "你是 PAEG 教育智能体的规划器。分析学生的问题，决定执行策略。\n"
            "判断是否需要调用工具：\n"
            "- 需要最新/外部信息 → 用 web_search\n"
            "- 数学表达式需验证 → 用 verify_math\n"
            "- 需要读网页全文 → 用 fetch_page\n"
            "- 其余可直接回答\n"
            "只输出 JSON：{\"needs_tools\": bool, \"plan\": \"一句话计划\"}"
        )
        r = self._safe_chat(sys, question, PLAN_MAX_TOKENS)
        if not r:
            return {"needs_tools": False, "plan": ""}
        try:
            # 提取 JSON
            start, end = r.find('{'), r.rfind('}')
            if start != -1 and end != -1:
                return json.loads(r[start:end + 1])
        except Exception:
            pass
        return {"needs_tools": False, "plan": r[:100]}

    # ─── Act 阶段（工具调用） ───
    def _act(self, system: str, question: str) -> Dict[str, Any]:
        """执行一次工具调用循环（复用 tool_registry.run_agent_loop）。"""
        try:
            from tool_registry import run_agent_loop
            return run_agent_loop(self.llm, system, question, max_iterations=3)
        except Exception as e:
            return {"answer": None, "tool_calls": [], "error": str(e)}

    # ─── Reflect 阶段 ───
    def _reflect(self, question: str, answer: str) -> Dict[str, Any]:
        """判断回答是否完整/准确。返回 {"complete", "issue", "suggestion"}"""
        sys = (
            "你是 PAEG 教育智能体的反思器。检查下面的回答是否："
            "1) 针对了问题（不答非所问）2) 足够深入 3) 有无明显错误\n"
            "只输出 JSON：{\"complete\": bool, \"issue\": \"问题描述或空\", "
            "\"suggestion\": \"改进建议或空\"}"
        )
        r = self._safe_chat(sys, f"问题：{question}\n回答：{answer[:800]}", REFLECT_MAX_TOKENS)
        if not r:
            return {"complete": True, "issue": "", "suggestion": ""}
        try:
            start, end = r.find('{'), r.rfind('}')
            if start != -1 and end != -1:
                return json.loads(r[start:end + 1])
        except Exception:
            pass
        return {"complete": True, "issue": "", "suggestion": ""}

    # ─── 主循环 ───
    def run(self, system: str, question: str) -> Dict[str, Any]:
        """执行完整 Agent 循环。"""
        trace: List[Dict[str, Any]] = []
        plan = self._plan(question)
        trace.append({"phase": "plan", **plan})

        answer = None
        tool_calls = []
        replans = 0

        for i in range(self.max_iterations):
            # Act
            act_result = self._act(system, question)
            candidate = act_result.get("answer")
            tool_calls = act_result.get("tool_calls", [])
            trace.append({"phase": "act", "iter": i,
                          "tool_calls": len(tool_calls)})

            if not candidate:
                # 工具循环失败，直接普通回答
                candidate = self._safe_chat(system, question, ANSWER_MAX_TOKENS)
            if not candidate:
                trace.append({"phase": "reflect", "complete": False,
                              "issue": "回答生成失败"})
                break
            answer = candidate

            # Reflect
            refl = self._reflect(question, answer)
            trace.append({"phase": "reflect", **refl})

            if refl.get("complete"):
                break

            # Replan（有改进建议且未超限）
            suggestion = refl.get("suggestion", "")
            if suggestion and replans < self.replan_limit and len(suggestion) > 10:
                replans += 1
                trace.append({"phase": "replan", "attempt": replans,
                              "suggestion": suggestion[:100]})
                # 带反思建议重新执行（普通对话，不重新规划工具）
                sys2 = system + f"\n\n上次回答的反思：{refl.get('issue','')}\n"
                sys2 += f"改进建议：{suggestion}\n请据此改进回答。"
                r2 = self._safe_chat(sys2, question, ANSWER_MAX_TOKENS)
                if r2:
                    answer = r2
                continue
            break

        return {"answer": answer, "plan": plan, "trace": trace,
                "tool_calls": tool_calls, "iterations": len(trace)}


def run_agent(llm, system: str, question: str,
              max_iterations: int = 5, replan_limit: int = 2) -> Dict[str, Any]:
    """便捷入口。"""
    eng = AgentEngine(llm, max_iterations, replan_limit)
    return eng.run(system, question)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("AgentEngine 就绪（Plan→Act→Observe→Reflect）")
    print("用法：run_agent(llm, system, question)")
