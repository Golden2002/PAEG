# -*- coding: utf-8 -*-
"""
PAEG Agent Steering — 学科自动识别层（v0.19.26 ⭐）

问题：用户手动设定学科（如"考研政治"）后，若问题属于另一个学科（如经济学），
agent 会用原设定回答——steering 能力不足。

本模块让 Agent 自动判断问题的学科：
1. 判断问题是否属于学科性内容（还是寒暄/闲聊/元问题）
2. 若属于，从 PAEG 26 个学科清单中选择最匹配的学科
3. 识别的学科 ≠ 用户设定 → 覆盖用户设定（steering 切换）
4. 问题明显属于某学科但不在清单（如量子力学/心理学）→ 返回 unknown:<学科名>
   → server 记录到自我更新日志 + 向用户反馈"后续优化升级"

设计原则：
- LLM 判断（规则无法覆盖"考研政治设定下问经济学"这种语义场景）
- 缓存同一问题 10 分钟（教学场景重复提问常见）
- 失败安全默认：保持用户设定（不打断正常教学）
"""

from __future__ import annotations

import re
import time
from typing import Optional

# 26 个学科清单（与 prompts.SUBJECT_STYLES 同步）
SUBJECT_CATALOG = [
    "physics", "math", "literature", "ethics", "phenomenology",
    "chemistry", "biology", "geography", "chinese", "politics",
    "law", "economics", "history", "english", "french",
    "german", "japanese", "philosophy", "aesthetics",
    "kaoyan_math", "kaoyan_politics", "writing", "coding",
    "thinking", "learning", "expression", "linguistics", "atmospheric_science", "qft",
]

# 缓存：question -> (subject_or_unknown, timestamp)
_CACHE = {}
_CACHE_TTL = 600  # 10 分钟


def _clear_cache():
    _CACHE.clear()


def detect_subject(text: str, llm=None, user_subject: str = "", grade: str = "") -> dict:
    """判断问题的学科归属。

    返回 {"subject": str|None, "unknown": bool, "unknown_name": str|None,
          "reason": str, "switched": bool}
    - subject: 识别的学科 key（在 27 清单内）
    - unknown=True: 问题明显属某学科但不在清单（如"量子力学"）
    - unknown_name: 未收录学科的中文名
    - switched: 识别学科 ≠ 用户设定（需要 steering 切换）
    - v0.25: grade 参数做学段-学科联动——识别到的学科若高于当前学段（如高中生问语言学），
      视为"未收录/暂不开放"，避免跨学段教学。
    """
    t = (text or "").strip()
    if not t or len(t) > 150:
        # 过长输入不做学科识别（保持用户设定）
        return {"subject": None, "unknown": False, "unknown_name": None,
                "reason": "输入过长，不做识别", "switched": False}

    # 缓存（v0.25: key 含 grade，避免跨学段串结果）
    now = time.time()
    _ckey = (t, grade)
    if _ckey in _CACHE and now - _CACHE[_ckey][1] < _CACHE_TTL:
        cached = _CACHE[_ckey][0]
        return _finalize(cached, user_subject)

    result = {"subject": None, "unknown": False, "unknown_name": None, "reason": "",
              "grade_blocked": False}
    if llm is not None:
        result = _llm_detect(t, llm)
    # v0.25 学段-学科联动：识别学科高于当前学段 → 降级为 unknown（该学段暂不开放）
    if result.get("subject") and grade:
        try:
            from prompts import SUBJECT_MIN_GRADE, _GRADE_ORDER
            min_g = SUBJECT_MIN_GRADE.get(result["subject"])
            if min_g and min_g != "graduate_exam" and _GRADE_ORDER.get(grade, 1) < _GRADE_ORDER.get(min_g, 2):
                _cn = result.get("subject")
                result["unknown"] = True
                result["grade_blocked"] = True
                result["unknown_name"] = {
                    "linguistics": "语言学", "atmospheric_science": "大气科学",
                    "phenomenology": "生命现象学", "aesthetics": "美学",
                }.get(_cn, _cn)
                result["grade_name"] = {
                    "middle_school": "初中", "high_school": "高中",
                    "undergraduate": "大学本科", "graduate_exam": "考研",
                }.get(min_g, min_g)
                result["subject"] = None
                result["reason"] = f"学科 {_cn} 需 {min_g} 及以上学段"
        except Exception:
            pass
    _CACHE[_ckey] = (result, now)
    return _finalize(result, user_subject)


