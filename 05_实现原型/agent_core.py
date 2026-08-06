"""
PAEG 智能体基础架构层（v0.10）

参照 opencode / codex 等通用 agent 的基础设计，为 PAEG 提供：
1. ToolRegistry —— 工具注册与调用（agent 的能力边界）
2. AgentLoop  —— 统一的"感知 → 规划 → 行动 → 反思"主循环
3. ContextManager —— 上下文组装（系统上下文 + 用户画像 + 会话历史）

设计原则：
- 教学专用逻辑（五子代理）仍然在 paeg.py，这里提供的是通用 agent 骨架
- 可测试、可扩展：新能力=注册新工具；新场景=用 AgentLoop 跑
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 1. Tool Registry（工具注册表）
# ============================================================

@dataclass
class Tool:
    """一个工具的定义。"""
    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any] = field(default_factory=dict)  # JSON Schema 风格
    enabled: bool = True

    def run(self, **kwargs) -> Any:
        if not self.enabled:
            raise RuntimeError(f"Tool '{self.name}' is disabled")
        try:
            result = self.func(**kwargs)
            return {"ok": True, "name": self.name, "result": result}
        except Exception as e:
            return {"ok": False, "name": self.name, "error": str(e)}


class ToolRegistry:
    """工具注册表：按名注册/查找/列出工具。"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list(self) -> List[dict]:
        return [
            {"name": t.name, "description": t.description,
             "parameters": t.parameters, "enabled": t.enabled}
            for t in self._tools.values()
        ]

    def run(self, name: str, **kwargs) -> dict:
        tool = self.get(name)
        if tool is None:
            return {"ok": False, "name": name, "error": f"Unknown tool: {name}"}
        return tool.run(**kwargs)


# ============================================================
# 2. Context Manager（上下文管理）
# ============================================================

@dataclass
class AgentContext:
    """Agent 一次执行的完整上下文。"""
    session_id: str
    user_id: str
    system_context: str = ""          # 系统级上下文（模型/版本等）
    user_description: str = ""        # 用户自我描述（注入画像）
    learner_profile: dict = field(default_factory=dict)  # 画像摘要
    history: List[dict] = field(default_factory=list)    # 会话历史
    memory: Dict[str, Any] = field(default_factory=dict)  # 临时记忆
    meta: Dict[str, Any] = field(default_factory=dict)    # 元数据（token/耗时）


class ContextManager:
    """组装发送给 LLM 的上下文。"""

    def __init__(self, max_history: int = 20):
        self.max_history = max_history

    def build_system(self, ctx: AgentContext, extra: str = "") -> str:
        """把用户画像 + 系统上下文组装成 system prompt 基础段。"""
        parts = [ctx.system_context]
        if ctx.user_description:
            parts.append(
                f"\n## 关于这位学生（TA 自己描述的，请始终尊重并据此教学）\n{ctx.user_description}"
            )
        if ctx.learner_profile:
            parts.append(f"\n## 学习者画像摘要\n{json.dumps(ctx.learner_profile, ensure_ascii=False)}")
        if ctx.memory.get('user_model'):
            # v0.11：从对话中学习的动态用户模型（对象意识）
            parts.append(
                f"\n## 我观察到这位学生（来自对话，不是 TA 自己说的）\n"
                f"{json.dumps(ctx.memory['user_model'], ensure_ascii=False)}"
            )
        if extra:
            parts.append(extra)
        return "\n".join(parts)

    def build_history(self, ctx: AgentContext) -> List[dict]:
        """返回会话历史（截断到 max_history）。"""
        return ctx.history[-self.max_history:]


