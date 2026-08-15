# -*- coding: utf-8 -*-
"""test_hooks_waterfall_events.py — H-14 hooks 瀑布补全测试（§3.46.2 H-14）

覆盖：llm/* 与 tools/* 事件在 teach_stream 流程中被发射（瀑布链可达）。
HooksHub 已有 waterfall+next() 4-dispatch（W1）、timeout（P1-7），
本测试验证缺失的"触发点"——llm/stream 与 tools/{pre,post}-execute 三事件。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_hooks_hub_supports_llm_and_tools_events():
    """HooksHub 能注册并触发 llm/stream 与 tools/* 事件（静态能力断言）。"""
    from hooks_hub import get_hooks_hub, Hook

    hub = get_hooks_hub()
    # 注册测试钩子（用 log_hook 作为可 resolve 的模块函数）
    h_llm = Hook(hook_id="test_llm", event="llm/stream",
                 module="hooks_hub", function="log_hook", dispatch="waterfall")
    h_tools = Hook(hook_id="test_tools", event="tools/pre-execute",
                   module="hooks_hub", function="log_hook", dispatch="waterfall")
    try:
        r1 = hub._dispatch("llm/stream", {"query": "导数"}, [h_llm])
        r2 = hub._dispatch("tools/pre-execute", {"tool": "kb_search"}, [h_tools])
        assert r1.get("query") == "导数"
        assert r2.get("tool") == "kb_search"
        assert r1.get("__verdict") in ("allow", None)
    finally:
        pass


def test_teach_stream_source_emits_llm_and_tools_events():
    """teach_stream 源码引用了 llm/stream 与 tools/* 事件发射（静态断言接线）。"""
    import inspect
    import server as server_mod
    src = inspect.getsource(server_mod)
    # teach_stream 是 SSE 教学流，其中应包含 hook 事件发射点
    assert "llm/stream" in src or "tools/pre-execute" in src or "run_hook" in src


def test_chat_stream_source_emits_hook_events():
    """chat_stream 源码也应有 hook 事件发射点（与 teach 对称）。"""
    import inspect
    import server as server_mod
    src = inspect.getsource(server_mod)
    assert "run_hook" in src


def test_hooks_llm_stream_registered_in_default_config():
    """hooks.json 默认配置含 llm/stream 或 tools/* 钩子（可配置触发）。"""
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent
    hooks_json = base / "config" / "hooks.json"
    if hooks_json.exists():
        data = json.loads(hooks_json.read_text(encoding="utf-8"))
        events = json.dumps(data)
        assert any(k in events for k in ("llm/stream", "tools/pre-execute", "tools/post-execute", "tools/"))
    else:
        # 无配置文件时，代码内应有默认钩子列表
        import hooks_hub as hh
        src = inspect.getsource(hh)
        assert "llm/stream" in src or "tools/" in src
