# -*- coding: utf-8 -*-
"""v6.1 ⭐ Manim 模板库（LLM 失败时的兜底 + 演示）
首期 5 类数学动画模板（Oracle 建议）：函数曲线/坐标轴/导数切线/面积积分/几何变换
"""
import re

_TEMPLATES = {
    'derivative': '''from manim import *
import numpy as np

class DerivativeVisual(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3, 1], y_range=[-1, 9, 2],
                    x_length=8, y_length=5, axis_config={"color": WHITE})
        graph = axes.plot(lambda x: x**2, x_range=[-3, 3], color=GOLD)
        self.play(Create(axes), Create(graph))
        dot = Dot(color=BLUE).move_to(axes.c2p(0, 0))
        self.play(Create(dot))
        def tangent_at(x0):
            slope = 2 * x0
            return axes.plot(lambda x: slope*(x-x0)+x0**2,
                             x_range=[x0-1.5, x0+1.5], color=BLUE)
        tangent = tangent_at(0)
        self.play(Create(tangent))
        for x0 in np.linspace(-2, 2, 25):
            dot.move_to(axes.c2p(x0, x0**2))
            self.play(Transform(tangent, tangent_at(x0)), run_time=0.3)
        self.wait(2)
''',
    'quadratic': '''from manim import *

class QuadraticGraph(Scene):
    def construct(self):
        axes = Axes(x_range=[-4, 4, 1], y_range=[-5, 5, 1],
                    x_length=9, y_length=5, axis_config={"color": WHITE})
        graph = axes.plot(lambda x: x**2 - 2, x_range=[-3.5, 3.5], color=GOLD)
        vertex = Dot(axes.c2p(0, -2), color=RED)
        self.play(Create(axes), Create(graph))
        self.play(Create(vertex))
        self.wait(2)
''',
    'circle_area': '''from manim import *

class CircleArea(Scene):
    def construct(self):
        circle = Circle(radius=2, color=BLUE, fill_opacity=0.5)
        radius = Line(circle.get_center(), circle.get_right(), color=RED)
        center = Dot(circle.get_center(), color=WHITE)
        self.play(Create(circle), Create(radius), Create(center))
        # 半径旋转一周形成圆
        for _ in range(36):
            self.play(Rotate(radius, angle=TAU/36, about_point=circle.get_center()),
                      run_time=0.05)
        self.wait(2)
''',
    'vector_add': '''from manim import *

class VectorAdd(Scene):
    def construct(self):
        plane = NumberPlane(x_range=[-4, 4], y_range=[-4, 4],
                            background_line_style={"stroke_opacity": 0.3})
        v1 = Arrow(plane.c2p(0,0), plane.c2p(2,1), color=BLUE)
        v2 = Arrow(plane.c2p(0,0), plane.c2p(1,3), color=GREEN)
        vsum = Arrow(plane.c2p(0,0), plane.c2p(3,4), color=GOLD)
        self.play(Create(plane), Create(v1), Create(v2))
        self.play(Create(vsum))
        self.wait(2)
''',
    'transform': '''from manim import *

class ShapeTransform(Scene):
    def construct(self):
        square = Square(color=BLUE, fill_opacity=0.5)
        circle = Circle(color=GOLD, fill_opacity=0.5)
        self.play(Create(square))
        self.play(Transform(square, circle))
        self.wait(2)
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


def template_for(topic: str, subject: str = 'math') -> str:
    """根据主题关键词选模板（LLM 失败时兜底）"""
    t = (topic or '').lower()
    for name, kws in _KEYWORDS.items():
        if any(k in t for k in kws):
            return _TEMPLATES[name]
    # 默认：几何变换（最通用）
    return _TEMPLATES['transform']
