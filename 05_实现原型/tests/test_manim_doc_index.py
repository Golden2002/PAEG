# -*- coding: utf-8 -*-
"""R2 RITL-DOC 测试（§3.111 ⭐：AST 抽 API + 签名注入）。"""
import os
import sys

sys.path.insert(0, r"D:\wbo-workspace\paeg_project\05_实现原型")

import pytest

from manim_doc_index import (
    extract_manim_apis, build_doc_block, get_api_doc, build_ritl_doc_prompt,
)


# ─────────────────────────────────────
# 1. API 索引
# ─────────────────────────────────────
class TestApiIndex:
    def test_common_apis_present(self):
        """≤200 常用 API 覆盖核心。"""
        for api in ("Scene", "self.play", "Circle", "MathTex", "Transform",
                    "Write", "Create", "Axes", "ValueTracker"):
            assert get_api_doc(api) is not None, f"缺 {api}"

    def test_signature_format(self):
        doc = get_api_doc("Create")
        assert "sig" in doc and "desc" in doc
        assert "描边" in doc["desc"]  # 有含义说明


# ─────────────────────────────────────
# 2. AST 抽取
# ─────────────────────────────────────
class TestExtract:
    def test_function_calls(self):
        code = "self.play(Create(circle), run_time=2)\nTransform(a, b)"
        apis = extract_manim_apis(code)
        assert "Create" in apis
        assert "Transform" in apis

    def test_attribute_calls(self):
        code = "self.wait(1)\ncircle.set_color(RED)"
        apis = extract_manim_apis(code)
        assert "set_color" in apis  # set_color 在索引

    def test_empty_and_clean(self):
        assert extract_manim_apis("") == []
        assert extract_manim_apis("print('hi')") == []

    def test_dedup(self):
        code = "self.play(Create(a))\nself.play(Create(b))"
        apis = extract_manim_apis(code)
        # Create 去重保留一个；self.play 的 attr "play" 不在索引（键是 "self.play"）
        assert apis.count("Create") == 1


# ─────────────────────────────────────
# 3. 文档块（只注入签名，剔除 Examples）
# ─────────────────────────────────────
class TestDocBlock:
    def test_block_has_signature_only(self):
        code = "self.play(Create(Text('hi')))"
        doc = build_doc_block(code)
        assert "Manim API 参考" in doc
        assert "Create" in doc
        # 不含完整 example 代码（只签名+说明）
        assert "class Demo" not in doc  # Examples 已剔除

    def test_empty_when_no_match(self):
        assert build_doc_block("print('hi')") == ""


# ─────────────────────────────────────
# 4. RITL-DOC prompt（错误 + 文档 + 修复指令）
# ─────────────────────────────────────
class TestRitlDocPrompt:
    def test_contains_error_and_doc(self):
        code = "self.play(Create(Text('hi')))"
        p = build_ritl_doc_prompt(code, "NameError: x")
        assert "NameError" in p
        assert "Manim API 参考" in p
        assert "请修复代码" in p

    def test_latex_hint(self):
        p = build_ritl_doc_prompt("x", "latex error")
        assert "Text() 替代 MathTex" in p
