"""
PAEG 教学策略库（v0.9）

基于教学法理论（苏格拉底/布鲁姆/掌握学习/支架式ZPD/费曼/刻意练习），
为 Planner 提供"诊断 → 策略选择 → 教学步骤"的规则。

来源：EEF 教学法工具包、Bloom 修订版(2001)、Vygotsky ZPD、Ericsson 刻意练习、
      ChatGPT Study Mode 分级支架等（详见 intermediate/03_自我反思与优化计划.md）
"""

from __future__ import annotations

# Bloom 认知层级
BLOOM_LEVELS = ["remember", "understand", "apply", "analyze", "evaluate", "create"]

# 学科 → 默认 Bloom 起点（概念性学科偏理解，技能性偏应用）
_SUBJECT_BLOOM_BASE = {
    # 概念性/文科：重理解与分析
    "literature": "analyze", "chinese": "analyze", "history": "analyze",
    "philosophy": "analyze", "aesthetics": "evaluate", "ethics": "evaluate",
    "phenomenology": "understand", "politics": "understand",
    # 理科：理解→应用
    "physics": "apply", "math": "apply", "chemistry": "apply", "biology": "understand",
    "geography": "understand",
    # 语言/技能：应用为主
    "english": "apply", "french": "apply", "german": "apply", "japanese": "apply",
    "coding": "create", "writing": "create", "thinking": "analyze",
    "learning": "apply", "expression": "apply",
    # 考研：应用/分析
    "math": "apply", "politics": "analyze",
    "default": "understand",
}

# 策略定义
STRATEGIES = {
    "socratic": {
        "name": "苏格拉底式",
        "when": "学生已有一定基础（理解≥60%）且目标是分析/评价等高阶思维；或学生已懂但讲不清",
        "steps": [
            {"type": "question", "topic": "引问：先让学生说出自己的想法", "bloom": "analyze"},
            {"type": "question", "topic": "追问：请举例/找反例/说明依据", "bloom": "analyze"},
            {"type": "guide", "topic": "收敛：引导学生自己总结", "bloom": "evaluate"},
        ],
        "presenter_hint": "先抛一个开放问题让学生开口，用'你怎么看''依据是什么''能举个反例吗'追问，最后让学生自己总结。不要直接给答案。",
    },
    "scaffolded": {
        "name": "支架式（ZPD）",
        "when": "学生完全陌生或基础薄弱（理解<40%）；或全新概念",
        "steps": [
            {"type": "present", "topic": "示范：用最小例子讲清核心", "bloom": "understand"},
            {"type": "present", "topic": "带做：拆成小步，每步一个小问题", "bloom": "apply"},
            {"type": "practice", "topic": "放手：给一个相似问题让学生独立做", "bloom": "apply"},
        ],
        "presenter_hint": "先示范最小例子，再拆成小步带着做，最后让学生独立做一个相似的。学生卡住时给更小的台阶，不直接给答案。",
    },
    "mastery": {
        "name": "掌握式",
        "when": "知识/技能基础课（数学/语法/科学事实）；评估显示未达80%",
        "steps": [
            {"type": "present", "topic": "精讲：一个核心目标，讲透", "bloom": "understand"},
            {"type": "practice", "topic": "小测：5-7 题形成性测验", "bloom": "apply"},
            {"type": "feedback", "topic": "矫正：针对错题再教一遍", "bloom": "apply"},
        ],
        "presenter_hint": "一次聚焦一个目标；小测后针对错题矫正；掌握达标才进下一步。",
    },
    "feynman": {
        "name": "费曼式",
        "when": "学生说'我懂但说不出来'；或复盘巩固阶段",
        "steps": [
            {"type": "question", "topic": "请学生用最简单的话讲一遍", "bloom": "understand"},
            {"type": "feedback", "topic": "找漏洞：哪里用了行话/逻辑跳了", "bloom": "analyze"},
            {"type": "guide", "topic": "回到原文补缺口，再讲一遍", "bloom": "understand"},
        ],
        "presenter_hint": "让学生当老师：用最朴素的话讲给'10岁小孩'听；你帮他找哪里讲不明白；让他补上再讲。",
    },
    "deliberate": {
        "name": "刻意练习",
        "when": "程序性技能（计算/代码/语法）；学生说'我一做就错'",
        "steps": [
            {"type": "present", "topic": "要点：明确这步要练什么", "bloom": "understand"},
            {"type": "practice", "topic": "练习：同型题反复练，每题即时反馈", "bloom": "apply"},
            {"type": "practice", "topic": "变式：换数字/换情境，防止死记", "bloom": "apply"},
        ],
        "presenter_hint": "目标明确、即时反馈、重复加变式。每题评'对/错+原因+下一步'。",
    },
    "default": {
        "name": "综合式",
        "when": "默认",
        "steps": [
            {"type": "present", "topic": "直观讲解", "bloom": "understand"},
            {"type": "present", "topic": "形式定义/方法", "bloom": "understand"},
            {"type": "practice", "topic": "应用与反思", "bloom": "apply"},
        ],
        "presenter_hint": "从具体例子切入，讲清是什么/为什么/怎么用，最后让学生自己验证一下。",
    },
}


