# -*- coding: utf-8 -*-
"""test_subagents_pre_retrieve.py —— §3 B3 ⭐ _pre_retrieve SOURCES 块重构测试

Oracle RAG 优化项 #3：检索结果注入格式改为结构化 SOURCES 块（含 [N] 编号 +
来源类型 + 来源 ID + 相关性分），LLM 提示词追加"引用编号/无答案路径"指令，
防幻觉可审计。

参考：deepseek-harness commit SHA 47f943859bef60e4160492346772ded9b24f765a
（dsh context 组装的 SOURCES 注入参考实现）。

设计契约（from B3 task）：
- _pre_retrieve 输出含 `SOURCES:` 块，每条格式：
    [N] {source_type} | {doc_id} | {relevance_score}
    {chunk/snippet 内容}
- 保留 `<<UNTRUSTED trust=external>>` 信封标记（安全基线不动）
- 检索结果为空 → 不输出 SOURCES 块（也不输出 UNTRUSTED 信封——避免误导）
- 提示词追加指令：「用 [N] 引用对应来源；若检索结果不包含答案，明确回复
  "知识库暂无此信息"，不要编造。」
- 检索逻辑本身不动（kb.search 调用、top_k、jieba 切词均保留）

测试策略：
- mock knowledge_base.KnowledgeBase（search/get_subject 桩函数）
- 直接传 retrieval_plan 跳过 LLM scope planner
- scopes 传空列表 → Library 文件扫描分支跳过（避免依赖磁盘）
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional

import pytest


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ───────────────────────────────────────────────────────────────────
# Fake fixtures：构造可注入的 KnowledgeBase + learner + LLM
# ───────────────────────────────────────────────────────────────────

class _FakeKB:
    """最小 KnowledgeBase 替身：只实现 _pre_retrieve 实际调用的方法。

    - search(query, subject, top_k) → hits list
    - get_subject(cid) → node dict or None
    - get_humanity(cid) / get_skill(cid) → 同上
    """

    def __init__(self, hits: Optional[List[dict]] = None,
                 node_for: Optional[dict] = None) -> None:
        self._hits = hits or []
        self._node = node_for or {}

    def search(self, query: str, subject: str = None, top_k: int = 5) -> List[dict]:
        return list(self._hits[:top_k])

    def get_subject(self, cid: str) -> Optional[dict]:
        if cid == self._node.get("id"):
            return self._node
        return None

    def get_humanity(self, cid: str) -> Optional[dict]:
        return None

    def get_skill(self, cid: str) -> Optional[dict]:
        return None


class _FakeLearner:
    """最小 learner 替身（_pre_retrieve 不依赖 learner 字段，但保留接口）。"""
    id = "test_learner"
    nickname = "测试"


def _patch_kb(monkeypatch, hits, node):
    """把 knowledge_base.KnowledgeBase 替换为返回 (_FakeKB, hits, node) 的工厂。

    _pre_retrieve 内部 ``from knowledge_base import KnowledgeBase`` 拿到类对象，
    然后 ``KnowledgeBase()`` 实例化——所以 patch 类的 __new__/调用路径即可。
    """
    import knowledge_base as _kb_mod

    fake = _FakeKB(hits=hits, node_for=node)

    def _factory(*args, **kwargs):
        return fake

    monkeypatch.setattr(_kb_mod, "KnowledgeBase", _factory)
    return fake


# ───────────────────────────────────────────────────────────────────
# 1) 有检索结果 → 输出含 SOURCES: 块与 [1] 编号
# ───────────────────────────────────────────────────────────────────

def test_pre_retrieve_emits_sources_block(monkeypatch):
    """_pre_retrieve 有命中 → 输出包含 'SOURCES:' 头与至少一条 [N] 编号行。"""
    import subagents as _sa

    hits = [
        {"concept_id": "derivative", "title": "导数",
         "snippet": "导数是函数在某点的瞬时变化率",
         "relevance_score": 4, "difficulty": 6},
        {"concept_id": "limit", "title": "极限",
         "snippet": "极限描述变量趋近某值时的行为",
         "relevance_score": 3, "difficulty": 5},
    ]
    node = {
        "id": "derivative",
        "definition": "函数在某点的瞬时变化率，几何意义为切线斜率。",
        "intuition": "想象把曲线无限放大，它几乎就是一条直线。",
    }
    _patch_kb(monkeypatch, hits, node)

    # scopes=[] 跳过 Library 文件扫描（不依赖磁盘），关键词走分词兜底
    plan = {"scopes": [], "keywords": ["导数"]}
    out = _sa._pre_retrieve("什么是导数", subject="math",
                            learner=_FakeLearner(), llm=None,
                            retrieval_plan=plan)
    assert out, "有命中时 _pre_retrieve 应返回非空字符串"
    assert "SOURCES:" in out, f"输出应包含 SOURCES: 头，实际前 200 字: {out[:200]}"
    assert "[1]" in out, "输出应包含 [1] 编号行（至少 1 条 source）"
    # 至少两条编号行（[1] [2]）——验证 N 自增与多条渲染
    assert "[2]" in out, "输出应包含 [2] 编号行（验证 N 自增与多条渲染）"
    print(f"✔ test_pre_retrieve_emits_sources_block (output len={len(out)})")


# ───────────────────────────────────────────────────────────────────
# 2) 每条含 source_type / doc_id / score 三要素
# ───────────────────────────────────────────────────────────────────

def test_pre_retrieve_inlines_source_metadata(monkeypatch):
    """[N] 行应内联 source_type=kb、doc_id、relevance_score 三元组。"""
    import subagents as _sa

    hits = [
        {"concept_id": "derivative", "title": "导数",
         "snippet": "导数是函数在某点的瞬时变化率",
         "relevance_score": 4, "difficulty": 6},
    ]
    node = {
        "id": "derivative",
        "definition": "函数在某点的瞬时变化率，几何意义为切线斜率。",
        "intuition": "",
    }
    _patch_kb(monkeypatch, hits, node)

    plan = {"scopes": [], "keywords": ["导数"]}
    out = _sa._pre_retrieve("什么是导数", subject="math",
                            learner=_FakeLearner(), llm=None,
                            retrieval_plan=plan)
    assert out, "应有命中"

    # 抽出第一个 [1] 行（到下一个 [N] 或段落结束）
    src_lines = [ln for ln in out.splitlines() if ln.startswith("[")]
    assert src_lines, f"应有 [N] 起始行，实际输出: {out}"
    first = src_lines[0]
    assert "source_type=kb" in first, (
        f"[1] 行应标注 source_type=kb，实际: {first}")
    assert "derivative" in first, f"[1] 行应含 doc_id=derivative，实际: {first}"
    # 相关性分以 | 分隔的数字形式出现
    assert "| 4" in first or "|4" in first, (
        f"[1] 行应含 relevance_score=4（以 | 分隔），实际: {first}")
    print(f"✔ test_pre_retrieve_inlines_source_metadata (first line: {first!r})")


# ───────────────────────────────────────────────────────────────────
# 3) 无结果 → 不输出 SOURCES 块（也不含 UNTRUSTED 信封）
# ───────────────────────────────────────────────────────────────────

def test_pre_retrieve_omits_sources_when_empty(monkeypatch):
    """kb.search 返回空 → _pre_retrieve 返回 ''（无 SOURCES: 头，无 UNTRUSTED 信封）。"""
    import subagents as _sa

    _patch_kb(monkeypatch, hits=[], node={})

    plan = {"scopes": [], "keywords": ["偏门冷词xyz123"]}
    out = _sa._pre_retrieve("偏门冷词xyz123是什么", subject="unknown",
                            learner=_FakeLearner(), llm=None,
                            retrieval_plan=plan)
    assert out == "", (
        f"无命中时 _pre_retrieve 应返回空串（不输出 SOURCES / 不输出 UNTRUSTED 信封），"
        f"实际: {out!r}")
    assert "SOURCES:" not in out, "无命中时输出不应含 SOURCES: 头"
    assert "<<UNTRUSTED" not in out, "无命中时输出不应含 UNTRUSTED 信封（避免误导）"
    print("✔ test_pre_retrieve_omits_sources_when_empty")


# ───────────────────────────────────────────────────────────────────
# 4) SOURCES 块必须被 UNTRUSTED 信封包裹（安全基线保留）
# ───────────────────────────────────────────────────────────────────

def test_pre_retrieve_untrusted_envelope_wraps_sources(monkeypatch):
    """有命中时，<<UNTRUSTED trust=external>> ... <</UNTRUSTED>> 包裹 SOURCES 块（v0.46 安全基线不动）。"""
    import subagents as _sa

    hits = [
        {"concept_id": "derivative", "title": "导数",
         "snippet": "导数是函数在某点的瞬时变化率",
         "relevance_score": 4, "difficulty": 6},
    ]
    node = {"id": "derivative", "definition": "瞬时变化率。", "intuition": ""}
    _patch_kb(monkeypatch, hits, node)

    plan = {"scopes": [], "keywords": ["导数"]}
    out = _sa._pre_retrieve("什么是导数", subject="math",
                            learner=_FakeLearner(), llm=None,
                            retrieval_plan=plan)
    assert out, "应有命中"
    assert "<<UNTRUSTED trust=external" in out, (
        f"输出应保留 UNTRUSTED 信封起标记（v0.46 安全基线），实际前 200: {out[:200]}")
    assert "<</UNTRUSTED>>" in out, (
        f"输出应保留 UNTRUSTED 信封闭标记，实际前 200: {out[:200]}")
    # SOURCES 块必须在信封内（信封外不能出现 source 内容）
    open_at = out.find("<<UNTRUSTED")
    close_at = out.find("<</UNTRUSTED>>")
    sources_at = out.find("SOURCES:")
    assert open_at < sources_at < close_at, (
        f"SOURCES 块必须被 UNTRUSTED 信封包裹（开→sources→闭），"
        f"实际偏移 open={open_at} sources={sources_at} close={close_at}")
    print("✔ test_pre_retrieve_untrusted_envelope_wraps_sources")


# ───────────────────────────────────────────────────────────────────
# 5) 提示词追加"引用编号/无答案路径"指令
# ───────────────────────────────────────────────────────────────────

def test_pre_retrieve_appends_citation_instruction(monkeypatch):
    """有命中时输出应包含引用编号指令（[N]）与无答案路径指令（'知识库暂无此信息'）。"""
    import subagents as _sa

    hits = [
        {"concept_id": "derivative", "title": "导数",
         "snippet": "导数是函数在某点的瞬时变化率",
         "relevance_score": 4, "difficulty": 6},
    ]
    node = {"id": "derivative", "definition": "瞬时变化率。", "intuition": ""}
    _patch_kb(monkeypatch, hits, node)

    plan = {"scopes": [], "keywords": ["导数"]}
    out = _sa._pre_retrieve("什么是导数", subject="math",
                            learner=_FakeLearner(), llm=None,
                            retrieval_plan=plan)
    assert out, "应有命中"
    assert "[N]" in out, (
        f"输出应包含引用编号指令（提示 LLM 用 [N] 引用），实际: {out[-300:]}")
    assert "知识库暂无此信息" in out, (
        f"输出应包含无答案路径指令（防幻觉），实际: {out[-300:]}")
    print("✔ test_pre_retrieve_appends_citation_instruction")


# ───────────────────────────────────────────────────────────────────
# 6) 检索逻辑不变：未命中时不调用 get_subject（且不依赖 KnowledgeBase 实际数据）
# ───────────────────────────────────────────────────────────────────

def test_pre_retrieve_search_call_count_preserved(monkeypatch):
    """保证检索逻辑不变：top_k 与循环结构保留——search 应至少被调用 1 次（关键词 + 兜底整句）。"""
    import subagents as _sa

    call_log = []
    kb = _FakeKB(hits=[])
    # wrap search to log
    orig_search = kb.search

    def _logged_search(query, subject=None, top_k=5):
        call_log.append((query, subject, top_k))
        return orig_search(query, subject=subject, top_k=top_k)

    kb.search = _logged_search

    import knowledge_base as _kb_mod
    monkeypatch.setattr(_kb_mod, "KnowledgeBase", lambda *a, **k: kb)

    plan = {"scopes": [], "keywords": ["导数", "极限"]}
    _sa._pre_retrieve("什么是导数", subject="math",
                      learner=_FakeLearner(), llm=None,
                      retrieval_plan=plan)

    # 检索逻辑必须保留：每个关键词调 1 次 search（top_k=3），再兜底整句 1 次
    assert len(call_log) >= 1, (
        f"search 应至少被调用 1 次（关键词 + 兜底），实际 {len(call_log)}: {call_log}")
    # top_k 必须保留 3（与原实现一致）
    for q, s, k in call_log:
        assert k == 3, f"top_k 必须保留为 3（v0.22.1 实现约定），实际 {k} (q={q})"
    print(f"✔ test_pre_retrieve_search_call_count_preserved (calls={len(call_log)})")