# -*- coding: utf-8 -*-
"""test_agent_scope.py — #9 Per-Agent Scope 测试（Harness 30 项 P1，§3.46.2）

覆盖：每 subagent 独立工具/提示词作用域（shadowing），会话级能力组合。
dsh Harness 借鉴（dsh-scope agent.ctx 隔离 realm，commit 47f9438）：
每 agent 可挂独立工具集（agent.ctx 隔离作用域），不互相污染。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_scope_has_default_all_tools():
    """AgentScope 默认允许全部工具（兼容现状）。"""
    from services.agent_scope import AgentScope
    scope = AgentScope("presenter")
    assert scope.allow_tool("web_search") is True
    assert scope.allow_tool("verify_math") is True


def test_scope_restricts_tools():
    """可为 subagent 限制工具集（如 affection 只允许检索类）。"""
    from services.agent_scope import AgentScope
    scope = AgentScope("affection_supportor", allow_tools={"web_search"})
    assert scope.allow_tool("web_search") is True
    assert scope.allow_tool("verify_math") is False


def test_scope_blocks_tools():
    """可显式禁用工具（shadowing：禁止项优先）。"""
    from services.agent_scope import AgentScope
    scope = AgentScope("answer_solver", block_tools={"verify_math"})
    assert scope.allow_tool("verify_math") is False
    assert scope.allow_tool("web_search") is True


def test_scope_prompt_override():
    """可为 subagent 注入提示词覆盖（作用域内 shadowing）。"""
    from services.agent_scope import AgentScope
    scope = AgentScope("presenter", prompt_override="你是资深数学教师")
    assert scope.get_prompt_override() == "你是资深数学教师"
    # 未设置 → 空（用现有 build_* 系统）
    scope2 = AgentScope("diagnostor")
    assert scope2.get_prompt_override() == ""


def test_scope_isolation_between_agents():
    """不同 subagent 作用域互不污染（隔离 realm）。"""
    from services.agent_scope import AgentScope
    presenter = AgentScope("presenter", allow_tools={"web_search"})
    diagnostor = AgentScope("diagnostor")  # 默认全工具
    assert presenter.allow_tool("verify_math") is False
    assert diagnostor.allow_tool("verify_math") is True


def test_default_scopes_for_9_subagents():
    """内置 9 个 subagent 的默认作用域（与 #1/#11 对齐）。"""
    from services.agent_scope import DEFAULT_AGENT_SCOPES
    expected = ["diagnostor", "planner", "presenter", "evaluator",
                "adapter", "answer_solver", "affection_supportor",
                "self_update_agent", "individuality"]
    for name in expected:
        assert name in DEFAULT_AGENT_SCOPES, f"缺 {name} 默认作用域"


def test_register_custom_scope():
    """可注册自定义 subagent 作用域（dsh 一切皆插件）。"""
    from services.agent_scope import (
        DEFAULT_AGENT_SCOPES, AgentScope, register_scope, get_scope,
    )
    register_scope("test_scope", AgentScope("test_scope", allow_tools={"web_search"}))
    try:
        assert "test_scope" in DEFAULT_AGENT_SCOPES
        assert get_scope("test_scope").allow_tool("web_search") is True
        assert get_scope("test_scope").allow_tool("verify_math") is False
    finally:
        DEFAULT_AGENT_SCOPES.pop("test_scope", None)


def test_get_scope_missing_falls_back_default():
    """未知 subagent 作用域回退默认（全工具，容错）。"""
    from services.agent_scope import get_scope
    scope = get_scope("no_such_agent")
    assert scope.allow_tool("web_search") is True
