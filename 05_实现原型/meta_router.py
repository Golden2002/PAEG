# -*- coding: utf-8 -*-
"""
PAEG 元问题路由（v0.17.1）

解决幻觉问题：当用户问的是"关于系统自身"的元问题（你是谁、你能做什么、
你能调用知识库吗、你有什么能力）时，模型常常把它当成一个学科概念去教学，
导致答非所问（比如问"你能调用知识库吗"却开始讲美学）。

本模块在进入教学流程前拦截这类问题，用闲聊模式（Émile 的身份与能力）回答。
"""
from __future__ import annotations

import re

# 元问题模式：关于 PAEG 自身身份/能力/机制的问题
META_PATTERNS = [
    # 身份
    r"你是谁|你叫什么|你是什么(东西|人|ai|AI)?$|自我介绍|介绍.*自己",
    r"你为什么叫|你名字.*(意思|来源|为什么)|你的名字",
    # 能力（一般性）
    r"你能(做什么|干什么|干嘛)|你(会|能)做什么|你的能力|你有什么能力",
    r"你有什么(功能|用处|本领)|你会什么|你能帮(我|人)做什么",
    # 知识库（v0.19.21：裸"知识库/资料库"移交给 knowledge 专用检测，这里只拦"调用/查"类动词）
    r"你(有|能)(调用|用|查|找|读|看).*(库|资料)|能不能(调用|查|找).*库",
    r"你能调用.*吗|调用知识库|检索.*知识|有没有知识库|你的知识(库|来源)",
    # 模型/技术
    r"你(是|用).*(模型|大模型|gpt|llm|deepseek|ai)|基于什么(模型|技术)|谁做的|谁开发",
    r"你的(技术|原理|架构|构成|系统)(是|什么样)|你是.*(技术|系统)吗",
    # 工作方式
    r"你怎么(工作|思考|学习|更新|记忆)|你会(记|学|忘|更新)吗|你能记住.*吗",
    r"你会(自我|自己)(更新|进化|学习)吗|你怎么(学习|成长)",
    # 关于对话本身
    r"什么是paeg|paeg是(什么|啥)|pega|这个(系统|网站|软件).*是(什么|谁)",
    r"怎么用你|你(能|会)教(什么|哪些)|教什么学科",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in META_PATTERNS]


# 寒暄/问候（v0.17.2）：用户打招呼时绝不能当学科概念教学
GREETING_PATTERNS = [
    r"^(你好|您好|你们好|大家好|嗨|哈喽|hello|hi|hey|hi~|在吗|在么|早上好|下午好|晚上好|早安|午安|晚安|你好呀|你好啊|您好呀)[!！。~～]*$",
    r"^(hello|hi|hey)[!！。~～\s]*$",
]

GREETING_COMPILED = [re.compile(p, re.IGNORECASE) for p in GREETING_PATTERNS]


# v0.19：出题/练习意图（"给我一道题" → 走出题逻辑，不当概念教学）
PROBLEM_REQ_PATTERNS = [
    r"给(我)?(出|来)?(一?道|些)?(经典|典型|例题|题目|题|练习|测试|题组|试卷|真题)",
    r"(出|来|给).{0,4}(题目|题|练习|例题|测试题|真题|卷子)",
    r"出(几)?道.{0,4}题|练习(一?下|几道)|考考(我)?|测(试|一?下)(我)?",
    r"来(几)?道题|做(一?道)?题|练习题|典型题|例题.{0,6}(给我|看看)?",
    r"给(我)?出.{0,10}(一道|几道)?题|出.{0,6}(一道|几道)?题",
]

PROBLEM_REQ_COMPILED = [re.compile(p, re.IGNORECASE) for p in PROBLEM_REQ_PATTERNS]


def is_problem_request(text: str) -> bool:
    """判断用户是否在请求出题/练习题（而非询问概念）。"""
    t = (text or "").strip()
    if not t or len(t) > 60:
        return False
    return any(p.search(t) for p in PROBLEM_REQ_COMPILED)


