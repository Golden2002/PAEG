# -*- coding: utf-8 -*-
"""
PAEG MCP 客户端（v0.19.25 ⭐）

借鉴 oh-my-opencode / opencode 的 MCP 集成模式：
- opencode 用 opencode.json 的 mcp 字段声明外部标准 MCP server（npx 启动 @modelcontextprotocol/server-*）
- oh-my-opencode 用 Skill-Embedded MCP 按需加载

本模块让 PAEG 内部 LLM/subagent 也能通过 MCP 调用外部标准化工具：
1. mcp_servers.json 声明要连接的标准 MCP server（stdio + npx，与 opencode 同款）
2. MCPClientManager 用 fastmcp.Client 连接，缓存工具列表
3. list_tool_defs() → 转成 Function Calling schema 喂给 LLM（get_all_tool_defs 合并）
4. call_tool(name, args) → 路由到对应 server 执行

用法：
    from mcp_client import MCPClientManager
    mgr = MCPClientManager()
    defs = mgr.list_tool_defs()      # [{"type":"function",...}, ...]
    result = mgr.call_tool("mcp__filesystem__read_file", {"path": "..."})
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

# 配置：声明要连接的外部标准 MCP server
DEFAULT_CONFIG = {
    "filesystem": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem",
                    "C:/Users/团聚体"],
        "enabled": True,
        "note": "文件系统读写（opencode 同款标准 server）"
    },
    "memory": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-memory"],
        "enabled": True,
        "note": "知识图谱记忆（opencode 同款标准 server）"
    },
    "fetch": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-fetch"],
        "enabled": False,
        "note": "网页抓取（标准包名已变，默认关闭避免 npx 404）"
    },
    "git": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-git"],
        "enabled": False,
        "note": "Git 操作（默认关闭，按需启用）"
    },
}


def _load_config() -> Dict[str, dict]:
    """加载 mcp_servers.json（若存在），否则用默认配置。"""
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_servers.json')
    try:
        with open(cfg_path, encoding='utf-8') as f:
            user_cfg = json.load(f)
        if isinstance(user_cfg, dict) and user_cfg:
            return user_cfg
    except Exception:
        pass
    return DEFAULT_CONFIG


class MCPClientManager:
    """管理多个外部 MCP server 的连接与工具调用。"""

    def __init__(self, config: Optional[Dict[str, dict]] = None):
        self.config = config or _load_config()
        self._clients: Dict[str, Any] = {}       # server_name -> fastmcp Client
        self._tools: Dict[str, dict] = {}        # "mcp__server__tool" -> {"server", "name", "schema"}
        self._session_ctxs: Dict[str, Any] = {}  # server_name -> session ctx
        self._lock = threading.Lock()
        self._connected = False
        self._last_error = ""

    # ─── 连接（惰性 + 容错，异步实现） ───
    def connect_all(self) -> int:
        """连接所有启用的 MCP server。返回成功连接数（同步包装）。"""
        import asyncio
        try:
            return asyncio.run(self._connect_all_async())
        except Exception as e:
            self._last_error = f"连接异常: {str(e)[:120]}"
            return 0

    async def _connect_all_async(self) -> int:
        if self._connected:
            return len(self._clients)
        try:
            from fastmcp import Client
            from fastmcp.client.transports import StdioTransport
        except Exception as e:
            self._last_error = f"fastmcp 客户端不可用: {e}"
            return 0

        for name, cfg in self.config.items():
            if not cfg.get("enabled", True):
                continue
            cmd = cfg.get("command")
            if not cmd or not isinstance(cmd, list):
                continue
            try:
                transport = StdioTransport(command=cmd[0], args=cmd[1:])
                async with Client(transport) as client:
                    tools_result = await client.list_tools()
                    tool_list = getattr(tools_result, 'tools', None) or tools_result or []
                    with self._lock:
                        self._clients[name] = client
                        for t in tool_list:
                            tname = getattr(t, 'name', '') or ''
                            if not tname:
                                continue
                            schema = getattr(t, 'inputSchema', None) or {}
                            desc = getattr(t, 'description', '') or ''
                            self._tools[f"mcp__{name}__{tname}"] = {
                                "server": name, "name": tname,
                                "schema": schema, "description": desc,
                            }
                print(f"[PAEG][mcp-client] 连接 {name}: {len(tool_list)} 个工具")
            except Exception as e:
                print(f"[PAEG][mcp-client] 连接 {name} 失败（跳过）: {str(e)[:80]}")
        self._connected = True
        return len(self._clients)

    # ─── 工具定义（转 Function Calling schema） ───
    def list_tool_defs(self) -> List[dict]:
        """把所有外部 MCP 工具转成 Function Calling 格式（供 LLM 选择）。"""
        if not self._connected:
            self.connect_all()
        defs = []
        for full_name, info in self._tools.items():
            schema = info.get("schema") or {}
            defs.append({
                "type": "function",
                "function": {
                    "name": full_name,
                    "description": (f"[MCP:{info['server']}] {info.get('description','')[:200]}"),
                    "parameters": schema if isinstance(schema, dict) else {"type": "object", "properties": {}},
                },
            })
        return defs

    def has_tools(self) -> bool:
        if not self._connected:
            self.connect_all()
        return bool(self._tools)

    # ─── 调用 ───
    def call_tool(self, full_name: str, arguments: Dict[str, Any]) -> str:
        """调用外部 MCP 工具。full_name 形如 mcp__server__tool（同步包装）。"""
        if not self._connected:
            self.connect_all()
        info = self._tools.get(full_name)
        if not info:
            return f"未知 MCP 工具: {full_name}（可用: {list(self._tools.keys())[:10]}）"
        import asyncio
        try:
            return asyncio.run(self._call_tool_async(full_name, arguments, info))
        except Exception as e:
            return f"MCP 调用异常: {str(e)[:120]}"

    async def _call_tool_async(self, full_name: str, arguments: Dict[str, Any], info: dict) -> str:
        server = info["server"]
        tool = info["name"]
        # 每次调用新建 session（client 在 async with 结束后自动关闭）
        try:
            from fastmcp import Client
            from fastmcp.client.transports import StdioTransport
            cmd = self.config.get(server, {}).get("command")
            if not cmd:
                return f"MCP server {server} 未配置"
            transport = StdioTransport(command=cmd[0], args=cmd[1:])
            async with Client(transport) as client:
                result = await client.call_tool(tool, arguments or {})
            # 解析结果
            structured = getattr(result, 'structuredContent', None)
            if structured:
                return json.dumps(structured, ensure_ascii=False)
            content = getattr(result, 'content', None) or []
            texts = [c.text for c in content if getattr(c, 'text', None)]
            return "\n".join(texts) if texts else str(result)[:1000]
        except Exception as e:
            return f"MCP 工具调用失败（{server}/{tool}）: {str(e)[:120]}"

    # ─── 状态 ───
    def stats(self) -> dict:
        return {
            "connected_servers": list(self._clients.keys()),
            "tool_count": len(self._tools),
            "last_error": self._last_error,
        }


# 全局单例（供 tool_registry 复用）
_client_mgr: Optional[MCPClientManager] = None
_client_lock = threading.Lock()


def get_mcp_client() -> MCPClientManager:
    """获取全局 MCP 客户端单例。"""
    global _client_mgr
    with _client_lock:
        if _client_mgr is None:
            _client_mgr = MCPClientManager()
        return _client_mgr


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    mgr = get_mcp_client()
    n = mgr.connect_all()
    print(f"连接 {n} 个 MCP server，工具 {len(mgr._tools)} 个")
    print("状态:", mgr.stats())
    if mgr._tools:
        print("工具示例:", list(mgr._tools.keys())[:5])
