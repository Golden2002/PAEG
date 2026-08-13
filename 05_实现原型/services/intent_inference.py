# -*- coding: utf-8 -*-
"""短指令补全层（v0.66 ⭐ 用户核心需求）

用户不会给完整完美提示词，通常短句式提问（"极限""行列式""做个PPT"）。
本模块把少信息输入 → 自动推断完整参数（学段/学科/深度/目标/时长）→
生成完整 prompt，产出完善回答。产出末尾附"假设清单"（可被用户一键修正）。

Oracle 调研：PEAR 框架 / 澄清预算（不反问，一次给完整）/ Khanmigo 会话推断。
"""
from __future__ import annotations

from typing import Dict, Optional

# ── 默认值表（可被用户输入覆盖）──────────────────────
_DEFAULTS = {
    "grade": "high_school",       # 高中（高三优先，最常用）
    "depth": "medium",            # 中等（定义+性质+例题+易错）
    "duration_min": 10,           # 讲义/视频默认 10 分钟
    "handout_chars": "约 1500 字",
    "style": "苏格拉底式引导 + 板书感",
}

# 输入 → 覆盖迹象
_GRADE_HINTS = {
    "小学|小升初": "middle_school", "初中|中考|初二|初三|初一": "middle_school",
    "高一|高二|高三|高考": "high_school", "大学|本科|考研|研究生": "graduate_exam",
    "考研|研究生|硕士": "graduate_exam",
}
_DEPTH_HINTS = {
    "入门|基础|简单|浅": "basic", "深入|高级|详细|进阶": "advanced",
    "简略|大纲|概述": "brief",
}
_DURATION_HINTS = {"短|3分钟|5分钟": 5, "长|20分钟|半小时": 20, "10分钟": 10}

# 学科推断（关键词 → 学科）
_SUBJECT_KEYWORDS = {
    "数学": ["极限", "函数", "导数", "积分", "矩阵", "行列式", "向量", "概率",
             "方程", "几何", "代数", "三角", "微积分", "线性代数", "统计", "集合"],
    "物理": ["力", "速度", "加速度", "电场", "磁场", "力学", "能量", "动量",
             "波动", "光学", "热学", "牛顿"],
    "化学": ["化学", "分子", "反应", "元素", "酸碱", "氧化", "方程式"],
    "生物": ["细胞", "基因", "遗传", "光合", "生态", "进化"],
    "语文": ["文言文", "古诗", "修辞", "作文", "拼音", "成语"],
    "英语": ["英语", "语法", "单词", "时态", "从句", "音标"],
    "历史": ["历史", "朝代", "战争", "革命", "古代", "近代"],
    "政治": ["政治", "经济", "哲学", "法律", "道德"],
    "地理": ["地理", "气候", "地形", "板块", "洋流", "经纬"],
}


def infer_context(query: str, explicit_grade: str = "",
                  explicit_subject: str = "") -> Dict:
    """短指令 → 完整推断上下文。

    Args:
        query: 用户原始输入（可能很短，如"极限"）
        explicit_grade/subject: 前端已选的学段/学科（覆盖推断）
    Returns:
        {topic, grade, subject, depth, duration_min, assumptions[]}
    """
    q = (query or "").strip()
    topic = q

    # 1. 学段推断
    grade = explicit_grade or _DEFAULTS["grade"]
    _g_assumption = f"假设学段为{grade}"
    for hint, g in _GRADE_HINTS.items():
        import re as _re
        if _re.search(hint, q):
            grade = g
            _g_assumption = f"从输入'{q}'推断学段为{g}"
            break

    # 2. 学科推断（从关键词）
    subject = explicit_subject or "数学"
    _s_assumption = f"假设学科为{subject}"
    for subj, kws in _SUBJECT_KEYWORDS.items():
        if any(k in q for k in kws):
            subject = subj
            _s_assumption = f"从输入'{q}'推断学科为{subj}"
            break

    # 3. 深度推断
    depth = _DEFAULTS["depth"]
    _d_assumption = f"讲解深度：{depth}"
    for hint, d in _DEPTH_HINTS.items():
        import re as _re
        if _re.search(hint, q):
            depth = d
            _d_assumption = f"从输入推断深度：{d}"
            break

    # 4. 时长推断
    duration = _DEFAULTS["duration_min"]
    for hint, m in _DURATION_HINTS.items():
        import re as _re
        if _re.search(hint, q):
            duration = m
            break

    # 5. 清理主题（去掉"做个/画一下/生成/讲解/的讲义"等指令词）
    for w in ["做个", "画一下", "生成", "讲解", "讲讲", "的讲义", "的大纲",
              "的讲稿", "的视频", "的PPT", "思维导图", "知识导图", "提纲"]:
        topic = topic.replace(w, "").strip()
    if not topic:
        topic = q

    assumptions = [_g_assumption, _s_assumption, _d_assumption,
                   f"目标产出：{depth}深度、约{duration}分钟课堂内容"]
    return {
        "topic": topic, "grade": grade, "subject": subject,
        "depth": depth, "duration_min": duration, "assumptions": assumptions,
    }


def build_assumption_note(ctx: Dict) -> str:
    """生成"假设清单"文本（附在产出末尾，用户可一键修正）。"""
    return ("\n\n---\n"
            f"*我假设你是{ctx['grade']}的{ctx['subject']}学生，需要{ctx['depth']}深度的"
            f"讲解（约{ctx['duration_min']}分钟）。如有偏差请告诉我，我会调整。*")