def _finalize(result: dict, user_subject: str) -> dict:
    """补充 switched 判断。"""
    subj = result.get("subject")
    result["switched"] = bool(subj and subj != user_subject and not result.get("unknown"))
    return result


def _llm_detect(text: str, llm) -> dict:
    """LLM 判断学科。"""
    try:
        from subagents import _safe_chat
        catalog = "、".join(SUBJECT_CATALOG)
        system = (
            "你是学科识别器。判断学生这句话属于哪个学科。\n"
            "规则：\n"
            "1. 如果是寒暄/闲聊/元问题/非学科内容（如'你好''今天天气''你是谁'），输出 {\"subject\": \"none\"}\n"
            "2. 如果属于下列学科之一，输出 {\"subject\": \"对应key\"}："
            f"{catalog}\n"
            "注意：热力学、统计物理、玻尔兹曼熵、电磁学都属于 physics；"
            "线性代数、微积分、概率论都属于 math；"
            "无机化学、有机化学都属于 chemistry。\n"
            "3. 如果明显属于某个学科但不在清单（如量子力学、心理学、计算机科学、医学），"
            "输出 {\"subject\": \"unknown\", \"unknown_name\": \"该学科中文名\"}\n"
            "只输出 JSON，不要多余文字。"
        )
        user = f"学生说：{text}"
        r = _safe_chat(llm, system, user, max_tokens=80)
        if r:
            import json as _json
            m = re.search(r'\{.*\}', r, re.S)
            if m:
                parsed = _json.loads(m.group(0))
                s = parsed.get("subject", "none")
                if s == "none" or not s:
                    return {"subject": None, "unknown": False, "unknown_name": None,
                            "reason": "非学科内容"}
                if s == "unknown":
                    return {"subject": None, "unknown": True,
                            "unknown_name": parsed.get("unknown_name", "该学科"),
                            "reason": f"未收录学科: {parsed.get('unknown_name', '')}"}
                if s in SUBJECT_CATALOG:
                    return {"subject": s, "unknown": False, "unknown_name": None,
                            "reason": f"识别为 {s}"}
    except Exception:
        pass
    return {"subject": None, "unknown": False, "unknown_name": None,
            "reason": "识别失败（保持用户设定）"}


# 轻量规则兜底：明显学科关键词（LLM 不可用时）
_KNOWN_KEYWORDS = {
    "physics": ["物理", "力学", "电磁", "量子", "相对论", "牛顿",
                "热力学", "熵", "玻尔兹曼", "统计物理", "热学", "热传导",
                "能量守恒", "熵增", "卡诺", "热机", "温度", "内能"],
    "math": ["数学", "导数", "积分", "方程", "函数", "几何", "代数", "概率", "矩阵"],
    "chemistry": ["化学", "分子", "反应", "元素", "酸碱"],
    "biology": ["生物", "细胞", "基因", "进化", "生态"],
    "geography": ["地理", "气候", "板块", "地形"],
    "economics": ["经济", "供需", "价格", "市场", "GDP", "通货膨胀", "机会成本"],
    "law": ["法律", "法条", "合同", "刑法", "民法", "宪法"],
    "history": ["历史", "朝代", "战争", "革命", "古代"],
    "philosophy": ["哲学", "存在", "意识", "伦理", "形而上学"],
    "politics": ["政治", "政策", "制度", "国家", "选举", "阶级"],
    "coding": ["编程", "代码", "算法", "python", "程序", "bug"],
    "english": ["英语", "单词", "语法", "vocabulary", "grammar"],
}


def rule_detect(text: str) -> Optional[str]:
    """规则兜底：命中关键词返回学科 key（无 LLM 时用）。"""
    t = (text or "").lower()
    scores = {}
    for subj, kws in _KNOWN_KEYWORDS.items():
        n = sum(1 for kw in kws if kw in t)
        if n:
            scores[subj] = n
    if not scores:
        return None
    return max(scores, key=scores.get)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    # 无 LLM 规则测试
    tests = ["什么是供需曲线", "如何求导", "量子力学是什么", "刑法第几条", "今天天气如何"]
    for t in tests:
        r = rule_detect(t)
        print(f'[{t}] 规则识别: {r}')
