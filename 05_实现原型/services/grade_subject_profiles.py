# -*- coding: utf-8 -*-
"""services/grade_subject_profiles.py —— §3.43 P0-2/3/4 ⭐ 学段学科 profile 模块（v1.1.5）

Oracle 诊断（§3.43 Step 1.6）：考研学科缺分键、缺收尾问题模板分流、
缺学科×学段深度阶梯。独立模块实现（避免 prompts.py 大文件低效编辑），
build_presenter_system 通过注入钩子消费。

内容：
- KOREAN_EXAM_STYLES：考研学科考点解剖风格（politics_exam/math_exam）
- KOREAN_EXAM_ALIASES：考研学科别名映射
- CLOSING_QUESTIONS：4 学段收尾问题模板
- SUBJECT_GRADE_DEPTH：5 学科 × 4 学段深度阶梯（20 条）
- inject_grade_profiles(system, subject, grade)：注入钩子
"""
from __future__ import annotations

from typing import Dict, Tuple


# ─────────────────────────────────────
# P0-2：考研学科考点解剖风格
# ─────────────────────────────────────
KOREAN_EXAM_STYLES: Dict[str, str] = {
    "politics_exam": (
        "考研政治·考点解剖：考什么→怎么考→套路→真题→易错点。"
        "按考点定位（近10年考频），给出得分要点与答题模板，标注⏱用时建议。"
    ),
    "math_exam": (
        "考研数学·考点解剖：考什么→怎么考→套路→真题→易错点。"
        "按考点定位（高数/线代/概率），给出解题套路与计算技巧，标注易错点。"
    ),
}

# 考研学科别名（供 subject_detector / 路由使用）
KOREAN_EXAM_ALIASES: Dict[str, str] = {
    "考研政治": "politics_exam",
    "考研数学": "math_exam",
    "考研英语": "college_english",
}


# ─────────────────────────────────────
# P0-3：收尾问题模板（4 学段）
# ─────────────────────────────────────
CLOSING_QUESTIONS: Dict[str, list] = {
    "middle_school": [
        "你能不能用自己的话告诉我，刚才那件事是怎么回事？",
        "今天你在生活里还看到过什么类似的现象？",
    ],
    "high_school": [
        "请尝试做一下这道变式题，看你能不能用到刚才的方法。",
        "请画出这节内容的知识结构图。",
    ],
    "undergraduate": [
        "如果某个条件不满足，这个定理/结论还成立吗？为什么？",
        "这个定理与之前学过的哪个概念有联系？请说明关系。",
    ],
    "graduate_exam": [
        "请说出本考点 3 个易错点。",
        "用 30 秒复述这个考点的解题套路。",
    ],
}


