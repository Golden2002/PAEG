# -*- coding: utf-8 -*-
"""services/grade_quality_gate.py —— §3.79 ⭐ 学段特征输出守门（Round 9 · 内容输出质量）

背景：Round 8 学段×学科质量验证发现——接线层 4/4 全过（GRADE_SCAFFOLDS +
SUBJECT_GRADE_DEPTH + method_guide 均注入 system），但**输出层 LLM 遵循度参差**
（考研样本 0/3：考点/题型/易错字样缺失）。

本模块实现"输出特征守门"：对每步教学输出做确定性学段特征检查，缺失时生成
补充段落追加（一次轻量 LLM 调用，最多 1 轮；失败静默降级，不改原内容）。

  - check_grade_features(content, grade) -> {missing, passed, matched}
  - build_refine_prompt(content, grade, missing, subject, concept)
  - refine_for_grade(llm, content, grade, missing, subject, concept) -> 补充文本或 ""

学段特征表（对应 GRADE_SCAFFOLDS 段名 + 用户需求）：
  初中：生活化 / 可视化 / 复述引导
  高中：定义公式 / 例题 / 误区
  大学：严格定义 / 定理证明 / 推导 / 应用 / 学科视野（lecture 式）
  考研：考点定位 / 题型套路 / 真题示范 / 易错得分
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List

# 学段 → 特征 → 判定正则（宽松，防误伤）
_GRADE_FEATURES: Dict[str, Dict[str, str]] = {
    "middle_school": {
        "生活化": r"例子|比如|生活|感觉|看得见|现象",
        "可视化": r"图|示意|画面|数轴|表",
        "复述引导": r"复述|自己的话|说说|回顾",
    },
    "high_school": {
        "定义公式": r"定义|概念|公式|定理|方程",
        "例题": r"例题|例子|示范",
        "误区": r"误区|常见错误|反例|注意|易错",
    },
    "undergraduate": {
        "严格定义": r"定义|严格",
        "定理证明": r"定理|证明|推导",
        "应用": r"应用|实际|场景",
        "学科视野": r"学科|历史|拓展|联系|前沿",
    },
    "graduate_exam": {
        "考点定位": r"考点|考什么|必考|频次",
        "题型套路": r"题型|套路|方法|步骤|变式",
        "真题示范": r"真题|示范|【",
        "易错得分": r"易错|踩分|得分|考场",
    },
}

_GATE_DEFAULT = os.environ.get("PAEG_GRADE_GATE", "1") != "0"  # 默认开启

# §3.79 Round 11 ⭐ 内容深度四要素（教学输出强化，借鉴张宇扬课件质量特征：
# 精确概念定义 → 机制解释 → 具体例子 → 小结/衔接）
_DEPTH_FEATURES: Dict[str, str] = {
    "定义": r"定义|概念|是指|称为|指的是",
    "机制": r"为什么|原理|机制|因为|本质|推导",
    "例子": r"例子|例如|比如|实例|案例|例题|生活",
    "小结": r"小结|总结|回顾|总之|因此|所以",
}
_DEPTH_MIN: int = 3  # 四要素命中 ≥3 视为达标（宽松防误伤）


def _normalize_grade(grade: str) -> str:
    _g = str(grade or "high_school").strip()
    return _g if _g in _GRADE_FEATURES else "high_school"


def check_grade_features(content: Any, grade: str) -> Dict[str, Any]:
    """学段特征确定性检查（无 LLM）。

    Returns: {"missing": [feature...], "passed": bool, "matched": {...}, "grade": 归一学段}
    """
    text = str(content or "")
    _g = _normalize_grade(grade)
    _matched: Dict[str, bool] = {}
    _missing: List[str] = []
    for _fname, _pat in _GRADE_FEATURES[_g].items():
        _hit = bool(re.search(_pat, text))
        _matched[_fname] = _hit
        if not _hit:
            _missing.append(_fname)
    return {"missing": _missing, "passed": not _missing,
            "matched": _matched, "grade": _g}


def build_refine_prompt(content: Any, grade: str, missing: List[str],
                        subject: str = "", concept: str = "") -> str:
    """构造补充段生成提示词（一次性，要求：不重复、衔接自然、按学段风格）。"""
    _g = _normalize_grade(grade)
    _labels = {
        "middle_school": "初中（生活化、直观、可复述）",
        "high_school": "高中（定义公式、例题、误区提醒）",
        "undergraduate": "大学本科 lecture 式（严格定义、定理证明、推导、应用、学科视野）",
        "graduate_exam": "考研（考点定位、题型套路、真题示范、易错得分）",
    }
    return (
        f"你是 {_labels.get(_g, _g)} 的学科老师。\n"
        f"学科：{subject or '未知'}；主题：{concept or '当前概念'}。\n"
        "刚才的讲解缺少以下学段特征，请**只补充缺失部分**（≤200 字，Markdown，"
        "不重复已有内容，自然衔接在原文之后）：\n"
        f"- 缺失：{'、'.join(missing)}\n"
        "输出：直接给补充段落文本，不要解释。"
    )


# ─────────────────────────────────────
# §3.79 Round 11 ⭐ 内容深度四要素守门（教学输出强化）
# ─────────────────────────────────────
def check_content_depth(content: Any, grade: str) -> Dict[str, Any]:
    """内容深度四要素检查（定义/机制/例子/小结；≥3 达标）。

    借鉴张宇扬课件质量特征：精确概念定义 → 机制解释 → 具体例子 → 小结衔接。
    对高中/大学/考研学段启用（初中以生活化为主，由 grade 特征守门覆盖）。

    Returns: {"missing": [...], "passed": bool, "matched": {...}, "grade": 归一学段}
    """
    text = str(content or "")
    _g = _normalize_grade(grade)
    _matched: Dict[str, bool] = {}
    _missing: List[str] = []
    for _fname, _pat in _DEPTH_FEATURES.items():
        _hit = bool(re.search(_pat, text))
        _matched[_fname] = _hit
        if not _hit:
            _missing.append(_fname)
    return {
        "missing": _missing,
        "passed": (len(_matched) - len(_missing)) >= _DEPTH_MIN,
        "matched": _matched,
        "grade": _g,
    }


def refine_content_depth(llm, content: Any, missing: List[str],
                         subject: str = "", concept: str = "") -> str:
    """深度四要素缺失 → 补充（一次轻量调用，失败降级 ""）。"""
    if not missing:
        return ""
    try:
        from subagents import _safe_chat
        _sys = ("你是 PAEG 的内容深度补充器。只输出补充段落，不解释、不重复，"
                "用通俗语言把缺失要素补上（≤180 字）。")
        _usr = (
            f"学科：{subject or '未知'}；主题：{concept or '当前概念'}。\n"
            f"现有讲解：{str(content)[:400]}\n"
            f"请补充以下要素：{'、'.join(missing)}\n"
            "输出：直接给补充段落文本。"
        )
        _raw = _safe_chat(llm, _sys, _usr, max_tokens=380)
        _txt = str(_raw or "").strip()
        return ("\n\n" + _txt) if len(_txt) >= 20 else ""
    except Exception:
        return ""


def refine_for_grade(llm, content: Any, grade: str, missing: List[str],
                     subject: str = "", concept: str = "") -> str:
    """缺特征 → 生成补充段（一次轻量调用；失败/超时返回 ""，静默降级）。"""
    if not missing:
        return ""
    try:
        _usr = build_refine_prompt(content, grade, missing, subject, concept)
        from subagents import _safe_chat
        _sys = ("你是 PAEG 的学段特征补充器。只输出补充段落，不解释、不重复。")
        _raw = _safe_chat(llm, _sys, _usr, max_tokens=400)
        _txt = str(_raw or "").strip()
        if len(_txt) < 20:
            return ""
        return "\n\n" + _txt
    except Exception:
        return ""


__all__ = ["check_grade_features", "build_refine_prompt", "refine_for_grade",
           "_GRADE_FEATURES", "_GATE_DEFAULT"]
