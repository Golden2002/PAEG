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
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llm_api import (ModelAPI, ModelError, MockModelAPI, OpenAICompatModelAPI,
                     AnthropicModelAPI, auto_detect_model_api, detect_model_candidates)


class AllProvidersFailedError(Exception):
    """§3.60 ⭐ 全部 LLM provider 均失败（failover 耗尽）。携带各家失败原因。"""

    def __init__(self, candidates: list, last_error: Optional[Exception] = None):
        labels = [getattr(c, "provider_label", c.name) for c in candidates]
        self.candidates = candidates
        self.last_error = last_error
        super().__init__(
            f"所有 LLM provider 均失败: {labels}"
            + (f" | 最后错误: {last_error}" if last_error else ""))


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
    """包装 ModelAPI，同时暴露新旧两套接口。

    §3.60 ⭐ 运行时 failover：可持多个候选 provider（candidates），
    chat() 遇可切错误（401/403/429/5xx/网络）自动跳下一家。
    """

    def __init__(self, api: ModelAPI = None, provider_label: str = "auto",
                 candidates: Optional[list] = None):
        # 兼容旧用法：api 单例 → candidates=[api]
        if candidates:
            self._candidates = list(candidates)
            self._api = self._candidates[0]
        else:
            self._api = api
            self._candidates = [api] if api else []
        self._provider_label = provider_label
        self._dead: set = set()                 # 永久失败（401/403）→ 本会话不再试
        self._cooldown_until: dict = {}         # 临时失败（429/5xx）→ 冷却截止时间
        self._COOLDOWN_S = 60.0
        self.last_used_label: str = ""          # 观测：最近成功 provider

    # ---- 新接口（subagents 用） ----
    @property
    def name(self) -> str:
        return self._api.name

    def chat(self, system: str, messages: list, max_tokens: int = 2000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        import time as _t
        now = _t.time()
        # 清理过期冷却
        self._cooldown_until = {k: v for k, v in self._cooldown_until.items() if v > now}
        last_err = None
        for api in self._candidates:
            label = getattr(api, "provider_label", api.name)
            if label in self._dead:
                continue
            if self._cooldown_until.get(label, 0) > now:
                continue
            try:
                r = api.chat(system, messages, max_tokens=max_tokens,
                             temperature=temperature, tools=tools,
                             tool_choice=tool_choice)
                self.last_used_label = label
                return r
            except ModelError as e:
                last_err = e
                if getattr(e, "failoverable", False):
                    if getattr(e, "permanent", False):
                        self._dead.add(label)   # 401/403 → key 坏，本会话不再试
                        print(f"[llm_failover] {label} 永久失败({e.http_code}) → 标记dead", file=sys.stderr)
                    else:
                        self._cooldown_until[label] = now + self._COOLDOWN_S
                        print(f"[llm_failover] {label} 临时失败({e.http_code}) → 冷却{self._COOLDOWN_S}s", file=sys.stderr)
                    # 尝试下一家
                    continue
                raise  # 非 failoverable（400/404/解析/内容）→ 直接抛
            except Exception as e:  # 非 ModelError（如网络异常未包装）
                last_err = e
                print(f"[llm_failover] {label} 异常({type(e).__name__}) → 试下一家", file=sys.stderr)
                continue
        # 全部失败 → 明确抛错（不静默 Mock）
        raise AllProvidersFailedError(self._candidates, last_err)

    def available(self) -> bool:
        return any(getattr(c, "available", lambda: False)() for c in self._candidates)

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
        # §3.60 ⭐ 运行时 failover：收集全部候选，AdapterLLM 持列表失败自动切换
        cands = detect_model_candidates(verbose=False)
        _ACTIVE_PROVIDER = "auto"
        return AdapterLLM(api=cands[0], provider_label="auto", candidates=cands)

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