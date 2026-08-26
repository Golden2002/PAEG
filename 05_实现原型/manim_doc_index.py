# -*- coding: utf-8 -*-
"""manim_doc_index.py — RITL-DOC 文档增强（§3.111 ⭐ R2 顶尖化）

基于 ManimTrainer（arXiv 2604.18364）RITL-DOC 方法：
- 渲染失败时，用 AST 抽取代码中的 Manim API 调用
- 检索本地 API 签名索引（≤200 最常用 API）
- 只注入签名 + 1 行说明（剔除 Examples——避免 prompt 撑爆）
- 注入到修复 prompt，让 LLM 精确使用正确 API

本地索引无需网络（离线可用）；未来可扩展 Context7 远程回退。
"""

from __future__ import annotations

import ast
import json
import os
import re
from typing import Dict, List, Optional

# ─────────────────────────────────────
# Manim 常用 API 签名索引（≤200，离线）
# 格式：API 名 → {"sig": 签名, "desc": 1 行说明, "example": 用法提示}
# ─────────────────────────────────────
_MANIM_API_INDEX: Dict[str, Dict[str, str]] = {
    # ── Scene 基础 ──
    "Scene": {"sig": "Scene()", "desc": "所有动画的基类，实现 construct(self)",
              "example": "class Demo(Scene):\n    def construct(self): ..."},
    "self.play": {"sig": "self.play(*animations, run_time=1, rate_func=smooth, lag_ratio=0)",
                  "desc": "播放动画（核心方法）",
                  "example": "self.play(Create(circle), run_time=2)"},
    "self.wait": {"sig": "self.wait(duration=1, frozen_frame=True)",
                  "desc": "暂停；frozen_frame=False 让 updater 继续",
                  "example": "self.wait(2)"},
    "self.add": {"sig": "self.add(*mobjects)", "desc": "直接添加对象到场景",
                 "example": "self.add(circle, label)"},
    "self.remove": {"sig": "self.remove(*mobjects)", "desc": "移除对象", "example": ""},
    "self.clear": {"sig": "self.clear()", "desc": "清空场景", "example": ""},

    # ── 几何对象 ──
    "Circle": {"sig": "Circle(radius=1, color=WHITE, fill_opacity=0)",
               "desc": "圆", "example": "Circle(radius=2, color=BLUE)"},
    "Square": {"sig": "Square(side_length=2, color=WHITE)", "desc": "正方形", "example": ""},
    "Rectangle": {"sig": "Rectangle(width=4, height=3, color=WHITE)", "desc": "矩形",
                  "example": ""},
    "Line": {"sig": "Line(start=LEFT, end=RIGHT, color=WHITE)", "desc": "线段",
             "example": "Line(ORIGIN, UP * 3)"},
    "Arrow": {"sig": "Arrow(start=LEFT, end=RIGHT, color=WHITE, stroke_width=3)",
              "desc": "箭头（避免 interpolate_color tip crash——用纯颜色）",
              "example": "Arrow(ORIGIN, RIGHT * 2)"},
    "Vector": {"sig": "Vector(direction, color=YELLOW)", "desc": "向量箭头",
               "example": "Vector([2, 1, 0])"},
    "Axes": {"sig": "Axes(x_range=[-5,5,1], y_range=[-3,3,1], axis_config=...)",
             "desc": "坐标轴", "example": "Axes(x_range=[-5,5,1], y_range=[-3,3,1])"},
    "NumberPlane": {"sig": "NumberPlane(x_range=[-5,5,1], y_range=[-3,3,1])",
                    "desc": "数字平面（网格）", "example": ""},
    "Polygon": {"sig": "Polygon(*vertices, color=WHITE)", "desc": "多边形",
                "example": "Polygon(LEFT, UP, RIGHT, DOWN)"},
    "Triangle": {"sig": "Triangle(color=WHITE)", "desc": "三角形", "example": ""},
    "Arc": {"sig": "Arc(radius=1, start_angle=0, angle=PI/2, color=WHITE)",
            "desc": "圆弧", "example": ""},
    "Dot": {"sig": "Dot(point=ORIGIN, radius=0.05, color=WHITE)", "desc": "点",
            "example": "Dot(ORIGIN, color=RED)"},
    "Angle": {"sig": "Angle(line1, line2, radius=0.5)", "desc": "角（弧线标注）",
              "example": ""},
    "RightAngle": {"sig": "RightAngle(line1, line2, length=0.5)", "desc": "直角标记",
                   "example": ""},
    "Brace": {"sig": "Brace(mobject, direction=DOWN, buff=0.2)",
              "desc": "大括号（不要用 get_text(font_size=)——会崩溃，用 put_at_tip）",
              "example": "b = Brace(line, DOWN); label = Tex('x'); b.put_at_tip(label)"},
    "Grid": {"sig": "Grid(rows=6, columns=6, height=6, width=6)", "desc": "网格",
             "example": ""},
    "CoordinateSystem": {"sig": "CoordinateSystem()", "desc": "坐标系基类", "example": ""},

    # ── 文本/公式 ──
    "Text": {"sig": "Text(text, color=WHITE, font_size=48)",
             "desc": "文本（用 Write 而非 Create 动画）",
             "example": "Text('Hello', color=YELLOW)"},
    "MathTex": {"sig": "MathTex('x^2', color=WHITE)",
                "desc": "数学公式（不要带 $——用 {{ }} 分组）",
                "example": "MathTex('x^2 + y^2 = z^2')"},
    "Tex": {"sig": "Tex('\\\\text{...}', color=WHITE)",
            "desc": "LaTeX 文本（无 LaTeX 环境时降级为 Text）",
            "example": "Tex('x^2')"},
    "Title": {"sig": "Title(text, include_underline=True)", "desc": "标题",
              "example": "Title('Introduction')"},
    "Paragraph": {"sig": "Paragraph(*texts, alignment='center')", "desc": "多段文本",
                  "example": ""},
    "DecimalNumber": {"sig": "DecimalNumber(number, num_decimal_places=2)",
                      "desc": "数值（配合 always_redraw 实时更新）",
                      "example": "DecimalNumber(3.14).add_updater(lambda m: m.set_value(x))"},

    # ── 组合 ──
    "VGroup": {"sig": "VGroup(*mobjects)", "desc": "垂直组合（.animate 只能用于 self.play 内）",
               "example": "VGroup(circle, square)"},
    "HGroup": {"sig": "HGroup(*mobjects)", "desc": "水平组合", "example": ""},
    "Group": {"sig": "Group(*mobjects)", "desc": "组合（子对象相对定位）", "example": ""},

    # ── 动画 ──
    "Create": {"sig": "Create(mobject)", "desc": "描边创建（只用于几何图形，Text 用 Write）",
               "example": "Create(Circle())"},
    "Write": {"sig": "Write(text_or_mobject)", "desc": "书写文本/公式（Create 的 Text 替代）",
              "example": "Write(Text('Hello'))"},
    "FadeIn": {"sig": "FadeIn(mobject)", "desc": "淡入", "example": "FadeIn(circle)"},
    "FadeOut": {"sig": "FadeOut(mobject)", "desc": "淡出", "example": ""},
    "Transform": {"sig": "Transform(mobject, target)",
                  "desc": "变换（保留原对象；若需替换用 ReplacementTransform）",
                  "example": ""},
    "ReplacementTransform": {"sig": "ReplacementTransform(source, target)",
                             "desc": "替换变换（原对象消失，目标对象获得身份）",
                             "example": "ReplacementTransform(square, circle)"},
    "TransformMatchingTex": {"sig": "TransformMatchingTex(source, target)",
                             "desc": "公式逐项匹配变换（渐进披露核心）",
                             "example": "TransformMatchingTex(eq1, eq2)"},
    "TransformMatchingShapes": {"sig": "TransformMatchingShapes(source, target)",
                                "desc": "形状匹配变换", "example": ""},
    "MoveToTarget": {"sig": "mobject.move_to_target()", "desc": "移到 target 位置", "example": ""},
    "Rotate": {"sig": "Rotate(mobject, angle)", "desc": "旋转", "example": "Rotate(t, PI/2)"},
    "Scale": {"sig": "mobject.scale(factor)", "desc": "缩放", "example": ""},
    "Shift": {"sig": "mobject.shift(vector)", "desc": "平移", "example": "c.shift(UP)"},
    "LaggedStart": {"sig": "LaggedStart(*animations, lag_ratio=0.2, run_time=1.5)",
                    "desc": "依次播放（替代 LaggedStartMap(Write, group) 崩溃）",
                    "example": "LaggedStart(*[Write(m) for m in group])"},
    "LaggedStartMap": {"sig": "LaggedStartMap(animation, mobject, ...)",
                       "desc": "⚠ 对 Write 会崩溃——用 LaggedStart",
                       "example": ""},
    "AnimationGroup": {"sig": "AnimationGroup(*animations)", "desc": "动画组", "example": ""},
    "Succession": {"sig": "Succession(*animations)", "desc": "串行动画", "example": ""},
    "Indicate": {"sig": "Indicate(mobject)", "desc": "高亮强调", "example": ""},
    "Flash": {"sig": "Flash(point)", "desc": "闪烁", "example": ""},
    "Circumscribe": {"sig": "Circumscribe(mobject)", "desc": "圈出强调", "example": ""},
    "ApplyWave": {"sig": "ApplyWave(mobject)", "desc": "波动", "example": ""},
    "Uncreate": {"sig": "Uncreate(mobject)", "desc": "逆向描边", "example": ""},

    # ── 定位/变换 ──
    "always_redraw": {"sig": "always_redraw(func)", "desc": "每帧重绘（实时数值）",
                      "example": "num = always_redraw(lambda: DecimalNumber(x))"},
    "move_to": {"sig": "mobject.move_to(point)", "desc": "移动到点", "example": ""},
    "next_to": {"sig": "mobject.next_to(reference, direction, buff=0.2)",
                "desc": "紧邻放置", "example": "label.next_to(circle, UP)"},
    "align_to": {"sig": "mobject.align_to(reference, direction)", "desc": "对齐", "example": ""},
    "shift": {"sig": "mobject.shift(vector)", "desc": "平移", "example": ""},
    "scale": {"sig": "mobject.scale(factor)", "desc": "缩放", "example": ""},
    "rotate": {"sig": "mobject.rotate(angle)", "desc": "旋转", "example": ""},
    "set_color": {"sig": "mobject.set_color(color)", "desc": "设置颜色", "example": ""},
    "set_fill": {"sig": "mobject.set_fill(color, opacity)", "desc": "填充", "example": ""},
    "set_stroke": {"sig": "mobject.set_stroke(color, width)", "desc": "描边", "example": ""},
    "copy": {"sig": "mobject.copy()", "desc": "复制（避免共享引用 bug）",
             "example": "ref = circle.copy()"},
    "get_center": {"sig": "mobject.get_center()", "desc": "中心点", "example": ""},
    "get_top": {"sig": "mobject.get_top()", "desc": "顶部点", "example": ""},
    "get_bottom": {"sig": "mobject.get_bottom()", "desc": "底部点", "example": ""},
    "get_left": {"sig": "mobject.get_left()", "desc": "左端点", "example": ""},
    "get_right": {"sig": "mobject.get_right()", "desc": "右端点", "example": ""},
    "get_vertices": {"sig": "mobject.get_vertices()", "desc": "顶点列表", "example": ""},
    "get_part_by_tex": {"sig": "eq.get_part_by_tex('x')",
                        "desc": "按 tex 取部分（可能返回 None——用 {{ }} 记号）",
                        "example": "part = eq.get_part_by_tex('x')\nif part: part.set_color(RED)"},

    # ── 数学工具 ──
    "ValueTracker": {"sig": "ValueTracker(value)",
                     "desc": "数值跟踪器（双表示联动）",
                     "example": "vt = ValueTracker(0); num.add_updater(lambda m: m.set_value(vt.get_value()))"},
    "Vector": {"sig": "Vector(direction)", "desc": "向量", "example": ""},
    "Matrix": {"sig": "Matrix(matrix)", "desc": "矩阵显示", "example": "Matrix([[1,2],[3,4]])"},
    "FunctionGraph": {"sig": "FunctionGraph(function, x_range=[-5,5], color=WHITE)",
                      "desc": "函数图像", "example": "FunctionGraph(lambda x: np.sin(x))"},
    "ParametricFunction": {"sig": "ParametricFunction(function, t_range=[0,TAU])",
                           "desc": "参数曲线", "example": ""},
    "ImplicitFunction": {"sig": "ImplicitFunction(func)", "desc": "隐函数曲线", "example": ""},
    "NumberLine": {"sig": "NumberLine(x_range=[-5,5,1], include_numbers=True)",
                   "desc": "数轴", "example": ""},

    # ── 颜色/样式 ──
    "interpolate_color": {"sig": "interpolate_color(c1, c2, alpha)",
                          "desc": "颜色插值（传 ManimColor 对象，非 hex 字符串）",
                          "example": "interpolate_color(BLUE, RED, 0.5)"},
    "ManimColor": {"sig": "ManimColor('#FF0000')",
                   "desc": "颜色包装（hex 字符串 → 颜色对象）",
                   "example": "ManimColor('#FF0000')"},
    "WHITE": {"sig": "WHITE", "desc": "白色", "example": ""},
    "YELLOW": {"sig": "YELLOW", "desc": "黄色（3B1B 主色）", "example": ""},
    "BLUE": {"sig": "BLUE", "desc": "蓝色", "example": ""},
    "RED": {"sig": "RED", "desc": "红色", "example": ""},
    "GREEN": {"sig": "GREEN", "desc": "绿色", "example": ""},
    "ORANGE": {"sig": "ORANGE", "desc": "橙色", "example": ""},
    "PURPLE": {"sig": "PURPLE", "desc": "紫色", "example": ""},

    # ── 常量 ──
    "ORIGIN": {"sig": "ORIGIN = [0, 0, 0]", "desc": "原点", "example": ""},
    "UP": {"sig": "UP = [0, 1, 0]", "desc": "上", "example": ""},
    "DOWN": {"sig": "DOWN = [0, -1, 0]", "desc": "下", "example": ""},
    "LEFT": {"sig": "LEFT = [-1, 0, 0]", "desc": "左", "example": ""},
    "RIGHT": {"sig": "RIGHT = [1, 0, 0]", "desc": "右", "example": ""},
    "PI": {"sig": "PI = 3.14159...", "desc": "圆周率", "example": ""},
    "TAU": {"sig": "TAU = 2*PI", "desc": "2π", "example": ""},
    "DEGREES": {"sig": "DEGREES", "desc": "角度转换", "example": ""},
}


