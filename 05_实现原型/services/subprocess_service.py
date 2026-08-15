# -*- coding: utf-8 -*-
"""services/subprocess_service.py —— #13 Shell/Subprocess Seam（Harness 30 项 P0，§3.46.2，2026-08-16）

dsh Harness 借鉴（packages/shell/executor seam + subprocess，commit 47f9438）：
本地/docker/沙箱执行可换——provider 可注册可替换，业务代码不感知切换。

设计：
- run_command(cmd, ...) 统一封装：返回码/stdout/stderr/超时（替代散落 13+ 处 subprocess.run）
- RunResult：统一结果类型（returncode/stdout/stderr/timed_out）
- SUBPROCESS_PROVIDERS：可插拔执行器注册表（默认 local；docker/沙箱可注册替换）
- get_provider(name)：未知 provider 回退 local（容错）

与现有代码关系：新代码经本服务执行子进程；既有 13+ 处 subprocess.run
（manim/video 等）逐步迁移（ratchet：本服务先可用，迁移渐进）。
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RunResult:
    """统一子进程执行结果。"""
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


# ─────────────────────────────────────
# Provider 注册表（可插拔执行器）
# ─────────────────────────────────────
# provider name -> factory(cmd, **kw) -> RunResult
SUBPROCESS_PROVIDERS: Dict[str, Callable[[List[str], Any], RunResult]] = {}


def _local_factory(cmd: List[str], **kw) -> RunResult:
    """默认本地执行器（Python subprocess.run 封装）。"""
    timeout = kw.pop("timeout", None)
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            **kw,
        )
        return RunResult(
            returncode=r.returncode,
            stdout=r.stdout or "",
            stderr=r.stderr or "",
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        return RunResult(returncode=-1, stdout="", stderr="", timed_out=True)
    except FileNotFoundError as e:
        return RunResult(returncode=127, stdout="", stderr=str(e), timed_out=False)


def _register_default_providers() -> None:
    """注册内置 provider（幂等）。"""
    if "local" not in SUBPROCESS_PROVIDERS:
        SUBPROCESS_PROVIDERS["local"] = _local_factory


# #13 ⭐ 模块加载即注册默认 provider（dsh Seam Definition 层）
_register_default_providers()


def register_provider(name: str, factory: Callable[[List[str], Any], RunResult]) -> None:
    """注册自定义执行器 provider（docker/沙箱/远程可插拔）。

    Args:
        name: provider 名（docker/sandbox/remote/...）
        factory: (cmd, **kw) -> RunResult
    """
    SUBPROCESS_PROVIDERS[name] = factory


def get_provider(name: Optional[str] = None) -> Callable[[List[str], Any], RunResult]:
    """获取执行器；未知/为空 → 回退 local（容错，不抛异常）。"""
    if not name:
        return SUBPROCESS_PROVIDERS["local"]
    return SUBPROCESS_PROVIDERS.get(name, SUBPROCESS_PROVIDERS["local"])


def run_command(cmd: List[str], *, timeout: Optional[float] = None,
                provider: Optional[str] = None, **kw) -> RunResult:
    """统一子进程执行入口（#13 ⭐ 替代散落 subprocess.run）。

    Args:
        cmd: 命令列表（[可执行, 参数...]）
        timeout: 超时秒数（None=不超时；超时返回 timed_out=True）
        provider: 执行器名（local 默认；docker/sandbox 等自定义）
        **kw: 透传执行器参数

    Returns:
        RunResult（returncode/stdout/stderr/timed_out）
    """
    return get_provider(provider)(cmd, timeout=timeout, **kw)


# 向后兼容：Python 可用解释器（供测试/工具用）
def python_cmd(*args: str) -> List[str]:
    """构造当前 Python 解释器命令（跨平台）。"""
    return [sys.executable] + list(args)


__all__ = [
    "RunResult", "SUBPROCESS_PROVIDERS",
    "register_provider", "get_provider", "run_command", "python_cmd",
]
