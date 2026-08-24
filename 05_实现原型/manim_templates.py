# -*- coding: utf-8 -*-
"""v6.1 ⭐ Manim 模板库（LLM 失败时的兜底 + 演示）
v0.65 ⭐ 三档分级速度：重复动作快(1.2s)、中间态中速(1.8s)、关键部分慢(3.0s)+Aha(2.5+3.0)。
引用 manim_speed 常量——用户不需要自己调速度，快慢交替符合教学节奏。
首期 5 类数学动画模板（Oracle 建议）：函数曲线/坐标轴/导数切线/面积积分/几何变换
"""
import re
from manim_speed import (
    QUICK_RUN, QUICK_WAIT, NORMAL_RUN, NORMAL_WAIT, KEY_RUN, KEY_WAIT,
    AHA_RUN, AHA_WAIT, CREATE_RUN, HOLD_WAIT, TITLE_RUN, TITLE_WAIT,
    END_WAIT, MID_WAIT,
)

_TEMPLATES = {
    'derivative': '''from manim import *
import numpy as np

class DerivativeVisual(Scene):
    def construct(self):
        self.wait(2)
        title = Text("导数：切线的斜率", font_size=42, color=WHITE)
        title.to_edge(UP)
        self.play(Write(title), run_time=__TITLE_RUN__)
        self.wait(__TITLE_WAIT__)
        axes = Axes(x_range=[-3, 3, 1], y_range=[-1, 9, 2],
                    x_length=8, y_length=5, axis_config={"color": WHITE})
        graph = axes.plot(lambda x: x**2, x_range=[-3, 3], color=GOLD)
        self.play(Create(axes), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Create(graph), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        dot = Dot(color=BLUE).move_to(axes.c2p(0, 0))
        self.play(Create(dot), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        def tangent_at(x0):
            slope = 2 * x0
            return axes.plot(lambda x: slope*(x-x0)+x0**2,
                             x_range=[x0-1.5, x0+1.5], color=BLUE)
        tangent = tangent_at(0)
        self.play(Create(tangent), run_time=__TRANSFORM_RUN__)
        self.wait(__HOLD_WAIT__)
        for x0 in np.linspace(-2, 2, 10):
            dot.move_to(axes.c2p(x0, x0**2))
            self.play(Transform(tangent, tangent_at(x0)), run_time=__MOVE_RUN__)
            self.wait(__MID_WAIT__)
        self.wait(__END_WAIT__)
''',
    'quadratic': '''from manim import *

class QuadraticGraph(Scene):
    def construct(self):
        self.wait(2)
        title = Text("二次函数 y = x² - 2", font_size=42, color=WHITE)
        title.to_edge(UP)
        self.play(Write(title), run_time=__TITLE_RUN__)
        self.wait(__TITLE_WAIT__)
        axes = Axes(x_range=[-4, 4, 1], y_range=[-5, 5, 1],
                    x_length=9, y_length=5, axis_config={"color": WHITE})
        graph = axes.plot(lambda x: x**2 - 2, x_range=[-3.5, 3.5], color=GOLD)
        self.play(Create(axes), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Create(graph), run_time=__TRANSFORM_RUN__)
        self.wait(__HOLD_WAIT__)
        vertex = Dot(axes.c2p(0, -2), color=RED)
        self.play(Create(vertex), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        vline = DashedLine(axes.c2p(0, -5), axes.c2p(0, 5), color=RED)
        self.play(Create(vline), run_time=__CREATE_RUN__)
        self.wait(__END_WAIT__)
''',
    'circle_area': '''from manim import *
import numpy as np

class CircleArea(Scene):
    """圆的面积：扇形切分 → 重组为近似长方形（v0.64 适中档）"""
    def construct(self):
        self.wait(2)
        title = Text("圆的面积：切分与重组", font_size=44, color=WHITE)
        title.to_edge(UP)
        self.play(Write(title), run_time=__TITLE_RUN__)
        self.wait(__TITLE_WAIT__)
        circle = Circle(radius=2.2, color=BLUE, fill_opacity=0.2)
        radius = Line(circle.get_center(), circle.get_right(), color=RED, stroke_width=3)
        r_label = Text("r", font_size=32, color=RED).move_to(radius.get_center() + UP*0.3)
        self.play(Create(circle), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Create(radius), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Write(r_label), run_time=__TITLE_RUN__)
        self.wait(__HOLD_WAIT__)
        n = 8
        sectors = []
        for i in range(n):
            start_ang = i * TAU / n
            sector = Sector(
                arc_center=circle.get_center(), radius=2.2,
                start_angle=start_ang, angle=TAU/n,
                color=BLUE if i % 2 == 0 else GOLD,
                fill_opacity=0.8, stroke_width=1.5,
            )
            sectors.append(sector)
        # 逐个慢速呈现切分（教学观察）
        for i, s in enumerate(sectors):
            self.play(FadeIn(s), run_time=__CREATE_RUN__)
            self.wait(__MID_WAIT__)
        self.wait(__HOLD_WAIT__)
        # 重组：淡出原扇形 → 新位置逐个显现（规避 Sector.animate 兼容）
        half = n // 2
        center = circle.get_center()
        target_positions = []
        for i in range(n):
            if i < half:
                x = center[0] - 2.8 + i * 1.55
                y = center[1] + 0.0
            else:
                x = center[0] - 2.8 + (i - half) * 1.55
                y = center[1] - 0.45
            target_positions.append((x, y))
        self.play(*[FadeOut(s) for s in sectors], run_time=__TRANSFORM_RUN__)
        self.wait(__MID_WAIT__)
        new_sectors = []
        for sec, tgt in zip(sectors, target_positions):
            ns = Sector(
                arc_center=np.array([tgt[0], tgt[1], 0.0]), radius=2.2,
                start_angle=0.0, angle=TAU/n,
                color=sec.color, fill_opacity=0.8, stroke_width=1.5,
            )
            new_sectors.append(ns)
        # 重组：一次两个
        for i in range(0, n, 2):
            self.play(*[FadeIn(s, shift=DOWN*0.2) for s in new_sectors[i:i+2]], run_time=__TRANSFORM_RUN__)
            self.wait(__MID_WAIT__)
        self.wait(__HOLD_WAIT__)
        base_line = Line(
            np.array([center[0] - 3.0, center[1] - 0.2, 0]),
            np.array([center[0] + 3.0, center[1] - 0.2, 0]),
            color=GREEN, stroke_width=3,
        )
        self.play(Create(base_line), run_time=__CREATE_RUN__)
        self.wait(__END_WAIT__)
''',
    'vector_add': '''from manim import *

class VectorAdd(Scene):
    def construct(self):
        self.wait(2)
        title = Text("向量加法：首尾相连", font_size=42, color=WHITE)
        title.to_edge(UP)
        self.play(Write(title), run_time=__TITLE_RUN__)
        self.wait(__TITLE_WAIT__)
        plane = NumberPlane(x_range=[-4, 4], y_range=[-4, 4],
                            background_line_style={"stroke_opacity": 0.3})
        v1 = Arrow(plane.c2p(0,0), plane.c2p(2,1), color=BLUE)
        v2 = Arrow(plane.c2p(0,0), plane.c2p(1,3), color=GREEN)
        vsum = Arrow(plane.c2p(0,0), plane.c2p(3,4), color=GOLD)
        self.play(Create(plane), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Create(v1), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Create(v2), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Create(vsum), run_time=__TRANSFORM_RUN__)
        self.wait(__END_WAIT__)
''',
    'transform': '''from manim import *

class ShapeTransform(Scene):
    def construct(self):
        self.wait(2)
        title = Text("几何变换：正方形到圆", font_size=42, color=WHITE)
        title.to_edge(UP)
        self.play(Write(title), run_time=__TITLE_RUN__)
        self.wait(__TITLE_WAIT__)
        square = Square(color=BLUE, fill_opacity=0.5)
        circle = Circle(color=GOLD, fill_opacity=0.5)
        self.play(Create(square), run_time=__CREATE_RUN__)
        self.wait(__HOLD_WAIT__)
        self.play(Transform(square, circle), run_time=__TRANSFORM_RUN__)
        self.wait(__END_WAIT__)
''',
}

