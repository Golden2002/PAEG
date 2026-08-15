# -*- coding: utf-8 -*-
"""services/model_routing.py —— §3.44 PTC-4 ⭐ 任务复杂度→模型选择路由（v1.1.5）

借鉴 dsh"模型×框架乘法关系，便宜模型性价比重新放大"：
- 简单任务（分类/检索/闲聊）→ 轻量模型（v4-flash，快/便宜）
- 复杂任务（生成/推理/长文）→ 强模型（reasoner/pro）
- 按任务类型自动路由；config/agents.json 可覆盖（不破坏 create_llm_for）

与 config_loader.create_llm_for 兼容：路由返回模型名，create_llm_for 构造 LLM。
"""
from __future__ import annotations

from typing import Dict, List, Optional

# 模型名映射（可被 config/agents.json global 覆盖）
_DEFAULT_MODELS = {
    "light": "deepseek-v4-flash",
    "medium": "deepseek-v4-flash",
    "strong": "deepseek-reasoner",
}

# 任务复杂度分类
TASK_COMPLEXITY: Dict[str, List[str]] = {
    "light": ["闲聊", "分类", "检索", "识别", "天气", "翻译"],
    "medium": ["默认", "教学", "讲解", "方法", "知识库", "资料"],
    "strong": ["复杂讲解", "推导", "证明", "推理", "长文", "教案", "视频脚本", "Manim 脚本"],
}

# 复杂度级别（供 route_by_level）
_COMPLEXITY_KEYWORDS = {
    "light": ("闲聊", "分类", "检索", "识别", "天气"),
    "strong": ("证明", "推导", "推理", "教案", "脚本", "复杂", "长文", "Manim"),
}


def route_model(task: str = "默认") -> str:
    """按任务类型路由模型名（简单→flash，复杂→reasoner）。"""
    level = _classify(task)
    return _DEFAULT_MODELS[level]


def route_by_level(level: str) -> str:
    """按显式级别路由（light/medium/strong）。"""
    if level not in _DEFAULT_MODELS:
        level = "medium"
    return _DEFAULT_MODELS[level]


def _classify(task: str) -> str:
    """分类任务复杂度（关键词匹配 + 默认 medium）。"""
    if not task:
        return "medium"
    t = str(task)
    for kw in _COMPLEXITY_KEYWORDS["strong"]:
        if kw in t:
            return "strong"
    for kw in _COMPLEXITY_KEYWORDS["light"]:
        if kw in t:
            return "light"
    return "medium"


def configure_models(overrides: Optional[Dict[str, str]] = None) -> None:
    """运行时覆盖模型映射（config/agents.json global 调用）。"""
    global _DEFAULT_MODELS
    if overrides:
        _DEFAULT_MODELS = {**_DEFAULT_MODELS, **overrides}


__all__ = ["route_model", "route_by_level", "TASK_COMPLEXITY", "configure_models"]