def infer_user_model(history: List[dict], description: str = "") -> Dict[str, Any]:
    """v0.11：从会话历史 + 自我描述推断用户特征（对象意识）。

    返回可注入 prompt 的用户模型摘要。规则简单、确定性，不依赖 LLM。
    """
    model: Dict[str, Any] = {
        "expression_style": "neutral",     # 表达风格
        "knowledge_hints": [],             # 知识水平线索
        "emotional_state": "neutral",      # 情绪状态
        "difficulty_signals": [],          # 常见困难信号
        "engagement": "unknown",           # 参与度
    }

    # 从自我描述提取
    if description:
        for kw in ("喜欢", "擅长", "感兴趣"):
            if kw in description:
                model["knowledge_hints"].append(f"自述: {kw}")
        for kw in ("不擅长", "怕", "难", "不好"):
            if kw in description:
                model["difficulty_signals"].append(f"自述: {kw}")
        for kw in ("焦虑", "紧张", "担心", "压力", "害怕"):
            if kw in description:
                model["emotional_state"] = "anxious"
        if "目标" in description or "想" in description or "希望" in description:
            model["knowledge_hints"].append("自述: 有明确目标/期望")

    # 从对话历史提取
    if history:
        # 情绪信号
        anxious_kw = ("焦虑", "紧张", "担心", "害怕", "压力", "烦", "累", "绝望", "难过")
        excited_kw = ("感兴趣", "好奇", "有意思", "太棒了", "明白了", "原来如此")
        for msg in history[-10:]:
            text = str(msg.get('content', ''))
            if any(k in text for k in anxious_kw):
                model["emotional_state"] = "anxious"
            elif any(k in text for k in excited_kw):
                model["emotional_state"] = "engaged"
            # 知识线索
            if any(k in text for k in ("不太懂", "不明白", "没听懂", "不会", "不懂")):
                model["difficulty_signals"].append(f"对话: 表达理解困难")
            if any(k in text for k in ("我知道", "明白了", "会了", "懂了")):
                model["knowledge_hints"].append(f"对话: 表达掌握")

    # 参与度（消息条数）
    if len(history) >= 8:
        model["engagement"] = "high"
    elif len(history) >= 3:
        model["engagement"] = "medium"
    elif len(history) > 0:
        model["engagement"] = "low"

    # 去重
    model["knowledge_hints"] = list(dict.fromkeys(model["knowledge_hints"]))
    model["difficulty_signals"] = list(dict.fromkeys(model["difficulty_signals"]))
    return model


# ============================================================
# 3. Agent Loop（主循环）
# ============================================================

@dataclass
class AgentResult:
    """Agent 一次执行的完整结果。"""
    output: str = ""
    steps: List[dict] = field(default_factory=list)   # 每步的轨迹
    tool_calls: List[dict] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class AgentLoop:
    """通用 Agent 主循环：感知 → 规划 → 行动 → 反思。

    这是 opencode/codex 等 agent 的"循环骨架"的轻量实现。
    PAEG 的教学流程（teach）可以在其上注册为一种"策略"。
    """

    def __init__(self, registry: Optional[ToolRegistry] = None,
                 max_steps: int = 8):
        self.tools = registry or ToolRegistry()
        self.max_steps = max_steps

    def run(self, ctx: AgentContext,
            plan_fn: Callable[[AgentContext], List[dict]],
            act_fn: Callable[[AgentContext, dict], Any],
            reflect_fn: Optional[Callable[[AgentContext, List[dict]], str]] = None,
            max_steps: Optional[int] = None) -> AgentResult:
        """执行主循环。

        plan_fn(ctx) -> steps: 返回行动计划（list of {action, **kwargs}）
        act_fn(ctx, step) -> result: 执行一步
        reflect_fn(ctx, steps) -> summary: 循环结束后总结
        """
        limit = max_steps or self.max_steps
        result = AgentResult()
        t0 = time.time()

        # 1. 规划
        try:
            steps = plan_fn(ctx)
        except Exception as e:
            result.error = f"plan failed: {e}"
            return result

        # 2. 行动
        for i, step in enumerate(steps[:limit]):
            step_trace = {"step": i + 1, **step}
            try:
                output = act_fn(ctx, step)
                step_trace["output"] = str(output)[:500]
                result.steps.append(step_trace)
                if isinstance(output, dict) and output.get("tool_calls"):
                    result.tool_calls.extend(output["tool_calls"])
            except Exception as e:
                step_trace["error"] = str(e)
                result.steps.append(step_trace)
                result.error = f"step {i+1} failed: {e}"
                break

        # 3. 反思
        if reflect_fn:
            try:
                result.output = reflect_fn(ctx, result.steps)
            except Exception as e:
                result.error = f"reflect failed: {e}"

        result.meta = {
            "steps_executed": len(result.steps),
            "elapsed_ms": int((time.time() - t0) * 1000),
            "session_id": ctx.session_id,
        }
        return result


