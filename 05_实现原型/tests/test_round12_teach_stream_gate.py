# -*- coding: utf-8 -*-
"""§3.79 Round 12 修复 ⭐ teach_stream 学段/深度守门接线回归测试。

Round 12 probe 验证发现：学段特征守门（grade_quality_gate）只在 paeg.teach
（sync 路径）接入；GUI 实际走的 /api/teach/stream（server.py _teach_stream_gen）
从未执行 gate → 0/4 全特征通过（初中缺感官/高中缺题型、考研缺考点等）。
本测试守卫：
  1. server.py 主循环在 presentation 生成后调用 check_grade_features/refine_for_grade
  2. 内容深度守门（高中/大学/考研）同样接入
  3. on_session_end 的 dialogue_summary 不再对 str 调 .get（修复 'str' has no attribute 'get'）
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

_SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server.py")


def _src() -> str:
    with open(_SERVER, encoding="utf-8") as f:
        return f.read()


def test_teach_stream_grade_gate_wired():
    """teach_stream 主循环必须接入学段特征守门（Round 12 根因修复）。"""
    src = _src()
    # gate 必须出现在 _teach_stream_gen 范围内（presentation 生成后、yield 前）
    assert "check_grade_features" in src
    assert "refine_for_grade" in src
    assert "grade_refined" in src
    # 必须位于主循环（_assistant_parts.append 之前），确保修改先于分片 yield
    assert src.index("check_grade_features") < src.index("_assistant_parts.append")
    # 需与 paeg.teach 同门控（PAEG_GRADE_GATE 环境开关 + llm_generated 判定）
    assert "PAEG_GRADE_GATE" in src
    assert 'presentation.get("llm_generated")' in src


def test_teach_stream_depth_gate_wired():
    """内容深度四要素守门（高中/大学/考研）必须同样接入 teach_stream。"""
    src = _src()
    assert "check_content_depth" in src
    assert "refine_content_depth" in src
    assert "depth_refined" in src
    assert '("high_school", "undergraduate", "graduate_exam")' in src


def test_on_session_end_summary_fixed():
    """on_session_end 的 dialogue_summary 不得对 str 列表元素调 .get（Round 12 修复）。"""
    src = _src()
    _m = re.search(r"dialogue_summary = .*?\n(\s*\)|\s*\)) or concept", src, re.S)
    assert _m, "dialogue_summary 构造块未找到"
    _blk = _m.group(0)
    # 修复后：isinstance 分支保护 str 元素
    assert "isinstance(p, str)" in _blk
    # 旧写法不得复活
    assert "p.get(\"content\") or \"\")[:100] for p" not in _blk.replace(
        "isinstance(p, str) else (p.get(\"content\") or \"\")[:100]", "")


def test_gate_functions_importable():
    """gate 函数可导入（防签名漂移）。"""
    from services.grade_quality_gate import (  # noqa: F401
        check_grade_features, build_refine_prompt, refine_for_grade,
        check_content_depth, refine_content_depth,
    )