def get_api_doc(api_name: str) -> Optional[Dict[str, str]]:
    """查 API 文档。"""
    return _MANIM_API_INDEX.get(api_name)


def extract_manim_apis(code: str) -> List[str]:
    """AST 抽取代码中的 Manim API 调用（RITL-DOC 核心）。

    抽取：函数调用（Create/Transform/...）+ 属性方法（self.play/self.wait/...）。
    """
    if not code:
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    apis = []
    for node in ast.walk(tree):
        # 函数调用：Create(...) / Transform(...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _MANIM_API_INDEX:
                apis.append(node.func.id)
        # 属性调用：self.play(...) / circle.set_color(...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _MANIM_API_INDEX:
                apis.append(node.func.attr)
    return list(dict.fromkeys(apis))  # 去重保序


def build_doc_block(code: str, max_apis: int = 12) -> str:
    """RITL-DOC：AST 抽 API → 只注入签名 + 1 行说明（剔除 Examples）。

    返回可注入 prompt 的文档块；无命中返回空。
    """
    apis = extract_manim_apis(code)
    if not apis:
        return ""
    lines = ["## Manim API 参考（精确签名，请按此使用）"]
    for api in apis[:max_apis]:
        doc = _MANIM_API_INDEX.get(api)
        if doc:
            sig = doc.get("sig", "")
            desc = doc.get("desc", "")
            lines.append(f"- **{api}**: `{sig}` — {desc}")
    return "\n".join(lines)


def build_ritl_doc_prompt(code: str, error: str) -> str:
    """RITL-DOC 完整反馈：错误 tail + API 文档注入（供 LLM 修复）。"""
    from manim_pipeline import _extract_error_tail, _classify_error
    tail = _extract_error_tail(error)
    cls = _classify_error(error)
    doc = build_doc_block(code)
    parts = [f"渲染失败（类型: {cls}）：\n{tail}"]
    if doc:
        parts.append(doc)
    if cls == "latex":
        parts.append("提示：LaTeX 不可用——用 Text() 替代 MathTex()/Tex()。")
    parts.append("请修复代码（保持功能，修正 API 用法）。输出完整代码。")
    return "\n\n".join(parts)


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _code = "self.play(Create(Text('hi')), run_time=2)\nself.wait(1)"
    print("抽取 API:", extract_manim_apis(_code))
    print("\n文档块:")
    print(build_doc_block(_code))
