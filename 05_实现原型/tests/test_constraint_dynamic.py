# -*- coding: utf-8 -*-
"""§3.92 动态约束架构测试：config 模式骨架注入 + default_layer + 告知块。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from constraint_engine import (constraint_layer_set, constraint_layer_scope,
                               _get_config_from_file)


def test_config_default_layer_is_7():
    """C1：default_layer=7（默认全放开，增强输出——§3.92 用户要求）。"""
    cfg = _get_config_from_file()
    assert cfg is not None
    assert cfg.get("default_layer") == 7


def test_config_has_layer_meta():
    """C2：layer_meta 8 层元数据（告知块素材）。"""
    cfg = _get_config_from_file()
    meta = cfg.get("layer_meta", {})
    assert len(meta) == 8
    assert meta["7"]["name"] == "完全放开层"
    assert "教授级" in meta["7"]["desc"]


def test_layer_set_l7_injects_full_skeleton():
    """C3：L7 全放开 → 注入 D.skeleton_full 完整教学法骨架。"""
    txt = constraint_layer_set(layer=7, reason="用户要详细讲")
    assert "核心前提" in txt
    assert "误区纠正" in txt
    assert "边界条件" in txt
    assert "延伸引导" in txt


def test_layer_set_l1_injects_brief_skeleton():
    """C4：L1 极简 → 注入 D.skeleton_brief（收紧版）。"""
    txt = constraint_layer_set(layer=1, reason="用户要简单讲")
    assert "简要版" in txt or "核心机制" in txt


def test_layer_set_contains_group_rules():
    """C5：放开组规则可见（unlocked_rules）。"""
    txt = constraint_layer_set(layer=7)
    assert "组[M]" in txt  # M 节奏
    assert "组[D]" in txt  # D 教学法深度
    assert "已放开" in txt


def test_layer_set_l0_keeps_reserved():
    """C6：L0 保底永不放开声明。"""
    txt = constraint_layer_set(layer=7)
    assert "L0 保底" in txt
    assert "永不放开" in txt


def test_layer_scope_available():
    """C7：layer_scope 提供清单（告知块）。"""
    scope = constraint_layer_scope()
    assert isinstance(scope, str) and len(scope) > 100
    assert "L" in scope


def test_group_rules_dict_structure():
    """C8：group_rules 结构化（default/unlocked 双态 + D 骨架）。"""
    cfg = _get_config_from_file()
    rules = cfg.get("group_rules", {})
    assert isinstance(rules["M"], dict)
    assert "default_rules" in rules["M"]
    assert "unlocked_rules" in rules["M"]
    assert "skeleton_full" in rules["D"]
    assert "skeleton_brief" in rules["D"]
