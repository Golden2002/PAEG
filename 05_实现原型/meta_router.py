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
from typing import Optional

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
# v0.27 设计原则 ⭐：正则只做"快准廉"的确定场景（纯寒暄），模糊意图（天气/闲聊/近况）
# 一律交给 LLM 综合判断（_llm_route_intent）——遵循"LLM 优先、规则兜底"。
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
    # v6.1 ⭐ 收紧：用户原则"固定模式不要宽泛正则，用完整关键词匹配 + LLM 判断"
    # 仅精确短语命中（完整表达），模糊变体由 LLM 判断（INTENT_PROMPT 已补示例）
    r"知识库|你(的)?知识库|资料库",
    r"你学过什么|你学了什么|你学过哪些|你学了哪些|你懂什么|你懂哪些|你会什么|你了解什么",
    r"你(掌握|知道)(什么|哪些)|有哪些知识|有什么知识|你的知识",
    r"你收藏了什么(资料|书)|你收着(什么|哪些)(资料|书)|知识库里(有|存)什么|库里有什么",
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
    # v0.35 ⭐ 排除：推荐类问题（"有什么推荐/推荐什么/推荐几本/哪个APP好"）——
    # 用户问"法语学习的软件有什么推荐"会被 `学习.*什么` 正则误判为知识库查询。
    # 推荐是主动咨询行为，不是"查我的知识库"，应走教学/回答管线。
    if re.search(r"(推荐|推荐什么|有什么推荐|哪个.{0,6}(好|好用|推荐)|推荐几|求推荐|安利)", t):
        return False
    # v6.0 ⭐ P1 修复：**明确能力类**问题（"你有哪些功能/你能做什么"）是询问 AI 能力，
    # 应走 interface 确定性模板，不是库清点。规则层只排除**明确**能力类；
    # ambiguous 输入（"你学过什么/你会什么"）留给 LLM 判断（INTENT_PROMPT 已补示例），
    # 规则层仍按 knowledge 兜底（问 AI 掌握的知识 = 库清点）。
    try:
        from self_referential import is_interface_query
        _t = text or ""
        # 明确能力类：含"功能/能力/做什么/帮什么" + "你"前缀
        if is_interface_query(_t) and re.search(r"(功能|能力|本领|做什么|帮什么|用处)", _t):
            return False
    except Exception:
        pass
    return any(p.search(t) for p in KNOWLEDGE_COMPILED)


def is_greeting(text: str) -> bool:
    """判断是否纯寒暄（如"你好""hi"）。"""
    t = (text or "").strip()
    if not t:
        return False
    return any(p.match(t) for p in GREETING_COMPILED)


# v0.35 ⭐ 推荐类问题：用户问"有什么推荐/推荐什么/哪个软件好"——
# 应联网检索真实推荐，不是查知识库，也不是普通教学。
# 这是"主动咨询"型输入（求资源/APP/书/课程），与"查我的知识库"不同，
# 也与一般教学（讲概念）不同——必须先有外部事实才能给有用答案。
RECOMMEND_PATTERNS = [
    r"推荐|有什么(好|不错|值得|适合).{0,6}(软件|书|资源|网站|课程|视频|应用|工具|资料|教材|APP)",
    r"(软件|书|资源|网站|课程|视频|应用|工具|教材|APP).{0,8}(推荐|推荐吗|哪个好)",
    r"(求|想要|找).{0,4}(推荐|资源|资料|教材)",
]
RECOMMEND_COMPILED = [re.compile(p, re.IGNORECASE) for p in RECOMMEND_PATTERNS]


def is_recommend_request(text: str) -> bool:
    """判断用户是否在问推荐类问题（软件/书/资源/课程等推荐）。

    v0.35 新增：解决"法语学习的软件有什么推荐"被 is_knowledge_query
    误判为查知识库、走到答非所问"清点藏书"的问题。
    长度限制与 is_knowledge_query 一致：>60 字通常不是咨询式推荐问题。
    """
    t = (text or "").strip()
    if not t or len(t) > 60:
        return False
    return any(p.search(t) for p in RECOMMEND_COMPILED)


# v0.35 ⭐ PPT 生成意图：用户要"做PPT/演示文稿/课件"
# 单独的规则函数（与 is_recommend_request / is_problem_request 都不同语义），
# 并补齐 VALID_INTENTS 里 "ppt" 选项的兜底路径。
PPT_PATTERNS = [
    r"(做|生成|制作|整理|创建).{0,6}(PPT|ppt|演示文稿|课件|幻灯片)",
    r"(PPT|ppt|演示文稿|课件|幻灯片).{0,6}(做|生成|制作|整理)",
    r"把.{0,10}(整理|做成|生成).{0,6}(PPT|ppt|演示文稿)",
]
PPT_COMPILED = [re.compile(p, re.IGNORECASE) for p in PPT_PATTERNS]


