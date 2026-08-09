# -*- coding: utf-8 -*-
"""
PAEG 教育智能体 — 检索器模块
=============================
提供基于 BM25（jieba 中文分词 + 自定义词典）的语义/关键词检索能力，
并在 rank_bm25 或 jieba 不可用时降级为纯 TF 词频匹配。

设计要点
--------
1. **自定义词典**：jieba 默认对教育/学术术语切分粗糙（"导数" → "导/数"），
   这里内置 50+ 教育/数学/物理/哲学/AI 术语，通过 ``jieba.add_word`` 注册，
   保证术语在分词阶段保持完整。
2. **BM25Retriever**：封装 ``rank_bm25.BM25Okapi``，支持 ``build`` / ``search``。
3. **KeywordRetriever**：纯 Python TF 词频匹配，作为不可用降级路径。
4. **make_retriever()**：工厂函数，优先尝试 BM25，失败回退 Keyword，并返回
   ``(retriever, mode_name)`` 让调用方知晓当前所处的检索模式。

依赖：``jieba``、``rank_bm25``（均为项目已装依赖；不可用时自动降级）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 自定义词典（教育 / 数学 / 物理 / 哲学 / AI 常用术语）
# ---------------------------------------------------------------------------
# 设计原则：
#   - 长词优先（先注册"瞬时变化率"再注册"导数"，避免短词把长词切碎）
#   - 频次 freq 给一个较高的值（~1e4），让 jieba 在 DAG 中倾向选该词
# ---------------------------------------------------------------------------
CUSTOM_TERMS: Tuple[str, ...] = (
    # —— 数学：微积分 ——
    "瞬时变化率", "瞬时速度", "切线斜率", "曲边梯形", "曲边三角形",
    "定积分", "不定积分", "二重积分", "三重积分", "曲线积分",
    "导函数", "原函数", "反函数", "复合函数", "初等函数",
    "导数", "积分", "极限", "微积分", "微分", "偏导", "全微分",
    "洛必达", "泰勒展开", "麦克劳林", "傅里叶",
    # —— 数学：代数 / 几何 ——
    "勾股定理", "余弦定理", "正弦定理", "三角函数", "反三角函数",
    "向量", "矩阵", "行列式", "特征值", "特征向量", "线性方程",
    "二次方程", "一元二次", "二元一次", "方程组", "不等式",
    "对数函数", "指数函数", "幂函数", "分段函数",
    "概率", "条件概率", "贝叶斯", "期望", "方差", "标准差", "正态分布",
    "排列组合", "二项式", "等差数列", "等比数列",
    "椭圆", "双曲线", "抛物线", "圆锥曲线",
    "球面", "立体几何", "解析几何",
    # —— 物理 ——
    "量子力学", "量子纠缠", "薛定谔", "波函数", "测不准原理",
    "相对论", "狭义相对论", "广义相对论", "时空弯曲", "光速不变",
    "热力学", "热力学第一定律", "热力学第二定律", "熵增", "熵",
    "电磁感应", "麦克斯韦方程", "光电效应", "牛顿第二定律",
    "动量守恒", "能量守恒", "万有引力", "加速度",
    "波粒二象性", "驻波", "多普勒效应",
    # —— 哲学 / 人文 ——
    "现象学", "存在主义", "实证主义", "实用主义", "结构主义",
    "后结构主义", "解构主义", "形而上学", "认识论", "本体论",
    "伦理学", "道德哲学", "政治哲学", "美学", "哲学",
    "苏格拉底", "柏拉图", "亚里士多德", "康德", "黑格尔",
    "尼采", "海德格尔", "萨特", "维特根斯坦", "罗素",
    "理性主义", "经验主义", "先验", "二律背反",
    # —— AI / 计算机 ——
    "人工智能", "机器学习", "深度学习", "神经网络", "卷积神经网络",
    "循环神经网络", "Transformer", "注意力", "自注意力", "多头注意力",
    "大语言模型", "预训练", "微调", "迁移学习", "强化学习",
    "梯度下降", "反向传播", "损失函数", "激活函数", "词嵌入",
    "向量数据库", "语义检索", "混合检索", "重排序",
    # —— 教育学术语 ——
    "认知负荷", "建构主义", "最近发展区", "支架式教学",
    "形成性评价", "终结性评价", "教学目标", "布鲁姆",
    "元认知", "工作记忆", "长时记忆", "图式",
)

# 保证长词先注册（短词若先注册，长词可能被错误切碎）
_SORTED_TERMS: Tuple[str, ...] = tuple(sorted(set(CUSTOM_TERMS), key=lambda x: -len(x)))


def ensure_custom_dict() -> int:
    """注册自定义词典到 jieba（幂等）。

    Returns
    -------
    int
        本次调用实际新注册（或刷新）的术语数量。
    """
    try:
        import jieba  # type: ignore
    except ImportError:
        logger.warning("jieba 未安装，跳过自定义词典注册")
        return 0

    registered = 0
    for term in _SORTED_TERMS:
        try:
            jieba.add_word(term, freq=10000, tag="n")
            registered += 1
        except Exception as exc:  # pragma: no cover - 防御性
            logger.debug("jieba.add_word(%s) 失败: %s", term, exc)
    logger.info("已注册 %d 个自定义术语到 jieba 词典", registered)
    return registered


# 模块导入时即注册（行为可预测，避免调用方忘记）
ensure_custom_dict()


# ---------------------------------------------------------------------------
# 工具：安全分词
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> List[str]:
    """使用 jieba 分词并过滤纯标点 / 空白。

    若 jieba 不可用，则退化为按字符切分（中文逐字），仍可被 BM25 索引。
    """
    text = (text or "").strip()
    if not text:
        return []
    try:
        import jieba  # type: ignore
        tokens = [t for t in jieba.lcut(text, cut_all=False) if t.strip()]
    except ImportError:
        # 退化：中文逐字 + 英文按空白拆
        tokens = [ch for ch in text if not ch.isspace()]
    # 过滤纯标点
    out: List[str] = []
    for tok in tokens:
        if any(ch.isalnum() for ch in tok):
            out.append(tok)
    return out


# ---------------------------------------------------------------------------
# BM25 检索器
# ---------------------------------------------------------------------------
class BM25Retriever:
    """基于 ``rank_bm25.BM25Okapi`` + jieba 的中文检索器。

    Examples
    --------
    >>> retriever = BM25Retriever()
    >>> retriever.build([
    ...     {"doc_name": "math.md", "chunk_index": 0, "text": "导数是函数在某一点的瞬时变化率"},
    ...     {"doc_name": "phy.md",  "chunk_index": 0, "text": "牛顿第二定律描述力与加速度的关系"},
    ... ])
    >>> retriever.search("导数怎么理解", top_k=2)
    [{'doc_name': 'math.md', 'chunk_index': 0, 'text': '...', 'score': ...}]
    """

    def __init__(self) -> None:
        self._bm25 = None  # type: ignore[var-annotated]
        self._docs: List[Dict[str, Any]] = []

    @property
    def mode(self) -> str:
        return "bm25"

    def build(self, docs: Sequence[Dict[str, Any]]) -> "BM25Retriever":
        """构建 BM25 索引。

        Parameters
        ----------
        docs : sequence of dict
            每个元素必须包含 ``doc_name``、``chunk_index``、``text`` 字段。
        """
        # 先确保词典已注册（防御幂等）
        ensure_custom_dict()

        from rank_bm25 import BM25Okapi  # type: ignore  # 本地导入，便于降级测试

        self._docs = list(docs)
        if not self._docs:
            # 空语料：构建空索引（search 时返回空）
            self._bm25 = BM25Okapi([[]])
            logger.warning("BM25Retriever.build 收到空文档列表")
            return self

        tokenized_corpus = [_tokenize(d.get("text", "")) for d in self._docs]
        self._bm25 = BM25Okapi(tokenized_corpus)
        logger.info(
            "BM25 索引构建完成：%d 个文档块，平均 token 数 %.1f",
            len(self._docs),
            sum(len(t) for t in tokenized_corpus) / max(1, len(tokenized_corpus)),
        )
        return self

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索 top-k 相关文档块。

        Parameters
        ----------
        query : str
            用户查询文本。
        top_k : int
            返回的最相关文档块数量。

        Returns
        -------
        list of dict
            每个 dict 形如 ``{doc_name, chunk_index, text, score}``，
            按 score 降序排列；若索引为空则返回空列表。
        """
        if self._bm25 is None or not self._docs:
            logger.warning("BM25 索引未构建或为空，search 返回 []")
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        # 取 top_k（按分数降序）
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        top = order[: max(1, int(top_k))]

        results: List[Dict[str, Any]] = []
        for idx in top:
            doc = self._docs[idx]
            results.append(
                {
                    "doc_name": doc.get("doc_name", ""),
                    "chunk_index": doc.get("chunk_index", idx),
                    "text": doc.get("text", ""),
                    "score": float(scores[idx]),
                }
            )
        return results


