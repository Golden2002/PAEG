# -*- coding: utf-8 -*-
"""学生状态机模拟器 v2 —— 15+ 轮教学流核心（动态响应，情况灵活多变）。

v2 强化（响应"教学流必须维持 15 轮以上，期间经历灵活多变的各种情况"）：
  1. 行为库扩充到 12+ 类（新增：确认复述/反例质疑/生活联想/跨学科/做题尝试/情绪波动/类比追问）
  2. 状态转移平滑：卡住不轻易放弃，而是换策略（问例子→问类比→问步骤→问为什么）
  3. 15+ 轮目标：round_limit 默认 18，状态机保证能撑到
  4. 行为选择加权随机 + 状态依赖：模拟真实学生的不确定性
  5. 理解-遗忘循环：学生时懂时不懂（学过 3 轮后仍可能回去问基础）
"""
from __future__ import annotations

import random
import re
from typing import Dict, List, Optional

# 行为库 v2：12 类行为，每类 2-4 个候选（话题无关模板 + {topic} 占位）
BEHAVIOR_POOL: Dict[str, List[str]] = {
    # ── 理解/求知类 ──
    "ask_confused": [
        "老师，{topic}到底是什么？我还是不太明白。",
        "刚才说的那部分我没听懂，能再讲一下吗？",
        "那个概念好抽象，我不太理解它的意思。",
    ],
    "ask_detail": [
        "那具体是怎么发生的？能说得详细一点吗？",
        "这一步是怎么推出来的？我不太清楚。",
        "为什么要这样？背后的原因是什么？",
    ],
    "ask_example": [
        "能给我举个生活中的例子吗？这样我好理解。",
        "有没有真实的事例？光说概念我记不住。",
        "你举的那个例子我还是有点模糊，能换个吗？",
    ],
    "ask_analogy": [
        "能用一个比喻来说吗？类比一下我就懂了。",
        "这就像什么？有没有类似的东西？",
        "能不能打个比方？",
    ],
    "ask_step": [
        "能一步一步讲吗？我跟着你的步骤走。",
        "第一步是什么？然后呢？",
        "别一下讲太多，一步步来。",
    ],
    "verify_rephrase": [
        "我理解得对吗？是不是就是……",
        "让我复述一下：……我这样理解对不对？",
        "那照这么说，{topic}其实就是……对吗？",
    ],
    "got_it_deepen": [
        "哦！这个我懂了！那接下来呢？",
        "明白了，那如果情况变一下会怎样？",
        "懂了懂了，这个可以再深入讲讲吗？",
    ],
    "apply_question": [
        "那这个在生活中有用吗？能举个例子吗？",
        "实际中怎么用？有真实的例子吗？",
        "如果遇到……的情况，应该怎么处理？",
    ],
    # ── 联想/拐题类 ──
    "tangent": [
        "等等，我突然想到……{tangent}",
        "那这个和{tangent}有关系吗？",
        "对了，{tangent}是怎么一回事？",
    ],
    "cross_subject": [
        "这和数学课上学的有没有关系？",
        "是不是和物理/化学里那个很像？",
        "我在别的课上也听过类似的，是同一个吗？",
    ],
    "life_assoc": [
        "我好像在生活中见过这个……是那个吗？",
        "昨天我看到一个东西，好像就和这有关？",
        "这和我们平时说的那个是不是一回事？",
    ],
    # ── 卡住/质疑类 ──
    "still_confused": [
        "我还是不太懂……能换一种说法吗？",
        "你刚才讲的我还是没明白，真的。",
        "不好意思老师，我还是不太理解，能再讲讲吗？",
    ],
    "counter_question": [
        "但是如果不是这种情况呢？那还成立吗？",
        "我想到一个反例，如果……那会怎样？",
        "会不会有例外？我觉得不一定吧？",
    ],
    "doubt_previous": [
        "等等，你刚才说的那个，我好像没跟上……",
        "前面那句再解释一下？我漏掉了。",
        "你之前说的和现在说的，我怎么觉得不一样？",
    ],
    # ── 做题/检验类 ──
    "try_problem": [
        "那让我做一道题试试？",
        "有没有练习题？我试试看自己会不会。",
        "出个题考考我吧！",
    ],
    "answer_check": [
        "我算出来是这个，对吗？",
        "答案是 X 吗？我有点不确定。",
        "我这样做对吗？你帮我看看。",
    ],
    # ── 情绪/状态类（15 轮后期）──
    "tired": [
        "老师，我有点听累了……能慢点吗？",
        "信息有点多，我脑袋有点乱。",
        "今天状态不太好，你能再说简单点吗？",
    ],
    "motivated": [
        "这个好有意思！再讲点！",
        "我觉得我好像喜欢上这个了，还能学什么？",
        "懂了之后感觉好有成就感！",
    ],
    "closing": [
        "好的，我明白了，谢谢老师！",
        "差不多了，今天学到这里吧，谢谢。",
        "谢谢老师，我回去再看看笔记。",
    ],
}

