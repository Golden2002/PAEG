# -*- coding: utf-8 -*-
"""§3.88 物料提示词模板测试：25 用例（5 物料 × 5 简单指令）。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from material_prompts import build_material_system, upgrade_simple_intent, _MATERIAL_TEMPLATES

MATERIAL_TYPES = ["handout", "ppt", "video", "manim", "mindmap"]
SIMPLE_INTENTS = [
    ("光合作用", "biology", "middle_school"),
    ("导数", "math", "high_school"),
    ("牛顿第二定律", "physics", "high_school"),
    ("二次函数", "math", "middle_school"),
    ("文言文阅读", "chinese", "high_school"),
]


def test_templates_defined():
    """S1：5 类物料模板齐全。"""
    assert set(_MATERIAL_TEMPLATES) == set(MATERIAL_TYPES)


def test_each_template_has_three_layers():
    """S2：每类模板含 role/schema/hard_checks/exemplar。"""
    for mt in MATERIAL_TYPES:
        t = _MATERIAL_TEMPLATES[mt]
        assert "role" in t, f"{mt} 缺 role"
        assert "schema" in t, f"{mt} 缺 schema"
        assert "hard_checks" in t and len(t["hard_checks"]) >= 4, f"{mt} 硬约束不足"
        assert "exemplar" in t and len(t["exemplar"]) > 20, f"{mt} 缺范例"


@pytest.mark.parametrize("material_type", MATERIAL_TYPES)
@pytest.mark.parametrize("topic,subject,grade", SIMPLE_INTENTS)
def test_build_material_system(material_type, topic, subject, grade):
    """S3-S27：5 物料 × 5 简单指令 → 系统提示词含角色/schema/硬约束/范例。"""
    sp = build_material_system(material_type, topic, subject, grade)
    assert "物料专属角色" in sp, f"{material_type}/{topic} 缺角色段"
    assert "输出 schema" in sp, f"{material_type}/{topic} 缺 schema"
    assert "质量红线" in sp, f"{material_type}/{topic} 缺硬约束"
    assert "优秀范例" in sp, f"{material_type}/{topic} 缺范例"
    # 学科学段动态注入
    grade_cn = {"middle_school": "初中", "high_school": "高中"}[grade]
    assert grade_cn in sp, f"{material_type}/{topic} 未注入学段 {grade_cn}"


@pytest.mark.parametrize("material_type", MATERIAL_TYPES)
@pytest.mark.parametrize("topic,subject,grade", SIMPLE_INTENTS)
def test_upgrade_simple_intent(material_type, topic, subject, grade):
    """S28-S52：简单指令升级器输出含主题/学科/学段/物料要求。"""
    up = upgrade_simple_intent(topic, material_type, subject, grade)
    assert topic in up, "缺主题"
    assert "学科" in up, "缺学科"
    assert "学段" in up, "缺学段"
    assert "要求" in up, "缺物料要求"


def test_unknown_material_type():
    """S53：未知物料类型抛明确异常。"""
    with pytest.raises(ValueError):
        build_material_system("nonexistent", "topic")


def test_dynamic_constraint_by_grade():
    """S54：不同学段注入不同教学对象（动态约束）。"""
    sp_ms = build_material_system("ppt", "光合作用", "biology", "middle_school")
    sp_hs = build_material_system("ppt", "光合作用", "biology", "high_school")
    assert "初中生物" in sp_ms
    assert "高中生物" in sp_hs
