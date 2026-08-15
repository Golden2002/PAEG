# -*- coding: utf-8 -*-
"""test_tool_timeout.py —— §3.42 W5 ⭐ 工具超时策略（tool-timeout-policy）

需求（§3.42 W5，借鉴 deepseek-harness guard/timeout-policy）：
- 工具声明加 timeoutMs 字段（mcp_tools.json / 内置均可声明）
- 执行超过 timeoutMs → 返回 TOOL_TIMEOUT 错误（不杀进程）
- 默认 timeoutMs = 30000（30s）
- 错误携带 trace_id（§3.42 W2 obs_trace 全链路）

TDD 红色测试（先 RED 后 GREEN）：
1. test_tool_with_timeout_ms           - 工具声明 timeoutMs，超时 → ToolTimeoutError
2. test_tool_without_timeout_default   - 缺 timeoutMs → 默认 30s（不触发）
3. test_timeout_raises_with_trace_id   - 超时错误带 trace_id
4. test_timeout_does_not_kill_process  - 超时后其他工具仍可执行

ratchet 铁律（不破坏现有行为）：
- 无 timeoutMs 声明的工具：行为完全不变（仍走原 handler）
- ThreadPoolExecutor 隔离：超时线程被丢弃后不污染主进程
"""
from __future__ import annotations

import os
import sys
import time

import pytest

# 确保项目根在 sys.path
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)


# ─────────────────────────────────────
# 辅助：注册一个临时 sleep 工具（带 / 不带 timeoutMs）
# ─────────────────────────────────────

def _register_slow_tool(name: str, sleep_seconds: float, timeout_ms: int = None) -> None:
    """动态注册一个 sleep 工具到 tool_registry._HANDLERS。
    timeout_ms=None 表示不声明（默认走 30s）。
    """
    import tool_registry

    def _slow(**kwargs):
        secs = float(kwargs.get("secs", sleep_seconds))
        time.sleep(secs)
        return f"done after {secs}s"

    tool_registry._HANDLERS[name] = _slow
    if timeout_ms is not None:
        tool_registry._HANDLERS_TIMEOUT_MS[name] = int(timeout_ms)
    elif name in tool_registry._HANDLERS_TIMEOUT_MS:
        del tool_registry._HANDLERS_TIMEOUT_MS[name]


@pytest.fixture
def _cleanup_test_tools():
    """测试结束移除临时工具（隔离）。"""
    import tool_registry
    created = []
    yield created
    for n in created:
        tool_registry._HANDLERS.pop(n, None)
        tool_registry._HANDLERS_TIMEOUT_MS.pop(n, None)


# ─────────────────────────────────────
# 测试 1：工具声明 timeoutMs → 超时 → ToolTimeoutError
# ─────────────────────────────────────

def test_tool_with_timeout_ms(_cleanup_test_tools):
    """工具声明 timeoutMs=200，执行 sleep(2s) → 抛 ToolTimeoutError。"""
    import tool_registry
    from infra.watchdog import ToolTimeoutError

    tool_name = "_w5_timeout_slow_tool"
    _cleanup_test_tools.append(tool_name)
    _register_slow_tool(tool_name, sleep_seconds=2.0, timeout_ms=200)

    start = time.time()
    with pytest.raises(ToolTimeoutError) as exc_info:
        tool_registry.execute_tool(tool_name, {"secs": 2.0})
    elapsed = time.time() - start

    # 超时应立即返回（不真等满 2s）
    assert elapsed < 1.5, f"超时未立即返回：等了 {elapsed:.2f}s"
    # 异常携带 trace_id
    assert exc_info.value.trace_id, f"ToolTimeoutError 应携带 trace_id，实际 {exc_info.value.trace_id!r}"
    # 异常携带工具名 + timeoutMs
    assert exc_info.value.tool_name == tool_name
    assert exc_info.value.timeout_ms == 200


# ─────────────────────────────────────
# 测试 2：无 timeoutMs → 默认 30s（快速工具不触发）
# ─────────────────────────────────────

def test_tool_without_timeout_default(_cleanup_test_tools):
    """无 timeoutMs 声明 → 默认 30s（sleep 0.5s 不触发超时，正常返回）。"""
    import tool_registry

    tool_name = "_w5_default_timeout_fast_tool"
    _cleanup_test_tools.append(tool_name)
    _register_slow_tool(tool_name, sleep_seconds=0.5, timeout_ms=None)

    # 快速工具：不应触发超时
    result = tool_registry.execute_tool(tool_name, {"secs": 0.5})
    assert result == "done after 0.5s", f"快速工具应正常返回，实际 {result!r}"

    # 默认 timeoutMs 应该是 30000ms（30s）
    default_ms = tool_registry._get_default_timeout_ms()
    assert default_ms == 30000, f"默认 timeoutMs 应为 30000，实际 {default_ms}"


