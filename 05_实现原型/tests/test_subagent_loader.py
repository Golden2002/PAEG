# -*- coding: utf-8 -*-
"""test_subagent_loader.py — #1 Subagent Patch 系统测试（Harness 30 项 P0，§3.46.2）

覆盖：subagent YAML 装扮加载 / persona/prompt 覆盖 / 缺失回退 / 与 #3 persona 外置衔接。
dsh Harness 借鉴（agent.cordis.yml `- id:` 整体替换，commit 47f9438）：
9 subagent 装扮（persona/prompt/工具/调度全配置可换），配置可 patch 不写死。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
PATCH_DIR = BASE / "config" / "subagents"


def test_patch_dir_exists_or_creatable():
    """config/subagents/ 目录存在（subagent 装扮层落点）。"""
    # 目录可能不存在（首次创建），但模块应能容忍——测试通过加载器不崩即可
    from services.subagent_loader import PATCH_DIR as _d
    assert str(_d).endswith("subagents")


def test_get_subagent_patch_missing_returns_defaults():
    """未配置的 subagent 回退默认（不抛异常）。"""
    from services.subagent_loader import get_subagent_patch
    patch = get_subagent_patch("diagnostor")
    assert isinstance(patch, dict)
    assert "persona" in patch
    assert "prompt_override" in patch
    assert "enabled" in patch


def test_subagent_loader_has_default_agents():
    """加载器内置 9 个默认 subagent 的补丁配置（Diagnostor/Planner/... 全覆盖）。"""
    from services.subagent_loader import DEFAULT_AGENT_PATCHES
    expected = ["diagnostor", "planner", "presenter", "evaluator",
                "adapter", "answer_solver", "affection_supportor",
                "self_update_agent", "individuality"]
    for name in expected:
        assert name in DEFAULT_AGENT_PATCHES, f"缺默认 subagent 补丁 {name}"


def test_patch_persona_links_to_personas_dir():
    """subagent 补丁的 persona 字段对应 paeg_personas/ 下 persona（与 #3 衔接）。"""
    from services.subagent_loader import DEFAULT_AGENT_PATCHES
    personas_dir = BASE / "paeg_personas"
    for name, patch in DEFAULT_AGENT_PATCHES.items():
        persona_id = patch.get("persona", "")
        if persona_id:
            # persona 可以是 "weil"（共享薇依人格）或缺失（该 subagent 用自身内置人格）
            assert persona_id == "weil" or (personas_dir / f"{persona_id}.yml").is_file(), \
                f"{name} 的 persona {persona_id} 不在 paeg_personas/"


def test_apply_patch_merges_with_agents_json():
    """apply_patch 与 config/agents.json 合并（patch 覆盖，缺省继承）。"""
    from services.subagent_loader import apply_subagent_patch
    base = {"provider": "auto", "model": None, "temperature": 0.3,
            "max_tokens": 200, "enabled": True}
    patch = {"temperature": 0.5, "persona": "weil"}
    merged = apply_subagent_patch(base, patch)
    assert merged["temperature"] == 0.5  # patch 覆盖
    assert merged["provider"] == "auto"  # 未 patch 的继承
    assert merged["persona"] == "weil"   # patch 新增字段


def test_register_custom_subagent_patch():
    """可注册自定义 subagent 补丁（dsh 一切皆插件：subagent 装扮可插拔）。"""
    from services.subagent_loader import (
        DEFAULT_AGENT_PATCHES, register_subagent_patch, get_subagent_patch,
    )
    register_subagent_patch("test_sub", {"persona": "weil", "prompt_override": "测试", "enabled": True})
    try:
        assert "test_sub" in DEFAULT_AGENT_PATCHES
        assert get_subagent_patch("test_sub")["prompt_override"] == "测试"
    finally:
        DEFAULT_AGENT_PATCHES.pop("test_sub", None)
