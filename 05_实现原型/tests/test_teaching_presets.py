# -*- coding: utf-8 -*-
"""test_teaching_presets.py — #7 教学预设测试（Harness 30 项 P0，§3.46.2）

覆盖：4 内置预设（standard/minimal/code-mode/weil-classical）/ 注册自定义 /
获取/列表 / 预设与权限档位、教学模式、persona 的联动解析。
dsh Harness 借鉴（apps/cli/config/agent-presets，commit 47f9438）：
preset = 教学模式 + 权限档位 + persona 的命名组合，可 mount/list/resolve。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_four_builtin_presets_exist():
    """4 内置教学预设齐全：standard/minimal/code-mode/weil-classical。"""
    from services.teaching_presets import TEACHING_PRESETS
    for name in ("standard", "minimal", "code-mode", "weil-classical"):
        assert name in TEACHING_PRESETS, f"缺内置预设 {name}"


def test_preset_has_required_fields():
    """每个预设含 desc/teaching_mode/permission_preset/persona 四字段。"""
    from services.teaching_presets import TEACHING_PRESETS
    for name, cfg in TEACHING_PRESETS.items():
        for field in ("desc", "teaching_mode", "permission_preset", "persona"):
            assert field in cfg, f"{name} 缺 {field}"


def test_get_preset_returns_config():
    """get_teaching_preset 返回预设配置。"""
    from services.teaching_presets import get_teaching_preset
    cfg = get_teaching_preset("minimal")
    assert cfg["teaching_mode"] == "easy"  # 极简教学
    assert cfg["permission_preset"] == "read_only"  # 只读权限


def test_get_preset_missing_returns_default():
    """未知预设回退 standard（不抛异常）。"""
    from services.teaching_presets import get_teaching_preset
    cfg = get_teaching_preset("nonexistent_preset")
    assert cfg["teaching_mode"] == "normal"


def test_register_custom_preset():
    """可注册自定义教学预设（dsh 一切皆插件：preset 可插拔）。"""
    from services.teaching_presets import (
        register_teaching_preset, get_teaching_preset, TEACHING_PRESETS,
    )
    register_teaching_preset("test_preset", {
        "desc": "测试预设",
        "teaching_mode": "deep",
        "permission_preset": "full",
        "persona": "weil",
    })
    try:
        assert "test_preset" in TEACHING_PRESETS
        assert get_teaching_preset("test_preset")["teaching_mode"] == "deep"
    finally:
        TEACHING_PRESETS.pop("test_preset", None)


def test_list_presets_returns_names():
    """list_teaching_presets 返回预设名列表（含 standard 默认）。"""
    from services.teaching_presets import list_teaching_presets
    names = list_teaching_presets()
    assert "standard" in names
    assert len(names) >= 4


def test_preset_permission_links_to_tool_registry():
    """预设的 permission_preset 是 tool_registry.PERMISSION_PRESETS 的合法键（联动有效）。"""
    from services.teaching_presets import TEACHING_PRESETS
    from tool_registry import PERMISSION_PRESETS
    for name, cfg in TEACHING_PRESETS.items():
        assert cfg["permission_preset"] in PERMISSION_PRESETS, \
            f"{name} 的权限档 {cfg['permission_preset']} 不在 tool_registry"


def test_standard_is_default():
    """standard 是默认教学预设（兼容现状）。"""
    from services.teaching_presets import DEFAULT_PRESET
    assert DEFAULT_PRESET == "standard"
