# -*- coding: utf-8 -*-
"""v0.42 ⭐ 提示词模板引擎（固定模板 + 动态填充）

设计（Oracle 方案 + explore 盘点）：
- 固定部分（STATIC_TEMPLATES）：角色/世界观/教育哲学/语言规范——依赖项目设计目标，
  每次 LLM 调用都相同，可前缀缓存。
- 动态部分（PromptContext + DYNAMIC_SLOTS）：用户画像/library/对话历史/本次提问/
  学段/学科/模式——按槽位填充，有结构边界（## 标题分隔）。

目标：消除 server.py/subagents.py 的 30+ 处 `system = system + "\n\n" + X` 散落拼接，
统一为"固定块 + 动态槽"的确定性渲染。

用法：
    from prompt_template import render_prompt, STATIC_TEMPLATES
    system = render_prompt(
        scene="chat:answer",
        context={"learner_profile": "...", "current_question": "...", ...},
    )
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ─────────────────────────────────────
# 固定模板层（每次 LLM 调用都相同）
# ─────────────────────────────────────
# 从 prompts.py 引用既有常量（避免重复维护），按场景组织。
# 场景路由：scene = "<role>:<scene_id>"，如 "chat:answer" / "presenter:math"
STATIC_TEMPLATES: Dict[str, List[str]] = {
    # 闲聊场景：角色 + 世界观 + 语言规范
    "chat": ["WEIL_CORE", "LANGUAGE_STYLE"],
    "chat:answer": ["WEIL_CORE", "LANGUAGE_STYLE"],
    "chat:method": ["WEIL_CORE", "LANGUAGE_STYLE"],
    "chat:knowledge": ["WEIL_CORE", "LANGUAGE_STYLE"],
    "chat:affection": ["WEIL_CORE", "LANGUAGE_STYLE"],
    # 教学场景：角色 + 世界观 + 语言规范（学科扩展由 build_presenter_system 内部注入）
    "presenter": ["WEIL_CORE", "LANGUAGE_STYLE"],
}


class SafeDict(dict):
    """缺失键 → 空串（不抛 KeyError）。"""

    def __missing__(self, key):
        return ""


# ─────────────────────────────────────
# 动态槽位定义（顺序 = 渲染顺序，**按对回答质量的重要性降序排列**）
# ─────────────────────────────────────
# 设计依据（记入元能力 §6.30 提示词模板架构）：
# LLM 是顺序处理器，靠前的上下文锚定其"注意力焦点"。把对本次回答
# 影响最大的上下文放在最前（模式 > 学段学科 > 本次提问 > 用户画像），
# 让模型先确立"用什么范式、讲多深、答什么、为谁答"，再进入辅助材料。
DYNAMIC_SLOTS = [
    # (槽位key, 标题, 是否必需)
    ("mode_scene", "当前模式场景", False),
    ("grade_subject", "学段与学科", False),
    ("current_question", "本次提问", True),
    ("learner_profile", "学习者画像", False),
    ("individuality", "个体化画像（LLM 建模）", False),
    ("user_facts", "用户说过的事实（记忆锚点）", False),
    ("teaching_memory", "教学记忆（可编辑，回答时引用）", False),
    ("user_library", "个人资料库（用户上传/收藏的资料，仅当与本次提问相关时引用）", False),
    ("user_corpus", "用户上传的资料（供回答参考）", False),
    ("web_retrieval", "检索补充材料", False),
    ("skill_catalog", "可用技能目录", False),
    ("chat_history", "对话历史", False),
]


def _render_slot(key: str, title: str, value: Any, max_chars: int = 800) -> str:
    """把单个动态槽值渲染为带标题的段落。空值/None → 空串。"""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        import json as _json
        text = _json.dumps(value, ensure_ascii=False)
    else:
        text = str(value).strip()
    if not text:
        return ""
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return f"## {title}\n{text}"


def render_dynamic_slots(context: Optional[Dict[str, Any]] = None,
                         slots: Optional[List] = None) -> str:
    """只渲染动态槽（不含固定块）。

    适用：基座 system 已由 build_*_system 生成（含固定模板），只需把
    后续注入段（画像/library/记忆/检索…）统一为有序槽位组织，消除
    `system = system + X` 的散落拼接，保证注入顺序确定性（重要性降序）。

    Args:
        context: 动态字段 dict（key 对应 DYNAMIC_SLOTS 的 key）
        slots: 覆盖槽位表（默认 DYNAMIC_SLOTS）

    Returns:
        渲染后的动态槽字符串（可能为空串）。
    """
    ctx = SafeDict(context or {})
    _slots = slots if slots is not None else DYNAMIC_SLOTS
    dynamic_parts = []
    for key, title, required in _slots:
        if key in ctx and ctx[key]:
            dynamic_parts.append(_render_slot(key, title, ctx[key]))
        elif required:
            dynamic_parts.append(f"## {title}\n（未提供）")
    return "\n\n".join(dynamic_parts)


def render_prompt(scene: str, context: Optional[Dict[str, Any]] = None,
                  static_blocks: Optional[List[str]] = None) -> str:
    """渲染完整提示词：固定块（前） + 动态槽（后）。

    Args:
        scene: 场景 ID（决定固定块组合；如 "chat:answer"/"presenter:math"）
        context: 动态字段 dict（key 对应 DYNAMIC_SLOTS 的 key）
        static_blocks: 额外固定块（覆盖 STATIC_TEMPLATES[scene]；供内部扩展用）

    Returns:
        渲染后的完整 system prompt 字符串。
    """
    ctx = SafeDict(context or {})
    # 1. 固定块（角色/世界观/语言规范）
    blocks = static_blocks if static_blocks is not None else (
        STATIC_TEMPLATES.get(scene, STATIC_TEMPLATES["chat"]))
    # 从 prompts.py 引用固定常量
    from prompts import LANGUAGE_STYLE, WEIL_CORE
    _STATIC_SRC = {"WEIL_CORE": WEIL_CORE, "LANGUAGE_STYLE": LANGUAGE_STYLE}
    fixed_parts = []
    for b in blocks:
        if b in _STATIC_SRC:
            fixed_parts.append(_STATIC_SRC[b])
        else:
            fixed_parts.append(b)  # 直接字符串块
    fixed = "\n\n".join(fixed_parts)
    # 2. 动态槽（画像/library/历史/提问/模式/学段学科）
    dynamic = render_dynamic_slots(ctx)
    # 3. 组合：固定在前（锚定身份），动态在后（聚焦当下），双换行分隔
    return fixed + "\n\n\n" + dynamic


if __name__ == "__main__":
    # 自检
    s = render_prompt("chat:answer", {"learner_profile": "昵称：团聚体",
                                       "current_question": "什么是熵？"})
    print(f"渲染 {len(s)} 字")
    print(s[:200])
