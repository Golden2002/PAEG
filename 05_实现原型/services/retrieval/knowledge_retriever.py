# -*- coding: utf-8 -*-
"""
PAEG 教育智能体 — KnowledgeRetriever 多路召回模块（A4 · Oracle RAG 优化项 #6）

职责：
- 把 B2 真 BM25Okapi（knowledge_base.search） + tag 匹配两条通道的结果用
  RRF(k=60) 融合（B1 retrieval.rrf_k 控制；与 web_search_tool.web_search_multi
  对齐：k=60 是项目内 RAG 惯例）
- 排除 status="superseded" 节点（A2 supersession 机制）
- 预留 semantic 通道接口（B8 embedding 接入点；当前 ``semantic.enabled=False``，
  通道整体跳过、不调用 embedding）
- 跨通道去重（同一 concept_id 只保留最高融合分；sources 字段记录所有命中通道）

设计要点
--------
1. **节点是 dict 而非 ORM**：本模块不直接读 KB / self_evolution 持久层，而是
   接受 ``nodes: dict``（{concept_id: node}）。生产路径 ``from_evolved_and_kb``
   会自动聚合：self_evolution 当日 ``evolved_*.json``（live 节点） + KB 三 dict
   （subjects / humanities / skills）。测试 / 一次性脚本可直接 ``KnowledgeRetriever(nodes=...)``
   注入迷你数据。
2. **BM25 通道**：复用 ``lib.ingest.retriever._tokenize`` + ``rank_bm25.BM25Okapi``；
   节点文本 = id + concept + definition + intuition + tags 拼接（与
   knowledge_base._node_text 思路一致，但额外把 tags 文本也算入 BM25 索引——
   让 tag 命中与文本命中同台竞争 RRF 分数）。
3. **tag 通道**：jieba 切 query → 对每节点计算 Jaccard 系数
   ``|q_tokens ∩ node_tags| / |q_tokens ∪ node_tags|``；0 命中排除。tag 通道
   是 BM25 的正交补——尤其在 query 极短（1-2 词）BM25 IDF 不稳时，tag 通道
   通过"主题命中"保证召回。
4. **semantic 通道（预留）**：当且仅当 ``config["semantic"]["enabled"] is True``
   时才调用 ``self._semantic_channel(query, nodes)``。当前实现返回 ``[]``；
   接入点在 docstring 标注（B8）。
5. **RRF 融合**：``score = Σ 1/(k + rank)``（k=config["retrieval"]["rrf_k"]，
   默认 60）。同一 concept_id 跨通道命中 → 累加 RRF 分并 union sources。
6. **排除 superseded**：在 build 阶段就过滤掉 ``status == "superseded"`` 的节点
   （避免后续通道再次处理它们）。未设置 status 的节点视为 live（兼容旧节点）。

依赖
----
- rank_bm25（已有；项目 requirements.txt）
- jieba（已有）
- services.rag_config.get_rag_config（已有）
- lib.ingest.retriever._tokenize（已有，含 jieba 自定义词典）
"""
from __future__ import annotations

import glob
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from services.rag_config import get_rag_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 模块内兜底常量（config 完全不可用时的最后防线——理论上 get_rag_config 永不抛，
# 但 defensive 编程以防万一）
# ---------------------------------------------------------------------------
_FALLBACK_RRF_K: int = 60
_FALLBACK_TOP_K: int = 5


# ---------------------------------------------------------------------------
# 工具：安全分词（与 lib.ingest.retriever._tokenize 对齐，便于对接）
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> List[str]:
    """使用 jieba 分词并过滤纯标点/空白。

    与 ``lib.ingest.retriever._tokenize`` 行为一致：若 jieba 不可用退化为按字
    符切分。模块级 import 该工具时会触发 ``ensure_custom_dict()``（lib.ingest
    模块导入副作用），自动把 80+ 教育术语注册到 jieba。
    """
    from lib.ingest.retriever import _tokenize as _ingest_tokenize

    return _ingest_tokenize(text)


def _safe_get_text(node: Dict[str, Any], *keys: str, default: str = "") -> str:
    """从节点 dict 读文本字段（多个候选 key，缺一个就试下一个；非 str 强转）。"""
    for k in keys:
        v = node.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            return v
        return str(v)
    return default