# 关键词 → 模板
_KEYWORDS = {
    'derivative': ['导数', '切线', '斜率', 'derivative', 'tangent', 'slope'],
    'quadratic': ['二次', '抛物线', 'quadratic', 'parabola'],
    'circle_area': ['圆面积', '圆的面积', 'circle area'],
    'vector_add': ['向量', '矢量', 'vector'],
    'transform': ['变换', '几何变换', 'transform', '旋转'],
}

# 用常量替换模板中的占位符（__CREATE_RUN__ 等）
for _name, _code in _TEMPLATES.items():
    _code = _code.replace('__CREATE_RUN__', repr(CREATE_RUN))
    _code = _code.replace('__TRANSFORM_RUN__', repr(NORMAL_RUN))
    _code = _code.replace('__MOVE_RUN__', repr(QUICK_RUN))
    _code = _code.replace('__HOLD_WAIT__', repr(HOLD_WAIT))
    _code = _code.replace('__TITLE_WAIT__', repr(TITLE_WAIT))
    _code = _code.replace('__TITLE_RUN__', repr(TITLE_RUN))
    _code = _code.replace('__END_WAIT__', repr(END_WAIT))
    _code = _code.replace('__MID_WAIT__', repr(MID_WAIT))
    _TEMPLATES[_name] = _code


