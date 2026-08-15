# -*- coding: utf-8 -*-
"""test_subagent_provider_types.py — #21 Subagent Registry Provider 可插拔测试（Harness 30 项 P0）

覆盖：in-process（已有）/ external-script / llm-call 三类 provider 注册与获取。
dsh Harness 借鉴（packages/subagent spawn/fork provider，commit 47f9438）：
subagent 的 provider 可插拔——进程内类 / 外部脚本 / LLM 调用，均可注册替换。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_in_process_provider_works():
    """in-process provider（现有）：注册类 → 构造实例。"""
    from infra.subagent_registry import Registry

    class FakeSub:
        def __init__(self, llm=None, kb=None, cfg=None):
            self.llm = llm

    reg = Registry()
    reg.register("fake_sub", FakeSub)
    inst = reg.get("fake_sub", llm="MOCK_LLM")
    assert inst is not None
    assert inst.llm == "MOCK_LLM"


def test_external_script_provider_registers():
    """external-script provider：注册外部命令 → 可用（spawn 语义）。"""
    from infra.subagent_registry import register_external_provider, get_external_provider

    register_external_provider("ext_calc", {
        "command": ["python", "-c", "print('ok')"],
        "desc": "外部计算脚本",
    })
    try:
        p = get_external_provider("ext_calc")
        assert p is not None
        assert "command" in p
        assert "python" in p["command"][0]
    finally:
        from infra.subagent_registry import EXTERNAL_PROVIDERS
        EXTERNAL_PROVIDERS.pop("ext_calc", None)


def test_external_provider_missing_returns_none():
    """未知 external provider 返回 None（容错）。"""
    from infra.subagent_registry import get_external_provider
    assert get_external_provider("no_such_provider") is None


def test_llm_call_provider_registers():
    """llm-call provider：注册 LLM 调用模板 → 可用。"""
    from infra.subagent_registry import register_llm_call_provider, get_llm_call_provider

    register_llm_call_provider("llm_quiz", {
        "system": "你是出题器",
        "desc": "LLM 调用型 subagent",
    })
    try:
        p = get_llm_call_provider("llm_quiz")
        assert p is not None
        assert "system" in p
        assert p["system"] == "你是出题器"
    finally:
        from infra.subagent_registry import LLM_CALL_PROVIDERS
        LLM_CALL_PROVIDERS.pop("llm_quiz", None)


def test_llm_call_provider_missing_returns_none():
    """未知 llm-call provider 返回 None（容错）。"""
    from infra.subagent_registry import get_llm_call_provider
    assert get_llm_call_provider("no_such") is None


def test_provider_type_registry_has_all_three():
    """Provider 类型注册表含 in-process/external-script/llm-call 三类。"""
    from infra.subagent_registry import PROVIDER_TYPES
    for t in ("in-process", "external-script", "llm-call"):
        assert t in PROVIDER_TYPES
