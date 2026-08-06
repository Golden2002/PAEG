"""
PAEG LLM 适配器（v0.5 - 统一为 llm_api 的薄兼容层）。

历史：v0.3 的 llm_adapter 使用独立实现（generate 接口 + LLMResponse）。
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
             temperature: float = 0.7) -> str:
        return self._api.chat(system, messages, max_tokens=max_tokens,
                              temperature=temperature)

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


def create_llm(provider: str = "auto", model: Optional[str] = None, **kwargs) -> AdapterLLM:
    """LLM 工厂（v0.5：自动发现优先）。

    Args:
        provider: "auto"(默认) / "mock" / "deepseek" / "openai" / "anthropic"
        model: 具体模型名（可选，覆盖默认）
    """
    if provider in ("auto", ""):
        api = auto_detect_model_api(verbose=False)
        return AdapterLLM(api, provider_label="auto")

    if provider == "mock":
        return AdapterLLM(MockModelAPI(), provider_label="mock")

    if provider not in _PROVIDER_MODELS:
        raise ValueError(f"Unknown provider: {provider}")

    base, default_model = _PROVIDER_MODELS[provider]
    model = model or default_model

    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            from llm_api import _find_opencode_auth
            key = _find_opencode_auth().get("anthropic")
        api = AnthropicModelAPI(key, model=model, base_url=base) if key else MockModelAPI()
    else:
        env_key = "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY"
        key = os.environ.get(env_key)
        if not key:
            from llm_api import _find_opencode_auth
            key = _find_opencode_auth().get(provider)
        if key:
            api = OpenAICompatModelAPI(key, base, model)
        else:
            api = MockModelAPI()
    return AdapterLLM(api, provider_label=provider)


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