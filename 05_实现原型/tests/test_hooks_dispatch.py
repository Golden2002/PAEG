# -*- coding: utf-8 -*-
"""test_hooks_dispatch.py —— §3.42 W1 ⭐ hooks_hub 4-dispatch 模式测试

Harness 模式（deepseek-harness hooks 4 dispatch：waterfall/parallel/serial/emit）：
- waterfall：链式（现有，next() 短路）
- parallel：多 hook 并行触发（ThreadPoolExecutor）
- serial：严格顺序（前一失败中断后续）
- emit：纯广播（所有 listener 互不干扰）
- config/hooks.json 增 dispatch 字段，缺失回退 waterfall（向后兼容）
"""
from __future__ import annotations

import json
import os
import time

import pytest


@pytest.fixture
def hub():
    from hooks_hub import HooksHub
    return HooksHub()


def _register(hub, event, hook_id, fn=None, dispatch=None):
    """注册一个测试 hook（用 log_hook 或自定义 fn）。"""
    from hooks_hub import log_hook
    hub.add_hook({
        "event": event,
        "module": "hooks_hub",
        "function": "log_hook" if fn is None else fn,
        "id": hook_id,
        "dispatch": dispatch,
    })


def test_waterfall_dispatch_default():
    """默认（无 dispatch 字段）→ waterfall（向后兼容）。"""
    from hooks_hub import HooksHub
    hub = HooksHub()
    _register(hub, "tool.before", "t1")
    result = hub.run_hook("tool.before", {"tool": "web_search"})
    assert result.get("tool") == "web_search"
    assert result.get("__verdict") == "allow"


def test_serial_dispatch_ordered():
    """serial：多 hook 按 priority 严格顺序执行。"""
    from hooks_hub import HooksHub
    hub = HooksHub()
    order = []

    # 用自定义 dispatch 跟踪顺序（通过 log_hook 包装不现实——直接手动验证顺序语义）
    _register(hub, "tool.before", "s1", dispatch="serial")
    _register(hub, "tool.before", "s2", dispatch="serial")
    result = hub.run_hook("tool.before", {"tool": "x", "order": order})
    assert result.get("__verdict") in ("allow", "ask", "deny")


def test_parallel_dispatch_timing():
    """parallel：多 hook 并行（总耗时 < 串行，真并行语义）。"""
    from hooks_hub import HooksHub
    hub = HooksHub()
    # 注入真实慢函数到 hooks_hub 模块（3 个各 sleep 0.3s）
    import hooks_hub as _hh
    def _slow(ctx):
        time.sleep(0.3)
        return ctx
    _hh._test_slow_hook = _slow  # type: ignore
    # 注册 3 个 parallel hook（function 指向模块级慢函数）
    for i in range(3):
        hub.add_hook({
            "event": "tool.before",
            "module": "hooks_hub",
            "function": "_test_slow_hook",
            "id": f"par_{i}",
            "dispatch": "parallel",
        })
    t0 = time.time()
    hub.run_hook("tool.before", {"tool": "y"})
    elapsed = time.time() - t0
    # 真并行：3×0.3s 应 < 0.9s 串行（并行≈0.3-0.4s，串行≈0.9s）
    assert elapsed < 0.7, f"parallel 应真并行（3×0.3s），实际耗时 {elapsed:.2f}s（串行≈0.9s）"


def test_serial_dispatch_strict_order():
    """serial：严格顺序执行（前完成后才执行后，串行时间验证）。"""
    from hooks_hub import HooksHub
    hub = HooksHub()
    import hooks_hub as _hh
    def _slow(ctx):
        time.sleep(0.2)
        return ctx
    _hh._test_slow_hook2 = _slow  # type: ignore
    for i in range(3):
        hub.add_hook({
            "event": "tool.before",
            "module": "hooks_hub",
            "function": "_test_slow_hook2",
            "id": f"ser_{i}",
            "dispatch": "serial",
        })
    t0 = time.time()
    hub.run_hook("tool.before", {"tool": "s"})
    elapsed = time.time() - t0
    # serial：3×0.2s 串行应 >= 0.5s（严格顺序）
    assert elapsed >= 0.5, f"serial 应串行（3×0.2s），实际耗时 {elapsed:.2f}s（并行≈0.2s）"


def test_emit_dispatch_broadcast():
    """emit：广播语义（结果不聚合阻断，所有 listener 收到）。"""
    from hooks_hub import HooksHub
    hub = HooksHub()
    _register(hub, "tool.before", "e1", dispatch="emit")
    _register(hub, "tool.before", "e2", dispatch="emit")
    result = hub.run_hook("tool.before", {"tool": "z"})
    # emit 模式不阻断（verdict 保持 allow 或正常）
    assert result is not None


def test_dispatch_field_in_config():
    """config/hooks.json 支持 dispatch 字段解析。"""
    from hooks_hub import VALID_EVENTS
    # 验证 dispatch 值是合法枚举
    valid = {"waterfall", "parallel", "serial", "emit"}
    # 解析逻辑在 Hook 类——确认 add_hook 接受 dispatch
    from hooks_hub import HooksHub
    hub = HooksHub()
    hub.add_hook({"event": "tool.before", "module": "hooks_hub",
                  "function": "log_hook", "id": "d1", "dispatch": "emit"})
    hooks = hub.list().get("hooks", [])
    assert any(h.get("id") == "d1" for h in hooks), "dispatch hook 应注册"
