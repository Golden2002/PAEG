# -*- coding: utf-8 -*-
"""services/quality_gate_config.py —— #28 Constitutional AI 补丁化（Harness 30 项 P2，§3.46.2，2026-08-16）

dsh Harness 借鉴（plan-mode + repeat-tool-reminder 走 patch 配置，commit 47f9438）：
反思/门禁/重复检测配置可 patch，不改代码调门禁。

设计（quality_gate 配置化，与 self_evolution 衔接）：
- DEFAULT_CONFIG_PATH：config/quality_gate.json（patch 配置落点）
- get_gate_config()：加载门禁配置（阈值/最小长度/宪法条款），缺省回退内置默认
- apply_to_gate(gate)：把配置注入 QualityGate（THRESHOLDS/MIN_CONTENT_LEN/MIN_WORDS）
- reset_cache()：清缓存（测试/热加载用）

与既有机制关系：
- quality_gate.py：QualityGate（内置 THRESHOLDS/MIN_CONTENT_LEN/MIN_WORDS 硬编码）
- self_evolution.py：蒸馏/工具经验过门禁（配置化后无需改代码调门禁）
- #5 config_loader overlay：配置加载链（本模块独立读 config/quality_gate.json）
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# config/quality_gate.json（patch 配置落点）
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "config", "quality_gate.json")

# 内置默认（与 quality_gate.py 硬编码一致——ratchet：无配置时行为不变）
_DEFAULT_CONFIG: Dict[str, Any] = {
    "thresholds": {"factuality": 4, "safety": 4, "novelty": 3, "pedagogy": 3},
    "min_content_len": 12,
    "min_words": 4,
    "constitution_extra": [],
}

_cache: Optional[Dict[str, Any]] = None


def get_gate_config() -> Dict[str, Any]:
    """加载质量门禁配置；文件缺失/解析失败 → 内置默认（容错）。"""
    global _cache
    if _cache is not None:
        return _cache
    _cfg = dict(_DEFAULT_CONFIG)
    if os.path.isfile(DEFAULT_CONFIG_PATH):
        try:
            with open(DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # 深合并（缺省继承默认）
                _cfg["thresholds"] = {**_DEFAULT_CONFIG["thresholds"],
                                      **data.get("thresholds", {})}
                _cfg["min_content_len"] = data.get("min_content_len", _DEFAULT_CONFIG["min_content_len"])
                _cfg["min_words"] = data.get("min_words", _DEFAULT_CONFIG["min_words"])
                _cfg["constitution_extra"] = data.get("constitution_extra",
                                                      _DEFAULT_CONFIG["constitution_extra"]) or []
        except Exception as e:
            print(f"[quality_gate_config] 配置加载失败（用默认）: {e}")
    _cache = _cfg
    return _cfg


def apply_to_gate(gate: Any) -> None:
    """把配置注入 QualityGate 实例（阈值/最小长度/宪法条款）。

    Args:
        gate: quality_gate.QualityGate 实例
    """
    cfg = get_gate_config()
    try:
        gate.THRESHOLDS = dict(cfg["thresholds"])
    except Exception:
        pass
    try:
        import quality_gate as _qg
        _qg.MIN_CONTENT_LEN = int(cfg["min_content_len"])
        _qg.MIN_WORDS = int(cfg["min_words"])
    except Exception:
        pass
    # 宪法条款注入（quality_gate.QualityGate 支持 constitution_extra）
    try:
        extra = cfg.get("constitution_extra") or []
        if extra and hasattr(gate, "constitution_extra"):
            gate.constitution_extra = list(extra)
    except Exception:
        pass


def reset_cache() -> None:
    """清空配置缓存（测试/热加载后重新读取）。"""
    global _cache
    _cache = None


__all__ = [
    "DEFAULT_CONFIG_PATH", "get_gate_config", "apply_to_gate", "reset_cache",
]