def choose_strategy(learner, diagnosis: dict, subject: str) -> dict:
    """根据诊断+学科选择教学策略。"""
    # 1. 学科默认 Bloom 起点
    base_bloom = _SUBJECT_BLOOM_BASE.get(subject, _SUBJECT_BLOOM_BASE["default"])

    # 2. 从诊断读取学生状态
    depth = diagnosis.get("recommended_depth", "moderate")  # basic/moderate/advanced
    gaps = diagnosis.get("identified_gaps", []) or []
    prereq_status = diagnosis.get("prerequisites_status", {})
    has_gaps = len(gaps) > 0

    # 3. 策略选择规则（按优先级）
    strategy_key = "default"
    if has_gaps and not prereq_status:
        strategy_key = "scaffolded"      # 有缺口且无前置 → 支架式
    elif depth == "basic":
        strategy_key = "scaffolded"      # 基础差 → 支架式
    elif base_bloom in ("analyze", "evaluate", "create"):
        strategy_key = "socratic"        # 高阶目标 → 苏格拉底
    elif subject in ("math", "physics", "chemistry", "coding", "english",
                     "french", "german", "japanese"):
        strategy_key = "mastery"         # 技能/理科 → 掌握式（含练习）
    elif subject in ("thinking", "writing"):
        strategy_key = "feynman"         # 表达/思考 → 费曼
    elif depth == "advanced":
        strategy_key = "socratic"

    # 4. 画像驱动（v0.69+ §3.12：让 17 维学习者画像真正驱动策略——此前 learner 参数未使用）
    # 仅补充默认场景（不覆盖上方 diagnosis 主规则：诊断优先、画像兜底）
    try:
        _gl = str(getattr(learner, "grade_level", "") or "") if learner else ""
        _cs = str(getattr(learner, "cognitive_style", "") or "") if learner else ""
        _tm = getattr(learner, "target_exam", None) if learner else None
        if strategy_key == "default":
            if _gl == "graduate_exam":
                strategy_key = "socratic"          # 考研：深度优先
            elif _gl in ("middle_school", "high_school") and subject in (
                    "math", "physics", "chemistry", "coding"):
                strategy_key = "mastery"           # 初高中技能学科：练习优先
            elif _tm:
                strategy_key = "socratic"          # 有目标考试：深度备考
        if strategy_key == "default" and _cs:
            _cs_l = str(_cs).lower()
            if any(k in _cs_l for k in ("具体", "实例", "视觉", "concrete", "visual", "经验")):
                strategy_key = "scaffolded"        # 具体/实例偏好：支架式（多例子）
    except Exception:
        pass

    return {**STRATEGIES[strategy_key], "key": strategy_key, "base_bloom": base_bloom}


