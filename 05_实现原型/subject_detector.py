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
    "german", "japanese", "philosophy", "aesthetics", "writing", "coding",
    "thinking", "learning", "expression", "linguistics", "atmospheric_science",
    "electronics", "computer_science", "artificial_intelligence",
    "college_chinese", "college_english", "college_politics",
]

# §3.79 Round 12 ⭐ 学科子学科/别名映射（修"量子力学被拒"根因）：
# LLM/规则把子学科判 unknown 的根因是缺少层级映射——量子力学/热力学/电磁学都是
# physics 的子学科，理应归入 physics 而非拒绝。识别流程：先查映射表命中 → 归入父学科；
# 未命中清单/映射才判 unknown。新增子学科只需在此表登记（教学可覆盖）。
SUBJECT_ALIASES: dict = {
    # physics 子学科/别名
    "physics": ["量子力学", "量子物理", "量子纠缠", "相对论", "电磁学", "电动力学",
                "热力学", "统计物理", "光学", "声学", "力学", "流体力学", "原子物理",
                "核物理", "粒子物理", "理论物理", "凝聚态", "天体物理", "宇宙学",
                "玻尔兹曼熵", "薛定谔", "麦克斯韦", "狭义相对论", "广义相对论"],
    # math 子学科/别名
    "math": ["微积分", "线性代数", "概率论", "数理统计", "离散数学", "数论", "实变函数",
             "复变函数", "泛函分析", "常微分方程", "偏微分方程", "拓扑学", "抽象代数",
             "近世代数", "解析几何", "高等数学", "数学分析"],
    # chemistry 子学科
    "chemistry": ["无机化学", "有机化学", "物理化学", "分析化学", "高分子化学",
                  "生物化学", "量子化学", "结构化学"],
    # biology 子学科
    "biology": ["分子生物学", "细胞生物学", "遗传学", "进化生物学", "生态学",
                "微生物学", "植物学", "动物学", "神经科学", "生物信息学",
                "发育生物学", "生物化学与分子生物学"],
    # computer_science 子学科
    "computer_science": ["数据结构", "操作系统", "计算机网络", "编译原理",
                         "算法设计", "数据库", "计算机组成原理", "软件工程",
                         "并行计算", "分布式系统", "密码学", "形式语言"],
    # economics 子学科
    "economics": ["微观经济学", "宏观经济学", "计量经济学", "国际经济学",
                  "发展经济学", "劳动经济学", "金融学", "货币银行学", "财政学"],
    # psychology 归入 thinking？——不，心理学是独立学科，无父学科 → 仍 unknown
    #   但若未来收录，加入 SUBJECT_CATALOG 即可；此处仅登记物理/数学等已收录父学科
    # law 子学科
    "law": ["民法", "刑法", "宪法", "行政法", "商法", "经济法", "国际法",
            "诉讼法", "法理学", "知识产权法"],
    # history 子学科
    "history": ["中国古代史", "中国近代史", "世界史", "二战史", "中世纪史",
                "考古学", "史料学"],
    # geography 子学科
    "geography": ["自然地理", "人文地理", "经济地理", "气象学", "气候学",
                  "地貌学", "水文地理"],
    # politics 子学科
    "politics": ["政治学理论", "国际关系", "比较政治", "公共政策", "行政管理"],
    # english 子学科
    "english": ["英语语法", "英语词汇", "英语阅读", "英语写作", "英语听力",
                "雅思", "托福", "四六级", "考研英语"],
    # philosophy 子学科
    "philosophy": ["西方哲学", "中国哲学", "逻辑学", "伦理学", "美学",
                   "认识论", "形而上学", "科学哲学", "政治哲学", "现象学"],
    # linguistics 子学科
    "linguistics": ["语音学", "音系学", "形态学", "句法学", "语义学", "语用学",
                    "社会语言学", "心理语言学", "计算语言学"],
    # electronics 子学科
    "electronics": ["模拟电路", "数字电路", "信号与系统", "通信原理",
                    "半导体物理", "微电子", "集成电路"],
    # artificial_intelligence 子学科
    "artificial_intelligence": ["机器学习", "深度学习", "自然语言处理", "计算机视觉",
                                "强化学习", "大语言模型", "知识图谱", "数据挖掘"],
    # atmospheric_science 子学科
    "atmospheric_science": ["气象学", "气候学", "大气物理", "天气学", "台风", "大气污染"],
}

# 反向索引：子学科名 -> 父学科 key（_llm_detect/rule_detect 共用）
_SUBJECT_ALIAS_INDEX: dict = {}
for _parent, _aliases in SUBJECT_ALIASES.items():
    for _a in _aliases:
        _SUBJECT_ALIAS_INDEX[_a] = _parent


