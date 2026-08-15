# -*- coding: utf-8 -*-
"""infra/retry_policy.py —— §3.42 W4 ⭐ 分类错误码重试（借鉴 deepseek-harness llm/llm-retry）

需求（W4）：
- 把 _safe_chat / chat 的错误处理升级为分类错误码重试
- 6 个错误类：rate_limit / context_overflow / tool_validation /
  transient_5xx / auth / unknown
- 每类不同退避曲线 + 重试预算
  - rate_limit：激进退避（让服务端恢复）
  - transient_5xx：中等退避
  - auth / context_overflow / tool_validation：直接失败（重试无意义）
  - unknown：保守退避（兜底）
- trace_id 附加到每次重试（observability 关联）

设计原则：
- **ratchet**：subagents._safe_chat 签名不变，仅替换内部重试块
- **可测试**：`classify_error` / `backoff_curve` / `retry_budget` 都是纯函数
- **可观测**：每次重试调用 `on_retry(attempt, err, code, trace_id)` 回调
- **可注入**：`sleep` 参数可注入（测试用零等待，生产用 time.sleep）
"""
from __future__ import annotations

import enum
import re
import time
from typing import Any, Callable, Optional


# ────────────────────────────────────────────────────────────
#  错误码枚举（6 类）
# ────────────────────────────────────────────────────────────
class RetryCode(str, enum.Enum):
    """LLM 调用错误分类（str 混入便于日志/事件 JSON 序列化）。"""
    RATE_LIMIT = "rate_limit"            # 429 — 限流
    TRANSIENT_5XX = "transient_5xx"      # 500/502/503/504 — 服务端瞬时错误
    AUTH = "auth"                        # 401/403 — 鉴权失败
    CONTEXT_OVERFLOW = "context_overflow"  # 400 context_length_exceeded
    TOOL_VALIDATION = "tool_validation"  # 400 invalid tool_calls
    UNKNOWN = "unknown"                  # 兜底


# ────────────────────────────────────────────────────────────
#  ModelError 重新导出（避免循环 import）
# ────────────────────────────────────────────────────────────
# 设计：从 llm_api 导入 ModelError；如果 llm_api 还没加载，使用本地兜底
try:
    from llm_api import ModelError  # type: ignore
except Exception:  # noqa: BLE001
    class ModelError(Exception):
        """兜底 ModelError（llm_api 不可用时）。"""
        pass


# ────────────────────────────────────────────────────────────
#  HTTP 码 → RetryCode 映射
# ────────────────────────────────────────────────────────────
def _http_code_from_message(msg: str) -> Optional[int]:
    """从 ModelError 消息中提取 HTTP 状态码（llm_api 抛出的格式是
    '[<provider>] HTTP <code>: <detail>'）。
    """
    if not msg:
        return None
    m = re.search(r"\bHTTP\s+(\d{3})\b", msg)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None
    return None


def classify_error(err: BaseException) -> RetryCode:
    """把异常分类为 6 个错误码之一。

    优先级（从最具体到最通用）：
    1. context_overflow：message 含 'context_length' / 'context_length_exceeded'
    2. tool_validation：message 含 'tool' 且 'invalid' / 'schema' 关键字
    3. rate_limit：HTTP 429
    4. auth：HTTP 401/403
    5. transient_5xx：HTTP 500/502/503/504
    6. unknown：兜底

    Args:
        err: LLM 调用抛出的异常（通常 ModelError）

    Returns:
        RetryCode 枚举值
    """
    msg = str(err or "")
    code = _http_code_from_message(msg)
    msg_l = msg.lower()

    # 1. context_overflow（按特征字符串优先于 HTTP 码——400 也可能包含）
    if "context_length" in msg_l or "context_length_exceeded" in msg_l \
            or "maximum context length" in msg_l:
        return RetryCode.CONTEXT_OVERFLOW

    # 2. tool_validation
    if "tool" in msg_l and ("invalid" in msg_l or "schema" in msg_l
                            or "validation" in msg_l):
        return RetryCode.TOOL_VALIDATION

    # 3-5. 按 HTTP 码分类
    if code == 429:
        return RetryCode.RATE_LIMIT
    if code in (401, 403):
        return RetryCode.AUTH
    if code in (500, 502, 503, 504):
        return RetryCode.TRANSIENT_5XX

    # 6. 兜底
    return RetryCode.UNKNOWN


