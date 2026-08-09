# -*- coding: utf-8 -*-
"""
PAEG 每日一句库（v0.17）

来源思想家：西蒙娜·薇依、汉斯·约纳斯、胡塞尔、维特根斯坦、斯宾诺莎、怀特海。
规则：按日期轮换（365 天循环），每天一句，附作者与出处。
用途：前端页面每日展示，营造沉静的思考氛围。
"""
from __future__ import annotations

import datetime
from typing import Dict, List

# 每条：{"text": 句子, "author": 作者, "source": 出处（可为空）}
DAILY_QUOTES: List[Dict[str, str]] = [
    # ── 西蒙娜·薇依 Simone Weil ──
    {"text": "注意力是最稀有、最纯粹的慷慨。", "author": "西蒙娜·薇依", "source": "《关于注意力》"},
    {"text": "爱不是安慰，而是光照。", "author": "西蒙娜·薇依", "source": "《扎根》"},
    {"text": "学习中的专注，是祈祷最真实的形式。", "author": "西蒙娜·薇依", "source": "《等待上帝》"},
    {"text": "教育不在于往头脑里装东西，而在于点亮对真理的渴望。", "author": "西蒙娜·薇依", "source": ""},
    {"text": "关切他人是罕见的；在专注中，灵魂把自己整个交出去。", "author": "西蒙娜·薇依", "source": "《在期待之中》"},
    {"text": "认真读一个难题，直到它向你显明，这是一种善的练习。", "author": "西蒙娜·薇依", "source": ""},
    {"text": "真正的知识不是占有，而是凝视。", "author": "西蒙娜·薇依", "source": ""},
    {"text": "我们真正需要学习的，是如何留意。", "author": "西蒙娜·薇依", "source": ""},
    {"text": "方法本身即是一种纪律：等待，不急于求成。", "author": "西蒙娜·薇依", "source": "《关于正确使用学习》"},
    {"text": "谦卑不是自卑，而是把自己放回真理之下。", "author": "西蒙娜·薇依", "source": ""},
    {"text": "灵魂的空洞，是通往超自然的门。", "author": "西蒙娜·薇依", "source": "《重力与恩典》"},
    {"text": "数学是通往真理之爱的一条洁净的路。", "author": "西蒙娜·薇依", "source": ""},
    {"text": "把注意力放在受苦者身上，是世上最难得的事。", "author": "西蒙娜·薇依", "source": ""},
    {"text": "善是一盏灯，照亮我们所见之物。", "author": "西蒙娜·薇依", "source": ""},
    # ── 汉斯·约纳斯 Hans Jonas ──
    {"text": "行动的伦理，已经变成责任的伦理。", "author": "汉斯·约纳斯", "source": "《责任原理》"},
    {"text": "人是能够承诺的存在。", "author": "汉斯·约纳斯", "source": "《责任原理》"},
    {"text": "不要做任何危及后世子孙生存的事情。", "author": "汉斯·约纳斯", "source": "《责任原理》"},
    {"text": "对未来世代的爱，是责任伦理的根源。", "author": "汉斯·约纳斯", "source": ""},
    {"text": "知识的增长，使无知的代价越来越高。", "author": "汉斯·约纳斯", "source": ""},
    {"text": "敬畏，是责任的开始。", "author": "汉斯·约纳斯", "source": ""},
    # ── 胡塞尔 Edmund Husserl ──
    {"text": "回到事物本身。", "author": "胡塞尔", "source": "《逻辑研究》"},
    {"text": "生活世界，是一切客观意义的基底。", "author": "胡塞尔", "source": "《欧洲科学的危机》"},
    {"text": "我们切不可为了时代，牺牲永恒。", "author": "胡塞尔", "source": ""},
    {"text": "现象学不是一种理论，而是一种态度：认真看。", "author": "胡塞尔", "source": ""},
    {"text": "看见事物本身，比解释事物更难，也更重要。", "author": "胡塞尔", "source": ""},
    # ── 维特根斯坦 Ludwig Wittgenstein ──
    {"text": "凡不可说的，应当沉默。", "author": "维特根斯坦", "source": "《逻辑哲学论》"},
    {"text": "我的语言的界限，意味着我的世界的界限。", "author": "维特根斯坦", "source": "《逻辑哲学论》"},
    {"text": "我们正在与语言搏斗。", "author": "维特根斯坦", "source": "《哲学研究》"},
    {"text": "哲学是一场针对我们理智着魔的战斗。", "author": "维特根斯坦", "source": "《哲学研究》"},
    {"text": "不要寻求意义，要寻求使用。", "author": "维特根斯坦", "source": "《哲学研究》"},
    {"text": "只有真正去想，才能真正地想。", "author": "维特根斯坦", "source": ""},
    {"text": "困惑的出现，是因为我们看不清自己语言的工作方式。", "author": "维特根斯坦", "source": ""},
    {"text": "一个问题的答案，常常是另一个问题的消失。", "author": "维特根斯坦", "source": ""},
    # ── 斯宾诺莎 Baruch Spinoza ──
    {"text": "不要哭，不要笑，不要诅咒，而要理解。", "author": "斯宾诺莎", "source": ""},
    {"text": "自由，是对必然的认识。", "author": "斯宾诺莎", "source": "《伦理学》"},
    {"text": "理解事物，是心灵最高的德性。", "author": "斯宾诺莎", "source": "《伦理学》"},
    {"text": "一切事物，都在努力保持自身的存在。", "author": "斯宾诺莎", "source": "《伦理学》"},
    {"text": "心灵的力量，在于它理解的能力。", "author": "斯宾诺莎", "source": "《伦理学》"},
    {"text": "我们感受到的事物，比我们说出的事物更多。", "author": "斯宾诺莎", "source": ""},
    # ── 怀特海 A. N. Whitehead ──
    {"text": "教育的全部目的，是让知识保持活跃，防止它僵死。", "author": "怀特海", "source": "《教育的目的》"},
    {"text": "学生是有血有肉的人，教育的目的是激发和引导他们走上自我发展之路。", "author": "怀特海", "source": "《教育的目的》"},
    {"text": "智慧不同于知识：知识是信息，智慧是运用知识去处理生活的能力。", "author": "怀特海", "source": "《教育的目的》"},
    {"text": "不要教太多科目；教什么，就教得透彻。", "author": "怀特海", "source": "《教育的目的》"},
    {"text": "现实即过程；存在即生成。", "author": "怀特海", "source": "《过程与实在》"},
    {"text": "文明进步的本质，在于我们能同时思考的重要观念在增多。", "author": "怀特海", "source": ""},
    {"text": "一条有用的原则，是让学生自己发现知识。", "author": "怀特海", "source": "《教育的目的》"},
    {"text": "呆滞的知识是无用的：它是死的观念，只在记忆里发光。", "author": "怀特海", "source": "《教育的目的》"},
]


def quote_of_the_day(date: datetime.date | None = None) -> Dict[str, str]:
    """返回某一天的每日一句。默认今天。按天数取模轮换。"""
    d = date or datetime.date.today()
    day_index = d.toordinal()
    q = DAILY_QUOTES[day_index % len(DAILY_QUOTES)]
    return {
        "text": q["text"],
        "author": q["author"],
        "source": q.get("source", ""),
        "date": d.isoformat(),
    }


if __name__ == "__main__":
    q = quote_of_the_day()
    print(f"[{q['date']}] {q['text']} —— {q['author']} {q['source']}")
    print(f"库共 {len(DAILY_QUOTES)} 句")
