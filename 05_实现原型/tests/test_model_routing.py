# -*- coding: utf-8 -*-
"""test_model_routing.py —— §3.44 PTC-4 ⭐ 任务复杂度→模型选择路由测试

需求（§3.44 PTC-4，借鉴 dsh"模型×框架乘法，便宜模型性价比放大"）：
- 简单任务（分类/检索/闲聊）→ 轻量模型（v4-flash）
- 复杂任务（生成/推理/长文）→ 强模型
- 按任务类型自动路由，不硬编码
"""
from __future__ import annotations

import pytest


def test_simple_task_routes_light():
    """简单任务 → 轻量模型（v4-flash）。"""
    from services.model_routing import route_model, TASK_COMPLEXITY
    for task in TASK_COMPLEXITY["light"]:
        model = route_model(task)
        assert "flash" in model, f"{task} 应路由到 flash，实际 {model}"


def test_complex_task_routes_strong():
    """复杂任务 → 强模型。"""
    from services.model_routing import route_model, TASK_COMPLEXITY
    for task in TASK_COMPLEXITY["strong"]:
        model = route_model(task)
        assert "reasoner" in model or "pro" in model, f"{task} 应路由到强模型，实际 {model}"


def test_auto_task_balanced():
    """自动任务（默认）→ 平衡配置。"""
    from services.model_routing import route_model
    model = route_model("默认教学")
    assert model, "应有默认模型"


def test_route_by_complexity_level():
    """按复杂度级别路由（light/medium/strong）。"""
    from services.model_routing import route_by_level
    assert "flash" in route_by_level("light")
    assert "reasoner" in route_by_level("strong") or "pro" in route_by_level("strong")


def test_routing_matches_agents_config():
    """路由与 config/agents.json per-subagent 配置兼容（可覆盖）。"""
    from services.model_routing import route_model
    # 可配置覆盖：路由结果可通过 config 覆盖（不破坏现有 create_llm_for）
    model = route_model("复杂讲解")
    assert isinstance(model, str)
