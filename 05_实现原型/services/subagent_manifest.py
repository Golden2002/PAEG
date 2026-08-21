# -*- coding: utf-8 -*-
"""services/subagent_manifest.py —— §3.79 A3 ⭐ subagent 声明化服务（渐进第一步）

读取 ``config/agents.yaml``（职责声明：id/name/role/keywords），
与 ``infra/subagent_registry``（注册层）做一致性校验——声明与注册必须吻合
（ratchet：只增加描述层，不改变调度行为）。

三层分工：
  - 声明层：本文件读取的 agents.yaml（id/name/role/keywords）
  - 注册层：infra/subagent_registry（10 内置 subagent 的 factory/enabled）
  - 运行参数层：config/agents.json（provider/model/temperature/max_tokens/thinking_level）

API：
  - get_manifest(path=None) -> dict：读声明（YAML，PyYAML 不可用时 JSON 兜底）
  - validate_against_registry(manifest=None) -> list[str]：声明与注册名字差集（空=一致）
  - agent_names() -> list[str]：声明中的 subagent id 列表
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
_MANIFEST_PATH = os.path.join(_CONFIG_DIR, "agents.yaml")

_cache: Optional[Dict[str, Any]] = None


def _load_manifest_file(path: str) -> Dict[str, Any]:
    """读 YAML（优先 PyYAML；降级 JSON）。失败返回 {"agents": []}。"""
    if not os.path.isfile(path):
        return {"version": 1, "agents": []}
    try:
        import yaml  # type: ignore
        _data = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
    except ImportError:
        # 降级：尝试 JSON（若有人把 yaml 写成 json）
        try:
            with open(path, "r", encoding="utf-8") as _fh:
                _data = json.load(_fh)
        except Exception:
            _data = {"version": 1, "agents": []}
    except Exception:
        _data = {"version": 1, "agents": []}
    if not isinstance(_data, dict) or not isinstance(_data.get("agents"), list):
        _data = {"version": 1, "agents": []}
    return _data


def get_manifest(path: Optional[str] = None) -> Dict[str, Any]:
    """读取 subagent 声明（进程级缓存）。"""
    global _cache
    _p = path or _MANIFEST_PATH
    if _cache is None or path is not None:
        _data = _load_manifest_file(_p)
        if path is None:
            _cache = _data
        return _data
    return _cache


def agent_names(manifest: Optional[Dict[str, Any]] = None) -> List[str]:
    """声明中的 subagent id 列表。"""
    _m = manifest or get_manifest()
    return [str(a.get("id")) for a in _m.get("agents", []) if a.get("id")]


def validate_against_registry(manifest: Optional[Dict[str, Any]] = None) -> List[str]:
    """声明 vs 注册层一致性校验。

    Returns:
        差异错误列表；空列表 = 一致（声明中的 id 全在 registry 中）。
    """
    _m = manifest or get_manifest()
    _declared = set(agent_names(_m))
    try:
        from infra.subagent_registry import get_default_registry
        _reg = set(get_default_registry().list())
    except Exception:
        return ["registry 不可用，无法校验"]
    _errors = []
    for _id in sorted(_declared - _reg):
        _errors.append(f"声明但未注册: {_id}")
    for _id in sorted(_reg - _declared):
        _errors.append(f"注册但未声明: {_id}（请补 agents.yaml）")
    return _errors


def validate_scopes(manifest: Optional[Dict[str, Any]] = None) -> List[str]:
    """agent_scope 消费点（§3.79 孤儿接线）：manifest 声明的 subagent 均应有默认作用域。

    Returns:
        缺少作用域的 subagent 列表；空列表 = 全部已注册（一致）。
    """
    _m = manifest or get_manifest()
    _declared = agent_names(_m)
    try:
        from services.agent_scope import DEFAULT_AGENT_SCOPES
    except Exception:
        return ["agent_scope 不可用，无法校验"]
    _missing = [a for a in _declared if a not in DEFAULT_AGENT_SCOPES]
    return _missing


def validate_contracts(manifest: Optional[Dict[str, Any]] = None) -> List[str]:
    """agent_trirole 消费点（§3.79 Round 3 孤儿接线）：manifest 声明的 subagent
    均应有三角色服务契约（ServiceDefinition）。

    接线背景：services/agent_trirole.py（Definition/Provider/Consumer 三角色，
    dsh ctx.shell 借鉴）此前零调用方（孤儿）——只有契约层没有消费点。
    本函数把 trirole 契约集接入 manifest 校验链：声明 → 契约 必须一致，
    Provider/Consumer 才能安全基于抽象契约协作（Rule vs LLM 可插拔）。

    Returns:
        缺少契约的 subagent 列表；空列表 = 全部已声明（一致）。
    """
    _m = manifest or get_manifest()
    _declared = set(agent_names(_m))
    try:
        from services.agent_trirole import DEFAULT_SERVICE_DEFINITIONS
    except Exception:
        return ["agent_trirole 不可用，无法校验"]
    _missing = [a for a in sorted(_declared) if a not in DEFAULT_SERVICE_DEFINITIONS]
    return _missing


def validate_declaration_fields(manifest: Optional[Dict[str, Any]] = None) -> List[str]:
    """A3 ⭐ 声明字段完整性校验（§3.79 Round 6 深化）：每个声明须含
    id/name/role/keywords 四字段（声明驱动的基础——字段缺失=声明退化）。

    Returns:
        声明不完整的 subagent 描述列表；空列表 = 全部完整。
    """
    _m = manifest or get_manifest()
    _req = ("id", "name", "role", "keywords")
    _bad = []
    for _a in _m.get("agents", []):
        if not isinstance(_a, dict):
            _bad.append(f"声明项非 dict: {str(_a)[:40]}")
            continue
        _missing_f = [f for f in _req if not _a.get(f)]
        if _missing_f:
            _bad.append(f"{_a.get('id', '?')}: 缺字段 {_missing_f}")
    return _bad


__all__ = ["get_manifest", "agent_names", "validate_against_registry",
           "validate_scopes", "validate_contracts", "validate_declaration_fields",
           "_MANIFEST_PATH"]
