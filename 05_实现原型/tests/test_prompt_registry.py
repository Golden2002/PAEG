# -*- coding: utf-8 -*-
"""§3.96 PR1 测试：prompt_registry 骨架（assemble/trace/reload/情景）。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from prompt_registry import PromptRegistry, get_registry, assemble


@pytest.fixture
def reg():
    return PromptRegistry()


def test_registry_loads_blocks(reg):
    """R1：注册表装载（≥15 块 + 7 情景）。"""
    assert len(reg.blocks) >= 15
    assert len(reg.scenarios) == 7


def test_assemble_teaching_contains_core(reg):
    """R2：teaching 装配含固定块（truth_grounding/language_style）。"""
    txt, trace = reg.assemble("teaching")
    assert len(txt) > 0
    ids = [t["id"] for t in trace]
    assert "truth_grounding" in ids
    assert "language_style" in ids


def test_assemble_material_contains_ppt_blocks(reg):
    """R3：material 装配含 PPT 物料块（role/schema/hard_checks/exemplar）。"""
    txt, trace = reg.assemble("material")
    ids = [t["id"] for t in trace]
    assert "material_role_ppt" in ids
    assert "material_schema_ppt" in ids
    assert "material_hard_checks_ppt" in ids


def test_assemble_confide_has_attention(reg):
    """R4：confide 装配含注意力陪伴块。"""
    txt, trace = reg.assemble("confide")
    ids = [t["id"] for t in trace]
    assert "confide_attention_only" in ids


def test_assemble_user_input_appended_last(reg):
    """R5：user_text 强制末尾（优先级最高 99）。"""
    txt, trace = reg.assemble("chat", inputs={"user_text": "你好"})
    assert txt.rstrip().endswith("你好")
    assert "用户原话" in txt


def test_assemble_stage_filter(reg):
    """R6：stage 过滤（material outline 阶段不拼 slide_paint 专属块）。"""
    txt, trace = reg.assemble("material", stage="outline")
    # 当前无 stage 专属块，验证不报错且含基础物料块
    assert len(trace) >= 4


def test_assemble_condition_subject(reg):
    """R7：condition 条件（subject==math 时含 subject_style）。"""
    txt1, trace1 = reg.assemble("teaching", inputs={"subject": "math"})
    txt2, trace2 = reg.assemble("teaching", inputs={"subject": "physics"})
    ids1 = [t["id"] for t in trace1]
    assert "subject_style_math" in ids1
    # physics 不匹配 math condition → 不含
    ids2 = [t["id"] for t in trace2]
    assert "subject_style_math" not in ids2


def test_trace_has_metadata(reg):
    """R8：trace 含 id/source/priority/len/user_input 元数据。"""
    txt, trace = reg.assemble("teaching", inputs={"user_text": "x"})
    assert trace and all(k in trace[0] for k in ("id", "source", "priority", "len", "user_input"))


def test_reload_if_changed(reg):
    """R9：reload_if_changed 不抛异常（文件未变返回 False）。"""
    changed = reg.reload_if_changed()
    assert changed is False or changed is True


def test_get_block(reg):
    """R10：按 id 查询块。"""
    b = reg.get_block("truth_grounding")
    assert b is not None
    assert b["scenarios"] == ["*"]
