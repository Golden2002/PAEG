# -*- coding: utf-8 -*-
"""material_prompts.py —— §3.88 ⭐ 物料结构化提示词模板体系（Oracle 设计）

5 类物料（讲义/PPT/教学视频/数学视频Manim/思维导图）各一套"角色+约束+范例"模板。
简单指令（"生成PPT：光合作用"）→ upgrade_simple_intent 升级为带学科/学段/物料要求的
完整 user prompt → LLM 按 build_material_system 的系统模板产出高质量提纲 → 制作物料。

设计原则（用户要求 + Oracle）：
- 约束是"层"不是"墙"：5 层基础约束（语言/真实/学科persona/学段/约束分级）+ 物料专属硬约束
- 每类物料 5-7 条反模式黑名单（硬约束死线）+ ≥1 段优秀范例（示例 > 规则，启发不限制）
- 动态注入：按 material_type × subject × grade 拼装，不同学科/学段自动适配
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 学科中文名（简易映射，完整在 prompts.py SUBJECT_STYLES）
_SUBJECT_CN = {
    "math": "数学", "physics": "物理", "chemistry": "化学", "biology": "生物",
    "chinese": "语文", "english": "英语", "history": "历史", "geography": "地理",
    "politics": "政治", "computer_science": "计算机", "default": "综合",
}

# 学段中文
_GRADE_CN = {
    "middle_school": "初中", "high_school": "高中",
    "undergraduate": "大学", "graduate_exam": "考研", "default": "高中",
}

# ──────────────── 5 类物料模板（角色 + schema + 硬约束 + 范例） ────────────────
_MATERIAL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "handout": {
        "role": "你是一位有 10 年教龄的{grade_cn}{subject_cn}老师，正在为「{topic}」撰写一份教学讲义。",
        "schema": (
            "输出 Markdown 讲义，结构为章节树，每节含 4 块：【核心概念】【典型例题】【易错点】【小结】。"
            "章节标题用 ##，小节用 ###。"
        ),
        "hard_checks": [
            "不得只有目录而无实质内容（每节必须有讲解文字）",
            "例题必须给出完整解题步骤，不能只有题目",
            "抽象概念必须配生活类比或具体例子",
            "内容必须准确，不得出现科学性错误",
            "语言规范，不得有病句/口语化表述",
        ],
        "exemplar": (
            "### 示例：光合作用讲义·核心概念节\n"
            "**光合作用** = 植物利用光能，把 CO₂ 和水合成有机物（葡萄糖）并释放 O₂ 的过程。\n"
            "类比：植物像一座太阳能工厂——叶子是太阳能板，叶绿体是发电机组，光能把水和空气变成'食物'。\n"
            "✅ 典型例题：光照下植物释放的气体是什么？→ 氧气（来自水的光解，不是 CO₂）。"
        ),
    },
    "ppt": {
        "role": "你是一位 PPT 教学设计师，按「6×6 原则」为{grade_cn}{subject_cn}学生设计「{topic}」演示文稿。",
        "schema": (
            '输出 JSON 数组 pages：每页 {title, points(≤6条), visual_focus(视觉焦点：图/表/公式/流程图), '
            'notes(教师备注)}。要求 6-10 页：封面→目录→3-5 页正文→小结→思考题。'
        ),
        "hard_checks": [
            "单页文字不得超过 6 行（6×6 原则）",
            "每页只能有一个主题，不得堆砌多个概念",
            "文字页必须有视觉焦点（图/表/流程图），不得纯文字",
            "正文页必须有具体例子或数据支撑",
            "不得有科学性错误",
        ],
        "exemplar": (
            '### 示例：牛顿第二定律 PPT 页\n'
            '{"title": "F=ma 的直觉", "points": ["力是改变运动的原因", "质量越大越难推动（惯性）", '
            '"a 与 F 成正比、与 m 成反比"], "visual_focus": "受力分析示意图+公式动画", '
            '"notes": "先用推购物车的生活例子引入，再给公式"}'
        ),
    },
    "video": {
        "role": "你是一位教学视频编剧，按 8-15s 分镜节奏为{grade_cn}{subject_cn}设计「{topic}」教学视频脚本。",
        "schema": (
            '输出 JSON scenes 数组：每 scene {duration_s(8-15), narration(旁白), on_screen(画面内容), '
            'transition(转场)}。总长 60-180s：引入→主体→take-away 结尾。'
        ),
        "hard_checks": [
            "单个镜头不得超过 15 秒（保持节奏）",
            "必须有引入（钩子）和 take-away 结尾，不得突兀开始/结束",
            "旁白必须具体，不得空话套话",
            "画面与旁白必须对应（讲什么就显示什么）",
            "不得有知识性错误",
        ],
        "exemplar": (
            '### 示例：圆面积视频分镜（片段）\n'
            '{"duration_s": 10, "narration": "你有没有想过，为什么圆面积是 πr²？今天我们用切披萨的方法来理解。", '
            '"on_screen": "一个圆被切成 8 块扇形", "transition": "切到切 16 块的动画"}'
        ),
    },
    "manim": {
        "role": "你是一位 Manim 数学动画设计师，强调几何直觉，为{grade_cn}{subject_cn}学生设计「{topic}」的数学可视化动画。",
        "schema": (
            "输出 Manim 动画脚本：先几何直觉（变换/过程可视化），后公式化。"
            "每个元素独立 Create/Write 后 wait，关键步骤留 pause。"
        ),
        "hard_checks": [
            "不得一步到位显示最终结果，必须展示变换过程",
            "公式必须正确，符号规范",
            "动画必须表达概念（非纯文字展示）",
            "关键步骤必须有 pause/等待（教学节奏）",
            "不得有数学错误",
        ],
        "exemplar": (
            "### 示例：导数动画（几何直觉）\n"
            "1. 画抛物线 y=x² 和其上一点 P\n"
            "2. 画经过 P 的割线 → 缓慢移动 Q 靠近 P → 割线变成切线\n"
            "3. 显示斜率标签 f'(x₀) → 说明'导数是切线的斜率'"
        ),
    },
    "mindmap": {
        "role": "你是一位知识结构师，按 3-5 主题层级为{grade_cn}{subject_cn}组织「{topic}」思维导图。",
        "schema": (
            "输出树结构：{root(中心主题), branches[{name, children[], summary}]}。"
            "中心 1 个 + 3-5 个一级分支，每分支 2-4 个二级节点。"
        ),
        "hard_checks": [
            "不得是扁平列表，必须有层级（中心→分支→子节点）",
            "一级分支不超过 5 个（记忆友好）",
            "每个分支必须总结成一句（summary）",
            "节点内容必须准确，逻辑关系清晰",
        ],
        "exemplar": (
            "### 示例：导数思维导图\n"
            "root: 导数\n"
            "branch1 定义: [极限定义, 几何意义(切线斜率)] → summary: 导数是变化率\n"
            "branch2 计算: [基本公式, 运算法则] → summary: 四则运算与常见函数导数"
        ),
    },
}


def _subject_cn(subject: str) -> str:
    return _SUBJECT_CN.get(subject, "综合")


def _grade_cn(grade: str) -> str:
    return _GRADE_CN.get(grade, "高中")


def build_material_system(material_type: str, topic: str, subject: str = "default",
                          grade: str = "high_school", learner=None) -> str:
    """统一装配器：5 层基础约束 + 物料专属角色/schema/硬约束/范例。

    Returns: 系统提示词字符串（供 LLM 生成高质量提纲）。
    """
    tmpl = _MATERIAL_TEMPLATES.get(material_type)
    if not tmpl:
        raise ValueError(f"未知物料类型: {material_type}（支持: {list(_MATERIAL_TEMPLATES.keys())}）")

    # Layer 1-2: 语言层 + 真实底线（从 prompts 复用，缺失则跳过）
    layers = []
    try:
        from prompts import LANGUAGE_STYLE, TRUTH_GROUNDING
        layers.append(LANGUAGE_STYLE)
        layers.append(TRUTH_GROUNDING)
    except Exception:
        pass

    # Layer 3-4: 学科 persona + 学段
    g_cn = _grade_cn(grade)
    s_cn = _subject_cn(subject)
    layers.append(f"教学对象：{g_cn}{s_cn}学生。")

    # Layer 5: 物料专属
    role = tmpl["role"].format(grade_cn=g_cn, subject_cn=s_cn, topic=topic)
    hard = "\n".join(f"- {c}" for c in tmpl["hard_checks"])

    return f"""
{chr(10).join(layers)}