def is_ppt_request(text: str) -> bool:
    """v0.35 ⭐ 判断用户是否要求生成 PPT / 演示文稿 / 课件。

    与 is_recommend_request 区别：推荐是"给个选项让我选"，PPT 是"直接产出文件"。
    """
    t = (text or "").strip()
    if not t or len(t) > 60:
        return False
    return any(p.search(t) for p in PPT_COMPILED)


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
# 原则（v0.35 ⭐ 用户原话："LLM 是被充分调用的主体，规则只兜底"）：
#   LLM 主路由（route_intent）优先——大模型先判断意图、在多选项中选一个；
#   规则（rule_fallback_intent）降级兜底——只在 LLM 失败/低置信度时介入。
#   下方的 is_teaching_intent 是更早版本的二分类判断（教/非教），v0.35 起
#   被 route_intent 的 11 类多分类取代；保留作回滚保险与向后兼容。

# 缓存：同一句输入 10 分钟内不重复调用 LLM（教学场景重复问同一概念很常见）
_INTENT_CACHE = {}
_INTENT_CACHE_TTL = 600


# ═════════════════════════════════════════════════════════════
# v0.35 ⭐ LLM 优先意图路由（用户原则：LLM 是被充分调用的主体，规则只兜底）
# 大模型先判断用户意图，在多个选项中选一个；规则仅作 LLM 失败/低置信度时的兜底。
# ═════════════════════════════════════════════════════════════
# v0.35 ⭐ 命名统一原则（用户原话："选项应该和兜底规则的变量名相同"）
# VALID_INTENTS 的每个 key 必须能在本模块（或被 try/except 引入的模块）里
# 找到对应的 is_xxx() 规则函数；LLM 选出来后 rule_fallback_intent() 用同名函数兜底。
#
# v0.36 ⭐ P0-E 修正（命名规范统一）：
# 本文件存在两套意图命名（历史遗留）：
#   1. **v0.35 LLM 主路由**用动词原形（teach / knowledge / recommend / method / emotion /
#      problem / meta / greeting / material / interface / ppt / answer / chat）——见下方 VALID_INTENTS。
#   2. **v0.35 之前 is_teaching_intent 旧二分类**返回 {"type": "teaching" / "non_teaching"}——保留
#      仅作回滚保险与向后兼容（行 ~432 起的 deprecated 函数）。
# v0.36 起规范：
#   - **新代码、对外 API、规则函数调用**：统一使用 v0.35 LLM 主路由的动词原形（teach/...）。
#   - **旧代码（is_teaching_intent 路径）**：保留 type 字段为 "teaching"/"non_teaching"，
#     但下游消费方应做归一化映射——见 route_intent() 行 ~614 的 priority 注释。
#   - 不允许再新增第三套命名（teach_xxx / is_teach_xxx 等）。
#   - 此约定 v0.36 起冻结，未来版本（v0.37+）可移除 is_teaching_intent 全部路径，
#     届时 VALID_INTENTS 仅留单数动词原形。
VALID_INTENTS = {
    "teach",          # is_teaching_intent       (LLM-only，规则已弃用)
    "knowledge",      # is_knowledge_query       (库清点)
    "knowledge_map",  # is_knowledge_map_request (思维导图/知识地图) — knowledge_map.py
    "recommend",      # is_recommend_request     (软件/书/资源推荐)
    "method",         # is_method_advice         (学习方法咨询)
    "emotion",        # is_affection_expression  (情绪/心理/危机)
    "problem",        # is_problem_request       (出题/练习)
    "meta",           # is_meta_question         (关于系统本身)
    "greeting",       # is_greeting              (寒暄/打招呼)
    "material",       # is_intent_with_material  (用户上传文件/复合指令+资料)
    "interface",      # is_interface_query       (界面操作) — server.py
    "ppt",            # is_ppt_request           (PPT/演示文稿生成) — 本文件新增
    "answer",         # 知识问答/直接回答（无规则函数，纯 LLM 判断）
    "chat",           # 闲聊（无规则函数，纯 LLM 判断）
}

