# -*- coding: utf-8 -*-
"""PP大纲 5 维评分函数 _score_ppt_outline 测试面（确定性，不依赖 LLM）

5 维评分：
  1. 页数 4-7（硬性，<4 或 >7 记 0 分）
  2. 6×6 法则（每页 ≤6 条要点，每条 ≤60 字）
  3. 单一主题（页间关键词重叠 ≥30%）
  4. 视觉焦点（≥30% 页含 [图]/[表]/[公式] 标记）
  5. 标题 ≤20 字

PPT 大纲结构：list of {page/title/points[]/visual_focus/layout}（LessonPrep 产出）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from subagents import _score_ppt_outline


# -------- 辅助构造 --------

def _page(title, points=None, visual_focus=""):
    """构造一页 PPT 大纲（匹配 LessonPrep ppt_outline 产出格式）。"""
    return {
        "page": 1,
        "title": title,
        "points": list(points) if points else [],
        "visual_focus": visual_focus,
        "layout": "左→右",
    }


# -------- 1. 页数在范围内 --------

def test_page_count_in_range():
    """5 页 → 页数维 1.0。"""
    outline = [_page(f"光合作用 第{i+1}节") for i in range(5)]
    r = _score_ppt_outline(outline)
    assert r["ppt_dim_scores"]["page_count"] == 1.0


# -------- 2. 页数过少 --------

def test_page_count_too_few():
    """3 页 → 页数维 0.0 + violation。"""
    outline = [_page(f"光合作用 第{i+1}节") for i in range(3)]
    r = _score_ppt_outline(outline)
    assert r["ppt_dim_scores"]["page_count"] == 0.0
    assert any(v["dim"] == "页数" for v in r["violations"]), (
        f"violations 应包含 '页数'，实际：{r['violations']}"
    )


# -------- 3. 页数过多 --------

def test_page_count_too_many():
    """8 页 → 页数维 0.0 + violation。"""
    outline = [_page(f"光合作用 第{i+1}节") for i in range(8)]
    r = _score_ppt_outline(outline)
    assert r["ppt_dim_scores"]["page_count"] == 0.0
    assert any(v["dim"] == "页数" for v in r["violations"]), (
        f"violations 应包含 '页数'，实际：{r['violations']}"
    )


# -------- 4. 6×6 法则全部合规 --------

def test_six_six_rule_pass():
    """5 页 × 5 条要点 × 每条 ≤60 字 → 6×6 维 1.0。"""
    outline = []
    for i in range(5):
        points = [f"要点 {j}" for j in range(5)]  # 每页 5 条
        outline.append(_page(f"光合作用 第{i+1}节", points=points))
    r = _score_ppt_outline(outline)
    assert r["ppt_dim_scores"]["six_six_rule"] == 1.0


# -------- 5. 6×6 法则部分违规 --------

def test_six_six_rule_violated():
    """5 页中 1 页 8 条要点 → 6×6 维部分分（介于 0-1）。

    合规度计算：每页要点数 ≤6 → 1；>6 → min(1, 6/len)。
    期望：4 页 × 1.0 + 1 页 × 6/8 = 0.75 → 均值 = (4 + 0.75) / 5 = 0.95
    """
    outline = []
    for i in range(5):
        if i == 0:
            points = [f"要点 {j}" for j in range(8)]  # 违规页
        else:
            points = [f"要点 {j}" for j in range(5)]
        outline.append(_page(f"光合作用 第{i+1}节", points=points))
    r = _score_ppt_outline(outline)
    s = r["ppt_dim_scores"]["six_six_rule"]
    assert 0.0 < s < 1.0, f"期望介于 (0, 1)，实际 {s}"
    assert s == pytest.approx(0.95, abs=0.01), f"期望 0.95，实际 {s}"


# -------- 6. 标题超长 --------

def test_title_length():
    """某页标题 21 字 → 标题维 0.0 + violation（硬性）。"""
    outline = []
    for i in range(5):
        if i == 0:
            title = "光" * 21  # 精确 21 字
        else:
            title = f"光合作用 第{i+1}节"  # 合规
        outline.append(_page(title, points=["要点"]))
    r = _score_ppt_outline(outline)
    assert len(outline[0]["title"]) == 21  # 测试数据自检
    assert r["ppt_dim_scores"]["title_length"] == 0.0
    assert any(v["dim"] == "标题" for v in r["violations"]), (
        f"violations 应包含 '标题'，实际：{r['violations']}"
    )


# -------- 7. 视觉焦点 --------

def test_visual_focus():
    """30% 页含 [图] 标记 → 视觉焦点维 1.0；0% → 0.0。"""
    # 场景 A：5 页中 2 页含 [图]（40% ≥ 30%）→ 1.0
    outline_a = [
        _page(
            f"光合作用 第{i+1}节",
            points=["要点"],
            visual_focus="[图]" if i in (0, 1) else "",
        )
        for i in range(5)
    ]
    r_a = _score_ppt_outline(outline_a)
    assert r_a["ppt_dim_scores"]["visual_focus"] == 1.0

    # 场景 B：所有页都不含视觉标记 → 0.0
    outline_b = [
        _page(f"光合作用 第{i+1}节", points=["要点"], visual_focus="")
        for i in range(5)
    ]
    r_b = _score_ppt_outline(outline_b)
    assert r_b["ppt_dim_scores"]["visual_focus"] == 0.0
    assert any(v["dim"] == "视觉焦点" for v in r_b["violations"])


# -------- 8. 单一主题 --------

def test_single_topic():
    """80% 页标题共享关键词 → 单一主题维 1.0。

    5 页中 4 页（80%）含 "光合作用"；该词覆盖率 = 4/5 = 80% ≥ 30% → 1.0
    """
    outline = []
    for i in range(5):
        if i < 4:
            title = f"光合作用 第{i+1}节"
        else:
            title = "实验验证方法"  # 不共享关键词
        outline.append(_page(title, points=["要点"]))
    r = _score_ppt_outline(outline)
    assert r["ppt_dim_scores"]["single_topic"] == 1.0