## 物料专属角色
{role}

## 输出 schema
{tmpl['schema']}

## 质量红线（违反任一条请重写）
{hard}

## 优秀范例（启发你的格式与深度，不必照抄）
{tmpl['exemplar']}
"""


def upgrade_simple_intent(topic: str, material_type: str, subject: str = "default",
                          grade: str = "high_school") -> str:
    """简单指令升级器：'生成PPT：光合作用' → 带学科/学段/物料要求的完整 user prompt。

    Returns: 升级后的 user prompt 字符串。
    """
    g_cn = _grade_cn(grade)
    s_cn = _subject_cn(subject)
    parts = [f"主题：{topic}", f"学科：{s_cn}", f"学段：{g_cn}"]
    if material_type == "ppt":
        parts.append("要求：封面+3-6页正文+小结；每页1-2个核心概念，有例子和视觉焦点")
    elif material_type == "video":
        parts.append("要求：60-180秒，按8-15秒分镜，有引入和take-away结尾")
    elif material_type == "manim":
        parts.append("要求：几何直觉优先，展示变换过程，关键步骤暂停")
    elif material_type == "handout":
        parts.append("要求：≥3节，每节含核心概念/例题/易错点/小结")
    elif material_type == "mindmap":
        parts.append("要求：中心+3-5一级分支，每分支2-4二级节点")
    return "\n".join(parts)


if __name__ == "__main__":
    # 冒烟测试
    sys_prompt = build_material_system("ppt", "光合作用", "biology", "middle_school")
    print(f"build_material_system(ppt, 光合作用, biology, 初中): {len(sys_prompt)} 字符")
    print("含角色:", "PPT 教学设计师" in sys_prompt)
    print("含硬约束:", "单页文字不得超过" in sys_prompt)
    print("含范例:", "牛顿第二定律" in sys_prompt)
    print()
    upgraded = upgrade_simple_intent("光合作用", "ppt", "biology", "middle_school")
    print("upgrade_simple_intent 输出:")
    print(upgraded)
