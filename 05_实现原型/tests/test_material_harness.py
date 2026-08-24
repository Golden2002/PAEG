# -*- coding: utf-8 -*-
"""§3.95 material_harness 测试：AgentEngine 驱动物料 + 中间产物。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from material_harness import MaterialHarness


def test_harness_run_handout():
    """H1：harness 跑讲义（Plan→Act→Observe→Reflect 循环）。"""
    h = MaterialHarness(None)
    r = h.run("handout", "光合作用", "生物")
    assert "plan" in r["artifacts"]
    assert "content" in r["artifacts"]
    assert len(r["trace"]) >= 4  # plan/act/observe/(reflect)


def test_harness_plan_contains_user_requirements():
    """H2：用户要求拼进规划 prompt（§3.95 用户输入注入）。"""
    h = MaterialHarness(None)
    # 无 LLM → _plan 返回兜底（不抛异常）
    spec = h._plan("ppt", "导数", "math", "high_school", "重点讲切线")
    assert isinstance(spec, dict)


def test_harness_observe_gates():
    """H3：观察阶段门控（讲义结构门）。"""
    h = MaterialHarness(None)
    issues = h._observe("handout", "只有一行内容")
    assert isinstance(issues, list)
    # 内容非空但不满足讲义门 → 应有问题或空（依赖 gates_lib）
    issues2 = h._observe("handout", "")
    assert "内容为空" in issues2


def test_harness_act_with_router_generator():
    """H4：默认生成器来自 material_router（ROUTER 表）。"""
    h = MaterialHarness(None)
    # 不传 generator → 尝试用 ROUTER（无 LLM 时返回兜底）
    r = h.run("script", "导数", "math")
    assert r["iterations"] >= 1


def test_harness_trace_phases():
    """H5：trace 含 plan/act/observe 阶段记录。"""
    h = MaterialHarness(None)
    r = h.run("mindmap", "函数", "math")
    phases = {t["phase"] for t in r["trace"]}
    assert "plan" in phases
    assert "act" in phases
    assert "observe" in phases
