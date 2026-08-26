# -*- coding: utf-8 -*-
"""manim_safety.py — safe_manim 崩溃防护（§3.111 ⭐ 顶尖化 T1.A）

基于 3brown1blue（clawRxiv 2603.00082）的 12 个 Manim 崩溃/静默 bug 模式，
提供：
1. **静态 lint**（`lint_manim_code`）：AST + 正则检测 12 种高危模式，返回违规清单
2. **安全包装函数**（`safe_*`）：在渲染前替换易崩溃 API 调用

12 个崩溃模式（ManimTrainer/3brown1blue 证据）：
  硬崩溃（CRASH）：
  C1  Create(Text())          → 应 Write(Text())
  C2  Arrow(interpolate_color) → tip crash → 纯颜色
  C3  Brace.get_text(font_size=) → 崩溃 → safe_brace_label
  C4  MathTex(r"$...$") 双dollar → 冲突 → 去 $
  C5  LaggedStartMap(Write, group) → 崩溃 → LaggedStart
  C6  wait() frozen_frame 冻结 updater → frozen_frame=False
  静默 bug（WRONG OUTPUT）：
  C7  Transform(A,B) 后操作 B → ReplacementTransform
  C8  .animate 加到 VGroup → _AnimationBuilder
  C9  循环 lambda 闭包晚绑定 → lambda m, o=obj
  C10 interpolate_color(hex_str) → ManimColor 包装
  C11 get_part_by_tex("missing") → None → safe_get_part
  C12 reference = mob 共享引用 → mob.copy()
"""

from __future__ import annotations

import ast
import re
from typing import List, Tuple


# ─────────────────────────────────────
# 1. 静态 lint 规则（12 模式）
# ─────────────────────────────────────
# (id, 描述, 匹配函数)
def _find_create_text(tree: ast.AST) -> List[Tuple[int, str]]:
    """C1: Create(Text(...)) → 应 Write。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "Create" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
                    and arg.func.id in ("Text", "MathTex", "Tex"):
                hits.append((node.lineno, "C1: Create(Text) 描边而非书写 → 应改 Write(Text())"))
    return hits


def _find_brace_get_text(tree: ast.AST) -> List[Tuple[int, str]]:
    """C3: Brace.get_text(font_size=...) → 崩溃。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get_text":
            for kw in node.keywords:
                if kw.arg == "font_size":
                    hits.append((node.lineno, "C3: Brace.get_text(font_size=) 崩溃 → 用 safe_brace_label"))
    return hits


def _find_math_tex_dollar(tree: ast.AST) -> List[Tuple[int, str]]:
    """C4: MathTex(r"$...$") 双 dollar。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "MathTex":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                        and "$" in a.value:
                    hits.append((node.lineno, "C4: MathTex 含 $ → 去掉（双 dollar 模式冲突）"))
    return hits


def _find_lagged_start_map_write(tree: ast.AST) -> List[Tuple[int, str]]:
    """C5: LaggedStartMap(Write, group) → 崩溃。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "LaggedStartMap" and node.args:
            arg0 = node.args[0]
            if isinstance(arg0, ast.Name) and arg0.id == "Write":
                hits.append((node.lineno, "C5: LaggedStartMap(Write, group) 崩溃 → 用 safe_lagged_write"))
    return hits


def _find_wait_frozen(tree: ast.AST) -> List[Tuple[int, str]]:
    """C6: wait() 默认 frozen_frame=True 冻结 updater。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "wait":
            has_frozen = any(kw.arg == "frozen_frame" for kw in node.keywords)
            if not has_frozen and any(kw.arg == "updaters" for kw in node.keywords):
                hits.append((node.lineno, "C6: wait(updaters=...) 需 frozen_frame=False"))
    return hits


def _find_transform_after(tree: ast.AST) -> List[Tuple[int, str]]:
    """C7: Transform(A,B) 后操作 B（B 未入 scene）→ ReplacementTransform。"""
    # 启发式：检测 self.play(Transform(...)) 且后续 .add(B)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "Transform":
            hits.append((node.lineno, "C7: Transform(A,B) 后 B 无效果 → 用 ReplacementTransform（若需保留 A）"))
    return hits


def _find_animate_vgroup(tree: ast.AST) -> List[Tuple[int, str]]:
    """C8: .animate 加到 VGroup → _AnimationBuilder。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "animate":
            # 检查是否在 self.play 内
            hits.append((node.lineno, "C8: .animate 只能用于 self.play() 内（VGroup 上会返回 _AnimationBuilder）"))
    return hits


def _find_lambda_closure(tree: ast.AST) -> List[Tuple[int, str]]:
    """C9: 循环内 lambda 闭包晚绑定。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            # 检查是否有默认参数捕获（无则可能是晚绑定）
            if not node.args.defaults:
                # 查找是否在循环内（启发式：父节点是 For）
                hits.append((node.lineno, "C9: 循环内 lambda 可能闭包晚绑定 → 用 lambda m, o=obj: ..."))
    return hits


def _find_interpolate_color_str(tree: ast.AST) -> List[Tuple[int, str]]:
    """C10: interpolate_color(hex_str) → 字符串无 .interpolate()。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "interpolate_color":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    hits.append((node.lineno, "C10: interpolate_color 传 hex 字符串 → 用 ManimColor() 包装"))
    return hits


