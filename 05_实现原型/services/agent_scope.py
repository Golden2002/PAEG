# -*- coding: utf-8 -*-
"""services/agent_scope.py —— #9 Per-Agent Scope（Harness 30 项 P1，§3.46.2，2026-08-16）

dsh Harness 借鉴（dsh-scope agent.ctx 隔离 realm，commit 47f9438）：
每 agent 可挂独立工具集/提示词作用域（shadowing），会话级能力组合。

设计（与 #1/#11/#21 衔接成完整体系）：
- AgentScope：单个 subagent 的作用域（allow_tools/block_tools/prompt_override）
  - 默认允许全部工具（兼容现状，ratchet 铁律）
  - allow_tools 白名单（限制工具集）
  - block_tools 黑名单（显式禁用，优先于白名单）
  - prompt_override 提示词覆盖（作用域内 shadowing）
- DEFAULT_AGENT_SCOPES：9 个内置 subagent 默认作用域（与 #1 装扮层/#11 契约层对齐）
- get_scope()：未知 subagent 回退默认（全工具，容错）
- register_scope()：自定义 subagent 作用域可插拔

与既有机制关系：
- #1 services/subagent_loader.py：9 subagent 装扮层（persona/prompt 配置）
- #11 services/agent_trirole.py：服务契约层（Definition/Provider/Consumer）
- #21 infra/subagent_registry.py：provider 注册表
- 本模块：每 subagent 独立工具/提示词作用域（能力组合）
"""
from __future__ import annotations

from typing import Dict, Optional, Set


class AgentScope:
    """单个 subagent 的作用域（工具集 + 提示词覆盖，shadowing 语义）。

    规则：
    - 默认允许全部工具（兼容现状）
    - allow_tools 非空时 → 仅允许白名单内工具
    - block_tools 命中 → 禁止（黑名单优先于白名单）
    - prompt_override 非空 → 覆盖该 subagent 的系统提示词
    """

    def __init__(
        self,
        name: str,
        allow_tools: Optional[Set[str]] = None,
        block_tools: Optional[Set[str]] = None,
        prompt_override: str = "",
    ):
        self.name = name
        self.allow_tools: Set[str] = set(allow_tools or ())
        self.block_tools: Set[str] = set(block_tools or ())
        self.prompt_override = prompt_override

    def allow_tool(self, tool_name: str) -> bool:
        """判断工具是否允许（黑名单优先，白名单限制，默认全放行）。"""
        if tool_name in self.block_tools:
            return False
        if self.allow_tools:
            return tool_name in self.allow_tools
        return True

    def get_prompt_override(self) -> str:
        """获取提示词覆盖（空 = 用现有 build_* 系统）。"""
        return self.prompt_override


# ─────────────────────────────────────
# 9 个内置 subagent 默认作用域（与 #1 装扮层/#11 契约层对齐）
# 默认全工具（ratchet：不改现状）；可在此为特定 subagent 限制工具集
# ─────────────────────────────────────
DEFAULT_AGENT_SCOPES: Dict[str, AgentScope] = {}


def _register_default_scopes() -> None:
    """注册内置 subagent 默认作用域（幂等）。

    §3.79 v1.2.8 ⭐ 补全：与 subagent_registry（10 个）对齐——新增
    lesson_prep / resource_librarian（默认全工具，ratchet）。
    """
    _names = [
        "diagnostor", "planner", "presenter", "evaluator",
        "adapter", "answer_solver", "affection_supportor",
        "self_update_agent", "individuality",
        "lesson_prep", "resource_librarian",
    ]
    for _n in _names:
        if _n not in DEFAULT_AGENT_SCOPES:
            DEFAULT_AGENT_SCOPES[_n] = AgentScope(_n)


# #9 ⭐ 模块加载即注册默认作用域
_register_default_scopes()


def get_scope(name: Optional[str] = None) -> AgentScope:
    """获取 subagent 作用域；未知/为空 → 默认全工具（容错）。"""
    if not name:
        return AgentScope("_default")
    return DEFAULT_AGENT_SCOPES.get(name, AgentScope(name))


def register_scope(name: str, scope: AgentScope) -> None:
    """注册自定义 subagent 作用域（dsh 一切皆插件：作用域可插拔）。"""
    DEFAULT_AGENT_SCOPES[name] = scope


def is_tool_allowed_for_agent(agent_name: str, tool_name: str) -> bool:
    """便捷入口：按 subagent 名判断工具是否允许（供 tool_registry 联动）。"""
    return get_scope(agent_name).allow_tool(tool_name)


__all__ = [
    "AgentScope", "DEFAULT_AGENT_SCOPES",
    "get_scope", "register_scope", "is_tool_allowed_for_agent",
]
