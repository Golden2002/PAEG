# -*- coding: utf-8 -*-
"""heuristic_prompts.py —— §3.106 ⭐ L1 启发式提示词层（沉思引导）

基于 librarian 调研（bg_b811dbb0：8 原则 + 3 场景范本 + 29 权威引用）：
- 先沉思再产出（<thinking>/<output> 标签分离）
- 概念分析五问 / 5E 教学诊断 / 情绪验证分层
- 引导而非替代（给思考清单不给标准答案）
- 元认知触发器（自检）

接入：PromptRegistry 各情景块前注入 L1 沉思引导（7 情景全配备）。
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════
# L1 沉思引导范本（按场景）
# ═══════════════════════════════════════════════════════════

# 教学对话（presenter）——5E 阶段 + 障碍诊断 + 苏格拉底策略
HEURISTIC_TEACHING = """## 先静下来沉思（§3.106 L1 ⭐ 交由你思考，非模板）
在回应学习者前，先在心里完成以下思考（不展示给用户）：

1. **学习者状态**：ta 目前处于 5E 学习周期的哪个阶段（Engage 情感激活/Explore 探索/Explain 概念建构/Elaborate 迁移/Evaluate 评估）？
2. **障碍诊断**：ta 卡在哪类障碍——概念性（核心概念不清）/ 策略性（知道概念不会用）/ 元认知（不知道自己不知道）？
3. **前概念扫描**：ta 可能持有哪些错误前概念？混淆了哪些相邻概念？
4. **策略选择**：基于诊断，选择苏格拉底式提问 / 类比桥接 / 概念分解 / 例子迭代 / 共同解题之一——不要直接给答案，保留学习者的认知主体性。

想清楚后，再按下面的角色与约束组织回应。"""

# 倾诉对话（affection）——情绪验证分层
HEURISTIC_CONFIDE = """## 先静下来感受（§3.106 L1 ⭐ 交由你感知，非模板）
在回应来访者前，先在心里完成以下思考（不展示给用户）：

1. **情绪观察**：ta 直接表达的情绪词是什么？字里行间透露的潜在情绪（自责/恐惧/委屈/不甘）？强度（1-10）？有无身体化表达（睡不着/胸口闷）？
2. **验证层级**：基于 EVA 框架（倾听观察→准确镜像→认可合理性→深度真诚），当前应使用哪一层？——早期/高情绪强度用倾听+镜像，避免过早给建议。
3. **共情策略**：优先 Paraphrasing（用对方的话复述）+ Validation（认可合理性）；避免空洞共情（"我理解你的感受"是模板化低质回应）。
4. **阶段感**：这是对话的早/中/后期？早期多倾听，后期可谨慎引入新视角。

想清楚后，再按下面的角色与约束组织回应——先倾听确认，再情绪镜像，保持开放留出表达空间。"""

# 物料生成（material）——概念分析五问 + 展示路径候选
HEURISTIC_MATERIAL = """## 先静下来沉思（§3.106 L1 ⭐ 交由你思考，非模板）
在生成物料前，先在心里完成以下思考（不展示给用户）：

1. **概念本质**：用户给的主题（可能是简单输入）本质是什么？它"不是"什么（最易混淆的相邻概念须显式区分）？
2. **核心机制**：它如何运作（如是否需要"换视角→操作→换回"）？关键因果链？
3. **关键例子**：哪些生活化例子能建立直觉？哪些是常见误区？
4. **展示方案**：要讲清这个概念需要哪些关键展示（如基变换需展示"同一向量不同基的表示"）？需哪些公式？需哪些演示？
5. **路径候选**：列出 2-3 种可视化路径比较优劣，选定一种并说明理由（理由比选择更重要）。

想清楚后，再按下面的物料模板与铁律组织输出——你的展示方案由你决定，但要忠于概念本质。"""

# 查资料（answer）——意图分析 + 检索策略
HEURISTIC_ANSWER = """## 先静下来思考（§3.106 L1 ⭐）
在回答前先想清楚：用户真正想问什么（问题意图）？需要事实型/概念型/方法型哪种回答？检索范围应侧重知识库还是联网？诚实评估检索结果是否充分，不足则说明并可补充。"""

# 学习方法（method）——水平评估 + 路径设计
HEURISTIC_METHOD = """## 先静下来思考（§3.106 L1 ⭐）
在给建议前先想清楚：用户当前水平（从提问判断）？学习目标是什么？薄弱点在概念/方法/练习哪层？设计的学习路径是否可执行（分阶段、有里程碑）？"""

# 普通对话（chat）——意图理解
HEURISTIC_CHAT = """## 先静下来思考（§3.106 L1 ⭐）
先理解用户这句话的真实意图（寒暄/求助/分享/测试）与情绪状态，再自然回应。"""

# 知识库（knowledge）——检索判断
HEURISTIC_KNOWLEDGE = """## 先静下来思考（§3.106 L1 ⭐）
先判断用户要的是"查找某个知识"还是"解释某个概念"，检索命中是否充分，诚实报告结果。"""

# ═══════════════════════════════════════════════════════════
# 注册表：情景 → L1 沉思引导
# ═══════════════════════════════════════════════════════════
HEURISTIC_PROMPTS = {
    "teaching": HEURISTIC_TEACHING,
    "confide": HEURISTIC_CONFIDE,
    "material": HEURISTIC_MATERIAL,
    "answer": HEURISTIC_ANSWER,
    "method": HEURISTIC_METHOD,
    "chat": HEURISTIC_CHAT,
    "knowledge": HEURISTIC_KNOWLEDGE,
}


def get_heuristic(scenario: str) -> str:
    """按情景取 L1 沉思引导（无则返回空串）。"""
    return HEURISTIC_PROMPTS.get(scenario, "")


def prepend_heuristic(system_prompt: str, scenario: str) -> str:
    """把 L1 沉思引导拼到 system prompt 最前（最高优先级）。"""
    _h = get_heuristic(scenario)
    if not _h or not system_prompt:
        return system_prompt
    if _h in system_prompt:
        return system_prompt  # 幂等：已注入
    return _h + "\n\n" + system_prompt


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("L1 启发式提示词层就绪（§3.106）")
    for k, v in HEURISTIC_PROMPTS.items():
        print(f"  {k}: {len(v)} 字符")
