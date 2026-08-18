# -*- coding: utf-8 -*-
"""test_concept_graph.py — C2 学科知识图谱测试（纯 Python 前驱关系图）。

覆盖：知识节点的前驱/后继/相关关系、薄弱点诊断路径、JSON 持久化。
场景：①查"导数"的前驱（极限）②查"积分"的完整路径 ③缺失节点容错。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.concept_graph import ConceptGraph


def test_prerequisites():
    """查"导数"的前驱知识（极限→导数）。"""
    g = ConceptGraph()
    pre = g.prerequisites("导数")
    assert "极限" in pre


def test_successors():
    """查"导数"的后继知识（导数→积分/微分方程）。"""
    g = ConceptGraph()
    succ = g.successors("导数")
    assert "积分" in succ


def test_full_path():
    """求"积分"的完整学习路径（前驱链：根→...→积分）。"""
    g = ConceptGraph()
    path = g.learning_path("积分")
    assert path[-1] == "积分"  # 终点是目标概念
    assert "函数" in path
    assert "极限" in path
    assert "导数" in path
    # 路径是前驱链：相邻节点有前驱关系
    for i in range(len(path) - 1):
        assert path[i] in g.prerequisites(path[i + 1])


def test_missing_node_fallback():
    """未知节点 → 返回空（不抛异常，容错）。"""
    g = ConceptGraph()
    assert g.prerequisites("不存在的概念xyz") == []
    assert g.successors("不存在的概念xyz") == []


def test_relation_types():
    """关系类型：prerequisite(前驱)/successor(后继)/related(相关)。"""
    g = ConceptGraph()
    rel = g.relations("导数")
    assert "related" in rel  # 导数有相关概念（如"变化率"）
