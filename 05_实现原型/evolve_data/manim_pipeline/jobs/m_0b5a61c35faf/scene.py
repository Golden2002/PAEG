```python
from manim import *
import numpy as np

class BasisChangeScene(Scene):
    def construct(self):
        # ===== 全局设置 =====
        self.camera.background_color = "#0d1117"
        
        # ===== 颜色常量 =====
        STANDARD_BASIS_COLOR = "#58a6ff"
        NEW_BASIS_COLOR = "#f78166"
        VECTOR_COLOR = "#ffd166"
        GRID_COLOR = "#2d333b"
        TEXT_COLOR = "#e6edf3"
        HIGHLIGHT_COLOR = "#7ee787"
        
        # ===== 场景1: hook (同一个向量) =====
        # 标准网格
        grid_standard = NumberPlane(
            x_range=[-5, 5, 1],
            y_range=[-5, 5, 1],
            background_line_style={"stroke_color": GRID_COLOR, "stroke_width": 1},
            axis_config={"stroke_color": GRID_COLOR, "stroke_width": 2},
        )
        
        # 目标向量 v = (2, 1)
        vector_v = Arrow(
            start=ORIGIN, 
            end=np.array([2, 1, 0]),
            color=VECTOR_COLOR,
            buff=0,
            stroke_width=6,
            max_tip_length_to_length_ratio=0.15
        )
        
        # 问题文字
        text_question = Text("同一个向量？", color=TEXT_COLOR, font_size=48)
        text_question.to_corner(UL)
        
        # 播放hook场景
        self.play(Create(grid_standard), run_time=1.5)
        self.wait(0.5)
        self.play(Create(vector_v), run_time=1.5)
        self.wait(0.5)
        self.play(vector_v.animate.set_color(HIGHLIGHT_COLOR), run_time=1.0)
        self.play(vector_v.animate.set_color(VECTOR_COLOR), run_time=0.5)
        self.play(Write(text_question), run_time=1.5)
        self.wait(2)
        
        # ===== 场景2: setup (两个坐标系) =====
        # 新基向量 b1 = (1.5, 0.5), b2 = (-0.5, 1.5) (斜网格)
        new_basis_matrix = np.array([[1.5, -0.5], [0.5, 1.5]])
        
        # 新网格（斜网格）
        grid_new = NumberPlane(
            x_range=[-5, 5, 1],
            y_range=[-5, 5, 1],
            background_line_style={"stroke_color": NEW_BASIS_COLOR, "stroke_width": 1, "stroke_opacity": 0.5},
            axis_config={"stroke_color": NEW_BASIS_COLOR, "stroke_width": 2},
        )
        grid_new.apply_matrix(new_basis_matrix)
        
        # 叠加显示向量（保持原样，因为它在标准基下）
        vector_v_dual = Arrow(
            start=ORIGIN, 
            end=np.array([2, 1, 0]),
            color=VECTOR_COLOR,
            buff=0,
            stroke_width=6,
            max_tip_length_to_length_ratio=0.15
        )
        
        # 坐标标签
        label_coords = Text(
            "标准基: (2,1)    新基: (1.2, 0.8)", 
            color=TEXT_COLOR, 
            font_size=36
        )
        label_coords.to_corner(DR)
        
        # 播放setup场景
        self.play(Create(grid_new), run_time=2)
        self.wait(0.5)
        self.play(Transform(vector_v, vector_v_dual), run_time=1.5)
        self.play(Write(label_coords), run_time=1.5)
        self.play(label_coords.animate.set_color(HIGHLIGHT_COLOR), run_time=1.0)
        self.wait(3)
        self.play(label_coords.animate.set_color(TEXT_COLOR), run_time=0.5)
        
        # ===== 场景3: exploration (基变换矩阵) =====
        # 标准基向量
        e1 = Arrow(
            start=ORIGIN, end=np.array([1, 0, 0]),
            color=STANDARD_BASIS_COLOR, buff=0, stroke_width=5,
            max_tip_length_to_length_ratio=0.15
        )
        e2 = Arrow(
            start=ORIGIN, end=np.array([0, 1, 0]),
            color=STANDARD_BASIS_COLOR, buff=0, stroke_width=5,
            max_tip_length_to_length_ratio=0.15
        )
        basis_standard = VGroup(e1, e2)
        
        # 新基向量（目标位置）
        b1 = Arrow(
            start=ORIGIN, end=np.array([1.5, 0.5, 0]),
            color=NEW_BASIS_COLOR, buff=0, stroke_width=5,
            max_tip_length_to_length_ratio=0.15
        )
        b2 = Arrow(
            start=ORIGIN, end=np.array([-0.5, 1.5, 0]),
            color=NEW_BASIS_COLOR, buff=0, stroke_width=5,
            max_tip_length_to_length_ratio=0.15
        )
        basis_new = VGroup(b1, b2)
        
        # 矩阵表达式（用简单的几何图形代替，避免复杂公式）
        matrix_rect = Rectangle(
            width=3.5, height=1.8, 
            color=HIGHLIGHT_COLOR, stroke_width=3
        )
        matrix_bracket_left = Text("[", color=HIGHLIGHT_COLOR, font_size=60)
        matrix_bracket_right = Text("]", color=HIGHLIGHT_COLOR, font_size=60)
        matrix_content = Text(
            "B = [b1 b2]",
            color=HIGHLIGHT_COLOR, font_size=30
        )
        matrix_expression = VGroup(
            matrix_bracket_left, matrix_content, matrix_bracket_right
        ).arrange(RIGHT, buff=0.1)
        matrix_expression.scale(0.8)
        matrix_expression.to_corner(UL)
        
        # 淡出setup场景的网格
        self.play(
            FadeOut(grid_new),
            FadeOut(label_coords),
            FadeOut(vector_v),
            run_time=1.5
        )
        
        # 创建标准基
        self.play(
            Create(e1),
            Create(e2),
            run_time=1.5
        )
        self.wait(0.5)
        
        # 标准基变换为新基（旋转和拉伸）
        self.play(
            Transform(e1, b1),
            Transform(e2, b2),
            run_time=3
        )
        self.wait(0.5)
        
        # 显示矩阵表达式
        self.play(Write(matrix_expression), run_time=1.5)
        self.play(matrix_expression.animate.set_color(HIGHLIGHT_COLOR), run_time=1.5)
        self.wait(3)
        
        # ===== 场景4: recap (核心回顾) =====
        # 最终展示同一个向量
        vector_final = Arrow(
            start=ORIGIN, 
            end=np.array([2, 1, 0]),
            color=VECTOR_COLOR,
            buff=0,
            stroke_width=6,
            max_tip_length_to_length_ratio=0.15
        )
        
        # 总结文字
        summary_text = Text(
            "向量不变，坐标随基变\n基变换矩阵 = 坐标转换器",
            color=HIGHLIGHT_COLOR, 
            font_size=36,
            line_spacing=1.5
        )
        summary_text.to_edge(DOWN, buff=1)
        
        # 淡出exploration场景
        self.play(
            FadeOut(e1),
            FadeOut(e2),
            FadeOut(matrix_expression),
            run_time=1.5
        )
        
        # 创建最终向量
        self.play(Create(vector_final), run_time=1.5)
        self.wait(0.5)
        
        # 显示总结
        self.play(Write(summary_text), run_time=2)
        self.wait(3)
        
        # 淡出总结
        self.play(FadeOut(summary_text), run_time=1)
        self.wait(1)
        
        # 保持最终画面
        self.wait(2)

# 运行方式: manim -pql 文件名.py BasisChangeScene
```