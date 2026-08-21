# -*- coding: utf-8 -*-
"""Round 11 ⭐ 物料质量强化测试（test_round18_material_quality.py）。

守护：
1. check_ppt_outline 新增检查器：合格 PPT 大纲通过、空页/占位/过短被拒
2. LessonPrep quality_report 接入 ppt_check（确定性 mock 路径）
3. 既有 handout/script/mindmap 检查器回归（不破坏）
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.material_quality import (
    check_handout, check_lecture_script, check_mindmap, check_ppt_outline,
)


class TestPptOutline:
    GOOD = (
        "## 封面\n- 函数的单调性\n- 数学 · 高中\n\n"
        "## 引入\n- 生活例子：气温变化\n- 提问：什么是增减\n\n"
        "## 定义\n- 单调递增/递减严格定义\n- 几何直观\n\n"
        "## 判定方法\n- 定义法步骤\n- 图像法\n\n"
        "## 例题\n- 例 1：证明 f(x)=x^2 在 [0,∞) 单调\n\n"
        "## 小结\n- 判定三法\n- 常见误区"
    )

    def test_good_passes(self):
        r = check_ppt_outline(self.GOOD)
        assert r["passed"], r["errors"]
        assert r["pages"] >= 5

    def test_too_few_pages(self):
        r = check_ppt_outline("## 封面\n- 标题")
        assert not r["passed"]
        assert any("分页过少" in e for e in r["errors"])

    def test_placeholder_rejected(self):
        bad = self.GOOD + "\n## 待补充\n- TODO 此处插入图片"
        r = check_ppt_outline(bad)
        assert not r["passed"]
        assert any("占位" in e for e in r["errors"])

    def test_empty_page_rejected(self):
        r = check_ppt_outline("## 封面\n- 标题\n\n## 正文\n\n## 小结\n- 结束")
        assert not r["passed"]
        assert any("空页" in e for e in r["errors"])

    def test_too_short(self):
        r = check_ppt_outline("## 页\n- 内容")
        assert not r["passed"]
        assert any("过短" in e for e in r["errors"])


class TestExistingCheckers:
    """回归：既有检查器不破坏。"""

    GOOD_HANDOUT = (
        "## 学习目标\n理解单调性\n\n"
        "## 核心内容\n定义与几何意义\n\n"
        "## 典型例题\n例 1：f(x)=x^2 在 [0,∞) 单调递增（数据：f(1)=1, f(2)=4）\n\n"
        "## 巩固练习\n练习：证明 f(x)=2x+1 单调\n\n"
        "## 小结\n定义法三步"
    )

    GOOD_SCRIPT = (
        "开场：同学们好，今天我们学习单调性。\n"
        "主体：好，那么先看定义，接下来我们证明。大家注意这里的符号。\n"
        "小结：总结三步判定法，用时 8 分钟。\n"
        "例子：就像爬山，海拔随路程上升。"
    )

    GOOD_MINDMAP = (
        "- 单调性\n"
        "  - 定义\n"
        "    - 递增\n"
        "    - 递减\n"
        "  - 判定\n"
        "    - 定义法\n"
        "    - 图像法"
    )

    def test_handout_good(self):
        r = check_handout(self.GOOD_HANDOUT)
        assert r["passed"], r["errors"]
        assert r["has_concrete_example"] and r["has_practice"]

    def test_handout_placeholder(self):
        r = check_handout(self.GOOD_HANDOUT + "\n待补充：例题二")
        assert not r["passed"]

    def test_script_good(self):
        r = check_lecture_script(self.GOOD_SCRIPT)
        assert r["passed"], r["errors"]

    def test_script_missing_transition(self):
        r = check_lecture_script("开场：你好。主体：内容。小结：结束。用时 5 分钟。")
        assert not r["passed"]

    def test_mindmap_good(self):
        r = check_mindmap(self.GOOD_MINDMAP)
        assert r["passed"], r["errors"]
        assert r["levels"] and max(r["levels"]) >= 1


class TestLessonPrepIntegration:
    """quality_report 接入 ppt_check（确定性 mock 路径）。"""

    def test_quality_report_has_ppt_check(self):
        from subagents import LessonPlanInput, LessonPrep

        class MockLLM:
            name = "mock"

            def chat(self, *a, **k):
                return "[mock]"

        prep = LessonPrep(MockLLM(), None)
        inp = LessonPlanInput(
            topic="函数的单调性", subject="math", grade="high_school",
            duration_min=10,
            objectives=["理解单调性", "掌握判定"],
        )
        out = prep.run(inp, learner=None)
        qr = out.get("quality_report") or {}
        assert "ppt_check" in qr, "quality_report 缺 ppt_check"
        assert qr["ppt_check"]["checked"], "ppt_check 未实际检查"
