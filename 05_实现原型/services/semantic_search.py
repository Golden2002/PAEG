# -*- coding: utf-8 -*-
"""services/semantic_search.py —— C3 语义检索（P0，§3.54）

借鉴来源：
source:  BGE (BAAI General Embedding) small-zh 模型 / sentence-transformers
repo:    https://github.com/FlagOpen/FlagEmbedding / huggingface.co/BAAI/bge-small-zh-v1.5
adapted: 渐进式架构——模型缺失时降级关键词匹配（BM25/jieba），模型就绪后升级向量检索
since:   PAEG v0.73 §3.54 C3

设计：
- index(docs)：索引文档（id + text）
- search(query)：检索 top-k（默认 5），返回 [{id, text, score}]
- 模型缺失（未下载 bge ONNX / 加载失败）→ 降级 jieba 关键词匹配（ratchet：能力可用，不抛异常）
- 模型就绪（data/models/bge-small-zh-v1.5/*.onnx）→ 向量余弦相似度
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi, BM25Plus


class SemanticSearch:
    """语义检索服务（渐进式：关键词基线 → 向量增强）。"""

    def __init__(self, model_dir: str = ""):
        self._docs: List[Dict[str, Any]] = []
        self._bm25: Optional[BM25Okapi] = None
        self._model = None
        self._tokenizer = None
        # 模型目录（默认 data/models/bge-small-zh-v1.5）
        base = os.path.dirname(os.path.abspath(__file__))
        self._model_dir = model_dir or os.path.join(base, "..", "data", "models", "bge-small-zh-v1.5")
        self._try_load_model()

    def _try_load_model(self) -> bool:
        """尝试加载 BGE ONNX 模型（缺失/失败 → 保持 None，降级关键词）。"""
        try:
            import onnxruntime as ort
            model_path = os.path.join(self._model_dir, "model.onnx")
            tok_path = os.path.join(self._model_dir, "tokenizer.json")
            if not (os.path.isfile(model_path) and os.path.isfile(tok_path)):
                return False
            self._model = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            try:
                from tokenizers import Tokenizer  # type: ignore
                self._tokenizer = Tokenizer.from_file(tok_path)
            except Exception:
                self._tokenizer = None
            return True
        except Exception:
            return False

    def index(self, docs: List[Dict[str, Any]]) -> None:
        """索引文档（清空重建）。"""
        self._docs = list(docs)
        # 关键词基线（jieba 分词）——BM25Plus 解决 BM25Okapi 对低频词的零分问题
        try:
            import jieba  # type: ignore
            corpus = [list(jieba.cut(d.get("text", ""))) for d in docs]
        except Exception:
            corpus = [list(d.get("text", "")) for d in docs]
        self._bm25 = BM25Plus(corpus) if corpus else None

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索：向量优先，模型缺失降级关键词。"""
        if not self._docs:
            return []
        if self._model is not None:
            return self._vector_search(query, top_k)
        return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """关键词匹配（BM25 + jieba）。"""
        if self._bm25 is None:
            return []
        try:
            import jieba  # type: ignore
            tokens = list(jieba.cut(query))
        except Exception:
            tokens = list(query)
        scores = self._bm25.get_scores(tokens)
        # 按得分降序排（保留原索引），过滤 0 分
        ranked = sorted(((scores[i], i) for i in range(len(scores)) if scores[i] > 0),
                        key=lambda x: -x[0])
        out = []
        for score, i in ranked:
            out.append({**self._docs[i], "score": float(score)})
            if len(out) >= top_k:
                break
        return out

    def _vector_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """向量检索（ONNX 余弦相似度；tokenizer 缺失时降级关键词）。"""
        if self._tokenizer is None:
            return self._keyword_search(query, top_k)
        try:
            import numpy as np
            q_enc = self._encode(query)
            if q_enc is None:
                return self._keyword_search(query, top_k)
            results = []
            for doc in self._docs:
                d_enc = self._encode(doc.get("text", ""))
                if d_enc is None:
                    continue
                sim = float(np.dot(q_enc, d_enc) / (np.linalg.norm(q_enc) * np.linalg.norm(d_enc) + 1e-9))
                results.append({**doc, "score": sim})
            results.sort(key=lambda x: -x["score"])
            return results[:top_k]
        except Exception:
            return self._keyword_search(query, top_k)

    def _encode(self, text: str):
        """文本 → 向量（BGE 模型输入处理）。"""
        try:
            import numpy as np
            if self._tokenizer is None or self._model is None:
                return None
            enc = self._tokenizer.encode(text)
            input_ids = np.array([enc.ids], dtype=np.int64)
            attention = np.array([enc.attention_mask], dtype=np.int64)
            out = self._model.run(None, {"input_ids": input_ids, "attention_mask": attention})
            emb = np.asarray(out[0][0])
            return emb / (np.linalg.norm(emb) + 1e-9)
        except Exception:
            return None

    @property
    def model_ready(self) -> bool:
        """模型是否就绪（向量检索可用）。"""
        return self._model is not None and self._tokenizer is not None


__all__ = ["SemanticSearch"]
