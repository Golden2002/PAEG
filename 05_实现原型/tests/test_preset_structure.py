# -*- coding: utf-8 -*-
"""test_preset_structure.py — #10 Preset 文件结构标准化测试（Harness 30 项 P1）

覆盖：preset 目录结构规范（agent.patch.yml + preset.yml + prompts/ + assets/），
与 #7 教学预设/#8 PresetService 衔接——preset 可持久化为标准文件结构。
dsh Harness 借鉴（preset 目录规范，commit 47f9438）：
preset = agent.patch.yml + preset.yml + prompts/ + assets/ 标准结构。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent


def test_default_preset_dir_exists():
    """默认 preset 目录（paeg/presets 或 config/presets）存在或可创建。"""
    from services.preset_structure import DEFAULT_PRESET_DIR, ensure_preset_dirs
    # ensure 幂等可调用
    d = ensure_preset_dirs()
    assert isinstance(d, Path)
    assert DEFAULT_PRESET_DIR is not None


def test_save_preset_to_dir(tmp_path):
    """保存 preset 为标准结构（preset.yml + agent.patch.yml）。"""
    from services.preset_structure import save_preset_to_dir, load_preset_from_dir
    preset = {
        "id": "weil-classical",
        "desc": "薇依经典",
        "teaching_mode": "normal",
        "permission_preset": "standard",
        "persona": "weil",
    }
    pdir = tmp_path / "weil-classical"
    save_preset_to_dir(preset, pdir)
    # 标准文件生成
    assert (pdir / "preset.yml").is_file()
    loaded = load_preset_from_dir(pdir)
    assert loaded["id"] == "weil-classical"
    assert loaded["teaching_mode"] == "normal"


def test_preset_dir_structure_has_expected_files(tmp_path):
    """preset 目录含标准文件（preset.yml/agent.patch.yml，可选 prompts/ assets/）。"""
    from services.preset_structure import save_preset_to_dir
    preset = {"id": "test", "desc": "测试", "teaching_mode": "easy",
              "permission_preset": "read_only", "persona": "weil"}
    pdir = tmp_path / "test"
    save_preset_to_dir(preset, pdir)
    names = {f.name for f in pdir.iterdir() if f.is_file()}
    assert "preset.yml" in names
    assert "agent.patch.yml" in names


def test_list_presets_in_dir(tmp_path):
    """list_presets_in_dir 列出目录下所有 preset。"""
    from services.preset_structure import save_preset_to_dir, list_presets_in_dir
    for pid in ("p1", "p2"):
        save_preset_to_dir({"id": pid, "desc": pid, "teaching_mode": "normal",
                            "permission_preset": "standard", "persona": "weil"},
                           tmp_path / pid)
    presets = list_presets_in_dir(tmp_path)
    assert "p1" in presets
    assert "p2" in presets


def test_load_missing_preset_returns_none(tmp_path):
    """缺失 preset 目录返回 None（容错）。"""
    from services.preset_structure import load_preset_from_dir
    assert load_preset_from_dir(tmp_path / "no_such") is None
