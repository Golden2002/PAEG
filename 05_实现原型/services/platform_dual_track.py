# -*- coding: utf-8 -*-
"""services/platform_dual_track.py —— #6 OS 平台双轨（Harness 30 项 P2，§3.46.2，2026-08-16）

dsh Harness 借鉴（bash+pwsh 双轨，commit 47f9438）：
同一功能在 win32/posix 平台用不同命令模板，config 条件挂载——TTS/STT/PPT 等按平台分支。

设计：
- get_platform()：检测当前平台（win32/posix）
- get_command_template(key, templates)：命令模板按平台选择（双轨）
- resolve_platform_value(cfg, key, default=None)：配置值按平台分支
  - 平台特定值（win32/posix）优先
  - 通用 common 值回退
  - 未知 key → default（容错）

与既有机制关系：
- config_loader.py：agents 配置加载（#5 overlay 四层合并）
- 本模块：平台感知配置辅助（TTS/STT/PPT 命令/路径按平台分支）
- 应用：ffmpeg 可执行、Python 解释器、脚本命令等在 win32/posix 不同
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional


def get_platform() -> str:
    """检测当前平台（win32 / posix）。"""
    if sys.platform.startswith("win"):
        return "win32"
    return "posix"


def get_command_template(key: str, templates: Dict[str, Dict[str, str]]) -> Optional[str]:
    """命令模板按平台选择（双轨：win32/posix）。

    Args:
        key: 命令名（ffmpeg/python/...）
        templates: {key: {win32: ..., posix: ...}}

    Returns:
        平台对应命令；缺失 → None（容错）
    """
    tpl = templates.get(key)
    if not tpl:
        return None
    return tpl.get(get_platform()) or tpl.get("common")


def resolve_platform_value(cfg: Dict[str, Dict[str, Any]], key: str,
                           default: Any = None) -> Any:
    """配置值按平台分支（平台特定优先，common 回退，未知 → default）。

    Args:
        cfg: {key: {win32: v, posix: v, common: v}}
        key: 配置键
        default: 未知 key 的回退值

    Returns:
        平台对应值；缺失 → default（容错）
    """
    entry = cfg.get(key)
    if not isinstance(entry, dict):
        return default
    _plat = get_platform()
    if _plat in entry:
        return entry[_plat]
    if "common" in entry:
        return entry["common"]
    return default


__all__ = [
    "get_platform", "get_command_template", "resolve_platform_value",
]