# §3.100 ⭐ 3B1B 公式推导链模板（TransformMatchingTex 渐进披露 + hook + recap）
_TEMPLATES['derivative_chain'] = '''from manim import *
import numpy as np

class DerivativeChainScene(Scene):
    """3B1B 风格公式推导链：钩子 → 几何直觉 → 公式逐步变形 → recap。"""
    def construct(self):
        # HOOK：反直觉问题（钩子开头，§3.100）
        hook = Text("割线会变成切线吗？", font_size=36)
        self.play(Write(hook))
        self.wait(1.5)
        self.play(FadeOut(hook))

        # 几何直觉：抛物线 + 割线逼近
        axes = Axes(x_range=[-2, 3], y_range=[-1, 5], axis_config={"include_numbers": True})
        graph = axes.plot(lambda x: x**2, color=BLUE)
        p1 = axes.c2p(1, 1)
        p2 = axes.c2p(2, 4)
        secant = Line(p1, p2, color=YELLOW)
        labels = MathTex("f(x)=x^2").to_corner(UL)
        self.play(Create(axes), Create(graph))
        self.play(Write(labels), Create(secant))
        self.wait(1.5)

        # 渐进披露：公式逐步变形（TransformMatchingTex，§3.100）
        slope_intro = MathTex("\\text{割线斜率} =", "\\frac{f(b)-f(a)}{b-a}")
        self.play(Write(slope_intro))
        self.wait(1.5)
        limit_form = MathTex("f'(a) =", "\\lim_{b \\to a}", "\\frac{f(b)-f(a)}{b-a}")
        self.play(TransformMatchingTex(slope_intro, limit_form))
        self.wait(2.0)
        tangent_form = MathTex("f'(a) =", "\\lim_{h \\to 0}", "\\frac{f(a+h)-f(a)}{h}")
        self.play(TransformMatchingTex(limit_form, tangent_form))
        self.wait(2.0)

        # RECAP：核心结论回顾（recap 结尾，§3.100）
        recap = Text("导数是切线的斜率", font_size=36, color=GREEN)
        self.play(Transform(tangent_form, recap))
        self.wait(2.0)

def template_for(topic: str, subject: str = 'math') -> str:
    """根据主题关键词选模板（LLM 失败时兜底）"""
    t = (topic or '').lower()
    for name, kws in _KEYWORDS.items():
        if any(k in t for k in kws):
            return _TEMPLATES[name]
    # 默认：几何变换（最通用）
    return _TEMPLATES['transform']


def template_by_key(key: str, topic: str = '') -> str:
    """v0.63 ⭐ 按意图 key 直接选模板（manim_prompts 场景匹配后兜底）。"""
    if key in _TEMPLATES:
        return _TEMPLATES[key]
    return template_for(topic)
