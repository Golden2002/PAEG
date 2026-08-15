"""
PAEG v0.5 知识库：4 类知识库（学科 / 素养 / 教学法 / 案例）。
覆盖高中 9 科 + 本科核心学科 + 人文素养 4 维度，30+ 学科节点。
v0.5 用内存存储；v1.0 替换为 PostgreSQL + 向量库。
"""
from __future__ import annotations

from typing import List, Optional

# §3.42 W12 ⭐ 接入 LRU+TTL 缓存（行为透明——返回节点 dict 或 None）
try:
    from infra.cache import LRUCache as _LRUCache
    _W12_CACHE_ENABLED = True
except Exception:  # noqa: BLE001 — infra.cache 不可用时回退到原始 dict 缓存
    _W12_CACHE_ENABLED = False
    _LRUCache = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# v0.42 ⭐ Oracle RAG 优化项 #2：search() 改用 BM25Okapi + jieba 真排序
# ---------------------------------------------------------------------------
# 复用 lib/ingest/retriever 的 jieba 自定义词典（80+ 教育/数学/物理/AI 术语）
# —— 这里只定义 fallback 词表，防止 lib/ingest 不可用时完全没词典可用。
_FALLBACK_JIEBA_TERMS = (
    "瞬时变化率", "切线斜率", "曲边梯形", "定积分", "不定积分", "导数", "积分", "极限",
    "微积分", "微分", "偏导", "全微分", "洛必达", "泰勒展开", "麦克劳林", "傅里叶",
    "勾股定理", "余弦定理", "正弦定理", "向量", "矩阵", "行列式", "特征值",
    "二次方程", "一元二次", "二元一次", "方程组", "对数函数", "指数函数", "幂函数",
    "概率", "条件概率", "贝叶斯", "期望", "方差", "标准差", "正态分布", "排列组合",
    "等差数列", "等比数列", "椭圆", "双曲线", "抛物线", "圆锥曲线", "球面",
    "量子力学", "量子纠缠", "薛定谔", "波函数", "相对论", "狭义相对论", "广义相对论",
    "时空弯曲", "光速不变", "热力学", "热力学第一定律", "热力学第二定律", "熵增", "熵",
    "电磁感应", "麦克斯韦方程", "光电效应", "牛顿第二定律", "动量守恒", "能量守恒",
    "万有引力", "加速度", "波粒二象性", "驻波", "多普勒效应", "现象学", "存在主义",
    "建构主义", "最近发展区", "支架式教学", "形成性评价", "终结性评价", "布鲁姆",
    "元认知", "工作记忆", "长时记忆", "图式",
)


def _ensure_kb_jieba_dict() -> bool:
    """确保 jieba 自定义词典已注册到 knowledge_base 上下文（幂等）。

    优先复用 lib/ingest/retriever.ensure_custom_dict()（80+ 术语）；
    不可用时退化用 _FALLBACK_JIEBA_TERMS。
    Returns True 表示已注册（成功或已存在）。
    """
    try:
        from lib.ingest.retriever import ensure_custom_dict  # type: ignore
        ensure_custom_dict()
        return True
    except Exception:
        pass
    # 退化：本地 fallback 词典
    try:
        import jieba  # type: ignore
        for term in sorted(set(_FALLBACK_JIEBA_TERMS), key=lambda x: -len(x)):
            try:
                jieba.add_word(term, freq=10000, tag="n")
            except Exception:
                pass
        return True
    except Exception:
        return False


# 模块加载时即注册一次（行为可预测，与 retriever 模块一致）
_ensure_kb_jieba_dict()


def _kb_tokenize(text: str) -> List[str]:
    """jieba 中文分词 + 过滤纯标点 / 空白（参考 lib/ingest/retriever._tokenize）。

    - 优先用 jieba.lcut（精确模式）。模块加载时已注册 80+ 教育/学术术语自定义
      词典——如"导数"/"瞬时变化率"/"熵"等术语不会被切碎。
    - jieba 不可用时退化：中文逐字 + 英文按字符，保留可索引性。
    - 过滤纯标点 / 空白 token。
    """
    text = (text or "").strip()
    if not text:
        return []
    try:
        import jieba  # type: ignore
        tokens = [t for t in jieba.lcut(text, cut_all=False) if t.strip()]
    except Exception:  # noqa: BLE001 — jieba 不可用时退化
        tokens = [ch for ch in text if not ch.isspace()]
    # 过滤纯标点 token（必须含至少一个 alnum 字符）
    out: List[str] = []
    for tok in tokens:
        if any(ch.isalnum() for ch in tok):
            out.append(tok)
    return out


def _kb_substring_fallback(
    query: str, candidates: list, subject: Optional[str], top_k: int
) -> list:
    """当 BM25Okapi / jieba 不可用或 query token 为空时的降级路径。

    简化为子串匹配计数（不依赖任何外部库），保证 search() 永不抛异常且返回
    schema 与真 BM25 路径完全一致。
    """
    q = (query or "").lower().strip()
    scored = []
    for nid, node in candidates:
        haystack = " ".join([
            nid,
            str(node.get("definition", "") or ""),
            str(node.get("intuition", "") or ""),
            str(node.get("core_question", "") or ""),
            str(node.get("concept", "") or ""),
            str(node.get("name", "") or ""),
        ]).lower()
        # 整句命中 +2；逐 token 命中 +1
        token_hits = sum(1 for tok in _kb_tokenize(query) if tok and tok.lower() in haystack)
        score = (2 if q and q in haystack else 0) + token_hits
        if score > 0:
            scored.append((score, nid, node))
    scored.sort(key=lambda x: (-x[0], x[1]))
    results = []
    for sc, nid, node in scored[: max(1, int(top_k))]:
        snippet = (node.get("definition") or node.get("core_question") or "")[:120]
        results.append({
            "concept_id": nid,
            "title": nid,
            "snippet": snippet,
            "relevance_score": float(sc),
            "difficulty": node.get("difficulty", 5),
        })
    return results


# 延迟导入：get_rag_config 在 search() 内调用，避免模块加载时强制读盘
def get_rag_config():
    """延迟导入 services.rag_config.get_rag_config（避免 knowledge_base 顶层 import）。"""
    try:
        from services.rag_config import get_rag_config as _grc
        return _grc()
    except Exception:  # noqa: BLE001 — 配置不可用兜底
        return {}


