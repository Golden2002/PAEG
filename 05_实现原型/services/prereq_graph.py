# -*- coding: utf-8 -*-
"""services/prereq_graph.py —— §3.12 ⭐ 知识依赖图注入（v1.1.5）

需求（2026-08-15 核实：leads_to 全项目 0 代码消费，prereqs 未注入 LLM 提示词）：
- 从 KB 抽 prereqs/leads_to → 生成"学这个概念前需要掌握 X，掌握后能继续学 Y"指令句
- 注入教学 system prompt，让知识图谱对 LLM 可见（学段锚定/路径指引）

设计：
- extract_concept_graph(kb, concept, subject)：从 KB 提取 {prerequisites, leads_to, concept}
- build_graph_instruction(graph)：生成教学指令句（无数据 → 空串）
- inject_graph_into_system(system, kb, concept, subject)：注入 system prompt
- 接入点：subagents.py Diagnostor（已有 prereqs 读取，补 leads_to）+ Presenter system
"""
from __future__ import annotations

from typing import Dict, List


def extract_concept_graph(kb, concept: str, subject: str = "math") -> Dict[str, list]:
    """从 KB 提取概念的前置/后继知识图谱。

    Returns:
        {"prerequisites": [..], "leads_to": [..], "concept": concept}
    """
    prereqs: List[str] = []
    leads: List[str] = []
    try:
        # 1. 用 resolve_node 精确解析（带缓存，优先）
        node = None
        if hasattr(kb, "resolve_node"):
            node = kb.resolve_node(concept, subject)
        if node:
            prereqs = list(node.get("prerequisites") or [])
            leads = list(node.get("leads_to") or [])
        else:
            # 2. 遍历学科节点找匹配
            nodes = kb.get_subject_nodes(subject) if hasattr(kb, "get_subject_nodes") else []
            for n in nodes:
                if n.get("id") == concept or n.get("name") == concept or n.get("concept") == concept:
                    prereqs = list(n.get("prerequisites") or [])
                    leads = list(n.get("leads_to") or [])
                    break
    except Exception:
        pass
    return {"prerequisites": prereqs, "leads_to": leads, "concept": concept}


def build_graph_instruction(graph: Dict[str, list]) -> str:
    """生成"学前需掌握 X，掌握后能学 Y"指令句。

    - 无前置且无后继 → 返回空串（无图数据，不注入）
    - 只学习指令语态（"需要先掌握" / "可以继续学"）
    """
    concept = graph.get("concept", "")
    prereqs = graph.get("prerequisites") or []
    leads = graph.get("leads_to") or []
    if not prereqs and not leads:
        return ""
    parts = []
    if prereqs:
        parts.append(f"学习「{concept}」前，学生需要先掌握：{'、'.join(prereqs[:5])}")
    if leads:
        parts.append(f"掌握「{concept}」后，可以继续学习：{'、'.join(leads[:5])}")
    return "【知识路径】" + "；".join(parts) + "。讲解时按此路径锚定学段与衔接。"


def inject_graph_into_system(system: str, kb, concept: str, subject: str = "math") -> str:
    """把知识依赖图指令注入 system prompt（无数据原样返回）。"""
    graph = extract_concept_graph(kb, concept, subject)
    inst = build_graph_instruction(graph)
    if not inst:
        return system
    if not system:
        return inst
    # 幂等：已含【知识路径】则不重复注入
    if "【知识路径】" in system:
        return system
    return system.rstrip() + "\n\n" + inst


__all__ = ["extract_concept_graph", "build_graph_instruction", "inject_graph_into_system"]
