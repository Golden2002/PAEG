# -*- coding: utf-8 -*-
"""services/preset_service.py —— #8 PresetService（Harness 30 项 P0，§3.46.2，2026-08-16）

dsh Harness 借鉴（ctx.agentPresets，commit 47f9438）：
preset 可 mount（挂载）/ list（列出）/ resolve（解析）/ recompose（重组）/ copy（复制）/ remove（移除）。

基于 #7 teaching_presets 扩展——预设管理服务化：
- list()：列出全部预设（含内置 + 自定义）
- get()：获取预设配置（未知 → None 容错）
- resolve()：解析为可执行配置（联动 tool_registry 权限档 + paeg_personas persona 正文）
- mount()：挂载新预设（幂等注册）
- copy()：复制预设为新名（继承原配置）
- recompose()：重组预设（覆盖部分字段生成新预设）
- remove()：移除预设（不存在容错）

与 #7 关系：#7 teaching_presets.py 是预设定义层（get/register/list/resolve），
本模块是服务层（完整管理 API），内部复用 teaching_presets 的定义与解析。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from services.teaching_presets import (
    DEFAULT_PRESET, TEACHING_PRESETS,
    get_teaching_preset, register_teaching_preset, resolve_preset,
)


class PresetService:
    """教学预设管理服务（完整 API：mount/list/resolve/recompose/copy/remove）。"""

    # ───────── 查询 ─────────
    def list(self) -> list:
        """列出全部预设名（内置 + 自定义）。"""
        return list(TEACHING_PRESETS.keys())

    def get(self, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取预设配置；未知 → None（容错）。"""
        if not name:
            return TEACHING_PRESETS.get(DEFAULT_PRESET)
        return TEACHING_PRESETS.get(name)

    def resolve(self, name: Optional[str] = None) -> Dict[str, Any]:
        """解析预设为可执行配置（联动权限档 + persona 正文）。"""
        return resolve_preset(name)

    # ───────── 写操作 ─────────
    def mount(self, name: str, config: Dict[str, Any]) -> None:
        """挂载新预设（幂等注册）。

        Args:
            name: 预设名
            config: {desc, teaching_mode, permission_preset, persona}
        """
        register_teaching_preset(name, config)

    def copy(self, source: str, new_name: str) -> bool:
        """复制预设为新名（继承原配置）。

        Args:
            source: 源预设名
            new_name: 新预设名

        Returns:
            True 成功；源不存在 → False
        """
        src = TEACHING_PRESETS.get(source)
        if src is None:
            return False
        TEACHING_PRESETS[new_name] = deepcopy(src)
        return True

    def recompose(self, source: str, new_name: str, overrides: Dict[str, Any]) -> bool:
        """重组预设：基于源预设，覆盖部分字段生成新预设。

        Args:
            source: 源预设名
            new_name: 新预设名
            overrides: 覆盖字段（desc/teaching_mode/permission_preset/persona 等）

        Returns:
            True 成功；源不存在 → False
        """
        src = TEACHING_PRESETS.get(source)
        if src is None:
            return False
        merged = deepcopy(src)
        if overrides:
            merged.update({k: v for k, v in overrides.items() if v is not None})
        TEACHING_PRESETS[new_name] = merged
        return True

    def remove(self, name: str) -> bool:
        """移除预设（不存在容错，返回 False）。

        内置预设可被移除（dsh 一切皆插件：preset 可卸载），但建议保留 standard 默认。
        """
        if name in TEACHING_PRESETS:
            del TEACHING_PRESETS[name]
            return True
        return False


__all__ = ["PresetService"]
