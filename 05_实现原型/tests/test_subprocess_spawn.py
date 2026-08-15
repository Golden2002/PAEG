# -*- coding: utf-8 -*-
"""test_subprocess_spawn.py — #17 Subprocess 抽象测试（Harness 30 项 P2）

覆盖：统一 spawn 服务（MCP 客户端/ffmpeg/PDF/PPT 等高语义封装），
基于 #13 subprocess_service（run_command）扩展——统一进程管理。
dsh Harness 借鉴（ctx.subprocess，commit 47f9438）：
子进程抽象统一 spawn——业务代码不直接调 subprocess.run。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_spawn_service_has_registry():
    """SpawnService 注册 ffmpeg/python/mcp 等已知 spawner。"""
    from services.subprocess_spawn import SPAWN_KINDS, get_spawner
    for kind in ("ffmpeg", "python", "mcp"):
        assert kind in SPAWN_KINDS, f"缺 spawner {kind}"
        assert get_spawner(kind) is not None


def test_spawn_python_runs():
    """python spawner 运行脚本（经 #13 run_command 统一执行）。"""
    from services.subprocess_spawn import get_spawner
    sp = get_spawner("python")
    r = sp.run(["-c", "print('hello spawn')"])
    assert r.returncode == 0
    assert "hello spawn" in r.stdout


def test_spawn_ffmpeg_builds_command():
    """ffmpeg spawner 构造命令（不实际执行，验证参数组装）。"""
    from services.subprocess_spawn import get_spawner
    sp = get_spawner("ffmpeg")
    cmd = sp.build(["-i", "in.mp4", "-c", "copy", "out.mp4"])
    assert cmd[0].endswith("ffmpeg") or "ffmpeg" in cmd[0]
    assert "-i" in cmd
    assert "in.mp4" in cmd


def test_spawn_mcp_builds_command():
    """mcp spawner 构造命令（npx/stdio 语义）。"""
    from services.subprocess_spawn import get_spawner
    sp = get_spawner("mcp")
    cmd = sp.build(["filesystem", "/tmp"])
    assert len(cmd) >= 2


def test_register_custom_spawner():
    """可注册自定义 spawner（dsh 一切皆插件：进程抽象可插拔）。"""
    from services.subprocess_spawn import SPAWN_KINDS, register_spawner, get_spawner

    class _FakeSpawner:
        def build(self, args):
            return ["fake"] + list(args)

        def run(self, args, **kw):
            from services.subprocess_service import RunResult
            return RunResult(returncode=0, stdout="fake-ok")

    register_spawner("fake", _FakeSpawner())
    try:
        assert "fake" in SPAWN_KINDS
        sp = get_spawner("fake")
        assert sp.run(["x"]).stdout == "fake-ok"
    finally:
        SPAWN_KINDS.pop("fake", None)


def test_unknown_spawner_falls_back():
    """未知 spawner 回退 python（容错）。"""
    from services.subprocess_spawn import get_spawner
    assert get_spawner("no_such_kind") is not None  # 回退默认
