# -*- coding: utf-8 -*-
"""test_llm_retry_codes.py —— §3.42 W4 ⭐ 分类错误码重试（借鉴 deepseek-harness llm-retry）

需求（W4）：
- 按错误类型分类（rate_limit / context_overflow / tool_validation /
  transient_5xx / auth / unknown）
- 每类不同退避曲线 + 重试预算（auth 不重试直接失败）
- trace_id 附加到每次重试（供 observability 关联）

设计：
- infra/retry_policy.py 提供 classify_error / backoff_curve / retry_budget /
  retry_with_policy（高层封装）
- subagents._safe_chat 调用 retry_with_policy 替换原 3 次固定退避
"""
from __future__ import annotations

import importlib
import sys
import time
from unittest.mock import MagicMock

import pytest


# ────────────────────────────────────────────────────────────
#  工具：动态加载 retry_policy（避免在 conftest 引入新依赖）
# ────────────────────────────────────────────────────────────
def _load_retry_policy():
    """延迟加载 infra.retry_policy（模块可能在测试间被重置）。"""
    if "infra.retry_policy" in sys.modules:
        return importlib.reload(sys.modules["infra.retry_policy"])
    return importlib.import_module("infra.retry_policy")


# ────────────────────────────────────────────────────────────
#  测试 1：rate_limit 分类
# ────────────────────────────────────────────────────────────
def test_error_classified_rate_limit():
    """429 → rate_limit 类 + 退避重试（应重试）。"""
    rp = _load_retry_policy()
    # 真实 ModelError 包含 'HTTP 429' 字符串（llm_api.py 抛出的格式）
    err = rp.ModelError("[openai_compat] HTTP 429: rate limit exceeded")
    code = rp.classify_error(err)
    assert code == rp.RetryCode.RATE_LIMIT, \
        f"429 应被分类为 RATE_LIMIT，实际 {code}"
    assert rp.retry_budget(code) >= 1, "rate_limit 应至少重试 1 次"
    assert rp.should_retry(code) is True, "rate_limit 应被重试"


# ────────────────────────────────────────────────────────────
#  测试 2：transient_5xx 分类
# ────────────────────────────────────────────────────────────
def test_error_classified_transient_5xx():
    """500/502/503 → transient_5xx 类 + 重试。"""
    rp = _load_retry_policy()
    for status in (500, 502, 503, 504):
        err = rp.ModelError(f"[openai_compat] HTTP {status}: server error")
        code = rp.classify_error(err)
        assert code == rp.RetryCode.TRANSIENT_5XX, \
            f"HTTP {status} 应被分类为 TRANSIENT_5XX，实际 {code}"
    assert rp.retry_budget(rp.RetryCode.TRANSIENT_5XX) >= 1
    assert rp.should_retry(rp.RetryCode.TRANSIENT_5XX) is True


# ────────────────────────────────────────────────────────────
#  测试 3：auth 不重试（直接失败）
# ────────────────────────────────────────────────────────────
def test_error_classified_auth():
    """401/403 → auth 类 + 不重试（直接失败）。"""
    rp = _load_retry_policy()
    for status in (401, 403):
        err = rp.ModelError(f"[openai_compat] HTTP {status}: unauthorized")
        code = rp.classify_error(err)
        assert code == rp.RetryCode.AUTH, \
            f"HTTP {status} 应被分类为 AUTH，实际 {code}"
    # 关键：auth 类不应重试（重试无意义，会持续失败）
    assert rp.should_retry(rp.RetryCode.AUTH) is False, \
        "auth 错误应直接失败，不重试"
    assert rp.retry_budget(rp.RetryCode.AUTH) == 0, \
        "auth 错误的 retry_budget 应为 0"


# ────────────────────────────────────────────────────────────
#  测试 4：unknown 异常 → 有限重试
# ────────────────────────────────────────────────────────────
def test_error_classified_unknown():
    """未识别的异常 → unknown 类 + 有限重试（兜底）。"""
    rp = _load_retry_policy()
    # 没有任何 HTTP 码标识的 ModelError
    err = rp.ModelError("[openai_compat] 网络错误: Name or service not known")
    code = rp.classify_error(err)
    assert code == rp.RetryCode.UNKNOWN, \
        f"网络/未知错误应被分类为 UNKNOWN，实际 {code}"
    # unknown 也允许重试（兜底），但预算应 < rate_limit（限流是"明确可重试"）
    assert rp.should_retry(rp.RetryCode.UNKNOWN) is True
    assert rp.retry_budget(rp.RetryCode.UNKNOWN) >= 1
    # 关键约束：unknown 的预算应 ≤ 限流的预算（防无限重试掩盖真实错误）
    assert rp.retry_budget(rp.RetryCode.UNKNOWN) <= rp.retry_budget(rp.RetryCode.RATE_LIMIT)


