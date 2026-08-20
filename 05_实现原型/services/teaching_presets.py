# -*- coding: utf-8 -*-
"""services/teaching_presets.py —— #7 教学预设（Harness 30 项 P0，§3.46.2，2026-08-16）

dsh Harness 借鉴（apps/cli/config/agent-presets 4 预设目录，commit 47f9438）：
preset = 教学模式 + 权限档位 + persona 的命名组合，可 mount/list/resolve/recompose。

4 内置预设（对齐 dsh standard/code/minimal/cordis 语义）：
- standard（默认）：正常教学模式 + 标准权限（读+写+联网）+ 薇依人格
- minimal（极简）：简单教学模式 + 只读权限（防干扰，专注讲解）
- code-mode（编程）：深度教学模式 + 全量权限（代码工具全开）
- weil-classical（薇依经典）：正常教学模式 + 标准权限 + 薇依人格（原汁原味）

联动：permission_preset 是 tool_registry.PERMISSION_PRESETS 合法键（exam 锁写）；
teaching_mode 是 subagents._detect_teaching_mode 的 easy/normal/deep 值；
persona 是 paeg_personas/ 下的 persona id（#3 外置）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# ─────────────────────────────────────
# 4 内置教学预设
# ─────────────────────────────────────
TEACHING_PRESETS: Dict[str, Dict[str, Any]] = {
    "standard": {
        "desc": "标准教学（默认）：正常模式 + 全工具（读+写+联网）",
        "teaching_mode": "normal",
        "permission_preset": "standard",
        "persona": "weil",
    },
    "minimal": {
        "desc": "极简教学：简单模式 + 只读权限（专注讲解防干扰）",
        "teaching_mode": "easy",
        "permission_preset": "read_only",
        "persona": "weil",
    },
    "code-mode": {
        "desc": "编程教学：深度模式 + 全量权限（代码/动画工具全开）",
        "teaching_mode": "deep",
        "permission_preset": "full",
        "persona": "weil",
    },
    "weil-classical": {
        "desc": "薇依经典：正常模式 + 标准权限（原汁原味薇依教学风格）",
        "teaching_mode": "normal",
        "permission_preset": "standard",
        "persona": "weil",
    },
    # v1.2.1 ⭐ §3.79 C1 补缺口：考试模式教学预设（对应总需求 TOP-2）
    # permission_preset="exam" 联动 tool_registry.PERMISSION_PRESETS["exam"]
    # （sandbox=read-only + approval=never + allow_write=False → 禁讲义/PPT/视频/动画/save_document）
    "exam": {
        "desc": "考试模式：锁定写工具（禁讲义/PPT/视频/动画/文档生成，专注解题评估；对学校/家长最硬卖点）",
        "teaching_mode": "normal",
        "permission_preset": "exam",
        "persona": "weil",
    },
}

# 默认教学预设（兼容现状——不改默认行为，ratchet 铁律）
DEFAULT_PRESET = "standard"


# ─────────────────────────────────────
# API
# ─────────────────────────────────────
def get_teaching_preset(name: Optional[str] = None) -> Dict[str, Any]:
    """获取教学预设配置；未知/为空 → 回退 standard（不抛异常）。

    Args:
        name: 预设名（standard/minimal/code-mode/weil-classical/自定义注册名）
    """
    if not name:
        return TEACHING_PRESETS[DEFAULT_PRESET]
    return TEACHING_PRESETS.get(name, TEACHING_PRESETS[DEFAULT_PRESET])


def register_teaching_preset(name: str, config: Dict[str, Any]) -> None:
    """注册自定义教学预设（dsh 一切皆插件：preset 可插拔）。

    Args:
        name: 预设名
        config: {desc, teaching_mode, permission_preset, persona}
    """
    TEACHING_PRESETS[name] = config


def list_teaching_presets() -> list:
    """列出全部教学预设名（含内置 + 自定义）。"""
    return list(TEACHING_PRESETS.keys())


def resolve_preset(name: Optional[str] = None) -> Dict[str, Any]:
    """解析预设为可执行配置（联动 tool_registry 权限档 + persona 正文）。

    返回：{preset, teaching_mode, permission_preset, persona, persona_body, allow_write, allow_web}
    """
    cfg = get_teaching_preset(name)
    result = {
        "preset": name or DEFAULT_PRESET,
        "teaching_mode": cfg.get("teaching_mode", "normal"),
        "permission_preset": cfg.get("permission_preset", "standard"),
        "persona": cfg.get("persona", "weil"),
        "persona_body": "",
        "allow_write": True,
        "allow_web": True,
    }
    # 联动 tool_registry 权限档（读档位元数据）
    try:
        from tool_registry import PERMISSION_PRESETS
        _perm = PERMISSION_PRESETS.get(result["permission_preset"], {})
        result["allow_write"] = bool(_perm.get("allow_write", True))
        result["allow_web"] = bool(_perm.get("allow_web", True))
    except Exception:
        pass
    # 联动 persona 正文（#3 外置）
    try:
        from prompts import _load_persona
        result["persona_body"] = _load_persona(result["persona"])
    except Exception:
        result["persona_body"] = ""
    return result


__all__ = [
    "TEACHING_PRESETS", "DEFAULT_PRESET",
    "get_teaching_preset", "register_teaching_preset",
    "list_teaching_presets", "resolve_preset",
]
