# -*- coding: utf-8 -*-
"""test_quality_gate_config.py — #28 Constitutional AI 补丁化测试（Harness 30 项 P2）

覆盖：质量门禁配置化（阈值/最小长度/宪法条款走 patch 配置，缺省回退内置）。
dsh Harness 借鉴（plan-mode + repeat-tool-reminder 走 patch 配置，commit 47f9438）：
反思/门禁/重复检测配置可 patch，不改代码调门禁。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_default_gate_config():
    """默认质量门禁配置（阈值/最小长度齐全）。"""
    from services.quality_gate_config import get_gate_config
    cfg = get_gate_config()
    assert "thresholds" in cfg
    assert "factuality" in cfg["thresholds"]
    assert "min_content_len" in cfg
    assert "min_words" in cfg


def test_config_loads_from_file(tmp_path, monkeypatch):
    """从配置文件加载门禁参数（patch 配置语义）。"""
    import services.quality_gate_config as qgc
    f = tmp_path / "quality_gate.json"
    f.write_text(json.dumps({
        "thresholds": {"factuality": 5, "safety": 5, "novelty": 3, "pedagogy": 3},
        "min_content_len": 20,
        "min_words": 6,
    }), encoding="utf-8")
    monkeypatch.setattr(qgc, "DEFAULT_CONFIG_PATH", str(f))
    qgc.reset_cache()
    cfg = qgc.get_gate_config()
    assert cfg["thresholds"]["factuality"] == 5
    assert cfg["min_content_len"] == 20
    assert cfg["min_words"] == 6


def test_config_missing_falls_back_defaults(tmp_path, monkeypatch):
    """配置文件缺失 → 回退内置默认（不抛异常）。"""
    import services.quality_gate_config as qgc
    monkeypatch.setattr(qgc, "DEFAULT_CONFIG_PATH", str(tmp_path / "nope.json"))
    qgc.reset_cache()
    cfg = qgc.get_gate_config()
    assert cfg["thresholds"]["factuality"] == 4  # 内置默认
    assert cfg["min_content_len"] == 12


def test_apply_config_to_quality_gate(tmp_path, monkeypatch):
    """配置注入 QualityGate（阈值/最小长度生效）。"""
    import quality_gate as qg
    import services.quality_gate_config as qgc

    f = tmp_path / "quality_gate.json"
    f.write_text(json.dumps({
        "thresholds": {"factuality": 5, "safety": 5, "novelty": 3, "pedagogy": 3},
        "min_content_len": 20,
        "min_words": 6,
    }), encoding="utf-8")
    monkeypatch.setattr(qgc, "DEFAULT_CONFIG_PATH", str(f))
    qgc.reset_cache()

    gate = qg.QualityGate(llm=None)
    qgc.apply_to_gate(gate)
    assert gate.THRESHOLDS["factuality"] == 5
    assert qg.MIN_CONTENT_LEN == 20
    assert qg.MIN_WORDS == 6


def test_constitution_extra_patchable(tmp_path, monkeypatch):
    """宪法条款可 patch（constitution_extra 配置化）。"""
    import services.quality_gate_config as qgc
    f = tmp_path / "quality_gate.json"
    f.write_text(json.dumps({
        "thresholds": {"factuality": 4, "safety": 4, "novelty": 3, "pedagogy": 3},
        "min_content_len": 12,
        "min_words": 4,
        "constitution_extra": ["不得输出政治敏感内容", "不得模仿学生口吻"],
    }), encoding="utf-8")
    monkeypatch.setattr(qgc, "DEFAULT_CONFIG_PATH", str(f))
    qgc.reset_cache()
    cfg = qgc.get_gate_config()
    assert len(cfg["constitution_extra"]) == 2
    assert "不得输出政治敏感内容" in cfg["constitution_extra"]