# v0.19.7：学习方法咨询检测——"如何学习X/怎么学/怎么复习/学习建议"
# 这类问题应走"学习方法指导"而非教学模式（避免被当概念教学或出题）
METHOD_ADVICE_PATTERNS = [
    r"如何(学习|学|复习|学好|掌握|备考)|怎么(学|复习|学好|备考|入手|开始)",
    r"学习方法|学习建议|复习(方法|计划|建议)|如何规划|怎么规划",
    r"学(好|会)?.{0,6}(难吗|要多久|怎么|如何)|从(哪|哪里|何).{0,4}(开始|入手)",
    r"有没有.{0,4}(学习方法|技巧|建议)|怎样才能(学|记|掌握)",
    # v0.21.3：思路/技巧/妙招/套路/解题思路（方法咨询，非知识库）
    r"(有什么|有何|求|求教|讲讲).{0,4}(思路|技巧|妙招|套路|方法|攻略)",
    r"(解题|做题|答题).{0,6}(思路|技巧|方法|套路|妙招|策略)",
    r"(基本思路|整体思路|解题思路|做题思路|答题思路)",
]
METHOD_COMPILED = [re.compile(p, re.IGNORECASE) for p in METHOD_ADVICE_PATTERNS]


def is_method_advice(text: str) -> bool:
    """判断用户是否在咨询"怎么学习"（方法/计划/建议）。"""
    t = (text or "").strip()
    if not t or len(t) > 60:
        return False
    # 排除纯题目请求（"给我一道题"不是方法咨询）
    if is_problem_request(t):
        return False
    return any(p.search(t) for p in METHOD_COMPILED)


# v0.19.15：知识库查询检测——用户问"你学过什么/你的知识库/你懂哪些"
# 固定关键词"知识库"，查询 Library 汇报已收录知识 + 提示可上传资料
KNOWLEDGE_QUERY_PATTERNS = [
    r"知识库|你(的)?知识|资料库",
    r"(你|我)?(学|学习|懂|掌握|知道|会|有)(过|了)?(什么|哪些|些).{0,4}(知识|内容)?",
    r"(学|懂|会|知道|掌握)(了|过)?(什么|哪些)",
    r"有哪些知识|有什么知识|会什么|懂什么|知道什么",
    r"你学了|你学了什么|你懂哪些|你了解什么",
    r"知识库里|库里",
]
KNOWLEDGE_COMPILED = [re.compile(p, re.IGNORECASE) for p in KNOWLEDGE_QUERY_PATTERNS]


def is_knowledge_query(text: str) -> bool:
    """判断用户是否在询问"知识库/你学过什么"（固定关键词）。

    v0.21.3：加排除规则——"有什么思路/方法/技巧/妙招"属方法咨询，不触发知识库。
    """
    t = (text or "").strip()
    if not t or len(t) > 60:
        return False
    # 排除：方法/技巧/思路类（应走学习方法或教学，不是知识库清点）
    if re.search(r"(思路|方法|技巧|妙招|套路|怎么(做|解|学|复习)|如何(解|学|复习)|解题)", t):
        return False
    return any(p.search(t) for p in KNOWLEDGE_COMPILED)


def is_greeting(text: str) -> bool:
    """判断是否纯寒暄（如"你好""hi"）。"""
    t = (text or "").strip()
    if not t:
        return False
    return any(p.match(t) for p in GREETING_COMPILED)


def is_meta_question(text: str) -> bool:
    """判断用户输入是否是元问题（关于系统自身）。"""
    t = (text or "").strip()
    if not t:
        return False
    # 长度限制：元问题通常较短（< 40 字）。过长输入即使含关键词也是教学问题。
    if len(t) > 40:
        # 但"你能调用知识库吗"这类含明确系统提问仍拦截
        if re.search(r"(你(能|会|可)).{0,12}(吗|吗？|么|么？)$", t) and any(p.search(t) for p in COMPILED):
            return True
        return False
    return any(p.search(t) for p in COMPILED)


# ─────────────────────────────────────────────
# v0.19.27：情绪与心理支持意图检测
# ─────────────────────────────────────────────
# 学生表达情绪/心理/人生困惑（而非学科问题）时，走 AffectionSupportor 子代理。

