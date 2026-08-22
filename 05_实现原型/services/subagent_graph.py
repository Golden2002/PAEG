# -*- coding: utf-8 -*-
"""services/subagent_graph.py —— §3.85 ⭐ subagent 显式图（Codex Harness 借鉴 P1）

背景（Oracle 策略 §3.85）：13 subagent 调度硬编码/扁平注册表——图声明缺失，
调度不可观测、不可演进。本模块：subagent_graph.json 声明节点（trigger/routing/
依赖边）+ 版本控制 + 校验 + admin 视图——让"谁在什么条件下调用谁"可审计。

设计：
- 图数据在 config/subagent_graph.json（版本化，schema 带 version）
- 节点：id / role / trigger（激活条件描述）/ routing（路由到哪些下游）
- 边：from → to（依赖/调用方向）
- 校验：所有节点 id 必须存在于 subagent_manifest（声明=实现）；边两端必须为已知节点
- admin 视图：graph_view() 供 /api/admin/subagent-graph 输出（运维可视化）
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GRAPH_PATH = os.path.join(_PROJ, "config", "subagent_graph.json")


def _load_graph(path: Optional[str] = None) -> Dict[str, Any]:
    """读 subagent 图声明（JSON）。文件缺失/损坏 → 空图（校验会报缺失）。"""
    _p = path or _GRAPH_PATH
    try:
        with open(_p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"version": "0", "nodes": [], "edges": []}


def get_graph(path: Optional[str] = None) -> Dict[str, Any]:
    return _load_graph(path)


def validate_graph(graph: Optional[Dict[str, Any]] = None,
                   manifest: Optional[Dict[str, Any]] = None) -> List[str]:
    """图校验：节点必须在 manifest（声明=实现）；边两端必须为已知节点；有依赖环检测。

    Returns: 错误列表（空 = 一致）。
    """
    _g = graph or _load_graph()
    errors: List[str] = []
    _nodes = {n.get("id") for n in _g.get("nodes") or [] if n.get("id")}
    if not _nodes:
        errors.append("图无节点（subagent_graph.json 缺失或为空）")
    # 1. 节点 ⊆ manifest
    try:
        from services.subagent_manifest import agent_names
        _manifest_names = set(agent_names(manifest))
        _unknown = _nodes - _manifest_names
        if _unknown:
            errors.append(f"图节点不在 manifest: {sorted(_unknown)}")
    except Exception as _e:
        errors.append(f"manifest 校验不可用: {_e}")
    # 2. 边两端必须为已知节点
    for _e in _g.get("edges") or []:
        _f, _t = _e.get("from"), _e.get("to")
        if _f not in _nodes:
            errors.append(f"边 from 未知节点: {_f}")
        if _t not in _nodes:
            errors.append(f"边 to 未知节点: {_t}")
    # 3. 依赖环检测（DFS）——跳过显式标记 cycle:true 的边（教学循环是设计意图：
    # 呈现→评估→调整→再呈现；无意的环才报错）
    _adj = {n: [] for n in _nodes}
    for _e in _g.get("edges") or []:
        if _e.get("from") in _adj and _e.get("to") in _adj and not _e.get("cycle"):
            _adj[_e["from"]].append(_e["to"])
    _visiting, _visited = set(), set()

    def _dfs(n: str, path: list) -> Optional[list]:
        if n in _visiting:
            return path + [n]
        if n in _visited:
            return None
        _visiting.add(n)
        for _nx in _adj.get(n, []):
            _r = _dfs(_nx, path + [n])
            if _r:
                return _r
        _visiting.discard(n)
        _visited.add(n)
        return None

    for _n in _nodes:
        _cycle = _dfs(_n, [])
        if _cycle:
            errors.append(f"依赖环: {'→'.join(_cycle)}")
            break
    return errors


def graph_view(graph: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """admin 视图（运维可视化）：节点+边+版本+统计。"""
    _g = graph or _load_graph()
    _nodes = _g.get("nodes") or []
    _edges = _g.get("edges") or []
    return {
        "version": _g.get("version", "0"),
        "nodes": [{"id": n.get("id"), "role": n.get("role", ""),
                   "trigger": (n.get("trigger") or "")[:80]} for n in _nodes],
        "edges": [{"from": e.get("from"), "to": e.get("to")} for e in _edges],
        "stats": {"nodes": len(_nodes), "edges": len(_edges)},
    }


__all__ = ["get_graph", "validate_graph", "graph_view"]
