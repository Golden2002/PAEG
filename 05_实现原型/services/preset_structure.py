# -*- coding: utf-8 -*-
"""services/preset_structure.py —— #10 Preset 文件结构标准化（Harness 30 项 P1，§3.46.2，2026-08-16）

dsh Harness 借鉴（preset 目录规范，commit 47f9438）：
preset = agent.patch.yml + preset.yml + prompts/ + assets/ 标准结构，可持久化可装载。

设计（与 #7 teaching_presets / #8 PresetService 衔接）：
- DEFAULT_PRESET_DIR：默认 preset 目录（05_实现原型/paeg/presets）
- ensure_preset_dirs()：确保目录存在（幂等）
- save_preset_to_dir(preset, dir)：把 preset 保存为标准文件结构
  - preset.yml：主配置（id/desc/teaching_mode/permission_preset/persona）
  - agent.patch.yml：subagent 装扮层补丁（与 #1 subagent_loader 衔接）
- load_preset_from_dir(dir)：从标准结构装载 preset（缺失 → None 容错）
- list_presets_in_dir(dir)：列出目录下所有 preset（按 id）

与既有机制关系：
- #7 services/teaching_presets.py：预设定义（内存注册表）
- #8 services/preset_service.py：预设管理 API（mount/copy/recompose/remove）
- 本模块：预设文件结构标准化（持久化/装载——preset 可落盘可移植）
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# 默认 preset 目录（05_实现原型/paeg/presets）
DEFAULT_PRESET_DIR = Path(__file__).resolve().parent.parent / "paeg" / "presets"


def ensure_preset_dirs(base: Optional[Path] = None) -> Path:
    """确保 preset 目录结构存在（幂等）：base/ + prompts/ + assets/。"""
    d = Path(base) if base is not None else DEFAULT_PRESET_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "prompts").mkdir(exist_ok=True)
    (d / "assets").mkdir(exist_ok=True)
    return d


def _write_yaml(path: Path, data: Dict[str, Any]) -> bool:
    """写 YAML（无 yaml 依赖时回退 JSON——preset 结构容错）。"""
    try:
        import yaml  # type: ignore
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        return True
    except Exception:
        # 无 yaml 依赖 → JSON 兜底（.yml 扩展名但内容 JSON，兼容读取）
        try:
            with open(path, "w", encoding="utf-8") as f:
                import json
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


def _read_yaml(path: Path) -> Optional[Dict[str, Any]]:
    """读 YAML（兼容 JSON 兜底；失败 → None）。"""
    if not path.is_file():
        return None
    try:
        import yaml  # type: ignore
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        # JSON 兜底（兼容 _write_yaml 无 yaml 回退路径）
        try:
            import json
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception:
            return None


def save_preset_to_dir(preset: Dict[str, Any], preset_dir: Path) -> bool:
    """把 preset 保存为标准文件结构。

    Args:
        preset: {id, desc, teaching_mode, permission_preset, persona, ...}
        preset_dir: 目标目录（如 paeg/presets/weil-classical）

    Returns:
        True 成功（生成 preset.yml + agent.patch.yml）
    """
    try:
        preset_dir = Path(preset_dir)
        preset_dir.mkdir(parents=True, exist_ok=True)

        # preset.yml：主配置（规范字段）
        preset_yml = {
            "id": preset.get("id", ""),
            "desc": preset.get("desc", ""),
            "teaching_mode": preset.get("teaching_mode", "normal"),
            "permission_preset": preset.get("permission_preset", "standard"),
            "persona": preset.get("persona", "weil"),
        }
        ok1 = _write_yaml(preset_dir / "preset.yml", preset_yml)

        # agent.patch.yml：subagent 装扮层补丁（与 #1 subagent_loader 衔接）
        patch = {
            "preset": preset.get("id", ""),
            "desc": preset.get("desc", ""),
            "persona": preset.get("persona", "weil"),
        }
        ok2 = _write_yaml(preset_dir / "agent.patch.yml", patch)
        return ok1 and ok2
    except Exception:
        return False


def load_preset_from_dir(preset_dir: Path) -> Optional[Dict[str, Any]]:
    """从标准结构装载 preset；缺失/解析失败 → None（容错）。"""
    preset_dir = Path(preset_dir)
    preset_yml = preset_dir / "preset.yml"
    if not preset_yml.is_file():
        return None
    data = _read_yaml(preset_yml)
    if data is None:
        return None
    # 补默认字段（缺省继承）
    data.setdefault("teaching_mode", "normal")
    data.setdefault("permission_preset", "standard")
    data.setdefault("persona", "weil")
    return data


def list_presets_in_dir(base_dir: Optional[Path] = None) -> List[str]:
    """列出目录下所有 preset（按 id，即子目录名含 preset.yml）。"""
    d = Path(base_dir) if base_dir is not None else DEFAULT_PRESET_DIR
    if not d.is_dir():
        return []
    presets = []
    for child in sorted(d.iterdir()):
        if child.is_dir() and (child / "preset.yml").is_file():
            presets.append(child.name)
    return presets


__all__ = [
    "DEFAULT_PRESET_DIR",
    "ensure_preset_dirs", "save_preset_to_dir",
    "load_preset_from_dir", "list_presets_in_dir",
]