INTENT_PROMPT = """你是 PAEG 教育智能体的意图路由器。你的任务：阅读用户输入，判断它属于下面 14 个意图中的哪一类，**只返回该意图的变量名**（如 "teach" / "interface"），不要做其他任何事。

【意图类型定义（每个类型是什么、边界在哪）】
- teach: 教学请求——用户要开始学习/继续学习/讲解某个学科概念（"教我法语""什么是导数""继续""下一题""讲解这个语法"）。注意：问"概念是什么"但目的是理解 → teach；只是要一句话结论 → answer。
- answer: 知识问答——用户要直接答案/快速结论（"法语难吗""π等于多少""这道题答案是什么"）。与 teach 的区别：answer 要结论，teach 要过程讲解。
- chat: 闲聊——与学习无关的日常对话、寒暄延伸、随便聊聊（"今天天气""你吃饭了吗""随便聊聊"）。注意：闲聊是**非学习**内容；学习相关一律不是 chat。
- knowledge: 清点/查询知识库——用户问"我学过什么/知识库有什么/你收藏了什么资料"（清点已有内容，非新教学）。
- knowledge_map: 生成/查看知识地图/思维导图（"画个思维导图""知识框架""结构图"）。
- recommend: 工具/软件/书/资源推荐——用户要"推荐/用什么好"（"学法语用什么软件""推荐几本英语书"）。
- method: 学习方法论/认知策略（"怎么记单词""如何高效学习""怎么复习"）。
- emotion: 情绪表达/倾诉/心理支持（"学不下去了""太难了想放弃""我很焦虑"）。**关键边界：用户是在「表达感受」还是在「寻求答案」**——表达感受/自我怀疑/挫败感 → emotion（如"是不是有些人怎么努力都没用？""我是不是很差"）；寻求答案/方法/原因（"怎么办/怎么学/为什么"）→ teach 或 knowledge。陈述句+情绪词 = 强 emotion。
- problem: 出题/测验/练习（"出10道题""考考我""来道练习"）。
- meta: 纯身份问题——关于"我是谁"（"你是谁""你叫什么""你是什么"）。注意：**"你能做什么/有什么功能/怎么用"不是 meta**，是 interface（问能力/功能/使用）。
- interface: 界面/功能/使用问题——用户问系统有什么功能、怎么用、界面操作（"你有什么功能""你能做什么""这个网站怎么用""换深色模式""按钮在哪""怎么切换语言"）。注意：功能/能力/使用类问题**都属于 interface**，不是 meta。
- material: 基于用户上传的文件操作（"看我上传的文件""用我的资料回答""讲义在哪"）。
- ppt: 生成演示文稿/PPT（"做PPT""整理成演示文稿""生成课件""把这些资料做成PPT"）。
- greeting: 寒暄/打招呼（"你好""在吗""嗨"）。

【关键区分示例】
- "你有什么功能" → interface（问能力清单），不是 meta
- "你能做什么" → interface（问能力），不是 meta
- "这个网站怎么用" → interface（问使用），不是 meta
- "你是谁" → meta（纯身份），不是 interface
- "学法语用什么软件" → recommend（推荐工具），不是 knowledge
- "教我法语" → teach（要开始教学），不是 recommend
- "法语难吗" → answer（知识问答），不是 method
- "怎么学法语" → method（学习方法），不是 teach
- "我学过什么" → knowledge（清点知识库），不是 teach
- "画个知识框架图" → knowledge_map（思维导图），不是 teach
- "把这些资料做成PPT" → ppt（生成演示文稿），不是 teach
- "看下我上传的笔记" → material（用户文件），不是 knowledge
- "换深色模式" → interface（界面操作），不是 teach
- "你学过什么/你会什么/你懂什么" → **ambiguous**：若指"你（AI）掌握的知识库内容" → knowledge（清点知识库）；若指"你（AI）的能力/本领" → interface（能力）。**由你判断语境**：知识内容 → knowledge，能力本领 → interface
- "你有哪些功能/你能做什么" → interface（问能力清单），不是 knowledge
- "知识库里有什么/你收藏了什么资料" → knowledge（清点资料库），不是 interface
- "今天天气怎么样" → chat（闲聊），不是 teach

【用户输入】
{text}

【输出要求】只输出严格 JSON（不要 markdown 代码块、不要任何其他文字）：
{"intent": "上面 14 个变量名之一", "confidence": 0.0-1.0, "reason": "简短中文原因"}
"""

_INTENT_CACHE_V2 = {}
_INTENT_CACHE_TTL_V2 = 600


