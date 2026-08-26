# -*- coding: utf-8 -*-
"""R5 MVQS 测试（§3.111 ⭐：代码级几何评估，无需渲染）。"""
import os
import sys

sys.path.insert(0, r"D:\wbo-workspace\paeg_project\05_实现原型")

import pytest

from manim_mvqs import mvqs_score, build_mvqs_feedback, audit_code

GOOD_CODE = '''
class Demo(Scene):
    def construct(self):
        c = Circle().move_to(LEFT)
        s = Square().next_to(c, RIGHT)
        t = Text("x").next_to(s, UP)
        self.play(Create(c), Create(s))
        self.wait(1)
'''

BAD_CODE = '''
class Demo(Scene):
    def construct(self):
        a = Circle()
        b = Square()
        c = Text("x")
        d = Dot()
        self.add(a, b, c, d)
'''


# ─────────────────────────────────────
# 1. MVQS 三维评分
# ─────────────────────────────────────
class TestMvqs:
    def test_good_code_pass(self):
        r = mvqs_score(GOOD_CODE)
        assert r["verdict"] == "PASS"
        assert r["mvqs"] >= 0.6
        assert r["overlap"] >= 0.8  # 有定位

    def test_bad_code_warn(self):
        r = mvqs_score(BAD_CODE)
        assert r["verdict"] in ("WARN", "FAIL")
        assert len(r["issues"]) >= 1  # 无定位 → 重叠/关系问题

    def test_returns_dims(self):
        r = mvqs_score(GOOD_CODE)
        for k in ("overlap", "relation", "boundary", "mvqs", "verdict", "issues"):
            assert k in r

    def test_empty_code(self):
        r = mvqs_score("")
        assert r["verdict"] in ("PASS", "WARN")

    def test_syntax_error(self):
        r = mvqs_score("class {")
        assert "mvqs" in r  # 不崩溃


# ─────────────────────────────────────
# 2. 反馈生成（供 RITL prompt）
# ─────────────────────────────────────
class TestMvqsFeedback:
    def test_good_no_feedback(self):
        assert build_mvqs_feedback(GOOD_CODE) == ""

    def test_bad_has_feedback(self):
        fb = build_mvqs_feedback(BAD_CODE)
        assert "MVQS 几何评估" in fb
        assert "避免重叠" in fb or "定位" in fb

    def test_alias(self):
        r = audit_code(GOOD_CODE)
        assert r["verdict"] == "PASS"
