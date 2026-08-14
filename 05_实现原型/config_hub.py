# -*- coding: utf-8 -*-
"""v0.68+ ⭐ config_hub.py —— PAEG 统一配置中心（独立成套配置接口体系）

用户需求：智能体有独立的成套接口来配置 MCP、skills、hooks、workflows；
智能体内部有完整模块读取这些配置，并接入智能体的工具调用链——
"点搜索工具就能用上新搜索工具"。

架构（Oracle 设计）：
- ConfigHub 持有 4 个子模块（mcp/skills/hooks/workflows）+ 内置工具
- 统一出口：get_all_tool_defs()（LLM 看到的工具）+ execute_tool()（执行派发）
- 每个子模块独立配置（config/mcp_servers.json、config/skills.json、
  config/hooks.json、config/workflows/*.json），改配置即生效
- 阶段 1：MCP + Skills 统一化；阶段 2：Hooks；阶段 3：Workflows

用法：
    from config_hub import get_hub
    defs = get_hub().get_all_tool_defs()     # LLM 工具列表
    result = get_hub().execute_tool(name, args)  # 统一执行
    get_hub().reload_all()                    # 动态重载全部配置
"""
from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional


# v0.69+ §3.16 P0：spill 溢出防护阈值（工具返回超限截断，防 LLM 上下文爆掉）
_SPILL_MAX_CHARS = 12000