def lookup_alias(name: str) -> Optional[str]:
    """子学科/别名 → 父学科 key；未命中返回 None。"""
    if not name:
        return None
    return _SUBJECT_ALIAS_INDEX.get(str(name).strip())

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
        # §3.79 Round 12 ⭐ 元能力铁律（L918）：**LLM 先判断，规则只兜底**——
        # 语义判断（量子力学属于物理学等子学科归属）必须交给 LLM 在选项内分类；
        # 规则不得覆盖 LLM 已作出的判断（此前规则/别名表无条件覆盖 → 规则成了主判断）。
        result = _llm_detect(t, llm)
        # LLM 判定 unknown 时二次查别名表：LLM 语义识别失败/漏判子学科才映射
        # （仍是 LLM 主判断的轻量修正，非规则抢先）
        if result.get("unknown"):
            _un = str(result.get("unknown_name") or "").strip()
            _alias_parent = lookup_alias(_un) if _un else None
            if _alias_parent:
                result = {"subject": _alias_parent, "unknown": False,
                          "unknown_name": None,
                          "reason": f"LLM 判 {_un} → 子学科映射 {_alias_parent}",
                          "grade_blocked": False}
    else:
        # llm=None（离线/无 key）：规则兜底是唯一路径（确定性降级，非主判断）
        _rule_subj = rule_detect(t) or _alias_detect(t)
        if _rule_subj:
            result = {"subject": _rule_subj, "unknown": False, "unknown_name": None,
                      "reason": f"规则兜底识别为 {_rule_subj}", "grade_blocked": False}
    # v0.25→v0.26 学段-学科联动：识别学科在当前学段不可用 → 降级为 unknown
    if result.get("subject") and grade:
        try:
            from prompts import SUBJECT_GRADES, SUBJECT_MIN_GRADE, _GRADE_ORDER, subject_available_for_grade
            # v0.26：优先用多学段集合判断；未定义回退最低学段
            available = subject_available_for_grade(result["subject"], grade)
            if not available:
                _cn = result.get("subject")
                grades = SUBJECT_GRADES.get(_cn)
                min_g = SUBJECT_MIN_GRADE.get(_cn)
                # 需要的最低学段（用于提示"需切换到哪一档"）
                need_grade = grades[0] if grades and grades[0] != "graduate_exam" else (min_g or "undergraduate")
                result["unknown"] = True
                result["grade_blocked"] = True
                result["unknown_name"] = {
                    "linguistics": "语言学", "atmospheric_science": "大气科学",
                    "phenomenology": "生命现象学", "aesthetics": "美学",
                    "electronics": "电子科学与技术", "computer_science": "计算机科学",
                    "artificial_intelligence": "人工智能",
                }.get(_cn, _cn)
                result["grade_name"] = {
                    "middle_school": "初中", "high_school": "高中",
                    "undergraduate": "大学本科", "graduate_exam": "考研",
                }.get(need_grade, need_grade)
                # v0.41.9 ⭐ 修复：保留 subject（不清 None）+ 加 required_grade——
                # 此前清 None → _finalize 的 switched 判断失效 → 自动切换学段不生效
                result["required_grade"] = need_grade
                result["reason"] = f"学科 {_cn} 需 {need_grade} 及以上学段"
        except Exception:
            pass
    _CACHE[_ckey] = (result, now)
    return _finalize(result, user_subject)


def _finalize(result: dict, user_subject: str) -> dict:
    """补充 switched 判断。v0.41.9 ⭐ grade_blocked 时也置 switched（检测到需切学段）。"""
    subj = result.get("subject")
    result["switched"] = bool(subj and subj != user_subject) and (
        not result.get("unknown") or bool(result.get("required_grade")))
    return result


