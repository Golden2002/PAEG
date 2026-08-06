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
    # 知识库
    r"知识库|资料库|你(有|能)(调用|用|查|找|读|看).*(库|资料)|能不能(调用|查|找).*库",
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
    r"知识库|你(学|懂|知道|会|有)(过)?(什么|哪些)|你(的)?知识|你会什么|你懂什么",
    r"学了什么|会什么|懂什么|知道什么|有哪些知识|你有什么",
    r"知识库里有|库里有|资料库",
]
KNOWLEDGE_COMPILED = [re.compile(p, re.IGNORECASE) for p in KNOWLEDGE_QUERY_PATTERNS]


def is_knowledge_query(text: str) -> bool:
    """判断用户是否在询问"知识库/你学过什么"（固定关键词）。"""
    t = (text or "").strip()
    if not t or len(t) > 60:
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
