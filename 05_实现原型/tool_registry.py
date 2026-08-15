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
import os
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


# v0.68+ ⭐ 权限预设（Step1.5：借鉴 deepseek-harness Permission Presets）
# 4 档预设：read-only（只读）/ standard（标准，教学默认）/ exam（考试模式，禁写）/ full（全量）
# 借鉴来源：deepseek-harness packages/bundle/base/cordis.patch.yml permission-presets
PERMISSION_PRESETS = {
    "read_only": {"desc": "只读：仅检索/查询类工具，禁止任何写操作",
                  "allow_write": False, "allow_web": True},
    "standard": {"desc": "标准：教学默认（读 + 联网 + 文档生成）",
                 "allow_write": True, "allow_web": True},
    "exam": {"desc": "考试模式：锁定写工具（禁讲义/PPT/视频/动画生成）",
             "allow_write": False, "allow_web": True},
    "full": {"desc": "全量：所有工具开放",
             "allow_write": True, "allow_web": True},
}

# 写类工具黑名单（exam/read_only 模式禁用）
_WRITE_TOOLS = {"save_document", "generate_handout", "generate_ppt", "generate_video",
                "generate_animation", "mcp__pptx__generate_presentation",
                "forbidden_words",          # v0.70 §3.28 Phase 4：违禁词维护属写操作
                "constraint_always_active",  # v0.70 §3.29：永远激活规则维护属写操作
                "constraint_self_evolve",    # v0.70 §3.29：约束自演化写入属写操作
                "generate_script",           # v1.1 §3.35：讲稿生成属写操作
                "generate_mindmap"}          # v1.1 §3.35：知识导图生成属写操作

_active_preset = "standard"  # 当前权限档（运行时可切换）


def set_permission_preset(preset: str) -> bool:
    """v0.68+ ⭐ 运行时切换权限档（如教师切"考试模式"）。

    #19 ⭐（§3.46.2 Harness P1）：切换成功后向 session_log 发射 permission/preset
    事件（记录 from→to），可回放审计——dsh permission/preset log-only 事件语义。
    """
    global _active_preset
    if preset not in PERMISSION_PRESETS:
        return False
    _prev = _active_preset
    _active_preset = preset
    # #19 ⭐ Permission 事件入 Session Log（切换可回放）
    try:
        from infra.session_log import get_session_log
        get_session_log().append(
            "permission/preset",
            {"from": _prev, "to": preset, "preset": preset},
        )
    except Exception:
        pass  # 日志发射失败不影响切换（容错）
    return True


def get_permission_preset() -> str:
    return _active_preset


def is_tool_allowed_by_preset(name: str) -> bool:
    """v0.68+ ⭐ 按当前权限档判定工具是否允许（exam 模式锁写工具）。"""
    _cfg = PERMISSION_PRESETS.get(_active_preset, PERMISSION_PRESETS["standard"])
    if not _cfg["allow_write"] and name in _WRITE_TOOLS:
        return False
    return True


