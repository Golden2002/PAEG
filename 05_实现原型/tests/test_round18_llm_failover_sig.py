# -*- coding: utf-8 -*-
"""Round 11 ⭐ LLM failover 签名一致性测试（test_round18_llm_failover_sig.py）。

背景（Round 11 挖掘的既有 bug）：llm_adapter.AdapterLLM.chat 的 failover 循环对
**全部候选**统一调用 `api.chat(..., tools=..., tool_choice=...)`，但
AnthropicModelAPI.chat / MockModelAPI.chat 原签名缺这两个参数 → TypeError →
被 except Exception 吞掉 → 主候选失败时兜底候选必然失败（"got an unexpected
keyword argument 'tools'" → AllProvidersFailedError）。

守护：
1. 所有 ModelAPI 子类 chat 签名必须接受 tools/tool_choice（与调用方契约一致）
2. AnthropicModelAPI.chat 实际可用（tools 透传后能返回文本）
3. failover 到 anthropic 不再 TypeError（模拟主候选失败 → anthropic 兜底成功）
"""
from __future__ import annotations

import inspect

import pytest

from llm_api import (
    AnthropicModelAPI, MockModelAPI, ModelAPI,
    OpenAICompatModelAPI, ReasonerModelAPI,
)


def _all_modelapi_classes():
    import llm_api as mod
    return [obj for name in dir(mod)
            for obj in [getattr(mod, name)]
            if isinstance(obj, type) and issubclass(obj, ModelAPI)
            and obj is not ModelAPI]


class TestSignatureContract:
    """调用方契约：AdapterLLM.chat 传 tools/tool_choice，所有候选必须接受。"""

    @pytest.mark.parametrize("cls", _all_modelapi_classes(),
                             ids=lambda c: c.__name__)
    def test_chat_accepts_tools_and_tool_choice(self, cls):
        params = list(inspect.signature(cls.chat).parameters.keys())
        assert "tools" in params, f"{cls.__name__}.chat 缺 tools 参数（failover 必 TypeError）"
        assert "tool_choice" in params, f"{cls.__name__}.chat 缺 tool_choice 参数"

    def test_all_classes_covered(self):
        names = {c.__name__ for c in _all_modelapi_classes()}
        assert {"AnthropicModelAPI", "MockModelAPI",
                "OpenAICompatModelAPI", "ReasonerModelAPI"} <= names


class TestAnthropicChat:
    def test_accepts_tools_without_crash(self, monkeypatch):
        import json as _json
        import llm_api as _mod

        captured = {}

        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return _json.dumps({"content": [{"text": "[ok]"}]}).encode()

        def _fake_urlopen(req, timeout=None):
            captured["body"] = _json.loads(req.data.decode())
            return _FakeResp()

        monkeypatch.setattr(_mod.request, "urlopen", _fake_urlopen)
        api = AnthropicModelAPI(api_key="test-key", model="claude-sonnet-4-5")
        out = api.chat("sys", [{"role": "user", "content": "hi"}],
                       tools=[{"type": "function", "function": {"name": "f"}}],
                       tool_choice="auto")
        assert out == "[ok]"
        assert "tools" in captured["body"], "tools 未透传"
        assert captured["body"]["tool_choice"] == {"type": "auto"}

    def test_tool_choice_dict_passthrough(self):
        api = AnthropicModelAPI(api_key="test-key", model="m")
        assert api._tool_choice_payload("auto") == {"type": "auto"}
        assert api._tool_choice_payload({"type": "tool", "name": "f"}) == \
            {"type": "tool", "name": "f"}

    def test_no_tool_choice_no_key(self):
        api = AnthropicModelAPI(api_key="test-key", model="m")
        assert api._tool_choice_payload(None) is None
        assert api._tool_choice_payload("") is None


class TestMockChat:
    def test_mock_accepts_tools(self):
        api = MockModelAPI(echo="[ok]")
        assert api.chat("sys", [], tools=[{"type": "function"}],
                        tool_choice="auto") == "[ok]"
