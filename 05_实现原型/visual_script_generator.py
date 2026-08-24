# -*- coding: utf-8 -*-
"""
visual_script_generator.py — PAEG 数学可视化脚本生成器（v0.70+ §3.26）

流程：对话+轮询收集信息 → 生成 script.json（单一真相源）→ 校验修补 → 5 资产联动。
方法来源：3Blue1Brown 8 大原则 + manim_skill 社区库 + Oracle 设计。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# ─── 脚本系统提示词（注入 LLM，产出 script.json） ───
# §3.102 ⭐ Phase 0 概念拆解（Oracle 方案——用户反馈基变换视频未拆解概念）
# §3.103 ⭐ L1 沉思引导（灵活度最高层——交由 LLM 思考，非模板）
CONCEPT_DECOMPOSITION_SYSTEM_PROMPT = """先静下来沉思，把下面的数学主题彻底想清楚，再输出分析。

请按你自己的理解回答以下问题（不必拘泥固定格式，可自由组织）：
1. 这个概念的本质是什么？它"不是"什么（最容易混淆的相邻概念必须显式区分）？
2. 它的核心机制如何运作（比如是否需要"换一个视角→操作→换回"）？
3. 哪些具体例子能建立直觉？哪些是常见误区？
4. 如果要可视化，怎样的展示路径最能让人理解（从直觉到形式化）？

分析完再输出。输出用结构化文本（可含列表/小标题），但由你决定组织方式。"""


def _is_complex_topic(topic: str) -> bool:
    """启发式：是否触发概念拆解（短 + 抽象概念词）。"""
    if len(topic or "") > 12:
        return False
    _KWS = ("变换", "结构", "关系", "性质", "分解", "组成", "定义",
            "等价", "不变", "同构", "映射", "基", "坐标", "矩阵")
    return any(k in (topic or "") for k in _KWS)


def decompose_concept(llm, topic: str, audience: str = "高中") -> Optional[dict]:
    """Phase 0：概念拆解。返回教学骨架 JSON；失败返回 None（降级无拆解）。"""
    try:
        from subagents import _safe_chat
        _raw = _safe_chat(llm, CONCEPT_DECOMPOSITION_SYSTEM_PROMPT,
                          f"主题：{topic}\n受众：{audience}\n输出 JSON 拆解骨架。",
                          max_tokens=1500)
        if not _raw:
            return None
        _m = re.search(r'\{.*\}', _raw, re.S)
        return json.loads(_m.group(0)) if _m else None
    except Exception as _e:
        print(f"[concept_decompose] 失败: {_e}")
        return None


VISUAL_SCRIPT_SYSTEM_PROMPT = """你是 PAEG 数学可视化剧本设计师。你的唯一任务：把教学主题转化为一幕幕"可被忠实执行的"动画剧本，而不是直接写 Manim 代码。

# 先静下来沉思（§3.103 L1 ⭐ 灵活度最高层）
在动手写分镜前，先彻底想清楚：
1. 用户给的主题（可能是简单输入如"基变换"）本质是什么？它"不是"什么（如基变换≠线性变换，是同一向量不同基的表示）？
2. 要真正讲清这个概念，需要哪些关键展示（如基变换需展示"换进观察者视角→变换→换回"）？
3. 需要哪些公式（哪些数学表达能帮助理解）？
4. 需要哪些演示/动画（哪些例子/过程能建立直觉）？
想清楚后，再按下面的分镜铁律设计 scene。你的展示方案由你决定——不要被固定格式限制，但要忠于概念本质。

# 角色约束
- 你不写代码。你写的是"导演分镜"，由下游渲染器翻译为 Manim。
- 你遵循 3Blue1Brown 的叙事方法：直觉先于形式化、单一聚焦、空间承载含义。
- 你的输出必须严格符合下面的 JSON Schema；任何字段缺失或含义模糊都会被拒绝。

