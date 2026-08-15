# -*- coding: utf-8 -*-
"""services/subagent_loader.py —— #1 Subagent Patch 系统（Harness 30 项 P0，§3.46.2，2026-08-16）

dsh Harness 借鉴（agent.cordis.yml `- id:` 整体替换，commit 47f9438）：
9 subagent 装扮（persona/prompt/工具/调度全配置可换），配置可 patch 不写死。

设计：
- DEFAULT_AGENT_PATCHES：9 个默认 subagent 的补丁配置（persona/prompt_override/enabled）
- get_subagent_patch(name)：获取补丁（缺失回退默认，不抛异常）
- apply_subagent_patch(base, patch)：与 config/agents.json 合并（patch 覆盖，缺省继承）
- register_subagent_patch(name, config)：自定义 subagent 装扮可插拔
- persona 字段对应 paeg_personas/（#3 Persona 外置衔接）

与既有机制关系：
- config/agents.json（§3.32）：per-subagent 模型/温度/思考级配置（Provider 层）
- 本模块：per-subagent persona/prompt 装扮（语义层）——两层互补
- 运行时 subagents.py 构造时调 get_subagent_patch() 注入 persona 覆盖
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

# config/subagents/ 目录（subagent YAML 装扮层落点，可放 {name}.patch.yml）
PATCH_DIR = Path(__file__).resolve().parent.parent / "config" / "subagents"

# ─────────────────────────────────────
# 9 个默认 subagent 补丁配置
# persona：对应 paeg_personas/（#3 外置）；空串 = 用 subagent 自身内置人格
# prompt_override：覆盖系统提示词（空 = 用现有 build_* 系统）
# ─────────────────────────────────────
DEFAULT_AGENT_PATCHES: Dict[str, Dict[str, Any]] = {
    "diagnostor": {
        "desc": "诊断器：学情诊断（知识缺口/认知风格）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "planner": {
        "desc": "规划器：学习计划（目标→步骤→资源）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "presenter": {
        "desc": "呈现器：核心讲解（因材施教注入）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "evaluator": {
        "desc": "评估器：掌握度评估（确定性启发式）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "adapter": {
        "desc": "调整器：教学策略调整（画像驱动）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "answer_solver": {
        "desc": "答题器：找答案/解题",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "affection_supportor": {
        "desc": "情绪陪伴：不教不答不解决（薇依注意力）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "self_update_agent": {
        "desc": "自我更新：反思→建议（质量门禁）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
    "individuality": {
        "desc": "个体化：17 维画像建模（因材施教）",
        "persona": "weil",
        "prompt_override": "",
        "enabled": True,
    },
}


# ─────────────────────────────────────
# API
# ─────────────────────────────────────
def get_subagent_patch(name: Optional[str] = None) -> Dict[str, Any]:
    """获取 subagent 补丁配置；未知/为空 → 回退默认（不抛异常）。

    Args:
        name: subagent 名（diagnostor/planner/.../自定义注册名）

    返回：{persona, prompt_override, enabled}（缺失字段填默认）
    """
    if not name:
        return {
            "persona": "weil",
            "prompt_override": "",
            "enabled": True,
        }
    patch = DEFAULT_AGENT_PATCHES.get(name)
    if patch is None:
        return {
            "persona": "weil",
            "prompt_override": "",
            "enabled": True,
        }
    return {
        "persona": patch.get("persona", "weil"),
        "prompt_override": patch.get("prompt_override", ""),
        "enabled": bool(patch.get("enabled", True)),
    }


def register_subagent_patch(name: str, config: Dict[str, Any]) -> None:
    """注册自定义 subagent 补丁（dsh 一切皆插件：装扮可插拔）。

    Args:
        name: subagent 名
        config: {desc?, persona?, prompt_override?, enabled?}
    """
    DEFAULT_AGENT_PATCHES[name] = config


def apply_subagent_patch(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """把 subagent 补丁合并到 config/agents.json 配置（patch 覆盖，缺省继承）。

    Args:
        base: agents.json 中该 subagent 的配置（provider/model/temperature/...）
        patch: subagent 补丁（persona/prompt_override/enabled）

    返回：合并后的 dict（新增 persona/prompt_override 字段）
    """
    merged = dict(base or {})
    if patch:
        merged.update({k: v for k, v in patch.items() if v is not None})
    # 保证字段存在
    merged.setdefault("persona", "weil")
    merged.setdefault("prompt_override", "")
    merged.setdefault("enabled", True)
    return merged


def load_yaml_patch(name: str) -> Optional[Dict[str, Any]]:
    """从 config/subagents/{name}.patch.yml 加载自定义补丁（可选扩展）。

    无 yaml 依赖时跳过（.patch.yml 是可选增强；内置 DEFAULT_AGENT_PATCHES 已够用）。
    """
    _f = PATCH_DIR / f"{name}.patch.yml"
    if not _f.is_file():
        return None
    try:
        import yaml  # type: ignore
        with open(_f, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or None
    except Exception:
        return None


def save_yaml_patch(name: str, config: Dict[str, Any]) -> bool:
    """AI 修改 preset → 写入 config/subagents/{name}.patch.yml（#27 Self-Update via Patch）。

    dsh tool-cordis 语义（cordis preset 可修改，commit 47f9438）：
    AI 可读写自身 preset 配置，无需人工改代码。

    Args:
        name: subagent 名
        config: {desc?, persona?, prompt_override?, enabled?}

    返回：是否写入成功（yaml 依赖缺失/写入异常 → False）
    """
    _f = PATCH_DIR / f"{name}.patch.yml"
    try:
        import yaml  # type: ignore
        PATCH_DIR.mkdir(parents=True, exist_ok=True)
        with open(_f, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, allow_unicode=True, sort_keys=False)
        return True
    except Exception:
        return False


def read_yaml_patch(name: str) -> Optional[Dict[str, Any]]:
    """AI 读回自己写入的 patch 文件（无 → None，不抛异常）。"""
    return load_yaml_patch(name)


def list_yaml_patches() -> List[str]:
    """枚举已有 YAML patch 清单（AI 可列出自己可修改的 preset）。

    返回：patch 文件名列表（不含 .patch.yml 后缀，按名称排序）
    """
    if not PATCH_DIR.is_dir():
        return []
    try:
        return sorted(
            p.name[:-len(".patch.yml")]
            for p in PATCH_DIR.glob("*.patch.yml")
        )
    except Exception:
        return []


__all__ = [
    "PATCH_DIR", "DEFAULT_AGENT_PATCHES",
    "get_subagent_patch", "register_subagent_patch",
    "apply_subagent_patch", "load_yaml_patch",
    "save_yaml_patch", "read_yaml_patch", "list_yaml_patches",
]