# ---------------------------------------------------------------------------
# TF 关键词降级检索器
# ---------------------------------------------------------------------------
class KeywordRetriever:
    """纯 TF 词频匹配降级检索器。

    当 ``rank_bm25`` 或 ``jieba`` 不可用时由 ``make_retriever`` 工厂返回。
    评分规则：``score = sum(tf_in_chunk[term]) for term in query_tokens``。
    """

    def __init__(self) -> None:
        self._docs: List[Dict[str, Any]] = []
        self._tf: List[Dict[str, int]] = []
        self._doc_lens: List[int] = []

    @property
    def mode(self) -> str:
        return "keyword"

    def build(self, docs: Sequence[Dict[str, Any]]) -> "KeywordRetriever":
        self._docs = list(docs)
        self._tf = []
        self._doc_lens = []
        for d in self._docs:
            tokens = _tokenize(d.get("text", ""))
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._tf.append(tf)
            self._doc_lens.append(max(1, len(tokens)))
        logger.info("Keyword 索引构建完成：%d 个文档块", len(self._docs))
        return self

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not self._docs:
            return []

        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        scores: List[float] = []
        for tf, dl in zip(self._tf, self._doc_lens):
            # 使用对数归一化 TF，避免长文档天然占优
            s = 0.0
            for t in q_tokens:
                if t in tf:
                    # 1 + log(tf) 是常见对数 TF 公式
                    s += 1.0 + (tf[t] ** 0.5)
            # 长度归一化（与 BM25 风格对齐，便于对比）
            scores.append(s / (dl ** 0.5))

        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        top = order[: max(1, int(top_k))]

        results: List[Dict[str, Any]] = []
        for idx in top:
            doc = self._docs[idx]
            results.append(
                {
                    "doc_name": doc.get("doc_name", ""),
                    "chunk_index": doc.get("chunk_index", idx),
                    "text": doc.get("text", ""),
                    "score": float(scores[idx]),
                }
            )
        return results


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------
def make_retriever(
    docs: Sequence[Dict[str, Any]], prefer: str = "bm25"
) -> Tuple[Any, str]:
    """构造检索器，优先 BM25，失败降级到 Keyword。

    Parameters
    ----------
    docs : sequence of dict
        文档块列表，元素含 ``doc_name`` / ``chunk_index`` / ``text``。
    prefer : str
        ``"bm25"`` 或 ``"keyword"``。当 prefer 为 ``"bm25"`` 但
        ``rank_bm25`` 不可用时自动降级到 ``"keyword"``；当 prefer 为
        ``"keyword"`` 时强制使用 KeywordRetriever。

    Returns
    -------
    (retriever, mode_name)
        ``mode_name`` 为 ``"bm25"`` 或 ``"keyword"``，供调用方记录 / 监控。
    """
    if prefer == "bm25":
        try:
            # 仅做一次导入试探，避免 build 失败导致上层崩溃
            from rank_bm25 import BM25Okapi  # noqa: F401  # type: ignore

            retriever: Any = BM25Retriever().build(docs)
            return retriever, "bm25"
        except ImportError as exc:
            logger.warning("rank_bm25 不可用，降级为 KeywordRetriever：%s", exc)
        except Exception as exc:  # pragma: no cover - 其他构建异常
            logger.exception("BM25Retriever 构建失败，降级为 KeywordRetriever: %s", exc)

    retriever = KeywordRetriever().build(docs)
    return retriever, "keyword"


__all__ = [
    "CUSTOM_TERMS",
    "ensure_custom_dict",
    "BM25Retriever",
    "KeywordRetriever",
    "make_retriever",
]