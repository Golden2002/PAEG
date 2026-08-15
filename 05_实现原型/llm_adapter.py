"""
PAEG LLM 适配器（v0.5 - 统一为 llm_api 的薄兼容层）。

历史：v0.38 的 llm_adapter 使用独立实现（generate 接口 + LLMResponse）。
v0.5 起统一到 llm_api.ModelAPI（auto_detect 自动发现凭据，已实测可用）。

本文件保留旧接口兼容性：
  - create_llm(provider, model) -> AdapterLLM
  - AdapterLLM.generate(messages, system, max_tokens) -> LLMResponse（旧调用方：server.py）
  - AdapterLLM.chat(system, messages, max_tokens, temperature) -> str（新调用方：subagents.py）
  - AdapterLLM.name / .available()

provider 取值：auto（默认，自动发现）/ mock / deepseek / openai / anthropic
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llm_api import (ModelAPI, ModelError, MockModelAPI, OpenAICompatModelAPI,
                     AnthropicModelAPI, auto_detect_model_api)


@dataclass
class LLMResponse:
    """统一 LLM 响应格式（旧接口）。"""
    text: str
    stop_reason: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    provider: str
    model: str


class AdapterLLM:
    """包装 ModelAPI，同时暴露新旧两套接口。"""

    def __init__(self, api: ModelAPI, provider_label: str = "auto"):
        self._api = api
        self._provider_label = provider_label

    # ---- 新接口（subagents 用） ----
    @property
    def name(self) -> str:
        return self._api.name

    def chat(self, system: str, messages: list, max_tokens: int = 2000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        return self._api.chat(system, messages, max_tokens=max_tokens,
                              temperature=temperature, tools=tools,
                              tool_choice=tool_choice)

    def available(self) -> bool:
        return self._api.available()

    # ---- 旧接口（server.py / test_demo_real_llm.py 用） ----
    def generate(self, messages: List[Dict[str, str]], system: str = "",
                 max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        start = time.time()
        text = self._api.chat(system, messages, max_tokens=max_tokens,
                              temperature=temperature)
        latency = (time.time() - start) * 1000
        model = getattr(self._api, "_model", "default")
        return LLMResponse(
            text=text,
            stop_reason="end_turn",
            input_tokens=0,
            output_tokens=len(text) // 2,
            latency_ms=latency,
            provider=self._api.name,
            model=str(model),
        )


_PROVIDER_MODELS = {
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "anthropic": ("https://api.anthropic.com", "claude-sonnet-4-5"),
}


# ─────────────────────────────────────
# #12 ⭐ LLM Provider Seam（§3.46.2 Harness P0，2026-08-16）
# dsh Harness 借鉴（packages/llm/seam，commit 47f9438）：Definition/Provider/Consumer 三角色
# ——provider 可注册可替换，业务代码不感知切换。
# ─────────────────────────────────────
# 注册表：provider name → 构造工厂（factory(provider, model, **kwargs) -> AdapterLLM）
PROVIDER_REGISTRY = {}

# 当前生效 provider（可观测：provider_info() 暴露）
_ACTIVE_PROVIDER = "auto"


def _factory_deepseek(provider: str, model: Optional[str], **kwargs) -> AdapterLLM:
    base, default_model = _PROVIDER_MODELS["deepseek"]
    model = model or default_model
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        from llm_api import _find_opencode_auth
        key = _find_opencode_auth().get("deepseek")
    api = OpenAICompatModelAPI(key, base, model) if key else MockModelAPI()
    return AdapterLLM(api, provider_label=provider)


def _factory_openai(provider: str, model: Optional[str], **kwargs) -> AdapterLLM:
    base, default_model = _PROVIDER_MODELS["openai"]
    model = model or default_model
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        from llm_api import _find_opencode_auth
        key = _find_opencode_auth().get("openai")
    api = OpenAICompatModelAPI(key, base, model) if key else MockModelAPI()
    return AdapterLLM(api, provider_label=provider)


def _factory_anthropic(provider: str, model: Optional[str], **kwargs) -> AdapterLLM:
    base, default_model = _PROVIDER_MODELS["anthropic"]
    model = model or default_model
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        from llm_api import _find_opencode_auth
        key = _find_opencode_auth().get("anthropic")
    api = AnthropicModelAPI(key, model=model, base_url=base) if key else MockModelAPI()
    return AdapterLLM(api, provider_label=provider)


def _factory_mock(provider: str, model: Optional[str], **kwargs) -> AdapterLLM:
    return AdapterLLM(MockModelAPI(), provider_label="mock")


def _register_default_providers() -> None:
    """注册内置 provider（幂等）。"""
    if "deepseek" not in PROVIDER_REGISTRY:
        PROVIDER_REGISTRY["deepseek"] = _factory_deepseek
    if "openai" not in PROVIDER_REGISTRY:
        PROVIDER_REGISTRY["openai"] = _factory_openai
    if "anthropic" not in PROVIDER_REGISTRY:
        PROVIDER_REGISTRY["anthropic"] = _factory_anthropic
    if "mock" not in PROVIDER_REGISTRY:
        PROVIDER_REGISTRY["mock"] = _factory_mock


# #12 ⭐ 模块加载即注册默认 provider（注册表导入即可观测——dsh Seam Definition 层）
_register_default_providers()


def register_provider(name: str, factory) -> None:
    """注册自定义 provider 工厂（dsh 一切皆插件：provider 可插拔）。"""
    PROVIDER_REGISTRY[name] = factory


def provider_info() -> dict:
    """暴露实际生效的 provider/model（可观测——解决'到底用了哪个'）。

    Returns:
        {"provider": str, "model": str, "available": bool}
    """
    global _ACTIVE_PROVIDER
    try:
        llm = create_llm(_ACTIVE_PROVIDER)
        model = getattr(llm._api, "_model", "default") if hasattr(llm, "_api") else "default"
        return {"provider": _ACTIVE_PROVIDER, "model": str(model), "available": llm.available()}
    except Exception as _e:  # noqa: BLE001
        return {"provider": _ACTIVE_PROVIDER, "model": "default", "available": False, "error": str(_e)}


def create_llm(provider: str = "auto", model: Optional[str] = None, **kwargs) -> AdapterLLM:
    """LLM 工厂（v0.5：自动发现优先；#12 ⭐ Provider Seam：注册表驱动 + env 可配置）。

    Args:
        provider: "auto"(默认) / "mock" / "deepseek" / "openai" / "anthropic" / 自定义注册名
        model: 具体模型名（可选，覆盖默认）
    """
    global _ACTIVE_PROVIDER
    _register_default_providers()

    # #12 ⭐ env 驱动：PAEG_LLM_PROVIDER 空/未传时读配置层（config.py LLM_PROVIDER 已读此 env）
    if not provider or provider == "auto":
        _env_provider = os.environ.get("PAEG_LLM_PROVIDER", "").strip()
        if _env_provider and _env_provider != "auto":
            provider = _env_provider

    # auto：自动发现（真实 provider 优先，降级 mock）
    if provider in ("auto", ""):
        api = auto_detect_model_api(verbose=False)
        _ACTIVE_PROVIDER = "auto"
        return AdapterLLM(api, provider_label="auto")

    # 注册表驱动（dsh Seam：provider 可插拔）
    if provider in PROVIDER_REGISTRY:
        _ACTIVE_PROVIDER = provider
        return PROVIDER_REGISTRY[provider](provider, model, **kwargs)

    if provider == "mock":
        _ACTIVE_PROVIDER = "mock"
        return AdapterLLM(MockModelAPI(), provider_label="mock")

    raise ValueError(f"Unknown provider: {provider}（可用：{sorted(PROVIDER_REGISTRY)}）")


if __name__ == "__main__":
    llm = create_llm("auto")
    print(f"Provider: {llm.name}, available={llm.available()}")
    if llm.available() and llm.name != "mock":
        resp = llm.generate(
            messages=[{"role": "user", "content": "用一句话介绍你自己。"}],
            system="你是简短的测试助手。",
            max_tokens=100,
        )
        print(f"generate() -> {resp.text[:150]}")
        reply = llm.chat(system="你是简短的测试助手。",
                         messages=[{"role": "user", "content": "再说一句话。"}],
                         max_tokens=100)
        print(f"chat()     -> {reply[:150]}")
    else:
        print("离线模式（mock）。")