# 剧本铁律（违反任何一条都视为失败）
1. **渐进揭示**：前 2 个 scene 不允许出现任何数学公式（用文字/箭头/动效表达）；公式从第 3 个 scene 起逐步引入，并始终先出现几何对象，再出现符号。
2. **单一聚焦**：每个 scene 的 `concept` 字段是 4-12 字的名词短语；如果一个 scene 需要解释两个概念，必须拆成两个 scene。
3. **空间与颜色语义**：颜色必须来自 `visual_system.palette` 的语义绑定，不允许随机配色。同一个数学对象在所有 scene 中颜色一致。
4. **节奏**：每个 scene 时长 8-45 秒；`pause_after_sec` >= 1 秒，关键极限/收敛/翻转处 >= 3 秒；关键变换用 rate_func "linear" 或 "smooth"。
5. **文字最小化**：`on_screen_text` <= 8 个汉字；超过则拆景或改为 narration。
6. **动画构图**：每 scene 的 mobject 数量 3-7 个。
7. **回看锚点**：跨 scene 复用的对象（坐标轴、参考点）必须用相同 id。
8. **依赖显式**：scenes[i].prerequisites 列出学习本场景前需要掌握的 scene id（供思维导图）。
9. **钩子开头（§3.100 3B1B）**：第 1 个 scene 必须是"提问性图像/反直觉现象"钩子（如一个奇怪的图形、一个待解的谜题），激发好奇心——不是直接宣告主题。
10. **recap 结尾（§3.100 3B1B）**：最后一个 scene 必须回顾核心结论（narration 总结 1-2 句话 + 视觉重现关键图形），形成闭环。

# 输入上下文（由系统注入）
- 主题：{topic}
- 受众与学段：{audience}
- 目标时长：{duration_target_sec} 秒
- 风格：{style}（3blue1brown / chalkboard / minimal）
- 已知前置概念：{prerequisites}
- 核心直觉（用户提供）：{intuition}
- 学习目标：{objectives}

# 输出要求
1. 仅输出一个合法 JSON 对象，不要任何 Markdown 代码块包裹，不要解释文字。
2. 顶层字段：meta, narrative_arc, visual_system, scenes, qa_self_check。
3. scenes 长度按目标时长：240s ≈ 6-9 个 scene；90s ≈ 3-4 个。
4. scenes[].animations 的 t 是相对该 scene 起点的秒数，单调递增。
5. qa_self_check 必须诚实填写——不达标在 notes 说明并修改，不隐瞒。

# 失败自检
- 前 2 个 scene 有没有公式？→ 有则重写
- 每 scene 是否只讲一件事？→ 否则拆分
- 颜色是否一致且有数学含义？→ 否则重排 palette
- 关键处有无停顿？→ 否则增大 pause_after_sec
- 时长是否匹配目标（±15%）？→ 否则增删 scene
"""


def build_script_prompt(topic: str, audience: str, duration_target_sec: int,
                        style: str = "3blue1brown", prerequisites: str = "",
                        intuition: str = "", objectives: str = "") -> str:
    """组装脚本生成 user prompt（含系统提示词 + 输入上下文）。"""
    return VISUAL_SCRIPT_SYSTEM_PROMPT.format(
        topic=topic, audience=audience, duration_target_sec=duration_target_sec,
        style=style, prerequisites=prerequisites or "无明确前置",
        intuition=intuition or "（待生成）", objectives=objectives or "（待生成）",
    )


def generate_script(llm, topic: str, audience: str, duration_target_sec: int,
                    style: str = "3blue1brown", prerequisites: str = "",
                    intuition: str = "", objectives: str = "") -> Optional[dict]:
    """调用 LLM 生成 script.json。失败返回 None。"""
    try:
        from subagents import _safe_chat
        _sys = build_script_prompt(topic, audience, duration_target_sec,
                                   style, prerequisites, intuition, objectives)
        _usr = f"请为主题「{topic}」生成数学可视化剧本（目标时长 {duration_target_sec} 秒）。"
        _raw = _safe_chat(llm, _sys, _usr, max_tokens=4000)
        if not _raw:
            return None
        _m = re.search(r'\{.*\}', _raw, re.S)
        if not _m:
            return None
        _script = json.loads(_m.group(0))
        _script.setdefault("meta", {"id": f"vis_{int(time.time())}", "title": topic,
                                    "topic": topic, "audience": audience,
                                    "duration_target_sec": duration_target_sec,
                                    "style": style})
        return _script
    except Exception as _e:
        print(f"[visual_script] 生成失败: {_e}")
        return None


import re
import time

if __name__ == "__main__":
    # 示例：打印提示词
    print(build_script_prompt("导数与切线的几何直觉", "高中", 240)[:500])
