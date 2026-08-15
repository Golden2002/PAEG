# -*- coding: utf-8 -*-
"""test_repeat_tool_guard.py —— §3.37 H-16 ⭐ repeat-tool-guard 升级测试

Harness 模式（packages/guard/repeat-tool-reminder，commit 47f9438）：
- chain key = JSON.stringify([name, canonicalArgs])——相同工具**不同参数不算重复**
- 多级阈值 [3, 5, 8]：3 温和提醒，5/8 详细提醒（含工具名+次数+参数预览）
- 用户插话（agent/pre-step 检测到 user message）→ 重置 chain
"""
from __future__ import annotations

import pytest


@pytest.fixture
def guard():
    from hooks_hub import HooksHub
    h = HooksHub()
    return h


def test_chain_key_differs_by_args(guard):
    """相同工具不同参数 → 不累计（chain key = name + canonical args）。"""
    # 用不同参数调用 3 次
    for i in range(3):
        r = guard.repeat_guard_check("web_search", learner_id="u1", tool_args={"query": f"问题{i}"})
        assert not r.get("blocked"), f"第{i+1}次不同参数不应拦截: {r}"
    # 相同参数再调用 1 次 → 应该命中 2 次阈值前不拦截
    r = guard.repeat_guard_check("web_search", learner_id="u1", tool_args={"query": "同一问题"})
    assert not r.get("blocked"), "首次同参数不应拦截"


def test_same_args_consecutive_triggers(guard):
    """相同工具+相同参数连续调用 ≥3 次 → 拦截提醒。"""
    for i in range(2):
        r = guard.repeat_guard_check("web_search", learner_id="u2", tool_args={"query": "重复查询"})
        assert not r.get("blocked")
    r = guard.repeat_guard_check("web_search", learner_id="u2", tool_args={"query": "重复查询"})
    assert r.get("blocked") is True, "第 3 次同参数应触发拦截"
    assert "web_search" in r.get("message", "")
    assert "3" in r.get("message", "")


def test_chain_reset_on_other_tool(guard):
    """换工具 → chain 重置（旧工具计数清零）。"""
    for i in range(2):
        guard.repeat_guard_check("web_search", learner_id="u3", tool_args={"query": "x"})
    # 换工具
    guard.repeat_guard_check("fetch_page", learner_id="u3", tool_args={"url": "http://a"})
    # 回到原工具，应从 1 重新计数
    r = guard.repeat_guard_check("web_search", learner_id="u3", tool_args={"query": "x"})
    assert not r.get("blocked"), "换工具后旧 chain 应重置"


def test_threshold_escalation(guard):
    """多级阈值：3 温和提醒 → 5 详细提醒（含参数预览）。"""
    args = {"query": "反复检索同一内容", "max_results": 4}
    blocked_msgs = []
    for i in range(7):
        r = guard.repeat_guard_check("web_search", learner_id="u4", tool_args=args)
        if r.get("blocked"):
            blocked_msgs.append(r["message"])
    assert len(blocked_msgs) >= 1, "超过阈值应产生提醒"
    # 第 5 级详细提醒应含参数预览
    detailed = [m for m in blocked_msgs if "参数" in m or "args" in m.lower() or "反复检索" in m]
    assert detailed, f"高阈值提醒应含参数预览，实际: {blocked_msgs}"


def test_user_message_resets_chain(guard):
    """用户插话 → chain 重置（agent/pre-step 语义）。"""
    for i in range(2):
        guard.repeat_guard_check("web_search", learner_id="u5", tool_args={"query": "z"})
    guard.on_user_message("u5")  # 用户插话
    r = guard.repeat_guard_check("web_search", learner_id="u5", tool_args={"query": "z"})
    assert not r.get("blocked"), "用户插话后 chain 应重置"