AFFECTION_PATTERNS = [
    # 情绪表达
    r"(难过|伤心|沮丧|失落|焦虑|紧张|害怕|恐惧|孤独|寂寞|迷茫|困惑|无助|绝望|崩溃)",
    r"(烦|烦死了|压力|累|疲惫|心累|emo|破防|没意思|没劲|空虚|麻木)",
    r"(开心|高兴|快乐|幸福).{0,6}(不起来|不了|不再)|提不起(劲|兴趣)",
    # 心理/状态
    r"心情(不好|很差|低落|糟糕)|情绪(低落|不好|崩溃)",
    r"最近(状态|心情).{0,4}(不好|差)|感觉自己(不行|没用|很糟糕|一无是处)",
    r"(抑郁|焦虑|失眠|没睡好|做噩梦)",
    # 人生/意义
    r"活着的(意义|意思)|人生的(意义|方向)|不知道(自己要什么|干嘛|为什么活着)",
    r"(迷茫|困惑).{0,6}(人生|未来|方向)|(想不通|想不明白).{0,6}(为什么|人生)",
    r"不知道(该干嘛|该做什么|怎么办)|没(方向|目标)|(没考好|考砸|失败|输了).{0,4}(很难受|难受|好难过)",
    # 关系/自我
    r"(失恋|分手|吵架|被孤立|被排挤|没朋友|交不到朋友)",
    r"(被|遭到).{0,4}(批评|否定|嘲笑|羞辱)|觉得自己(不够好|很差)",
    # 求助
    r"(帮帮我|救救我|好难受|受不了了|撑不下去|坚持不下去)",
    r"想(哭|一个人待着|消失|离开)|不想(说话|见人|活了)",
]
AFFECTION_COMPILED = [re.compile(p, re.IGNORECASE) for p in AFFECTION_PATTERNS]


def is_affection_expression(text: str) -> bool:
    """判断是否情绪/心理/人生困惑（而非学科问题）。"""
    t = (text or "").strip()
    if not t or len(t) > 100:
        return False
    return any(p.search(t) for p in AFFECTION_COMPILED)


# ─────────────────────────────────────────────
# v0.19.21：意向性层（Intentionality Layer）⭐
# ─────────────────────────────────────────────
# 问题：教学模式问"你今天怎么样"会被强行变成数学课（水杯/导数隐喻）——
# 教学 harness 的指令覆盖了用户提问的出发点与目的。
# 解法：在进入教学 harness 前，用 LLM 判断用户输入是否为"教学意图"。
#   教学意图   → 正常走教学（学科知识/概念/题目/方法）
#   非教学意图 → 一般化响应（寒暄/情感/生活话题/非学科闲聊），不套教学模板
# 原则：规则拦截（is_knowledge_query/meta/greeting/method/problem）永远优先且廉价；
#       LLM 意向性判断是"兜底"，只对规则没拦住的输入启用。

# 缓存：同一句输入 10 分钟内不重复调用 LLM（教学场景重复问同一概念很常见）
_INTENT_CACHE = {}
_INTENT_CACHE_TTL = 600


def is_teaching_intent(text: str, llm=None) -> bool:
    """LLM 判断用户输入是否为教学意图（默认 True——教学模式假设可教）。

    返回 True（教学） / False（一般性对话，走闲聊响应）。
    规则已拦截的输入不应到这里（调用方保证）；此函数只兜底。
    """
    t = (text or "").strip()
    if not t or len(t) > 120:
        return True  # 超长输入按教学处理（安全默认）
    # 缓存
    import time as _t
    now = _t.time()
    if t in _INTENT_CACHE and now - _INTENT_CACHE[t][1] < _INTENT_CACHE_TTL:
        return _INTENT_CACHE[t][0]

    intent = True  # 默认教学
    if llm is not None:
        try:
            from subagents import _safe_chat
            system = (
                "你是意图判断器。判断学生的这句话是不是想学习学科知识。\n"
                "返回严格 JSON：{\"teaching\": true/false, \"reason\": \"简短原因\"}\n"
                "teaching=true：涉及学科知识/概念/题目/解题/学习方法/复习备考等。\n"
                "teaching=false：寒暄/情感倾诉/生活闲聊/非学科话题/问老师近况/感谢/告别等。\n"
                "只输出 JSON。"
            )
            user = f"学生说：{t}"
            r = _safe_chat(llm, system, user, max_tokens=80)
            if r:
                import json as _json, re as _re
                m = _re.search(r'\{.*\}', r, _re.S)
                if m:
                    parsed = _json.loads(m.group(0))
                    intent = bool(parsed.get("teaching", True))
        except Exception:
            intent = True  # LLM 失败安全默认教学
    _INTENT_CACHE[t] = (intent, now)
    return intent


