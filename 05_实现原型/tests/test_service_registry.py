# -*- coding: utf-8 -*-
"""test_service_registry.py — #30 Cordis 式 Service Registry 测试（Harness 30 项 P1）

覆盖：统一服务注册表（"一切皆 ctx"——llm/sessions/agents/tools/subagents...），
服务可注册/获取/覆盖，业务代码经 ctx.<key> 取依赖不感知实现。
dsh Harness 借鉴（ctx.<key> Service，commit 47f9438）：
Cordis 一切皆 ctx——服务注册表统一入口，可注册可替换。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_registry_has_core_services():
    """ServiceRegistry 预注册核心服务（llm/sessions 等）。"""
    from services.service_registry import get_service_registry
    reg = get_service_registry()
    # 至少 llm/sessions 核心服务在注册表中
    assert reg.has("llm") or reg.has("sessions")


def test_register_and_get_service():
    """可注册自定义服务 → 可获取（一切皆 ctx 语义）。"""
    from services.service_registry import ServiceRegistry
    reg = ServiceRegistry()
    reg.register("test_svc", lambda: {"name": "test"})
    assert reg.get("test_svc")["name"] == "test"


def test_get_missing_returns_none():
    """未知服务返回 None（容错）。"""
    from services.service_registry import ServiceRegistry
    reg = ServiceRegistry()
    assert reg.get("no_such_service") is None


def test_override_service():
    """可覆盖已注册服务（dsh 一切皆插件：服务可替换）。"""
    from services.service_registry import ServiceRegistry
    reg = ServiceRegistry()
    reg.register("greeter", lambda: "hello")
    assert reg.get("greeter") == "hello"
    reg.register("greeter", lambda: "你好")
    assert reg.get("greeter") == "你好"


def test_list_services():
    """list() 返回已注册服务名。"""
    from services.service_registry import ServiceRegistry
    reg = ServiceRegistry()
    reg.register("svc_a", lambda: 1)
    reg.register("svc_b", lambda: 2)
    names = reg.list()
    assert "svc_a" in names
    assert "svc_b" in names


def test_registry_links_to_infra_runtime():
    """核心服务懒加载关联 infra.runtime（get_llm/get_paeg 等）。"""
    from services.service_registry import get_service_registry
    reg = get_service_registry()
    # llm 服务应能从 infra.runtime 解析（懒加载不抛异常）
    if reg.has("llm"):
        svc = reg.get("llm")
        assert svc is not None
