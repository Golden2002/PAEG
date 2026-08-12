# -*- coding: utf-8 -*-
"""Manim 教学动画速度规范（v0.65 ⭐ 三档分级制，固定化标准）

用户需求：不同模块速度不同——重复动作可稍快、关键部分放慢，
统一速度不符合要求。本规范基于 Manim 社区 pacing 最佳实践
（browser-use/video-use + rohitg00/manim-video-generator + adithya-s-k/manim_skill
+ Manim 官方 DEFAULT_ANIMATION_RUN_TIME=1.0）：

三档分级：
- 快速 QUICK：重复动作（循环移动/逐步演示/辅助变换）0.8-1.5s
- 中速 NORMAL：中间态（普通 Transform/写公式/过渡）1.5-2.0s
- 慢速 KEY：关键部分（标题/结论/推导核心/Aha 时刻）2.5-4.0s
黄金法则：每个 play 后必须有 wait——观众需要"读→联系→预期"三步。
节奏变化：同场景内快慢交替（铺垫慢、辅助快、结论最慢），禁全程一致。
"""

# ── 三档速度常量 ─────────────────────────────────
QUICK_RUN = 1.2        # 快速：重复动作/循环移动/辅助变换（0.8-1.5s 区间）
QUICK_WAIT = 0.4       # 快速后小停顿

NORMAL_RUN = 1.8       # 中速：普通 Transform/写公式/过渡（1.5-2.0s 区间）
NORMAL_WAIT = 0.8      # 中速后观察

KEY_RUN = 3.0          # 慢速：标题/结论/推导核心（2.5-4.0s 区间）
KEY_WAIT = 2.0         # 关键后留白

AHA_RUN = 2.5          # Aha 时刻动画
AHA_WAIT = 3.0         # Aha 后最长留白（戏剧性停顿）

CREATE_RUN = 1.8       # 元素创建（Create/Write/FadeIn）→ 中速
HOLD_WAIT = 1.0        # 创建后观察

TITLE_RUN = 2.5        # 标题展示（关键，慢）
TITLE_WAIT = 2.0

END_WAIT = 3.0         # 结尾留白
MID_WAIT = 0.6         # 分段间小停顿

# ── 给 LLM 的速度规范文本（注入 manim_prompts 与 manim_service）─────
_SPEED_STANDARD_TEXT = """
【速度规范（三档分级固定标准，必须遵守，用户不需要再调速度）】
档位1 快速（重复动作）：run_time=1.2，步间 wait=0.4 —— 循环移动/逐步演示/辅助变换
档位2 中速（中间态）：run_time=1.8，后 wait=0.8 —— 普通 Transform/写公式/过渡
档位3 慢速（关键部分）：run_time=3.0，后 wait=2.0 —— 标题/结论/推导核心
Aha 时刻：run_time=2.5 + wait=3.0（戏剧性停顿，揭示关键洞察）
黄金法则：每个 self.play() 后必须跟 self.wait()——观众需要"读→联系→预期"
节奏变化：同一场景内快慢交替（铺垫慢、辅助细节快、结论最慢），禁止全程同一速度
禁止：run_time<0.5（快闪看不清）与 run_time>4.0（拖沓）
"""