# v0.21.9：复合输入检测——"指令 + 资源"（用户给指令让处理一段资料）
_COMPOSITE_CMD = re.compile(
    r"(帮我|请|麻烦|能不能|可以|我想让你|求|帮我看看|帮我分析|帮我解释|帮我翻译|"
    r"帮我总结|帮我找|帮我改|帮我写|帮我润色|帮我检查|帮我点评|帮我评价|帮我读|"
    r"分析一下|解释一下|翻译一下|总结一下|检查一下|看看|点评一下|"
    r"这段|这段代码|这个代码|下面这段|以下这段|这段文字|这段内容)"
    r".{0,12}(这|本|以下|下面|那|一段|这篇|这个|这份|我的|这段|这份)?"
    r"(段|篇|文|文章|内容|代码|题目|对话|资料|材料|文字|作文|话|简历|论文|"
    r"有什么问题|什么毛病|对不对|怎么改|什么意思)?"
    r"([:：]\s*)?"
)
_SEP_MARKERS = (":\n", "：\n", "\n\n", "```", "「", "\u201c", "【")

_IS_INTENT_CACHE: dict = {}


def is_intent_with_material(text: str) -> bool:
    """v0.21.9：检测"指令 + 资料"复合输入。

    形态 B：用户输入 = 指令（分析/翻译/找问题/总结）+ 一大段资源（文章/代码/资料）。
    检测信号：
    1. 长度 > 60 且含明显分隔符（冒号换行/双换行/代码块/引号）
    2. 短指令关键词（"帮我分析/请解释/翻译一下"）+ 跟资源指示词（这段/这篇/以下）
    返回 True 时，调用方应走"资源分析"流程而非"概念教学"流程。
    """
    t = (text or "").strip()
    if not t:
        return False
    cache_key = t[:60]
    if cache_key in _IS_INTENT_CACHE:
        return _IS_INTENT_CACHE[cache_key]
    result = False
    # 信号 1：长文本 + 分隔符
    if len(t) > 60 and any(sep in t for sep in _SEP_MARKERS):
        result = True
    # 信号 2：复合指令关键词（长度 ≥ 20，避免"你好"类误判）
    elif _COMPOSITE_CMD.search(t) and len(t) >= 20:
        result = True
    _IS_INTENT_CACHE[cache_key] = result
    return result


def split_intent_and_material(text: str):
    """v0.21.9：把"指令+资料"切成 (指令, 资料) 两段。

    用第一个分隔符（冒号换行/双换行/引号）切分；找不到则指令=前80字。
    """
    t = (text or "").strip()
    for sep in _SEP_MARKERS:
        idx = t.find(sep)
        if idx > 0:
            return t[:idx].strip(), t[idx + len(sep):].strip()
    # 退化：前 80 字当指令，其余当资料
    return t[:80], t[80:]


if __name__ == "__main__":
    tests = [
        "你能调用知识库吗",           # True（幻觉案例）
        "你是谁",                     # True
        "你能做什么",                 # True
        "你叫什么名字",               # True
        "什么是熵？",                 # False（学科问题）
        "请解释一下光合作用",          # False
        "你能调用知识库来查一下勾股定理吗",  # True
        "帮我讲讲欧拉公式",            # False
        "你为什么叫Émile？",           # True
        "物理学中的摩擦力怎么算",       # False
    ]
    for t in tests:
        print(f"{'✅' if is_meta_question(t) else '❌'} {t}")