def route_intent(text: str, llm=None, use_cache: bool = True, mode: str = None) -> dict:
    """v0.35 ⭐ LLM 主路由：判断用户意图（在选项中选一个）。
    返回 {"intent": str, "confidence": float, "reason": str}
    LLM 不可用/失败/超时 → 返回 {"intent": "chat", "confidence": 0.0, "reason": "llm_error"}

    v0.41.6 ⭐ 模式短路（确定性信号优先于 LLM 判断）：
    前端已显式选择模式（chat/teach/answer/method/knowledge/affection/ppt）时，
    直接返回该模式对应意图——用户已点"闲聊"按钮，LLM 不必再判断"这是不是闲聊"。
    这是"确定性信号 → LLM 判断 → 规则兜底"管线的第一层。
    """
    import time as _t
    t = (text or "").strip()
    if not t:
        return {"intent": "chat", "confidence": 0.0, "reason": "empty"}
    # v6.0 ⭐ Magic 口令优先：特定口令（"你是谁/你能做什么/你学过什么"）是
    # 比模式选择更强的确定性信号——即使前端选了 knowledge，问"你是谁"也应答身份模板。
    # 模糊变体（"你是谁呀"）不命中，留给 LLM 判断（INTENT_PROMPT 已补示例）。
    try:
        from magic_intent import match_magic
        _magic = match_magic(t)
        if _magic:
            return {"intent": _magic["intent"], "confidence": 0.98,
                    "reason": _magic["reason"]}
    except Exception:
        pass
    # v0.41.6 ⭐ 模式短路：前端 mode 是用户显式选择，是最强确定性信号
    _MODE_TO_INTENT = {
        "teach": "teach", "chat": "chat", "answer": "answer",
        "method": "method", "knowledge": "knowledge",
        "affection": "emotion", "ppt": "ppt", "problem": "problem",
    }
    if mode and mode in _MODE_TO_INTENT:
        return {"intent": _MODE_TO_INTENT[mode], "confidence": 0.95,
                "reason": f"mode:{mode}"}
    now = _t.time()
    if use_cache and t in _INTENT_CACHE_V2 and now - _INTENT_CACHE_V2[t][1] < _INTENT_CACHE_TTL_V2:
        return _INTENT_CACHE_V2[t][0]
    if llm is None:
        return {"intent": "chat", "confidence": 0.0, "reason": "no_llm"}
    try:
        from subagents import _safe_chat
        # 用 replace 而非 format：模板里有 JSON 示例（{...}），不能用 format 当占位符
        prompt = INTENT_PROMPT.replace("{text}", t[:120])
        raw = _safe_chat(llm, prompt, t[:120], max_tokens=120)
        if not raw:
            return {"intent": "chat", "confidence": 0.0, "reason": "llm_empty"}
        # 提取 JSON（可能被 ```json 包裹）
        import re as _re, json as _json
        m = _re.search(r'\{.*\}', raw, _re.S)
        if not m:
            return {"intent": "chat", "confidence": 0.0, "reason": "no_json"}
        data = _json.loads(m.group(0))
        intent = str(data.get("intent", "chat")).strip()
        if intent not in VALID_INTENTS:
            intent = "chat"
        conf = float(data.get("confidence", 0.5))
        result = {"intent": intent, "confidence": max(0.0, min(1.0, conf)),
                  "reason": str(data.get("reason", ""))[:100]}
        if use_cache:
            _INTENT_CACHE_V2[t] = (result, now)
        return result
    except Exception as e:
        return {"intent": "chat", "confidence": 0.0, "reason": f"llm_error:{type(e).__name__}"}


def rule_fallback_intent(text: str) -> dict:
    """v0.35 ⭐ 规则降级兜底：LLM 失败/低置信度时用。
    危机/自伤必须 fast-path（安全 > 延迟）；其余按现有规则函数判定。
    命名与 VALID_INTENTS 一一对应（用户原则：选项=兜底规则变量名）。
    """
    t = (text or "").strip()
    # 危机/自伤：无条件 fast-path（不依赖 LLM）
    try:
        from safety import guard_input
        res = guard_input(t)
        if res and res.get("blocked") and "self_harm" in (res.get("reason") or []):
            return {"intent": "emotion", "confidence": 0.95, "reason": "rule:emergency"}
    except Exception:
        pass
    if is_greeting(t):
        return {"intent": "greeting", "confidence": 0.85, "reason": "rule:greeting"}
    # v6.0 ⭐ Magic 口令层：精确匹配"你是谁/你能做什么/你学过什么" → 固定模板（零 LLM）
    # 用户指示：特定口令精确匹配不走 LLM；模糊变体由 LLM 判断（更上游 route_intent）。
    # 命中则直接分流（interface→身份/能力模板，knowledge→库清点）。
    try:
        from magic_intent import match_magic
        _magic = match_magic(t)
        if _magic:
            return {"intent": _magic["intent"], "confidence": 0.95,
                    "reason": _magic["reason"]}
    except Exception:
        pass
    # v0.41.5 ⭐ 顺序修正：interface（功能/使用/界面）优先于 meta（纯身份）
    # —— "你有什么功能/怎么用"是 interface（确定性模板回答），"你是谁"才是 meta。
    # 此前 meta 在 interface 之前 → LLM 不可用时"你有什么功能"走错 meta 分支（自由发挥）。
    try:
        from self_referential import is_interface_query
        if is_interface_query(t):
            return {"intent": "interface", "confidence": 0.8, "reason": "rule:interface"}
    except Exception:
        pass
    if is_meta_question(t):
        return {"intent": "meta", "confidence": 0.8, "reason": "rule:meta"}
    try:
        if is_recommend_request(t):
            return {"intent": "recommend", "confidence": 0.7, "reason": "rule:recommend"}
    except Exception:
        pass
    # v0.35 ⭐ 知识地图 / 思维导图（独立模块 knowledge_map.py）
    try:
        from knowledge_map import is_knowledge_map_request
        if is_knowledge_map_request(t):
            return {"intent": "knowledge_map", "confidence": 0.8, "reason": "rule:knowledge_map"}
    except Exception:
        pass
    # v0.35 ⭐ 用户上传文件 / 指令+资料复合
    try:
        if is_intent_with_material(t):
            return {"intent": "material", "confidence": 0.7, "reason": "rule:material"}
    except Exception:
        pass
    # v0.35 ⭐ material 兜底补强：is_intent_with_material 只认"指令+资料"复合形态
    # （长度 > 60 + 分隔符 或 复合指令关键词），对"看我上传的笔记"等短句上传类
    # 输入会漏判。这里加一个轻量关键词兜底（不修改原 is_intent_with_material）。
    if re.search(
        r"(我(的)?|刚)(上传|传|发|提交)(的|了)?.{0,6}(文件|资料|笔记|讲义|文档|作业|附件|图片|资料)",
        t,
    ):
        return {"intent": "material", "confidence": 0.7, "reason": "rule:material_upload"}
    # v0.35 ⭐ PPT / 演示文稿生成（本文件新增 is_ppt_request）
    try:
        if is_ppt_request(t):
            return {"intent": "ppt", "confidence": 0.8, "reason": "rule:ppt"}
    except Exception:
        pass
    if is_knowledge_query(t):
        return {"intent": "knowledge", "confidence": 0.5, "reason": "rule:knowledge_low"}
    if is_method_advice(t):
        return {"intent": "method", "confidence": 0.7, "reason": "rule:method"}
    try:
        if is_problem_request(t):
            return {"intent": "problem", "confidence": 0.7, "reason": "rule:problem"}
    except Exception:
        pass
    try:
        if is_affection_expression(t):
            return {"intent": "emotion", "confidence": 0.7, "reason": "rule:emotion"}
    except Exception:
        pass
    return {"intent": "chat", "confidence": 0.3, "reason": "rule:default"}


