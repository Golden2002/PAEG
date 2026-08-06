# -*- coding: utf-8 -*-
"""
PAEG MCP 工具网关（v0.19）

P0-3：把 PAEG 的能力暴露为标准 MCP（Model Context Protocol）服务器。
- 外部 MCP 客户端（Claude/Codex/OpenCode 等）可通过 http://host:8765/mcp 连接，
  复用 PAEG 的工具（搜索/数学验证/每日一句/做题/文档）。
- 同时保持内部函数调用（tool_registry.execute_tool）不受影响。

用法：
    # 单独启动 MCP 服务器（供外部智能体连接）：
    python mcp_gateway.py
    # 客户端连接 http://localhost:8765/mcp

    # 或作为模块在 server.py 中启动线程：
    from mcp_gateway import start_mcp_server
    start_mcp_server(port=8765)
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

try:
    from fastmcp import FastMCP

    _FASTMCP_OK = True
except Exception:
    _FASTMCP_OK = False


def _run_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
    """内部工具执行（复用 tool_registry）。"""
    from tool_registry import execute_tool
    return execute_tool(name, arguments or {})


def _solve_problem(problem: str, subject: str = "math",
                   grade_level: str = "high_school") -> str:
    """做题：生成标准答案。"""
    from problem_solver import solve_problem
    from llm_adapter import create_llm
    try:
        llm = create_llm("auto")
    except Exception:
        return "做题失败：LLM 不可用"
    r = solve_problem(llm, problem, subject=subject, grade_level=grade_level)
    return (r.get("answer") or "") + (f"\n[验证: {r.get('verification_note')}]" if r.get("verification_note") else "")


def _save_document(title: str, content: str, subject: str = "通用") -> str:
    """把内容保存为文档，返回路径。"""
    from file_generator import FileGenerator
    from llm_adapter import create_llm
    try:
        llm = create_llm("auto")
    except Exception:
        return "文档生成失败：LLM 不可用"
    fg = FileGenerator(llm)
    md, html = fg.save_answer(content, title, subject)
    return f"已保存：{md}\nHTML: {html}"


def _quote() -> str:
    from quotes import quote_of_the_day
    q = quote_of_the_day()
    return f"「{q['text']}」——{q['author']} {q.get('source','')}"


# ─────────────────────────────────────
# FastMCP 服务器构建
# ─────────────────────────────────────

_mcp = None


def build_mcp_server() -> Optional[Any]:
    """构建 FastMCP 服务器（含 PAEG 教育工具）。"""
    global _mcp
    if not _FASTMCP_OK:
        return None
    if _mcp is not None:
        return _mcp

    _mcp = FastMCP("PAEG Education Tools")

    @_mcp.tool()
    def web_search(query: str, max_results: int = 4) -> str:
        """搜索网络获取最新/外部信息。"""
        return _run_tool("web_search", {"query": query, "max_results": max_results})

    @_mcp.tool()
    def verify_math(expr: str) -> str:
        """用 SymPy 验证/计算数学表达式。"""
        return _run_tool("verify_math", {"expr": expr})

    @_mcp.tool()
    def fetch_page(url: str) -> str:
        """抓取网页正文（转 markdown）。"""
        return _run_tool("fetch_page", {"url": url})

    @_mcp.tool()
    def daily_quote() -> str:
        """获取每日一句。"""
        return _quote()

    @_mcp.tool()
    def get_time() -> str:
        """获取当前日期时间。"""
        return _run_tool("get_time", {})

    @_mcp.tool()
    def solve_problem(problem: str, subject: str = "math",
                      grade_level: str = "high_school") -> str:
        """做题：生成可作为考试标准答案的解答（论述/计算/证明）。"""
        return _solve_problem(problem, subject, grade_level)

    @_mcp.tool()
    def save_document(title: str, content: str, subject: str = "通用") -> str:
        """把内容保存为可下载文档。"""
        return _save_document(title, content, subject)

    return _mcp


# ─────────────────────────────────────
# 线程启动（供 server.py 集成）
# ─────────────────────────────────────

_server_thread = None


def start_mcp_server(port: int = 8765) -> bool:
    """在后台线程启动 MCP HTTP 服务器。返回是否启动成功。"""
    global _server_thread
    if not _FASTMCP_OK:
        print("[MCP] fastmcp 未安装，跳过 MCP 服务器")
        return False
    mcp = build_mcp_server()
    if mcp is None:
        return False

    def _run():
        try:
            mcp.run(transport="http", host="0.0.0.0", port=port)
        except Exception as e:
            print(f"[MCP] 服务器异常: {e}")

    if _server_thread is None or not _server_thread.is_alive():
        _server_thread = threading.Thread(target=_run, daemon=True)
        _server_thread.start()
        print(f"[MCP] 教育工具网关已启动: http://localhost:{port}/mcp")
        return True
    return False


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if not _FASTMCP_OK:
        print("fastmcp 不可用，请先 pip install fastmcp")
        sys.exit(1)
    print("启动 PAEG MCP 网关（HTTP）…")
    print("外部智能体可连接: http://localhost:8765/mcp")
    mcp = build_mcp_server()
    mcp.run(transport="http", host="0.0.0.0", port=8765)
