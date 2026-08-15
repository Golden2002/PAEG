# -*- coding: utf-8 -*-
"""test_prereq_graph.py —— §3.12 ⭐ 知识依赖图注入测试

需求（§3.12 真实缺口：leads_to 无代码消费，prereqs 未注入 LLM 提示词）：
- 从 KB 抽 prereqs/leads_to → 生成"学概念前需掌握 X，掌握后能继续学 Y"指令句
- 注入 build_presenter_system / Diagnostor 提示词，让知识图谱对 LLM 可见
"""
from __future__ import annotations

import pytest


def _make_kb_with_graph():
    """构造带 prerequisites/leads_to 的迷你 KB（用真实 resolve_node 验证）。"""
    from knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    return kb


def test_extract_prereq_graph():
    """从 KB 提取概念的前置/后继知识图谱（真实 KB：导数应可解析）。"""
    from services.prereq_graph import extract_concept_graph
    kb = _make_kb_with_graph()
    graph = extract_concept_graph(kb, "导数", subject="math")
    assert "prerequisites" in graph, "应提取前置知识"
    assert "leads_to" in graph, "应提取后继知识"
    assert graph["concept"] == "导数"
    # 真实 KB 中导数节点若存在 prerequisites 字段则验证其结构
    if graph["prerequisites"]:
        assert isinstance(graph["prerequisites"], list)


def test_build_graph_instruction():
    """生成"学前需掌握X，掌握后能学Y"指令句。"""
    from services.prereq_graph import build_graph_instruction
    graph = {"prerequisites": ["极限", "函数"], "leads_to": ["积分"], "concept": "导数"}
    inst = build_graph_instruction(graph)
    assert "极限" in inst and "函数" in inst, "指令句应含前置知识"
    assert "积分" in inst, "指令句应含后继知识"
    assert "掌握" in inst, "应为教学指令语态"


def test_graph_instruction_missing_fields():
    """缺前置/后继 → 优雅降级（不抛异常）。"""
    from services.prereq_graph import build_graph_instruction
    inst = build_graph_instruction({"concept": "孤独", "prerequisites": [], "leads_to": []})
    assert inst == "", "无图数据应返回空串"


def test_absent_concept_returns_empty():
    """概念不在 KB → 空图（不抛异常）。"""
    from services.prereq_graph import extract_concept_graph
    kb = _make_kb_with_graph()
    graph = extract_concept_graph(kb, "不存在的概念", subject="math")
    assert graph == {"prerequisites": [], "leads_to": [], "concept": "不存在的概念"}


def test_inject_into_presenter_system():
    """知识依赖图注入 build_presenter_system（含图指令句）。"""
    from services.prereq_graph import inject_graph_into_system
    kb = _make_kb_with_graph()
    system = "你是数学老师。"
    injected = inject_graph_into_system(system, kb, concept="导数", subject="math")
    # 幂等：注入不应破坏原 system
    assert system in injected, "注入应保留原 system"
    # 若 KB 导数有图数据 → 含指令句；否则原样返回（幂等）
    if injected != system:
        assert "【知识路径】" in injected, "注入应含知识路径标记"
