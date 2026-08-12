"""
PAEG v0.5 模型接口层（ModelAPI）。

设计：
- 抽象基类 ModelAPI：统一 chat() 接口
- OpenAICompatModelAPI：兼容 DeepSeek / OpenAI / Ollama / Qwen / Kimi / 智谱 等
  （绝大多数国内/国际模型都提供 OpenAI 兼容端点）
- AnthropicModelAPI：Anthropic 专属
- MockModelAPI：无 key / 离线时的兜底（v0.1 行为）
- auto_detect_model_api()：自动发现可用配置
  优先级：环境变量 PAEG_API_KEY > DEEPSEEK_API_KEY > opencode auth.json(deepseek) > Mock

安全：本模块只做"自动发现"与"读取配置"，绝不打印 key 明文。
"""

import json
import os
import sys
from typing import Optional
from urllib import request, error


class ModelAPI:
    """模型接口抽象基类。"""

    name = "abstract"

    def chat(self, system: str, messages: list, max_tokens: int = 2000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        """一次对话。messages: [{"role": "user"/"assistant", "content": str}, ...]
        返回模型回复文本。若模型请求工具调用，返回 JSON 字符串（含 tool_calls）。
        失败抛 ModelError。"""
        raise NotImplementedError

    def available(self) -> bool:
        return False


class ModelError(Exception):
    pass


class MockModelAPI(ModelAPI):
    """兜底模型：返回结构化占位回复（v0.1 行为，用于离线演示与测试）。"""

    name = "mock"

    def __init__(self, echo: str = "[模拟回复]"):
        self._echo = echo

    def chat(self, system: str, messages: list, max_tokens: int = 2000,
             temperature: float = 0.7) -> str:
        return self._echo

    def available(self) -> bool:
        return True


class OpenAICompatModelAPI(ModelAPI):
    """OpenAI 兼容端点（DeepSeek / OpenAI / Ollama / Qwen / Kimi / 智谱 ...）。"""

    name = "openai_compat"

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout: int = 60, temperature: float = 0.7):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._temperature = temperature

    def _url(self) -> str:
        # 兼容 Ollama 等无 /v1 路径的端点
        if self._base_url.endswith("/v1"):
            return self._base_url + "/chat/completions"
        return self._base_url + "/v1/chat/completions"

    def chat(self, system: str, messages: list, max_tokens: int = 2000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self._url(),
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            # v0.19：若模型请求工具调用，返回完整 message（含 tool_calls）
            if msg.get("tool_calls"):
                return json.dumps({
                    "tool_calls": [
                        {"id": tc.get("id", ""),
                         "name": tc.get("function", {}).get("name", ""),
                         "arguments": tc.get("function", {}).get("arguments", "{}")}
                        for tc in msg["tool_calls"]
                    ],
                }, ensure_ascii=False)
            return msg.get("content") or ""
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise ModelError(f"[{self.name}] HTTP {e.code}: {detail}") from e
        except error.URLError as e:
            raise ModelError(f"[{self.name}] 网络错误: {e.reason}") from e
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ModelError(f"[{self.name}] 响应解析失败: {e}") from e

    def available(self) -> bool:
        return bool(self._api_key) and bool(self._base_url) and bool(self._model)


class ReasonerModelAPI(OpenAICompatModelAPI):
    """深度思考模式 API（v0.51 ⭐ DeepSeek V4 thinking 接入）。

    与普通 OpenAICompatModelAPI 的差异：
    - 请求带 `thinking: {"type": "enabled"}` + `reasoning_effort`
    - 响应提取 `reasoning_content`（思考链）字段
    - `chat()` 保持原契约：返回 content 字符串（现有 130+ 调用方零改动）
    - `chat_with_reasoning()` 返回完整结构 {"thinking", "content", "reasoning_tokens", ...}

    参考（librarian 调研 2026-08）：
    - DeepSeek V4 思考模式：https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
    - 思考模式下 temperature/top_p 等采样参数不生效（API 静默忽略）
    - 模型名用 V4 系列（deepseek-v4-flash / deepseek-v4-pro）；旧 deepseek-reasoner 别名已下线
    """

    name = "reasoner"

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout: int = 120, temperature: float = 0.7,
                 reasoning_effort: str = "high"):
        super().__init__(api_key, base_url, model, timeout=timeout,
                         temperature=temperature)
        self._reasoning_effort = reasoning_effort  # low / high / max

    def chat(self, system: str, messages: list, max_tokens: int = 2000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        """保持原 chat() 行为：返回 content 字符串（向后兼容）。

        thinking 通过 chat_with_reasoning() 单独获取。
        """
        r = self.chat_with_reasoning(system, messages, max_tokens,
                                     temperature, tools, tool_choice)
        return r.get("content") or ""

    def chat_with_reasoning(self, system: str, messages: list,
                            max_tokens: int = 4000,
                            temperature: float = 0.7,
                            tools: Optional[list] = None,
                            tool_choice: Optional[str] = None) -> dict:
        """返回完整结构 {thinking, content, reasoning_tokens, total_tokens}。

        思考模式下 tools 不支持（DeepSeek reasoner 不可 tool call）——
        若传 tools 直接抛 ModelError（调用方降级到普通 chat 路径）。
        失败抛 ModelError（同 chat 契约）。
        """
        if tools:
            raise ModelError(
                "[reasoner] 思考模式不支持 tools，请用普通 chat + 后置工具循环")
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            # v0.51 ⭐ DeepSeek V4 思考模式（OpenAI 兼容 extra 字段透传）
            "thinking": {"type": "enabled"},
            "reasoning_effort": self._reasoning_effort,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self._url(),
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            usage = data.get("usage") or {}
            return {
                "thinking": msg.get("reasoning_content") or "",
                "content": msg.get("content") or "",
                "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise ModelError(f"[{self.name}] HTTP {e.code}: {detail}") from e
        except error.URLError as e:
            raise ModelError(f"[{self.name}] 网络错误: {e.reason}") from e
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ModelError(f"[{self.name}] 响应解析失败: {e}") from e

    def available(self) -> bool:
        return bool(self._api_key) and bool(self._base_url) and bool(self._model)


class AnthropicModelAPI(ModelAPI):
    """Anthropic Claude 专属端点。"""

    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5",
                 base_url: str = "https://api.anthropic.com", timeout: int = 60):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def chat(self, system: str, messages: list, max_tokens: int = 2000,
             temperature: float = 0.7) -> str:
        payload = {
            "model": self._model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self._base_url + "/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise ModelError(f"[{self.name}] HTTP {e.code}: {detail}") from e
        except error.URLError as e:
            raise ModelError(f"[{self.name}] 网络错误: {e.reason}") from e
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ModelError(f"[{self.name}] 响应解析失败: {e}") from e

    def available(self) -> bool:
        return bool(self._api_key)


# ---------------------------------------------------------------------------
# 自动配置发现
# ---------------------------------------------------------------------------

def _find_opencode_auth() -> dict:
    """在 opencode auth.json 中查找 deepseek / anthropic 凭据。
    返回 {"deepseek": key} 或 {"anthropic": key} 等，找不到返回 {}。
    """
    candidates = [
        os.path.expanduser("~/.local/share/opencode/auth.json"),
        os.path.expanduser("~/.config/opencode/auth.json"),
        os.path.join(os.environ.get("APPDATA", ""), "opencode", "auth.json"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result = {}
                for provider in ("deepseek", "anthropic", "openai"):
                    entry = data.get(provider)
                    if isinstance(entry, dict):
                        key = entry.get("key") or entry.get("api_key")
                        if key:
                            result[provider] = key
                    elif isinstance(entry, str):
                        result[provider] = entry
                return result
            except (OSError, json.JSONDecodeError):
                continue
    return {}


def auto_detect_model_api(verbose: bool = True) -> ModelAPI:
    """按优先级自动选择一个可用模型接口：
    1. PAEG_API_KEY + PAEG_API_BASE（自定义）
    2. DEEPSEEK_API_KEY -> DeepSeek
    3. ANTHROPIC_API_KEY -> Anthropic
    4. OPENAI_API_KEY -> OpenAI
    5. opencode auth.json（deepseek 优先）
    6. 全部不可用 -> MockModelAPI（离线演示）

    v0.51 ⭐ 深度思考：PAEG_MODEL=deepseek-v4-pro / PAEG_REASONING=on 时
    返回 ReasonerModelAPI（thinking 模式）；否则默认 V4-Flash 普通对话。
    旧别名 deepseek-chat/deepseek-reasoner 已下线（2026-07-24），自动迁移到 V4。
    """
    def log(msg):
        if verbose:
            print(f"[llm_api] {msg}", file=sys.stderr)

    # v0.51 ⭐ 模型名迁移：旧别名 deepseek-chat → deepseek-v4-flash（2026-07-24 下线）
    def _migrate_model(m: str) -> str:
        if m in ("deepseek-chat", "deepseek-reasoner"):
            return "deepseek-v4-flash"
        return m

    def _maybe_reasoner(key: str, base: str, model: str, **kw) -> ModelAPI:
        """PAEG_REASONING=on 或 PAEG_MODEL 含 reasoner/v4-pro → ReasonerModelAPI。"""
        reasoning = os.environ.get("PAEG_REASONING", "off").lower() in ("on", "1", "true")
        pro_reasoner = ("pro" in model.lower() or "reasoner" in model.lower())
        effort = os.environ.get("PAEG_REASONING_EFFORT", "high")
        if reasoning or pro_reasoner:
            log(f"深度思考模式（reasoner, effort={effort}）")
            return ReasonerModelAPI(key, base, model, reasoning_effort=effort, **kw)
        return OpenAICompatModelAPI(key, base, model, **kw)

    # 1. 自定义
    custom_key = os.environ.get("PAEG_API_KEY")
    custom_base = os.environ.get("PAEG_API_BASE", "https://api.deepseek.com/v1")
    custom_model = _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash"))
    if custom_key:
        log(f"使用 PAEG_API_KEY（{custom_model} @ {custom_base}）")
        return _maybe_reasoner(custom_key, custom_base, custom_model)

    # 2-4. 标准环境变量
    if os.environ.get("DEEPSEEK_API_KEY"):
        log("使用 DEEPSEEK_API_KEY")
        return _maybe_reasoner(
            os.environ["DEEPSEEK_API_KEY"], "https://api.deepseek.com/v1",
            _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash")))
    if os.environ.get("ANTHROPIC_API_KEY"):
        log("使用 ANTHROPIC_API_KEY")
        return AnthropicModelAPI(os.environ["ANTHROPIC_API_KEY"])
    if os.environ.get("OPENAI_API_KEY"):
        log("使用 OPENAI_API_KEY")
        return OpenAICompatModelAPI(
            os.environ["OPENAI_API_KEY"], "https://api.openai.com/v1", "gpt-4o-mini")

    # 5. opencode auth.json
    auth = _find_opencode_auth()
    if auth.get("deepseek"):
        log("使用 opencode auth.json 中的 DeepSeek 凭据")
        return _maybe_reasoner(
            auth["deepseek"], "https://api.deepseek.com/v1",
            _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash")))
    if auth.get("anthropic"):
        log("使用 opencode auth.json 中的 Anthropic 凭据")
        return AnthropicModelAPI(auth["anthropic"])

    # 6. 兜底
    log("未找到 API 凭据，回退到 MockModelAPI（离线演示模式）")
    return MockModelAPI()


# ---------------------------------------------------------------------------
# 便捷测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    api = auto_detect_model_api()
    print(f"选中的模型接口: {api.name}, available={api.available()}")
    if api.available() and api.name != "mock":
        try:
            reply = api.chat(
                system="你是一个简短的测试助手。",
                messages=[{"role": "user", "content": "用一句话介绍你自己。"}],
                max_tokens=100,
            )
            print(f"真实回复: {reply[:200]}")
        except ModelError as e:
            print(f"调用失败: {e}")
    else:
        print("处于离线模式，未调用真实模型。")