def get_tool_defs() -> List[dict]:
    """返回全部工具的 Function Calling 定义。"""
    return _apply_config_meta([
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
        _make_tool(
            "compose_dynamic_prompt",
            "获取自我更新的动态提示词补丁（学科教学改进/工具经验/教师笔记）。"
            "当你需要最新自我改进建议来调整教学时调用——将返回的动态段与当前 system 合并参考。",
            {},
            [],
        ),
        # v0.70+ §3.28 Phase 4 ⭐ 语言规范 MCP 标准化
        _make_tool(
            "normalize_text",
            "语言规范守门：对生成内容（讲义/讲稿/视频/PPT 文案等）做 L0+L2 双层语言规范处理——"
            "去除 AI 味、修正省略句/动宾搭配、深度矫正为最规范语言。"
            "当一段文本将交付给学生/外部使用、且需要保证语言质量时调用。",
            {"text": {"type": "string", "description": "待规范的文本"},
             "context": {"type": "string", "description": "上下文（可选）"},
             "apply_l2": {"type": "boolean", "description": "是否启用 L2 深度矫正（默认 true）"}},
            ["text"],
        ),
        _make_tool(
            "language_policy_check",
            "语言政策检查：本地确定性检测文本的 AI 味概率与违禁词命中（不调 LLM）。"
            "返回 AI 味概率与命中违禁词列表，供判断是否需要改写。",
            {"text": {"type": "string", "description": "待检查的文本"}},
            ["text"],
        ),
        _make_tool(
            "forbidden_words",
            "外部违禁词数据维护（list/add/remove，落盘 data/forbidden_words.json）。"
            "scope 可选 extra_forbidden（网络用语/AI 腔）、pseudo_empathy_verbs（伪共情）、ai_tells_extra（套话）。"
            "当需要动态增删语言规范禁词时调用。",
            {"action": {"type": "string", "description": "操作：list / add / remove"},
             "word": {"type": "string", "description": "add/remove 的违禁词"},
             "scope": {"type": "string", "description": "分类：extra_forbidden / pseudo_empathy_verbs / ai_tells_extra"}},
            ["action"],
            risk="write",
        ),
        # v0.70 §3.29 ⭐ L0-L8 约束系统 MCP 化（constraint_engine 6 API）
        _make_tool(
            "constraint_layer_get",
            "读取 L0-L8 约束层（0-7）当前放开组与规则。"
            "当需要了解某约束层内容、或确认当前约束状态时调用。",
            {"layer": {"type": "integer", "description": "层号 0-7（默认 4）"}},
            [],
        ),
        _make_tool(
            "constraint_layer_set",
            "动态切换 L0-L8 约束层（教学/考试/自由）。返回该层约束配置段，"
            "可拼接进 system prompt。当需要按场景调整约束严格度时调用。",
            {"layer": {"type": "integer", "description": "目标层 0-7（默认 4 标准新授）"},
             "session": {"type": "string", "description": "会话标识（可选）"},
             "reason": {"type": "string", "description": "切换原因（记录用）"}},
            [],
        ),
        _make_tool(
            "constraint_compose",
            "任意提示词块组合拼接（如 WEIL_CORE+LANGUAGE_STYLE+约束段）。"
            "当需要把多个提示词块合成一个 system prompt 时调用。",
            {"parts": {"type": "array", "items": {"type": "string"}, "description": "提示词块列表"},
             "title": {"type": "string", "description": "组合标题（默认'组合提示词'）"}},
            ["parts"],
        ),
        _make_tool(
            "constraint_always_active",
            "永远激活提示词管理（list/add/remove，落盘 always_active.json）。"
            "这些规则不随约束层放开，任何层都保留。当需要固定某条规则永远生效时调用。",
            {"action": {"type": "string", "description": "操作：list / add / remove"},
             "rule": {"type": "string", "description": "add/remove 的规则文本"}},
            ["action"],
            risk="write",
        ),
        _make_tool(
            "constraint_self_evolve",
            "约束系统自我演化：把教学洞察提炼为约束规则写入指定层/组（数据化落盘）。"
            "当从教学反思中发现可复用的约束改进时调用。",
            {"insight": {"type": "string", "description": "教学洞察/新规则文本"},
             "target_layer": {"type": "integer", "description": "目标层 0-7（默认 4）"},
             "group": {"type": "string", "description": "目标组 M/R/T/D/S/P（默认 D 教学法深度）"}},
            ["insight"],
            risk="write",
        ),
        _make_tool(
            "constraint_feedback_adjust",
            "反馈调强/调弱约束：根据用户反馈（太啰嗦/太直接/太机械/太深等信号）"
            "给出约束调整建议并记录。当用户对输出风格/深度不满时调用。",
            {"feedback": {"type": "string", "description": "用户反馈文本"},
             "target": {"type": "string", "description": "调整目标 layer/group/active（默认 layer）"}},
            ["feedback"],
        ),
        _make_tool(
            "constraint_layer_scope",
            "约束层级框架自省：返回当前层范围（L0-Lmax）、内嵌层与外部扩展层来源、"
            "可用约束组、以及如何扩展（更换层内容/拓展更多层级/新增组）。"
            "当需要了解约束系统可扩展性或指导他人二次开发时调用。",
            {},
            [],
        ),
        # v1.1 §3.35 ⭐ 物料流水线 MCP 化（多阶段+门控+自检范式，material_pipeline）
        _make_tool(
            "generate_handout",
            "生成结构化讲义（markdown 双格式，附概念/例题/小结），经语言规范门与门控流水线。"
            "当学生需要完整讲解材料时调用。",
            {"topic": {"type": "string", "description": "教学主题"},
             "subject": {"type": "string", "description": "学科（默认通用）"},
             "learner_id": {"type": "string", "description": "学习者 ID（可选）"}},
            ["topic", "subject"],
            risk="write",
        ),
        _make_tool(
            "generate_script",
            "生成讲稿（含 TTS 朗读稿，按幕分段），经语言规范门。当学生需要讲解脚本/口播稿时调用。",
            {"topic": {"type": "string", "description": "教学主题"},
             "subject": {"type": "string", "description": "学科（默认通用）"},
             "learner_id": {"type": "string", "description": "学习者 ID（可选）"}},
            ["topic", "subject"],
            risk="write",
        ),
        _make_tool(
            "generate_ppt",
            "生成 PPT 大纲（封面 + 3-6 页正文 + 结尾，供 pptx_mcp_server 排版），经门控流水线。"
            "当学生需要演示文稿时调用。",
            {"topic": {"type": "string", "description": "教学主题"},
             "subject": {"type": "string", "description": "学科（默认通用）"},
             "learner_id": {"type": "string", "description": "学习者 ID（可选）"}},
            ["topic", "subject"],
            risk="write",
        ),
        _make_tool(
            "generate_mindmap",
            "生成知识导图（中心主题 + 3-5 一级分支 + 2-4 二级节点，markdown 缩进列表），经门控流水线。"
            "当学生需要知识结构图/思维导图时调用。",
            {"topic": {"type": "string", "description": "教学主题"},
             "subject": {"type": "string", "description": "学科（默认通用）"},
             "learner_id": {"type": "string", "description": "学习者 ID（可选）"}},
            ["topic", "subject"],
            risk="write",
        ),
    ] + _extended_tool_defs() + _config_tool_defs())