# ────────────────────────────────────────────────────────────
#  测试 5：退避曲线差异化
# ────────────────────────────────────────────────────────────
def test_retry_backoff_differs():
    """不同错误码应有不同的退避曲线。"""
    rp = _load_retry_policy()
    curve_rate = rp.backoff_curve(rp.RetryCode.RATE_LIMIT)
    curve_5xx = rp.backoff_curve(rp.RetryCode.TRANSIENT_5XX)
    curve_unknown = rp.backoff_curve(rp.RetryCode.UNKNOWN)

    # 1) 限流退避应更激进（更长等待让服务端恢复）
    # 2) 5xx 退避应中等
    # 3) unknown 退避应保守
    assert curve_rate, "rate_limit 退避曲线非空"
    assert curve_5xx, "transient_5xx 退避曲线非空"
    assert curve_unknown, "unknown 退避曲线非空"

    # 总等待时间应不同（限流应比 5xx 等待更久）
    assert sum(curve_rate) > sum(curve_5xx), \
        f"rate_limit 总退避 ({sum(curve_rate)}) 应 > transient_5xx 总退避 ({sum(curve_5xx)})"

    # 退避值应严格递增（指数退避核心特征）
    for label, curve in [("rate_limit", curve_rate),
                          ("transient_5xx", curve_5xx),
                          ("unknown", curve_unknown)]:
        for i in range(1, len(curve)):
            assert curve[i] > curve[i - 1], \
                f"{label} 退避曲线应在 i={i} 递增：{curve}"


# ────────────────────────────────────────────────────────────
#  测试 6：trace_id 附加到每次重试
# ────────────────────────────────────────────────────────────
def test_trace_id_attached_retry():
    """重试期间 trace_id 必须保持稳定（每次重试都关联到当前 trace）。

    验证：
    - retry_with_policy 接受 trace_id 参数
    - 重试回调能拿到 trace_id（用于日志/事件关联）
    - 重试成功后 result 包含 trace_id 信息
    """
    rp = _load_retry_policy()
    trace_id = "trc_test_abc123def456"
    seen_trace_ids = []
    call_count = {"n": 0}

    def flaky_call():
        call_count["n"] += 1
        # 第一次失败（429），第二次成功
        if call_count["n"] == 1:
            raise rp.ModelError("[openai_compat] HTTP 429: rate limit")
        return "success"

    def on_retry(attempt, err, code, current_trace_id):
        """每次重试的回调——记录 trace_id。"""
        seen_trace_ids.append(current_trace_id)

    result = rp.retry_with_policy(
        flaky_call,
        trace_id=trace_id,
        on_retry=on_retry,
        # 测试加速：让退避几乎为 0
        sleep=rp._zero_sleep,  # 由 retry_policy 提供的零等待
    )
    assert result == "success", "重试后应成功"
    # 第一次失败 → 触发 1 次 on_retry → seen_trace_ids 长度 = 1
    assert len(seen_trace_ids) == 1, f"应触发 1 次重试回调，实际 {len(seen_trace_ids)}"
    assert seen_trace_ids[0] == trace_id, \
        f"重试回调拿到的 trace_id 应等于传入值：期望 {trace_id}，实际 {seen_trace_ids[0]}"


# ────────────────────────────────────────────────────────────
#  附加测试：retry_with_policy 行为（auth 不重试直接抛）
# ────────────────────────────────────────────────────────────
def test_auth_does_not_retry_raises_immediately():
    """auth 错误：retry_with_policy 应在第一次失败时直接抛出（不重试）。"""
    rp = _load_retry_policy()
    call_count = {"n": 0}

    def failing_call():
        call_count["n"] += 1
        raise rp.ModelError("[openai_compat] HTTP 401: invalid api key")

    with pytest.raises(rp.ModelError) as exc_info:
        rp.retry_with_policy(
            failing_call,
            trace_id="trc_xyz",
            sleep=rp._zero_sleep,
        )
    assert call_count["n"] == 1, \
        f"auth 错误应只调用 1 次（不重试），实际调用了 {call_count['n']} 次"
    assert "HTTP 401" in str(exc_info.value)


# ────────────────────────────────────────────────────────────
#  附加测试：context_overflow / tool_validation 分类
# ────────────────────────────────────────────────────────────
def test_error_classified_context_overflow_and_tool_validation():
    """context_overflow (400 with context_length) + tool_validation 分类正确。"""
    rp = _load_retry_policy()
    # 1) context_overflow：message 提示 context_length / context_length_exceeded
    err_ctx = rp.ModelError("[openai_compat] HTTP 400: context_length_exceeded")
    code = rp.classify_error(err_ctx)
    assert code == rp.RetryCode.CONTEXT_OVERFLOW, \
        f"context_length_exceeded 应被分类为 CONTEXT_OVERFLOW，实际 {code}"
    # context_overflow 也不应重试（重试同一个 prompt 还会溢出）
    assert rp.should_retry(rp.RetryCode.CONTEXT_OVERFLOW) is False, \
        "context_overflow 应直接失败（让调用方截断上下文）"

    # 2) tool_validation：tool_calls 校验失败
    err_tool = rp.ModelError("[openai_compat] HTTP 400: invalid tool_calls schema")
    code2 = rp.classify_error(err_tool)
    assert code2 == rp.RetryCode.TOOL_VALIDATION, \
        f"tool 校验失败应被分类为 TOOL_VALIDATION，实际 {code2}"
    assert rp.should_retry(rp.RetryCode.TOOL_VALIDATION) is False, \
        "tool_validation 错误应直接失败（重试不会修复 schema）"
