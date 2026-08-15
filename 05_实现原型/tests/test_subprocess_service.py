# -*- coding: utf-8 -*-
"""test_subprocess_service.py — #13 Shell/Subprocess Seam 测试（Harness 30 项 P0，§3.46.2）

覆盖：统一 subprocess 封装（run 返回码/输出捕获/超时）/ 可替换 provider（本地/docker 语义）/
未知 provider 容错 / 与现有 subprocess.run 调用兼容。
dsh Harness 借鉴（packages/shell/executor seam + subprocess，commit 47f9438）：
本地/docker/沙箱执行可换——provider 可注册可替换，业务代码不感知。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_run_simple_command():
    """统一封装运行命令：返回 CompletedProcess 语义（returncode+stdout）。"""
    from services.subprocess_service import run_command
    r = run_command(["python", "-c", "print('hello')"])
    assert r.returncode == 0
    assert "hello" in (r.stdout or "")


def test_run_captures_stderr():
    """stderr 被捕获（不抛异常，含错误输出）。"""
    from services.subprocess_service import run_command
    r = run_command(["python", "-c", "import sys; print('err', file=sys.stderr)"])
    assert r.returncode == 0
    assert "err" in (r.stderr or "")


def test_run_failure_returns_code():
    """命令失败：returncode 非零（不抛异常）。"""
    from services.subprocess_service import run_command
    r = run_command(["python", "-c", "import sys; sys.exit(3)"])
    assert r.returncode == 3


def test_run_timeout():
    """超时：返回 timeout 标记（不挂起）。"""
    from services.subprocess_service import run_command
    r = run_command(["python", "-c", "import time; time.sleep(5)"], timeout=1)
    assert r.timed_out is True


def test_provider_registry_has_local():
    """Provider 注册表含 local（默认执行器）。"""
    from services.subprocess_service import SUBPROCESS_PROVIDERS, get_provider
    assert "local" in SUBPROCESS_PROVIDERS
    assert get_provider("local") is not None


def test_register_custom_provider():
    """可注册自定义 provider（dsh 一切皆插件：执行器可插拔）。"""
    from services.subprocess_service import (
        SUBPROCESS_PROVIDERS, register_provider, get_provider,
    )

    def _fake_factory(cmd, **kw):
        from services.subprocess_service import RunResult
        return RunResult(returncode=0, stdout="fake", stderr="", timed_out=False)

    register_provider("fake_executor", _fake_factory)
    try:
        assert get_provider("fake_executor") is not None
        r = get_provider("fake_executor")(["echo", "x"])
        assert r.stdout == "fake"
    finally:
        SUBPROCESS_PROVIDERS.pop("fake_executor", None)


def test_unknown_provider_falls_back_local():
    """未知 provider 回退 local（容错）。"""
    from services.subprocess_service import get_provider
    assert get_provider("no_such_provider") is not None  # 回退 local
