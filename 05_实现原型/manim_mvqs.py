# -*- coding: utf-8 -*-
"""manim_mvqs.py — MVQS 几何质量评估（§3.111 ⭐ R5 顶尖化）

基于 SGA（arXiv 2607.18116）的 MVQS（Manim Visual Quality Score）方法：
- **无需渲染**（6-18x 快于渲染+VLM 评估）
- 三维加权：Overlap avoidance（避免重叠）/ Relation consistency（关系一致）/
  Boundary validity（边界合法）
- 通过 AST 分析 Manim 代码的几何操作（定位/缩放/颜色）推断空间布局

与现有 manim_geometric_audit（渲染后像素分析）互补：
- MVQS：渲染前代码级快速检查（快，可早期拦截）
- geometric_audit：渲染后像素级兜底（准，最终确认）
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List


# ─────────────────────────────────────
# AST 几何信息抽取（代码级空间布局推断）
# ─────────────────────────────────────
def _extract_geometry_ops(code: str) -> Dict[str, List[Dict[str, Any]]]:
    """抽取代码中的几何操作（定位/缩放/平移/创建）。"""
    ops = {"creations": [], "positions": [], "scales": [], "shifts": []}
    if not code:
        return ops
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ops
    for node in ast.walk(tree):
        # 创建对象（Circle/Square/Text/MathTex 等）
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name in ("Circle", "Square", "Rectangle", "Line", "Arrow",
                        "Text", "MathTex", "Tex", "Dot", "Polygon", "Axes",
                        "VGroup", "Group", "NumberPlane", "Triangle"):
                ops["creations"].append({"type": name, "line": node.lineno})
        # 平移（mobject.shift(...)）
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "shift" and node.args:
            ops["shifts"].append({"line": node.lineno})
        # 缩放（mobject.scale(...)）
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "scale" and node.args:
            try:
                v = ast.literal_eval(node.args[0])
                ops["scales"].append({"value": v, "line": node.lineno})
            except Exception:
                ops["scales"].append({"value": None, "line": node.lineno})
        # 定位（mobject.move_to(...) / next_to(...)）
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("move_to", "next_to", "align_to"):
            ops["positions"].append({"op": node.func.attr, "line": node.lineno})
    return ops


# ─────────────────────────────────────
# MVQS 三维评分
# ─────────────────────────────────────
def _score_overlap_avoidance(ops: Dict[str, List]) -> float:
    """维度 1：避免重叠。
    - 创建对象多但无定位操作 → 可能重叠（低分）
    - 有 move_to/next_to 定位 → 良好（高分）
    """
    creations = len(ops["creations"])
    if creations == 0:
        return 0.8  # 无对象不评估
    positioned = len(ops["positions"])
    # 定位覆盖率：至少 50% 对象应有定位
    coverage = positioned / max(creations, 1)
    if coverage >= 0.5:
        return 0.9
    if coverage >= 0.25:
        return 0.6
    return 0.3


def _score_relation_consistency(ops: Dict[str, List]) -> float:
    """维度 2：对象关系一致。
    - 使用 next_to/align_to（相对定位）→ 关系明确（高分）
    - 只 move_to（绝对定位）→ 关系弱（中分）
    - 无定位 → 关系不明（低分）
    """
    positions = ops["positions"]
    if not positions:
        return 0.4
    relative = sum(1 for p in positions if p["op"] == "next_to")
    if relative >= 1:
        return 0.9
    return 0.6


def _score_boundary_validity(ops: Dict[str, List]) -> float:
    """维度 3：边界合法（对象不越界）。
    - 异常缩放（>10 或 <0.1）→ 可能越界（低分）
    - 大量平移无缩放 → 可能移出边界（中分）
    """
    scales = ops["scales"]
    shifts = ops["shifts"]
    score = 0.8
    for s in scales:
        v = s.get("value")
        if v is not None and (v > 10 or (v > 0 and v < 0.1)):
            score -= 0.3  # 异常缩放
    if len(shifts) > len(ops["creations"]) * 2:
        score -= 0.2  # 过多平移可能越界
    return max(0.2, min(1.0, score))


def mvqs_score(code: str) -> Dict[str, Any]:
    """MVQS 综合评估（无需渲染）。

    Returns:
        {overlap, relation, boundary, mvqs, verdict, issues}
        mvqs: 0-1 加权综合（overlap 0.4 + relation 0.3 + boundary 0.3）
        verdict: PASS（≥0.6）/ WARN（≥0.4）/ FAIL（<0.4）
    """
    ops = _extract_geometry_ops(code)
    overlap = _score_overlap_avoidance(ops)
    relation = _score_relation_consistency(ops)
    boundary = _score_boundary_validity(ops)
    mvqs = round(0.4 * overlap + 0.3 * relation + 0.3 * boundary, 3)

    issues = []
    if overlap < 0.5:
        issues.append("对象可能重叠——创建对象后缺少定位（move_to/next_to）")
    if relation < 0.5:
        issues.append("对象关系不明——建议用 next_to/align_to 建立相对位置")
    if boundary < 0.5:
        issues.append("存在异常缩放/过多平移——对象可能越界")

    if mvqs >= 0.6:
        verdict = "PASS"
    elif mvqs >= 0.4:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "overlap": round(overlap, 3),
        "relation": round(relation, 3),
        "boundary": round(boundary, 3),
        "mvqs": mvqs,
        "verdict": verdict,
        "issues": issues,
        "creations_count": len(ops["creations"]),
        "positions_count": len(ops["positions"]),
    }


def build_mvqs_feedback(code: str) -> str:
    """MVQS 反馈（供 RITL prompt 注入）。"""
    r = mvqs_score(code)
    if r["verdict"] == "PASS":
        return ""
    lines = [f"## MVQS 几何评估（§3.111 R5）：{r['verdict']}（mvqs={r['mvqs']}）"]
    lines.append(f"- overlap={r['overlap']} relation={r['relation']} boundary={r['boundary']}")
    for i in r["issues"]:
        lines.append(f"- ⚠ {i}")
    lines.append("请调整对象定位/缩放，避免重叠与越界（用 next_to/move_to/scale）。")
    return "\n".join(lines)


# 兼容别名（geometric_audit 命名）
audit_code = mvqs_score


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    # 良好代码
    good = '''
class Demo(Scene):
    def construct(self):
        c = Circle().move_to(LEFT)
        s = Square().next_to(c, RIGHT)
        t = Text("x").next_to(s, UP)
        self.play(Create(c), Create(s))
'''
    print("良好代码 MVQS:", mvqs_score(good)["verdict"], mvqs_score(good)["mvqs"])
    # 差代码（无定位）
    bad = '''
class Demo(Scene):
    def construct(self):
        a = Circle()
        b = Square()
        c = Text("x")
        d = Dot()
        self.add(a, b, c, d)
'''
    r = mvqs_score(bad)
    print("差代码 MVQS:", r["verdict"], r["mvqs"], "issues:", len(r["issues"]))
