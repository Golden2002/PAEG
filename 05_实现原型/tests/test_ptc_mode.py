# -*- coding: utf-8 -*-
"""test_ptc_mode.py —— §3.44 PTC-1 ⭐ PTC 模式（程序化步骤）测试

需求（§3.44 PTC-1，借鉴 dsh PTC 模式）：
- workflows_hub 新增 programmatic 步骤类型：把连续多步操作组织成可执行脚本一次跑完
- 支持：多步循环 / 数据采样 / 结果落盘 / 中间结果传递
- 对比标准模式（逐步调用）更少来回、更快更稳
"""
from __future__ import annotations

import json
import os
import time

import pytest


def _make_workflow_step(step_type="programmatic", code="", **kw):
    from workflows_hub import WorkflowStep
    return WorkflowStep(step_id=kw.get("id", "s1"), step_type=step_type,
                        agent=kw.get("agent", ""), config=kw.get("config", {}),
                        depends_on=kw.get("depends_on", []))


def test_ptc_programmatic_step_exists():
    """PTC：workflows_hub 支持 programmatic 步骤类型。"""
    from workflows_hub import WorkflowsHub
    hub = WorkflowsHub()
    st = _make_workflow_step(step_type="programmatic", config={
        "code": "_result = str(1 + 1)",
    })
    result = hub._run_step(st, {}, {})
    assert result is not None, "programmatic 步骤应执行并返回结果"


def test_ptc_executes_python_code():
    """PTC：执行 Python 代码片段并返回结果。"""
    from workflows_hub import WorkflowsHub
    hub = WorkflowsHub()
    st = _make_workflow_step(step_type="programmatic", config={
        "code": "total = sum(range(1, 101))\n_result = f'total={total}'",
    })
    result = hub._run_step(st, {}, {})
    assert "total=5050" in result, f"应计算 1+...+100=5050，实际: {result}"


def test_ptc_loop_sampling():
    """PTC：循环采样（多步重复操作组织成程序一次执行）。"""
    from workflows_hub import WorkflowsHub
    hub = WorkflowsHub()
    st = _make_workflow_step(step_type="programmatic", config={
        "code": (
            "import statistics\n"
            "samples = [i * 2 for i in range(10)]\n"
            "_result = f'avg={statistics.mean(samples):.1f} n={len(samples)}'"
        ),
    })
    result = hub._run_step(st, {}, {})
    assert "avg=9.0" in result, f"10 个样本均值应 9.0，实际: {result}"
    assert "n=10" in result


def test_ptc_accesses_args():
    """PTC：程序可访问 workflow args（参数传递）。"""
    from workflows_hub import WorkflowsHub
    hub = WorkflowsHub()
    st = _make_workflow_step(step_type="programmatic", config={
        "code": "_result = f'topic={args.get(\"topic\", \"\")} region={args.get(\"region\", \"\")}'",
    })
    result = hub._run_step(st, {"topic": "测速", "region": "香港"}, {})
    assert "topic=测速" in result and "region=香港" in result


def test_ptc_writes_result_to_disk():
    """PTC：结果落盘（原始数据保存）。"""
    from workflows_hub import WorkflowsHub
    import tempfile
    tmpdir = tempfile.mkdtemp()
    from workflows_hub import WorkflowsHub as WH
    hub = WH()
    st = _make_workflow_step(step_type="programmatic", config={
        "code": (
            f"import json\n"
            f"data = [{{'region': 'A', 'ms': 100}}, {{'region': 'B', 'ms': 200}}]\n"
            f"with open({tmpdir!r} + '/result.json', 'w') as f:\n"
            f"    json.dump(data, f)\n"
            f"_result = 'written ' + str(len(data)) + ' records'"
        ),
    })
    result = hub._run_step(st, {}, {})
    assert "written 2" in result, f"应写入 2 条记录，实际: {result}"
    out = os.path.join(tmpdir, "result.json")
    assert os.path.exists(out), "结果应落盘"
    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2


def test_ptc_error_safe():
    """PTC：代码错误 → 返回错误信息（不崩溃）。"""
    from workflows_hub import WorkflowsHub
    hub = WorkflowsHub()
    st = _make_workflow_step(step_type="programmatic", config={
        "code": "_result = undefined_variable",
    })
    result = hub._run_step(st, {}, {})
    assert result is not None, "错误应被捕获并返回信息"