# ─────────────────────────────────────
# P0-4：SUBJECT_GRADE_DEPTH 二维阶梯（5 学科 × 4 学段）
# ─────────────────────────────────────
SUBJECT_GRADE_DEPTH: Dict[Tuple[str, str], dict] = {
    # ── physics ──
    ("physics", "middle_school"): {
        "scope": "课标：力/运动/声/光/热/电基础",
        "avoid_terms": ["拉格朗日", "梯度", "麦克斯韦", "薛定谔", "相对论"],
        "must_terms": ["力", "速度", "能量", "电路"],
        "depth_examples": ["用锅盖跳动讲能量", "用滑梯讲摩擦"],
    },
    ("physics", "high_school"): {
        "scope": "高中物理 + 高考",
        "avoid_terms": ["四大力学", "算符", "规范场"],
        "must_terms": ["受力分析", "能量守恒", "动量", "电场"],
        "depth_examples": ["受力分析三步法", "能量守恒链条"],
    },
    ("physics", "undergraduate"): {
        "scope": "普通物理 + 四大力学导论",
        "avoid_terms": [],
        "must_terms": ["守恒律", "对称性", "算符", "严格定义"],
        "depth_examples": ["薛定谔方程升降算符", "麦克斯韦方程组积分形式"],
    },
    ("physics", "graduate_exam"): {
        "scope": "考研物理（普物 + 部分四大力学）",
        "avoid_terms": ["实验设计细节"],
        "must_terms": ["考点", "易错点", "套路"],
        "depth_examples": ["普物常考题型解剖"],
    },
    # ── math ──
    ("math", "middle_school"): {
        "scope": "课标：代数/几何基础",
        "avoid_terms": ["极限", "导数", "积分", "矩阵"],
        "must_terms": ["方程", "函数", "几何"],
        "depth_examples": ["用天平讲方程", "用地图讲比例"],
    },
    ("math", "high_school"): {
        "scope": "高中数学 + 高考",
        "avoid_terms": ["测度", "拓扑", "泛函"],
        "must_terms": ["函数性质", "导数", "圆锥曲线", "数列"],
        "depth_examples": ["导数几何意义", "圆锥曲线联立"],
    },
    ("math", "undergraduate"): {
        "scope": "数学分析 + 线性代数 + 概率统计",
        "avoid_terms": [],
        "must_terms": ["严格证明", "ε-δ", "收敛", "线性空间"],
        "depth_examples": ["ε-δ 证明", "矩阵对角化"],
    },
    ("math", "graduate_exam"): {
        "scope": "考研数学（高数/线代/概率统计）",
        "avoid_terms": ["前沿数学物理"],
        "must_terms": ["考点", "套路", "易错点"],
        "depth_examples": ["二重积分计算套路", "线代大题模板"],
    },
    # ── chemistry ──
    ("chemistry", "middle_school"): {
        "scope": "课标：物质/反应/实验基础",
        "avoid_terms": ["量子化学", "分子轨道", "有机机理"],
        "must_terms": ["元素", "化合价", "化学方程式"],
        "depth_examples": ["用厨房小苏打讲反应", "用生锈讲氧化"],
    },
    ("chemistry", "high_school"): {
        "scope": "高中化学 + 高考",
        "avoid_terms": ["波函数", "前线轨道"],
        "must_terms": ["氧化还原配平", "化学平衡", "有机官能团"],
        "depth_examples": ["氧化还原配平三步骤", "化学平衡移动"],
    },
    ("chemistry", "undergraduate"): {
        "scope": "无机/有机/物化基础",
        "avoid_terms": [],
        "must_terms": ["热力学", "动力学", "分子结构", "光谱"],
        "depth_examples": ["Hess 定律", "阿伦尼乌斯方程"],
    },
    ("chemistry", "graduate_exam"): {
        "scope": "考研化学",
        "avoid_terms": ["实验设计细节"],
        "must_terms": ["考点", "易错点"],
        "depth_examples": ["物化常考题型"],
    },
    # ── biology ──
    ("biology", "middle_school"): {
        "scope": "课标：细胞/生物圈基础",
        "avoid_terms": ["中心法则细节", "基因编辑"],
        "must_terms": ["细胞", "生态", "遗传现象"],
        "depth_examples": ["用花园讲生态", "用家族照片讲遗传"],
    },
    ("biology", "high_school"): {
        "scope": "高中生物 + 高考",
        "avoid_terms": ["基因组学", "表观遗传"],
        "must_terms": ["光合作用", "细胞呼吸", "遗传规律", "中心法则"],
        "depth_examples": ["孟德尔遗传推导", "光合作用过程链"],
    },
    ("biology", "undergraduate"): {
        "scope": "分子/细胞/遗传基础",
        "avoid_terms": [],
        "must_terms": ["DNA 复制", "转录", "翻译", "信号通路"],
        "depth_examples": ["中心法则分子机制", "基因表达调控"],
    },
    ("biology", "graduate_exam"): {
        "scope": "考研生物",
        "avoid_terms": ["实验设计细节"],
        "must_terms": ["考点", "易错点"],
        "depth_examples": ["遗传题常考推导"],
    },
    # ── chinese ──
    ("chinese", "middle_school"): {
        "scope": "课标：阅读/写作基础",
        "avoid_terms": ["文学理论", "叙事学"],
        "must_terms": ["记叙文", "说明文", "修辞"],
        "depth_examples": ["用故事讲记叙文六要素"],
    },
    ("chinese", "high_school"): {
        "scope": "高中语文 + 高考",
        "avoid_terms": ["解构主义", "接受美学"],
        "must_terms": ["文言文", "诗歌鉴赏", "议论文结构"],
        "depth_examples": ["文言实词推断法", "议论文三段式"],
    },
    ("chinese", "undergraduate"): {
        "scope": "大学语文/文学基础",
        "avoid_terms": [],
        "must_terms": ["文学史", "文本分析", "批评方法"],
        "depth_examples": ["叙事结构分析", "意象解读"],
    },
    ("chinese", "graduate_exam"): {
        "scope": "考研语文/文学",
        "avoid_terms": [],
        "must_terms": ["考点", "答题套路"],
        "depth_examples": ["文学史常考脉络"],
    },
}


# ─────────────────────────────────────
# 注入钩子
# ─────────────────────────────────────
def inject_grade_profiles(system: str, subject: str = "", grade: str = "") -> str:
    """注入学段学科 profile（深度阶梯 + 收尾模板）到 system prompt。

    - 深度阶梯：命中 (subject, grade) → 注入 scope/avoid/must
    - 收尾模板：命中 grade → 注入 closing_questions
    - 考研学科：subject 命中别名 → 注入考点解剖风格
    - 无命中 → 原样返回（幂等）
    """
    if not system:
        return system
    parts = []

    # 1. 深度阶梯
    depth = SUBJECT_GRADE_DEPTH.get((subject, grade))
    if depth:
        parts.append(
            f"【学段学科深度 {subject}/{grade}】范围：{depth['scope']}；"
            f"避免术语：{'、'.join(depth['avoid_terms'][:5]) or '无'}；"
            f"必含概念：{'、'.join(depth['must_terms'][:5])}"
        )

    # 2. 收尾模板
    if grade in CLOSING_QUESTIONS:
        qs = CLOSING_QUESTIONS[grade]
        parts.append(f"【收尾提问】讲解结束时，从以下模板选一个问学生：{qs[0]} / {qs[1]}")

    # 3. 考研学科风格
    if subject in KOREAN_EXAM_STYLES:
        parts.append(f"【考研风格】{KOREAN_EXAM_STYLES[subject]}")

    if not parts:
        return system
    if "【学段学科深度" in system:
        return system  # 幂等：已注入
    return system.rstrip() + "\n\n" + "\n".join(parts)


__all__ = ["KOREAN_EXAM_STYLES", "KOREAN_EXAM_ALIASES", "CLOSING_QUESTIONS",
           "SUBJECT_GRADE_DEPTH", "inject_grade_profiles"]
