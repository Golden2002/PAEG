# -*- coding: utf-8 -*-
"""test_agent_trirole.py — #11 9 Subagent 三角色契约测试（Harness 30 项 P0，§3.46.2）

覆盖：ServiceDefinition / ServiceProvider / Consumer 三角色契约定义，
与 #1 subagent_loader（装扮层）+ #21 Registry（provider 注册表）衔接。
dsh Harness 借鉴（ctx.shell 三角色，commit 47f9438）：RuleDiagnostor vs LLMDiagnostor
——同一 ServiceDefinition 可挂多个 Provider，Consumer 不感知实现。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_service_definition_has_contract():
    """ServiceDefinition 含 name/desc/input_schema/output_schema 契约。"""
    from services.agent_trirole import ServiceDefinition
    sd = ServiceDefinition(
        name="diagnostor",
        desc="学情诊断",
        input_schema={"question": "str", "subject": "str"},
        output_schema={"diagnosis": "dict"},
    )
    assert sd.name == "diagnostor"
    assert sd.input_schema["question"] == "str"
    assert sd.output_schema["diagnosis"] == "dict"


def test_provider_implements_definition():
    """ServiceProvider 绑定 ServiceDefinition，实现 execute 契约。"""
    from services.agent_trirole import ServiceDefinition, ServiceProvider

    sd = ServiceDefinition(name="diagnostor", desc="诊断", input_schema={}, output_schema={})

    class RuleDiagnostor(ServiceProvider):
        def __init__(self):
            super().__init__(sd)

        def execute(self, **inputs):
            return {"diagnosis": {"rule": True}}

    p = RuleDiagnostor()
    assert p.definition.name == "diagnostor"
    assert p.execute(question="x")["diagnosis"]["rule"] is True


def test_two_providers_same_definition():
    """同一 ServiceDefinition 可挂多个 Provider（RuleDiagnostor vs LLMDiagnostor 语义）。"""
    from services.agent_trirole import ServiceDefinition, ServiceProvider

    sd = ServiceDefinition(name="diagnostor", desc="诊断", input_schema={}, output_schema={})

    class RuleDiagnostor(ServiceProvider):
        def __init__(self):
            super().__init__(sd)

        def execute(self, **inputs):
            return {"mode": "rule"}

    class LLMDiagnostor(ServiceProvider):
        def __init__(self):
            super().__init__(sd)

        def execute(self, **inputs):
            return {"mode": "llm"}

    assert RuleDiagnostor().execute()["mode"] == "rule"
    assert LLMDiagnostor().execute()["mode"] == "llm"
    assert RuleDiagnostor().definition is LLMDiagnostor().definition or \
        RuleDiagnostor().definition.name == LLMDiagnostor().definition.name


def test_consumer_uses_provider_abstractly():
    """Consumer 不感知 Provider 实现（经 execute 抽象调用）。"""
    from services.agent_trirole import ServiceDefinition, ServiceProvider

    sd = ServiceDefinition(name="planner", desc="规划", input_schema={}, output_schema={})

    class StudyPlanner(ServiceProvider):
        def __init__(self):
            super().__init__(sd)

        def execute(self, **inputs):
            return {"plan": ["step1", "step2"]}

    def consume(provider: ServiceProvider, **kw):
        """Consumer：只依赖 ServiceProvider 抽象契约。"""
        return provider.execute(**kw)

    assert consume(StudyPlanner())["plan"] == ["step1", "step2"]


def test_default_9_subagent_definitions():
    """内置 9 个 subagent 的 ServiceDefinition 齐全（与 #1 装扮层对齐）。"""
    from services.agent_trirole import DEFAULT_SERVICE_DEFINITIONS
    expected = ["diagnostor", "planner", "presenter", "evaluator",
                "adapter", "answer_solver", "affection_supportor",
                "self_update_agent", "individuality"]
    for name in expected:
        assert name in DEFAULT_SERVICE_DEFINITIONS, f"缺 {name} 定义"
        sd = DEFAULT_SERVICE_DEFINITIONS[name]
        assert sd.name == name
        assert sd.desc


def test_register_custom_definition():
    """可注册自定义 ServiceDefinition（dsh 一切皆插件）。"""
    from services.agent_trirole import (
        DEFAULT_SERVICE_DEFINITIONS, ServiceDefinition, register_definition,
    )
    register_definition(ServiceDefinition(name="test_sd", desc="测试", input_schema={}, output_schema={}))
    try:
        assert "test_sd" in DEFAULT_SERVICE_DEFINITIONS
    finally:
        DEFAULT_SERVICE_DEFINITIONS.pop("test_sd", None)
