# -*- coding: utf-8 -*-
"""R7 叙事质量测试（§3.111 ⭐：17 视觉原则 + 6 叙事结构）。"""
import os
import sys

sys.path.insert(0, r"D:\wbo-workspace\paeg_project\05_实现原型")
_PLUGIN = r"D:\wbo-workspace\paeg_project\paeg-teaching-materials\src"
if os.path.isdir(_PLUGIN) and _PLUGIN not in sys.path:
    sys.path.insert(0, _PLUGIN)

import pytest


# ─────────────────────────────────────
# 1. 主项目：manim_narrative 常量
# ─────────────────────────────────────
class TestManimNarrative:
    def test_17_principles_loaded(self):
        from manim_narrative import VISUAL_PRINCIPLES_17
        # 17 条原则
        assert "Geometry before algebra" in VISUAL_PRINCIPLES_17
        assert "Opacity layering" in VISUAL_PRINCIPLES_17
        assert "Continuous morphing" in VISUAL_PRINCIPLES_17
        assert "Concrete values" in VISUAL_PRINCIPLES_17
        assert "Caption zone" in VISUAL_PRINCIPLES_17

    def test_6_narrative_arcs(self):
        from manim_narrative import NARRATIVE_ARCS, NARRATIVE_ARC_PROMPT
        assert len(NARRATIVE_ARCS) == 6
        assert "wrong_less_wrong_right" in NARRATIVE_ARCS
        assert "mystery_investigation" in NARRATIVE_ARCS
        assert "wrong_less_wrong_right" in NARRATIVE_ARC_PROMPT

    def test_narrative_arc_list(self):
        from manim_narrative import narrative_arc_list
        s = narrative_arc_list()
        assert "specific_general" in s
        assert "history_narrative" in s


# ─────────────────────────────────────
# 2. 主项目：visual_script_generator prompt 注入
# ─────────────────────────────────────
class TestScriptPromptR7:
    def test_prompt_has_principles(self):
        from visual_script_generator import build_script_prompt
        p = build_script_prompt("基变换", "高中", 240)
        assert "3Blue1Brown 视觉设计原则" in p
        assert "Geometry before algebra" in p
        assert "叙事结构" in p
        assert "wrong_less_wrong_right" in p


# ─────────────────────────────────────
# 3. 插件：manim_quality 同步常量 + ManimGenerator 注入
# ─────────────────────────────────────
class TestPluginR7:
    def test_plugin_constants(self):
        from paeg_teaching_materials.manim_quality import (
            VISUAL_PRINCIPLES_17, NARRATIVE_ARC_PROMPT)
        assert "Geometry before algebra" in VISUAL_PRINCIPLES_17
        assert "wrong_less_wrong_right" in NARRATIVE_ARC_PROMPT

    def test_plugin_generator_injects(self):
        """ManimGenerator system prompt 含 17 原则 + 叙事结构。"""
        from paeg_teaching_materials import MaterialRegistry
        from paeg_teaching_materials.generators import ManimGenerator

        captured = {}

        def mock_llm(system, user, max_tokens=2000, temperature=0.7):
            captured["system"] = system
            return "class Demo(Scene):\n    def construct(self):\n        self.play(FadeIn(Circle()))"

        MaterialRegistry.inject(llm=mock_llm)
        gen = ManimGenerator()
        gen.generate("导数", "数学")
        assert "3Blue1Brown 视觉设计原则" in captured["system"]
        assert "Geometry before algebra" in captured["system"]
        assert "wrong_less_wrong_right" in captured["system"]