# ─────────────────────────────────────
# #14 ⭐ Tool Registry 能力协商（Harness 30 项 P1，§3.46.2，2026-08-16）
# dsh 借鉴（defer_loading + listChanged，commit 47f9438）：
# 工具元数据先注入 name/desc（轻量，省上下文），完整定义按需加载；变更可追踪。
# ─────────────────────────────────────

# 工具注册表版本号（register_external_tools 等注册点递增——listChanged 语义）
_TOOL_REVISION: int = 0


def _bump_tool_revision() -> None:
    """工具注册表变更时递增版本号（listChanged 追踪）。"""
    global _TOOL_REVISION
    _TOOL_REVISION += 1


def get_tool_metadata() -> List[dict]:
    """返回工具轻量元数据（name/description/risk——不含完整 parameters）。

    供 LLM 上下文先注入名称与用途（省 token），完整定义按需 get_tool_full_def()。
    """
    meta = []
    for d in get_tool_defs():
        fn = d.get("function", {})
        meta.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "risk": get_tool_risk(fn.get("name", "")),
        })
    return meta


def get_tool_full_def(name: str) -> Optional[dict]:
    """按需返回工具完整定义（含 parameters）；未知 → None（容错）。"""
    for d in get_tool_defs():
        fn = d.get("function", {})
        if fn.get("name") == name:
            return d
    return None


def get_tool_revision() -> int:
    """返回工具注册表当前版本号（listChanged 追踪基线）。"""
    return _TOOL_REVISION


def list_changed_since(seq: int) -> List[str]:
    """返回自 seq 版本以来新增/变更的工具名（dsh listChanged 语义）。

    简化实现：当前全部工具名（PAEG 工具集静态为主，MCP/skills/workflows 经
    register_external_tools 合并时 _bump_tool_revision 递增——调用方用
    get_tool_revision() 对比即知是否有变更）。
    """
    _ = seq  # 版本对比由调用方 get_tool_revision() 完成
    return [d.get("function", {}).get("name", "") for d in get_tool_defs()]


def _apply_config_meta(defs: List[dict]) -> List[dict]:
    """§3.36 ⭐ 配置驱动元数据覆盖：JSON 声明的 description/params 覆盖内置工具。

    - 内置工具（tool_registry 硬编码）默认保留 handler，仅元数据被配置覆盖
    - 覆盖 handler 需 JSON 显式 override:true（此处只处理元数据层）
    """
    try:
        from mcp_tools_loader import get_loaded_meta
        meta = get_loaded_meta()
        if not meta:
            return defs
        out = []
        for d in defs:
            name = d.get("function", {}).get("name", "")
            m = meta.get(name)
            if m:
                d2 = json.loads(json.dumps(d))  # deep copy
                d2["function"]["description"] = m.get("description", d2["function"]["description"])
                if m.get("risk"):
                    _RISK_LEVELS[name] = m["risk"]
                # params 覆盖（若配置声明了 params）
                if m.get("params"):
                    _props = {}
                    for k, v in m["params"].items():
                        if isinstance(v, dict) and "type" in v:
                            _props[k] = v
                        elif isinstance(v, str):
                            _props[k] = {"type": v}
                        else:
                            _props[k] = {"type": "string"}
                    d2["function"]["parameters"]["properties"] = _props
                    if m.get("required"):
                        d2["function"]["parameters"]["required"] = m["required"]
                out.append(d2)
            else:
                out.append(d)
        return out
    except Exception:
        return defs