# 拐题候选池（通用 + 每话题可覆盖）
TANGENT_POOL: List[str] = [
    "那和这个相反的情况会怎样？",
    "这和另一门课学的有没有关系？",
    "是不是有个历史故事和这个有关？",
    "那如果条件变了，结论还成立吗？",
    "我记得好像有个科学家研究过这个？",
    "那在太空里这个还成立吗？",
]


class StudentSimulator:
    """学生状态机 v2：15+ 轮教学流，行为灵活多变。"""

    # 状态转移权重表：当前状态 → 各行为的概率
    STATE_WEIGHTS = {
        # start → 开场
        "start": {"ask_confused": 1.0},
        # 探索/好奇：多问、多联想
        "curious": {"ask_detail": 0.25, "ask_example": 0.15, "tangent": 0.2,
                    "cross_subject": 0.1, "life_assoc": 0.1, "verify_rephrase": 0.1,
                    "got_it_deepen": 0.05, "ask_confused": 0.05},
        # 困惑：要例子/类比/步骤/换说法
        "confused": {"ask_example": 0.2, "ask_analogy": 0.2, "ask_step": 0.2,
                     "still_confused": 0.15, "ask_detail": 0.15, "verify_rephrase": 0.1},
        # 卡住：轮番换策略，不轻易放弃
        "stuck": {"ask_analogy": 0.2, "ask_step": 0.2, "ask_example": 0.15,
                  "counter_question": 0.1, "doubt_previous": 0.1,
                  "still_confused": 0.15, "tired": 0.05, "ask_detail": 0.05},
        # 理解了：深入/应用/做题/确认
        "got_it": {"got_it_deepen": 0.3, "apply_question": 0.2, "try_problem": 0.2,
                   "verify_rephrase": 0.15, "answer_check": 0.1, "motivated": 0.05},
        # 应用/做题阶段
        "applying": {"try_problem": 0.25, "answer_check": 0.25, "apply_question": 0.2,
                     "ask_detail": 0.1, "got_it_deepen": 0.1, "motivated": 0.1},
        # 疲惫但坚持
        "fatigued": {"tired": 0.25, "ask_example": 0.15, "ask_step": 0.15,
                     "still_confused": 0.15, "verify_rephrase": 0.15,
                     "motivated": 0.1, "closing": 0.05},
        # 收尾
        "done": {"closing": 1.0},
    }

    def __init__(self, topic: str, behavior_pool: Optional[Dict[str, List[str]]] = None,
                 profile: str = "中等理解力，易联想，抽象概念易卡，但好奇好学",
                 round_limit: int = 18):
        self.topic = topic
        self.pool = behavior_pool or BEHAVIOR_POOL
        self.profile = profile
        self.state = "start"
        self.round = 0
        self.stuck_count = 0
        self.got_count = 0
        self.apply_count = 0
        self.round_limit = round_limit  # 15+ 轮目标
        self._tangent_used: set = set()
        self._last_reply: str = ""
        self._consecutive_repeat = 0
        self._behavior_history: List[str] = []  # 已用行为（避免连续重复）

    # ── 工具 ──
    def _fill(self, template: str) -> str:
        return template.replace("{topic}", self.topic).replace("{tangent}", self._pick_tangent())

    def _pick_tangent(self) -> str:
        available = [t for t in TANGENT_POOL if t not in self._tangent_used]
        if not available:
            self._tangent_used.clear()
            available = TANGENT_POOL
        t = random.choice(available)
        self._tangent_used.add(t)
        return t

    def _weighted_choice(self, state: str) -> str:
        """按状态权重表选行为（避免连续重复同一行为）。"""
        weights = self.STATE_WEIGHTS.get(state, self.STATE_WEIGHTS["curious"])
        # 过滤掉最近 2 轮已用的行为（避免死循环复读）
        recent = set(self._behavior_history[-2:])
        candidates = {k: w for k, w in weights.items() if k not in recent}
        if not candidates:
            candidates = weights
        # 加权随机
        items = list(candidates.items())
        total = sum(w for _, w in items)
        r = random.uniform(0, total)
        acc = 0
        for name, w in items:
            acc += w
            if r <= acc:
                return name
        return items[0][0]

    def _analyze_reply(self, reply: str) -> Dict[str, bool]:
        """分析 AI 回复特征（驱动状态转移）。"""
        reply = reply or ""
        return {
            "long": len(reply) > 200,
            "detailed": bool(re.search(r"[0-9一二三]|[比如例如|因为|所以|步骤|首先|然后]", reply)),
            "offered_example": bool(re.search(r"比如|例如|想象|类比|就像|生活", reply)),
            "offered_step": bool(re.search(r"第一步|首先|然后|接着|最后|步骤", reply)),
            "asked_back": bool(re.search(r"明白|理解|跟上|清楚|懂了吗|是不是", reply)),
            "repetitive": self._detect_repetition(reply),
            "impatient": bool(re.search(r"我(刚才|已经|之前)说|再(听|看)一遍|这是", reply)),
            "deep": bool(re.search(r"深入|扩展|进阶|进一步|原理|本质", reply)),
        }

    def _detect_repetition(self, reply: str) -> bool:
        """相邻回复相似度（复读机信号）。"""
        if not self._last_reply:
            self._last_reply = reply
            return False
        a, b = self._last_reply[:300], reply[:300]
        common = sum(1 for i in range(0, min(len(a), len(b)) - 10) if a[i:i+10] in b)
        sim = common / max(1, min(len(a), len(b)) - 10)
        self._last_reply = reply
        if sim > 0.5:
            self._consecutive_repeat += 1
        else:
            self._consecutive_repeat = 0
        return sim > 0.5

    # ── 核心：状态转移 + 行为选择 ──
    def next_input(self, last_ai_reply: str = "") -> Optional[str]:
        """根据 AI 回复 + 状态机决定学生下一步。

        保证 15+ 轮：状态转移平滑，卡住换策略而非放弃；理解后进入应用/深入/做题循环。
        """
        self.round += 1
        if self.state == "done":
            return None

        # 开场
        if self.round == 1:
            self.state = "curious"
            self._behavior_history.append("ask_confused")
            return f"老师，{self.topic}是什么？我之前听过但没太懂。"

        feats = self._analyze_reply(last_ai_reply)

        # ── 状态转移逻辑（核心：模拟真实学生 15+ 轮的动态变化）──
        # 1. AI 不耐烦/复读 → 学生更困惑（压力升级，但换策略而非放弃）
        if feats.get("impatient") or feats.get("repetitive"):
            self.stuck_count += 1
            self.state = "stuck"
            if self._consecutive_repeat >= 3:
                # 连续 3 次复读 → 学生表达不满/想放弃（暴露耐心缺陷）
                self.state = "fatigued"
                return self._fill(random.choice(self.pool["tired"]))
            # 换策略（问例子/类比/步骤）
            choice = random.choice(["ask_example", "ask_analogy", "ask_step"])
            self._behavior_history.append(choice)
            return self._fill(random.choice(self.pool[choice]))

        # 2. 学生持续困惑（stuck_count 累积）→ 换说法，不放弃
        if self.stuck_count >= 2:
            # 交替用：反例质疑 / 换例子 / 步骤
            choice = random.choice(["counter_question", "ask_example", "ask_step", "doubt_previous"])
            self.state = "stuck"
            self._behavior_history.append(choice)
            return self._fill(random.choice(self.pool[choice]))

        # 3. 随机联想/拐题（15+ 轮需多次出现）
        if self.round >= 3 and random.random() < 0.25:
            self.state = "curious"
            choice = random.choice(["tangent", "cross_subject", "life_assoc"])
            self._behavior_history.append(choice)
            return self._fill(random.choice(self.pool[choice]))

        # 4. AI 给了例子/步骤/详细 → 学生有概率"懂了"
        if feats.get("offered_example") or feats.get("offered_step") or feats.get("detailed"):
            roll = random.random()
            if roll < 0.35:
                self.state = "got_it"
                self.got_count += 1
                if self.got_count >= 2:
                    # 懂了两轮 → 进入应用/做题阶段
                    self.state = "applying"
                    self.apply_count += 1
                    choice = random.choice(["try_problem", "apply_question", "got_it_deepen"])
                    self._behavior_history.append(choice)
                    return self._fill(random.choice(self.pool[choice]))
                choice = random.choice(["got_it_deepen", "verify_rephrase"])
                self._behavior_history.append(choice)
                return self._fill(random.choice(self.pool[choice]))
            elif roll < 0.65:
                # 仍困惑（抽象点还是卡）
                self.stuck_count += 1
                self.state = "confused"
                choice = random.choice(["still_confused", "ask_example", "ask_analogy"])
                self._behavior_history.append(choice)
                return self._fill(random.choice(self.pool[choice]))
            else:
                # 验证理解
                self._behavior_history.append("verify_rephrase")
                return self._fill(random.choice(self.pool["verify_rephrase"]))

        # 5. 理解-遗忘循环：学过 5+ 轮后，仍可能回去问基础（模拟遗忘）
        if self.round >= 5 and self.got_count >= 1 and random.random() < 0.15:
            self.state = "confused"
            self._behavior_history.append("doubt_previous")
            return self._fill(random.choice(self.pool["doubt_previous"]))

        # 6. 疲惫（15 轮左右出现）
        if self.round >= 14 and random.random() < 0.3:
            self.state = "fatigued"
            self._behavior_history.append("tired")
            return self._fill(random.choice(self.pool["tired"]))

        # 7. 默认：按状态权重选
        choice = self._weighted_choice(self.state)
        self._behavior_history.append(choice)
        if choice == "closing":
            self.state = "done"
        return self._fill(random.choice(self.pool[choice]))

    def should_end(self) -> bool:
        """是否结束：达轮次上限（15+ 目标）或学生明确收尾。"""
        if self.round >= self.round_limit:
            self.state = "done"
            return True
        return self.state == "done"


