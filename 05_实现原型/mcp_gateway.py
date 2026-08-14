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

    # v0.19.25：新增标准教育工具（外部 agent 也能调）
    @_mcp.tool()
    def generate_quiz(concept: str, subject: str = "math",
                      grade_level: str = "high_school", learner_id: str = "external") -> str:
        """根据知识点生成练习题（含答案与讲解）。"""
        try:
            from server import _handle_problem_request
            from paeg import LearnerProfile
            learner = LearnerProfile(id=learner_id, nickname="外部",
                                     grade_level=grade_level, age=18)
            resp = _handle_problem_request(learner, concept, subject)
            data = resp.get_json() if hasattr(resp, 'get_json') else resp
            pres = (data.get("presentations") or [{}])[0]
            return pres.get("content", "（未生成题目）")
        except Exception as e:
            return f"出题失败: {str(e)[:100]}"

    @_mcp.tool()
    def knowledge_search(query: str, subject: str = "") -> str:
        """在 PAEG 知识库/Library 中检索相关知识点。"""
        try:
            from knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            hits = kb.search(query, subject=subject, top_k=3)
            if not hits:
                return "（知识库中未找到相关节点）"
            parts = []
            for h in hits:
                node = kb.get_subject(h.get("concept_id", "")) or {}
                parts.append(f"- {h.get('concept_id','')}: {node.get('definition','') or node.get('intuition','')}")
            return "\n".join(parts)
        except Exception as e:
            return f"知识库检索失败: {str(e)[:100]}"

    # v0.70 §3.28 Phase 4 ⭐ 语言规范 MCP 标准化（外部 agent 也可调用 PAEG 语言规范能力）
    @_mcp.tool()
    def normalize_text(text: str, context: str = "", apply_l2: bool = True) -> str:
        """语言规范守门（L0+L2）：去除 AI 味、修正省略句/动宾搭配、深度矫正为最规范语言。"""
        return _run_tool("normalize_text", {"text": text, "context": context, "apply_l2": apply_l2})

    @_mcp.tool()
    def language_policy_check(text: str) -> str:
        """语言政策检查：本地确定性检测 AI 味概率与违禁词命中（不调 LLM）。"""
        return _run_tool("language_policy_check", {"text": text})

    @_mcp.tool()
    def forbidden_words(action: str, word: str = "", scope: str = "extra_forbidden") -> str:
        """外部违禁词数据维护（list/add/remove，落盘 forbidden_words.json）。"""
        return _run_tool("forbidden_words", {"action": action, "word": word, "scope": scope})

    # v0.70 §3.29 ⭐ L0-L8 约束系统 MCP 化（constraint_engine 6 API）
    @_mcp.tool()
    def constraint_layer_get(layer: int = 4) -> str:
        """读取 L0-L8 约束层（0-7）当前放开组与规则。"""
        return _run_tool("constraint_layer_get", {"layer": layer})

    @_mcp.tool()
    def constraint_layer_set(layer: int = 4, session: str = "", reason: str = "") -> str:
        """动态切换 L0-L8 约束层（教学/考试/自由）。返回该层约束配置段。"""
        return _run_tool("constraint_layer_set", {"layer": layer, "session": session, "reason": reason})

    @_mcp.tool()
    def constraint_compose(parts: list, title: str = "组合提示词") -> str:
        """任意提示词块组合拼接（如 WEIL_CORE+LANGUAGE_STYLE+约束段）。"""
        return _run_tool("constraint_compose", {"parts": parts, "title": title})

    @_mcp.tool()
    def constraint_always_active(action: str, rule: str = "") -> str:
        """永远激活提示词管理（list/add/remove，落盘 always_active.json）。"""
        return _run_tool("constraint_always_active", {"action": action, "rule": rule})

    @_mcp.tool()
    def constraint_self_evolve(insight: str, target_layer: int = 4, group: str = "D") -> str:
        """约束系统自我演化：把教学洞察提炼为约束规则写入指定层/组。"""
        return _run_tool("constraint_self_evolve",
                         {"insight": insight, "target_layer": target_layer, "group": group})

    @_mcp.tool()
    def constraint_feedback_adjust(feedback: str, target: str = "layer") -> str:
        """反馈调强/调弱约束（太啰嗦/太直接/太机械/太深等信号 → 调整建议 + 记录）。"""
        return _run_tool("constraint_feedback_adjust", {"feedback": feedback, "target": target})

    @_mcp.tool()
    def constraint_layer_scope() -> str:
        """约束层级框架自省：层范围（L0-Lmax）/内嵌与外部来源/可用组/扩展指南。"""
        return _run_tool("constraint_layer_scope", {})

    # v1.1 §3.35 ⭐ 物料流水线 MCP 化（多阶段+门控+自检范式，material_pipeline）
    @_mcp.tool()
    def generate_handout(topic: str, subject: str = "通用", learner_id: str = "anon") -> str:
        """生成结构化讲义（markdown，附概念/例题/小结），经语言规范门与门控流水线。"""
        return _run_tool("generate_handout",
                         {"topic": topic, "subject": subject, "learner_id": learner_id})

    @_mcp.tool()
    def generate_script(topic: str, subject: str = "通用", learner_id: str = "anon") -> str:
        """生成讲稿（含 TTS 朗读稿），经语言规范门。"""
        return _run_tool("generate_script",
                         {"topic": topic, "subject": subject, "learner_id": learner_id})

    @_mcp.tool()
    def generate_ppt(topic: str, subject: str = "通用", learner_id: str = "anon") -> str:
        """生成 PPT 大纲（供 pptx_mcp_server 排版），经门控流水线。"""
        return _run_tool("generate_ppt",
                         {"topic": topic, "subject": subject, "learner_id": learner_id})

    @_mcp.tool()
    def generate_mindmap(topic: str, subject: str = "通用", learner_id: str = "anon") -> str:
        """生成知识导图（markdown 缩进列表），经门控流水线。"""
        return _run_tool("generate_mindmap",
                         {"topic": topic, "subject": subject, "learner_id": learner_id})

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
