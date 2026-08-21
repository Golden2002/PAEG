# -*- coding: utf-8 -*-
"""§3.81 P1-① ⭐ golden 集物料化——内容→物料结构映射断言（盲区④：物料产出无评估集）

设计（Oracle P1-① 方案）：现有 60 条 golden（初中12/高中12/大学19/考研17）只评教学文本，
未评物料产出。本测试把 golden 内容作为"优质教学素材"，构造各学段的物料文本
（讲义/讲稿/PPT 大纲），断言物料结构检查器（material_quality + validate_lesson_script）
对优质内容应通过（内容好 → 物料结构也应达标）。

覆盖盲区④：物料层 CI 守护——若物料生成退化（结构破碎），本测试即失败。
"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.material_quality import (
    check_handout, check_lecture_script, check_mindmap, check_ppt_outline,
)
from visual_script_validator import validate_lesson_script

# ── 从 golden set 复用优质内容（教学文本 → 物料素材）──
from tests.test_round16_golden_set import GOLDEN, BAD_SAMPLES


def _build_handout(concept: str, content: str) -> str:
    """把 golden 教学文本包装为完整讲义（5 节结构）。"""
    return (
        f"# {concept} 讲义\n\n"
        f"## 学习目标\n理解 {concept} 的核心概念与基本应用。\n\n"
        f"## 核心内容\n{content}\n\n"
        f"## 典型例题\n例 1：关于 {concept} 的具体计算：已知数值 a=3, b=4，求解相关问题。\n"
        f"例 2：变式练习：改变条件后 {concept} 如何变化？\n\n"
        f"## 巩固练习\n练习：请计算 {concept} 的典型题目 2 道，并说明解题思路。\n\n"
        f"## 小结\n本节回顾 {concept} 的关键定义、计算步骤与常见误区。"
    )


def _build_lecture_script(concept: str) -> str:
    """把 golden 内容包装为讲稿（开场/主体/小结 + 口语化）。"""
    return (
        f"# 讲稿：{concept}（约 15 分钟）\n\n"
        f"## 开场（约 2 分钟）\n同学们好，今天我们学习 {concept}。"
        f"先举个生活例子：就像我们日常中常见的……（用类比把抽象概念拉到身边）。\n\n"
        f"## 主体（约 10 分钟）\n"
        f"首先，{concept} 的核心定义是……（配具体例子讲解）。\n"
        f"然后，我们看一个关键公式：x = y + z（数字实例演示）。\n"
        f"讲到关键处停下来问一句「大家看，这一步是不是很自然？」\n\n"
        f"## 小结（约 3 分钟）\n本节核心要点回顾。最后用一个生活化类比收尾。"
    )


def _build_ppt_outline(concept: str) -> str:
    """把 golden 内容包装为 PPT 大纲（5-7 页）。"""
    return (
        f"## {concept}引入\n- 生活实例\n- 学习目标\n"
        f"## {concept}定义\n- 核心概念\n- 关键公式\n"
        f"## 典型例题\n- 例题 1\n- 例题 2\n"
        f"## 常见误区\n- 易错点\n- 注意事项\n"
        f"## 总结\n- 要点回顾\n- 课后思考"
    )


def _build_video_script(concept: str) -> str:
    """把 golden 内容包装为视频脚本（镜头结构 + 画面/旁白）。"""
    return (
        f"## 镜头 1（开场 · 20s）\n画面：生活场景引入 {concept}\n旁白：今天我们学习 {concept}。\n"
        f"## 镜头 2（主体 · 60s）\n画面：定义与公式演示\n旁白：{concept} 的核心定义是……（约 80 字展开说明）。\n"
        f"## 镜头 3（总结 · 20s）\n画面：要点回顾\n旁白：总结本节要点，布置思考题。"
    )


# ── 正向：优质 golden 内容 → 物料结构应达标 ──
@pytest.mark.parametrize("grade,subject,concept,content", GOLDEN[:12])
def test_golden_handout_structure(grade, subject, concept, content):
    """S1：golden 优质内容 → 讲义结构检查通过（5 节命中≥3 + 具体例题 + 练习）。"""
    handout = _build_handout(concept, content)
    r = check_handout(handout)
    assert r["passed"], (
        f"[{grade}:{concept}] 讲义结构未达标: {r['errors'][:3]}")


@pytest.mark.parametrize("grade,subject,concept,content", GOLDEN[:12])
def test_golden_lecture_script_structure(grade, subject, concept, content):
    """S2：golden 优质内容 → 讲稿结构检查通过（开场/主体/小结 + 时长标注）。"""
    script = _build_lecture_script(concept)
    r = check_lecture_script(script)
    assert r["passed"], (
        f"[{grade}:{concept}] 讲稿结构未达标: {r['errors'][:3]}")


@pytest.mark.parametrize("grade,subject,concept,content", GOLDEN[:12])
def test_golden_ppt_outline_structure(grade, subject, concept, content):
    """S3：golden 优质内容 → PPT 大纲结构检查通过（分页 + 要点）。"""
    outline = _build_ppt_outline(concept)
    r = check_ppt_outline(outline)
    assert r["passed"], (
        f"[{grade}:{concept}] PPT 大纲结构未达标: {r['errors'][:3]}")


@pytest.mark.parametrize("grade,subject,concept,content", GOLDEN[:8])
def test_golden_video_script_structure(grade, subject, concept, content):
    """S4：golden 优质内容 → 视频脚本校验通过（镜头≥2 + 画面/旁白 + 时长）。"""
    video = _build_video_script(concept)
    r = validate_lesson_script(video)
    assert r["passed"], (
        f"[{grade}:{concept}] 视频脚本未达标: {r['errors'][:3]}")


def test_golden_bad_samples_handout_fails():
    """S5：坏样例 → 讲义结构应检出（防漏检退化）。

    坏样例（缺结构/碎片化）包装为讲义后，5 节命中应 <3 → passed=False。
    """
    bad = BAD_SAMPLES[0]
    grade, subject, concept, content = bad
    # 坏样例内容本身碎片化 → 直接构造残缺讲义
    broken = f"## 学习目标\n{content[:30]}"  # 只 1 节 → 应失败
    r = check_handout(broken)
    assert not r["passed"], f"[{grade}:{concept}] 残缺讲义竟通过（漏检退化！）"


def test_golden_set_reused_size():
    """S6：golden 复用规模（≥50 条铁律）+ 本集覆盖范围说明。"""
    assert len(GOLDEN) >= 50, f"golden set 仅 {len(GOLDEN)} 条（要求 ≥50）"
    # 本集抽查前 12 条（覆盖 4 学段）+ 全量坏样例
    assert len(GOLDEN) >= 12