def _llm_detect(text: str, llm) -> dict:
    """LLM 判断学科（§3.79 Round 12 ⭐ LLM 主判断、规则兜底）。

    设计（元能力 L918 铁律）：学科归属是语义判断，由 LLM 在选项内分类。
    子学科→父学科映射（量子力学→physics 等）作为 LLM 分类知识注入 prompt，
    **不是**代码规则替代——LLM 完全有能力判断"量子力学是物理学的一部分"。
    仅当 LLM 不可用（llm=None）时走规则兜底（detect_subject 的 else 分支）。
    """
    try:
        from subagents import _safe_chat
        catalog = "、".join(SUBJECT_CATALOG)
        # §3.79 Round 12 ⭐ 子学科归属写入 LLM 分类规则（LLM 语义判断的选项知识）：
        # 让 LLM 直接把子学科归入父学科（physics/math/...），而非判 unknown。
        # 不逐条枚举（避免 prompt 过长），给出代表性子学科 + "等一切该学科的子领域"
        # 的开放性指引——LLM 靠语义能力判断归属（如"量子纠缠"明显是物理）。
        system = (
            "你是学科识别器。判断学生这句话属于哪个学科。\n"
            "规则：\n"
            "1. 如果是寒暄/闲聊/元问题/非学科内容（如'你好''今天天气''你是谁'），输出 {\"subject\": \"none\"}\n"
            "2. 如果属于下列学科之一，输出 {\"subject\": \"对应key\"}："
            f"{catalog}\n"
            "子学科归属（用语义判断，不限于下列例子）：\n"
            "- physics：量子力学、量子纠缠、相对论、电磁学、热力学、统计物理、光学、力学、"
            "原子核物理、凝聚态物理等一切物理子领域\n"
            "- math：微积分、线性代数、概率论、数论、离散数学、实变函数、拓扑学等一切数学子领域\n"
            "- chemistry：无机化学、有机化学、物理化学、分析化学等一切化学子领域\n"
            "- biology：分子生物学、遗传学、神经科学、生态学、微生物学等一切生物子领域\n"
            "- computer_science：数据结构、操作系统、计算机网络、算法设计等一切计算机子领域\n"
            "- economics：微观/宏观/计量经济学、金融学、货币银行学等一切经济子领域\n"
            "- law：民法、刑法、宪法、商法等一切法学子领域\n"
            "- history：中国古代史、世界史、考古学等一切历史子领域\n"
            "- 其他学科同理：其公认的子领域归属该学科\n"
            "3. 如果确实不属于任何已列学科及其子领域（如心理学、医学、建筑学、音乐学），"
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
                    # LLM 语义识别子学科名 → 由 detect_subject 二次查别名表归入父学科
                    return {"subject": None, "unknown": True,
                            "unknown_name": str(parsed.get("unknown_name", "") or "").strip()
                            or "该学科",
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
    "biology": ["生物", "细胞", "基因", "进化", "生态", "遗传", "神经"],
    "geography": ["地理", "气候", "板块", "地形"],
    "economics": ["经济", "供需", "价格", "市场", "GDP", "通货膨胀", "机会成本"],
    "law": ["法律", "法条", "合同", "刑法", "民法", "宪法"],
    "history": ["历史", "朝代", "战争", "革命", "古代"],
    "philosophy": ["哲学", "存在", "意识", "伦理", "形而上学"],
    "politics": ["政治", "政策", "制度", "国家", "选举", "阶级"],
    "coding": ["编程", "代码", "算法", "python", "程序", "bug", "计算机基础"],
    "english": ["英语", "单词", "语法", "vocabulary", "grammar"],
    # v0.26 ⭐ 补全：新学科/拆键学科关键词（审计修复）
    "chinese": ["语文", "古诗", "文言文", "作文", "阅读", "拼音", "汉字"],
    "literature": ["文学", "小说", "散文", "诗歌", "名著", "莎士比亚", "文学史"],
    "ethics": ["道德", "伦理", "孝", "诚信", "价值观"],
    "aesthetics": ["美学", "审美", "艺术鉴赏", "美"],
    "french": ["法语", "français", "bonjour"],
    "german": ["德语", "deutsch", "hallo"],
    "japanese": ["日语", "五十音", "假名", "こんにちは"],
    "thinking": ["批判性思维", "思辨", "逻辑", "推理", "思维方法"],
    "learning": ["学习法", "学习方法", "费曼", "记忆", "专注力", "高效学习"],
    "expression": ["演讲", "表达", "口才", "公众表达", "沟通"],
    "writing": ["写作", "议论文", "作文技巧", "论证"],
    "linguistics": ["语言学", "音位", "形态学", "句法", "语义", "语用", "语言"],
    "atmospheric_science": ["大气", "气象", "台风", "气候", "天气", "臭氧"],
    "electronics": ["电路", "电子", "MOS", "集成电路", "半导体", "KVL", "放大器"],
    "computer_science": ["计算机", "数据结构", "操作系统", "算法复杂度", "递归", "编译", "网络协议", "数据库"],
    "artificial_intelligence": ["人工智能", "机器学习", "深度学习", "神经网络", "Transformer", "大模型", "RAG", "强化学习", "AI"],
    "college_chinese": ["大学语文"],
    "college_english": ["大学英语", "学术英语", "四级", "六级"],
    "college_politics": ["政治学", "政治学理论"],
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


def _alias_detect(text: str) -> Optional[str]:
    """§3.79 Round 12 ⭐ 子学科名直接匹配（量子纠缠/微积分/遗传学 等 → 父学科）。

    LLM 不可用或关键词未覆盖时，若文本中出现别名表子学科名（或其包含词），
    归入对应父学科——修"量子力学被拒"根因的另一层防线。
    """
    t = (text or "").strip()
    if not t:
        return None
    hits = {}
    for _alias, _parent in _SUBJECT_ALIAS_INDEX.items():
        if _alias and _alias in t:
            hits[_parent] = hits.get(_parent, 0) + 1
    if not hits:
        return None
    return max(hits, key=hits.get)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    # 无 LLM 规则测试
    tests = ["什么是供需曲线", "如何求导", "量子力学是什么", "刑法第几条", "今天天气如何"]
    for t in tests:
        r = rule_detect(t)
        print(f'[{t}] 规则识别: {r}')
