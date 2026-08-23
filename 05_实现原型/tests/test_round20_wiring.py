# -*- coding: utf-8 -*-
"""§3.86 模块接线测试：sandbox 判定 + exec_engine 接入 tool_registry。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.sandbox import check, preset_for_mode


def test_sandbox_read_tools_allowed():
    """S1：只读工具任何 preset 放行。"""
    assert check("web_search", "teaching") == (True, "")
    assert check("get_time", "admin") == (True, "")


def test_sandbox_write_tools_teaching_denied():
    """S2：写工具 teaching 拒绝（教育安全：教学默认不落盘）。"""
    allowed, reason = check("generate_handout", "teaching")
    assert allowed is False
    assert "写操作" in reason or "preset" in reason


def test_sandbox_write_tools_lessonprep_allowed():
    """S3：写工具 lesson_prep 放行（备课物料生产）。"""
    assert check("generate_handout", "lesson_prep") == (True, "")
    assert check("generate_ppt", "lesson_prep") == (True, "")


def test_sandbox_exec_tools_only_admin():
    """S4：exec 工具仅 admin 放行（受控执行需运维权限）。"""
    assert check("execute_python", "teaching")[0] is False
    assert check("execute_python", "lesson_prep")[0] is False
    assert check("execute_python", "admin") == (True, "")


def test_preset_for_mode_mapping():
    """S5：教学模式 → preset 映射正确。"""
    assert preset_for_mode("lesson_prep") == "lesson_prep"
    assert preset_for_mode("teach") == "teaching"
    assert preset_for_mode("affection") == "teaching"


def test_exec_engine_validate_blocked():
    """S6：exec_engine 恶意代码拦截（安全红线）。"""
    from services.exec_engine import validate_code
    ok, _ = validate_code("import os; os.system('x')")
    assert not ok  # os import 必须拦截
    ok2, _ = validate_code("print('hi')")
    assert ok2  # 合法代码放行
