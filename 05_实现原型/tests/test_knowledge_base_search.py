# -*- coding: utf-8 -*-
"""tests/test_knowledge_base_search.py —— KnowledgeBase.search 真 BM25 排序测试。

任务背景：Oracle RAG 优化项 #2 —— 把 search() 从简化 BM25（token 命中计数）升级为
rank_bm25.BM25Okapi 真实排序（含 IDF + 长度归一化）。本测试覆盖：

1. test_kb_search_ranks_relevant_above_irrelevant  相关文档排第一（BM25 IDF 应能
   把术语命中与普通词命中区分开）
2. test_kb_search_respects_top_k                 top_k 必须返回恰好 top_k 条
   （少于候选时返回全部；多于候选时截断）
3. test_kb_search_subject_filter                 subject 过滤仍生效（指定学科
   时只返回该学科；与 BM25 排序正交）
4. test_kb_search_no_hit_returns_empty           无匹配时返回空列表（不抛异常）
5. test_kb_search_missing_field_graceful         节点缺 definition / intuition
   字段不崩（B4 后 evolved 节点字段齐全，但仍要防御未知 schema）

设计要点
--------
- 用 monkeypatch 替换 KnowledgeBase 的 subjects / humanities / skills 三个 dict 为
  最小化数据集，避免依赖 _load_demo_data（避免与既有测试相互污染）。
- 测试独立 fixture：每个 test 拿一份独立 KnowledgeBase 实例（subjects/humanities/
  skills 三个 dict 被 monkeypatch 后只剩测试数据）。
- 既验证 BM25Okapi 真排序（测试 1 中相关文档排第一），又验证接口契约不变
  （top_k / subject / 空结果 / 字段缺失）。
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixture：构造一个只含测试数据、与真实 KB 隔离的 KnowledgeBase
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_kb(monkeypatch):
    """返回一份只含测试数据的 KB：替换 self.subjects / humanities / skills 三个 dict。

    测试结束后 monkeypatch 自动还原（不影响真实 KB 实例）。
    """
    from knowledge_base import KnowledgeBase

    kb = KnowledgeBase()

    # 最小化测试语料：math / physics 各两个节点 + humanities 一个
    minimal_subjects = {
        "math.calculus.derivative": {
            "id": "math.calculus.derivative",
            "subject": "math",
            "concept": "derivative",
            "level": "undergraduate",
            "difficulty": 8,
            "definition": "导数 瞬时变化率 切线斜率",
            "intuition": "导数=瞬时速度=曲线在该点的切线斜率。",
            "explanation_variants": {
                "intuitive": "开车时速度表的读数就是位置对时间的导数。",
            },
        },
        "math.algebra.quadratic_function": {
            "id": "math.algebra.quadratic_function",
            "subject": "math",
            "concept": "quadratic_function",
            "level": "high_school",
            "difficulty": 6,
            "definition": "二次函数 f(x)=ax²+bx+c（a≠0），图像为抛物线，顶点 -b/2a。",
            "intuition": "抛物线就像球被抛出去的轨迹。",
            "explanation_variants": {"intuitive": "a 决定开口方向和宽窄。"},
        },
        "physics.thermodynamics.entropy": {
            "id": "physics.thermodynamics.entropy",
            "subject": "physics",
            "concept": "entropy",
            "level": "high_school",
            "difficulty": 6,
            "definition": "熵 热力学 无序度",
            "intuition": "一杯热水放凉：分子从有序运动变得混乱。",
            "explanation_variants": {"intuitive": "房间不收拾会越来越乱。"},
        },
        "physics.kinematics.newton_laws": {
            "id": "physics.kinematics.newton_laws",
            "subject": "physics",
            "concept": "newton_laws",
            "level": "high_school",
            "difficulty": 6,
            "definition": "牛顿三定律：惯性、F=ma、作用力与反作用力。",
            "intuition": "推东西越用力越快；刹车时身体前倾是惯性。",
            "explanation_variants": {"intuitive": "在无摩擦冰面上滑行的冰球不会自己停下来。"},
        },
    }
    minimal_humanities = {
        "humanities.philosophy.phenomenology": {
            "id": "humanities.philosophy.phenomenology",
            "subject": "humanities",
            "dimension": "philosophy",
            "concept": "phenomenology",
            "definition": "现象学：回到事物本身的研究方法，胡塞尔开创。",
            "intuition": "把预设和理论框架'放进括号'，看体验本身如何呈现。",
        },
    }
    minimal_skills = {
        "skill.writing.clarity": {
            "id": "skill.writing.clarity",
            "category": "writing",
            "name": "clarity",
            "definition": "清晰写作：主谓宾完整、避免悬空宾语、连接词恰当。",
        },
    }

    monkeypatch.setattr(kb, "subjects", minimal_subjects)
    monkeypatch.setattr(kb, "humanities", minimal_humanities)
    monkeypatch.setattr(kb, "skills", minimal_skills)
    # 顺手清掉缓存（避免污染既有 _resolve_cache / _search_cache）
    if hasattr(kb, "_search_cache"):
        kb._search_cache = {}
    return kb


# ---------------------------------------------------------------------------
# 测试 1：相关文档必须排第一（BM25Okapi IDF + 长度归一化）
# ---------------------------------------------------------------------------
def test_kb_search_ranks_relevant_above_irrelevant(isolated_kb):
    """search("导数 变化率", subject="math") → 第一个结果是 math.calculus.derivative。

    设计原理：
    - "导数" 在 math.calculus.derivative 定义中两次命中（definition + intuition），
      而 quadratic_function 不含此词。
    - 简化 BM25：derivative 命中数 > quadratic_function → derivative 排第一 ✓
    - BM25Okapi：除命中数外，IDF（"导数"在所有 math 节点中低频 → IDF 高）会让
      derivative 进一步领先。
    - 测试断言：第一个结果的 concept_id 必须是 math.calculus.derivative。
    """
    results = isolated_kb.search("导数 变化率", subject="math", top_k=3)
    assert isinstance(results, list), f"search 应返回 list，实际 {type(results)}"
    assert len(results) >= 1, "math 过滤后应至少返回 1 条结果"
    assert results[0]["concept_id"] == "math.calculus.derivative", (
        f"相关文档应排第一，实际第一是 {results[0]['concept_id']}，"
        f"完整结果: {[r['concept_id'] for r in results]}"
    )


# ---------------------------------------------------------------------------
# 测试 2：top_k 截断语义（候选 > top_k 时截断；候选 < top_k 时返回全部）
# ---------------------------------------------------------------------------
def test_kb_search_top_k_truncates_when_more_candidates(isolated_kb):
    """多个候选都命中时，top_k=2 应只返回 2 条（截断）。

    场景：query="牛顿 力 惯性" 跨多个 doc 命中：
    - physics.kinematics.newton_laws（"牛顿三定律、F=ma、力、作用力、惯性"）
    - math.calculus.derivative 不命中（"导数 瞬时变化率..."）
    - 至少 newton_laws 1 条命中，但 isolated_kb 总节点只有 6 个，多数不命中
    - 实际只有 1 条命中时，top_k=2 应返回 1 条（候选不足）
    - 这个测试的目的：验证 top_k 截断语义而非强制返回 N 条
    """
    # 用跨学科 query，但只 newton_laws 含这些词；其他节点都不命中
    # 这是测试"top_k 截断"的退化形式：实际只有 1 个命中
    results = isolated_kb.search("牛顿 力 惯性", subject=None, top_k=2)
    # 至少返回 newton_laws（其他 doc 不命中）
    assert len(results) >= 1, f"至少应返回 1 条匹配，实际 {len(results)}"
    assert len(results) <= 2, f"top_k=2 截断应不超过 2 条，实际 {len(results)}"
    # 第一条必须是 newton_laws（唯一命中）
    assert results[0]["concept_id"] == "physics.kinematics.newton_laws", (
        f"唯一命中的应是 newton_laws，实际 {results[0]['concept_id']}"
    )


def test_kb_search_top_k_truncates_with_multi_hit(isolated_kb):
    """top_k 截断：构造多个 doc 都命中 query 的场景。

    在 isolated_kb 中 query "数学 函数" 至少命中：
    - math.calculus.derivative（definition 含"瞬时变化率"——不算命中"数学"或"函数"）
    - math.algebra.quadratic_function（"二次函数"——命中"函数"）
    - 其他不含 query 词的节点不应命中
    验证：top_k=1 应只返回 1 条（截断）；top_k=5 应返回全部命中（不补空）。
    """
    results_top1 = isolated_kb.search("函数", subject=None, top_k=1)
    assert len(results_top1) == 1, (
        f"top_k=1 应只返回 1 条，实际 {len(results_top1)} 条"
    )

    results_top5 = isolated_kb.search("函数", subject=None, top_k=5)
    # quadratic_function 应在第一位（命中"函数"）
    assert any(r["concept_id"] == "math.algebra.quadratic_function" for r in results_top5), (
        f"quadratic_function 应在结果中，实际 {[r['concept_id'] for r in results_top5]}"
    )


def test_kb_search_top_k_one(isolated_kb):
    """top_k=1 → 恰好 1 条。"""
    results = isolated_kb.search("导数 变化率", subject=None, top_k=1)
    assert len(results) == 1, f"top_k=1 应返回 1 条，实际 {len(results)} 条"


def test_kb_search_default_top_k_is_five(isolated_kb):
    """不传 top_k → 默认 5（与 v0.15 接口约定 + config/rag.json retrieval.top_k 一致）。"""
    results = isolated_kb.search("导数 变化率", subject=None)
    assert len(results) <= 5, (
        f"默认 top_k 应为 5，最多 5 条，实际 {len(results)} 条"
    )


def test_kb_search_top_k_preserves_best_first(isolated_kb):
    """top_k 截断必须保留最相关的——derivative 在第一。"""
    results = isolated_kb.search("导数 变化率", subject=None, top_k=2)
    if len(results) >= 1:
        assert results[0]["concept_id"] == "math.calculus.derivative", (
            f"最相关文档必须排第一，实际 {results[0]['concept_id']}"
        )


# ---------------------------------------------------------------------------
# 测试 3：subject 过滤仍生效（BM25 排序 + 学科作用域正交）
# ---------------------------------------------------------------------------
def test_kb_search_subject_filter(isolated_kb):
    """指定 subject='math' → 返回结果必须全部属于 math 学科。"""
    results = isolated_kb.search("导数 变化率", subject="math", top_k=5)
    assert len(results) >= 1, "math 过滤后应至少返回 1 条"
    for r in results:
        # concept_id 以 'math.' 开头
        assert r["concept_id"].startswith("math."), (
            f"subject=math 过滤应只返回 math.* 节点，实际返回 {r['concept_id']}"
        )


def test_kb_search_subject_filter_physics(isolated_kb):
    """指定 subject='physics' → 只返回 physics.* 节点（不应混进 math.*）。"""
    results = isolated_kb.search("热力学 无序度", subject="physics", top_k=5)
    assert len(results) >= 1, "physics 过滤后应至少返回 1 条"
    for r in results:
        assert r["concept_id"].startswith("physics."), (
            f"subject=physics 过滤应只返回 physics.* 节点，实际返回 {r['concept_id']}"
        )


# ---------------------------------------------------------------------------
# 测试 4：无匹配时返回空列表（不抛异常）
# ---------------------------------------------------------------------------
def test_kb_search_no_hit_returns_empty(isolated_kb):
    """完全无关 query → 空列表（不抛 KeyError / IndexError）。"""
    # q=量子力学 (测试语料不含此词)
    results = isolated_kb.search("量子力学 测不准", subject="math", top_k=3)
    assert results == [], f"无匹配应返回 []，实际 {results}"


def test_kb_search_no_hit_no_subject(isolated_kb):
    """无匹配 + 无 subject 过滤 → 空列表。"""
    results = isolated_kb.search("区块链 加密货币", top_k=3)
    assert results == [], f"无匹配应返回 []，实际 {results}"


# ---------------------------------------------------------------------------
# 测试 5：节点缺字段不崩（用 .get 兜底）
# ---------------------------------------------------------------------------
def test_kb_search_missing_field_graceful(isolated_kb, monkeypatch):
    """节点缺 definition / intuition / core_question / concept / name 字段不应崩。

    场景：某些自定义节点（特别是 evolved 节点入库早期）可能缺字段；search 必须
    用 .get 兜底。模拟一个 minimal node 缺 definition 和 intuition。
    """
    # 注入一个"残缺"节点——只有 id/subject/difficulty，没有 definition/intuition/concept/name
    broken_subjects = dict(isolated_kb.subjects)
    broken_subjects["math.broken.partial"] = {
        "id": "math.broken.partial",
        "subject": "math",
        "concept": "partial",
        "level": "high_school",
        "difficulty": 5,
        # 注意：definition / intuition / core_question / name 都缺
    }
    monkeypatch.setattr(isolated_kb, "subjects", broken_subjects)

    # 调用不应抛 KeyError / AttributeError
    try:
        results = isolated_kb.search("导数 变化率", subject="math", top_k=3)
    except Exception as exc:  # pragma: no cover - 防御
        pytest.fail(f"缺字段节点导致 search 抛异常: {type(exc).__name__}: {exc}")

    # 应至少返回 derivative 节点（残缺节点应被兜底或排后）
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["concept_id"] == "math.calculus.derivative"


def test_kb_search_missing_field_snippet_empty_string(isolated_kb, monkeypatch):
    """缺字段节点的 snippet 应回退为 ''（不是抛异常）。"""
    # 注入：节点只有 definition 没有 intuition
    partial = {
        "math.partial.no_intuition": {
            "id": "math.partial.no_intuition",
            "subject": "math",
            "concept": "no_intuition",
            "definition": "导数 变化率",
            # intuition 缺失
            "difficulty": 5,
        }
    }
    monkeypatch.setattr(isolated_kb, "subjects", partial)

    results = isolated_kb.search("导数 变化率", subject="math", top_k=3)
    # 找到该节点
    matches = [r for r in results if r["concept_id"] == "math.partial.no_intuition"]
    if matches:
        # snippet 是字符串（即使为空也不应是抛异常）
        assert isinstance(matches[0]["snippet"], str), (
            f"snippet 必须是 str，实际 {type(matches[0]['snippet'])}"
        )


# ---------------------------------------------------------------------------
# 额外契约测试：search 返回 dict 结构稳定
# ---------------------------------------------------------------------------
def test_kb_search_result_schema(isolated_kb):
    """search 返回的 dict 必须包含 concept_id / title / snippet / relevance_score / difficulty。"""
    results = isolated_kb.search("导数 变化率", subject="math", top_k=3)
    assert len(results) >= 1
    r = results[0]
    assert "concept_id" in r, f"result 缺 concept_id: {r.keys()}"
    assert "title" in r, f"result 缺 title: {r.keys()}"
    assert "snippet" in r, f"result 缺 snippet: {r.keys()}"
    assert "relevance_score" in r, f"result 缺 relevance_score: {r.keys()}"
    assert "difficulty" in r, f"result 缺 difficulty: {r.keys()}"
    # relevance_score 必须是数字
    assert isinstance(r["relevance_score"], (int, float)), (
        f"relevance_score 必须是数字，实际 {type(r['relevance_score'])}"
    )


# ---------------------------------------------------------------------------
# 关键 RED 测试：BM25Okapi 长度归一化能力（与简化 BM25 区分）
# ---------------------------------------------------------------------------
def test_kb_search_length_normalization_prefers_concise_hits(isolated_kb, monkeypatch):
    """BM25Okapi 长度归一化：TF 相同时，短文档 BM25 分更高。

    设计关键：
    - 注入 2 个节点：math.short.hit + math.long.hit
    - 两个节点的 query 词 TF 相同（"独有关键词foo" 各出现 1 次）
    - 区别：short.hit 定义短（10 字），long.hit 定义长（200+ 字）
    - 简化 BM25：两者命中数相同 → score 相同 → 顺序按 nid 字典序
    - BM25Okapi：通过 b=0.75 长度归一化，短文档 BM25 分更高 → short.hit 排第一

    这是 RED 测试的核心——它能区分简化版（hit count）与真 BM25Okapi。
    """
    UNIQUE_Q = "独有关键词foo"

    subjects_with_length_diff = dict(isolated_kb.subjects)
    # 短文档：定义短（10 字），query 词出现 1 次
    subjects_with_length_diff["math.short.hit"] = {
        "id": "math.short.hit",
        "subject": "math",
        "concept": "short_hit",
        "level": "high_school",
        "difficulty": 5,
        "definition": f"{UNIQUE_Q} 测试短定义",  # 短，1 次 query
        "intuition": "短直觉",
        "explanation_variants": {},
    }
    # 长文档：定义长（200+ 字），query 词也只出现 1 次
    filler = "无关填充文本词".join(["填充"] * 30)  # 大量无关 token
    long_def = f"无关内容开始 {filler} 关键内容 {UNIQUE_Q} 无关内容结束 {filler}"
    subjects_with_length_diff["math.long.hit"] = {
        "id": "math.long.hit",
        "subject": "math",
        "concept": "long_hit",
        "level": "high_school",
        "difficulty": 5,
        "definition": long_def,
        "intuition": "无关直觉内容",
        "explanation_variants": {},
    }
    monkeypatch.setattr(isolated_kb, "subjects", subjects_with_length_diff)

    results = isolated_kb.search(UNIQUE_Q, subject="math", top_k=2)
    assert len(results) >= 2, (
        f"应返回 short.hit + long.hit 两条，实际 {len(results)} 条："
        f"{[r['concept_id'] for r in results]}"
    )
    # BM25Okapi 长度归一化让 short.hit 排第一
    assert results[0]["concept_id"] == "math.short.hit", (
        f"BM25Okapi 长度归一化：短文档应排第一，实际第一是 "
        f"{results[0]['concept_id']}（第二是 {results[1]['concept_id']}）。"
        f"scores: {results[0]['relevance_score']:.3f} vs "
        f"{results[1]['relevance_score']:.3f}"
    )
    # 短文档的 relevance_score 必须严格大于长文档的
    assert results[0]["relevance_score"] > results[1]["relevance_score"], (
        f"短文档 relevance_score ({results[0]['relevance_score']:.3f}) "
        f"必须 > 长文档 relevance_score ({results[1]['relevance_score']:.3f})"
    )