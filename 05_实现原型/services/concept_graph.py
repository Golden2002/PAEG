# -*- coding: utf-8 -*-
"""services/concept_graph.py —— C2 学科知识图谱（P1，§3.54）

借鉴来源：
source:  networkx 图论模型（Directed Acyclic Graph）
adapted: 纯 Python 实现（零依赖）+ 内置数学/物理学科前驱关系
since:   PAEG v0.73 §3.54 C2

设计：
- 学科知识的前驱/后继/相关关系（如 函数→极限→导数→积分）
- ConceptGraph.prerequisites() / successors() / learning_path() / relations()
- 内置种子数据（数学/物理核心链），后续可扩展 data/concept_graph.json
- 缺失节点容错（返回空，不抛异常）
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

# 内置种子数据：数学核心链（前驱→后继）
_EDGES = [
    # 数学基础链
    ("函数", "极限"),
    ("极限", "导数"),
    ("导数", "积分"),
    ("积分", "微分方程"),
    ("导数", "微分方程"),
    # 代数链
    ("方程", "不等式"),
    ("方程", "函数"),
    ("集合", "函数"),
    # 几何链
    ("三角形", "相似三角形"),
    ("三角形", "勾股定理"),
    ("勾股定理", "三角函数"),
    # 物理链
    ("位移", "速度"),
    ("速度", "加速度"),
    ("力", "牛顿定律"),
    ("牛顿定律", "功"),
    ("功", "能量"),
]

_RELATED = {
    "导数": ["变化率"],
    "函数": ["图像", "定义域"],
    "速度": ["平均速度", "瞬时速度"],
}


class ConceptGraph:
    """学科概念前驱关系图（纯 Python，零依赖）。"""

    def __init__(self, data_path: str = ""):
        self._edges: List[tuple] = list(_EDGES)
        self._related: Dict[str, List[str]] = {k: list(v) for k, v in _RELATED.items()}
        # 可选：从 data/concept_graph.json 加载扩展
        if data_path and os.path.isfile(data_path):
            try:
                with open(data_path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._edges = list(data.get("edges", self._edges))
                    self._related = dict(data.get("related", self._related))
            except Exception:
                pass

    def prerequisites(self, concept: str) -> List[str]:
        """前驱知识（直接依赖）：A→concept 的所有 A。"""
        return [a for a, b in self._edges if b == concept]

    def successors(self, concept: str) -> List[str]:
        """后继知识（可进阶）：concept→B 的所有 B。"""
        return [b for a, b in self._edges if a == concept]

    def relations(self, concept: str) -> Dict[str, List[str]]:
        """全部关系（前驱/后继/相关）。"""
        return {
            "prerequisites": self.prerequisites(concept),
            "successors": self.successors(concept),
            "related": list(self._related.get(concept, [])),
        }

    def learning_path(self, concept: str) -> List[str]:
        """完整学习路径：从根节点到目标概念的前驱链。

        沿 prerequisites 递归回溯，返回 根→...→目标 的路径。
        找不到根（图环或缺失）时返回 [concept] 本身。
        """
        if concept not in self._all_concepts():
            return [concept]
        path = [concept]
        current = concept
        visited = set()
        while current not in visited:
            visited.add(current)
            pres = self.prerequisites(current)
            if not pres:
                break
            # 取第一个前驱继续回溯
            current = pres[0]
            path.insert(0, current)
        return path

    def _all_concepts(self) -> set:
        all_c = set()
        for a, b in self._edges:
            all_c.add(a)
            all_c.add(b)
        return all_c


__all__ = ["ConceptGraph"]
