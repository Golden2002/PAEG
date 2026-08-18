"""
PAEG v0.22.2 — 16 维正交学生特征框架（Student Trait Framework）
===========================================================

本模块是 PAEG 个体化（因材施教）能力的规范化核心。它把当前
`LearnerProfile`（人口学 + 世界观）+ `user_model`（动态对话推断）
+ `infer_bdi`（信念/愿望/意图）三处分散的字段，整合为一份
**彼此正交**的 16 维学生特征表。

设计原则
--------
1. **正交**：每维承载互不重叠的信息（例：`mastery` 持"已会/未会"
   证据，`engagement` 持"当下投入度"，`intention` 持"当前想做什么"）。
   任何一维的变化不会隐式修改另一维。
2. **可注入 prompt**：每维都映射到一段可读的字符串（`to_prompt`），
   可以按"分级"策略注入到 LLM 上下文（核心 5 维 / 触发注入 / 懒加载）。
3. **可持久化**：通过 `to_dict()` 输出 schema_version="2" 的字典，
   可作为 `LearnerProfile` 的可选扩展字段保存进 profile.json。
4. **向后兼容**：`from_learner()` 从旧版 `LearnerProfile` + 旧版
   `user_model` 字典提取，不要求调用方改造既有代码。
5. **无新依赖**：仅使用 dataclass 与 typing。

16 维一览
--------

1.  identity          — 身份（年级/年龄段）
2.  cognitive_style   — 认知通道（VARK）
3.  mastery           — 知识状态（按学科双向证据）
4.  study_goal        — 学习目标（合并 exam + specialty）
5.  world_view        — 价值观（4 元权重）
6.  emotion           — 情感状态
7.  motivation        — 学习动机（BDI desires 强化）
8.  belief            — 自我信念（BDI beliefs）
9.  intention         — 当前意图（会话级）
10. engagement        — 投入度（行为轴）
11. learning_rhythm   — 学习节奏（短/中/长）
12. time_preference   — 时段偏好（晨/午/晚/夜）
13. error_response    — 错误反应（脆弱/适应/韧性）
14. collaboration     — 协作偏好（独/双/群/混合）
15. media_preference  — 多媒体偏好（文/图/公式/音/视）
16. accessibility     — 可用性（视觉/听觉/读写/其他）

注入策略
--------
- **L1 核心 5 维**（始终注入）：identity / cognitive_style / mastery /
  study_goal / emotion
- **L2 触发注入**：engagement / motivation / belief / intention /
  error_response
- **L3 懒加载**：world_view / learning_rhythm / time_preference /
  collaboration / media_preference / accessibility
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ============================================================
# 1. 16 维定义表（供文档/测试引用）
# ============================================================

ORTHOGONAL_DEFS: List[Dict[str, str]] = [
    {
        "name": "identity",
        "type": "Demographic",
        "value_space": "{grade_level, age_band}",
        "orthogonality": (
            "描述'他是谁'（人口学），不携带能力/偏好/情绪信息；"
            "其他 15 维的取值都可在固定 identity 下自由变化。"
        ),
    },
    {
        "name": "cognitive_style",
        "type": "LearningChannel",
        "value_space": "{visual, auditory, reading, kinesthetic, mixed}",
        "orthogonality": (
            "描述'用哪种通道学最快'，不评价知识掌握度（→mastery），"
            "不评价情绪（→emotion），不评价时段（→time_preference）。"
        ),
    },
    {
        "name": "mastery",
        "type": "KnowledgeState",
        "value_space": "Dict[subject, {level, evidence_pos, evidence_neg, recency}]",
        "orthogonality": (
            "描述'已经会什么/不会什么'。"
            "正向证据（已掌握）不蕴含负面情绪（→emotion 独立），"
            "证据本身不携带学习节奏信息（→learning_rhythm 独立）。"
        ),
    },
    {
        "name": "study_goal",
        "type": "MotivationTarget",
        "value_space": "{exam?, specialty?, deadline?}",
        "orthogonality": (
            "描述'为谁而学/考什么'。"
            "只承载目标结构，不承载'现在感觉如何'（→emotion 独立）、"
            "不承载'想理解还是想拿分'（→motivation 独立）。"
        ),
    },
    {
        "name": "world_view",
        "type": "ValueBlend",
        "value_space": "Dict[1..4, weight]，权重和=1",
        "orthogonality": (
            "描述价值观倾向。它影响表达语气（由 world_view.select_tone"
            " 决定），但不动知识掌握度（→mastery 独立），"
            "不动情绪标签（→emotion 独立）。"
        ),
    },
    {
        "name": "emotion",
        "type": "AffectiveState",
        "value_space": "{anxious, engaged, neutral, withdrawn}",
        "orthogonality": (
            "描述'此刻情绪'。"
            "engagement 是行为（消息数/答题数），emotion 是心理，"
            "二者独立：可以 engaged-anxious（焦虑但坚持）"
            "或 neutral-withdrawn（安静但已离线）。"
        ),
    },
    {
        "name": "motivation",
        "type": "BDI-Desires",
        "value_space": (
            "primary ∈ {understand, score, avoid_shame, interest, help}"
        ),
        "orthogonality": (
            "描述'为什么而学'。与 study_goal 区分："
            "study_goal 是'考什么学校'（客观目标），"
            "motivation 是'想拿分还是想真懂'（心理取向）。"
        ),
    },
    {
        "name": "belief",
        "type": "BDI-Beliefs",
        "value_space": (
            "primary ∈ {self_doubt, subject_fear, growth, fixed}"
        ),
        "orthogonality": (
            "描述'学生相信自己能学会吗'。"
            "self_doubt 是对自身能力的判断，subject_fear 是对某学科的"
            "恐惧；二者可并存（自我贬低 + 害怕数学）。"
        ),
    },
    {
        "name": "intention",
        "type": "BDI-Intentions (session-level)",
        "value_space": (
            "{ask_question, seeking_help, about_to_give_up, "
            "verifying, self_testing}"
        ),
        "orthogonality": (
            "描述'当前这轮他打算做什么'。是会话级临时状态，"
            "不持久化到 belief/motivation；下一轮可被覆盖。"
        ),
    },
    {
        "name": "engagement",
        "type": "BehavioralMetric",
        "value_space": "{unknown, low, medium, high}",
        "orthogonality": (
            "纯行为信号（消息数/停留时间）。"
            "不与 emotion 耦合：可以 high-withdrawn（看似活跃但已失兴趣）"
            "或 low-engaged（消息少但精神高度集中）。"
        ),
    },
    {
        "name": "learning_rhythm",
        "type": "Pace",
        "value_space": "{short(<30m), medium(30-90m), long(>90m)}",
        "orthogonality": (
            "单次专注时长偏好。是节奏，与 cognitive_style 互补："
            "style 选通道，rhythm 选时长。"
        ),
    },
    {
        "name": "time_preference",
        "type": "Circadian",
        "value_space": "{morning, afternoon, evening, night, flexible}",
        "orthogonality": (
            "一天中偏好的学习时段。与 learning_rhythm 互补："
            "rhythm=多长，time_preference=何时。"
        ),
    },
    {
        "name": "error_response",
        "type": "AffectiveResponse",
        "value_space": "{fragile, adaptive, resilient, unknown}",
        "orthogonality": (
            "出错时的反应模式。fragile 受挫退缩，adaptive 调整继续，"
            "resilient 越挫越勇。与 emotion 互补："
            "emotion 是当下，error_response 是面对错误的态度倾向。"
        ),
    },
    {
        "name": "collaboration",
        "type": "SocialStyle",
        "value_space": "{solo, pair, group, mixed}",
        "orthogonality": (
            "协作偏好。是个体化教学安排中的社交层。"
            "不影响认知通道（→cognitive_style 独立）。"
        ),
    },
    {
        "name": "media_preference",
        "type": "MediaChannel",
        "value_space": "{text, diagram, formula, audio, video, mixed}",
        "orthogonality": (
            "内容呈现媒介偏好。与 cognitive_style 区分："
            "style=用哪种感官通道处理信息（接收），"
            "media_preference=希望材料以什么形式给出（呈现）。"
        ),
    },
    {
        "name": "accessibility",
        "type": "Accommodation",
        "value_space": (
            "List[{'kind': vision|hearing|literacy|other, 'note': str}]"
        ),
        "orthogonality": (
            "无障碍需求。是约束条件而非能力评价，"
            "不参与其他 15 维的取值逻辑，只在 to_prompt 阶段被翻译为"
            "教学约束（如：需要纯文字 / 需要音频转写）。"
        ),
    },
]


# 注入级别（L1=核心必注 / L2=触发注入 / L3=懒加载）
LEVEL_L1_CORE = 1
LEVEL_L2_TRIGGER = 2
LEVEL_L3_LAZY = 3

INJECTION_LEVELS: Dict[str, int] = {
    # L1 核心 5 维
    "identity": LEVEL_L1_CORE,
    "cognitive_style": LEVEL_L1_CORE,
    "mastery": LEVEL_L1_CORE,
    "study_goal": LEVEL_L1_CORE,
    "emotion": LEVEL_L1_CORE,
    # L2 触发注入
    "engagement": LEVEL_L2_TRIGGER,
    "motivation": LEVEL_L2_TRIGGER,
    "belief": LEVEL_L2_TRIGGER,
    "intention": LEVEL_L2_TRIGGER,
    "error_response": LEVEL_L2_TRIGGER,
    # L3 懒加载
    "world_view": LEVEL_L3_LAZY,
    "learning_rhythm": LEVEL_L3_LAZY,
    "time_preference": LEVEL_L3_LAZY,
    "collaboration": LEVEL_L3_LAZY,
    "media_preference": LEVEL_L3_LAZY,
    "accessibility": LEVEL_L3_LAZY,
}


# ============================================================
# 2. 16 维 dataclass
# ============================================================

_VALID_COGNITIVE = {"visual", "auditory", "reading", "kinesthetic", "mixed"}
_VALID_EMOTION = {"anxious", "engaged", "neutral", "withdrawn", "unknown"}
_VALID_ENGAGEMENT = {"unknown", "low", "medium", "high"}
_VALID_RHYTHM = {"short", "medium", "long", "unknown"}
_VALID_TIME = {"morning", "afternoon", "evening", "night", "flexible", "unknown"}
_VALID_ERROR = {"fragile", "adaptive", "resilient", "unknown"}
_VALID_COLLAB = {"solo", "pair", "group", "mixed", "unknown"}
_VALID_MEDIA = {"text", "diagram", "formula", "audio", "video", "mixed", "unknown"}
_VALID_MOTIVATION = {"understand", "score", "avoid_shame", "interest", "help", "unknown"}
_VALID_BELIEF = {"self_doubt", "subject_fear", "growth", "fixed", "unknown"}
_VALID_INTENTION = {
    "ask_question", "seeking_help", "about_to_give_up",
    "verifying", "self_testing", "unknown",
}


@dataclass
class StudentTrait:
    """16 维正交学生特征（v0.22.2 个体化核心）——每维彼此正交（信息不重叠）。

    设计目标：作为因材施教（teaching_tailored）的输入基础。
    - ``from_learner``：从现有 LearnerProfile + 旧版 user_model 字典无侵入地提取。
    - ``to_prompt``：按注入级别（L1/L2/L3）生成可注入 LLM 的文本。
    - ``to_dict``：持久化为 schema_version="2" 的 JSON 兼容字典。
    """

    # ---- L1 核心 5 维 ----
    identity: Dict[str, Any] = field(
        default_factory=lambda: {"grade_level": "unknown", "age_band": "unknown"}
    )
    """维度 1：身份（人口学轴）
    值空间：``{"grade_level": str, "age_band": str}``
    正交说明：仅描述'他是谁'，不携带能力/偏好/情绪。
    """

    cognitive_style: str = "unknown"
    """维度 2：认知通道
    值空间：``{visual, auditory, reading, kinesthetic, mixed, unknown}``
    正交说明：仅描述通道偏好，不评价掌握度（→mastery），不评价情绪（→emotion）。
    """

    native_language: str = "zh"
    """维度 2.5 / 第 17 维：用户母语（v0.22.3 ⭐ 跨语言教学）
    值空间：``{zh, en, fr, de, es, ja, ko, ...}``（ISO 639-1 或自定义）
    正交说明：仅描述'用哪种语言回复'，独立于认知通道/知识状态/情绪；
    该维直接控制 LLM 的回复语言——英语/法语用户用其母语获得教学。
    """

    mastery: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """维度 3：知识状态（按学科双向证据）
    值空间：``Dict[subject, {level, evidence_pos, evidence_neg, recency}]``
    正交说明：仅描述'已会/未会'，不携带学习节奏（→learning_rhythm）。
    """

    study_goal: Dict[str, Any] = field(
        default_factory=lambda: {"exam": None, "specialty": None, "deadline": None}
    )
    """维度 4：学习目标
    值空间：``{"exam": Optional[str], "specialty": Optional[str], "deadline": Optional[str]}``
    正交说明：合并自旧字段 target_exam+specialty_target；不承载'想拿分还是想真懂'（→motivation）。
    """

    emotion: str = "unknown"
    """维度 5：情感状态
    值空间：``{anxious, engaged, neutral, withdrawn, unknown}``
    正交说明：与 engagement（行为）和 motivation（取向）独立。
    """

    # ---- L2 触发注入 5 维 ----
    engagement: str = "unknown"
    """维度 10：投入度
    值空间：``{unknown, low, medium, high}``（由消息条数等行为信号推断）
    正交说明：纯行为信号，不与 emotion 耦合。
    """

    motivation: str = "unknown"
    """维度 7：学习动机（BDI desires 强化）
    值空间：``{understand, score, avoid_shame, interest, help, unknown}``
    正交说明：与 study_goal 区分——目标结构 vs 心理取向。
    """

    belief: str = "unknown"
    """维度 8：自我信念（BDI beliefs）
    值空间：``{self_doubt, subject_fear, growth, fixed, unknown}``
    正交说明：是对自身/学科能力的判断，与 mastery（已会/未会事实）独立。
    """

    intention: str = "unknown"
    """维度 9：当前意图（会话级）
    值空间：``{ask_question, seeking_help, about_to_give_up, verifying, self_testing, unknown}``
    正交说明：会话级临时状态，不持久化到 belief/motivation。
    """

    error_response: str = "unknown"
    """维度 13：错误反应
    值空间：``{fragile, adaptive, resilient, unknown}``
    正交说明：面对错误的态度倾向，与 emotion（当下）独立。
    """

    # ---- L3 懒加载 6 维 ----
    world_view: Dict[int, float] = field(
        default_factory=lambda: {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
    )
    """维度 5：价值观（4 元权重）
    值空间：``Dict[1,2,3,4, weight]``，权重和=1
    正交说明：仅影响语气（由 world_view.select_tone 决定）。
    """

    learning_rhythm: str = "unknown"
    """维度 11：学习节奏
    值空间：``{short(<30m), medium(30-90m), long(>90m), unknown}``
    正交说明：选时长；与 cognitive_style 互补（选通道）。
    """

    time_preference: str = "unknown"
    """维度 12：时段偏好
    值空间：``{morning, afternoon, evening, night, flexible, unknown}``
    正交说明：选何时；与 learning_rhythm 互补（选时长）。
    """

    collaboration: str = "unknown"
    """维度 14：协作偏好
    值空间：``{solo, pair, group, mixed, unknown}``
    正交说明：社交层偏好；不影响认知通道。
    """

    media_preference: str = "unknown"
    """维度 15：多媒体偏好
    值空间：``{text, diagram, formula, audio, video, mixed, unknown}``
    正交说明：选呈现形式；与 cognitive_style（接收通道）区分。
    """

    accessibility: List[Dict[str, str]] = field(default_factory=list)
    """维度 16：可用性
    值空间：``List[{kind: vision|hearing|literacy|other, note: str}]``
    正交说明：约束条件；不参与其他 15 维的取值逻辑。
    """

    # ============================================================
    # 3. 工厂：从旧 LearnerProfile + 旧 user_model 提取
    # ============================================================
    @classmethod
    def from_learner(
        cls,
        learner: Any,
        user_model: Optional[Dict[str, Any]] = None,
        bdi: Optional[Dict[str, Any]] = None,
    ) -> "StudentTrait":
        """从 LearnerProfile（及可选 user_model/bdi 字典）提取 16 维。

        兼容旧字段：
        - ``learner.target_exam`` + ``learner.specialty_target`` → ``study_goal``
        - ``learner.subjects_mastery`` → ``mastery``（带 evidence_pos）
        - ``user_model['knowledge_hints']`` / ``user_model['difficulty_signals']``
          → ``mastery`` 的 evidence_pos / evidence_neg
        - ``user_model['emotional_state']`` / ``user_model['engagement']`` → emotion / engagement
        - ``bdi['beliefs'][0]`` / ``bdi['desires'][0]`` / ``bdi['intentions'][0]``
          → belief / motivation / intention
        """
        t = cls()

        # 1. identity
        grade = getattr(learner, "grade_level", None) or "unknown"
        age = getattr(learner, "age", None)
        if age is None:
            age_band = "unknown"
        elif age < 12:
            age_band = "child"
        elif age < 16:
            age_band = "early_teen"
        elif age < 19:
            age_band = "teen"
        elif age < 23:
            age_band = "young_adult"
        elif age < 30:
            age_band = "adult"
        else:
            age_band = "senior"
        t.identity = {"grade_level": grade, "age_band": age_band, "age": age}

        # 1.5 native_language（v0.22.3 用户母语——控制 LLM 回复语言）
        _nl = getattr(learner, "native_language", None) or "zh"
        if isinstance(_nl, dict):
            _nl = _nl.get("code") or _nl.get("native_language") or "zh"
        t.native_language = str(_nl or "zh")

        # 2. cognitive_style
        cs = getattr(learner, "cognitive_style", None) or "unknown"
        t.cognitive_style = cs if cs in _VALID_COGNITIVE else "unknown"

        # 3. mastery（合并 subjects_mastery + 旧 user_model 双向证据）
        mastery: Dict[str, Dict[str, Any]] = {}
        for subj, m in (getattr(learner, "subjects_mastery", {}) or {}).items():
            mastery[subj] = {
                "level": m.get("level", 0.5) if isinstance(m, dict) else m,
                "evidence_pos": list(m.get("evidence_pos", [])) if isinstance(m, dict) else [],
                "evidence_neg": list(m.get("evidence_neg", [])) if isinstance(m, dict) else [],
                "recency": m.get("recency", "") if isinstance(m, dict) else "",
            }
        if user_model:
            for h in user_model.get("knowledge_hints", []):
                # 启发式：没有"学科"标注时归入"general"
                subj = "general"
                mastery.setdefault(subj, {
                    "level": 0.7, "evidence_pos": [], "evidence_neg": [], "recency": "",
                })
                mastery[subj]["evidence_pos"].append(h)
            for s in user_model.get("difficulty_signals", []):
                subj = "general"
                mastery.setdefault(subj, {
                    "level": 0.3, "evidence_pos": [], "evidence_neg": [], "recency": "",
                })
                mastery[subj]["evidence_neg"].append(s)
        t.mastery = mastery

        # 4. study_goal（合并 target_exam + specialty_target）
        t.study_goal = {
            "exam": getattr(learner, "target_exam", None),
            "specialty": getattr(learner, "specialty_target", None),
            "deadline": None,
        }

        # 5. world_view
        wv = getattr(learner, "world_view_blend", None)
        if isinstance(wv, dict) and wv:
            # 归一化
            total = sum(float(v) for v in wv.values()) or 1.0
            t.world_view = {int(k): round(float(v) / total, 3) for k, v in wv.items()}
        else:
            t.world_view = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}

        # 6. emotion（从 user_model.emotional_state）
        if user_model:
            em = user_model.get("emotional_state", "unknown")
            t.emotion = em if em in _VALID_EMOTION else "unknown"

        # 7. engagement（从 user_model.engagement）
        if user_model:
            eg = user_model.get("engagement", "unknown")
            t.engagement = eg if eg in _VALID_ENGAGEMENT else "unknown"

        # 8. motivation / belief / intention（从 bdi）
        if bdi:
            desires = bdi.get("desires", []) or []
            beliefs = bdi.get("beliefs", []) or []
            intentions = bdi.get("intentions", []) or []
            if desires and desires[0] in _VALID_MOTIVATION:
                t.motivation = desires[0]
            if beliefs and beliefs[0] in _VALID_BELIEF:
                t.belief = beliefs[0]
            if intentions and intentions[0] in _VALID_INTENTION:
                t.intention = intentions[0]

        return t

    # ============================================================
    # 4. 注入 prompt
    # ============================================================
    def to_prompt(
        self,
        levels: Optional[List[int]] = None,
        max_chars: int = 1200,
    ) -> str:
        """生成可注入 LLM 的文本（按注入级别筛选）。

        Args:
            levels: 注入级别集合；默认 ``[1, 2]``（核心+触发）。
                    传 ``[1, 2, 3]`` 注入全部 16 维；传 ``[1]`` 仅核心 5 维。
            max_chars: 输出最大字符数（硬上限，超出截断）。

        v0.23.0：动态扩展维（add_dimension 加入的字段）若其 INJECTION_LEVELS
        对应的级别被纳入 levels，则自动出现在输出末尾；新维默认 L3 懒加载。
        """
        if levels is None:
            levels = [LEVEL_L1_CORE, LEVEL_L2_TRIGGER]
        levels = set(levels)

        sections: List[str] = []
        # L1 核心 5 维 + 母语（v0.22.3 母语必须注入——控制回复语言）
        if LEVEL_L1_CORE in levels:
            sections.append(self._fmt_native_language())
            sections.append(self._fmt_identity())
            sections.append(self._fmt_cognitive_style())
            sections.append(self._fmt_mastery())
            sections.append(self._fmt_study_goal())
            sections.append(self._fmt_emotion())
        # L2 触发注入 5 维
        if LEVEL_L2_TRIGGER in levels:
            sections.append(self._fmt_engagement())
            sections.append(self._fmt_motivation())
            sections.append(self._fmt_belief())
            sections.append(self._fmt_intention())
            sections.append(self._fmt_error_response())
        # L3 懒加载 6 维
        if LEVEL_L3_LAZY in levels:
            sections.append(self._fmt_world_view())
            sections.append(self._fmt_learning_rhythm())
            sections.append(self._fmt_time_preference())
            sections.append(self._fmt_collaboration())
            sections.append(self._fmt_media_preference())
            sections.append(self._fmt_accessibility())

        # v0.23.0：动态扩展维——按 INJECTION_LEVELS 自动注入
        _core_names = {
            "native_language", "identity", "cognitive_style", "mastery",
            "study_goal", "emotion", "engagement", "motivation", "belief",
            "intention", "error_response", "world_view", "learning_rhythm",
            "time_preference", "collaboration", "media_preference",
            "accessibility", "schema_version",  # schema_version 在 to_dict
        }
        # 注：to_dict 调用 asdict 会包含所有 dataclass 字段（含 schema_version 不会，
        # 因为它不是 field；所以这里只跳过 17 个原生字段 + schema_version）
        for k, lvl in INJECTION_LEVELS.items():
            if k in _core_names:
                continue  # 已在上方格式化
            if lvl not in levels:
                continue
            if k not in self.__dict__:
                continue
            v = self.__dict__[k]
            # 跳过 None / 空 list / 空 dict——它们没信息量
            if v is None:
                continue
            if isinstance(v, (list, dict)) and len(v) == 0:
                continue
            sections.append(f"- {k}（动态扩展维）：{self._fmt_dynamic(k, v)}")

        text = "## 学生个体化特征（16 维正交框架）\n" + "\n".join(s for s in sections if s)
        if len(text) > max_chars:
            text = text[: max_chars - 3] + "..."
        return text

    # ---- 维度格式化（私有） ----
    def _fmt_native_language(self) -> str:
        """母语格式化——直接指令 LLM 用该语言回复。"""
        _lang_names = {
            "zh": "中文", "en": "英语", "fr": "法语", "de": "德语",
            "es": "西班牙语", "ja": "日语", "ko": "韩语",
        }
        lang = self.native_language or "zh"
        name = _lang_names.get(lang, lang)
        return f"- 回复语言（v0.22.3 必须遵守）：请用【{name}】回复学生（用户母语为 {lang}）"

    def _fmt_identity(self) -> str:
        ident = self.identity or {}
        return f"- 身份：{ident.get('grade_level', 'unknown')}, {ident.get('age_band', 'unknown')}"

    def _fmt_cognitive_style(self) -> str:
        return f"- 认知通道：{self.cognitive_style}"

    def _fmt_mastery(self) -> str:
        if not self.mastery:
            return "- 知识状态：未知（暂无证据）"
        lines = ["- 知识状态："]
        for subj, m in list(self.mastery.items())[:4]:
            pos = len(m.get("evidence_pos", []))
            neg = len(m.get("evidence_neg", []))
            lines.append(
                f"  · {subj}: level={m.get('level', 0):.2f}, "
                f"正证据={pos}, 负证据={neg}"
            )
        return "\n".join(lines)

    def _fmt_study_goal(self) -> str:
        g = self.study_goal or {}
        exam = g.get("exam") or "无"
        spec = g.get("specialty") or "无"
        dl = g.get("deadline") or "无"
        return f"- 学习目标：考试={exam}, 专业方向={spec}, 截止={dl}"

    def _fmt_emotion(self) -> str:
        return f"- 情感状态：{self.emotion}"

    def _fmt_engagement(self) -> str:
        return f"- 投入度：{self.engagement}"

    def _fmt_motivation(self) -> str:
        return f"- 学习动机：{self.motivation}"

    def _fmt_belief(self) -> str:
        return f"- 自我信念：{self.belief}"

    def _fmt_intention(self) -> str:
        return f"- 当前意图：{self.intention}"

    def _fmt_error_response(self) -> str:
        return f"- 错误反应：{self.error_response}"

    def _fmt_world_view(self) -> str:
        wv = self.world_view or {}
        items = ", ".join(f"{k}={v:.2f}" for k, v in sorted(wv.items()))
        return f"- 价值观：[{items}]"

    def _fmt_learning_rhythm(self) -> str:
        return f"- 学习节奏：{self.learning_rhythm}"

    def _fmt_time_preference(self) -> str:
        return f"- 时段偏好：{self.time_preference}"

    def _fmt_collaboration(self) -> str:
        return f"- 协作偏好：{self.collaboration}"

    def _fmt_media_preference(self) -> str:
        return f"- 多媒体偏好：{self.media_preference}"

    def _fmt_accessibility(self) -> str:
        if not self.accessibility:
            return "- 可用性：默认（无特殊需求）"
        items = "; ".join(
            f"{a.get('kind', '?')}:{a.get('note', '')}" for a in self.accessibility
        )
        return f"- 可用性：{items}"

    # ============================================================
    # 5. 持久化（schema_version="2"）
    # ============================================================
    SCHEMA_VERSION = "2"

    def to_dict(self) -> Dict[str, Any]:
        """输出 schema_version="2" 的字典（供 profile.json 扩展）。

        不修改 LearnerProfile 现有字段；调用方可把结果存为
        ``learner_profile['student_trait_v2'] = trait.to_dict()``。

        v0.23.0：包含运行时动态扩展维（add_dimension 加入的字段），
        用 ``self.__dict__`` 合并到 ``asdict`` 输出后。
        """
        d = asdict(self)
        # 合并 __dict__ 中不在原生 dataclass 字段里的动态维（如 interests、personal_facts）
        _declared_fields = set(d.keys())
        for k, v in self.__dict__.items():
            if k not in _declared_fields and not k.startswith("_"):
                d[k] = v
        d["schema_version"] = self.SCHEMA_VERSION
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StudentTrait":
        """从 ``to_dict`` 输出的字典还原 StudentTrait。

        v0.23.0：原生字段用 ``__init__`` 传入；非原生字段（动态维）写入 ``__dict__``。
        这样 ``update_from_dialogue`` / ``add_dimension`` 加入的运行时字段在
        ``to_dict → from_dict`` 来回后仍保留。
        """
        if d.get("schema_version") != cls.SCHEMA_VERSION:
            # 兼容缺失/未知版本：尽可能加载
            pass
        obj = cls.__new__(cls)  # 绕过 __init__（避免动态字段被丢弃）
        for k, v in d.items():
            if k == "schema_version":
                continue
            try:
                object.__setattr__(obj, k, v)
            except Exception:
                obj.__dict__[k] = v
        return obj

    def to_json(self, **kw: Any) -> str:
        """便捷 JSON 序列化。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, **kw)

    # ============================================================
    # 6. v0.23.0 ⭐ 动态更新方法（Individuality 持久化闭环核心）
    # ============================================================
    def update_from_dialogue(self, llm_modeled: Dict[str, Any]) -> "StudentTrait":
        """把 LLM 建模结果（6 类）合并进画像。

        合并规则（确定性映射，v0.23.0）：
        - ``knowledge_strengths`` → mastery[subject].evidence_pos（每条作为正向证据）
        - ``knowledge_gaps`` → mastery[subject].evidence_neg（每条作为负向证据）
        - ``emotional_tendency`` → emotion（值域白名单过滤，否则保持原值）
        - ``learning_style`` → cognitive_style（仅当当前为 unknown 时才覆盖，避免
          覆盖显式设定）
        - ``motivation`` → motivation（值域白名单过滤）
        - ``interests`` → self.interests（新增第 18 维，可扩展）；list 合并去重

        返回 self（链式 + 显式 self-return，方便调用方写
        ``trait = trait.update_from_dialogue(modeled)``）。
        """
        if not isinstance(llm_modeled, dict):
            return self

        # 1) knowledge_strengths → mastery[subject].evidence_pos
        for subj in llm_modeled.get("knowledge_strengths") or []:
            if not isinstance(subj, str) or not subj.strip():
                continue
            m = self.mastery.setdefault(subj, {
                "level": 0.7,
                "evidence_pos": [],
                "evidence_neg": [],
                "recency": "",
            })
            note = f"LLM建模:{subj}"
            if note not in m["evidence_pos"]:
                m["evidence_pos"].append(note)

        # 2) knowledge_gaps → mastery[subject].evidence_neg
        for subj in llm_modeled.get("knowledge_gaps") or []:
            if not isinstance(subj, str) or not subj.strip():
                continue
            m = self.mastery.setdefault(subj, {
                "level": 0.3,
                "evidence_pos": [],
                "evidence_neg": [],
                "recency": "",
            })
            note = f"LLM建模:{subj}是薄弱点"
            if note not in m["evidence_neg"]:
                m["evidence_neg"].append(note)
            # 薄弱点降低 level（封顶 0.3，防止被正向证据拉爆）
            m["level"] = min(m.get("level", 0.5), 0.3)

        # 3) emotional_tendency → emotion（白名单过滤）
        em = llm_modeled.get("emotional_tendency")
        if isinstance(em, str) and em in _VALID_EMOTION:
            self.emotion = em

        # 4) learning_style → cognitive_style（仅 unknown 时覆盖）
        ls = llm_modeled.get("learning_style")
        if isinstance(ls, str) and ls in _VALID_COGNITIVE:
            if self.cognitive_style in ("unknown", None, ""):
                self.cognitive_style = ls

        # 5) motivation → motivation（白名单过滤）
        mot = llm_modeled.get("motivation")
        if isinstance(mot, str) and mot in _VALID_MOTIVATION:
            self.motivation = mot

        # 6) interests → self.interests（第 18 维，list 合并去重）
        interests_in = llm_modeled.get("interests") or []
        if isinstance(interests_in, list) and interests_in:
            current = list(getattr(self, "interests", []) or [])
            seen = {str(x).strip().lower() for x in current if x}
            for it in interests_in:
                if not isinstance(it, str):
                    continue
                key = it.strip().lower()
                if not key or key in seen:
                    continue
                current.append(it.strip())
                seen.add(key)
            self.interests = current

        return self

    def update_from_facts(self, facts: list) -> "StudentTrait":
        """把 extract_user_facts 提取的个人事实并入 self.personal_facts。

        去重（大小写不敏感），保留出现顺序；事实不直接映射到 16 维的某一维——
        它们是"记忆锚点"（"我叫张三"/"我喜欢蓝绿色"），用于 LLM 引用而非建模。

        返回 self（链式 + 显式 self-return）。
        """
        if not facts:
            return self
        current = list(getattr(self, "personal_facts", []) or [])
        seen = {str(f).strip().lower() for f in current if f}
        for f in facts:
            if not isinstance(f, str):
                continue
            txt = f.strip()
            if not txt:
                continue
            key = txt.lower()
            if key in seen:
                continue
            current.append(txt)
            seen.add(key)
        self.personal_facts = current
        return self

    def add_dimension(self, name: str, value: Any,
                      orthogonality: str = "") -> None:
        """动态扩展维度（v0.23.0 � 框架可扩展性核心）。

        三件事同时做：
        1. ``ORTHOGONAL_DEFS`` 追加新维定义（供文档/测试引用）
        2. ``INJECTION_LEVELS`` 追加新维注入级别（默认 L3 懒加载——新增维不主动注入）
        3. dataclass 用 ``__dict__`` 动态加字段——但 dataclass 不允许 ``__dict__`` 写入，
           实际用 ``object.__setattr__`` 绕开 frozen；后续 ``to_prompt`` 会自动读取新维
           并格式化输出（若字段名为 ``_fmt_<name>`` 则调用，否则用通用 ``str()`` 回退）

        维度名重复：值覆盖 + ORTHOGONAL_DEFS 同名条目追加；不抛错（幂等）。

        参数：
        - ``name``：维度名（必须是非空 ASCII/字母数字下划线；用作 attribute key）
        - ``value``：维度值（任意类型；list/dict/str/数字均可）
        - ``orthogonality``：正交说明（可选；写入 ORTHOGONAL_DEFS）

        返回 None（in-place 修改；调用方负责保存）。
        """
        if not name or not isinstance(name, str):
            return
        key = name.strip()
        if not key:
            return
        # 1) 写 dataclass 实例字段（绕 dataclass frozen 用 object.__setattr__）
        try:
            object.__setattr__(self, key, value)
        except Exception:
            # 极个别 dataclass 配置问题——直接塞 __dict__
            self.__dict__[key] = value
        # 2) ORTHOGONAL_DEFS 追加（同名允许：再追加一条）
        ORTHOGONAL_DEFS.append({
            "name": key,
            "type": "DynamicExtension",
            "value_space": f"任意（运行时 add_dimension 注入：{type(value).__name__}）",
            "orthogonality": orthogonality or "运行时扩展维（v0.23.0）；与其他维正交关系由调用方保证",
        })
        # 3) INJECTION_LEVELS 默认 L3（懒加载——不污染 L1/L2）
        if key not in INJECTION_LEVELS:
            INJECTION_LEVELS[key] = LEVEL_L3_LAZY
        return None

    def _fmt_dynamic(self, name: str, value: Any) -> str:
        """动态维格式化（to_prompt 自动调用）。

        优先级：
        1) 若实例有 ``_fmt_<name>`` 方法，调用它
        2) 否则按值类型通用格式化：list → 'a/b/c'；dict → 'k=v;k=v'；其他 → str()
        """
        fmt = getattr(self, f"_fmt_{name}", None)
        if callable(fmt):
            try:
                return str(fmt())
            except Exception:
                pass
        if isinstance(value, list):
            return ", ".join(str(v) for v in value[:5]) or "（空）"
        if isinstance(value, dict):
            return "; ".join(f"{k}={v}" for k, v in list(value.items())[:5]) or "（空）"
        return str(value)