class ConfigHub:
    """统一配置中心：持有 MCP/Skills/Hooks/Workflows/内置工具 子模块。"""

    def __init__(self):
        self._lock = threading.RLock()
        self.mcp = None          # 延迟初始化（mcp_client.MCPClientManager）
        self.skills = None       # 延迟初始化（skill_registry.SkillRegistry）
        self.hooks = None        # 阶段 2（hooks_hub.HooksHub）
        self.workflows = None    # 阶段 3（workflows_hub.WorkflowsHub）
        self._init_sub_hubs()

    # ─── 初始化 ───
    def _init_sub_hubs(self):
        """初始化已实现的子模块（MCP + Skills）。Hooks/Workflows 阶段化接入。"""
        try:
            from mcp_client import get_mcp_client
            self.mcp = get_mcp_client()
        except Exception as _e:
            print(f"[config_hub] MCP 初始化失败: {_e}")
        try:
            from skill_registry import SkillRegistry
            self.skills = SkillRegistry()
        except Exception as _e:
            print(f"[config_hub] Skills 初始化失败: {_e}")
        # 阶段 2/3：hooks/workflows 接入点（模块存在时自动挂载）
        try:
            from hooks_hub import HooksHub
            self.hooks = HooksHub()
        except Exception:
            self.hooks = None
        try:
            from workflows_hub import WorkflowsHub
            self.workflows = WorkflowsHub()
        except Exception:
            self.workflows = None

    # ─── 统一重载 ───
    def reload_all(self):
        """动态重载全部配置（改 config/ 后调用即生效，无需重启）。"""
        with self._lock:
            if self.mcp is not None:
                try:
                    self.mcp.reload_all()
                except Exception as _e:
                    print(f"[config_hub] MCP reload 失败: {_e}")
            if self.skills is not None:
                try:
                    self.skills.reload()
                except Exception as _e:
                    print(f"[config_hub] Skills reload 失败: {_e}")
            if self.hooks is not None:
                try:
                    self.hooks.reload()
                except Exception:
                    pass
            if self.workflows is not None:
                try:
                    self.workflows.reload()
                except Exception:
                    pass

    # ─── LLM 工具列表（统一出口 1） ───
    def get_all_tool_defs(self) -> List[dict]:
        """LLM 视角的统一工具列表：内置 → MCP → Skills → Workflows。"""
        defs: List[dict] = []
        try:
            from tool_registry import get_tool_defs
            defs += get_tool_defs()          # 内置 7 个
        except Exception:
            pass
        if self.mcp is not None:
            try:
                defs += self.mcp.list_tool_defs()   # mcp__server__tool
            except Exception:
                pass
        if self.skills is not None:
            try:
                defs += self.skills.tool_defs()     # load_skill__name
            except Exception:
                pass
        if self.workflows is not None:
            try:
                defs += self.workflows.tool_defs()  # run_workflow__id
            except Exception:
                pass
        return defs

    # ─── 统一执行（统一出口 2，含 hooks 钩子） ───
    def execute_tool(self, name: str, arguments: dict) -> str:
        """统一执行入口：路由到 MCP/Skills/Workflows/内置工具，含 hooks 钩子。

        规则（与 tool_registry.execute_tool 对齐）：
        - mcp__*       → MCP 工具
        - load_skill__* → Skill 激活
        - run_workflow__* → Workflow 执行
        - 其他         → 内置 _HANDLERS
        """
        # tool.before 钩子（阶段 2）
        if self.hooks is not None:
            try:
                _ctx = self.hooks.run_hook("tool.before", {"tool": name, "args": arguments})
                if _ctx and _ctx.get("skip"):
                    return _ctx.get("skipped_result", "[hook 拦截]")
            except Exception:
                pass
        # v0.68+ ⭐ repeat-tool-reminder Guard（Step1.5：连续同工具调用超阈值 → 拦截提醒）
        if self.hooks is not None:
            try:
                _lid = arguments.get("learner_id") if isinstance(arguments, dict) else "_global"
                _rg = self.hooks.repeat_guard_check(name, learner_id=str(_lid or "_global"))
                if _rg.get("blocked"):
                    return _rg["message"]
            except Exception:
                pass
        # 路由
        _result = ""
        if name.startswith("mcp__"):
            if self.mcp is not None:
                _result = self.mcp.call_tool(name, arguments or {})
            else:
                _result = f"MCP 未初始化: {name}"
        elif name.startswith("load_skill__"):
            if self.skills is not None:
                _result = self.skills.activate(name[len("load_skill__"):])
            else:
                _result = f"Skills 未初始化: {name}"
        elif name.startswith("run_workflow__"):
            if self.workflows is not None:
                _result = self.workflows.invoke(name[len("run_workflow__"):], arguments or {})
            else:
                _result = f"Workflows 未初始化: {name}"
        else:
            try:
                from tool_registry import execute_tool as _exec
                _result = _exec(name, arguments)
            except Exception as _e:
                _result = f"工具执行失败 {name}: {_e}"
        # tool.after 钩子（阶段 2）
        if self.hooks is not None:
            try:
                self.hooks.run_hook("tool.after", {"tool": name, "args": arguments, "result": _result})
            except Exception:
                pass
        # v0.69+ §3.16 P0：spill 溢出防护（借鉴 deepseek-harness guard/prompt-overflow）——
        # 工具返回超长（MCP/PDF/联网大文档）会爆 LLM 上下文 → 截断 + 保留首尾 + 标记
        try:
            if isinstance(_result, str) and len(_result) > _SPILL_MAX_CHARS:
                _keep_head = _SPILL_MAX_CHARS * 3 // 4
                _keep_tail = _SPILL_MAX_CHARS - _keep_head
                _result = (_result[:_keep_head]
                           + f"\n\n[spill-guard] 工具 {name} 返回过长（{len(_result)} 字符），"
                             f"已截断保留首 {_keep_head} + 尾 {_keep_tail} 字符。需要全文请分段请求。\n\n"
                           + _result[-_keep_tail:])
        except Exception:
            pass
        return _result

    # ─── admin 查看 ───
    def list_all(self) -> dict:
        """列出全部配置状态（供 admin API / 调试）。"""
        out = {"mcp": {}, "skills": {}, "hooks": {}, "workflows": {}}
        if self.mcp is not None:
            try:
                out["mcp"]["tools"] = len(self.mcp._tools) if hasattr(self.mcp, "_tools") else 0
                out["mcp"]["servers"] = list(getattr(self.mcp, "config", {}).keys())
            except Exception:
                pass
        if self.skills is not None:
            try:
                out["skills"] = self.skills.stats()
            except Exception:
                pass
        if self.hooks is not None:
            try:
                out["hooks"] = self.hooks.list()
            except Exception:
                pass
        if self.workflows is not None:
            try:
                out["workflows"] = self.workflows.list()
            except Exception:
                pass
        return out


# ─── 全局单例 ───
_hub = None
_hub_lock = threading.Lock()


def get_hub() -> ConfigHub:
    """全局 ConfigHub 单例。"""
    global _hub
    with _hub_lock:
        if _hub is None:
            _hub = ConfigHub()
        return _hub


__all__ = ["ConfigHub", "get_hub"]
