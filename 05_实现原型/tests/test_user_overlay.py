# -*- coding: utf-8 -*-
"""test_user_overlay.py — #5 用户家目录 overlay 测试（Harness 30 项 P1，§3.46.2）

覆盖：~/.paeg/cordis.patch.yml YAML patch 加载（不改代码改默认模型/学科），
与 defaults/user agents.json/project agents.json 三层合并。
dsh Harness 借鉴（$DSH_HOME/cordis.patch.yml，commit 47f9438）：
用户家目录 overlay——用户级配置可 patch，无需改项目代码。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent


def test_load_yaml_overlay_defaults_to_empty():
    """无 ~/.paeg/cordis.patch.yml → overlay 为空（不抛异常）。"""
    from config_loader import load_yaml_overlay
    overlay = load_yaml_overlay("/nonexistent/path/cordis.patch.yml")
    assert overlay == {}


def test_load_yaml_overlay_parses(tmp_path):
    """YAML patch 文件可解析为 dict（含嵌套结构）。"""
    from config_loader import load_yaml_overlay
    f = tmp_path / "cordis.patch.yml"
    f.write_text(
        "global:\n  default_model: deepseek-v4-pro\n"
        "agents:\n  presenter:\n    temperature: 0.8\n",
        encoding="utf-8",
    )
    overlay = load_yaml_overlay(str(f))
    assert overlay["global"]["default_model"] == "deepseek-v4-pro"
    assert overlay["agents"]["presenter"]["temperature"] == 0.8


def test_overlay_merges_into_config(tmp_path, monkeypatch):
    """overlay 合并进三层配置（defaults → user → project → overlay 最高优先）。"""
    import config_loader as cl

    # 构造临时项目/user/overlay 配置
    proj = tmp_path / "agents.json"
    proj.write_text(json.dumps({
        "global": {"default_provider": "auto", "default_model": None},
        "agents": {"presenter": {"provider": "auto", "model": None,
                                 "temperature": 0.3, "max_tokens": 512,
                                 "thinking_level": "A", "enabled": True}},
    }), encoding="utf-8")
    overlay = tmp_path / "cordis.patch.yml"
    overlay.write_text(
        "global:\n  default_model: deepseek-v4-pro\n"
        "agents:\n  presenter:\n    temperature: 0.8\n",
        encoding="utf-8",
    )

    # 用 monkeypatch 覆盖路径
    monkeypatch.setattr(cl, "_PROJECT_CONFIG", str(proj))
    monkeypatch.setattr(cl, "_USER_CONFIG", str(tmp_path / "nonexistent.json"))

    cfg = cl.load_agents_config(overlay_path=str(overlay))
    assert cfg["global"]["default_model"] == "deepseek-v4-pro"  # overlay 覆盖
    assert cfg["agents"]["presenter"]["temperature"] == 0.8      # overlay 覆盖
    assert cfg["agents"]["presenter"]["max_tokens"] == 512       # 未覆盖的继承 project


def test_overlay_precedence_over_project(tmp_path, monkeypatch):
    """overlay 优先级高于 project（同键 overlay 胜出）。"""
    import config_loader as cl

    proj = tmp_path / "agents.json"
    proj.write_text(json.dumps({
        "global": {"default_provider": "auto", "default_model": "deepseek-chat"},
        "agents": {"diagnostor": {"provider": "auto", "model": None,
                                  "temperature": 0.3, "max_tokens": 200,
                                  "thinking_level": "B", "enabled": True}},
    }), encoding="utf-8")
    overlay = tmp_path / "cordis.patch.yml"
    overlay.write_text(
        "global:\n  default_model: deepseek-v4-pro\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cl, "_PROJECT_CONFIG", str(proj))
    monkeypatch.setattr(cl, "_USER_CONFIG", str(tmp_path / "nonexistent.json"))

    cfg = cl.load_agents_config(overlay_path=str(overlay))
    assert cfg["global"]["default_model"] == "deepseek-v4-pro"  # overlay > project


def test_default_overlay_path_is_home_paeg(tmp_path, monkeypatch):
    """默认 overlay 路径为 ~/.paeg/cordis.patch.yml（dsh $DSH_HOME 语义）。"""
    import config_loader as cl
    # 默认路径含 .paeg 目录且以 cordis.patch.yml 结尾
    assert ".paeg" in cl.DEFAULT_OVERLAY_PATH
    assert cl.DEFAULT_OVERLAY_PATH.endswith("cordis.patch.yml")