class KnowledgeBase:
    def __init__(self):
        self.subjects = {}     # 学科知识
        self.humanities = {}   # 素养知识
        self.strategies = {}   # 教学法
        self.cases = {}        # 案例
        self.skills = {}       # 技能（G4：编程/写作/思辨/问题解决/表达/学习法）
        self._load_demo_data()
        # v0.15：检索缓存（避免每次 Presenter 都重新 search）
        self._search_cache = {}
        # §3.42 W12 ⭐ resolve_node 缓存升级为 LRU+TTL（原 dict 缓存保留为兜底）
        # 容量 256 / TTL 300s；reload_all 时按 namespace 失效
        if _W12_CACHE_ENABLED:
            self._resolve_cache = _LRUCache(capacity=256, default_ttl=300.0,
                                              name="knowledge_base.resolve_node")
            # 注册到全局 CacheRegistry，让 config_hub.reload_all 能按 ns 失效
            try:
                from infra.cache import get_cache_registry as _gcr
                _gcr()._caches["knowledge_base.resolve_node"] = self._resolve_cache
            except Exception:  # noqa: BLE001 — 注册失败不影响本地缓存使用
                pass
        else:
            self._resolve_cache = {}

    # ------------------------------------------------------------------
    # v0.15：检索缓存 + §3.42 W12 LRU+TTL 升级
    # ------------------------------------------------------------------
    def resolve_node(self, concept: str, subject: str = None):
        """解析概念对应的知识节点（带缓存）。

        优先精确匹配，其次检索。缓存同一 (concept, subject) 的结果，
        避免每次教学都重新 search（节省时间）。

        §3.42 W12：缓存升级为 LRU+TTL（infra.cache.LRUCache），配置热重载时
        按 namespace=knowledge_base.resolve_node 失效。None 也是合法结果，
        需通过 ``fetch()`` + ``set_force()`` 区分未命中 / 命中但值为 None。
        """
        if not concept:
            return None
        key = f"{concept}::{subject or ''}"

        # 缓存查（区分 miss / 命中 None）
        if _W12_CACHE_ENABLED:
            hit, value = self._resolve_cache.fetch(key)
            if hit:
                return value
        else:
            # 兜底：原 dict 缓存（不区分 None 与 miss——这是已知限制）
            if key in self._resolve_cache:
                return self._resolve_cache[key]

        # 未命中 → 实际解析
        node = (self.get_subject(concept) or self.get_humanity(concept)
                or self.get_skill(concept))
        if node is None:
            hits = self.search(concept, subject=subject, top_k=1)
            if hits:
                cid = hits[0]["concept_id"]
                node = (self.get_subject(cid) or self.get_humanity(cid)
                        or self.get_skill(cid))
        if node is None and subject:
            node = self.get_skill_by_name(subject)

        # 写入缓存（None 也是合法结果，用 set_force 保留）
        if _W12_CACHE_ENABLED:
            self._resolve_cache.set_force(key, node)
        else:
            self._resolve_cache[key] = node
        return node

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def _load_demo_data(self):
        self._load_subjects()
        self._load_humanities()
        self._load_strategies()
        self._load_cases()
        self._load_skills()
        self._load_extended_subjects()

    def _load_extended_subjects(self):
        """v0.8.2：15 学科体系 × 学段分层扩展节点。"""
        try:
            from subjects_ext import load_extended_subjects
            load_extended_subjects(self.subjects)
        except Exception as e:
            # 扩展失败不阻断主流程（知识库退回基础节点）
            print(f"[knowledge_base] 扩展学科加载失败（忽略）: {e}")

    def _load_subjects(self):
        s = self.subjects

        # ===== 数学 =====
        s["math.arithmetic.negative"] = {
            "id": "math.arithmetic.negative", "subject": "math", "topic": "arithmetic",
            "concept": "negative", "level": "middle_school", "difficulty": 4,
            "prerequisites": ["math.arithmetic.addition"],
            "leads_to": ["math.algebra.linear_equation"],
            "definition": "负负得正：(-a)×(-b)=ab。源于相反数与数轴方向的反向之反向。",
            "intuition": "向前走=加，向后走=减；负号是'反向'，反向的反向=正向。",
            "explanation_variants": {
                "intuitive": "欠债还清：欠两次钱后翻倍归还，相当于赚回。",
                "formal": "由分配律推出：(-1)×(-1)=1 是环公理的必然结论。",
                "analogy": "电影倒放（反向）再倒放（反向的反向）等于正放。",
            },
            "common_misconceptions": ["以为负号是'删除'而非'反向'"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["math.algebra.quadratic_function"] = {
            "id": "math.algebra.quadratic_function", "subject": "math", "topic": "algebra",
            "concept": "quadratic_function", "level": "high_school", "difficulty": 6,
            "prerequisites": ["math.arithmetic.negative", "math.algebra.linear_equation"],
            "leads_to": ["math.calculus.derivative"],
            "definition": "二次函数 f(x)=ax²+bx+c（a≠0），图像为抛物线，顶点 -b/2a。",
            "intuition": "抛物线就像球被抛出去的轨迹。",
            "explanation_variants": {
                "intuitive": "a 决定开口方向和宽窄，c 决定上下位置。",
                "visual": "顶点坐标公式 ( -b/2a, (4ac-b²)/4a )，对称轴 x=-b/2a。",
            },
            "common_misconceptions": ["以为 a 必须为正", "混淆顶点与对称轴"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["math.calculus.derivative"] = {
            "id": "math.calculus.derivative", "subject": "math", "topic": "calculus",
            "concept": "derivative", "level": "undergraduate", "difficulty": 8,
            "prerequisites": ["math.algebra.quadratic_function"],
            "leads_to": ["math.calculus.integral"],
            "definition": "导数 f'(x)=lim(Δx→0) [f(x+Δx)-f(x)]/Δx，度量变化率。",
            "intuition": "导数=瞬时速度=曲线在该点的切线斜率。",
            "explanation_variants": {
                "intuitive": "开车时速度表的读数就是位置对时间的导数。",
                "formal": "极限定义的严格表述。",
            },
            "common_misconceptions": ["以为导数只是公式", "混淆变化率与总量"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["math.probability.bayes"] = {
            "id": "math.probability.bayes", "subject": "math", "topic": "probability",
            "concept": "bayes", "level": "undergraduate", "difficulty": 7,
            "prerequisites": ["math.probability.conditional"],
            "definition": "贝叶斯定理 P(A|B)=P(B|A)P(A)/P(B)，用新证据更新先验信念。",
            "intuition": "怀疑一个说法时，要用新证据不断修正自己的相信程度。",
            "explanation_variants": {
                "analogy": "医生告诉你检查阳性，但还要结合发病率（先验）才知真实患病概率。",
            },
            "common_misconceptions": ["忽略先验概率", "混淆 P(A|B) 与 P(B|A)"],
            "worldview_fit": {1: 0.10, 2: 0.60, 3: 0.10, 4: 0.20},
        }
        s["math.linear_algebra.vector"] = {
            "id": "math.linear_algebra.vector", "subject": "math", "topic": "linear_algebra",
            "concept": "vector", "level": "undergraduate", "difficulty": 6,
            "prerequisites": [],
            "leads_to": ["math.linear_algebra.matrix"],
            "definition": "向量是有大小和方向的量，可相加、缩放；n 维向量是 n 元有序数组。",
            "intuition": "箭头：既有长度又有方向；高维向量=数据点（如身高、体重、成绩）。",
            "explanation_variants": {
                "analogy": "地图上的位移；大模型里每个词都是一个高维向量。",
            },
            "common_misconceptions": ["以为向量必须画在纸上"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }

        # ===== 物理 =====
        s["physics.kinematics.newton_laws"] = {
            "id": "physics.kinematics.newton_laws", "subject": "physics", "topic": "mechanics",
            "concept": "newton_laws", "level": "high_school", "difficulty": 6,
            "prerequisites": ["math.algebra.quadratic_function"],
            "definition": "牛顿三定律：惯性、F=ma、作用力与反作用力。",
            "intuition": "推东西越用力越快；刹车时身体前倾是惯性。",
            "explanation_variants": {
                "intuitive": "在无摩擦冰面上滑行的冰球不会自己停下来。",
            },
            "common_misconceptions": ["以为力是运动的原因而非改变运动的原因"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["physics.thermodynamics.entropy"] = {
            "id": "physics.thermodynamics.entropy", "subject": "physics", "topic": "thermodynamics",
            "concept": "entropy", "level": "high_school", "difficulty": 6,
            "prerequisites": ["physics.kinematics.newton_laws", "math.probability.conditional"],
            "leads_to": ["physics.thermodynamics.second_law"],
            "definition": "熵是系统微观状态数的对数：S=k·lnΩ，度量'混乱'或'可能性数量'。",
            "intuition": "一杯热水放凉：分子从有序运动变得混乱；打碎的杯子不会自动复原。",
            "explanation_variants": {
                "intuitive": "房间不收拾会越来越乱，因为'乱'的排列方式远多于'整齐'。",
                "formal": "玻尔兹曼公式 S=k·lnΩ，热力学第二定律：孤立系统熵不减。",
            },
            "common_misconceptions": ["以为熵=混乱本身（实为可能状态数）"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["physics.electromagnetism.em_induction"] = {
            "id": "physics.electromagnetism.em_induction", "subject": "physics",
            "topic": "electromagnetism", "concept": "em_induction", "level": "high_school",
            "difficulty": 7,
            "prerequisites": ["physics.electromagnetism.magnetic_field"],
            "definition": "法拉第电磁感应：磁通量变化产生感应电动势，发电机原理。",
            "intuition": "磁铁快速插入线圈，灯泡会亮——动的磁场产生电。",
            "explanation_variants": {
                "analogy": "磁通量变化就像'穿过线圈的磁力线数量'在变。",
            },
            "common_misconceptions": ["以为磁铁静止也能产生感应电流"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["physics.quantum.entanglement"] = {
            "id": "physics.quantum.entanglement", "subject": "physics", "topic": "quantum",
            "concept": "entanglement", "level": "undergraduate", "difficulty": 9,
            "prerequisites": ["physics.quantum.superposition"],
            "definition": "量子纠缠：两个粒子的状态不可分割地关联，测量一个立即决定另一个。",
            "intuition": "两只手套分装两个盒子：打开一个知道颜色，另一个立刻确定。",
            "explanation_variants": {
                "intuitive": "但量子版更神奇：打开之前'颜色'根本不存在。",
            },
            "common_misconceptions": ["以为纠缠=超光速通信（不能传信息）"],
            "worldview_fit": {1: 0.10, 2: 0.50, 3: 0.20, 4: 0.20},
        }
        s["physics.relativity.special"] = {
            "id": "physics.relativity.special", "subject": "physics", "topic": "relativity",
            "concept": "special", "level": "undergraduate", "difficulty": 8,
            "prerequisites": ["physics.kinematics.newton_laws"],
            "definition": "狭义相对论：光速不变，时间膨胀、长度收缩，E=mc²。",
            "intuition": "高速运动的时钟走得慢；'同时'是相对的。",
            "explanation_variants": {
                "intuitive": "光速是宇宙速度上限，任何物体都无法超过。",
            },
            "common_misconceptions": ["以为相对论只在高速时才有意义（GPS 也要修正）"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }

        # ===== 化学 =====
        s["chemistry.general.periodic_table"] = {
            "id": "chemistry.general.periodic_table", "subject": "chemistry",
            "topic": "general", "concept": "periodic_table", "level": "high_school",
            "difficulty": 5,
            "prerequisites": ["chemistry.general.atom"],
            "definition": "元素周期表按原子序数排列，性质随周期/族周期性变化。",
            "intuition": "同族元素'性格相似'（碱金属都活泼），同周期从左到右金属性减弱。",
            "explanation_variants": {
                "analogy": "像按身高排队：相邻的人像，隔一段出现规律。",
            },
            "common_misconceptions": ["以为周期表只是背下来的死表"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["chemistry.reactions.equilibrium"] = {
            "id": "chemistry.reactions.equilibrium", "subject": "chemistry",
            "topic": "reactions", "concept": "equilibrium", "level": "high_school",
            "difficulty": 6,
            "prerequisites": ["chemistry.general.periodic_table"],
            "definition": "化学平衡：正逆反应速率相等时宏观静止；勒夏特列原理。",
            "intuition": "水池进水和排水一样快，水面不再变化，但水一直在换。",
            "explanation_variants": {
                "analogy": "两边排队人数相等时队伍长度不变。",
            },
            "common_misconceptions": ["以为平衡=反应停止"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["chemistry.organic.functional_groups"] = {
            "id": "chemistry.organic.functional_groups", "subject": "chemistry",
            "topic": "organic", "concept": "functional_groups", "level": "undergraduate",
            "difficulty": 6,
            "prerequisites": ["chemistry.general.periodic_table"],
            "definition": "官能团决定有机物的主要化学性质（羟基、羧基、氨基等）。",
            "intuition": "碳骨架是身体，官能团是'性格'：-OH 易亲水，-COOH 显酸性。",
            "explanation_variants": {
                "analogy": "同一件衣服（碳骨架），不同的徽章（官能团）赋予不同身份。",
            },
            "common_misconceptions": ["以为碳链长=性质差异大（实为官能团主导）"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }

        # ===== 生物 =====
        s["biology.cell.structure"] = {
            "id": "biology.cell.structure", "subject": "biology", "topic": "cell",
            "concept": "structure", "level": "high_school", "difficulty": 5,
            "prerequisites": [],
            "definition": "细胞是生命的基本单位：细胞膜、细胞质、细胞核（真核）。",
            "intuition": "细胞像一座微型工厂：膜=围墙，线粒体=发电厂，核=指挥部。",
            "explanation_variants": {
                "analogy": "工厂各部门分工协作。",
            },
            "common_misconceptions": ["以为所有细胞都有细胞核（原核生物没有）"],
            "worldview_fit": {1: 0.05, 2: 0.60, 3: 0.20, 4: 0.15},
        }
        s["biology.genetics.mendel"] = {
            "id": "biology.genetics.mendel", "subject": "biology", "topic": "genetics",
            "concept": "mendel", "level": "high_school", "difficulty": 6,
            "prerequisites": ["biology.cell.structure"],
            "leads_to": ["biology.genetics.dna"],
            "definition": "孟德尔遗传：显隐性、分离定律、自由组合定律。",
            "intuition": "豌豆的圆/皱性状像'抽签'，由基因决定但不简单混合。",
            "explanation_variants": {
                "intuitive": "父母各给一份'说明书'，显性基因优先显示。",
            },
            "common_misconceptions": ["以为显性=更常见"],
            "worldview_fit": {1: 0.05, 2: 0.60, 3: 0.20, 4: 0.15},
        }
        s["biology.evolution.darwin"] = {
            "id": "biology.evolution.darwin", "subject": "biology", "topic": "evolution",
            "concept": "darwin", "level": "high_school", "difficulty": 6,
            "prerequisites": ["biology.genetics.mendel"],
            "definition": "自然选择：变异+遗传+选择压力→适应性进化。",
            "intuition": "长颈鹿的脖子：变异产生长短差异，环境筛选留下更适合的。",
            "explanation_variants": {
                "intuitive": "不是'想要'变长，而是'碰巧'长脖子的活了下来。",
            },
            "common_misconceptions": ["以为进化=有目的（拉马克式错误）"],
            "worldview_fit": {1: 0.10, 2: 0.60, 3: 0.15, 4: 0.15},
        }
        s["biology.genetics.dna"] = {
            "id": "biology.genetics.dna", "subject": "biology", "topic": "genetics",
            "concept": "dna", "level": "undergraduate", "difficulty": 7,
            "prerequisites": ["biology.genetics.mendel"],
            "definition": "DNA 双螺旋：A-T、G-C 碱基配对，基因=编码蛋白质的 DNA 片段。",
            "intuition": "DNA 像一本用 4 个字母写成的生命说明书。",
            "explanation_variants": {
                "analogy": "4 个碱基=4 个字母，三个一组=单词（密码子）。",
            },
            "common_misconceptions": ["以为 DNA 突变总是有害（多为中性）"],
            "worldview_fit": {1: 0.05, 2: 0.65, 3: 0.15, 4: 0.15},
        }

        # ===== 计算机 =====
        s["cs.algorithms.search_sort"] = {
            "id": "cs.algorithms.search_sort", "subject": "cs", "topic": "algorithms",
            "concept": "search_sort", "level": "undergraduate", "difficulty": 6,
            "prerequisites": ["math.linear_algebra.vector"],
            "definition": "二分查找 O(log n)、快速排序 O(n log n) 等基础算法。",
            "intuition": "猜数字游戏每次排除一半→二分查找。",
            "explanation_variants": {
                "analogy": "查字典不用从第一页翻起，直接翻到大概位置。",
            },
            "common_misconceptions": ["以为排序必须逐个比较（有计数/基数排序）"],
            "worldview_fit": {1: 0.10, 2: 0.55, 3: 0.15, 4: 0.20},
        }
        s["cs.ai.llm_basics"] = {
            "id": "cs.ai.llm_basics", "subject": "cs", "topic": "ai",
            "concept": "llm_basics", "level": "undergraduate", "difficulty": 7,
            "prerequisites": ["cs.algorithms.search_sort", "math.probability.bayes"],
            "definition": "大语言模型=用海量文本训练的 Transformer，预测下一个 token。",
            "intuition": "它像'超强版输入法'：根据前文预测下一个字，但学到的远不止字面规律。",
            "explanation_variants": {
                "intuitive": "训练=读亿万本书并记住'哪些词通常一起出现'，涌现出推理能力。",
            },
            "common_misconceptions": ["以为 LLM 会'思考'而非'统计预测'（辩论话题）"],
            "worldview_fit": {1: 0.10, 2: 0.50, 3: 0.15, 4: 0.25},
        }
        s["cs.data_structure.stack_queue"] = {
            "id": "cs.data_structure.stack_queue", "subject": "cs", "topic": "data_structure",
            "concept": "stack_queue", "level": "undergraduate", "difficulty": 5,
            "prerequisites": [],
            "definition": "栈=后进先出（LIFO），队列=先进先出（FIFO）。",
            "intuition": "栈=叠盘子（后放的先拿），队列=排队买票（先来的先走）。",
            "explanation_variants": {
                "analogy": "撤销操作就是栈：最后做的先撤销。",
            },
            "common_misconceptions": ["混淆两者顺序"],
            "worldview_fit": {1: 0.10, 2: 0.55, 3: 0.15, 4: 0.20},
        }

        # ===== 逻辑 =====
        s["logic.formal.syllogism"] = {
            "id": "logic.formal.syllogism", "subject": "logic", "topic": "formal",
            "concept": "syllogism", "level": "undergraduate", "difficulty": 5,
            "prerequisites": [],
            "definition": "三段论：大前提+小前提→结论（所有人会死；苏格拉底是人；故苏格拉底会死）。",
            "intuition": "逻辑的'搭积木'：两块前提严丝合缝推出结论。",
            "explanation_variants": {
                "intuitive": "检测推理是否有效的骨架。",
            },
            "common_misconceptions": ["前提为假但形式有效≠推理错误"],
            "worldview_fit": {1: 0.05, 2: 0.70, 3: 0.10, 4: 0.15},
        }
        s["logic.informal.fallacies"] = {
            "id": "logic.informal.fallacies", "subject": "logic", "topic": "informal",
            "concept": "fallacies", "level": "undergraduate", "difficulty": 5,
            "prerequisites": [],
            "definition": "常见谬误：人身攻击、诉诸权威、滑坡谬误、稻草人、虚假两难。",
            "intuition": "吵架中常见的'偷换概念'和'攻击人'。",
            "explanation_variants": {
                "intuitive": "稻草人=把对方观点歪曲后再攻击。",
            },
            "common_misconceptions": ["以为情绪化发言=逻辑谬误（情绪本身不是谬误）"],
            "worldview_fit": {1: 0.10, 2: 0.60, 3: 0.15, 4: 0.15},
        }

        # ===== 历史 =====
        s["history.world.french_revolution"] = {
            "id": "history.world.french_revolution", "subject": "history",
            "topic": "world", "concept": "french_revolution", "level": "high_school",
            "difficulty": 5,
            "prerequisites": [],
            "definition": "法国大革命（1789）：推翻旧制度，传播自由平等博爱理念。",
            "intuition": "旧制度下等级固化，第三等级（平民）愤怒爆发。",
            "explanation_variants": {
                "intuitive": "不是单一原因：财政危机+启蒙思想+社会不公叠加。",
            },
            "common_misconceptions": ["以为革命只是'砍国王'（有多阶段、恐怖统治等复杂史实）"],
            "worldview_fit": {1: 0.30, 2: 0.30, 3: 0.20, 4: 0.20},
        }
        s["history.world.silk_road"] = {
            "id": "history.world.silk_road", "subject": "history", "topic": "world",
            "concept": "silk_road", "level": "high_school", "difficulty": 4,
            "prerequisites": [],
            "definition": "丝绸之路：连接东西方的贸易与文化交流网络（不止一条路）。",
            "intuition": "不只是运丝绸，还有宗教、技术、疾病在流动。",
            "explanation_variants": {
                "intuitive": "像古代的'互联网'：商品和思想双向传播。",
            },
            "common_misconceptions": ["以为丝路只卖丝绸、只有一条"],
            "worldview_fit": {1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20},
        }

        # ===== 经济 =====
        s["economics.micro.supply_demand"] = {
            "id": "economics.micro.supply_demand", "subject": "economics",
            "topic": "micro", "concept": "supply_demand", "level": "high_school",
            "difficulty": 5,
            "prerequisites": [],
            "definition": "供需定律：价格由供给与需求共同决定，均衡价格使市场出清。",
            "intuition": "奶茶店降价→排队变长（需求多）；成本涨→涨价（供给少）。",
            "explanation_variants": {
                "analogy": "跷跷板：价格是中间支点，供需是两端。",
            },
            "common_misconceptions": ["以为价格只由成本决定"],
            "worldview_fit": {1: 0.30, 2: 0.40, 3: 0.10, 4: 0.20},
        }
        s["economics.micro.opportunity_cost"] = {
            "id": "economics.micro.opportunity_cost", "subject": "economics",
            "topic": "micro", "concept": "opportunity_cost", "level": "high_school",
            "difficulty": 4,
            "prerequisites": [],
            "definition": "机会成本=做一件事所放弃的次优选择的价值。",
            "intuition": "上大学的机会成本不只是学费，还有打工本可赚的钱。",
            "explanation_variants": {
                "intuitive": "任何选择都有'隐形的代价'。",
            },
            "common_misconceptions": ["只看账面成本，忽略放弃的收益"],
            "worldview_fit": {1: 0.25, 2: 0.40, 3: 0.15, 4: 0.20},
        }

        # ===== 心理 =====
        s["psychology.cognitive.bias"] = {
            "id": "psychology.cognitive.bias", "subject": "psychology",
            "topic": "cognitive", "concept": "bias", "level": "undergraduate",
            "difficulty": 5,
            "prerequisites": [],
            "definition": "认知偏差：确认偏误、可得性启发、锚定效应等系统性思维捷径偏差。",
            "intuition": "只记得支持自己想法的证据（确认偏误），忘记反对的。",
            "explanation_variants": {
                "intuitive": "大脑的'省电模式'，速度快但会走捷径出错。",
            },
            "common_misconceptions": ["以为聪明人没有偏差（人人都有）"],
            "worldview_fit": {1: 0.15, 2: 0.45, 3: 0.25, 4: 0.15},
        }
        s["psychology.humanistic.maslow"] = {
            "id": "psychology.humanistic.maslow", "subject": "psychology",
            "topic": "humanistic", "concept": "maslow", "level": "undergraduate",
            "difficulty": 4,
            "prerequisites": [],
            "definition": "马斯洛需求层次：生理→安全→归属→尊重→自我实现。",
            "intuition": "先吃饱（生理），才有力气追求意义（自我实现）。",
            "explanation_variants": {
                "intuitive": "像爬楼梯，但现代研究认为层次并不严格。",
            },
            "common_misconceptions": ["以为必须逐级满足（实际可跳级）"],
            "worldview_fit": {1: 0.40, 2: 0.20, 3: 0.30, 4: 0.10},
        }

        # ===== 哲学 =====
        s["philosophy.epistemology.truth"] = {
            "id": "philosophy.epistemology.truth", "subject": "philosophy",
            "topic": "epistemology", "concept": "truth", "level": "undergraduate",
            "difficulty": 7,
            "prerequisites": [],
            "definition": "真理理论：符合论（与事实相符）、融贯论（与信念体系一致）、实用论（有用即真）。",
            "intuition": "'地球是圆的'为什么是'真'的？三种理论给出不同回答。",
            "explanation_variants": {
                "intuitive": "符合论=对得上事实；实用论=用它做事能成功。",
            },
            "common_misconceptions": ["以为真理只有一个标准答案"],
            "worldview_fit": {1: 0.25, 2: 0.40, 3: 0.20, 4: 0.15},
        }
        s["philosophy.metaphysics.free_will"] = {
            "id": "philosophy.metaphysics.free_will", "subject": "philosophy",
            "topic": "metaphysics", "concept": "free_will", "level": "undergraduate",
            "difficulty": 8,
            "prerequisites": ["physics.quantum.entanglement"],
            "definition": "自由意志：决定论 vs 相容论 vs 自由意志论；意识与因果的关系。",
            "intuition": "如果一切都有原因，我'选择'还是只是'发生'？",
            "explanation_variants": {
                "intuitive": "决定论：宇宙像发条钟；相容论：即使被决定，'我的选择'依然有意义。",
            },
            "common_misconceptions": ["把'自由'等同于'毫无原因'"],
            "worldview_fit": {1: 0.30, 2: 0.30, 3: 0.20, 4: 0.20},
        }

        # ===== 语言 =====
        s["language.english.grammar_tense"] = {
            "id": "language.english.grammar_tense", "subject": "language",
            "topic": "english", "concept": "grammar_tense", "level": "high_school",
            "difficulty": 5,
            "prerequisites": [],
            "definition": "英语时态：时（过去/现在/将来）×体（一般/进行/完成/完成进行）。",
            "intuition": "时=时间轴位置，体=动作状态（正在进行/已完成）。",
            "explanation_variants": {
                "analogy": "时=拍照时刻，体=快门是单张还是连拍。",
            },
            "common_misconceptions": ["把'时'和'态'混为一谈"],
            "worldview_fit": {1: 0.10, 2: 0.50, 3: 0.20, 4: 0.20},
        }

        # ===== 地理 =====
        s["geography.natural.climate"] = {
            "id": "geography.natural.climate", "subject": "geography",
            "topic": "natural", "concept": "climate", "level": "high_school",
            "difficulty": 5,
            "prerequisites": [],
            "definition": "气候类型：纬度+海陆位置+地形+洋流共同决定（热带雨林、地中海等）。",
            "intuition": "同样在赤道，高山和海边气候完全不同——地形改变一切。",
            "explanation_variants": {
                "intuitive": "气候=长期天气统计，天气=短期瞬时状态。",
            },
            "common_misconceptions": ["混淆'天气'与'气候'"],
            "worldview_fit": {1: 0.10, 2: 0.50, 3: 0.20, 4: 0.20},
        }

        # ===== 艺术 =====
        s["art.theory.perspective"] = {
            "id": "art.theory.perspective", "subject": "art", "topic": "theory",
            "concept": "perspective", "level": "undergraduate", "difficulty": 5,
            "prerequisites": [],
            "definition": "透视法：线性透视（消失点）在二维平面上表现三维空间的技法。",
            "intuition": "铁路轨道在远方交于一点——那就是消失点。",
            "explanation_variants": {
                "visual": "近大远小、平行线汇聚于消失点。",
            },
            "common_misconceptions": ["以为透视是'真实'（只是观看方式之一）"],
            "worldview_fit": {1: 0.10, 2: 0.30, 3: 0.40, 4: 0.20},
        }

    def _load_humanities(self):
        h = self.humanities

        # ---- 审美 ----
        h["literature.epic.iliad"] = {
            "id": "literature.epic.iliad", "dimension": "aesthetics",
            "core_question": "为什么特洛伊战争持续十年？",
            "tradition_perspectives": {
                "homer": "《伊利亚特》开篇就揭示：阿基琉斯与阿伽门农的私人冲突",
                "nietzsche": "荣誉与权力是希腊悲剧的核心",
                "zhuangzi": "战争与和平皆是'道'的表现",
            },
            "teaching_modes": ["lecture", "contemplation"],
            "worldview_fit": {1: 0.20, 2: 0.10, 3: 0.60, 4: 0.10},
        }
        h["aesthetics.tragic_beauty"] = {
            "id": "aesthetics.tragic_beauty", "dimension": "aesthetics",
            "sub_dimension": "tragical_aesthetics",
            "core_question": "什么是悲剧美？为什么人类在悲剧中获得审美愉悦？",
            "tradition_perspectives": {
                "aristotle": "亚里士多德《诗学》：通过怜悯与恐惧的净化（katharsis）",
                "nietzsche": "尼采《悲剧的诞生》：日神与酒神的对峙",
                "zhuangzi": "《庄子·齐物论》：天地与我并生，万物与我为一",
                "confucian": "《论语·阳货》：诗可以兴、可以观、可以群、可以怨",
            },
            "teaching_modes": ["lecture", "dialogue", "practice", "contemplation"],
            "worldview_fit": {1: 0.20, 2: 0.20, 3: 0.50, 4: 0.10},
        }
        h["aesthetics.what_is_beauty"] = {
            "id": "aesthetics.what_is_beauty", "dimension": "aesthetics",
            "core_question": "美是什么？是客观属性还是主观感受？",
            "tradition_perspectives": {
                "plato": "美是理念（客观）",
                "hume": "美存在于鉴赏者的心中（主观）",
                "kant": "美是无目的的合目的性（判断力）",
                "zhuangzi": "天地有大美而不言（自然）",
            },
            "teaching_modes": ["dialogue", "contemplation"],
            "worldview_fit": {1: 0.15, 2: 0.20, 3: 0.55, 4: 0.10},
        }

        # ---- 道德 ----
        h["ethics.dilemma.trolley"] = {
            "id": "ethics.dilemma.trolley", "dimension": "morality",
            "core_question": "电车难题该拉开关吗？",
            "tradition_perspectives": {
                "kant": "义务论：人是目的，不能为救多数牺牲一人",
                "mill": "功利论：救多数人最大化幸福",
                "confucian": "经权之辨：常理与权变需平衡",
            },
            "teaching_modes": ["dialogue", "practice"],
            "worldview_fit": {1: 0.50, 2: 0.20, 3: 0.20, 4: 0.10},
        }
        h["ethics.theory.deontology_utilitarianism"] = {
            "id": "ethics.theory.deontology_utilitarianism", "dimension": "morality",
            "core_question": "判断对错看动机（义务论）还是看结果（功利论）？",
            "tradition_perspectives": {
                "kant": "义务论：道德律令，人是目的",
                "mill": "功利论：最大多数人的最大幸福",
                "confucian": "义利之辨：君子喻于义，小人喻于利",
            },
            "teaching_modes": ["lecture", "dialogue"],
            "worldview_fit": {1: 0.50, 2: 0.20, 3: 0.20, 4: 0.10},
        }
        h["ethics.virtue.character"] = {
            "id": "ethics.virtue.character", "dimension": "morality",
            "core_question": "成为什么样的人比做什么事更重要？（德性伦理）",
            "tradition_perspectives": {
                "aristotle": "德性=中道（勇敢是鲁莽与怯懦的中道）",
                "confucian": "修身齐家治国平天下",
                "mencius": "四端说：恻隐、羞恶、辞让、是非",
            },
            "teaching_modes": ["dialogue", "contemplation"],
            "worldview_fit": {1: 0.50, 2: 0.15, 3: 0.25, 4: 0.10},
        }

        # ---- 思辨 ----
        h["critical_thinking.argument"] = {
            "id": "critical_thinking.argument", "dimension": "thinking",
            "core_question": "如何评估一个论证的好坏？",
            "tradition_perspectives": {
                "aristotle": "逻辑三段论与修辞学",
                "popper": "可证伪性：好理论必须可被检验推翻",
                "confucian": "叩其两端而竭焉：从两端入手穷尽问题",
            },
            "teaching_modes": ["dialogue", "practice"],
            "worldview_fit": {1: 0.20, 2: 0.50, 3: 0.15, 4: 0.15},
        }
        h["critical_thinking.dialogue"] = {
            "id": "critical_thinking.dialogue", "dimension": "thinking",
            "core_question": "如何在对话中共同接近真理？",
            "tradition_perspectives": {
                "socrates": "苏格拉底式诘问：通过提问暴露无知",
                "confucian": "教学相长：三人行必有我师",
                "gadamer": "视域融合：对话改变双方",
            },
            "teaching_modes": ["dialogue"],
            "worldview_fit": {1: 0.20, 2: 0.40, 3: 0.30, 4: 0.10},
        }

        # ---- 生命现象学 ----
        h["phenomenology.loneliness"] = {
            "id": "phenomenology.loneliness", "dimension": "life",
            "core_question": "为什么人会感到孤独？",
            "tradition_perspectives": {
                "heidegger": "此在（Dasein）：人是被抛入世界的存在，孤独是存在的基本情态",
                "levinas": "他者：孤独源于面对他者的无限责任",
                "zhuangzi": "独与天地精神往来：独处不是空虚而是丰盈",
            },
            "teaching_modes": ["dialogue", "contemplation"],
            "worldview_fit": {1: 0.20, 2: 0.10, 3: 0.60, 4: 0.10},
        }
        h["phenomenology.time"] = {
            "id": "phenomenology.time", "dimension": "life",
            "core_question": "时间对我们意味着什么？",
            "tradition_perspectives": {
                "augustine": "奥古斯丁：时间在心灵中（过去是记忆，未来是期待）",
                "heidegger": "向死而生：时间是存在的地平线",
                "zhuangzi": "白驹过隙：人生天地之间，若白驹之过隙",
                "buddhist": "诸行无常：一切都在变化中",
            },
            "teaching_modes": ["lecture", "contemplation"],
            "worldview_fit": {1: 0.15, 2: 0.10, 3: 0.65, 4: 0.10},
        }
        h["phenomenology.death"] = {
            "id": "phenomenology.death", "dimension": "life",
            "core_question": "如何理解死亡？（向死而生）",
            "tradition_perspectives": {
                "heidegger": "向死而生：意识到有限性才能活得本真",
                "epicurus": "死亡与我无关：我存在时死亡不存在，死亡存在时我不存在",
                "confucian": "未知生，焉知死：先活好此生",
                "zhuangzi": "鼓盆而歌：生死一体，气之聚散",
            },
            "teaching_modes": ["dialogue", "contemplation"],
            "worldview_fit": {1: 0.25, 2: 0.15, 3: 0.50, 4: 0.10},
        }
        h["phenomenology.meaning"] = {
            "id": "phenomenology.meaning", "dimension": "life",
            "core_question": "生命的意义是什么？",
            "tradition_perspectives": {
                "camus": "西西弗斯：荒谬中依然选择热爱",
                "frankl": "意义疗法：人可以被剥夺一切，除了选择的自由",
                "confucian": "仁者爱人：意义在关系中生成",
                "buddhist": "缘起性空：意义在空性中自在",
            },
            "teaching_modes": ["dialogue", "contemplation"],
            "worldview_fit": {1: 0.25, 2: 0.10, 3: 0.55, 4: 0.10},
        }

    def _load_strategies(self):
        st = self.strategies
        st["socratic_dialogue"] = {
            "id": "socratic_dialogue",
            "applicable_to": ["critical_thinking", "moral_dilemma", "philosophy"],
            "philosophy_origin": "古希腊苏格拉底",
            "steps": ["先问学生的初始看法", "通过反问暴露矛盾", "引入多元视角", "引导学生自己综合"],
            "when_to_use": "学生有明确观点但理由不足时",
            "worldview_emphasis": {1: 0.10, 2: 0.40, 3: 0.30, 4: 0.20},
        }
        st["analogy_based"] = {
            "id": "analogy_based",
            "applicable_to": ["physics", "math", "cs", "chemistry"],
            "philosophy_origin": "教育心理学（类比迁移）",
            "steps": ["选一个学生熟悉的具体场景", "建立概念与场景的映射", "指出类比边界"],
            "when_to_use": "抽象概念初次接触时",
            "worldview_emphasis": {1: 0.10, 2: 0.50, 3: 0.20, 4: 0.20},
        }
        st["phenomenological_reflection"] = {
            "id": "phenomenological_reflection",
            "applicable_to": ["phenomenology", "aesthetics", "literature"],
            "philosophy_origin": "现象学（胡塞尔/海德格尔）",
            "steps": ["回到事情本身（现象）", "悬置成见", "邀请内省与描述", "保留沉默空间"],
            "when_to_use": "生命体验、审美、存在类话题",
            "worldview_emphasis": {1: 0.10, 2: 0.10, 3: 0.70, 4: 0.10},
        }
        st["scaffolding"] = {
            "id": "scaffolding",
            "applicable_to": ["math", "physics", "language"],
            "philosophy_origin": "维果茨基最近发展区",
            "steps": ["评估学生当前水平", "拆解任务到可达成粒度", "逐步提供支架", "逐步撤除支架"],
            "when_to_use": "学生接近但未达到目标能力时",
            "worldview_emphasis": {1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20},
        }
        st["case_based"] = {
            "id": "case_based",
            "applicable_to": ["history", "economics", "ethics", "psychology"],
            "philosophy_origin": "案例教学法（哈佛商学院）",
            "steps": ["呈现真实案例", "分析关键要素", "抽象出一般原理", "迁移到新案例"],
            "when_to_use": "需要情境化理解时",
            "worldview_emphasis": {1: 0.15, 2: 0.35, 3: 0.20, 4: 0.30},
        }

    def _load_cases(self):
        c = self.cases
        c["soccer_pass_strategy"] = {
            "id": "soccer_pass_strategy", "type": "analogy",
            "used_in": ["math.game_theory", "economics.micro.opportunity_cost", "psychology.cognitive.bias"],
            "content": "足球场上的传球策略：5 个前锋如何分配球权（博弈论纳什均衡的直观案例）",
            "why_good": "具体、生动、学生熟悉、跨学科可迁移", "difficulty": 4,
        }
        c["gps_relativity"] = {
            "id": "gps_relativity", "type": "application",
            "used_in": ["physics.relativity.special"],
            "content": "GPS 卫星因相对论每天快约 38 微秒，必须修正否则定位每天偏 10 公里",
            "why_good": "让学生看到'高深'理论就在手机里", "difficulty": 5,
        }
        c["fake_news_bayes"] = {
            "id": "fake_news_bayes", "type": "application",
            "used_in": ["math.probability.bayes", "logic.informal.fallacies", "psychology.cognitive.bias"],
            "content": "用贝叶斯思维评估'某消息是假的'：先验（该来源可信度）× 新证据（内容可疑度）",
            "why_good": "把数学变成日常判断工具", "difficulty": 6,
        }
        c["trolley_transplant"] = {
            "id": "trolley_transplant", "type": "dilemma",
            "used_in": ["ethics.dilemma.trolley", "ethics.theory.deontology_utilitarianism"],
            "content": "电车难题变体：牺牲一个健康人救五个病人（对比'拉开关'与'亲手杀人'的心理差异）",
            "why_good": "暴露义务论/功利论的深层张力", "difficulty": 7,
        }
        c["homesick_loneliness"] = {
            "id": "homesick_loneliness", "type": "life",
            "used_in": ["phenomenology.loneliness", "phenomenology.meaning"],
            "content": "离家求学时的孤独：既是'被抛'（海德格尔），也是重新认识自己的契机（庄子'独与天地精神往来'）",
            "why_good": "贴近学生真实体验，让现象学落地", "difficulty": 5,
        }

    def _load_skills(self):
        """G4 技能教学：可操作技能（编程/写作/思辨/问题解决/表达/学习法）。
        结构：skills[skill_id] = {id, category, name, definition, steps, practice, pitfalls, worldview_fit}"""
        s = self.skills

        s["skill.coding.python_basics"] = {
            "id": "skill.coding.python_basics", "category": "coding", "name": "Python 编程入门",
            "definition": "掌握变量、条件、循环、函数四大基础，能独立写出解决简单问题的脚本。",
            "steps": [
                "先理解'程序=数据处理流程'：输入 → 处理 → 输出",
                "变量：给数据起名字（x = 5）；类型：数字/字符串/布尔",
                "条件：if/elif/else 让程序'做选择'；循环：for/while 让程序'重复'",
                "函数：把一段逻辑打包复用（def 函数名():）",
                "练习：写一个'输入成绩→判断等级'的脚本",
            ],
            "practice": "用'编程闯关'方式：先读代码猜输出，再改代码验证，最后独立写",
            "pitfalls": ["初学者常把'等于(=)'与'相等(==)'混淆", "缩进错误是语法错误的主因"],
            "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
        }

        s["skill.writing.argumentative"] = {
            "id": "skill.writing.argumentative", "category": "writing", "name": "议论文写作",
            "definition": "掌握'论点-论据-论证'结构，能写出逻辑清晰、有说服力的议论文。",
            "steps": [
                "审题定论点：一句话说清'我主张什么'",
                "搭建框架：引论（现象/问题）→ 本论（2-3 个分论点）→ 结论（升华）",
                "每个分论点 = 观点 + 事实/理论论据 + 分析（'所以'逻辑链）",
                "用'让步-反驳'增强说服力：承认反方合理处，再指出其不足",
                "修改：删冗余、查逻辑漏洞、换更精准的词",
            ],
            "practice": "就'手机该不该进校园'写 600 字提纲，逐段填充再互评",
            "pitfalls": ["论据堆砌无分析（'摆事实'≠'讲道理'）", "论点游移（一段一个主张）"],
            "worldview_fit": {"1": 0.2, "2": 0.4, "3": 0.2, "4": 0.2},
        }

        s["skill.thinking.critical"] = {
            "id": "skill.thinking.critical", "category": "thinking", "name": "批判性思维",
            "definition": "能识别论证结构、发现逻辑谬误、评估证据强度，独立形成有依据的判断。",
            "steps": [
                "拆解论证：结论是什么？理由是什么？",
                "检验理由：事实有来源吗？数据样本够吗？有没有因果混淆？",
                "识别常见谬误：以偏概全、诉诸权威、滑坡、人身攻击",
                "换位思考：支持/反对双方的最佳论据各是什么？",
                "形成'可证伪'的判断：什么证据能推翻我的结论？",
            ],
            "practice": "选一条热点新闻，用'证据-推理-结论'框架写分析，再与反方观点对读",
            "pitfalls": ["把'感受'当'证据'", "只找支持自己的信息（确认偏误）"],
            "worldview_fit": {"1": 0.3, "2": 0.4, "3": 0.2, "4": 0.1},
        }

        s["skill.problem.solving"] = {
            "id": "skill.problem.solving", "category": "thinking", "name": "问题解决（PBL）",
            "definition": "用结构化流程解决复杂问题：定义→拆解→方案→执行→复盘。",
            "steps": [
                "定义问题：真正的目标是什么？（区分'症状'与'根因'）",
                "拆解问题：大问题分解为可处理的小问题",
                "头脑风暴多方案：不评判，先发散",
                "评估选择：按'影响×可行性'矩阵打分",
                "执行并复盘：哪些有效？哪些假设错了？如何迭代？",
            ],
            "practice": "用此法解决'如何提升一门课的成绩'，写下每一步的思考",
            "pitfalls": ["急于给答案而跳过'定义问题'", "只做一个方案就投入"],
            "worldview_fit": {"1": 0.2, "2": 0.3, "3": 0.3, "4": 0.2},
        }

        s["skill.expression.public_speaking"] = {
            "id": "skill.expression.public_speaking", "category": "expression", "name": "公众表达",
            "definition": "能在公众面前清晰、有条理地表达观点，控制紧张，感染听众。",
            "steps": [
                "定目标：我要让听众记住/理解/行动什么？",
                "组织内容：开场抓注意（问题/故事/数据）→ 主体三点 → 结尾回扣",
                "练习脱稿：只记关键词，不背稿",
                "控制紧张：提前到场、深呼吸、把紧张当作兴奋",
                "交付技巧：语速放慢、看听众、用手势强调",
            ],
            "practice": "用'三点式'结构做 3 分钟即兴演讲，录视频回看",
            "pitfalls": ["信息过载（想讲太多）", "盯着幻灯片/天花板不看听众"],
            "worldview_fit": {"1": 0.3, "2": 0.2, "3": 0.3, "4": 0.2},
        }

        s["skill.learning.method"] = {
            "id": "skill.learning.method", "category": "learning", "name": "高效学习法（费曼+间隔）",
            "definition": "掌握费曼技巧与间隔重复两大学习法，能自学任何新知识。",
            "steps": [
                "费曼四步：学概念 → 用自己的话讲给'小白' → 发现卡壳处 → 回到原处补齐",
                "主动回忆：合上书自测，比反复阅读有效 2-3 倍",
                "间隔重复：按 1/3/7/15 天复习，对抗遗忘曲线",
                "输出倒逼输入：写笔记、讲给别人、做练习",
                "建立知识联系：新知识与已有知识'挂钩'",
            ],
            "practice": "选一个陌生概念，用费曼法学，并制定 7 天间隔复习计划",
            "pitfalls": ["'划重点'式假学习", "只输入不输出"],
            "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
        }

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------
    def get_subject(self, concept_id: str) -> Optional[dict]:
        return self.subjects.get(concept_id)

    def get_humanity(self, concept_id: str) -> Optional[dict]:
        return self.humanities.get(concept_id)

    def get_strategy(self, strategy_id: str) -> Optional[dict]:
        return self.strategies.get(strategy_id)

    def get_skill(self, skill_id: str) -> Optional[dict]:
        """返回技能节点（G4 技能教学）。"""
        return self.skills.get(skill_id)

    def get_skill_by_name(self, name: str) -> Optional[dict]:
        """按名称模糊匹配技能。"""
        name_l = name.lower()
        for nid, node in self.skills.items():
            if name_l in nid.lower() or name_l in node.get("name", "").lower() or name_l in node.get("category", "").lower():
                return node
        return None

    def get_subject_nodes(self, subject: str) -> list:
        """返回指定学科的所有知识节点。"""
        return [n for n in self.subjects.values() if n.get("subject") == subject]

    def search(self, query: str, subject: str = None, top_k: int = 5) -> list:
        """关键词检索（真 BM25Okapi 排序 + jieba 中文分词）。

        v0.42 ⭐ Oracle RAG 优化项 #2：从"简化 BM25"（token 命中计数，无 IDF / 无
        长度归一化）升级为 ``rank_bm25.BM25Okapi`` 真排序（含 IDF + 长度归一化 +
        jieba 中文分词 + 自定义词典），预期 Recall +10~20%。

        设计要点：
        - **懒构建语料**：每次 search 重建 BM25Okapi 语料。KB 节点数 ~100 量级，
          重建开销可接受；避免 ``_search_cache``（v0.15 raw dict，语义可能与新
          BM25 不一致——Oracle 风险提示）带来的缓存失效问题。
        - **缺字段兜底**：节点缺 definition / intuition 等字段不崩（用 ``.get``
          兜底，生成空字符串。B4 后 evolved 节点字段齐全，但未 schema 节点仍需
          防御）。
        - **降级路径**：BM25Okapi / jieba 不可用时，回退为简单子串匹配（保证
          永不抛异常）。
        - **保留签名与返回 schema**：``(query, subject=None, top_k=5)`` →
          ``[{concept_id, title, snippet, relevance_score, difficulty}, ...]``。

        Parameters
        ----------
        query : str
            用户查询文本（中文/英文混合均可）。
        subject : str, optional
            学科过滤（math / physics / chemistry / ...）。None 时不过滤。
        top_k : int, default 5
            返回的最相关节点数；候选不足时返回全部（不补空）。

        Returns
        -------
        list of dict
            按 ``relevance_score`` 降序排列的相关节点；无匹配返回 ``[]``。
        """
        # ---- 1) subject 过滤：构造候选节点列表 + 保留 nid 顺序 ----
        candidates: list = []  # [(nid, node)]
        for nid, node in {**self.subjects, **self.humanities, **self.skills}.items():
            if subject:
                # subjects 用 "subject" 键，humanities 用 "dimension"，
                # skills 用 "category"——三处都要兼容
                if (node.get("subject") != subject
                        and node.get("dimension") != subject
                        and node.get("category") != subject):
                    continue
            candidates.append((nid, node))

        if not candidates:
            return []

        # ---- 2) 构造语料：每节点拼成一个文本 + tokenize ----
        def _node_text(nid: str, node: dict) -> str:
            """把节点的"语义相关字段"拼成一段可索引文本。缺字段自动兜底为空串。"""
            perspectives = node.get("tradition_perspectives", {}) or {}
            return " ".join([
                nid,
                str(node.get("definition", "") or ""),
                str(node.get("intuition", "") or ""),
                str(node.get("core_question", "") or ""),
                str(node.get("concept", "") or ""),
                str(node.get("name", "") or ""),
                " ".join(str(v) for v in perspectives.values()),
            ])

        corpus_texts = [_node_text(nid, node) for nid, node in candidates]

        # ---- 3) jieba 分词（参考 lib/ingest/retriever._tokenize） ----
        q_tokens = _kb_tokenize(query)

        # 无 token（纯标点/空白/无法分词）→ 回退子串匹配（防崩溃）
        if not q_tokens:
            return _kb_substring_fallback(query, candidates, subject=subject, top_k=top_k)

        # ---- 4) 懒构建 BM25Okapi 语料索引 ----
        try:
            from rank_bm25 import BM25Okapi  # type: ignore

            # 读取 BM25 参数（k1 / b）—— 配置化（B1：config/rag.json）
            try:
                _cfg = get_rag_config().get("retrieval", {})
                _k1 = float(_cfg.get("bm25_k1", 1.5))
                _b = float(_cfg.get("bm25_b", 0.75))
            except Exception:  # pragma: no cover - 配置不可用兜底
                _k1, _b = 1.5, 0.75

            tokenized_corpus = [_kb_tokenize(t) for t in corpus_texts]
            # rank_bm25 已知小语料库问题：corpus_size < 5 时 IDF 容易为 0，
            # 导致 BM25 分数全为 0 → 排序失效。修复：填充"通用语料" dummy docs
            # 到语料库（无关领域词），让 IDF 计算正常；最后只对真实候选取 scores。
            _BM25_PAD_TEXTS = (
                "雨伞 雨鞋 雨衣 防雨 衣物 穿着 户外 旅行 包 背包 行李 工具 锤子 钉子 螺丝",
                "音乐 钢琴 吉他 小提琴 鼓 乐器 演奏 音符 节拍 旋律 作曲 唱歌 演唱会",
                "水果 苹果 香蕉 橙子 西瓜 葡萄 草莓 樱桃 桃子 梨 菠萝 芒果",
                "运动 篮球 足球 排球 网球 跑步 游泳 健身 瑜伽 舞蹈 比赛 体育",
                "电影 导演 演员 剧本 摄影 剪辑 特效 影院 票房 观众 评分",
                "宠物 狗 猫 鸟 鱼 仓鼠 兔子 饲养 兽医 训练 玩具",
                "汽车 轮胎 引擎 方向盘 刹车 油 电动 充电 驾驶 公路 高速",
            )
            if len(tokenized_corpus) < len(_BM25_PAD_TEXTS) + 1:
                # 仅在候选较少时填充（避免在 ~100 doc 真实语料库下污染）
                while len(tokenized_corpus) < 5:
                    pad_text = _BM25_PAD_TEXTS[len(tokenized_corpus) % len(_BM25_PAD_TEXTS)]
                    tokenized_corpus.append(_kb_tokenize(pad_text))

            bm25 = BM25Okapi(tokenized_corpus, k1=_k1, b=_b)
            # 只取真实候选对应的 scores（padding 不进入结果）
            scores = bm25.get_scores(q_tokens)[: len(candidates)]
        except Exception as exc:  # pragma: no cover - rank_bm25 不可用兜底
            # BM25 构建失败（如 rank_bm25 未装 / jieba 不可用）→ 降级子串匹配
            return _kb_substring_fallback(query, candidates, subject=subject, top_k=top_k)

        # ---- 5) 排序 + 截断 top_k ----
        # 按 score 降序（同分按 nid 升序，保证稳定性）
        indexed = sorted(
            enumerate(scores),
            key=lambda x: (-x[1], candidates[x[0]][0]),
        )
        results = []
        for idx, sc in indexed[: max(1, int(top_k))]:
            # BM25Okapi 对完全无命中的 doc 返回 0 分；过滤掉 0 分结果（保持原行为）
            if sc <= 0:
                continue
            nid, node = candidates[idx]
            snippet = (node.get("definition") or node.get("core_question") or "")[:120]
            results.append({
                "concept_id": nid,
                "title": nid,
                "snippet": snippet,
                "relevance_score": float(sc),
                "difficulty": node.get("difficulty", 5),
            })
        return results

    def subject_catalog(self) -> dict:
        """返回学科目录（CLI 用）。"""
        subjects = {}
        for nid, node in self.subjects.items():
            subjects.setdefault(node["subject"], []).append(nid)
        return subjects

    def total_nodes(self) -> int:
        return len(self.subjects) + len(self.humanities) + len(self.strategies) + len(self.cases) + len(self.skills)

    # ------------------------------------------------------------------
    # 兼容垫片（v0.2/v0.3 旧接口：server.py、test_demo_real_llm.py 依赖）
    # ------------------------------------------------------------------
    def stats(self) -> dict:
        """旧接口：返回知识库统计（server.py /api/health 使用）。"""
        catalog = self.subject_catalog()
        skill_cats = {}
        for nid, node in self.skills.items():
            skill_cats.setdefault(node.get("category", "other"), []).append(nid)
        return {
            "subjects": len(self.subjects),
            "humanities": len(self.humanities),
            "strategies": len(self.strategies),
            "cases": len(self.cases),
            "skills": len(self.skills),
            "total": self.total_nodes(),
            "subject_breakdown": {k: len(v) for k, v in catalog.items()},
            "skill_breakdown": {k: len(v) for k, v in skill_cats.items()},
        }

    def search_subjects(self, query: str, subject: str = None) -> list:
        """旧接口：搜索学科节点（server.py /api/knowledge/search 使用）。"""
        return self.search(query, subject=subject, top_k=20)


if __name__ == "__main__":
    kb = KnowledgeBase()
    print(f"知识库节点总数: {kb.total_nodes()}")
    print(f"学科节点: {len(kb.subjects)} 个")
    print(f"素养节点: {len(kb.humanities)} 个")
    print(f"教学策略: {len(kb.strategies)} 个")
    print(f"案例: {len(kb.cases)} 个")
    print(f"\n学科分布: ")
    for subj, ids in kb.subject_catalog().items():
        print(f"  {subj}: {len(ids)} 个节点")