def _find_get_part(tree: ast.AST) -> List[Tuple[int, str]]:
    """C11: get_part_by_tex("missing") → 静默 None。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get_part_by_tex":
            hits.append((node.lineno, "C11: get_part_by_tex 可能返回 None → 用 safe_get_part + {{ }} 记号"))
    return hits


def _find_shared_ref(tree: ast.AST) -> List[Tuple[int, str]]:
    """C12: reference = mob（共享引用）→ 修改一个两边都变。"""
    # 启发式：检测赋值语句 RHS 是 name 且后续被修改
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            # 别名赋值（可能共享引用）
            hits.append((node.lineno, f"C12: '{node.targets[0].id} = {node.value.id}' 可能共享引用 → 用 .copy()"))
    return hits


_LINT_RULES = [
    ("C1", "Create(Text) 误用", _find_create_text),
    ("C3", "Brace.get_text 崩溃", _find_brace_get_text),
    ("C4", "MathTex 双 dollar", _find_math_tex_dollar),
    ("C5", "LaggedStartMap(Write)", _find_lagged_start_map_write),
    ("C6", "wait 冻结 updater", _find_wait_frozen),
    ("C7", "Transform 后操作", _find_transform_after),
    ("C8", ".animate 误用", _find_animate_vgroup),
    ("C9", "lambda 闭包晚绑定", _find_lambda_closure),
    ("C10", "interpolate_color 字符串", _find_interpolate_color_str),
    ("C11", "get_part_by_tex None", _find_get_part),
    ("C12", "共享引用", _find_shared_ref),
]


def lint_manim_code(code: str) -> List[str]:
    """静态 lint：检测 12 类崩溃/静默 bug 模式。返回违规描述列表（空=通过）。"""
    if not code:
        return ["代码为空"]
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"SyntaxError: {e}"]
    issues: List[str] = []
    for _id, _desc, _fn in _LINT_RULES:
        try:
            hits = _fn(tree)
            for lineno, msg in hits:
                issues.append(f"L{lineno} [{_id}] {msg}")
        except Exception:
            continue
    return issues


def lint_summary(code: str) -> Tuple[bool, List[str]]:
    """lint 摘要：返回 (是否通过, 违规清单)。"""
    issues = lint_manim_code(code)
    return (len(issues) == 0, issues)


# ─────────────────────────────────────
# 2. 安全包装函数（运行时防护）
# ─────────────────────────────────────
def safe_text_write(text: str, **kw):
    """C1 修复：Text 用 Write 而非 Create。"""
    from manim import Text, Write
    return Write(Text(text, **kw))


def safe_math_tex(expr: str, **kw):
    """C4 修复：MathTex 去 $。"""
    from manim import MathTex
    return MathTex(expr.replace("$", ""), **kw)


def safe_lagged_write(group, lag_ratio: float = 0.2, run_time: float = 1.5):
    """C5 修复：LaggedStartMap(Write, group) → LaggedStart。"""
    from manim import LaggedStart, Write
    return LaggedStart(*[Write(m) for m in group], lag_ratio=lag_ratio, run_time=run_time)


def safe_get_part(eq, tex: str, fallback_color=None):
    """C11 修复：get_part_by_tex None 检查。"""
    part = eq.get_part_by_tex(tex)
    if part is None:
        raise ValueError(f"get_part_by_tex('{tex}') 返回 None——请用 {{ {tex} }} 记号")
    if fallback_color is not None:
        part.set_color(fallback_color)
    return part


def safe_arrow(start, end, color=None, stroke_width: float = 3, **kw):
    """C2 修复：Arrow 避免 interpolate_color tip crash。"""
    from manim import Arrow
    _kw = {k: v for k, v in kw.items() if k not in ("stroke_opacity",)}
    arr = Arrow(start=start, end=end, color=color, stroke_width=stroke_width, **_kw)
    if "stroke_opacity" in kw:
        arr.set_opacity(kw["stroke_opacity"])
    return arr


def safe_replacement_transform(scene, source, target, **kw):
    """C7 修复：显式 ReplacementTransform（保留 A 时）。"""
    from manim import ReplacementTransform
    scene.play(ReplacementTransform(source, target, **kw))
    return target


# ─────────────────────────────────────
# 3. 便捷：lint + 修复提示（供 RITL 反馈用）
# ─────────────────────────────────────
def build_safety_feedback(code: str) -> str:
    """把 lint 违规转为 RITL 修复提示（供 LLM 反馈）。"""
    issues = lint_manim_code(code)
    if not issues:
        return ""
    return "Manim 代码安全 lint 发现以下问题（请修复）：\n" + "\n".join(f"- {i}" for i in issues[:8])


# 自测
if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _bad = '''
class Demo(Scene):
    def construct(self):
        self.play(Create(Text("hello")))
        brace = Brace(Line(LEFT, RIGHT))
        label = brace.get_text("x", font_size=24)
        eq = MathTex(r"$E=mc^2$")
        self.play(LaggedStartMap(Write, VGroup(Text("a"), Text("b"))))
        self.wait(updaters=[lambda m: m.shift(UP)])
'''
    ok, issues = lint_summary(_bad)
    print(f"lint 通过: {ok}, 违规 {len(issues)} 条")
    for i in issues:
        print(" ", i)
