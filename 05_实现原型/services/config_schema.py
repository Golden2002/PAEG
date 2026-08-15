# -*- coding: utf-8 -*-
"""services/config_schema.py —— §3.42 W11 ⭐ 配置 schema 校验（v1.1.5）

需求（§3.42 W11）：config/*.json 加轻量 schema 校验——热重载时校验，
无效配置拒绝且不改变运行时状态；校验失败发 config.invalid 事件。

设计（轻量内联 schema，不引入 jsonschema 依赖）：
- 每个配置文件一个校验函数（hooks/agents/mcp_servers/mcp_tools）
- validate(name, data) → (ok, errors)
- 校验失败 → emit_event_typed("config/invalid")（需在 event_types 注册）
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


class ConfigValidator:
    """config/*.json 轻量校验器。"""

    def __init__(self):
        self._validators = {
            "hooks.json": self._validate_hooks,
            "agents.json": self._validate_agents,
            "mcp_servers.json": self._validate_mcp_servers,
            "mcp_tools.json": self._validate_mcp_tools,
        }

    # ─── 入口 ───
    def validate(self, name: str, data: Any) -> Tuple[bool, List[str]]:
        """校验配置。未知文件跳过（True）。"""
        v = self._validators.get(name)
        if v is None:
            return True, []
        if not isinstance(data, dict):
            return False, [f"{name}: 顶层应为对象"]
        return v(name, data)

    # ─── 各文件校验器 ───
    def _validate_hooks(self, name: str, data: dict) -> Tuple[bool, List[str]]:
        errs = []
        hooks = data.get("hooks") or []
        if not isinstance(hooks, list):
            return False, [f"{name}: hooks 应为列表"]
        for i, h in enumerate(hooks):
            if not isinstance(h, dict):
                errs.append(f"{name}: hooks[{i}] 应为对象")
                continue
            if not h.get("id"):
                errs.append(f"{name}: hooks[{i}] 缺 id")
            if not h.get("event"):
                errs.append(f"{name}: hooks[{i}] 缺 event")
            if not h.get("module") or not h.get("function"):
                errs.append(f"{name}: hooks[{i}] 缺 module/function")
            if "dispatch" in h and h["dispatch"] not in ("waterfall", "parallel", "serial", "emit"):
                errs.append(f"{name}: hooks[{i}] dispatch 非法: {h['dispatch']}")
        return (not errs), errs

    def _validate_agents(self, name: str, data: dict) -> Tuple[bool, List[str]]:
        errs = []
        agents = data.get("agents") or {}
        if not isinstance(agents, dict):
            return False, [f"{name}: agents 应为对象"]
        for an, cfg in agents.items():
            if not isinstance(cfg, dict):
                errs.append(f"{name}: agent[{an}] 应为对象")
                continue
            if "enabled" in cfg and not isinstance(cfg["enabled"], bool):
                errs.append(f"{name}: agent[{an}].enabled 应为布尔")
            if "temperature" in cfg and cfg["temperature"] is not None \
               and not isinstance(cfg["temperature"], (int, float)):
                errs.append(f"{name}: agent[{an}].temperature 应为数字")
        return (not errs), errs

    def _validate_mcp_servers(self, name: str, data: dict) -> Tuple[bool, List[str]]:
        errs = []
        servers = data.get("servers") or data.get("mcpServers") or {}
        if not isinstance(servers, dict):
            return False, [f"{name}: servers 应为对象"]
        for sname, scfg in servers.items():
            if not isinstance(scfg, dict):
                errs.append(f"{name}: server[{sname}] 应为对象")
                continue
            if not scfg.get("command"):
                errs.append(f"{name}: server[{sname}] 缺 command")
        return (not errs), errs

    def _validate_mcp_tools(self, name: str, data: dict) -> Tuple[bool, List[str]]:
        errs = []
        tools = data.get("tools") or []
        if not isinstance(tools, list):
            return False, [f"{name}: tools 应为列表"]
        for i, t in enumerate(tools):
            if not isinstance(t, dict):
                errs.append(f"{name}: tools[{i}] 应为对象")
                continue
            if not t.get("name"):
                errs.append(f"{name}: tools[{i}] 缺 name")
            if "risk" in t and t["risk"] not in ("read", "write", "destructive"):
                errs.append(f"{name}: tools[{i}].risk 非法: {t['risk']}")
        return (not errs), errs

    # ─── 集成入口：校验 + 事件 ───
    def validate_and_emit(self, name: str, data: Any) -> Tuple[bool, List[str]]:
        """校验 + 失败发 config.invalid 事件。"""
        ok, errs = self.validate(name, data)
        if not ok:
            try:
                from observability import emit_event_typed
                emit_event_typed("config/invalid",
                                 config=name, errors=errs[:5],
                                 count=len(errs))
            except Exception:
                pass
        return ok, errs


def validate_config(name: str, data: Any) -> Tuple[bool, List[str]]:
    """便捷入口。"""
    return ConfigValidator().validate(name, data)


__all__ = ["ConfigValidator", "validate_config"]
