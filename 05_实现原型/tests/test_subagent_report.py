# -*- coding: utf-8 -*-
"""test_subagent_report.py — #22 Subagent Report/Continuable 协议测试（Harness 30 项 P1）

覆盖：子代理回报（report）+ 父发消息（continuable——父可继续驱动子代理）。
dsh Harness 借鉴（subagent-control/report，commit 47f9438）：
子代理完成任务后回报结果；父代理可发消息继续驱动（多轮协作）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_report_message_shape():
    """报告消息含 agent/status/result 契约字段。"""
    from services.subagent_report import make_report
    r = make_report("diagnostor", "completed", {"diagnosis": {"rule": True}})
    assert r["agent"] == "diagnostor"
    assert r["status"] == "completed"
    assert r["result"]["diagnosis"]["rule"] is True
    # 含时间戳
    assert "ts" in r


def test_report_failure_shape():
    """失败报告含 error 字段。"""
    from services.subagent_report import make_report
    r = make_report("planner", "failed", {"error": "LLM 超时"})
    assert r["status"] == "failed"
    assert "error" in r["result"]


def test_continuable_message():
    """父发消息（continuable）含 to/instruction 契约。"""
    from services.subagent_report import make_instruction
    m = make_instruction("presenter", "请重新讲解概念部分")
    assert m["to"] == "presenter"
    assert m["instruction"] == "请重新讲解概念部分"
    assert "ts" in m


def test_report_registry_store_and_get():
    """报告注册表存储子代理回报 → 可按 agent 查询。"""
    from services.subagent_report import ReportRegistry
    reg = ReportRegistry()
    reg.add_report("diagnostor", "completed", {"diagnosis": {}})
    reg.add_report("planner", "failed", {"error": "x"})
    reports = reg.get_reports("diagnostor")
    assert len(reports) == 1
    assert reports[0]["status"] == "completed"
    assert len(reg.get_reports("planner")) == 1


def test_report_registry_all():
    """报告注册表 list_all 返回全部（按 agent 分组）。"""
    from services.subagent_report import ReportRegistry
    reg = ReportRegistry()
    reg.add_report("a", "completed", {})
    reg.add_report("b", "failed", {"error": "e"})
    all_r = reg.list_all()
    assert "a" in all_r
    assert "b" in all_r


def test_report_registry_unknown_agent_empty():
    """未知 agent 报告列表为空（容错）。"""
    from services.subagent_report import ReportRegistry
    reg = ReportRegistry()
    assert reg.get_reports("no_such_agent") == []
