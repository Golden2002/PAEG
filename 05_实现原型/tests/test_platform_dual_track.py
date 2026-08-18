# -*- coding: utf-8 -*-
"""test_platform_dual_track.py — #6 OS 平台双轨测试（Harness 30 项 P2）

覆盖：TTS/STT/PPT 等模块按平台分支（bash+pwsh 双轨）——配置/命令模板平台感知。
dsh Harness 借鉴（bash+pwsh 双轨，commit 47f9438）：
同一功能在 win32/posix 平台用不同命令模板，config 条件挂载。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_platform_detection():
    """检测当前平台（win32/posix）。"""
    from services.platform_dual_track import get_platform
    p = get_platform()
    assert p in ("win32", "posix")


def test_command_template_for_platform():
    """命令模板按平台选择（ffmpeg/echo 等双轨）。"""
    from services.platform_dual_track import get_command_template
    # 定义双轨模板
    templates = {
        "ffmpeg": {"win32": "ffmpeg.exe", "posix": "ffmpeg"},
    }
    cmd = get_command_template("ffmpeg", templates)
    assert cmd  # 返回非空（win32 → ffmpeg.exe 或回退）
    assert isinstance(cmd, str)


def test_platform_aware_config():
    """配置按平台分支（同一 key 不同平台值）。"""
    from services.platform_dual_track import resolve_platform_value
    cfg = {"python": {"win32": "python.exe", "posix": "python3"}}
    val = resolve_platform_value(cfg, "python")
    assert val
    # 未知 key 回退默认
    assert resolve_platform_value(cfg, "no_such", default="fallback") == "fallback"


def test_platform_key_fallback():
    """平台特定 key 缺失时回退通用 key。"""
    from services.platform_dual_track import resolve_platform_value
    cfg = {"tool": {"common": "generic-tool"}}  # 无平台特定，只有 common
    val = resolve_platform_value(cfg, "tool")
    assert val == "generic-tool"