if __name__ == "__main__":
    # 自测：验证能跑 15+ 轮且行为多变
    s = StudentSimulator("光合作用")
    reply = "我来讲讲光合作用：叶绿体吸收光能，把 CO₂ 和水变成有机物和氧气。你明白了吗？"
    behaviors_seen = set()
    rounds_ran = 0
    for i in range(25):
        inp = s.next_input(reply)
        if inp is None or s.should_end():
            break
        rounds_ran += 1
        # 记录行为（从发言推断）
        for bname in BEHAVIOR_POOL:
            if any(t.replace("{topic}", "光合作用").replace("{tangent}", "") in inp for t in BEHAVIOR_POOL[bname]):
                behaviors_seen.add(bname)
                break
        # 模拟 AI 正常回复（多样化：有时详细、有时简短、有时反问）
        replies = [
            "这里我用类比：就像给手机充电，光反应把能量存进 ATP 电池，暗反应再用电池制造有机物。",
            "我们一步步来：第一步光反应在类囊体，第二步暗反应在基质。先跟上前一步。",
            "举个例子：植物晒太阳能长高，就是因为光合作用在制造养分。你想到什么？",
            "这个问题很好！其实这涉及到叶绿素吸收光谱，我可以展开讲。",
            "你理解得方向对了，我再补充一个细节：氧气其实来自水的分解。",
            "嗯。",
            "对，就是这样。你还有什么疑问吗？",
            "你可以试着做这道题：光照强度对光合速率的影响曲线怎么分析？",
            "这个问题和呼吸作用有关联，我们下次会讲，你先记住光合是储能。",
            "我理解你的困惑，很多学生在这里都会卡住，我们再换个角度。",
        ]
        reply = replies[i % len(replies)]
    print(f"=== 状态机自测：跑了 {rounds_ran} 轮 ===")
    print(f"出现的行为类型 ({len(behaviors_seen)}): {sorted(behaviors_seen)}")
    print(f"目标 15+ 轮: {'✅' if rounds_ran >= 15 else '❌'}")
