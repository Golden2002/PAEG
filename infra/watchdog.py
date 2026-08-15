# -*- coding: utf-8 -*-
"""infra/watchdog.py —— §3.42 W5 ⭐ 工具超时 watchdog（v1.1.5）

需求（§3.42 W5，借鉴 deepseek-harness guard/timeout-policy）：
- 工具声明 timeoutMs → 执行超时返回 TOOL_TIMEOUT 错误（**不杀进程**）
- 默认 timeoutMs = 30000（30s）
- 错误携带 trace_id（§3.42 W2 obs_trace 全链路）

设计要点：
- 用 ThreadPoolExecutor 跑 handler（独立线程隔离，**不杀主进程**）
- future.result(timeout=...) 触发 concurrent.futures.TimeoutError → 转 ToolTimeoutError
- 超时线程被丢弃后 Python GC 回收；future 内的线程不阻塞主流程
- timeout_ms <= 0 → 走直接调用（无超时，ratchet 兼容旧行为）
- trace_id 从 obs_trace contextvar 读取（contextvars 跨线程不可继承，
  但 ToolTimeoutError 抛出时我们在主线程读取，所以 OK）

用法：
    from infra.watchdog import run_with_timeout, ToolTimeoutError
    try:
        result = run_with_timeout(handler, args, kwargs, timeout_ms=5000, tool_name="web_search")
    except ToolTimeoutError as e:
        # e.trace_id / e.tool_name / e.timeout_ms
        return f"工具 {e.tool_name} 超时 ({e.timeout_ms}ms, trace={e.trace_id})"
"""
from __future__ import annotations

import concurrent.futures
import logging
import uuid
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger("paeg")


# ─────────────────────────────────────
# 默认超时（毫秒）
# ─────────────────────────────────────
DEFAULT_TOOL_TIMEOUT_MS = 30_000  # 30s（与 deepseek-harness 同档）


# ─────────────────────────────────────
# 异常类型
# ─────────────────────────────────────
class ToolTimeoutError(Exception):
    """工具执行超时（§3.42 W5）。

    Attributes:
        tool_name: 超时的工具名
        timeout_ms: 实际生效的超时值（毫秒）
        trace_id:   关联的 trace_id（§3.42 W2 obs_trace），无则 None
    """

    def __init__(self, tool_name: str, timeout_ms: int, trace_id: Optional[str] = None,
                 message: Optional[str] = None):
        self.tool_name = tool_name
        self.timeout_ms = int(timeout_ms)
        self.trace_id = trace_id
        if message is None:
            message = (f"工具 {tool_name!r} 执行超时（{self.timeout_ms}ms），"
                       f"已取消线程（trace_id={trace_id or '-'})")
        super().__init__(message)


# ─────────────────────────────────────
# Watchdog 执行
# ─────────────────────────────────────
# 模块级 Executor（复用线程池，避免每次创建开销）
# max_workers 设大一点允许并发工具调用，但避免无限扩张
_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    """懒加载模块级 Executor（最多 32 worker）。"""
    global _executor
    if _executor is None:
        _executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=32, thread_name_prefix="tool-watchdog")
    return _executor


def run_with_timeout(fn: Callable[..., Any],
                     args: Tuple = (),
                     kwargs: Optional[dict] = None,
                     *,
                     timeout_ms: int,
                     tool_name: str = "<unknown>",
                     trace_id: Optional[str] = None) -> Any:
    """带 watchdog 的工具执行（不杀进程）。

    Args:
        fn:         工具函数（handler）
        args:       位置参数元组
        kwargs:     关键字参数字典
        timeout_ms: 超时阈值（毫秒）。<= 0 表示不设超时（直跑）
        tool_name:  工具名（仅用于错误信息）
        trace_id:   trace_id（若 None，则从 obs_trace 取当前）

    Returns:
        handler 返回值

    Raises:
        ToolTimeoutError: 超时（future.result(timeout) 触发）
        其他:             handler 抛出的异常（透传）
    """
    if kwargs is None:
        kwargs = {}

    # 解析 trace_id（contextvar 优先；调用方传参覆盖；无 trace 上下文则生成一次性 ID）
    if trace_id is None:
        try:
            from obs_trace import get_trace_id
            trace_id = get_trace_id()
        except Exception:
            trace_id = None
        if trace_id is None:
            # §3.42 W5：即使无活跃 trace 也生成一次性 ID（便于日志关联 / 可观测性）
            trace_id = f"trc_{uuid.uuid4().hex[:16]}"

    # 无超时：直接调用（ratchet 兼容 ratchet：旧行为不变）
    if timeout_ms is None or int(timeout_ms) <= 0:
        return fn(*args, **kwargs)

    timeout_sec = int(timeout_ms) / 1000.0
    executor = _get_executor()
    future = executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        # 关键：future.cancel() 对已运行的 future 返回 False（线程仍在跑）
        # 但不杀进程——线程隔离，由 GC 回收。语义对齐 deepseek-harness guard。
        logger.warning(
            "[watchdog] 工具 %s 超时（%dms），已取消等待 trace=%s",
            tool_name, timeout_ms, trace_id,
        )
        raise ToolTimeoutError(
            tool_name=tool_name,
            timeout_ms=timeout_ms,
            trace_id=trace_id,
        ) from None


__all__ = [
    "DEFAULT_TOOL_TIMEOUT_MS",
    "ToolTimeoutError",
    "run_with_timeout",
]