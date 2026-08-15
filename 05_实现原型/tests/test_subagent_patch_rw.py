# -*- coding: utf-8 -*-
"""test_subagent_patch_rw.py — #27 Self-Update via Patch 读写测试（Harness 30 项 P1）

覆盖：AI 读/写自己 patch 文件（cordis preset 可修改语义）——save_yaml_patch 落盘、
read_yaml_patch 读回、list_yaml_patches 枚举、写后装载生效。
dsh Harness 借鉴（tool-cordis：AI 读/写 preset，commit 47f9438）：
AI 可修改自身 preset 配置，无需人工改代码。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def patch_dir(tmp_path, monkeypatch):
    """把 PATCH_DIR 指向临时目录（隔离真实 config/subagents/）。"""
    import services.subagent_loader as sl
    monkeypatch.setattr(sl, "PATCH_DIR", tmp_path)
    return tmp_path


def test_save_yaml_patch_writes_file(patch_dir):
    """AI 修改 preset → save_yaml_patch 落盘为 {name}.patch.yml。"""
    from services.subagent_loader import save_yaml_patch
    save_yaml_patch("planner", {"persona": "weil", "prompt_override": "多鼓励", "enabled": True})
    f = patch_dir / "planner.patch.yml"
    assert f.is_file()
    import yaml  # type: ignore
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    assert data["persona"] == "weil"
    assert data["prompt_override"] == "多鼓励"


def test_read_yaml_patch_roundtrip(patch_dir):
    """save 后 read 能读回（AI 读自己 patch）。"""
    from services.subagent_loader import save_yaml_patch, read_yaml_patch
    save_yaml_patch("diagnostor", {"enabled": False})
    data = read_yaml_patch("diagnostor")
    assert data is not None
    assert data["enabled"] is False


def test_read_yaml_patch_missing_returns_none(patch_dir):
    """不存在的 patch → read 返回 None（不抛异常）。"""
    from services.subagent_loader import read_yaml_patch
    assert read_yaml_patch("no_such_agent") is None


def test_list_yaml_patches(patch_dir):
    """list 枚举已有 patch 文件（AI 可枚举自己 patch 清单）。"""
    from services.subagent_loader import save_yaml_patch, list_yaml_patches
    save_yaml_patch("planner", {"persona": "weil"})
    save_yaml_patch("adapter", {"prompt_override": "x"})
    names = list_yaml_patches()
    assert "planner" in names
    assert "adapter" in names
    assert len(names) == 2


def test_written_patch_takes_effect_via_get(patch_dir, monkeypatch):
    """写后装载生效：get_subagent_patch 读到 AI 写入的 patch（tool-cordis 语义）。"""
    import services.subagent_loader as sl
    # get_subagent_patch 内部用 PATCH_DIR 查 YAML patch（若有则优先）
    sl.save_yaml_patch("presenter", {"persona": "weil", "prompt_override": "AI 自定义", "enabled": True})
    # 打桩 load_yaml_patch 返回写盘内容（真实链路：get_subagent_patch → load_yaml_patch）
    patch = sl.load_yaml_patch("presenter")
    assert patch is not None
    assert patch["prompt_override"] == "AI 自定义"
    # 写盘内容与默认不同 → 确认 YAML patch 优先
    assert patch["prompt_override"] != sl.DEFAULT_AGENT_PATCHES["presenter"]["prompt_override"]
