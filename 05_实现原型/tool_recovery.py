# -*- coding: utf-8 -*-
"""
PAEG 工具调用错误恢复层（v0.19.2）

对标 CrewAI / AutoGPT / LiteLLM / LangGraph 的行业共识：
1. 防：硬超时（防止 AgentLoop 卡死）
2. 治：智能重试（区分瞬时/永久错误，指数退避+抖动）
3. 降：失败安全（返回教学友好的"基于训练数据"信号，不让 LLM 编造）
4. 记：每工具指标（注入 AgentLoop Reflect，供决策）

用法：
    from tool_recovery import with_recovery
    @with_recovery(max_retries=2, timeout_s=15, tool_name="web_search")
    def my_tool(...): ...
"""
from __future__ import annotations

import functools
import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("paeg.tool_recovery")


class ErrorClass(Enum):
    TRANSIENT = "transient"        # 网络超时/5xx/连接重置 → 重试
    PERMANENT = "permanent"        # 400/401/404/参数错 → 不重试
    RATE_LIMIT = "rate_limit"      # 429 → 重试+长退避
    QUOTA_EXHAUSTED = "quota"      # 配额耗尽 → 不重试+降级
    EMPTY_RESULT = "empty"         # 调用成功但无数据 → 视情况重试


@dataclass
class ToolMetrics:
    """每个工具的运行时指标。"""
    name: str
    calls: int = 0
    successes: int = 0
    retries: int = 0
    permanent_failures: int = 0
    total_latency_ms: float = 0.0
    last_error: str = ""


METRICS: Dict[str, ToolMetrics] = {}


# ─────────────────────────────────────
# 错误分类与退避
# ─────────────────────────────────────

def classify_error(exc: Exception) -> ErrorClass:
    """把异常映射到错误分类（决定重试 vs 降级）。"""
    msg = str(exc).lower()
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    try:
        code = int(code)
    except Exception:
        code = None

    # 配额
    if "quota" in msg or "usage_limit" in msg or "billing" in msg:
        return ErrorClass.QUOTA_EXHAUSTED
    # 限流
    if code == 429 or "rate_limit" in msg:
        return ErrorClass.RATE_LIMIT
    # 永久
    if code in (400, 401, 403, 404, 422):
        return ErrorClass.PERMANENT
    if "unauthorized" in msg or "forbidden" in msg or "invalid" in msg:
        return ErrorClass.PERMANENT
    # TypeError/ValueError = 参数错误（永久，不重试）
    if isinstance(exc, TypeError) or "unexpected keyword" in msg \
            or "argument" in msg or "required" in msg:
        return ErrorClass.PERMANENT
    # 瞬时
    if code in (500, 502, 503, 504, 520, 524, 529):
        return ErrorClass.TRANSIENT
    if "timeout" in msg or "connection" in msg or "reset" in msg \
            or "timed out" in msg or "network" in msg:
        return ErrorClass.TRANSIENT
    return ErrorClass.TRANSIENT  # 保守：默认重试


def compute_backoff(attempt: int, error_class: ErrorClass,
                   retry_after: Optional[float] = None) -> float:
    """退避：优先服务器 Retry-After，否则指数退避 + 抖动。"""
    if retry_after is not None:
        return min(retry_after, 30.0)
    if error_class == ErrorClass.RATE_LIMIT:
        base = 5 * (2 ** attempt)
    else:
        base = 2 ** attempt
    return base + random.uniform(0, 0.5 * base)


# ─────────────────────────────────────
# 空结果检测
# ─────────────────────────────────────

def _is_empty_result(tool_name: str, result: Any) -> bool:
    """检测"调用成功但没拿到数据"（web_search 最常见的失败）。"""
    if result is None:
        return True
    if isinstance(result, (list, dict)) and len(result) == 0:
        return True
    if isinstance(result, str):
        s = result.strip()
        if s in ("", "[]", "{}", "None", "null"):
            return True
        markers = {
            "web_search": ["搜索未返回结果", "未返回有效结果", "no results"],
            "fetch_page": ["404", "not found", "页面不存在"],
        }
        low = s.lower()
        if tool_name in markers:
            return any(m.lower() in low for m in markers[tool_name])
    return False


# ─────────────────────────────────────
# 优雅降级信号
# ─────────────────────────────────────