def build_plan_steps(strategy: dict, concept: str, tone: str, bloom_level: str = None) -> list:
    """根据策略生成教学步骤（与世界观语气联动），每个 step 携带策略提示。

    v0.15：topic 明确标注"本步阶段"（第1步直觉/第2步机制/第3步应用/辨析），
    避免三步都讲同一个概念导致重复。
    """
    steps = []
    hint = strategy.get("presenter_hint", "")
    n = len(strategy["steps"])
    for i, s in enumerate(strategy["steps"], 1):
        # 阶段名：按步骤类型和序号生成差异化话题
        stage = s.get("topic", "讲解")
        if "{concept}" in stage:
            topic = stage.replace("{concept}", concept)
        else:
            # 给话题加"阶段后缀"，明确每步的推进方向
            if i == 1 and n > 1:
                topic = f"{stage}：{concept}（本步讲直觉和现象）"
            elif i == n:
                topic = f"{stage}：{concept}（本步讲应用/辨析/练习，不重复前两步）"
            else:
                topic = f"{stage}：{concept}（本步讲机制和定义，在上一步基础上深入）"
        steps.append({
            "step_id": i,
            "type": s["type"],
            "topic": topic,
            "duration_min": 3 if s["type"] in ("present", "guide") else 2,
            "worldview": tone,
            "strategy": strategy["key"],
            "bloom": s.get("bloom", bloom_level or "understand"),
            "tools_to_use": ["search_subject_kb"],
            "expected_outcome": f"完成：{s['topic']}",
            "strategy_hint": hint,  # 注入教学策略提示（Presenter 读取）
        })
    return steps


# §3.62 ⭐ LLM 动态教学规划：策略知识库作为参考（非强制模板）
PLANNER_SYSTEM_PROMPT = """你是教学规划专家。根据学生完整上下文，动态生成教学步骤计划。

## 学生上下文
- 学段/年级：{grade}
- 学科：{subject}
- 认知风格：{cognitive_style}
- 掌握度/薄弱点：{mastery}
- 诊断：depth={depth}, gaps={gaps}
- 请求类型：{request_type}
{teach_state_section}
{action_section}

## 策略知识库（参考，可自由组合，非强制模板）
- 苏格拉底式：高阶思维、学生有基础 → 引问/追问/收敛
- 支架式（ZPD）：完全陌生/基础薄弱 → 示范/带做/放手
- 掌握式：技能/理科 → 示范/练习/反馈
- 费曼式：学生能讲但讲不清 → 让学生复述/纠偏
- 综合式：默认 → 按内容动态组合

## 规划要求
1. **步数动态**：逐句/逐条讲解时，每内容单元一步（如《将进酒》每句一步）；新主题 3-5 步；深入 5+ 步
2. **续讲时**：必须从已讲进度之后继续（讲第 N+1 句/下一段），不重复已讲
3. 每步 topic 具体（≤50字）、bloom 递进、duration 合理
4. 输出严格 JSON（无 markdown 包裹）：
{{"strategy": "...", "strategy_name": "...", "base_bloom": "...", "presenter_hint": "≤80字", "rationale": "≤100字", "steps": [{{"step_id": 1, "type": "present|question|guide|practice|feedback", "topic": "≤50字", "bloom": "remember|understand|apply|analyze|evaluate|create", "duration_min": 1-5, "tools_to_use": ["search_subject_kb"], "expected_outcome": "≤30字", "worldview": "balanced"}}]}}"""


def validate_plan(plan: dict) -> bool:
    """§3.62 ⭐ 校验 LLM 生成的 plan（防幻觉）：非法则调用方回退静态。"""
    try:
        steps = plan.get("steps") or []
        if not isinstance(steps, list) or not steps or len(steps) > 20:
            return False
        valid_types = {"present", "question", "guide", "practice", "feedback"}
        valid_blooms = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                return False
            if s.get("step_id") != i + 1:
                return False
            if s.get("type") not in valid_types:
                return False
            if s.get("bloom") not in valid_blooms:
                return False
            topic = s.get("topic") or ""
            if not topic or len(topic) > 100:
                return False
            d = s.get("duration_min", 3)
            if not isinstance(d, int) or not (1 <= d <= 10):
                return False
        return True
    except Exception:
        return False
