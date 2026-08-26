# -*- coding: utf-8 -*-
"""RITL 闭环测试（§3.111 ⭐ T1.A：渲染错误回灌）。"""
import os
import sys

sys.path.insert(0, r"D:\wbo-workspace\paeg_project\05_实现原型")

import pytest

from manim_pipeline import (
    _extract_error_tail, _classify_error, _build_ritl_prompt,
)


# ─────────────────────────────────────
# 1. 错误 tail 截取（ManimTrainer N=10）
# ─────────────────────────────────────
class TestExtractErrorTail:
    def test_short_error_full(self):
        e = "NameError: x"
        assert _extract_error_tail(e) == "NameError: x"

    def test_long_error_tail_10(self):
        e = "\n".join(f"line {i}" for i in range(30))
        tail = _extract_error_tail(e)
        assert tail == "\n".join(f"line {i}" for i in range(20, 30))  # 最后 10 行
        assert len(tail.splitlines()) == 10

    def test_empty(self):
        assert _extract_error_tail("") == "NONE"


# ─────────────────────────────────────
# 2. 错误签名分类
# ─────────────────────────────────────
class TestClassifyError:
    def test_code_api(self):
        assert _classify_error("SyntaxError: invalid syntax") == "code_api"
        assert _classify_error("AttributeError: 'Scene' has no attribute 'x'") == "code_api"
        assert _classify_error("NameError: name 'Text' is not defined") == "code_api"

    def test_latex(self):
        assert _classify_error("latex error: missing package") == "latex"
        assert _classify_error("TexTemplateError: LaTeX failed") == "latex"

    def test_resource(self):
        assert _classify_error("TimeoutError: render timed out") == "resource"

    def test_generic(self):
        assert _classify_error("something unexpected happened") == "generic"


# ─────────────────────────────────────
# 3. RITL 修复提示（含 safety lint 反馈）
# ─────────────────────────────────────
class TestRitlPrompt:
    def test_contains_error_tail(self):
        p = _build_ritl_prompt("Manim 代码", {"code": "x"}, "Traceback: NameError: x")
        assert "NameError" in p
        assert "Manim 代码 修复器" in p

    def test_contains_safety_feedback(self):
        """含 12 崩溃模式 lint 反馈（C1 Create(Text)）。"""
        bad_code = "class S(Scene):\n    def construct(self):\n        self.play(Create(Text('hi')))"
        p = _build_ritl_prompt("Manim 代码", bad_code, "NameError", code=bad_code)
        assert "C1" in p  # safety lint 反馈

    def test_latex_hint(self):
        p = _build_ritl_prompt("Manim 代码", "x", "latex error: missing")
        assert "Text() 替代 MathTex" in p

    def test_clean_code_no_safety(self):
        clean = "class S(Scene):\n    def construct(self):\n        self.play(FadeIn(Circle()))"
        p = _build_ritl_prompt("Manim 代码", clean, "NameError", code=clean)
        assert "C1" not in p  # 无违规不注入 lint 反馈
