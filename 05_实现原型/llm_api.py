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

    def chat(self, system: str, messages: list, max_tokens: int = 8000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        """一次对话。messages: [{"role": "user"/"assistant", "content": str}, ...]
        返回模型回复文本。若模型请求工具调用，返回 JSON 字符串（含 tool_calls）。
        失败抛 ModelError。"""
        raise NotImplementedError

    def available(self) -> bool:
        return False


class ModelError(Exception):
    """模型调用错误。§3.60 ⭐ 增加分类：http_code + permanent（供运行时 failover 判断）。"""

    def __init__(self, message: str, http_code: int = 0):
        super().__init__(message)
        self.http_code = http_code
        # 401/403 = key 无效（本会话不再重试）；429/5xx/网络 = 临时故障（冷却后重试）
        self.permanent = http_code in (401, 403)
        self.failoverable = (
            http_code in (401, 403, 429) or 500 <= http_code < 600 or http_code == 0
        )

    @classmethod
    def from_http(cls, code: int, detail: str) -> "ModelError":
        return cls(f"HTTP {code}: {detail}", http_code=code)


class MockModelAPI(ModelAPI):
    """兜底模型：返回结构化占位回复（v0.1 行为，用于离线演示与测试）。"""

    name = "mock"

    def __init__(self, echo: str = "[模拟回复]"):
        self._echo = echo

    def chat(self, system: str, messages: list, max_tokens: int = 8000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        # v1.2.23 ⭐ 签名对齐（Round 11 挖掘）：MockModelAPI 也需接受 tools/tool_choice，
        # 否则 failover 候选含 mock 时同样 TypeError（Anthropic 同类隐患一并修复）。
        return self._echo

    def available(self) -> bool:
        return True


class OpenAICompatModelAPI(ModelAPI):
    """OpenAI 兼容端点（DeepSeek / OpenAI / Ollama / Qwen / Kimi / 智谱 ...）。"""

    name = "openai_compat"

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout: int = 60, temperature: float = 0.7,
                 provider_label: str = "openai_compat"):
        # §3.60 ⭐ provider_label：日志显示 deepseek/qwen 而非 openai_compat（failover 诊断关键）
        self.provider_label = provider_label
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

    def chat(self, system: str, messages: list, max_tokens: int = 8000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            # v0.68 修复：v4-flash 是思考型模型——普通 chat 必须显式关思考，
            # 否则 content 被思考链占满返回空（OFF/B 路径被污染）。
            # 只有 ReasonerModelAPI（A 路径）才开启 thinking。
            # max_tokens 放开到 4000：思考型模型需要 token 空间（用户要求不限制）。
            "thinking": {"type": "disabled"},
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
            # v0.68 修复：deepseek-v4-flash 是思考型模型——即使不请求 thinking，
            # API 也先输出 reasoning_content。content 为空时降级取 reasoning_content 尾部
            # （避免空响应导致调用方走兜底/报错）。
            _content = msg.get("content") or ""
            if not _content.strip():
                _rc = msg.get("reasoning_content") or ""
                if _rc.strip():
                    # 取思考链最后一句作为可用内容（去掉思考前缀，保留结论性文字）
                    _content = _rc.strip().split("\n")[-1][:500]
            return _content
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise ModelError.from_http(e.code, detail) from e
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

    def chat(self, system: str, messages: list, max_tokens: int = 8000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        """保持原 chat() 行为：返回 content 字符串（向后兼容）。

        thinking 通过 chat_with_reasoning() 单独获取。
        """
        r = self.chat_with_reasoning(system, messages, max_tokens,
                                     temperature, tools, tool_choice)
        return r.get("content") or ""

    def chat_with_reasoning(self, system: str, messages: list,
                            max_tokens: int = 8000,
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
            # §3.79 D1 ⭐ token 埋点（SLO token 成本；防御式，不阻断主流程）
            try:
                from observability import record_metric
                record_metric("paeg.llm.tokens", float(usage.get("total_tokens", 0) or 0))
            except Exception:
                pass
            return {
                "thinking": msg.get("reasoning_content") or "",
                "content": msg.get("content") or "",
                "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise ModelError.from_http(e.code, detail) from e
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

    def chat(self, system: str, messages: list, max_tokens: int = 8000,
             temperature: float = 0.7, tools: Optional[list] = None,
             tool_choice: Optional[str] = None) -> str:
        # v1.2.23 ⭐ P0 修复（Round 11 挖掘）：llm_adapter failover 对全部候选统一传
        # tools/tool_choice——AnthropicModelAPI.chat 原签名缺这两个参数 → TypeError →
        # 被 failover 循环吞掉 → 若主候选失败，anthropic 兜底必然失败（"got an unexpected
        # keyword argument 'tools'"）。现签名对齐 OpenAICompatModelAPI，支持 tools 透传
        # （Anthropic Messages API 原生支持 tools 字段），tool_choice 仅支持显式字符串
        # （"auto"/"any"/"tool"），不支持 dict 时忽略（降级普通生成，不抛错）。
        payload = {
            "model": self._model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
        _tc = self._tool_choice_payload(tool_choice)
        if _tc:
            payload["tool_choice"] = _tc
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
            raise ModelError.from_http(e.code, detail) from e
        except error.URLError as e:
            raise ModelError(f"[{self.name}] 网络错误: {e.reason}") from e
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ModelError(f"[{self.name}] 响应解析失败: {e}") from e

    def available(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _tool_choice_payload(tool_choice):
        """Anthropic tool_choice 归一化：str → {"type": str}；dict → 原样；其他 → None。"""
        if not tool_choice:
            return None
        if isinstance(tool_choice, str):
            return {"type": tool_choice}
        if isinstance(tool_choice, dict):
            return tool_choice
        return None  # 其他类型：忽略（Anthropic 不支持的复杂 tool_choice 降级）


# ---------------------------------------------------------------------------
# 自动配置发现
# ---------------------------------------------------------------------------

def _find_opencode_auth() -> dict:
    """在 opencode auth.json 中查找 deepseek / anthropic 凭据。
    返回 {"deepseek": key} 或 {"anthropic": key} 等，找不到返回 {}。

    §3.70 ⭐ 项目级优先：先查项目目录 secret/auth.json（本地化配置，
    不入 git——.gitignore 已忽略 auth.json 系列），再查 opencode 系统级。
    """
    # 项目级 secret/auth.json（§3.70 本地化配置——最高优先级）
    project_secret = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "secret", "auth.json"
    )
    candidates = [
        project_secret,  # §3.70 ⭐ 项目本地化（用户级/项目级公共配置）
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
    1. PAEG_API_KEY + PAEG_API_BASE（自定义，默认 DeepSeek）
    2. DEEPSEEK_API_KEY -> DeepSeek（V4-Flash）
    3. QWEN_API_KEY / DASHSCOPE_API_KEY -> 阿里通义千问（Qwen）
    4. ANTHROPIC_API_KEY -> Anthropic / OPENAI_API_KEY -> OpenAI
    5. opencode auth.json（deepseek 优先，本地开发兜底）
    6. 全部不可用 -> MockModelAPI（离线演示）

    v0.51 ⭐ 深度思考：PAEG_MODEL=deepseek-v4-pro / PAEG_REASONING=on 时
    返回 ReasonerModelAPI（thinking 模式）；否则默认 V4-Flash 普通对话。
    旧别名 deepseek-chat/deepseek-reasoner 已下线（2026-07-24），自动迁移到 V4。

    §3.55 ⭐ 多模型 fallback（2026-08-16）：魔搭 Docker 无 DeepSeek key 时
    自动 fallback 到阿里通义千问，避免落到 Mock（"对话不输出"根因修复）。
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

    # 2. DeepSeek
    if os.environ.get("DEEPSEEK_API_KEY"):
        log("使用 DEEPSEEK_API_KEY")
        return _maybe_reasoner(
            os.environ["DEEPSEEK_API_KEY"], "https://api.deepseek.com/v1",
            _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash")))

    # 3. 阿里通义千问（QWEN_API_KEY 或 DASHSCOPE_API_KEY）§3.55
    _qwen_key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if _qwen_key:
        log("使用 QWEN_API_KEY / DASHSCOPE_API_KEY（阿里通义千问）")
        _qwen_model = os.environ.get("QWEN_MODEL", "qwen-plus")
        return OpenAICompatModelAPI(
            _qwen_key, "https://dashscope.aliyuncs.com/compatible-mode/v1", _qwen_model)

    # 4. Anthropic / OpenAI
    if os.environ.get("ANTHROPIC_API_KEY"):
        log("使用 ANTHROPIC_API_KEY")
        return AnthropicModelAPI(os.environ["ANTHROPIC_API_KEY"])
    if os.environ.get("OPENAI_API_KEY"):
        log("使用 OPENAI_API_KEY")
        return OpenAICompatModelAPI(
            os.environ["OPENAI_API_KEY"], "https://api.openai.com/v1", "gpt-4o-mini")

    # 6. opencode auth.json（本地开发兜底）§3.55
    auth = _find_opencode_auth()
    if auth.get("deepseek"):
        log("使用 opencode auth.json 中的 DeepSeek 凭据")
        return _maybe_reasoner(
            auth["deepseek"], "https://api.deepseek.com/v1",
            _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash")))
    if auth.get("anthropic"):
        log("使用 opencode auth.json 中的 Anthropic 凭据")
        return AnthropicModelAPI(auth["anthropic"])

    # 7. 兜底（离线演示）§3.55
    log("未找到 API 凭据，回退到 MockModelAPI（离线演示模式）")
    return MockModelAPI()


def detect_model_candidates(verbose: bool = True) -> list:
    """§3.60 ⭐ 检测全部可用 LLM provider（有序候选列表，供运行时 failover）。

    与 auto_detect_model_api 同优先级，但**收集所有**有 key 的 provider：
    [PAEG自定义, DeepSeek, Qwen, Anthropic, OpenAI, auth.json...]（按优先级）
    零真实 key 时返回 [MockModelAPI]（离线演示，与旧行为一致）。
    返回 list[ModelAPI]，首个为首选。
    """
    def log(msg):
        if verbose:
            print(f"[llm_api] {msg}", file=sys.stderr)

    def _migrate_model(m: str) -> str:
        return "deepseek-v4-flash" if m in ("deepseek-chat", "deepseek-reasoner") else m

    cands = []
    # 1. 自定义
    custom_key = os.environ.get("PAEG_API_KEY")
    if custom_key:
        cands.append(OpenAICompatModelAPI(
            custom_key,
            os.environ.get("PAEG_API_BASE", "https://api.deepseek.com/v1"),
            _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash")),
            provider_label="custom"))
    # 2. DeepSeek
    if os.environ.get("DEEPSEEK_API_KEY"):
        cands.append(OpenAICompatModelAPI(
            os.environ["DEEPSEEK_API_KEY"], "https://api.deepseek.com/v1",
            _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash")),
            provider_label="deepseek"))
    # 3. Qwen（§3.60 ⭐ 新增——用户配置了但从未被用）
    _qwen_key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if _qwen_key:
        cands.append(OpenAICompatModelAPI(
            _qwen_key, "https://dashscope.aliyuncs.com/compatible-mode/v1",
            os.environ.get("QWEN_MODEL", "qwen-plus"),
            provider_label="qwen"))
    # 4. Anthropic / OpenAI
    if os.environ.get("ANTHROPIC_API_KEY"):
        cands.append(AnthropicModelAPI(os.environ["ANTHROPIC_API_KEY"]))
    if os.environ.get("OPENAI_API_KEY"):
        cands.append(OpenAICompatModelAPI(
            os.environ["OPENAI_API_KEY"], "https://api.openai.com/v1", "gpt-4o-mini",
            provider_label="openai"))
    # 5. auth.json
    auth = _find_opencode_auth()
    if auth.get("deepseek"):
        cands.append(OpenAICompatModelAPI(
            auth["deepseek"], "https://api.deepseek.com/v1",
            _migrate_model(os.environ.get("PAEG_MODEL", "deepseek-v4-flash")),
            provider_label="auth-deepseek"))
    if auth.get("anthropic"):
        cands.append(AnthropicModelAPI(auth["anthropic"]))

    # 去重：同 (base_url, api_key[:8]) 只留一个（env + auth.json 同 key 场景）
    seen, uniq = set(), []
    for c in cands:
        key = (getattr(c, "_base_url", ""), str(getattr(c, "_api_key", ""))[:8])
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    cands = uniq

    if not cands:
        log("未找到 API 凭据，候选仅 MockModelAPI（离线演示）")
        return [MockModelAPI()]
    log(f"检测到 {len(cands)} 个候选: {[getattr(c, 'provider_label', c.name) for c in cands]}")
    return cands


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