# ────────────────────────────────────────────────────────────
#  退避曲线 & 重试预算
# ────────────────────────────────────────────────────────────
def backoff_curve(code: RetryCode) -> list:
    """返回退避曲线（秒）：第 i 次重试前等待的时间。

    曲线长度 = retry_budget(code)（即"最多还能重试几次"对应的等待值）。
    设计：
    - rate_limit：3 次退避 [2, 4, 8]（共 14s）—— 让服务端配额恢复
    - transient_5xx：2 次退避 [1, 2]（共 3s）—— 中等等待
    - unknown：1 次退避 [1]（共 1s）—— 保守兜底
    - auth / context_overflow / tool_validation：空 []（不重试）
    """
    if code == RetryCode.RATE_LIMIT:
        return [2.0, 4.0, 8.0]
    if code == RetryCode.TRANSIENT_5XX:
        return [1.0, 2.0]
    if code == RetryCode.UNKNOWN:
        return [1.0]
    # auth / context_overflow / tool_validation：不重试
    return []


def retry_budget(code: RetryCode) -> int:
    """返回该错误码的重试预算（最多额外重试几次）。"""
    return len(backoff_curve(code))


def should_retry(code: RetryCode) -> bool:
    """是否应该重试？auth / context_overflow / tool_validation 直接失败。"""
    return retry_budget(code) > 0


# ────────────────────────────────────────────────────────────
#  退避实际值（带 jitter 开关，默认关闭以保证测试稳定）
# ────────────────────────────────────────────────────────────
def _compute_sleep(curve_value: float, jitter: bool = False) -> float:
    """计算实际 sleep 时长（默认无 jitter——可复现/可测试）。"""
    if not jitter:
        return curve_value
    # 简单 ±20% jitter（生产用，避免雪崩）
    import random
    return curve_value * (0.8 + 0.4 * random.random())


# ────────────────────────────────────────────────────────────
#  默认 sleep（生产用 time.sleep）
# ────────────────────────────────────────────────────────────
def _default_sleep(seconds: float) -> None:
    """默认 sleep 函数（生产）。测试可注入 _zero_sleep。"""
    if seconds > 0:
        time.sleep(seconds)


def _zero_sleep(seconds: float) -> None:
    """零等待 sleep（测试用，让 backoff 立即返回）。"""
    return None


# ────────────────────────────────────────────────────────────
#  核心：retry_with_policy（高层封装）
# ────────────────────────────────────────────────────────────
def retry_with_policy(
    fn: Callable[[], Any],
    *,
    trace_id: Optional[str] = None,
    on_retry: Optional[Callable[[int, BaseException, RetryCode, Optional[str]], None]] = None,
    sleep: Callable[[float], None] = _default_sleep,
    jitter: bool = False,
) -> Any:
    """带分类错误码策略的重试执行器。

    Args:
        fn: 无参 callable，每次重试调用一次。返回值为结果；抛异常视为失败。
        trace_id: 当前 trace_id（传给 on_retry 回调，用于 observability 关联）。
        on_retry: 重试前回调 `on_retry(attempt, err, code, trace_id)`。
                  attempt 是 0-indexed（第 0 次 = 第一次失败后即将重试）。
        sleep: sleep 函数（可注入测试用零等待）。
        jitter: 是否给退避加随机抖动（生产防雪崩；测试关闭）。

    Returns:
        fn() 成功时的返回值。

    Raises:
        fn 抛出的最后一个异常（重试耗尽或不可重试时）。
    """
    # 第一次调用：先试一次，根据错误分类动态决定是否重试
    # （而不是预先按某个码固定循环上限——错误码未知要等异常后才能分类）
    max_total_attempts = 4  # 硬上限：rate_limit(3 retry) + 1 = 4
    for attempt in range(max_total_attempts):
        try:
            return fn()
        except BaseException as e:  # noqa: BLE001 — 重试器必须捕获所有
            code = classify_error(e)
            curve = backoff_curve(code)
            budget = len(curve)

            # 不可重试 / 预算耗尽 → 抛出
            if budget == 0 or attempt >= budget:
                raise

            # 计算本次重试前等待时间
            wait = _compute_sleep(curve[attempt], jitter=jitter)
            # 通知回调（每次重试都关联 trace_id）
            if on_retry is not None:
                try:
                    on_retry(attempt, e, code, trace_id)
                except Exception:  # noqa: BLE001 — 回调异常不影响主流程
                    pass
            # 实际等待
            sleep(wait)

    # 不可达：循环要么 return、要么 raise
    raise RuntimeError("retry_with_policy: unreachable")