# ---------------------------------------------------------------------------
# 节点文本拼接（BM25 索引语料）
# ---------------------------------------------------------------------------
def _node_corpus_text(nid: str, node: Dict[str, Any]) -> str:
    """把节点关键字段拼成一段可索引文本，供 BM25 索引。

    字段顺序（按对 BM25 贡献的经验权重）：
    - id（节点唯一标识，BM25 命中权重高）
    - concept / name（核心概念，标题级）
    - definition（精确定义）
    - intuition（直觉解释，常含通俗比喻）
    - tags（主题标签——同时是 BM25 文本来源与 tag 通道独立索引源）
    - core_question（人文节点）
    - category / subject（学科背景）

    缺字段自动以空串兜底（不崩）。
    """
    tags_text = " ".join(str(t) for t in (node.get("tags") or []) if t)
    parts: List[str] = [
        nid,
        _safe_get_text(node, "concept", "name", "title"),
        _safe_get_text(node, "definition"),
        _safe_get_text(node, "intuition"),
        _safe_get_text(node, "core_question"),
        tags_text,
        _safe_get_text(node, "subject", "dimension", "category"),
    ]
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# KnowledgeRetriever 主体
# ---------------------------------------------------------------------------
class KnowledgeRetriever:
    """多路召回检索器：BM25（主）+ tag（正交补）+ semantic（预留），RRF 融合。

    Examples
    --------
    >>> nodes = {
    ...     "math.calculus.derivative": {
    ...         "id": "math.calculus.derivative",
    ...         "concept": "导数",
    ...         "definition": "导数是函数在某一点的瞬时变化率。",
    ...         "tags": ["数学", "微积分"],
    ...     },
    ... }
    >>> retriever = KnowledgeRetriever(nodes=nodes)
    >>> retriever.recall("导数", top_k=3)
    [{'concept_id': 'math.calculus.derivative', 'title': 'math.calculus.derivative',
      'snippet': '导数是函数在某一点的瞬时变化率。',
      'relevance_score': 0.01639, 'sources': ['bm25', 'tag']}]
    """

    def __init__(
        self,
        nodes: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """构造检索器。

        Parameters
        ----------
        nodes : dict, optional
            ``{concept_id: node_dict}``。缺省走 :meth:`from_evolved_and_kb`
            聚合（self_evolution 当日 evolved_*.json + KB 三 dict）。
            节点缺 status 视为 live；status="superseded" 一律过滤。
        config : dict, optional
            RAG 配置（``get_rag_config()`` 返回结构）。缺省走
            :func:`get_rag_config` 单例读取（带缓存）。
        """
        if nodes is None:
            nodes = self.from_evolved_and_kb()
        if config is None:
            try:
                config = get_rag_config()
            except Exception:  # pragma: no cover - 防御性兜底
                config = {}
        self._raw_nodes: Dict[str, Any] = dict(nodes)
        self._config: Dict[str, Any] = config
        # 过滤 superseded（在 build 阶段就剔除，下游通道无需再判断）
        self._nodes: Dict[str, Any] = {
            nid: n
            for nid, n in self._raw_nodes.items()
            if not self._is_superseded(n)
        }
        # 懒构建 BM25 索引（首次 recall 时再 build；此处仅记录 dirty flag）
        self._bm25_cache = None  # type: ignore[var-annotated]
        self._bm25_ids: List[str] = []

    # ------------------------------------------------------------------
    # 静态 / 类方法：从 self_evolution + KB 聚合节点
    # ------------------------------------------------------------------
    @staticmethod
    def from_evolved_and_kb() -> Dict[str, Any]:
        """聚合节点源：self_evolution 当日 ``evolved_*.json``（live 节点） + KB 三 dict。

        来源优先级（后写覆盖先写，符合"自进化节点优先"直觉）：
        1. ``Library/KnowledgeBase/subjects/evolved_*.json``（所有日期文件合并，
           同一 nid 后写覆盖先写——与 self_evolution 当日文件语义对齐）
        2. ``knowledge_base.KnowledgeBase.subjects``（学科节点）
        3. ``knowledge_base.KnowledgeBase.humanities``（人文节点）
        4. ``knowledge_base.KnowledgeBase.skills``（技能节点）

        返回 ``{nid: node}``。任一来源不可用（文件缺失 / KB import 失败）都
        不抛异常——只把可用的源加进来，让检索器至少有"一部分"数据可用。

        排除规则：status="superseded" 一律不返回。
        """
        out: Dict[str, Any] = {}

        # 1) evolved_*.json（自进化节点库）
        try:
            from self_evolution import SelfEvolution  # 延迟 import，避免循环依赖

            se = SelfEvolution(llm=None, verbose=False)
            evolved_dir = se.evolved_dir
        except Exception:
            # 退化路径：直接用相对路径定位（仅用于子目录跑测试场景）
            evolved_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "Library",
                "KnowledgeBase",
                "subjects",
            )

        if os.path.isdir(evolved_dir):
            for fpath in sorted(glob.glob(os.path.join(evolved_dir, "evolved_*.json"))):
                try:
                    with open(fpath, encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as exc:  # pragma: no cover - 单文件坏不连累整体
                    logger.debug("evolved 文件读失败（%s）：%s", fpath, exc)
                    continue
                if not isinstance(data, dict):
                    continue
                for nid, node in data.items():
                    if not isinstance(node, dict):
                        continue
                    if node.get("status") == "superseded":
                        continue
                    out[nid] = node

        # 2-4) KB 三 dict
        try:
            from knowledge_base import KnowledgeBase

            kb = KnowledgeBase()
        except Exception as exc:  # pragma: no cover - KB 不可用兜底
            logger.debug("KnowledgeBase 初始化失败（%s），跳过 KB 来源", exc)
            return out

        for attr in ("subjects", "humanities", "skills"):
            sub = getattr(kb, attr, None)
            if not isinstance(sub, dict):
                continue
            for nid, node in sub.items():
                if not isinstance(node, dict):
                    continue
                if node.get("status") == "superseded":
                    continue
                # evolved 已有的 nid 不被 KB 覆盖（自进化优先）
                out.setdefault(nid, node)

        return out

    @staticmethod
    def _is_superseded(node: Dict[str, Any]) -> bool:
        """判断节点是否被 A2 supersession 机制标记为废弃。"""
        if not isinstance(node, dict):
            return False
        return str(node.get("status", "")).strip().lower() == "superseded"

    # ------------------------------------------------------------------
    # BM25 通道
    # ------------------------------------------------------------------
    def _build_bm25_index(self) -> None:
        """懒构建 BM25 索引（每个实例一次；rank_bm25 / jieba 不可用时降级 KeywordTF）。"""
        if self._bm25_cache is not None:
            return

        ids = list(self._nodes.keys())
        corpus_texts = [_node_corpus_text(nid, self._nodes[nid]) for nid in ids]
        tokenized = [_tokenize(t) for t in corpus_texts]

        try:
            from rank_bm25 import BM25Okapi  # type: ignore

            try:
                cfg = self._config.get("retrieval", {}) or {}
                k1 = float(cfg.get("bm25_k1", 1.5))
                b = float(cfg.get("bm25_b", 0.75))
            except Exception:  # pragma: no cover
                k1, b = 1.5, 0.75

            # 小语料库 padding（与 knowledge_base.search 对齐，避 IDF=0）
            if 0 < len(tokenized) < 5:
                _PAD = (
                    "雨伞 雨鞋 雨衣 工具 锤子 钉子",
                    "音乐 钢琴 吉他 音符 旋律",
                    "水果 苹果 香蕉 西瓜 葡萄 樱桃",
                    "运动 篮球 足球 跑步 游泳 比赛",
                    "电影 导演 演员 剧本 摄影 观众",
                )
                while len(tokenized) < 5:
                    tokenized.append(_tokenize(_PAD[len(tokenized) % len(_PAD)]))

            self._bm25_cache = BM25Okapi(tokenized, k1=k1, b=b)
            self._bm25_ids = ids
        except Exception as exc:
            logger.warning("BM25 索引构建失败，降级为 TF 词频：%s", exc)
            # 降级：仅存 tokenized + ids，_bm25_channel 用 TF 公式
            self._bm25_cache = ("keyword", tokenized)
            self._bm25_ids = ids

    def _bm25_channel(self, query: str) -> List[Tuple[str, float]]:
        """BM25 通道：返回 ``[(concept_id, score), ...]``，按 score 降序。

        降级路径：当 rank_bm25 / jieba 不可用时（self._bm25_cache = ("keyword",
        tokenized)），用对数 TF + 长度归一化作为降级。
        """
        if not self._nodes:
            return []
        self._build_bm25_index()
        if not self._bm25_ids:
            return []

        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        cache = self._bm25_cache
        scores: List[float]

        if isinstance(cache, tuple) and cache and cache[0] == "keyword":
            # 降级：TF + 长度归一
            tokenized = cache[1]
            scores = [0.0] * len(self._bm25_ids)
            for i, tf_map in enumerate(tokenized):
                doc_len = max(1, len(tf_map))
                s = 0.0
                for t in q_tokens:
                    if t in tf_map:
                        s += 1.0 + (tf_map.count(t) ** 0.5)
                scores[i] = s / (doc_len ** 0.5)
        else:
            # 真 BM25
            try:
                all_scores = cache.get_scores(q_tokens)
            except Exception as exc:  # pragma: no cover - 防御性
                logger.debug("BM25 get_scores 失败：%s", exc)
                return []
            scores = list(all_scores[: len(self._bm25_ids)])

        # 排序（同分按 nid 升序稳定）
        indexed = sorted(
            range(len(scores)),
            key=lambda i: (-float(scores[i]), self._bm25_ids[i]),
        )
        out: List[Tuple[str, float]] = []
        for idx in indexed:
            sc = float(scores[idx])
            if sc <= 0:
                continue  # 完全无命中 → 丢弃
            out.append((self._bm25_ids[idx], sc))
        return out

    # ------------------------------------------------------------------
    # Tag 通道
    # ------------------------------------------------------------------
    def _tag_channel(self, query: str) -> List[Tuple[str, float]]:
        """Tag 匹配通道：query tokens 与节点 tags 计算 Jaccard 系数排序。

        评分公式：``Jaccard = |q_tokens ∩ node_tags| / |q_tokens ∪ node_tags|``。
        节点缺 tags 或交集为空 → 排除。

        返回 ``[(concept_id, score), ...]`` 按 score 降序。
        """
        if not self._nodes:
            return []
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return []

        scored: List[Tuple[str, float]] = []
        for nid, node in self._nodes.items():
            raw_tags = node.get("tags") or []
            if not raw_tags:
                continue
            # tag 文本也走 jieba 切，保证与 query 同一分词空间
            tag_tokens: set = set()
            for t in raw_tags:
                if not t:
                    continue
                for tok in _tokenize(str(t)):
                    tag_tokens.add(tok)
            if not tag_tokens:
                continue
            inter = q_tokens & tag_tokens
            if not inter:
                continue
            union = q_tokens | tag_tokens
            score = len(inter) / max(1, len(union))
            scored.append((nid, float(score)))

        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored

    # ------------------------------------------------------------------
    # Semantic 通道（预留，B8 embedding 接入点）
    # ------------------------------------------------------------------
    def _semantic_channel(self, query: str, nodes: Dict[str, Any]) -> List[Tuple[str, float]]:
        """Semantic 通道（**预留接口，当前 disabled**）。

        B8 接入点：将本方法替换为真实 embedding 相似度计算
        （如 sentence-transformers / openai embeddings / 国产 BGE 等）。当前
        实现仅返回空列表，确保 ``semantic.enabled=False`` 时绝不调用本方法
        （由 :meth:`recall` 的 guard 控制）。

        Parameters
        ----------
        query : str
            用户原始 query。
        nodes : dict
            ``{concept_id: node}``，已过滤 superseded。

        Returns
        -------
        list of (concept_id, score) tuples
            按 score 降序。空列表 → 本通道不参与 RRF。
        """
        # B8 接入：此处替换为 embedding 模型调用（cosine 相似度归一到 [0,1]）
        # 当前实现：占位（永远返回 []）。若意外被调用，至少在 logger 留痕。
        logger.debug(
            "_semantic_channel 被调用（B8 未接入，当前返回空列表）；"
            "query=%r nodes=%d",
            query[:50],
            len(nodes),
        )
        return []

    # ------------------------------------------------------------------
    # RRF 融合
    # ------------------------------------------------------------------
    @staticmethod
    def _rrf_fuse(
        channels: List[Tuple[str, List[Tuple[str, float]]]],
        rrf_k: int,
    ) -> List[Tuple[str, float, List[str]]]:
        """RRF 融合：跨通道累加 ``1/(k + rank)``，返回按融合分降序的 ``(nid, score, sources)`` 列表。

        Parameters
        ----------
        channels : list of (channel_name, ranked_results)
            每个通道的排序结果 ``[(nid, score), ...]``（已按 score 降序）；
            channel_name 用于 sources 字段（"bm25" / "tag" / "semantic"）。
        rrf_k : int
            RRF 平滑参数（默认 60，与 web_search_tool 对齐）。

        Returns
        -------
        list of (nid, fused_score, sources)
            sources 是去重保序的通道名列表（按 channels 出现顺序）。
        """
        fused: Dict[str, float] = {}
        sources: Dict[str, List[str]] = {}
        for channel_name, ranked in channels:
            for rank, (nid, _raw_score) in enumerate(ranked, start=1):
                fused[nid] = fused.get(nid, 0.0) + 1.0 / (rrf_k + rank)
                # 保序去重（首次出现的通道名在 sources 列表前部）
                lst = sources.setdefault(nid, [])
                if channel_name not in lst:
                    lst.append(channel_name)
        # 按融合分降序（同分按 nid 升序稳定）
        ordered = sorted(fused.items(), key=lambda x: (-x[1], x[0]))
        return [(nid, sc, sources.get(nid, [])) for nid, sc in ordered]

    # ------------------------------------------------------------------
    # 主入口：recall
    # ------------------------------------------------------------------
    def recall(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """多路召回：BM25 + tag [+ semantic] → RRF → top_k。

        Parameters
        ----------
        query : str
            用户查询（中文/英文混合）。
        top_k : int, default 5
            返回的最相关节点数（截断到恰好 top_k；候选不足时返回全部）。

        Returns
        -------
        list of dict
            按 ``relevance_score``（RRF 融合分）降序排列。每条 result 形如::

                {
                    "concept_id": str,           # 节点 id
                    "title": str,                # 显示标题（nid or concept）
                    "snippet": str,              # 短摘要（definition 截断 120 字）
                    "relevance_score": float,    # RRF 融合分
                    "sources": [str, ...],       # 命中的通道名列表（去重保序）
                }

            无任何命中或数据源为空 → 返回 ``[]``。
        """
        if not self._nodes:
            return []
        if not query or not query.strip():
            return []

        # 1) 读 config（兜底常量）
        try:
            retrieval_cfg = (self._config or {}).get("retrieval", {}) or {}
            rrf_k = int(retrieval_cfg.get("rrf_k", _FALLBACK_RRF_K))
        except Exception:  # pragma: no cover
            rrf_k = _FALLBACK_RRF_K
        try:
            semantic_enabled = bool(
                (self._config or {}).get("semantic", {}).get("enabled", False)
            )
        except Exception:  # pragma: no cover
            semantic_enabled = False

        # 2) 跑各通道
        bm25_results = self._bm25_channel(query)
        tag_results = self._tag_channel(query)
        semantic_results: List[Tuple[str, float]] = []

        channels: List[Tuple[str, List[Tuple[str, float]]]] = [
            ("bm25", bm25_results),
            ("tag", tag_results),
        ]
        if semantic_enabled:
            # B8 接入点：仅在显式开启时才调用 embedding 通道（避免无谓开销）
            try:
                semantic_results = self._semantic_channel(query, self._nodes) or []
            except Exception as exc:  # pragma: no cover - 通道失败不连累整体
                logger.warning("semantic 通道失败：%s", exc)
                semantic_results = []
            if semantic_results:
                channels.append(("semantic", semantic_results))

        # 3) RRF 融合
        fused = self._rrf_fuse(channels, rrf_k=rrf_k)
        if not fused:
            return []

        # 4) 截断到 top_k（≤0 视为 1，缺省回退）
        try:
            k = int(top_k)
        except Exception:
            k = _FALLBACK_TOP_K
        k = max(1, k)
        fused = fused[:k]

        # 5) 构造 result dict（含 concept_id / title / snippet / relevance_score / sources）
        results: List[Dict[str, Any]] = []
        for nid, fused_score, sources in fused:
            node = self._nodes.get(nid, {})
            title = (
                node.get("concept")
                or node.get("name")
                or node.get("title")
                or nid
            )
            snippet = (
                node.get("definition")
                or node.get("intuition")
                or node.get("core_question")
                or ""
            )
            if isinstance(snippet, str) and len(snippet) > 200:
                snippet = snippet[:200]
            results.append(
                {
                    "concept_id": nid,
                    "title": str(title),
                    "snippet": str(snippet),
                    "relevance_score": round(float(fused_score), 6),
                    "sources": list(sources),
                }
            )
        return results


__all__ = [
    "KnowledgeRetriever",
]
