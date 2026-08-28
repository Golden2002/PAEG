# -*- coding: utf-8 -*-
"""test_answer_solver_tool_loop.py —— _execute_tool_calls 工具执行循环接线测试。

背景（v0.45 E2E 修复遗留 bug）：AnswerSolver 通过 ``get_tool_defs()`` 向 LLM
暴露**全部**内置工具，但 ``subagents._execute_tool_calls`` 只硬编码处理 3 个
工具名（solve_problem / verify_math / web_search）：

1. ``verify_math`` 分支 ``from verify_math import verify_expression`` —— 但
   ``verify_math.py`` 根本不存在（真正的 verify_math 内联在
   ``tool_registry._exec_verify_math``，走 sympy）→ ImportError →
   "[工具 verify_math 执行失败]"。
2. 其余工具（daily_quote / get_time / ...）落入 else 分支 →
   "（工具 X 执行结果未知）"。

正确行为：委托 ``config_hub.get_hub().execute_tool(name, arguments) -> str``
（四类全派发：内置 + mcp__ + load_skill__ + run_workflow__；config_hub 不可用时
回退 ``tool_registry.execute_tool``）。

测试策略：
- 直接调 ``_execute_tool_calls``（真实执行循环，非最小复现）。
- monkeypatch ``subagents._safe_chat`` → 返回 None，跳过二次 LLM 调用，
  使函数落到 ``return _tool_ctx[:1800]`` 兜底，从而拿到工具结果字符串。
"""
from __future__ import annotations

import json
import os
import sys

import pytest


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import subagents as _sa


def _tool_calls_answer(calls) -> str:
    """构造 LLM 返回的工具调用 JSON 串（answer 形如 {"tool_calls": [...]}）。"""
    return json.dumps({"tool_calls": calls}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def _no_second_llm(monkeypatch):
    """跳过工具执行后的二次 LLM 调用，落到 _tool_ctx 兜底返回。"""
    monkeypatch.setattr(_sa, "_safe_chat", lambda *a, **k: None)


def test_verify_math_delegates_to_tool_registry():
    # Given: LLM 返回 verify_math 工具调用（expr 参数，与 get_tool_defs 声明一致）
    answer = _tool_calls_answer([
        {"name": "verify_math", "arguments": json.dumps({"expr": "x**2 - 4"})},
    ])

    # When: 执行工具调用循环
    out = _sa._execute_tool_calls(None, answer, "验证 x^2-4", "sys", "user", [])

    # Then: 结果是真实 SymPy 输出，不是 ImportError 失败 / 未知
    assert "[工具 verify_math 执行失败]" not in out
    assert "执行结果未知" not in out
    assert "解析成功" in out          # _exec_verify_math 成功路径标志


def test_daily_quote_delegates_to_tool_registry():
    # Given: LLM 返回一个非三工具名 daily_quote（无参数）
    answer = _tool_calls_answer([
        {"name": "daily_quote", "arguments": "{}"},
    ])

    # When: 执行工具调用循环
    out = _sa._execute_tool_calls(None, answer, "来一句名言", "sys", "user", [])

    # Then: 结果是真实名言输出，不是 "执行结果未知"
    assert "执行结果未知" not in out
    assert "[工具 daily_quote 执行失败]" not in out
    assert "——" in out                # _exec_daily_quote 输出「...」——作者 格式


def test_get_time_delegates_to_tool_registry():
    # Given: LLM 返回另一个非三工具名 get_time（无参数）
    answer = _tool_calls_answer([
        {"name": "get_time", "arguments": "{}"},
    ])

    # When: 执行工具调用循环
    out = _sa._execute_tool_calls(None, answer, "今天几号", "sys", "user", [])

    # Then: 结果是真实时间输出，不是 "执行结果未知"
    assert "执行结果未知" not in out
    assert "[工具 get_time 执行失败]" not in out
    assert "今天是" in out            # _exec_get_time 输出 "今天是 ..."


def test_load_skill_delegates_to_config_hub():
    # Given: LLM 返回 load_skill__ 技能加载工具调用（get_tool_defs 暴露 11 个技能）
    answer = _tool_calls_answer([
        {"name": "load_skill__concept-explainer", "arguments": "{}"},
    ])

    # When: 执行工具调用循环
    out = _sa._execute_tool_calls(None, answer, "加载概念解释技能", "sys", "user", [])

    # Then: 走 config_hub 的 skills.activate，不是 "未知工具"
    assert "未知工具" not in out
    assert "[工具 load_skill__concept-explainer 执行失败]" not in out


def test_run_workflow_delegates_to_config_hub():
    # Given: LLM 返回 run_workflow__ 工作流工具调用（get_tool_defs 暴露 4 个工作流）
    answer = _tool_calls_answer([
        {"name": "run_workflow__teach_concept", "arguments": json.dumps({"concept": "什么是熵"})},
    ])

    # When: 执行工具调用循环
    out = _sa._execute_tool_calls(None, answer, "跑教学概念工作流", "sys", "user", [])

    # Then: 走 config_hub 的 workflows.invoke，不是 "未知工具"
    assert "未知工具" not in out
    assert "[工具 run_workflow__teach_concept 执行失败]" not in out
