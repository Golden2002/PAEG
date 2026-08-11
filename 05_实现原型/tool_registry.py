# -*- coding: utf-8 -*-
"""
PAEG 工具注册表（v0.19）

P0-1：DeepSeek 原生 Function Calling 的工具定义与执行。
每个工具：name / description / parameters(JSON Schema) / handler(函数)

现有工具：
- web_search      联网搜索（Bing/Tavily/Serper）
- verify_math     SymPy 数学表达式验证（计算题反幻觉）
- fetch_page      抓取网页正文
- daily_quote     获取每日一句
- save_doc        把回答保存为文档
- get_time        获取当前时间（含日期，帮助回答时效性问题）

用法：
    from tool_registry import TOOL_DEFS, execute_tool, run_agent_loop
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


# ─────────────────────────────────────
# 工具定义（OpenAI/DeepSeek Function Calling 格式）
# ─────────────────────────────────────

def _make_tool(name: str, description: str, properties: dict,
               required: List[str], risk: str = "read") -> dict:
    """构造工具定义。v0.46 ⭐ P0：风险分级（对照 OWASP Agentic Top10 / 发布标准）。

    risk 取值：
      - "read"   ：只读安全工具（检索/查询）——LLM 可自由调用
      - "write"  ：写入工具（上传/生成文件）——需策略门放行
      - "destructive"：破坏性工具（删除/覆盖）——需 HITL 人工确认（预留）
    风险分级元数据存入 _RISK_LEVELS，供执行前 policy gate 校验。
    """
    global _RISK_LEVELS
    _RISK_LEVELS[name] = risk
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# v0.46 ⭐ P0：工具风险分级注册表（执行前策略门依据）
_RISK_LEVELS: Dict[str, str] = {}


def get_tool_risk(name: str) -> str:
    """返回工具风险等级（默认 read——未知工具保守对待）。"""
    return _RISK_LEVELS.get(name, "read")


def is_tool_allowed(name: str, action: str = "auto") -> bool:
    """v0.46 ⭐ P0：工具调用策略门（对照调研 B 表安全维度）。

    规则：
      - read 工具：auto 模式允许（LLM 自主调用）
      - write/destructive 工具：默认拦截（需显式 HITL/人工确认）
    当前 PAEG 全部工具为 read 级（web_search/verify_math/fetch_page/daily_quote/get_time），
    未来加写工具时此处即拦截点。
    """
    risk = get_tool_risk(name)
    if risk == "read":
        return True
    # write/destructive：仅显式人工授权时放行
    return action == "manual_confirm"


def get_tool_defs() -> List[dict]:
    """返回全部工具的 Function Calling 定义。"""
    return [
        _make_tool(
            "web_search",
            "搜索网络获取最新/外部信息（新闻、版本、资料推荐、不熟悉的知识）。"
            "当学生的问题涉及最近事件、外部资源、或不在此前知识范围内时使用。",
            {"query": {"type": "string", "description": "搜索查询词（自然语言）"},
             "max_results": {"type": "integer", "description": "返回条数 1-8，默认 4"}},
            ["query"],
        ),
        _make_tool(
            "verify_math",
            "用 SymPy 符号计算验证数学表达式/等式/导数/积分。"
            "当学生给出数学答案需要验证、或涉及可符号化的计算时使用。返回验证结果。",
            {"expr": {"type": "string", "description": "要验证/计算的数学表达式，如 x**2-4 或 derivative 等"}},
            ["expr"],
        ),
        _make_tool(
            "fetch_page",
            "抓取指定网页的正文内容（转 markdown）。当搜索结果摘要不够、需要读全文时使用。",
            {"url": {"type": "string", "description": "要抓取的网页 URL"}},
            ["url"],
        ),
        _make_tool(
            "daily_quote",
            "获取今天的每日一句（薇依/约纳斯/胡塞尔/维特根斯坦/斯宾诺莎/怀特海）。"
            "当学生询问名言、格言、或想听一句有分量的话时使用。",
            {},
            [],
        ),
        _make_tool(
            "get_time",
            "获取当前日期和时间。当学生的问题涉及'今天/现在/最新/几号'等时效性内容时使用。",
            {},
            [],
        ),
        # v0.19.25：MCP-only 工具同步到 Function Calling 端（内部 LLM 也能用）
        _make_tool(
            "solve_problem",
            "做题：生成可作为标准答案的完整解答（论述/计算/证明题）。"
            "当学生明确要一道题的完整答案、解题过程或标准解时使用。",
            {"problem": {"type": "string", "description": "题目内容"},
             "subject": {"type": "string", "description": "学科（math/physics 等）"},
             "grade_level": {"type": "string", "description": "学段（high_school 等）"}},
            ["problem"],
        ),
        _make_tool(
            "save_document",
            "把当前回答保存为可下载的文档（markdown + HTML）。"
            "当学生想要'讲义/要点/笔记/文章'文件下载时使用。",
            {"title": {"type": "string", "description": "文档标题"},
             "content": {"type": "string", "description": "文档内容"},
             "subject": {"type": "string", "description": "学科（可选）"}},
            ["title", "content"],
        ),
    ]


# ─────────────────────────────────────
# 工具执行
# ─────────────────────────────────────

def _exec_web_search(query: str, max_results: int = 4) -> str:
    """搜索（v0.19.2 改进：失败自动换短查询重试，给 LLM 明确错误）。"""
    try:
        from web_search_tool import web_search
        result = web_search(query, max_results=min(max_results, 8))
        if "搜索未返回结果" in result or "未返回有效结果" in result:
            # 第一次失败 → 拆短查询重试（中文长短语 Bing 分词差）
            try:
                from web_search_tool import _shorten_query, _bing_search
                short_q = _shorten_query(query)
                if short_q and short_q != query:
                    short_results = _bing_search(short_q, min(max_results, 4))
                    if short_results:
                        parts = []
                        for i, r in enumerate(short_results, 1):
                            parts.append(f"[来源 {i}] {r.get('title','')}\n"
                                         f"URL: {r.get('url','')}\n{r.get('content','')}")
                        return "\n\n".join(parts)
            except Exception:
                pass
        return result
    except Exception as e:
        return f"搜索失败（请换更短的关键词重试）: {e}"


def _exec_verify_math(expr: str) -> str:
    try:
        import sympy as sp
        e = sp.sympify(expr)
        return (f"表达式解析成功：{sp.sstr(e)}\n"
                f"LaTeX: {sp.latex(e)}\n"
                f"数值（若可）：{e.evalf() if e.is_number else '非数值'}")
    except Exception as ex:
        return f"SymPy 解析失败: {ex}"


def _exec_fetch_page(url: str) -> str:
    try:
        from web_search_tool import fetch_page
        return fetch_page(url)[:4000]
    except Exception as e:
        return f"抓取失败: {e}"


def _exec_daily_quote() -> str:
    try:
        from quotes import quote_of_the_day
        q = quote_of_the_day()
        return f"「{q['text']}」——{q['author']} {q.get('source', '')}"
    except Exception as e:
        return f"获取失败: {e}"


def _exec_get_time() -> str:
    now = datetime.now()
    week = "一二三四五六日"[now.weekday()]
    return f"今天是 {now.strftime('%Y-%m-%d')} 星期{week} {now.strftime('%H:%M')}"


# 工具名 → 执行函数
# v0.19.2：接入 tool_recovery（错误恢复：重试 + 降级 + 指标）
try:
    from tool_recovery import with_recovery
    _RECOVERY = True
except Exception:
    _RECOVERY = False


def _wrap(name, fn, retries=2):
    """给工具加错误恢复装饰器（若 tool_recovery 可用）。"""
    if _RECOVERY:
        return with_recovery(max_retries=retries, tool_name=name)(fn)
    return fn


def _exec_solve_problem(problem: str, subject: str = "math",
                        grade_level: str = "high_school") -> str:
    """做题：生成标准答案。"""
    try:
        from problem_solver import solve_problem
        from llm_adapter import create_llm
        llm = create_llm("auto")
        r = solve_problem(llm, problem, subject=subject, grade_level=grade_level)
        ans = (r.get("answer") or "") + (f"\n[验证: {r.get('verification_note')}]"
                                         if r.get("verification_note") else "")
        return ans or "（未能生成答案）"
    except Exception as e:
        return f"做题失败: {str(e)[:100]}"


def _exec_save_document(title: str, content: str, subject: str = "通用") -> str:
    """保存为文档。"""
    try:
        from file_generator import FileGenerator
        from llm_adapter import create_llm
        llm = create_llm("auto")
        fg = FileGenerator(llm)
        md, html = fg.save_answer(content, title, subject)
        return f"已保存：{md}\nHTML: {html}"
    except Exception as e:
        return f"文档保存失败: {str(e)[:100]}"


_HANDLERS: Dict[str, Callable[..., str]] = {
    "web_search": _wrap("web_search", _exec_web_search, retries=2),
    "verify_math": _wrap("verify_math", _exec_verify_math, retries=1),
    "fetch_page": _wrap("fetch_page", _exec_fetch_page, retries=2),
    "daily_quote": _wrap("daily_quote", _exec_daily_quote, retries=1),
    "get_time": _wrap("get_time", _exec_get_time, retries=1),
    # v0.19.25：MCP-only 工具同步到 FC 端
    "solve_problem": _exec_solve_problem,
    "save_document": _exec_save_document,
}


def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    """执行工具（v0.19.3 改进：缓存 + 重试 + 明确错误建议）。

    v0.19.3：确定性工具（daily_quote/get_time/verify_math）走结果缓存，
    命中直接返回（0 延迟 + 省 token）。失败时返回含"修复建议"的错误信息。
    """
    handler = _HANDLERS.get(name)
    if not handler:
        # v0.19.25：fallback 到外部 MCP 工具（mcp__server__tool 形式）
        if name.startswith("mcp__"):
            try:
                from mcp_client import get_mcp_client
                return get_mcp_client().call_tool(name, arguments or {})
            except Exception as e:
                return f"MCP 工具 {name} 调用失败: {str(e)[:120]}"
        return f"未知工具: {name}（可用工具：{', '.join(_HANDLERS.keys())}）"
    if not isinstance(arguments, dict):
        arguments = {}

    # v0.19.3：工具结果缓存（确定性工具高价值缓存目标）
    try:
        from tool_cache import cached_call
        if name in ("daily_quote", "get_time", "verify_math"):
            # 注意：verify_math 失败会自动重试（_retry），缓存只存成功结果
            result, _from_cache = cached_call(name, arguments, handler)
            if name == "verify_math" and ("失败" in str(result) or "错误" in str(result)):
                expr = arguments.get("expr", "")
                retried = _retry_verify_math(expr)
                if retried:
                    return retried
            return str(result)
    except Exception:
        pass  # 缓存失败不影响正常执行

    try:
        result = str(handler(**arguments))
        # verify_math 失败时自动重试（简化/修正表达式）
        if name == "verify_math" and ("失败" in result or "错误" in result):
            expr = arguments.get("expr", "")
            retried = _retry_verify_math(expr)
            if retried:
                return retried
        return result
    except TypeError as e:
        # 参数不匹配：对无参工具（daily_quote/get_time）直接调用；
        # 有参工具直接给参数建议（不盲目重试，避免返回误导结果）
        if name in ("daily_quote", "get_time"):
            try:
                return str(handler())
            except Exception:
                pass
        return (f"工具 {name} 参数错误: {e}。"
                f"需要的参数：{_describe_params(name)}。请修正后重试。")
    except Exception as e:
        return f"工具 {name} 执行出错: {e}（请换一种方式重试）"


def _retry_verify_math(expr: str) -> str:
    """verify_math 失败时的重试策略：去空格、转中缀、补 *。"""
    if not expr:
        return ""
    try:
        import sympy as sp
        candidates = [expr]
        # 1. 去空格
        candidates.append(expr.replace(" ", ""))
        # 2. 隐式乘法：2x → 2*x
        import re
        candidates.append(re.sub(r'(\d)([a-zA-Zα-ωπ])', r'\1*\2', expr))
        for cand in candidates:
            try:
                e = sp.sympify(cand)
                return (f"表达式（经自动修正）解析成功：{sp.sstr(e)}\n"
                        f"LaTeX: {sp.latex(e)}")
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _describe_params(name: str) -> str:
    """返回工具需要的参数说明（供错误提示）。"""
    params = {
        "web_search": "query(str) 必填, max_results(int) 可选",
        "verify_math": "expr(str) 必填 - 数学表达式",
        "fetch_page": "url(str) 必填",
        "daily_quote": "无参数",
        "get_time": "无参数",
    }
    return params.get(name, "见工具描述")


# ─────────────────────────────────────
# 工具调用循环（agent loop 核心）
# ─────────────────────────────────────

# v0.19：P1-4 Skills 技能加载工具（合并进工具列表）
def get_all_tool_defs() -> List[dict]:
    """工具定义 + 技能加载定义 + 外部 MCP 工具（v0.19.25）。

    MCP 工具通过 mcp_client.MCPClientManager 合并进来，
    LLM 可用 mcp__server__tool 形式的工具名调用外部标准工具。
    """
    defs = get_tool_defs()
    try:
        from skill_registry import SkillRegistry
        reg = SkillRegistry()
        defs += reg.tool_defs()
    except Exception:
        pass
    # v0.19.25：合并外部 MCP 工具（filesystem/memory 等标准 server）
    try:
        from mcp_client import get_mcp_client
        _mcp = get_mcp_client()
        defs += _mcp.list_tool_defs()
    except Exception:
        pass
    return defs


def _exec_skill_load(name: str) -> str:
    """执行 load_skill__<名称>。"""
    try:
        from skill_registry import SkillRegistry
        reg = SkillRegistry()
        return reg.activate(name)
    except Exception as e:
        return f"技能加载失败: {e}"


def run_agent_loop(model, system: str, user_input: str,
                   max_iterations: int = 3, include_skills: bool = True,
                   history: Optional[List[dict]] = None) -> Dict[str, Any]:
    """让 LLM 自主决定是否调用工具/技能（最多 max_iterations 轮）。

    v0.20.2：新增 history 参数——在 user_input 前注入历史对话（多轮连贯性）。
    返回：{"answer": str, "tool_calls": [{"name","arguments","result"}]}
    """
    messages = list(history or [])
    messages.append({"role": "user", "content": user_input})
    tool_defs = get_all_tool_defs() if include_skills else get_tool_defs()
    calls_log: List[Dict[str, Any]] = []

    # v0.32 ⭐ 辅助：检测本轮是否调用了 web_search——供前端 badge 区分"知识库检索/网络检索"
    def _web_searched_flag() -> bool:
        return any(c.get("name") == "web_search" for c in calls_log)

    for _ in range(max_iterations):
        try:
            resp = model.chat(
                system=system,
                messages=messages,
                max_tokens=1500,
                temperature=0.7,
                tools=tool_defs,
                tool_choice="auto",
            )
        except Exception as e:
            return {"answer": f"（模型调用失败: {e}）", "tool_calls": calls_log,
                    "web_searched": _web_searched_flag()}

        # 若返回的是工具调用 JSON
        if resp.strip().startswith('{"tool_calls"'):
            try:
                data = json.loads(resp)
            except json.JSONDecodeError:
                return {"answer": resp, "tool_calls": calls_log,
                        "web_searched": _web_searched_flag()}

            tool_calls = data.get("tool_calls", [])
            if not tool_calls:
                return {"answer": resp, "tool_calls": calls_log,
                        "web_searched": _web_searched_flag()}

            # 执行所有工具调用并回传
            assistant_msg = {"role": "assistant", "content": None,
                             "tool_calls": [
                                 {"id": tc["id"], "type": "function",
                                  "function": {"name": tc["name"],
                                               "arguments": tc.get("arguments", "{}")}}
                                 for tc in tool_calls]}
            messages.append(assistant_msg)

            for tc in tool_calls:
                name = tc.get("name", "")
                try:
                    args = json.loads(tc.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if name.startswith("load_skill__"):
                    result = _exec_skill_load(name.replace("load_skill__", ""))
                else:
                    result = execute_tool(name, args)
                calls_log.append({"name": name, "arguments": args, "result": result[:200]})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                 "content": result})
            continue  # 下一轮让模型基于工具结果回答

        # 正常文本回答
        return {"answer": resp, "tool_calls": calls_log,
                "web_searched": _web_searched_flag()}

    return {"answer": "（工具调用轮数超限，停止）", "tool_calls": calls_log,
            "metrics": _tool_metrics(), "web_searched": _web_searched_flag()}


def _tool_metrics() -> dict:
    """收集工具调用指标（供 harness / Reflect 评估 tool-use）。"""
    try:
        from tool_recovery import get_metrics_summary
        return get_metrics_summary()
    except Exception:
        return {}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("工具定义数:", len(get_tool_defs()))
    for t in get_tool_defs():
        print(f"  - {t['function']['name']}: {t['function']['description'][:40]}")
    print("\n测试 execute_tool:")
    print("  get_time ->", execute_tool("get_time", {}))
    print("  verify_math ->", execute_tool("verify_math", {"expr": "x**2-4"}))
    print("  daily_quote ->", execute_tool("daily_quote", {})[:50])
