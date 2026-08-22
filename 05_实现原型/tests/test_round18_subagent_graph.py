# -*- coding: utf-8 -*-
"""Round 12 续 ⭐ subagent 图测试（test_round18_subagent_graph.py）。

§3.85 P1（Codex Harness 借鉴）：subagent 显式图——调度可观测/可演进。
守护：
1. 图声明存在且可加载（10 节点）
2. 节点全部在 manifest 中（声明=实现）
3. 边两端均为已知节点
4. 无依赖环
5. graph_view admin 视图结构
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.subagent_graph import (
    get_graph, validate_graph, graph_view,
)
from services.subagent_manifest import get_manifest, agent_names


class TestSubagentGraph:
    def test_graph_loaded(self):
        g = get_graph()
        assert g.get("version") == "1"
        assert len(g.get("nodes") or []) >= 10

    def test_nodes_in_manifest(self):
        errors = validate_graph()
        assert not errors, f"图校验失败: {errors}"

    def test_manifest_coverage(self):
        # 图节点应覆盖 manifest 全部 agent（声明=实现）
        g = get_graph()
        g_nodes = {n["id"] for n in g.get("nodes") or []}
        m_names = set(agent_names(get_manifest()))
        missing = m_names - g_nodes
        assert not missing, f"manifest 中未入图: {missing}"

    def test_no_cycle(self):
        errors = validate_graph()
        assert not any("依赖环" in e for e in errors), errors

    def test_graph_view(self):
        v = graph_view()
        assert v["stats"]["nodes"] >= 10
        assert v["version"] == "1"
        assert all("id" in n for n in v["nodes"])
