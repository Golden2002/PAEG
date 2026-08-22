# -*- coding: utf-8 -*-
"""services/sandbox.py —— §3.85 ⭐ Sandbox 治理层（Codex Harness 借鉴 A9）

背景（需求文档 §4 A9）：Codex Harness sandbox（rwx 分域 + approval）——agent 工具
执行前过 sandbox 判定，越权操作拒绝或走审批。PAEG：教学 Agent 默认只读用户资料库
+ 白名单工具；敏感工具（写文件/改配置）需权限 preset。

设计（对齐 C1 Permission Preset 思路 + 轻量实现）：
- PRESET 定义：teaching（默认）/ lesson_prep（备课，放行物料写）/ admin（运维）
- 工具分域：read（安全）/ write（需 preset 放行）/ exec（受控子进程，已过 AST 校验）
- check(name, args, preset) -> (allowed, reason)：判定工具是否可在该 preset 下执行
- 白名单表：内置工具按域分类；MCP 工具默认 read 放行（外部工具谨慎）
- 越权 → 返回拒绝原因（调用方转成友好错误，不静默执行）
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# 工具分域：read=安全只读 / write=写操作 / exec=子进程执行（已过 AST 校验）
_READ_TOOLS = {
    "get_time", "daily_quote", "web_search", "fetch_page", "search_facts",
    "knowledge_map", "search_subjects", "get_weather", "calc", "verify_math",
    "normalize_text", "language_policy_check", "forbidden_words",
    "constraint_layer_get", "skill_activate", "skill_catalog",
}
_WRITE_TOOLS = {
    "generate_handout", "generate_script", "generate_ppt", "generate_mindmap",
    "generate_video_script", "generate_manim", "save_note", "save_insight",
    "create_mindmap", "render_manim",
}
_EXEC_TOOLS = {
    "execute_python", "execute_shell", "run_manim",
}

# 角色 preset → 允许的写/执行工具（读工具全放行）
_PRESET_WRITE: Dict[str, set] = {
    "teaching": set(),          # 教学默认：只读（不落盘、不执行）
    "lesson_prep": _WRITE_TOOLS,  # 备课：放行物料产出
    "admin": _WRITE_TOOLS | _EXEC_TOOLS,  # 运维：全量
}
_PRESET_EXEC: Dict[str, set] = {
    "teaching": set(),
    "lesson_prep": set(),
    "admin": _EXEC_TOOLS,
}

_DEFAULT_PRESET = "teaching"


def check(name: str, preset: str = "") -> Tuple[bool, str]:
    """sandbox 判定：工具是否可在 preset 下执行。

    Returns: (allowed, reason)。拒绝时 reason 说明原因与可行 preset。
    """
    _p = preset or _DEFAULT_PRESET
    if name in _READ_TOOLS or name.startswith("mcp__"):
        return True, ""  # 只读/外部工具默认放行（外部 MCP 谨慎但教学场景无害）
    if name in _WRITE_TOOLS:
        if name in _PRESET_WRITE.get(_p, set()):
            return True, ""
        return False, f"工具 {name} 是写操作，当前 preset={_p} 不允许（需 lesson_prep/admin）"
    if name in _EXEC_TOOLS:
        if name in _PRESET_EXEC.get(_p, set()):
            return True, ""
        return False, f"工具 {name} 是执行操作，当前 preset={_p} 不允许（需 admin）"
    # 未知工具：默认放行（registry 有 handler 即合法；未知会由 registry 返回错误）
    return True, ""


def preset_for_mode(mode: str) -> str:
    """教学模式 → sandbox preset。"""
    if mode == "lesson_prep" or mode == "lesson_prep_modify":
        return "lesson_prep"
    if mode in ("teach", "chat", "answer", "method", "knowledge", "affection"):
        return "teaching"
    return _DEFAULT_PRESET


__all__ = ["check", "preset_for_mode", "_READ_TOOLS", "_WRITE_TOOLS"]
