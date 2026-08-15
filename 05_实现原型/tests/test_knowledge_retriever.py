# -*- coding: utf-8 -*-
"""
A4 · KnowledgeRetriever 多路召回模块测试

任务背景：Oracle RAG 优化项 #6 — HybridRetriever 抽象 + RRF 融合（BM25 + tag
双通道；semantic 钩子预留，当前 disabled），为 B8 embedding 接入铺路。

本测试覆盖（任务 MUST DO 列表）：
1. test_recall_merges_bm25_and_tag_channels       BM25 + tag 双通道经 RRF 融合后
   A 排第一，B 在 C 前（验证融合顺序符合直觉）
2. test_recall_excludes_superseded_nodes          status="superseded" 节点绝不
   出现在结果中（即使语义最相关）
3. test_recall_returns_top_k                      top_k=2 → 恰好 2 条
4. test_recall_empty_source_returns_empty         无节点 → []
5. test_recall_semantic_disabled_by_default       semantic.enabled=False → 不抛
   错、不调 embedding（用 fake 确认 _semantic_channel 未被调用）
6. test_recall_dedup_same_node_across_channels    同一节点被两通道命中 → 结果
   只出现一次，且 sources 列表含两个通道名

设计要点
--------
- 全部用 dict 节点直接注入，不依赖真实 KB / self_evolution（保证测试纯净+无
  I/O）；只有 ``test_recall_empty_source_returns_empty`` 也允许空 dict。
- 隔离 rag_config：monkeypatch 重定向 ``services.rag_config._CONFIG_PATH`` 到
  tmp，避免污染真实 config（与其他 RAG 测试一致）。
- fake 注入语义通道：构造 ``_FakeKnowledgeRetriever`` 子类，覆写
  ``_semantic_channel``，在 ``test_recall_semantic_disabled_by_default`` 中
  确认没被调用。
- RRF(k=60)：与 web_search_tool.web_search_multi 对齐（k=60 是 RAG 内部惯例）。
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

# 与项目内其他测试一致：把 05_实现原型 根目录加入 sys.path
_PROJ_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)


# ────────────────────────────────────────────────────────────
# Fixture：隔离 rag_config（每个 test 拿到一份独立 tmp config）
# ────────────────────────────────────────────────────────────
@pytest.fixture
def isolated_rag_config(tmp_path, monkeypatch):
    """重定向 services.rag_config._CONFIG_PATH 到 tmp，并 reset 缓存。

    每个 test 写自己的 rag.json（覆盖 retrieval/semantic 等字段）→ 完全不
    污染真实 config/rag.json。
    """
    import services.rag_config as rc

    cfg_path = tmp_path / "rag.json"
    monkeypatch.setattr(rc, "_CONFIG_PATH", cfg_path)
    rc.reset_rag_config_cache()

    # 写入默认三节（包含 top_k / rrf_k / semantic.enabled=False）
    cfg_path.write_text(
        json.dumps(
            {
                "chunker": {"max_chars": 400, "overlap": 50},
                "retrieval": {"top_k": 5, "bm25_k1": 1.5, "bm25_b": 0.75, "rrf_k": 60},
                "dedup": {"key": "subject+concept"},
                "semantic": {"enabled": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rc.reset_rag_config_cache()
    yield cfg_path
    rc.reset_rag_config_cache()


# ────────────────────────────────────────────────────────────
# 节点构造 helper：任务 MUST DO 列表里给定的 A/B/C/D 节点
# ────────────────────────────────────────────────────────────
def _node_A() -> Dict[str, Any]:
    """节点 A：concept=导数，tags=[数学,微积分]——BM25 + tag 都强相关。"""
    return {
        "id": "math.calculus.derivative",
        "subject": "math",
        "concept": "导数",
        "definition": "导数是函数在某一点的瞬时变化率。",
        "intuition": "导数=瞬时速度=曲线在该点的切线斜率。",
        "tags": ["数学", "微积分"],
        "difficulty": 6,
        "importance": "high",
        "type": "concept",
        "status": "live",
    }


def _node_B() -> Dict[str, Any]:
    """节点 B：concept=积分，tags=[数学,微积分]——tag 强相关，BM25 文本部分命中。"""
    return {
        "id": "math.calculus.integral",
        "subject": "math",
        "concept": "积分",
        "definition": "积分是求和的极限，与导数互为逆运算。",
        "intuition": "积分求面积，导数求斜率；两者构成微积分的基石。",
        "tags": ["数学", "微积分"],
        "difficulty": 6,
        "importance": "high",
        "type": "concept",
        "status": "live",
    }


def _node_C() -> Dict[str, Any]:
    """节点 C：concept=熵，tags=[物理]——BM25 文本命中（query 含"导数 微积分"）较弱、tag 不命中。"""
    return {
        "id": "physics.thermodynamics.entropy",
        "subject": "physics",
        "concept": "熵",
        "definition": "熵是热力学中描述系统无序度的状态量。",
        "intuition": "一杯热水放凉：分子从有序运动变得混乱。",
        "tags": ["物理"],
        "difficulty": 6,
        "importance": "medium",
        "type": "concept",
        "status": "live",
    }


def _node_D_superseded() -> Dict[str, Any]:
    """节点 D：status="superseded"——即使文本最相关也必须被排除。"""
    return {
        "id": "math.calculus.derivative.legacy",
        "subject": "math",
        "concept": "导数（已废弃版本）",
        "definition": "这是被 A2 superseded 机制标记的旧版本节点。",
        "intuition": "导数是瞬时变化率。",
        "tags": ["数学", "微积分"],
        "difficulty": 5,
        "importance": "low",
        "type": "concept",
        "status": "superseded",  # ← 关键：必须被排除
    }


# ────────────────────────────────────────────────────────────
# 测试 1：BM25 + tag 双通道经 RRF 融合
# ────────────────────────────────────────────────────────────
def test_recall_merges_bm25_and_tag_channels(isolated_rag_config):
    """query="导数 微积分" → A 排第一，B 在 C 前。

    直觉分解：
    - A：BM25 命中"导数"（最强信号）+ tag 命中"微积分"（双通道）→ RRF 加成最高
    - B：BM25 命中"微积分"或文本部分相关 + tag 命中"微积分"→ 双通道但 BM25 略弱
    - C：BM25 文本含"积分"等（query 没"积分"）→ 几乎不命中；tag 通道无"微积分" → RRF 最低
    """
    from services.retrieval.knowledge_retriever import KnowledgeRetriever

    # 关键：dict 的 key 必须等于 node["id"]，与生产路径
    # ``from_evolved_and_kb()`` 构造的 ``{nid: node}`` shape 一致
    nodes = {
        "math.calculus.derivative": _node_A(),
        "math.calculus.integral": _node_B(),
        "physics.thermodynamics.entropy": _node_C(),
    }
    retriever = KnowledgeRetriever(nodes=nodes)

    results = retriever.recall("导数 微积分", top_k=5)

    assert len(results) >= 2, f"应有 ≥2 个结果，实际 {len(results)}: {results}"
    # A 必须排第一（双通道命中：BM25 命中"导数" + tag 命中"微积分"）
    assert results[0]["concept_id"] == "math.calculus.derivative", (
        f"A 应排第一，实际第一名 concept_id={results[0]['concept_id']}；"
        f"results={results}"
    )
    # B 必须在结果中（BM25 部分命中"积分"或文本 + tag 双通道）
    ids = [r["concept_id"] for r in results]
    assert "math.calculus.integral" in ids, (
        f"B 必须在结果中（B 双通道命中），实际 ids={ids}"
    )
    # C（无任何信号）如果出现必须在 A/B 之后（C 无 BM25 命中，tag 也不命中）
    if "physics.thermodynamics.entropy" in ids:
        assert ids.index("math.calculus.derivative") < ids.index(
            "physics.thermodynamics.entropy"
        ), f"A 必须在 C 前（A 双通道，C 无信号），实际 ids={ids}"
        assert ids.index("math.calculus.integral") < ids.index(
            "physics.thermodynamics.entropy"
        ), f"B 必须在 C 前（B tag 命中，C 无信号），实际 ids={ids}"

    # 每条 result 必须有 sources 字段（非空 list）
    for r in results:
        assert "sources" in r, f"result 缺 sources 字段: {r}"
        assert isinstance(r["sources"], list)
        assert len(r["sources"]) >= 1, f"sources 至少含 1 通道: {r}"
        # relevance_score 必须是数字
        assert isinstance(r["relevance_score"], (int, float))
        assert r["relevance_score"] > 0, f"relevance_score 应 >0: {r}"


# ────────────────────────────────────────────────────────────
# 测试 2：superseded 节点必须被排除
# ────────────────────────────────────────────────────────────
def test_recall_excludes_superseded_nodes(isolated_rag_config):
    """即使 D 的文本与 query 最相关（人为构造），status="superseded" 也必须被排除。"""
    from services.retrieval.knowledge_retriever import KnowledgeRetriever

    # 把 D 写得"看起来"最相关（定义完全照搬 query）——验证排除是按 status，不是按相关性
    d = _node_D_superseded()
    d["definition"] = "导数 微积分 导数 微积分 强相关被废弃节点"  # 文本上看起来很命中
    d["intuition"] = "导数是微积分的基础 已被 A2 机制 superseded"

    nodes = {
        "math.calculus.derivative": _node_A(),
        "math.calculus.integral": _node_B(),
        "math.calculus.derivative.legacy": d,
    }
    retriever = KnowledgeRetriever(nodes=nodes)

    results = retriever.recall("导数 微积分", top_k=5)

    ids = [r["concept_id"] for r in results]
    assert "math.calculus.derivative.legacy" not in ids, (
        f"superseded 节点 D 必须被排除，实际 ids={ids}"
    )
    # A 和 B 仍应在
    assert "math.calculus.derivative" in ids, f"live 节点 A 应保留，实际 ids={ids}"
    assert "math.calculus.integral" in ids, f"live 节点 B 应保留，实际 ids={ids}"


# ────────────────────────────────────────────────────────────
# 测试 3：top_k 必须截断到恰好 top_k（候选充足时）
# ────────────────────────────────────────────────────────────
def test_recall_returns_top_k(isolated_rag_config):
    """top_k=2 → 恰好 2 条（候选 3 个节点）。"""
    from services.retrieval.knowledge_retriever import KnowledgeRetriever

    nodes = {
        "math.calculus.derivative": _node_A(),
        "math.calculus.integral": _node_B(),
        "physics.thermodynamics.entropy": _node_C(),
    }
    retriever = KnowledgeRetriever(nodes=nodes)

    results = retriever.recall("导数 微积分", top_k=2)
    assert len(results) == 2, f"top_k=2 应返回恰好 2 条，实际 {len(results)}: {results}"


# ────────────────────────────────────────────────────────────
# 测试 4：空数据源 → 空结果（不抛错）
# ────────────────────────────────────────────────────────────
def test_recall_empty_source_returns_empty(isolated_rag_config):
    """无任何节点 → recall() 返回 []。"""
    from services.retrieval.knowledge_retriever import KnowledgeRetriever

    retriever = KnowledgeRetriever(nodes={})
    results = retriever.recall("导数 微积分", top_k=5)
    assert results == [], f"空数据源应返回 []，实际 {results}"


# ────────────────────────────────────────────────────────────
# 测试 5：semantic.enabled=False → 不调用 _semantic_channel
# ────────────────────────────────────────────────────────────
def test_recall_semantic_disabled_by_default(isolated_rag_config):
    """默认 config 中 semantic.enabled=False → _semantic_channel 必须不被调用。

    实现方式：定义 ``_FakeKnowledgeRetriever`` 子类，覆写 _semantic_channel
    抛 AssertionError。如果被调用则测试失败（这样在没有任何 embedding 实现
    的情况下也能保证"不调用"契约）。
    """
    from services.retrieval.knowledge_retriever import KnowledgeRetriever

    class _FakeKnowledgeRetriever(KnowledgeRetriever):
        def _semantic_channel(self, query: str, nodes: dict) -> list:
            raise AssertionError(
                "_semantic_channel 不应在 semantic.enabled=False 时被调用"
            )

    nodes = {
        "math.calculus.derivative": _node_A(),
        "math.calculus.integral": _node_B(),
    }
    retriever = _FakeKnowledgeRetriever(nodes=nodes)

    # 不抛错即说明 semantic 通道没被调用
    results = retriever.recall("导数 微积分", top_k=3)
    assert isinstance(results, list)
    assert len(results) >= 1

    # 同时验证 config 真的是 disabled（兜底）
    from services.rag_config import get_rag_config

    assert get_rag_config()["semantic"]["enabled"] is False


# ────────────────────────────────────────────────────────────
# 测试 6：同一节点被多通道命中 → 去重，且 sources 列出所有通道
# ────────────────────────────────────────────────────────────
def test_recall_dedup_same_node_across_channels(isolated_rag_config):
    """A 同时被 BM25 通道（"导数"）和 tag 通道（"微积分"）命中 → 结果只出现 1 次，sources 含 2 通道。"""
    from services.retrieval.knowledge_retriever import KnowledgeRetriever

    nodes = {
        "math.calculus.derivative": _node_A(),
        "math.calculus.integral": _node_B(),
    }
    retriever = KnowledgeRetriever(nodes=nodes)

    results = retriever.recall("导数 微积分", top_k=5)

    # A 应只出现 1 次
    a_hits = [r for r in results if r["concept_id"] == "math.calculus.derivative"]
    assert len(a_hits) == 1, (
        f"同一节点被多通道命中应去重为 1 次，实际 A 出现 {len(a_hits)} 次: {a_hits}"
    )

    # A 的 sources 应含 ≥2 通道（"bm25" + "tag"）
    a = a_hits[0]
    assert "sources" in a, f"result 缺 sources: {a}"
    assert isinstance(a["sources"], list)
    assert "bm25" in a["sources"], f"A 的 sources 应含 bm25，实际 {a['sources']}"
    assert "tag" in a["sources"], f"A 的 sources 应含 tag，实际 {a['sources']}"
    # 唯一性（去重）
    assert len(set(a["sources"])) == len(a["sources"]), (
        f"sources 列表不应有重复通道: {a['sources']}"
    )


if __name__ == "__main__":
    # 直跑模式（不依赖 pytest 收集）——确保 import 路径正确
    import subprocess

    r = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    sys.exit(r.returncode)