def _config_tool_defs() -> List[dict]:
    """§3.36 ⭐ 配置驱动的外部工具定义（mcp_tools.json 声明、非内置的工具）。"""
    try:
        from mcp_tools_loader import get_loaded_defs
        return get_loaded_defs()
    except Exception:
        return []


def register_external_tools() -> int:
    """§3.36 ⭐ 合并配置驱动的外部工具到 _HANDLERS + _WRITE_TOOLS 同步。

    返回本次注册的外部工具数。幂等：重复调用重新同步。
    - 外部 handler 合入 _HANDLERS（覆盖内置需 override:true）
    - risk=write 的工具自动加入 _WRITE_TOOLS（exam 模式锁定）
    - §3.42 W5：timeoutMs 字段同步到 _HANDLERS_TIMEOUT_MS（未声明不动）
    - 失败不抛异常（保留现有工具表）
    """
    try:
        from mcp_tools_loader import get_loaded_handlers, get_loaded_meta
        handlers = get_loaded_handlers()
        meta = get_loaded_meta()
        if handlers:
            for name, fn in handlers.items():
                _HANDLERS[name] = fn
                if not callable(_HANDLERS.get(name)):
                    _HANDLERS.pop(name, None)
        if meta:
            for name, m in meta.items():
                if m.get("risk") == "write":
                    _WRITE_TOOLS.add(name)
                if m.get("risk") == "read":
                    _WRITE_TOOLS.discard(name)
                _RISK_LEVELS[name] = m.get("risk", "read")
                # §3.42 W5：timeoutMs 同步到 _HANDLERS_TIMEOUT_MS（ratchet：未声明不动）
                _tms = m.get("timeoutMs")
                if isinstance(_tms, (int, float)) and _tms > 0:
                    _HANDLERS_TIMEOUT_MS[name] = int(_tms)
                elif name in _HANDLERS_TIMEOUT_MS and _tms is None:
                    # 显式 None/缺失 → 保留默认值（不抹掉）
                    pass
        # #14 ⭐ 外部工具注册后递增版本号（listChanged 追踪）
        _bump_tool_revision()
        return len(handlers)
    except Exception:
        return 0


_ext_defs_cache = None      # v0.68+ 缓存（避免重复初始化 config_hub）
_ext_defs_loading = False   # 递归守卫（ConfigHub 初始化链中重入时返回空）


