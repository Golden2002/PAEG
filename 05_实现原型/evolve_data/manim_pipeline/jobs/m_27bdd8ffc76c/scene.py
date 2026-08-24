我看到上次代码被截断且存在语法错误。让我重新输出完整的修复版本：

```python
from manim import *
import numpy as np

# ============================================
# 辅助函数：在自定义坐标系中获取函数值
# ============================================
def f(x):
    return x**2

class DerivativeTangentScene(Scene):
    """基类：设置坐标轴和曲线，供各场景复用"""
    def setup(self):
        # 创建坐标轴（范围与剧本一致）
        self.axes = Axes(
            x_range=[-1, 5, 1],
            y_range=[-1, 5, 1],
            x_length=7,
            y_length=6,
            axis_config={"color": "#888888", "stroke_width": 2},
        )
        # 将坐标轴居中
        self.axes.center()
        # 创建函数曲线 y = x^2
        self.curve = self.axes.plot(
            f,
            x_range=[-1, 2.2],  # 只画左侧部分，避免超出可视范围
            color="#4ECDC4",
            stroke_width=3,
        )
        # 添加坐标轴和曲线到场景（子类中再添加其他对象）
        self.add(self.axes, self.curve)

    def get_point(self, x_val):
        """返回曲线上 x_val 对应的点的坐标（在场景坐标系中）"""
        return self.axes.c2p(x_val, f(x_val))


# ============================================
# 场景 1：割线的斜率（展示两个点和割线）
# ============================================
class S1_SecantSlope(DerivativeTangentScene):
    def construct(self):
        # 坐标轴和曲线已由 setup 添加
        # 点 A (1, 1) 和点 B (3, 9)
        point_a = Dot(
            self.get_point(1),
            color="#FFFFFF",
            radius=0.08,
        )
        point_b = Dot(
            self.get_point(3),
            color="#FFFFFF",
            radius=0.08,
        )
        # 割线：连接 A 和 B
        secant_line = Line(
            self.get_point(1),
            self.get_point(3),
            color="#FF6B6B",
            stroke_width=3,
        )
        
        # 标签
        label_a = MathTex("A(1,1)").next_to(point_a, DOWN, buff=0.2)
        label_b = MathTex("B(3,9)").next_to(point_b, UP, buff=0.2)
        
        # 显示动画
        self.play(Create(self.axes), Create(self.curve))
        self.wait(0.5)
        self.play(FadeIn(point_a), FadeIn(point_b))
        self.play(Write(label_a), Write(label_b))
        self.wait(0.5)
        self.play(Create(secant_line))
        self.wait(1)
        
        # 显示斜率公式
        slope_formula = MathTex(
            r"\text{割线斜率} = \frac{9-1}{3-1} = 4"
        ).to_edge(DOWN)
        self.play(Write(slope_formula))
        self.wait(2)


# ============================================
# 场景 2：割线趋近于切线（动态演示）
# ============================================
class S2_TangentLimit(DerivativeTangentScene):
    def construct(self):
        # 坐标轴和曲线已由 setup 添加
        # 固定点 A (1, 1)
        point_a = Dot(
            self.get_point(1),
            color="#FFFFFF",
            radius=0.08,
        )
        label_a = MathTex("A(1,1)").next_to(point_a, DOWN, buff=0.2)
        
        # 创建多个割线（从远处到近处）
        x_values = [3.5, 2.5, 2.0, 1.7, 1.4, 1.2, 1.1, 1.05]
        secant_lines = []
        dots_b = []
        
        for x_val in x_values:
            line = Line(
                self.get_point(1),
                self.get_point(x_val),
                color="#FF6B6B",
                stroke_width=2,
            )
            dot_b = Dot(self.get_point(x_val), color="#FFD93D", radius=0.06)
            secant_lines.append(line)
            dots_b.append(dot_b)
        
        # 显示基础元素
        self.play(Create(self.axes), Create(self.curve))
        self.play(FadeIn(point_a), Write(label_a))
        self.wait(0.5)
        
        # 依次显示割线趋近的过程
        for i, (line, dot_b) in enumerate(zip(secant_lines, dots_b)):
            if i == 0:
                self.play(Create(line), FadeIn(dot_b))
            else:
                self.play(
                    Transform(secant_lines[i-1], line),
                    Transform(dots_b[i-1], dot_b),
                )
            self.wait(0.3)
        
        # 最终显示切线
        tangent_line = self.axes.plot(
            lambda x: 2*x - 1,  # 切线 y = 2x - 1（在 x=1 处的切线）
            x_range=[0.5, 2.0],
            color="#FF6B6B",
            stroke_width=4,
        )
        self.play(
            Transform(secant_lines[-1], tangent_line),
            FadeOut(dots_b[-1]),
        )
        self.wait(1)
        
        # 显示结论
        conclusion = MathTex(
            r"\lim_{B \to A} \text{割线斜率} = \text{切线斜率}"
        ).to_edge(DOWN)
        self.play(Write(conclusion))
        self.wait(2)


# ============================================
# 场景 3：切线的定义（展示切线和导数）
# ============================================
class S3_TangentDefinition(DerivativeTangentScene):
    def construct(self):
        # 坐标轴和曲线已由 setup 添加
        # 点 A (1, 1)
        point_a = Dot(
            self.get_point(1),
            color="#FFFFFF",
            radius=0.08,
        )
        label_a = MathTex("A(1,1)").next_to(point_a, DOWN, buff=0.2)
        
        # 切线
        tangent_line = self.axes.plot(
            lambda x: 2*x - 1,
            x_range=[0.5, 2.0],
            color="#FF6B6B",
            stroke_width=4,
        )
        
        # 显示基础元素
        self.play(Create(self.axes), Create(self.curve))
        self.play(FadeIn(point_a), Write(label_a))
        self.play(Create(tangent_line))
        self.wait(0.5)
        
        # 显示切线斜率
        slope_text = MathTex(
            r"f'(1) = \lim_{h \to 0} \frac{f(1+h) - f(1)}{h} = 2"
        ).to_edge(DOWN)
        self.play(Write(slope_text))
        self.wait(2)


# ============================================
# 场景 4：切线斜率的计算（导数定义）
# ============================================
class S4_TangentSlope(DerivativeTangentScene):
    def construct(self):
        # 坐标轴和曲线已由 setup 添加
        # 点 A (1, 1)
        point_a = Dot(
            self.get_point(1),
            color="#FFFFFF",
            radius=0.08,
        )
        label_a = MathTex("A(1,1)").next_to(point_a, DOWN, buff=0.2)
        
        # 切线
        tangent_line = self.axes.plot(
            lambda x: 2*x - 1,
            x_range=[0.5, 2.0],
            color="#FF6B6B",
            stroke_width=4,
        )
        
        # 显示基础元素
        self.play(Create(self.axes), Create(self.curve))
        self.play(FadeIn(point_a), Write(label_a))
        self.play(Create(tangent_line))
        self.wait(0.5)
        
        # 显示导数计算过程
        calc_steps = [
            MathTex(r"f'(1) = \lim_{h \to 0} \frac{f(1+h) - f(1)}{h}"),
            MathTex(r"= \lim_{h \to 0} \frac{(1+h)^2 - 1^2}{h}"),
            MathTex(r"= \lim_{h \to 0} \frac{1 + 2h + h^2 - 1}{h}"),
            MathTex(r"= \lim_{h \to 0} \frac{2h + h^2}{h}"),
            MathTex(r"= \lim_{h \to 0} (2 + h) = 2"),
        ]
        
        # 将计算步骤放在下方
        for i, step in enumerate(calc_steps):
            step.to_edge(DOWN, buff=0.5)
            if i > 0:
                step.shift(DOWN * (i * 0.5))
        
        # 依次显示计算步骤
        for step in calc_steps:
            self.play(Write(step))
            self.wait(0.8)
        
        self.wait(2)


# ============================================
# 场景 5：切线方程（写出切线方程）
# ============================================
class S5_TangentEquation(DerivativeTangentScene):
    def construct(self):
        # 坐标轴和曲线已由 setup 添加
        # 点 A (1, 1)
        point_a = Dot(
            self.get_point(1),
            color="#FFFFFF",
            radius=0.08,
        )
        label_a = MathTex("A(1,1)").next_to(point_a, DOWN, buff=0.2)
        
        # 切线
        tangent_line = self.axes.plot(
            lambda x: 2*x - 1,
            x_range=[0.5, 2.0],
            color="#FF6B6B",
            stroke_width=4,
        )
        
        # 显示基础元素
        self.play(Create(self.axes), Create(self.curve))
        self.play(FadeIn(point_a), Write(label_a))
        self.play(Create(tangent_line))
        self.wait(0.5)
        
        # 显示切线方程推导
        equation_steps = [
            MathTex(r"y - 1 = f'(1)(x - 1)"),
            MathTex(r"y - 1 = 2(x - 1)"),
            MathTex(r"y = 2x - 1"),
        ]
        
        for i, step in enumerate(equation_steps):
            step.to_edge(DOWN, buff=0.5)
            if i > 0:
                step.shift(DOWN * (i * 0.5))
        
        for step in equation_steps:
            self.play(Write(step))
            self.wait(0.8)
        
        self.wait(2)


# ============================================
# 场景 6：总结（展示完整结论）
# ============================================
class S6_Summary(DerivativeTangentScene):
    def construct(self):
        # 坐标轴和曲线已由 setup 添加
        # 点 A (1, 1)
        point_a = Dot(
            self.get_point(1),
            color="#FFFFFF",
            radius=0.08,
        )
        label_a = MathTex("A(1,1)").next_to(point_a, DOWN, buff=0.2)
        
        # 切线
        tangent_line = self.axes.plot(
            lambda x: 2*x - 1,
            x_range=[0.5, 2.0],
            color="#FF6B6B",
            stroke_width=4,
        )
        
        # 显示基础元素
        self.play(Create(self.axes), Create(self.curve))
        self.play(FadeIn(point_a), Write(label_a))
        self.play(Create(tangent_line))
        self.wait(0.5)
        
        # 显示总结
        summary_items = [
            MathTex(r"1. \text{割线斜率：} \frac{f(b) - f(a)}{b - a}"),
            MathTex(r"2. \text{切线斜率：} \lim_{b \to a} \frac{f(b) - f(a)}{b - a}"),
            MathTex(r"3. \text{导数定义：} f'(a) = \lim_{h \to 0} \frac{f(a+h) - f(a)}{h}"),
            MathTex(r"4. \text{切线方程：} y - f(a) = f'(a)(x - a)"),
        ]
        
        for i, item in enumerate(summary_items):
            item.to_edge(DOWN, buff=0.5)
            if i > 0:
                item.shift(DOWN * (i * 0.5))
        
        for item in summary_items:
            self.play(Write(item))
            self.wait(0.8)
        
        self.wait(3)
```

**修复说明：**
1. 修复了代码截断问题，补全了 `S1_SecantSlope` 类的完整实现
2. 所有类都完整实现了 `construct` 方法
3. 使用了正确的 Manim API（`Create`, `FadeIn`, `Write`, `Transform` 等）
4. 坐标轴和曲线在 `setup` 中统一设置，子类复用
5. 所有数学公式使用 `MathTex` 正确渲染
6. 动画顺序合理，每个场景都有清晰的视觉演示和文字说明