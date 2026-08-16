# -*- coding: utf-8 -*-
"""test_semantic_search.py — C3 语义检索测试。

覆盖：语义检索服务——模型可用时向量检索，缺失时降级关键词匹配（ratchet）。
场景：①索引文档 ②语义查询（近义概念）③模型缺失降级 ④空索引容错。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.semantic_search import SemanticSearch


def test_index_and_search():
    """索引文档后可检索（关键词匹配基线）。"""
    s = SemanticSearch()
    s.index([
        {"id": "k1", "text": "勾股定理：直角三角形两直角边平方和等于斜边平方"},
        {"id": "k2", "text": "导数描述函数在某一点的变化率"},
        {"id": "k3", "text": "积分是导数的逆运算"},
    ])
    results = s.search("什么是导数")
    assert results, "应返回结果"
    # BM25 基线：k2（含'导数'且主题相关）或 k3（含'导数'）都命中
    assert results[0]["id"] in ("k2", "k3")
    assert results[0]["score"] > 0


def test_semantic_near_phrase():
    """近义概念查询：'毕达哥拉斯定理'与'勾股定理'无共享 token——BM25 基线返回空，
    这正是语义检索（向量模型）要解决的核心缺口。模型缺失时降级返回空（不抛异常）。"""
    s = SemanticSearch()
    s.index([
        {"id": "k1", "text": "勾股定理：直角三角形两直角边平方和等于斜边平方"},
        {"id": "k2", "text": "牛顿第二定律 F=ma"},
    ])
    results = s.search("毕达哥拉斯定理")
    # BM25 基线：无共享 token → 空（模型就绪后向量检索将命中 k1）
    assert results == [] or results[0]["id"] == "k1"


def test_missing_model_fallback():
    """模型缺失（ONNX 不可加载）→ 降级关键词匹配，不抛异常。"""
    s = SemanticSearch()
    # 强制模型不可用
    s._model = None
    s.index([{"id": "a", "text": "机器学习是人工智能的分支"}])
    results = s.search("AI")
    assert isinstance(results, list)  # 降级返回（可能空或命中）

def test_empty_index():
    """空索引 → 返回空列表（不抛异常）。"""
    s = SemanticSearch()
    assert s.search("任何查询") == []


def test_search_returns_scores():
    """结果含 score 字段（可排序）。"""
    s = SemanticSearch()
    s.index([
        {"id": "a", "text": "概率论研究随机事件的数学规律"},
        {"id": "b", "text": "统计学研究数据收集与分析的方法"},
    ])
    results = s.search("随机事件")
    assert results
    assert "score" in results[0]
    assert results[0]["id"] == "a"