def _extended_tool_defs() -> list:
    """v0.68+ P0-3 修复（Step4）：合并 config_hub 的扩展工具（skills/MCP/workflows），
    使 LLM 在 run_agent_loop 中真正看到 load_skill__*/mcp__*/run_workflow__*。
    失败/重入时降级为仅内置（不阻断）。"""
    global _ext_defs_cache, _ext_defs_loading
    if _ext_defs_cache is not None:
        return _ext_defs_cache
    if _ext_defs_loading:
        return []  # 递归守卫：get_hub() 初始化链重入时返回空
    _ext_defs_loading = True
    try:
        from config_hub import get_hub
        _hub = get_hub()
        _ext = list(_hub.get_all_tool_defs()) if _hub is not None else []
        # 去重：跳过内置工具（get_tool_defs 已含）——必须与 get_tool_defs 全量同步，
        # 否则 config_hub 回灌内置定义时产生重复（v0.70 §3.28 Phase 4 修复）
        _BUILTIN_NAMES = {"web_search", "verify_math", "fetch_page",
                          "daily_quote", "get_time", "solve_problem", "save_document",
                          "compose_dynamic_prompt",
                          "normalize_text", "language_policy_check", "forbidden_words",
                          "constraint_layer_get", "constraint_layer_set", "constraint_compose",
                          "constraint_always_active", "constraint_self_evolve",
                          "generate_handout", "generate_script", "generate_ppt", "generate_mindmap",
                          "constraint_feedback_adjust", "constraint_layer_scope"}
        _ext = [d for d in _ext
                if isinstance(d, dict)
                and d.get("function", {}).get("name") not in _BUILTIN_NAMES]
        _seen = {d.get("function", {}).get("name") for d in _ext if isinstance(d, dict)}
        # 补上 workflows 工具声明（若 config_hub 未含）
        try:
            from workflows_hub import get_workflows_hub
            _wf = get_workflows_hub()
            _wf_items = []
            try:
                _wf_dict = _wf.list() if hasattr(_wf, "list") else {}
                if isinstance(_wf_dict, dict):
                    _wf_items = _wf_dict.get("workflows", []) or []
                elif isinstance(_wf_dict, list):
                    _wf_items = _wf_dict
            except Exception:
                _wf_items = []
            for _wfd in _wf_items:
                _wn = _wfd.get("id") if isinstance(_wfd, dict) else str(_wfd)
                if not _wn:
                    continue
                _n = f"run_workflow__{_wn}"
                if _n not in _seen:
                    _ext.append({
                        "type": "function",
                        "function": {
                            "name": _n,
                            "description": f"执行教学工作流 {_wn}（DAG：诊断→计划→实施→评估）",
                            "parameters": {"type": "object",
                                           "properties": {"concept": {"type": "string"},
                                                          "subject": {"type": "string"}},
                                           "required": ["concept"]},
                        },
                    })
                    _seen.add(_n)
        except Exception:
            pass
        _ext_defs_cache = _ext
        return _ext
    except Exception:
        return []
    finally:
        _ext_defs_loading = False


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


def _exec_compose_dynamic_prompt(*args, **kwargs) -> str:
    """v0.69+ §3.8：动态提示词拼接 tool——返回当前自我更新的动态反思补丁
    （subject_patches 学科补丁 / tool_lessons 工具经验 / teacher_notes 教师笔记 / 方法论）。
    LLM 调用后可将动态段与固定 system prompt 合并（每次发送时动态刷新）。"""
    try:
        from teaching_memory import load_teaching_memory
        _mem = load_teaching_memory()
        if _mem and _mem.strip():
            return f"[动态提示词补丁（自进化，供合并参考）]\n{_mem[:1800]}"
        return "[动态提示词补丁] 当前无动态补丁"
    except Exception as e:
        return f"[动态提示词补丁] 读取失败: {str(e)[:100]}"


# ─────────────────────────────────────
# v0.70+ §3.28 Phase 4 ⭐ 语言规范 MCP 标准化（三工具）
#   normalize_text          → 统一语言规范入口（L0+L2，同 lang_gate.gate_content）
#   language_policy_check   → 违禁词/AI 味本地确定性检测（不调 LLM）
#   forbidden_words         → 外部违禁词数据维护（add/remove/list，落盘 forbidden_words.json）
# ─────────────────────────────────────

_FORBIDDEN_WORDS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "forbidden_words.json")


def _load_forbidden_data() -> dict:
    """读取外部违禁词数据（缺失/损坏 → 空骨架，不抛异常）。"""
    try:
        with open(_FORBIDDEN_WORDS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"extra_forbidden": [], "pseudo_empathy_verbs": [], "ai_tells_extra": []}