# ─────────────────────────────────────
# 测试 3：超时错误带 trace_id
# ─────────────────────────────────────

def test_timeout_raises_with_trace_id(_cleanup_test_tools):
    """ToolTimeoutError 携带当前 obs_trace 的 trace_id。"""
    import tool_registry
    from infra.watchdog import ToolTimeoutError
    from obs_trace import begin_trace, end_trace, get_trace_id

    tool_name = "_w5_timeout_with_trace"
    _cleanup_test_tools.append(tool_name)
    _register_slow_tool(tool_name, sleep_seconds=2.0, timeout_ms=150)

    tid = begin_trace("chat_w5")
    try:
        with pytest.raises(ToolTimeoutError) as exc_info:
            tool_registry.execute_tool(tool_name, {"secs": 2.0})
        # 关键断言：trace_id 应来自 obs_trace（§3.42 W2 全链路）
        current_tid = get_trace_id()
        assert current_tid is not None, "trace 上下文应激活"
        assert exc_info.value.trace_id == current_tid, (
            f"ToolTimeoutError.trace_id={exc_info.value.trace_id!r} "
            f"应等于 obs_trace 当前 trace_id={current_tid!r}"
        )
    finally:
        end_trace()


# ─────────────────────────────────────
# 测试 4：超时后其他工具仍可执行（不杀进程）
# ─────────────────────────────────────

def test_timeout_does_not_kill_process(_cleanup_test_tools):
    """超时不破坏工具表 + 后续工具可正常执行。"""
    import tool_registry

    slow_name = "_w5_timeout_slow_other"
    fast_name = "_w5_timeout_fast_other"
    _cleanup_test_tools.append(slow_name)
    _cleanup_test_tools.append(fast_name)
    _register_slow_tool(slow_name, sleep_seconds=2.0, timeout_ms=100)
    _register_slow_tool(fast_name, sleep_seconds=0.05, timeout_ms=None)

    from infra.watchdog import ToolTimeoutError

    # 1) 触发超时
    with pytest.raises(ToolTimeoutError):
        tool_registry.execute_tool(slow_name, {"secs": 2.0})

    # 2) 同一进程内 fast 工具仍可正常执行（线程隔离，未杀进程）
    result = tool_registry.execute_tool(fast_name, {"secs": 0.05})
    assert result == "done after 0.05s", f"超时后其他工具应仍可执行，实际 {result!r}"

    # 3) 反复触发超时 + 正常调用 N 次，进程仍稳定
    for _ in range(3):
        with pytest.raises(ToolTimeoutError):
            tool_registry.execute_tool(slow_name, {"secs": 2.0})
        r = tool_registry.execute_tool(fast_name, {"secs": 0.05})
        assert r == "done after 0.05s"


# ─────────────────────────────────────
# 测试 5（额外）：mcp_tools.json 声明的 timeoutMs 生效
# ─────────────────────────────────────

def test_mcp_json_timeout_ms_in_meta(_cleanup_test_tools):
    """mcp_tools.json 声明的 timeoutMs 字段应被 mcp_tools_loader 解析进 meta。
    ratchet：现有无 timeoutMs 的工具行为不变。
    """
    import json
    import tempfile
    import mcp_tools_loader

    cfg_path = os.path.join(_PROJ_ROOT, "config", "mcp_tools.json")
    backup = None
    if os.path.isfile(cfg_path):
        with open(cfg_path, encoding="utf-8") as f:
            backup = f.read()

    try:
        # 构造临时配置（含 timeoutMs 字段）
        tmp_cfg = {
            "tools": [
                {
                    "name": "forbidden_words",
                    "description": "外部违禁词维护（list/add/remove）。",
                    "risk": "write",
                    "module": "tool_registry",
                    "function": "forbidden_words",
                    "params": {"action": "string"},
                    "timeoutMs": 5000,  # ⭐ 新字段
                }
            ]
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(tmp_cfg, f, ensure_ascii=False, indent=1)

        defs, handlers = mcp_tools_loader.reload_config_tools()
        meta = mcp_tools_loader.get_loaded_meta()
        assert "forbidden_words" in meta, "声明的工具应进入 meta"
        assert meta["forbidden_words"].get("timeoutMs") == 5000, (
            f"timeoutMs 应被解析进 meta，实际 {meta['forbidden_words']}"
        )
    finally:
        # 还原原配置
        if backup is not None:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(backup)
        else:
            if os.path.isfile(cfg_path):
                os.remove(cfg_path)
        # 重新加载原始配置（保证其他测试不受影响）
        try:
            mcp_tools_loader.reload_config_tools()
        except Exception:
            pass


# ─────────────────────────────────────
# 入口（直接运行验证）
# ─────────────────────────────────────

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.exit(pytest.main([__file__, "-v", "--no-header"]))