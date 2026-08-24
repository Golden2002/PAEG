我看到代码在第97行附近被截断了，而且存在全角冒号字符问题。让我修复并补全代码：

```python
from manim import *

class DerivativeTangentScene(Scene):
    def construct(self):
        # 配置
        self.camera.background_color = "#1e1e1e"
        
        # 坐标轴
        axes = Axes(
            x_range=[-1, 5, 1],
            y_range=[-1, 5, 1],
            x_length=8,
            y_length=6,
            axis_config={"color": "#FFFFFF", "include_numbers": True}
        )
        axes.shift(DOWN * 0.5)
        
        # 函数曲线 f(x) = 0.2*(x-2)^2 + 1
        curve = axes.plot(
            lambda x: 0.2 * (x - 2) ** 2 + 1,
            x_range=[-0.5, 4.5],
            color="#4ECDC4",
            stroke_width=3
        )
        
        # 固定点 P(2,1)
        fixed_point = Dot(
            axes.coords_to_point(2, 1),
            color="#FF6B6B",
            radius=0.08
        )
        fixed_label = Text("P", color="#FF6B6B", font_size=24).next_to(fixed_point, UR, buff=0.1)
        
        # 动点 Q（初始位置远离 P）
        q_x = 3.5
        q_y = 0.2 * (q_x - 2) ** 2 + 1
        moving_point = Dot(
            axes.coords_to_point(q_x, q_y),
            color="#FFD93D",
            radius=0.08
        )
        moving_label = Text("Q", color="#FFD93D", font_size=24).next_to(moving_point, UR, buff=0.1)
        
        # 割线（初始）
        secant_line = Line(
            fixed_point.get_center(),
            moving_point.get_center(),
            color="#FF6B6B",
            stroke_width=2
        )
        secant_label = Text("割线", color="#FF6B6B", font_size=24).next_to(secant_line, DOWN, buff=0.1)
        
        # 创建所有元素
        self.play(Create(axes), Create(curve))
        self.play(Create(fixed_point), Write(fixed_label))
        self.play(Create(moving_point), Write(moving_label))
        self.play(Create(secant_line), Write(secant_label))
        
        # 动画：Q 点逐渐靠近 P 点
        q_x_values = [3.5, 3.0, 2.5, 2.2, 2.05, 2.01]
        for i in range(1, len(q_x_values)):
            new_q_x = q_x_values[i]
            new_q_y = 0.2 * (new_q_x - 2) ** 2 + 1
            new_point = Dot(
                axes.coords_to_point(new_q_x, new_q_y),
                color="#FFD93D",
                radius=0.08
            )
            new_line = Line(
                fixed_point.get_center(),
                new_point.get_center(),
                color="#FF6B6B",
                stroke_width=2
            )
            
            # 更新动点、割线和标签
            self.play(
                Transform(moving_point, new_point),
                Transform(secant_line, new_line),
                run_time=0.5
            )
            moving_label.next_to(moving_point, UR, buff=0.1)
        
        # 最终显示切线
        tangent_line = Line(
            axes.coords_to_point(0.5, 0.2 * (0.5 - 2) ** 2 + 1),
            axes.coords_to_point(3.5, 0.2 * (3.5 - 2) ** 2 + 1),
            color="#FFD93D",
            stroke_width=3
        )
        tangent_label = Text("切线", color="#FFD93D", font_size=24).next_to(tangent_line, UR, buff=0.1)
        
        self.play(
            Transform(secant_line, tangent_line),
            Write(tangent_label)
        )
        
        # 移除割线标签，保留切线标签
        self.play(FadeOut(secant_label))
        
        self.wait(2)
```