# -*- coding: utf-8 -*-
"""services/subprocess_spawn.py —— #17 Subprocess 抽象（Harness 30 项 P2，§3.46.2，2026-08-16）

dsh Harness 借鉴（ctx.subprocess，commit 47f9438）：
子进程抽象统一 spawn——业务代码不直接调 subprocess.run。
基于 #13 subprocess_service（run_command）扩展：MCP 客户端/ffmpeg/PDF/PPT 等统一进程管理。

设计：
- Spawner：单个进程类型的 spawner（build 构造命令 + run 执行）
- SPAWN_KINDS：已知 spawner 注册表（ffmpeg/python/mcp）
- get_spawner(kind)：获取 spawner（未知回退 python，容错）
- register_spawner()：自定义 spawner 可插拔
- 执行统一走 #13 run_command（本地/docker/沙箱可换 provider）

与既有机制关系：
- #13 services/subprocess_service.py：run_command 统一执行入口（底层）
- 本模块：高层 spawner 抽象（按进程类型封装命令构造与执行）
"""
from __future__ import annotations

import shutil
import sys
from typing import Any, Dict, List, Optional

from services.subprocess_service import RunResult, python_cmd, run_command


class Spawner:
    """单个进程类型的 spawner（build 构造命令 + run 执行）。

    Args:
        kind: 进程类型名（ffmpeg/python/mcp/自定义）
        executable: 可执行文件路径（自动探测；None 时按 kind 推导）
    """

    def __init__(self, kind: str, executable: Optional[str] = None):
        self.kind = kind
        self.executable = executable

    def _resolve_exe(self) -> str:
        """解析可执行文件路径（已配置 → 探测系统 PATH → 回退）。"""
        if self.executable:
            return self.executable
        _probe = {
            "ffmpeg": "ffmpeg",
            "python": sys.executable,
            "mcp": "npx",
        }
        _candidate = _probe.get(self.kind, sys.executable)
        _found = shutil.which(_candidate)
        return _found or _candidate

    def build(self, args: List[str]) -> List[str]:
        """构造完整命令（可执行 + 参数）。"""
        return [self._resolve_exe()] + list(args)

    def run(self, args: List[str], *, timeout: Optional[float] = None,
            provider: Optional[str] = None, **kw) -> RunResult:
        """执行命令（经 #13 run_command 统一入口）。"""
        cmd = self.build(args)
        return run_command(cmd, timeout=timeout, provider=provider, **kw)


# ─────────────────────────────────────
# 已知 spawner 注册表
# ─────────────────────────────────────
SPAWN_KINDS: Dict[str, Spawner] = {}


def _register_default_spawners() -> None:
    """注册内置 spawner（幂等）。"""
    if "python" not in SPAWN_KINDS:
        SPAWN_KINDS["python"] = Spawner("python", sys.executable)
    if "ffmpeg" not in SPAWN_KINDS:
        SPAWN_KINDS["ffmpeg"] = Spawner("ffmpeg", shutil.which("ffmpeg") or "ffmpeg")
    if "mcp" not in SPAWN_KINDS:
        SPAWN_KINDS["mcp"] = Spawner("mcp", shutil.which("npx") or "npx")


# #17 ⭐ 模块加载即注册默认 spawner
_register_default_spawners()


def get_spawner(kind: Optional[str] = None) -> Spawner:
    """获取 spawner；未知/为空 → 回退 python（容错）。"""
    if not kind:
        return SPAWN_KINDS.get("python", Spawner("python", sys.executable))
    return SPAWN_KINDS.get(kind, SPAWN_KINDS.get("python", Spawner("python", sys.executable)))


def register_spawner(kind: str, spawner: Spawner) -> None:
    """注册自定义 spawner（dsh 一切皆插件：进程抽象可插拔）。"""
    SPAWN_KINDS[kind] = spawner


# 便捷入口：python_cmd 转发（与 #13 一致语义）
def spawn_python(args: List[str], **kw) -> RunResult:
    """运行 Python 脚本（统一 spawn）。"""
    return get_spawner("python").run(args, **kw)


__all__ = [
    "Spawner", "SPAWN_KINDS",
    "get_spawner", "register_spawner", "spawn_python",
]
