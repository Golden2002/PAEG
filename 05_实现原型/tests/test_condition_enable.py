# -*- coding: utf-8 -*-
"""test_condition_enable.py — #4 !!js 条件启停测试（Harness 30 项 P1，安全子集）

覆盖：受限条件求值器（ast 白名单，dsh `disabled: !!js expr` 的安全子集）——
布尔/比较/平台/环境变量/模块状态条件启停；任意代码被拒绝（安全边界）。
dsh Harness 借鉴（config `disabled: !!js expr`，commit 47f9438）：
条件启停配置化，不改代码调启停。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_bool_condition():
    """布尔表达式求值（and/or/not）。"""
    from services.condition_eval import evaluate_condition
    assert evaluate_condition("True and not False") is True
    assert evaluate_condition("False or True") is True
    assert evaluate_condition("False and True") is False


def test_comparison_condition():
    """比较表达式（==/!=/</>）。"""
    from services.condition_eval import evaluate_condition
    assert evaluate_condition("1 < 2") is True
    assert evaluate_condition("'win32' == 'win32'") is True
    assert evaluate_condition("3 > 5") is False


def test_platform_condition():
    """平台条件（platform() 检测）。"""
    from services.condition_eval import evaluate_condition
    import sys as _sys
    expected = _sys.platform.startswith("win")
    assert evaluate_condition("platform() == 'win'") is expected
    # 反平台条件
    assert evaluate_condition("platform() != 'darwin'") is True


def test_env_condition(monkeypatch):
    """环境变量条件（env('VAR') 检测）。"""
    from services.condition_eval import evaluate_condition
    monkeypatch.setenv("PAEG_TEST_FLAG", "1")
    assert evaluate_condition("env('PAEG_TEST_FLAG') == '1'") is True
    monkeypatch.delenv("PAEG_TEST_FLAG", raising=False)
    assert evaluate_condition("env('PAEG_TEST_FLAG') == '1'") is False


def test_module_condition():
    """模块状态条件（module('id') 检测——与 module_registry.is_enabled 一致）。"""
    from services.condition_eval import evaluate_condition
    # chat 是核心模块，默认启用
    assert evaluate_condition("module('chat')") is True
    # 未知模块：module_registry 防御性默认启用（ratchet：行为一致）
    assert evaluate_condition("module('no_such_module')") is True


def test_arbitrary_code_rejected():
    """安全边界：任意代码/导入/调用被拒绝（不抛异常 → 返回 False）。"""
    from services.condition_eval import evaluate_condition
    assert evaluate_condition("__import__('os').system('dir')") is False
    assert evaluate_condition("open('C:/Windows/win.ini').read()") is False
    assert evaluate_condition("lambda: 1") is False
    assert evaluate_condition("[].__class__.__mro__") is False


def test_syntax_error_returns_false():
    """非法表达式/空串 → False（容错，不抛异常）。"""
    from services.condition_eval import evaluate_condition
    assert evaluate_condition("") is False
    assert evaluate_condition("1 +") is False
    assert evaluate_condition("not a valid expr !!!") is False