def _save_forbidden_data(data: dict) -> bool:
    """写回外部违禁词数据（保持原有其他键）。"""
    try:
        with open(_FORBIDDEN_WORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _exec_normalize_text(text: str, context: str = "", apply_l2: bool = True) -> str:
    """v0.70 §3.28 Phase 4：语言规范守门（L0 polish + L2 深度矫正）。
    生成内容（讲义/讲稿/视频/PPT 等）产出后调用，得到最规范语言。
    失败静默回退原文（不阻塞生成）。"""
    if not text or not text.strip():
        return text
    try:
        from services.lang_gate import lang_gate_content
        return lang_gate_content(text, context=context, apply_l2=bool(apply_l2))
    except Exception:
        return text


def _exec_language_policy_check(text: str) -> str:
    """v0.70 §3.28 Phase 4：本地确定性检测违禁词 + AI 味（不调 LLM）。
    返回 AI 味概率 + 命中的违禁词列表，供外部 agent 自行决定是否重写。"""
    if not text or not text.strip():
        return "文本为空"
    report = []
    # 1) AI 味概率（ai_taste_detector）
    ai_prob = 0.0
    try:
        from ai_taste_detector import detect_ai_taste
        sig = detect_ai_taste(text)
        ai_prob = getattr(sig, "ai_likelihood", 0.0)
    except Exception:
        pass
    report.append(f"AI 味概率: {ai_prob:.2f}（>=0.4 建议改写）")
    # 2) 违禁词命中（内嵌 AI_TELLS + 外部 forbidden_words.json）
    hits = []
    try:
        from infra.runtime import get_paeg
        paeg = get_paeg()
        if paeg is not None and getattr(paeg, "refiner", None) is not None:
            hits = paeg.refiner.detect_ai_tells(text)
    except Exception:
        # 无 paeg 运行时 → 退化：直接加载 LanguageRefiner 类检测
        try:
            from language_refiner import LanguageRefiner
            _r = LanguageRefiner(llm=None)
            hits = _r.detect_ai_tells(text)
        except Exception:
            hits = []
    if hits:
        report.append(f"违禁词命中 {len(hits)} 个: {', '.join(hits[:10])}")
    else:
        report.append("违禁词命中: 0")
    return "\n".join(report)


def _exec_forbidden_words(action: str, word: str = "", scope: str = "extra_forbidden") -> str:
    """v0.70 §3.28 Phase 4：外部违禁词数据维护（write 级工具）。
    action ∈ {list, add, remove}；scope ∈ {extra_forbidden, pseudo_empathy_verbs, ai_tells_extra}。"""
    data = _load_forbidden_data()
    if scope not in data or not isinstance(data.get(scope), list):
        scope = "extra_forbidden"
    words = data.setdefault(scope, [])
    action = (action or "list").strip().lower()
    if action == "add":
        w = (word or "").strip()
        if not w:
            return "参数错误：add 需要 word"
        if w not in words:
            words.append(w)
            if _save_forbidden_data(data):
                return f"已添加违禁词「{w}」到 {scope}（共 {len(words)} 项）"
            return f"添加失败：写入 {_FORBIDDEN_WORDS_PATH} 出错"
        return f"「{w}」已在 {scope} 中（共 {len(words)} 项）"
    if action == "remove":
        w = (word or "").strip()
        if not w:
            return "参数错误：remove 需要 word"
        if w in words:
            words.remove(w)
            if _save_forbidden_data(data):
                return f"已移除违禁词「{w}」（剩余 {len(words)} 项）"
            return f"移除失败：写入 {_FORBIDDEN_WORDS_PATH} 出错"
        return f"「{w}」不在 {scope} 中"
    if action == "list":
        if not words:
            return f"{scope}: （空）"
        return f"{scope}（{len(words)} 项）: " + "、".join(words[:30])
    return f"未知操作: {action}（可用: list / add / remove）"


def _exec_constraint(name: str, arguments: dict) -> str:
    """v0.70 §3.29：转发到 constraint_engine 约束引擎执行。"""
    try:
        from constraint_engine import execute as _ce_execute
        return _ce_execute(name, arguments or {})
    except Exception as e:
        return f"约束引擎 {name} 调用失败: {str(e)[:120]}"


def _exec_material(material_type: str, arguments: dict) -> str:
    """v1.1 §3.35 ⭐ 物料流水线执行器：转发到 material_pipeline.run_material_pipeline。

    风险：写盘 + 调 LLM——按权限预设拦截（与 save_document 同策略）。
    """
    try:
        if not is_tool_allowed_by_preset(f"generate_{material_type}"):
            return f"权限档拦截：当前预设不允许 generate_{material_type}"
        from material_pipeline import run_material_pipeline
        from llm_adapter import create_llm
        llm = create_llm("auto")
        args = arguments or {}
        result = run_material_pipeline(
            llm, material_type,
            args.get("topic", ""),
            args.get("subject", "通用"),
            args.get("learner_id", "anon"),
        )
        return json.dumps({"ok": result.get("ok"), "errors": result.get("errors", []),
                           "output": str(result.get("output", ""))[:500],
                           "path": result.get("path", "")}, ensure_ascii=False)
    except Exception as e:
        return f"物料流水线 {material_type} 调用失败: {str(e)[:120]}"


_HANDLERS: Dict[str, Callable[..., str]] = {
    "web_search": _wrap("web_search", _exec_web_search, retries=2),
    "verify_math": _wrap("verify_math", _exec_verify_math, retries=1),
    "fetch_page": _wrap("fetch_page", _exec_fetch_page, retries=2),
    "daily_quote": _wrap("daily_quote", _exec_daily_quote, retries=1),
    "get_time": _wrap("get_time", _exec_get_time, retries=1),
    # v0.19.25：MCP-only 工具同步到 FC 端
    "solve_problem": _exec_solve_problem,
    "save_document": _exec_save_document,
    # v0.69+ §3.8 ⭐ 动态提示词拼接（用户核心设想）：LLM 主动调取自我更新的动态反思补丁
    "compose_dynamic_prompt": _exec_compose_dynamic_prompt,
    # v0.70+ §3.28 Phase 4 ⭐ 语言规范 MCP 标准化（三工具）
    "normalize_text": _exec_normalize_text,
    "language_policy_check": _exec_language_policy_check,
    "forbidden_words": _exec_forbidden_words,
    # v0.70 §3.29 ⭐ L0-L8 约束系统 MCP 化（constraint_engine 6 API 转发）
    "constraint_layer_get": lambda **kw: _exec_constraint("constraint_layer_get", kw),
    "constraint_layer_set": lambda **kw: _exec_constraint("constraint_layer_set", kw),
    "constraint_compose": lambda **kw: _exec_constraint("constraint_compose", kw),
    "constraint_always_active": lambda **kw: _exec_constraint("constraint_always_active", kw),
    "constraint_self_evolve": lambda **kw: _exec_constraint("constraint_self_evolve", kw),
    "constraint_feedback_adjust": lambda **kw: _exec_constraint("constraint_feedback_adjust", kw),
    "constraint_layer_scope": lambda **kw: _exec_constraint("constraint_layer_scope", kw),
    # v1.1 §3.35 ⭐ 物料流水线 MCP 化（handout/script/ppt/mindmap）
    "generate_handout": lambda **kw: _exec_material("handout", kw),
    "generate_script": lambda **kw: _exec_material("script", kw),
    "generate_ppt": lambda **kw: _exec_material("ppt", kw),
    "generate_mindmap": lambda **kw: _exec_material("mindmap", kw),
}

# §3.36 ⭐ 配置驱动：启动即合并外部工具（mcp_tools.json 声明；失败不阻塞）
# §3.42 W5 ⭐ 工具超时策略：声明 _HANDLERS_TIMEOUT_MS 在 register_external_tools 之前
#   （register_external_tools 会把 JSON 声明的 timeoutMs 同步进来）
_HANDLERS_TIMEOUT_MS: Dict[str, int] = {}
try:
    register_external_tools()
except Exception:
    pass


# ─────────────────────────────────────
# §3.42 W5 ⭐ 工具超时策略（tool-timeout-policy）
# ─────────────────────────────────────

# 工具名 → timeoutMs（毫秒）。声明的工具走 watchdog；未声明的走默认 30s。
# （声明已在上方 §3.36 块完成，此处不再重复——避免重复定义）


def _get_default_timeout_ms() -> int:
    """§3.42 W5 默认 timeoutMs（毫秒）。可被 config/hooks.json 的
    `tools.default_timeout_ms` 覆盖（缺失则用 infra.watchdog.DEFAULT_TOOL_TIMEOUT_MS = 30000）。
    """
    try:
        import json as _json
        import os as _os
        _path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "config", "hooks.json")
        if _os.path.isfile(_path):
            with open(_path, encoding="utf-8") as f:
                _cfg = _json.load(f)
            _tools_sec = _cfg.get("tools") if isinstance(_cfg, dict) else None
            if isinstance(_tools_sec, dict):
                _v = _tools_sec.get("default_timeout_ms")
                if isinstance(_v, (int, float)) and _v > 0:
                    return int(_v)
    except Exception:
        pass
    try:
        from infra.watchdog import DEFAULT_TOOL_TIMEOUT_MS
        return DEFAULT_TOOL_TIMEOUT_MS
    except Exception:
        return 30_000