def new_session(user_id: str) -> AgentContext:
    """创建一个新的 Agent 上下文。"""
    return AgentContext(
        session_id=f"ag_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
    )


# ============================================================
# v0.13：Theory of Mind — BDI（信念/愿望/意图）推断
# ============================================================

# 常见信念信号（学生"相信什么"）
_BELIEF_SIGNALS = {
    "self_doubt": ("我不行", "我笨", "学不会", "没天赋", "太笨"),
    "subject_fear": ("数学好难", "物理不会", "英语很差", "看不懂"),
    "growth": ("我想试试", "慢慢来", "总会会的", "再想想"),
    "fixed": ("我就是不会", "天生不行", "没办法"),
}

# 常见愿望信号（学生"想要什么"）
_DESIRE_SIGNALS = {
    "understand": ("想懂", "理解", "明白原理", "搞清楚"),
    "score": ("考好", "得分", "提分", "及格", "高分"),
    "avoid_shame": ("怕被笑", "不好意思", "怕说错"),
    "interest": ("好奇", "感兴趣", "想了解", "有意思"),
    "help": ("帮我", "教教我", "怎么办"),
}

# 常见意图信号（学生"正打算做什么"）
_INTENTION_SIGNALS = {
    "ask_question": ("？", "吗", "怎么", "为什么", "是什么"),
    "seeking_help": ("帮我", "教我", "指导", "提示"),
    "about_to_give_up": ("算了", "放弃", "不学了", "太难了"),
    "verifying": ("对吗", "是不是", "这样对吗", "对不对"),
    "self_testing": ("试试", "做一下", "练一练"),
}


def infer_bdi(history: List[dict], description: str = "") -> Dict[str, Any]:
    """v0.13：推断学生的 BDI（Beliefs/Desires/Intentions）。

    基于 ToM 文献（BDI 建模：beliefs/desires/intentions 三要素），
    从对话历史 + 自我描述推断学生心理状态，增强对象意识。
    """
    bdi = {
        "beliefs": [],
        "desires": [],
        "intentions": [],
        "summary": "",
    }

    texts = [str(m.get("content", "")) for m in history]
    full = " ".join(texts) + " " + (description or "")

    # 信念推断
    for belief, signals in _BELIEF_SIGNALS.items():
        if any(s in full for s in signals):
            bdi["beliefs"].append(belief)
    # 愿望推断
    for desire, signals in _DESIRE_SIGNALS.items():
        if any(s in full for s in signals):
            bdi["desires"].append(desire)
    # 意图推断（看最新几条）
    recent = " ".join(texts[-3:]) if texts else ""
    for intent, signals in _INTENTION_SIGNALS.items():
        if any(s in recent for s in signals):
            bdi["intentions"].append(intent)

    # 生成可读摘要
    parts = []
    if bdi["beliefs"]:
        parts.append("信念：" + "、".join({
            "self_doubt": "有些自我怀疑", "subject_fear": "对某学科有畏难情绪",
            "growth": "有成长型心态", "fixed": "可能认为能力固定"}.
            get(b, b) for b in bdi["beliefs"]))
    if bdi["desires"]:
        parts.append("愿望：" + "、".join({
            "understand": "想真正理解", "score": "在意成绩",
            "avoid_shame": "怕丢脸", "interest": "有好奇心", "help": "需要帮助"}.
            get(d, d) for d in bdi["desires"]))
    if bdi["intentions"]:
        parts.append("意图：" + "、".join({
            "ask_question": "在提问", "seeking_help": "在求助",
            "about_to_give_up": "可能要放弃", "verifying": "在求证",
            "self_testing": "在尝试"}.
            get(i, i) for i in bdi["intentions"]))
    bdi["summary"] = "；".join(parts)

    return bdi
