# -*- coding: utf-8 -*-
"""manim_narrative.py — Manim 叙事质量增强（§3.111 ⭐ R7 顶尖化）

基于 3B1B 17 视觉设计原则（clawRxiv 2603.00082）+ 6 叙事结构（manim_skill 社区库），
编码为可注入 visual_script_generator / 插件 ManimGenerator 的提示词常量。

来源：
- 17 视觉原则：Geometry before algebra / Opacity layering / Persistent context /
  Linked dual representations / Parameter manipulation / Continuous morphing /
  Question frames / Annotations ON objects / Color as semantic data /
  Concrete values / Progressive complexity / Emotional anchoring /
  Live values in diagrams / Density ramp / Per-scene skeleton / Caption zone /
  Monospace for all Text
- 6 叙事结构：Mystery→Investigation→Resolution / Build Up→Payoff /
  Two Perspectives→Unity / Wrong→Less Wrong→Right / Specific→General /
  History as Narrative
"""

from __future__ import annotations


# ─────────────────────────────────────
# 3B1B 17 视觉设计原则（精简版，注入剧本 prompt）
# ─────────────────────────────────────
VISUAL_PRINCIPLES_17 = """### 3Blue1Brown 视觉设计原则（17 条 · §3.111 ⭐）
1. **Geometry before algebra**：图形先于公式——先展示几何对象，再引入符号（视觉记忆快 6 倍）
2. **Opacity layering**：层级透明度——主对象 100% / 上下文 40% / 网格 15%
3. **Persistent context**：上下文常驻——被缩小的父对象保留 30-40% 可见度，不消失
4. **Linked dual representations**：双重表示联动——共享 ValueTracker，图形与公式同步变化
5. **Parameter manipulation**：参数操控——让观众"玩"参数（滑块/拖动）理解影响
6. **Continuous morphing**：连续形变——用 ReplacementTransform 保持对象身份（非突变）
7. **Question frames**：提问帧——先提问→停 2-3 秒→再视觉回答
8. **Annotations ON objects**：标注贴物体——标签紧贴对象（防 split-attention）
9. **Color as semantic data**：颜色即语义——一色一义，颜色有数学含义
10. **Concrete values**：具体数值——用真数字（[0.34, 0.16, ...]）而非符号占位
11. **Progressive complexity**：渐进复杂度——层层叠加，旧层 dim 到 0.3
12. **Emotional anchoring**：情感锚点——关键时刻用强烈视觉（如大号文字/醒目色）
13. **Live values in diagrams**：实时数值——DecimalNumber + always_redraw 显示变化
14. **Density ramp**：密度渐变——从 2 元素渐增到 15 元素
15. **Per-scene skeleton**：每场景锚图——每 scene 一个核心视觉锚
16. **Caption zone**：字幕区——底部 20% 留白给字幕/标注
17. **Monospace for all Text**：等宽字体——所有文本用等宽字体（如 Menlo）"""


# ─────────────────────────────────────
# 6 叙事结构（剧本 prompt 选 1 个）
# ─────────────────────────────────────
NARRATIVE_ARCS = {
    "mystery_investigation": "谜题→调查→解答：开头抛出一个反直觉现象/谜题，逐步揭示机制，结尾解答",
    "build_up_payoff": "搭建→兑现：先铺垫工具/概念，关键时刻统一兑现（如所有工具同时发挥作用）",
    "two_perspectives_unity": "双视角→统一：从两个看似矛盾的角度看同一对象，最终统一为一个洞见",
    "wrong_less_wrong_right": "错误→更接近→正确（学习增益最强）：先展示常见错误直觉，逐步修正到正确理解",
    "specific_general": "特例→一般：先深入一个具体例子，再推广到一般规律",
    "history_narrative": "历史叙事：按概念发现的历史顺序讲述，每一步为何被提出",
}

NARRATIVE_ARC_PROMPT = """### 叙事结构（§3.111 ⭐ 选 1 个填 narrative_arc）
根据主题选择最合适的叙事结构，填到 narrative_arc 字段：
- mystery_investigation：谜题→调查→解答（开头抛反直觉现象/谜题）
- build_up_payoff：搭建→兑现（先铺垫工具，关键处统一兑现）
- two_perspectives_unity：双视角→统一（矛盾视角最终统一）
- wrong_less_wrong_right：错误→更接近→正确（先展示错误直觉再修正——学习增益最强）
- specific_general：特例→一般（具体例子→一般规律）
- history_narrative：历史叙事（按发现顺序讲述）"""


def narrative_arc_list() -> str:
    """6 叙事结构清单（供 prompt 注入）。"""
    return "\n".join(f"- {k}: {v}" for k, v in NARRATIVE_ARCS.items())
