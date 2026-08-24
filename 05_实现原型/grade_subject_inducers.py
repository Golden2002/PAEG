# -*- coding: utf-8 -*-
"""grade_subject_inducers.py —— §3.107 学段×学科专属诱导层（提升式更改）

现有结构：SUBJECT_STYLES（36 学科 persona，无学段）+ _GRADE_GUIDE（5 学段深度，独立学科）。
本模块补 **学段×学科组合诱导**——不做破坏式更改，只增加拼接：

    现有拼接（build_presenter_system）:
      SUBJECT_STYLES[subject] persona/structure
      + _GRADE_GUIDE[grade] depth
      + L1 启发式提示词（heuristic_prompts）
      + 学科诱导（subject_inducers）
      + 物料诱导（material_inducers）
      ↓ 新增
      + 学段×学科组合诱导（grade_subject_inducers）——高中/考研/大学×数学/物理/文学等

设计：学段（高中/考研/大学/初中）决定"讲解深度与严谨度"，学科决定"认知侧重"，
组合后得到该场景专属的额外启发式提示词——拼接进现有架构（非破坏）。
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════
# 学段×学科组合诱导（部分高价值组合，可扩展）
# 结构：{grade: {subject: "额外启发式提示词"}}
# ═══════════════════════════════════════════════════════════
GRADE_SUBJECT_INDUCERS = {
    "high_school": {
        "math": "【高中数学诱导】在直觉之上建立严谨：先具体例子（数列/函数）建立直觉，再给定义与公式推导；"
                "强调高考考点映射（题型/易错点）；例题配完整步骤与变式练习。",
        "physics": "【高中物理诱导】现象→受力/能量分析→公式应用：先生活现象，用受力图/能量守恒解释；"
                   "强调高考题型（选择题陷阱/大题步骤）；实验思想渗透。",
        "chinese": "【高中语文诱导】文本细读 + 高考考点：先疏通文意/手法，再落到高考题型（阅读/作文）；"
                   "兼顾素养与应试。",
    },
    "graduate_exam": {
        "math": "【考研数学诱导】重严格推导与综合：直接给定义/定理，强调证明思路与条件边界；"
                "考点定位（高数/线代/概率）+ 题型套路 + 易错点；综合题分解。",
        "physics": "【考研物理诱导】重理论体系与推导：从基本定律出发，推导公式与结论；"
                   "强调数学工具（微积分/矢量）与物理图像的结合；典型题精讲。",
    },
    "undergraduate": {
        "physics": "【大学物理诱导】重严格理论与数学框架：直接进入概念（严格定义/定理/推导），"
                   "强调数学表达（微积分/偏微分/矢量）；联系前沿应用激发兴趣。",
        "literature": "【大学文学诱导】重理论视角与文本批评：先文本细读，再用文学理论（结构主义/叙事学/文化研究）"
                      "分析；强调学术论证（论点-证据-阐释）。",
        "economics": "【大学经济诱导】重模型与机制：直接给理论模型（供需/博弈/宏观），强调假设-推导-结论逻辑；"
                     "用实证案例/政策讨论支撑。",
        "math": "【大学数学诱导】重严格定义与证明：直接进入概念（定义/定理/证明），"
                "强调数学结构（空间/映射/结构）与抽象思维；习题精讲。",
    },
    "middle_school": {
        "math": "【初中数学诱导】重生活化与具象：用具体数字/图形/生活例子建立直觉，"
                "少术语；强调运算基础与常见错误纠正。",
        "chinese": "【初中语文诱导】重基础与兴趣：疏通文意/字词/朗读，激发阅读兴趣；"
                   "简单手法分析 + 情感体验。",
    },
}


def get_grade_subject_inducer(grade: str, subject: str) -> str:
    """按学段×学科取组合诱导（无匹配返回空——不强制）。"""
    return GRADE_SUBJECT_INDUCERS.get(grade, {}).get(subject, "")


def get_grade_subjects(grade: str) -> dict:
    """按学段取可用学科诱导（调试/文档用）。"""
    return GRADE_SUBJECT_INDUCERS.get(grade, {})


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("学段×学科组合诱导层就绪（§3.107 提升式）")
    for g in ["high_school", "graduate_exam", "undergraduate", "middle_school"]:
        subs = get_grade_subjects(g)
        print(f"  {g}: {list(subs.keys())}")
    print()
    print(get_grade_subject_inducer("high_school", "math")[:60])
    print(get_grade_subject_inducer("undergraduate", "literature")[:60])
