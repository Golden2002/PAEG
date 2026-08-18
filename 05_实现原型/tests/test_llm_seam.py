# -*- coding: utf-8 -*-
"""test_llm_seam.py — #12 LLM Provider Seam 测试（§3.46.2 Harness P0）

覆盖：Provider 注册表 / 显式 provider 构造 / config 驱动 / 可观测 info / Mock 兜底。
dsh Harness 借鉴（packages/llm/seam，commit 47f9438）：Definition/Provider/Consumer 三角色——
provider 可注册可替换，业务代码不感知切换。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_provider_registry_has_defaults():
    """Provider 注册表含 deepseek/openai/anthropic/mock 四个默认 provider。"""
    from llm_adapter import PROVIDER_REGISTRY
    assert "deepseek" in PROVIDER_REGISTRY
    assert "openai" in PROVIDER_REGISTRY
    assert "anthropic" in PROVIDER_REGISTRY
    assert "mock" in PROVIDER_REGISTRY


def test_register_custom_provider():
    """可注册自定义 provider（dsh 一切皆插件：provider 可插拔）。"""
    from llm_adapter import PROVIDER_REGISTRY, register_provider

    def _fake_factory(provider, model, **kw):
        from llm_api import MockModelAPI
        from llm_adapter import AdapterLLM
        return AdapterLLM(MockModelAPI(), provider_label=provider)

    register_provider("test_seam_provider", _fake_factory)
    try:
        assert "test_seam_provider" in PROVIDER_REGISTRY
    finally:
        PROVIDER_REGISTRY.pop("test_seam_provider", None)


def test_create_llm_explicit_provider():
    """显式指定 provider（跳过 auto 检测）→ 构造对应 provider 的 LLM。"""
    from llm_adapter import create_llm
    llm = create_llm("mock")
    assert llm.name == "mock"
    assert llm.available() is True


def test_create_llm_auto_returns_configured():
    """auto 模式返回实际可用 provider（不抛异常，name 非空）。"""
    from llm_adapter import create_llm
    llm = create_llm("auto")
    assert llm.name  # name 非空（真实 provider 或 mock）


def test_provider_info_observable():
    """provider_info() 暴露实际生效的 provider/model（可观测——解决'到底用了哪个'）。"""
    from llm_adapter import provider_info
    info = provider_info()
    assert "provider" in info
    assert "model" in info
    assert info["provider"] in ("auto", "deepseek", "openai", "anthropic", "mock")


def test_provider_info_reflects_choice():
    """显式 provider 后 provider_info 反映该选择。"""
    from llm_adapter import create_llm, provider_info
    create_llm("mock")
    info = provider_info()
    assert info["provider"] == "mock"


def test_config_driven_provider(monkeypatch):
    """PAEG_LLM_PROVIDER env 驱动 create_llm 默认（config 层，非散落调用点）。"""
    from llm_adapter import create_llm
    monkeypatch.setenv("PAEG_LLM_PROVIDER", "mock")
    # 不传 provider 时读 env（走 config 层）
    from infra.runtime import get_llm
    # infra.runtime.get_llm 用 config.LLM_PROVIDER；这里验证 llm_adapter 层也支持 env 驱动
    llm = create_llm("")  # 空串 → 读 env
    assert llm.name == "mock"
