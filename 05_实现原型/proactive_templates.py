# -*- coding: utf-8 -*-
"""定时主动问候模板（v0.67 ⭐ Oracle 设计）

用户需求：用户在页面停留 5-10 分钟无操作时，智能体自动发一句话关心。
每个固定会话有 5-20 条对话模板字典，按时段/学科/idle 时长选一条。
"""
from __future__ import annotations

import random
from datetime import datetime

# 模板字典：学科 × idle 时长（short 5-8min / long 8+min）+ 晚间特例
PROACTIVE_TEMPLATES = {
    "通用": {
        "short_idle": [
            "在忙什么呀？有问题随时告诉我。",
            "卡住了吗？要不要换个思路看看？",
            "我刚想到一个相关点，你想听吗？",
            "看你一直没动，是休息一下还是需要帮忙？",
            "要不要我陪你过一遍刚才的内容？",
        ],
        "long_idle": [
            "离开很久啦，别忘了回来呀。",
            "我在这里等你，想继续随时说。",
            "要不要先休息一下？回来我们接着聊。",
            "今天的进度有点慢，我来帮你梳理下？",
            "我把刚才的思路总结了一下，看一眼？",
        ],
    },
    "数学": {
        "short_idle": [
            "这道题是不是卡在公式套用上了？",
            "要不要我先给你个提示？",
            "试试画出辅助线？",
            "我们先把定义再过一遍，可能会想通。",
        ],
        "long_idle": [
            "我们回到刚才那道题好吗？",
            "先看看定义，再用例子走一遍。",
        ],
    },
    "物理": {
        "short_idle": [
            "这个物理量是不是还没理清？",
            "要不要画个受力分析图？",
        ],
        "long_idle": [
            "我们回到刚才那个物理情景好吗？",
        ],
    },
    "语文": {
        "short_idle": [
            "这段文言文是不是卡在字词上了？",
            "要不要先疏通大意再细读？",
        ],
        "long_idle": [
            "我们回到刚才那篇文章好吗？",
        ],
    },
    "英语": {
        "short_idle": [
            "这个句型是不是还没掌握？",
            "要不要先看一个例句？",
        ],
        "long_idle": [
            "我们回到刚才那个语法点好吗？",
        ],
    },
    "晚上": {
        "通用": [
            "夜深了，别太晚，注意休息哦。",
            "明天还有精神吗？要不要先收个尾？",
            "今天学到这吧，记得复盘一下。",
            "学到这可以休息了，明天我在这里等你。",
        ],
    },
}

# 最近会话用过的模板（避免重复）
_used_per_session: dict = {}


def pick_template(subject: str = "通用", idle_ms: int = 0,
                  session_id: str = "", hour: int = None) -> str:
    """按 时段 × 学科 × idle 时长 选一条模板（避免重复）。"""
    hour = datetime.now().hour if hour is None else hour

    if hour >= 21 or hour < 6:
        pool = PROACTIVE_TEMPLATES["晚上"]["通用"]
    else:
        bucket = "long_idle" if idle_ms >= 8 * 60 * 1000 else "short_idle"
        pool = PROACTIVE_TEMPLATES.get(subject, PROACTIVE_TEMPLATES["通用"]).get(bucket, [])
        if not pool:
            pool = PROACTIVE_TEMPLATES["通用"][bucket]

    # 避免同一会话重复抽到同一句
    used = _used_per_session.get(session_id, set())
    candidates = [t for t in pool if t not in used]
    if not candidates:
        candidates = pool
        _used_per_session[session_id] = set()
    chosen = random.choice(candidates)
    used.add(chosen)
    _used_per_session[session_id] = used
    return chosen