def graceful_degradation(tool_name: str, exc: Optional[Exception] = None) -> str:
    """失败兜底——返回教学友好的"不知道"信号（防 LLM 编造）。"""
    msg = str(exc)[:100] if exc else "unknown"
    return json.dumps({
        "status": "tool_unavailable",
        "tool": tool_name,
        "error": msg,
        "guidance": "工具暂时不可用。请基于已有知识回答，并明确告诉学生"
                    "'这是我基于训练数据回答的，最新信息请查证'。",
    }, ensure_ascii=False)


# ─────────────────────────────────────
# 重试装饰器
# ─────────────────────────────────────

def with_recovery(*, max_retries: int = 2, timeout_s: float = 15.0,
                  fallback: Optional[Callable] = None,
                  tool_name: Optional[str] = None):
    """给工具加三层防护：硬超时 + 智能重试 + 失败降级。"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = tool_name or func.__name__
            if name not in METRICS:
                METRICS[name] = ToolMetrics(name=name)
            m = METRICS[name]

            last_exc = None
            for attempt in range(max_retries + 1):
                m.calls += 1  # 每次真实调用都计数
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    # 空结果视为失败（可重试一次）
                    if _is_empty_result(name, result):
                        if attempt < max_retries:
                            raise ValueError("empty result (retryable)")
                        # 空结果且重试完 → 交给降级
                        raise ValueError("empty result after retries")
                    m.successes += 1
                    m.total_latency_ms += (time.perf_counter() - start) * 1000
                    return result
                except Exception as exc:
                    last_exc = exc
                    err_class = classify_error(exc)
                    m.last_error = str(exc)[:200]

                    if err_class in (ErrorClass.PERMANENT, ErrorClass.QUOTA_EXHAUSTED):
                        m.permanent_failures += 1
                        # TypeError（参数错误）重新抛出，让调用方（execute_tool）给参数建议
                        if isinstance(exc, TypeError):
                            raise
                        break
                    if attempt < max_retries:
                        m.retries += 1
                        wait_s = compute_backoff(attempt, err_class)
                        logger.info(f"[{name}] retry {attempt+1} after {wait_s:.1f}s "
                                    f"({err_class.value})")
                        time.sleep(min(wait_s, timeout_s))
                    else:
                        break

            # 失败降级
            if fallback is not None:
                try:
                    fb = fallback(*args, **kwargs)
                    if not _is_empty_result(name, fb):
                        return fb
                except Exception:
                    pass
            return graceful_degradation(name, last_exc)
        return wrapper
    return decorator


def get_metrics_summary() -> Dict[str, dict]:
    """给 AgentLoop Reflect 阶段用的指标汇总。"""
    summary = {}
    for name, m in METRICS.items():
        if m.calls == 0:
            continue
        summary[name] = {
            "calls": m.calls,
            "success_rate": round(m.successes / m.calls, 2),
            "retry_rate": round(m.retries / m.calls, 2),
            "permanent_failure_rate": round(m.permanent_failures / m.calls, 2),
            "avg_latency_ms": round(m.total_latency_ms / m.calls, 1),
            "last_error": m.last_error[:100],
        }
    return summary


def reset_metrics():
    METRICS.clear()


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    # 自测
    calls = [0]

    @with_recovery(max_retries=3, tool_name="test_flaky")
    def flaky_tool(q):
        calls[0] += 1
        if calls[0] < 3:
            raise TimeoutError("simulated timeout")
        return json.dumps([{"title": "ok", "url": "x"}])

    r = flaky_tool("query")
    print("瞬时错误重试:", "ok" in r, f"(调用{calls[0]}次, 期望3)")
    print("指标:", get_metrics_summary())
    reset_metrics()

    calls2 = [0]

    @with_recovery(max_retries=3, tool_name="test_bad")
    def bad_tool(q):
        calls2[0] += 1
        raise ValueError("401 Unauthorized")

    r2 = bad_tool("q")
    print("\n永久错误不重试:", calls2[0] == 1, f"(调用{calls2[0]}次, 期望1)")
    import json as _j
    parsed = _j.loads(r2)
    print("降级信号:", parsed.get("status"), "| guidance:", "训练数据" in parsed.get("guidance", ""))