def _get_timeout_for_tool(name: str) -> int:
    """返回工具生效的 timeoutMs。优先级：_HANDLERS_TIMEOUT_MS > 默认 30s。
    返回 <= 0 表示不设超时（ratchet：旧行为完全保留）。
    """
    ms = _HANDLERS_TIMEOUT_MS.get(name)
    if ms is None:
        return _get_default_timeout_ms()
    return int(ms)


def set_tool_timeout(name: str, timeout_ms: int) -> None:
    """为工具设置 timeoutMs（毫秒）。<= 0 表示取消超时（走直跑，ratchet 兼容）。"""
    if timeout_ms is None or int(timeout_ms) <= 0:
        _HANDLERS_TIMEOUT_MS.pop(name, None)
    else:
        _HANDLERS_TIMEOUT_MS[name] = int(timeout_ms)


def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    """执行工具（v0.19.3 改进：缓存 + 重试 + 明确错误建议）。

    v0.19.3：确定性工具（daily_quote/get_time/verify_math）走结果缓存，
    命中直接返回（0 延迟 + 省 token）。失败时返回含"修复建议"的错误信息。

    §3.42 W5 ⭐ 新增：工具声明的 timeoutMs 通过 watchdog 强制（不杀进程）。
    超时 → 返回 TOOL_TIMEOUT 错误（含 trace_id），工具表不变，其他工具可继续执行。
    """
    handler = _HANDLERS.get(name)
    if not handler:
        # v0.19.25：fallback 到外部 MCP 工具（mcp__server__tool 形式）
        # v0.69+ P2-2 统一：优先走 config_hub（触发 hooks/repeat_guard），回退直连
        if name.startswith("mcp__"):
            try:
                from config_hub import get_hub
                _h = get_hub()
                if _h is not None and getattr(_h, "mcp", None) is not None:
                    return _h.execute_tool(name, arguments or {})
            except Exception:
                pass
            try:
                from mcp_client import get_mcp_client
                return get_mcp_client().call_tool(name, arguments or {})
            except Exception as e:
                return f"MCP 工具 {name} 调用失败: {str(e)[:120]}"
        return f"未知工具: {name}（可用工具：{', '.join(_HANDLERS.keys())}）"
    if not isinstance(arguments, dict):
        arguments = {}

    # §3.42 W5：解析生效的 timeoutMs（工具声明 > config/hooks.json > 默认 30s）
    timeout_ms = _get_timeout_for_tool(name)

    # §3.42 W5：超时执行（watchdog 包装；超时 → ToolTimeoutError）
    try:
        from infra.watchdog import run_with_timeout, ToolTimeoutError
    except Exception:
        # watchdog 不可用时退化（ratchet：不阻断旧路径）
        run_with_timeout = None
        ToolTimeoutError = None

    # §3.42 W5 核心路径：用 watchdog 包住 handler 调用。
    # 内部 _call_impl 仍含缓存 / 重试 / 错误格式化（ratchet：旧行为不变）。
    def _call_impl():
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

    # §3.42 W5：watchdog 包装（不杀进程——超时的线程被丢弃，future GC）
    # 超时 → 直接抛出 ToolTimeoutError（携带 trace_id + tool_name + timeout_ms），
    # 由调用方（run_agent_loop / config_hub.execute_tool）决定如何格式化错误。
    if run_with_timeout is not None and ToolTimeoutError is not None and timeout_ms and timeout_ms > 0:
        return run_with_timeout(
            _call_impl, args=(), kwargs={},
            timeout_ms=timeout_ms,
            tool_name=name,
        )

    # 无 watchdog / 无超时 → 走原路径（ratchet）
    return _call_impl()


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

    v0.68+ ⭐ 统一配置中心：优先走 config_hub.get_all_tool_defs()
    （独立成套配置接口：MCP/skills/workflows 统一合并），
    config_hub 不可用时回退原逻辑（ratchet 铁律：行为不变）。
    """
    try:
        from config_hub import get_hub
        return get_hub().get_all_tool_defs()
    except Exception:
        pass
    # ─── 原逻辑（fallback） ───
    defs = get_tool_defs()
    try:
        from skill_registry import SkillRegistry
        reg = SkillRegistry()
        defs += reg.tool_defs()
    except Exception:
        pass
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
                    # v0.68+ P0-1 修复（Step4）：统一走 config_hub 路由——解锁 hooks(tool.before/after)
                    # + repeat-tool-reminder Guard + run_workflow__* 路由；失败回退旧路径
                    try:
                        from config_hub import get_hub as _get_hub
                        result = _get_hub().execute_tool(name, args)
                    except Exception:
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
