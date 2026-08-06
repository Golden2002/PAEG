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
               required: List[str]) -> dict:
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
    ]


# ─────────────────────────────────────
# 工具执行
# ─────────────────────────────────────

def _exec_web_search(query: str, max_results: int = 4) -> str:
    try:
        from web_search_tool import web_search
        return web_search(query, max_results=min(max_results, 8))
    except Exception as e:
        return f"搜索失败: {e}"


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
_HANDLERS: Dict[str, Callable[..., str]] = {
    "web_search": _exec_web_search,
    "verify_math": _exec_verify_math,
    "fetch_page": _exec_fetch_page,
    "daily_quote": _exec_daily_quote,
    "get_time": _exec_get_time,
}


def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    """执行工具，返回文本结果（给 LLM 看）。"""
    handler = _HANDLERS.get(name)
    if not handler:
        return f"未知工具: {name}"
    try:
        if not isinstance(arguments, dict):
            arguments = {}
        return str(handler(**arguments))
    except TypeError as e:
        # 参数不匹配：尝试忽略多余参数
        return str(handler())
    except Exception as e:
        return f"工具执行出错: {e}"


# ─────────────────────────────────────
# 工具调用循环（agent loop 核心）
# ─────────────────────────────────────

# v0.19：P1-4 Skills 技能加载工具（合并进工具列表）
def get_all_tool_defs() -> List[dict]:
    """工具定义 + 技能加载定义。"""
    defs = get_tool_defs()
    try:
        from skill_registry import SkillRegistry
        reg = SkillRegistry()
        defs += reg.tool_defs()
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
                   max_iterations: int = 3, include_skills: bool = True) -> Dict[str, Any]:
    """让 LLM 自主决定是否调用工具/技能（最多 max_iterations 轮）。

    返回：{"answer": str, "tool_calls": [{"name","arguments","result"}]}
    """
    messages = [{"role": "user", "content": user_input}]
    tool_defs = get_all_tool_defs() if include_skills else get_tool_defs()
    calls_log: List[Dict[str, Any]] = []

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
            return {"answer": f"（模型调用失败: {e}）", "tool_calls": calls_log}

        # 若返回的是工具调用 JSON
        if resp.strip().startswith('{"tool_calls"'):
            try:
                data = json.loads(resp)
            except json.JSONDecodeError:
                return {"answer": resp, "tool_calls": calls_log}

            tool_calls = data.get("tool_calls", [])
            if not tool_calls:
                return {"answer": resp, "tool_calls": calls_log}

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
        return {"answer": resp, "tool_calls": calls_log}

    return {"answer": "（工具调用轮数超限，停止）", "tool_calls": calls_log}


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