# ============================================================
# 7. 自测入口（python student_trait.py）
# ============================================================
if __name__ == "__main__":
    # 1) 构造最小 LearnerProfile-like 对象
    class _LP:
        id = "s_demo"
        nickname = "小明"
        grade_level = "high_school"
        age = 17
        cognitive_style = "visual"
        subjects_mastery = {
            "math": {"level": 0.6, "evidence_pos": ["月考85分"], "evidence_neg": [], "recency": "2026-07"},
            "english": {"level": 0.4, "evidence_pos": [], "evidence_neg": ["作文被标错"], "recency": "2026-08"},
        }
        world_view_blend = {1: 0.20, 2: 0.35, 3: 0.35, 4: 0.10}
        target_exam = "高考"
        specialty_target = "计算机"
        self_description = "我数学比较好但英语有点怕"

    learner = _LP()
    user_model = {
        "expression_style": "neutral",   # 死字段——被忽略
        "knowledge_hints": ["自述: 擅长"],
        "difficulty_signals": ["对话: 表达理解困难"],
        "emotional_state": "anxious",
        "engagement": "medium",
    }
    bdi = {
        "beliefs": ["subject_fear", "growth"],
        "desires": ["score"],
        "intentions": ["seeking_help"],
    }

    trait = StudentTrait.from_learner(learner, user_model=user_model, bdi=bdi)

    print("=" * 60)
    print("【16 维 StudentTrait（from_learner 转换结果）】")
    print("=" * 60)
    for k, v in trait.to_dict().items():
        print(f"  {k:18s} = {v}")

    print()
    print("=" * 60)
    print("【to_prompt(level=L1+L2，默认）】")
    print("=" * 60)
    print(trait.to_prompt(levels=[1, 2]))

    print()
    print("=" * 60)
    print("【to_prompt(level=L1+L2+L3，全量）】")
    print("=" * 60)
    print(trait.to_prompt(levels=[1, 2, 3]))

    print()
    print("=" * 60)
    print("【ORTHOGONAL_DEFS 一览（16 维）】")
    print("=" * 60)
    for i, d in enumerate(ORTHOGONAL_DEFS, 1):
        print(f"  {i:2d}. {d['name']:20s} | {d['type']:20s} | {d['value_space']}")