def is_teaching_intent(text: str, llm=None, fallback_to_teach: bool = True) -> bool:
    """（v0.35 起弃用——用 route_intent 替代）LLM 判断用户输入是否为教学意图（默认 True——教学模式假设可教）。

    返回 True（教学） / False（一般性对话，走闲聊响应）。
    规则已拦截的输入不应到这里（调用方保证）；此函数只兜底。

    v0.24（PAEG 自闭环）：LLM 异常不再静默默认 True，而是按调用方的
    ``fallback_to_teach`` 参数决定 —— 默认仍为 True 保持兼容，但打 warn 日志；
    调用方 route() 内部可通过此参数避免静默吞错。
    """
    t = (text or "").strip()
    if not t or len(t) > 120:
        return True  # 超长输入按教学处理（安全默认）
    # 缓存
    import time as _t
    now = _t.time()
    if t in _INTENT_CACHE and now - _INTENT_CACHE[t][1] < _INTENT_CACHE_TTL:
        return _INTENT_CACHE[t][0]

    intent = True  # 默认教学（兼容旧调用）
    llm_failed = False
    llm_none_return = False  # v0.24：_safe_chat 静默返回 None（_is_real_llm 失败 / 异常被吞）也视为异常
    if llm is None and not fallback_to_teach:
        # 无 LLM + 调用方明确不希望静默默认教学 → 显式返回 False + warn 日志
        import warnings as _w
        _w.warn(f"[PAEG][meta_router] is_teaching_intent: 无 LLM 实例且"
                f" fallback_to_teach=False，改返 False（不再静默默认教学）",
                RuntimeWarning, stacklevel=2)
        print(f"[PAEG][meta_router] is_teaching_intent 无 LLM 且 fallback_to_teach=False"
              f" → intent=False")
        _INTENT_CACHE[t] = (False, now)
        return False
    if llm is not None:
        try:
            from subagents import _safe_chat, _is_real_llm
            # v0.24：_is_real_llm 先判一次 —— 若 LLM 实例不真实（_safe_chat 会静默返 None）
            if not _is_real_llm(llm):
                llm_failed = True
                intent = bool(fallback_to_teach)
                _msg = f"_is_real_llm=False: llm={type(llm).__name__}"
                import warnings as _w
                _w.warn(f"[PAEG][meta_router] is_teaching_intent: {_msg} (fallback_to_teach={fallback_to_teach})",
                        RuntimeWarning, stacklevel=2)
            else:
                system = (
                    "你是意图判断器。判断学生的这句话是不是想学习学科知识。\n"
                    "返回严格 JSON：{\"teaching\": true/false, \"reason\": \"简短原因\"}\n"
                    "teaching=true：涉及学科知识/概念/题目/解题/学习方法/复习备考等。\n"
                    "teaching=false：寒暄/情感倾诉/生活闲聊/非学科话题/问老师近况/感谢/告别等。\n"
                    "【端点语义优先级（v0.34 ⭐）】\n"
                    "- 此判断在 /api/teach/stream 端点被调用，已通过前端模式开关选定教学模式。\n"
                    "- 普通概念提问（'什么是熵'、'解释牛顿第二定律'）即使形式像聊天，"
                    "也必须返回 teaching=true（这是教学模式的核心契约）。\n"
                    "- 仅当用户表达明确属于下列子意图时才返回 teaching=false：\n"
                    "  * 情绪宣泄（'我很焦虑'）\n"
                    "  * 方法论咨询（'怎么学好物理'）\n"
                    "  * 知识库查询（'查一下课本第 X 章'）\n"
                    "  * 界面操作/元问题（'换皮肤'、'你是谁'）\n"
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
                else:
                    # v0.24：_safe_chat 返 None —— 可能是 LLM 抛异常被吞/超时/泄漏等
                    llm_none_return = True
                    llm_failed = True
                    intent = bool(fallback_to_teach)
        except Exception as _e:
            llm_failed = True
            # v0.24：不再静默 —— 显式 warn 日志
            import warnings as _w
            _w.warn(f"[PAEG][meta_router] is_teaching_intent: LLM 调用失败: {_e}",
                    RuntimeWarning, stacklevel=2)
            intent = bool(fallback_to_teach)
    if llm_failed:
        # 额外 print 方便 server 日志检索（warnings.warn 在某些环境下不显眼）
        if llm_none_return:
            print(f"[PAEG][meta_router] is_teaching_intent _safe_chat 静默返 None"
                  f"（可能 LLM 异常被吞），fallback_to_teach={fallback_to_teach} → intent={intent}")
        else:
            print(f"[PAEG][meta_router] is_teaching_intent LLM 失败，使用 "
                  f"fallback_to_teach={fallback_to_teach} → intent={intent}")
    _INTENT_CACHE[t] = (intent, now)
    return intent


# v0.24：route() 集中分发 —— 替代散落在 server.py 中的巨型 if/elif 链
# 优先级（与 server.py teach 496-674 / teach_stream 798-980 保持一致，按任务要求：
#   affection 危机最高优先 → meta → greeting → knowledge → method → problem → teaching → 默认）
# 注：本模块暂未实现 is_file_operation detector（任务列表里列了，实际 server.py
#   也无对应拦截）；新增的 composite 优先级放在 affection 之后 / meta 之前，避免
#   "指令+资料"被元问题截胡。
#
# 返回 dict：{"type": str, "confidence": float, "reason": str, "raw": {...}}
# 调用方用 type 决定后续分支，confidence 用于日志/灰度，reason 用于调试。

ROUTE_TYPE_ORDER = (
    "affection",      # 0. 情绪/心理危机（最优先，crisis-first）
    "composite",      # 1. 指令+资料复合
    "meta",           # 2. 元问题（你是谁/你能做什么）
    "greeting",       # 3. 寒暄（你好）
    "knowledge",      # 4. 知识库查询（你学过什么）
    "method",         # 5. 学习方法咨询
    "problem",        # 6. 出题请求
    "teaching",       # 7. 教学意图（LLM 兜底）
    "non_teaching",   # 8. 默认：非教学
)




def _llm_route_intent(text: str, llm) -> Optional[str]:
    """v0.26 ⭐ LLM 综合意图判断（发挥 LLM 理解能力为原则）。

    让 LLM 结合输入语义判断用户真正意图，而非只用规则正则硬拦。
    规则（is_*_query）仍是快速路径，但 LLM 判断优先于部分规则——
    规则可能误判"有什么思路"等语境，LLM 能理解完整语义。

    返回意图 key：teach / answer / affection / knowledge / method / problem / meta / greeting / non_teaching
    LLM 失败返回 None（调用方回退规则）。
    """
    try:
        from subagents import _safe_chat
        _sys = (
            "你是 PAEG 的意图理解器。判断学生这句话属于哪类意图：\n"
            "1. teach：想学一个概念/知识点（'什么是导数''讲讲勾股定理'）\n"
            "2. answer：想要一个直接答案/结果（'2+2等于几''帮我算一下'）\n"
            "3. affection：表达情绪/需要陪伴（'我今天很难过''感觉好累'）\n"
            "4. knowledge：问我的知识库/能力（'你知道什么''你的知识库里有啥'）\n"
            "5. method：问学习方法/技巧（'怎么学数学''有什么学习技巧'）\n"
            "6. problem：给一道题求解决（'解这个方程'）\n"
            "7. meta：问你是谁/怎么用（'你是什么''你叫什么'）\n"
            "8. greeting：打招呼（'你好''hi'）\n"
            "9. non_teaching：其他/闲聊/日常话题（'今天天气怎么样''最近好吗''随便聊聊''现在几点''你吃饭了吗'）\n"
            "判断规则：\n"
            "- **无关话题/闲聊/寒暄性提问必须归 non_teaching**，绝不能因含名词（如'天气'）就当 teach——那是答非所问\n"
            "- 只有学生明确表达'想学/讲讲/什么是'某学科概念时才算 teach\n"
            "【端点语义优先级（v0.34 ⭐）】\n"
            "- 若调用方传入 endpoint_hint=\"teach_stream\"，表示已通过前端模式开关选定教学模式。\n"
            "- 此模式下，仅当用户表达明确属于下列子意图时才返回非 teach：\n"
            "  * affection：情绪宣泄（'我很焦虑'）\n"
            "  * method：方法论咨询（'怎么学好物理'）\n"
            "  * knowledge：知识库查询（'查一下课本第 X 章'）\n"
            "  * greeting/meta：界面/元问题（'换皮肤''你是谁'）\n"
            "- 普通概念提问（'什么是熵'、'解释牛顿第二定律'）即使形式像聊天，也必须返回 teach。\n"
            "只输出一个词：teach/answer/affection/knowledge/method/problem/meta/greeting/non_teaching。不要多余文字。"
        )
        _user = str(text)[:200]
        # v0.34 ⭐ 端点语义锚点注入（支持 context 时透传 endpoint_hint）
        try:
            r = _safe_chat(llm, _sys, _user, max_tokens=20, context={"endpoint_hint": "teach_stream"})
        except TypeError:
            # _safe_chat 不支持 context 参数时回退原签名
            r = _safe_chat(llm, _sys, _user, max_tokens=20)
        if r:
            intent = r.strip().lower()
            valid = ("teach", "answer", "affection", "knowledge", "method", "problem", "meta", "greeting", "non_teaching")
            if intent in valid:
                return intent
    except Exception:
        pass
    return None


def route(text: str, learner=None, session=None, llm=None,
          fallback_to_teach: bool = False, endpoint_hint: Optional[str] = None) -> dict:
    """v0.24：集中路由决策器 —— 替代 server.py 中的 if/elif 链。

    依次按优先级评估现有 detector：
      1. is_affection_expression   → affection （crisis-first）
      2. is_intent_with_material   → composite（指令+资源）
      3. is_meta_question          → meta（你是谁/能做什么）
      4. is_greeting               → greeting（寒暄）
      5. is_knowledge_query        → knowledge（库清点）
      6. is_method_advice          → method（方法咨询）
      7. is_problem_request        → problem（出题）
      8. is_teaching_intent        → teaching（LLM 兜底，不再静默）
      9. 否则                        → non_teaching

    Args:
        text: 用户输入文本。
        learner: LearnerProfile（预留，给 future 个性化权重用 —— 当前不动）。
        session: Session（预留，给 future 个性化权重用）。
        llm: LLM 实例，传给 is_teaching_intent。
        fallback_to_teach: 当 LLM 不可用或异常时，is_teaching_intent 是否返回 True。
            route() 默认 False —— 不再静默按教学处理，记录 warn 日志。
        endpoint_hint: v0.34 ⭐ 端点语义提示（如 "teach_stream"），用于上下文锚定。
            当前主要在 prompt 中体现；调用方应自行兜底（避免被 LLM 误判绕过）。

    Returns:
        dict 形如
            {
              "type": "teach|meta|greeting|knowledge|method|problem|affection|composite|non_teaching",
              "confidence": float,  # 0~1
              "reason": str,
              "raw": dict,         # 命中的 detector 反馈 + 后备
              "fallback_to_teach": bool,  # 透传给 is_teaching_intent
              "endpoint_hint": Optional[str],  # v0.34 端点语义提示
            }
    """
    t = (text or "").strip()
    if not t:
        return {
            "type": "non_teaching",
            "confidence": 0.0,
            "reason": "空输入",
            "raw": {"empty": True},
            "fallback_to_teach": fallback_to_teach,
            "endpoint_hint": endpoint_hint,
        }

    raw = {}

    # 1) affection：危机优先
    try:
        if is_affection_expression(t):
            return {"type": "affection", "confidence": 0.95,
                    "reason": "情绪/心理/人生困惑模式命中", "raw": {**raw, "detector": "is_affection_expression"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["affection_error"] = str(_e)

    # 2) composite：指令+资料
    try:
        if is_intent_with_material(t):
            return {"type": "composite", "confidence": 0.9,
                    "reason": "复合输入（指令+资料）命中", "raw": {**raw, "detector": "is_intent_with_material"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["composite_error"] = str(_e)

    # 3) meta：元问题
    try:
        if is_meta_question(t):
            return {"type": "meta", "confidence": 0.9,
                    "reason": "元问题模式命中", "raw": {**raw, "detector": "is_meta_question"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["meta_error"] = str(_e)

    # 4) greeting：寒暄
    try:
        if is_greeting(t):
            return {"type": "greeting", "confidence": 0.95,
                    "reason": "寒暄模式命中", "raw": {**raw, "detector": "is_greeting"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["greeting_error"] = str(_e)

    # 5) knowledge：库清点
    try:
        if is_knowledge_query(t):
            return {"type": "knowledge", "confidence": 0.9,
                    "reason": "知识库查询模式命中", "raw": {**raw, "detector": "is_knowledge_query"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["knowledge_error"] = str(_e)

    # 6) method：学习方法咨询
    try:
        if is_method_advice(t):
            return {"type": "method", "confidence": 0.85,
                    "reason": "学习方法咨询模式命中", "raw": {**raw, "detector": "is_method_advice"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["method_error"] = str(_e)

    # 7) problem：出题
    try:
        if is_problem_request(t):
            return {"type": "problem", "confidence": 0.85,
                    "reason": "出题意图模式命中", "raw": {**raw, "detector": "is_problem_request"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["problem_error"] = str(_e)

    # 7.5) v0.26 ⭐ LLM 综合意图判断（发挥 LLM 理解能力为原则）
    # 规则 1-7 都未命中时，让 LLM 结合语义综合判断意图（规则可能误判/漏判语境）
    try:
        if llm is not None:
            _llm_intent = _llm_route_intent(t, llm)
            if _llm_intent and _llm_intent != "teach":
                # LLM 明确是其他意图（answer/affection/knowledge/method/problem/meta/greeting/non_teaching）
                # 且规则未命中——信任 LLM 判断（发挥 LLM 能力），而非默认 teaching
                return {"type": _llm_intent, "confidence": 0.8,
                        "reason": f"LLM 综合意图判断为 {_llm_intent}（规则未命中，LLM 语义理解）",
                        "raw": {**raw, "detector": "_llm_route_intent"},
                        "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["llm_route_error"] = str(_e)

    # 8) teaching：LLM 兜底（不再静默）
    try:
        if is_teaching_intent(t, llm=llm, fallback_to_teach=fallback_to_teach):
            return {"type": "teaching", "confidence": 0.6,
                    "reason": "LLM 意图判断为教学意图", "raw": {**raw, "detector": "is_teaching_intent"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
        else:
            # LLM 明确非教学意图 → 直接 non_teaching（不再 fallback 教学）
            return {"type": "non_teaching", "confidence": 0.7,
                    "reason": "LLM 意图判断为非教学意图", "raw": {**raw, "detector": "is_teaching_intent"},
                    "fallback_to_teach": fallback_to_teach,
                    "endpoint_hint": endpoint_hint}
    except Exception as _e:
        raw["teaching_error"] = str(_e)
        # route() 自己兜底：若调用方愿意降级为教学，返回 teaching；
        # 否则返回 non_teaching（不再静默按教学处理）
        if fallback_to_teach:
            return {"type": "teaching", "confidence": 0.3,
                    "reason": f"LLM 异常且 fallback_to_teach=True: {_e}",
                    "raw": {**raw, "detector": "fallback"},
                    "fallback_to_teach": True,
                    "endpoint_hint": endpoint_hint}
        return {"type": "non_teaching", "confidence": 0.3,
                "reason": f"LLM 异常且 fallback_to_teach=False: {_e}",
                "raw": {**raw, "detector": "fallback"},
                "fallback_to_teach": False,
                "endpoint_hint": endpoint_hint}


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
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    # 清缓存以保证每次调用都跑到原路径（不依赖上一轮缓存）
    from meta_router import _INTENT_CACHE, _IS_INTENT_CACHE
    _INTENT_CACHE.clear()
    _IS_INTENT_CACHE.clear()
    tests = [
        "你能调用知识库吗",           # meta
        "你是谁",                     # meta
        "你能做什么",                 # meta
        "你叫什么名字",               # meta
        "什么是熵？",                 # teaching（LLM 兜底；model=None → non_teaching）
        "请解释一下光合作用",          # teaching
        "你能调用知识库来查一下勾股定理吗",  # meta
        "帮我讲讲欧拉公式",            # teaching（LLM 兜底）
        "你为什么叫Émile？",           # meta
        "物理学中的摩擦力怎么算",       # teaching
        "你好",                       # greeting
        "我最近好难过，撑不下去",       # affection
        "你的知识库里有什么",           # knowledge
        "怎么学好线性代数",             # method
        "给我出一道经典题目",           # problem
        "帮我看看这段代码有什么问题：\nprint('hi')",  # composite
    ]
    print("=== is_meta_question 回归 ===")
    for t in tests[:10]:
        print(f"{'PASS' if is_meta_question(t) else 'FAIL'} {t}")
    print("\n=== route() 集中分发（fallback_to_teach=True, llm=None） ===")
    for t in tests:
        _INTENT_CACHE.pop(t, None)  # 清当前条目，保证真实路径
        _IS_INTENT_CACHE.pop(t[:60], None)
        r = route(t, llm=None, fallback_to_teach=True)
        print(f"{r['type']:<12} | {r['reason']} | {t}")
    print("\n=== route() 默认（fallback_to_teach=False） ===")
    for t in tests:
        _INTENT_CACHE.pop(t, None)
        _IS_INTENT_CACHE.pop(t[:60], None)
        r = route(t)
        print(f"{r['type']:<12} | {r['reason']} | {t}")
