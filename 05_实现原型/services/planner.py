# -*- coding: utf-8 -*-
"""v0.68 ⭐ services/planner.py —— 学习计划工作流核心（Oracle 架构设计）

为"对某领域感兴趣、想要学习计划和资源"的用户生成完整学习计划：
阶段划分（确定性骨架）+ 里程碑内容（LLM 个性化）+ 资源推荐（复用统一资源门面）。

设计原则（呼应元能力 §1.1 指挥 LLM 而非替代 LLM）：
- 阶段骨架（数量/名称/周数/模板）→ 确定性规则（可测试、可复现）
- 里程碑内容/资源排序/个性化 → LLM（擅长语义与个性化）

与 method 的关系：学习计划是 method 模式的"子意图"（is_study_plan_intent 命中时
走本工作流），不是新 mode——复用 method 模块门控、会话落盘、语言规范链路。
"""
from __future__ import annotations

import datetime as _dt
import re
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal


# ---------------------------------------------------------------------------
# 数据结构（StudyPlan JSON Schema）
# ---------------------------------------------------------------------------

@dataclass
class Resource:
    """单个学习资源。"""
    kind: Literal["book", "video", "course", "paper", "tool", "note", "link"]
    title: str
    url_or_path: str = ""      # 联网 URL 或 Library 路径
    source: str = "kb"         # kb | web | user_library | facts
    est_hours: float = 0.0
    difficulty: int = 3        # 1-5
    snippet: str = ""


@dataclass
class Milestone:
    """阶段内的一个里程碑（可点击"开始学习"切 teach）。"""
    id: str = ""
    title: str = ""
    deliverables: List[str] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)
    hours_estimate: float = 0.0
    checkpoint: str = ""


@dataclass
class Phase:
    """学习计划的一个阶段（基础/强化/实战…）。"""
    id: str = ""
    name: str = ""
    goal: str = ""
    duration_days: int = 14
    weekly_hours: float = 6.0
    milestones: List[Milestone] = field(default_factory=list)


@dataclass
class StudyPlan:
    """完整学习计划。"""
    plan_id: str = ""
    learner_id: str = ""
    topic: str = ""
    subject: str = "general"
    goal: str = "系统学习"               # v0.68 修复：summary 渲染引用
    deadline: Optional[str] = None
    grade_level: str = "high_school"
    total_weeks: int = 8
    weekly_hours: float = 6.0
    phases: List[Phase] = field(default_factory=list)
    summary_md: str = ""
    created_at: str = ""
    personalization_notes: List[str] = field(default_factory=list)


@dataclass
class PlanInputs:
    """从用户输入 + 画像抽取的计划参数。"""
    topic: str = ""
    subject: str = "general"
    raw_input: str = ""             # v0.68 原始输入（原话给 LLM，LM 优先）
    deadline: Optional[str] = None      # ISO date；缺省按 8 周
    weekly_hours: float = 6.0           # 缺省用画像节奏
    prior_knowledge: str = ""           # 从 self_description / 历史提取
    goal: str = "系统学习"              # 系统学习 / 备考 / 入门


# ---------------------------------------------------------------------------
# 阶段模板（确定性）
# ---------------------------------------------------------------------------

# 按主题类型选择阶段模板：基础 → 强化 → 实战（默认），语言类、备考类有特化
_PHASE_TEMPLATES = {
    "default": ["基础建立", "强化提升", "实战应用"],
    "language": ["输入积累", "输出练习", "实战交流", "复盘精进"],
    "exam": ["基础梳理", "专题强化", "真题冲刺"],
}

_LANG_HINTS = ("英语", "法语", "德语", "日语", "语言", "外语", "雅思", "托福", "口语")
_EXAM_HINTS = ("高考", "考研", "考试", "备考", "期末", "竞赛", "证书", "资格")


def select_phase_template(topic: str, subject: str = "") -> str:
    """确定性：按主题选择阶段模板 key。"""
    t = f"{topic} {subject}"
    if any(k in t for k in _LANG_HINTS):
        return "language"
    if any(k in t for k in _EXAM_HINTS):
        return "exam"
    return "default"


def decide_phase_count(deadline_days: Optional[int], weekly_hours: float) -> int:
    """确定性：按期限与每周可用小时决定阶段数（2-4）。"""
    if deadline_days is None:
        return 3
    weeks = max(1.0, deadline_days / 7.0)
    if weeks <= 3:
        return 2
    if weeks <= 10:
        return 3
    return 4


def _parse_deadline(text: str) -> Optional[str]:
    """从输入解析截止日期。支持：3 个月/8 周/11月/今年底。返回 ISO date。"""
    t = (text or "").strip()
    today = _dt.date.today()
    m = re.search(r"(\d+)\s*(个月|月)", t)
    if m:
        n = int(m.group(1))
        d = today + _dt.timedelta(days=30 * n)
        return d.isoformat()
    m = re.search(r"(\d+)\s*周", t)
    if m:
        d = today + _dt.timedelta(days=7 * int(m.group(1)))
        return d.isoformat()
    m = re.search(r"(\d+)\s*天", t)
    if m:
        d = today + _dt.timedelta(days=int(m.group(1)))
        return d.isoformat()
    # "X月底/今年底/年底" → 12-31
    if "年底" in t or "年末" in t:
        return _dt.date(today.year, 12, 31).isoformat()
    # "今年11月" / "11月" → 今年（若已过则明年）
    m = re.search(r"(今年|明年)?(\d{1,2})月", t)
    if m:
        try:
            _y = today.year
            if m.group(1) == "明年":
                _y += 1
            _mo = int(m.group(2))
            if _mo < today.month and m.group(1) != "明年":
                _y += 1
            return _dt.date(_y, _mo, 1).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{4})[年/-](\d{1,2})", t)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), 1).isoformat()
        except ValueError:
            return None
    return None


def _estimate_weekly_hours(learner) -> float:
    """从画像估计每周可用小时（缺省 6h）。"""
    try:
        qa = getattr(learner, "questionnaire_answers", None) or {}
        raw = str(qa.get("学习时段") or qa.get("每周学习时间") or "")
        m = re.search(r"(\d+(?:\.\d+)?)", raw)
        if m:
            return max(2.0, min(30.0, float(m.group(1))))
    except Exception:
        pass
    return 6.0


def extract_plan_inputs(text: str, learner, subject: str = "") -> PlanInputs:
    """从输入 + 画像抽取计划参数。

    v0.68 ⭐ LM 优先简化（用户指示"不需要分词"）：topic 不做复杂分词，
    直接取原话（去最外层意图词前缀）；真正的主题理解交给 LLM
    （design_phases 的 system prompt 里给 LLM 原话让它设计阶段内容）。
    """
    t = (text or "").strip()
    # topic：仅去最外层意图词前缀（"我想/请帮我/对…感兴趣"），保留原话核心
    topic = re.sub(r"^(我想|我要|打算|准备|计划|想|请|麻烦你?|帮我?|给我?|对|关于)[，,、\s]*", "", t)
    # 去掉"该怎么样入门/如何学习/怎么做规划"等尾部询问壳（轻量，非分词）
    topic = re.sub(r"[，,。？！]?(该?怎么样|该怎么|如何|怎样|怎么).{0,8}(入门|开始|学习|学|规划|计划|入手|安排).?$", "", topic)
    topic = topic.strip("，。？！,?! 的：:；;")[:40] or t[:40]
    goal = "备考" if _EXAM_HINTS and any(k in f"{topic} {subject}" for k in _EXAM_HINTS) else "系统学习"
    return PlanInputs(
        topic=topic,
        subject=subject or "general",
        raw_input=t,
        deadline=_parse_deadline(t),
        weekly_hours=_estimate_weekly_hours(learner),
        prior_knowledge=str(getattr(learner, "self_description", "") or "")[:200],
        goal=goal,
    )


# ---------------------------------------------------------------------------
# 资源聚合（复用统一资源门面）
# ---------------------------------------------------------------------------

def aggregate_resources(topic: str, subject: str, learner, llm=None,
                        include_web: bool = True) -> List[Resource]:
    """确定性编排：复用 services.library.collect_all_resources 一次性聚合 4 路
    （用户物料/知识库/facts/联网），再解析为 Resource 列表。

    ★ 只调一次门面（避免重复检索）——Oracle 架构约束。
    """
    _resources: List[Resource] = []
    _uid = str(getattr(learner, "id", ""))
    try:
        from services.library import collect_all_resources
        _blk = collect_all_resources(_uid, topic=topic, llm=llm,
                                     subject=subject, include_web=include_web)
    except Exception as _e:
        print(f"[planner] collect_all_resources 失败: {_e}")
        _blk = {}
    _has = bool(_blk and _blk.get("has_any"))

    # 知识库命中
    if _blk.get("kb_hits"):
        _resources.append(Resource(
            kind="note", title=f"知识库：{topic}", source="kb",
            snippet=str(_blk["kb_hits"])[:120], difficulty=2))
    # 用户物料
    if _blk.get("user_assets"):
        _resources.append(Resource(
            kind="note", title="用户资料库", source="user_library",
            snippet=str(_blk["user_assets"])[:120], difficulty=1))
    # facts
    if _blk.get("facts"):
        _resources.append(Resource(
            kind="paper", title=f"事实资料：{topic}", source="facts",
            snippet=str(_blk["facts"])[:120], difficulty=3))
    # 联网（每条 web 结果一个资源）
    if _blk.get("web_hits"):
        _resources.append(Resource(
            kind="link", title=f"网络资料：{topic}", source="web",
            url_or_path="", snippet=str(_blk["web_hits"])[:150], difficulty=3))
    # 兜底：零命中也给一个引导资源
    if not _resources:
        _resources.append(Resource(
            kind="note", title=f"入门资料：{topic}", source="kb",
            snippet="先从概念建立直觉，再结合例题与练习巩固。", difficulty=1))
    return _resources


# ---------------------------------------------------------------------------
# LLM 阶段设计（个性化）
# ---------------------------------------------------------------------------

def _load_study_planner_skill() -> str:
    """读取 study-planner SKILL.md 全文（激活 Skill L2）。"""
    try:
        import os as _os
        _p = _os.path.join(_os.path.dirname(__file__), "..", "skills",
                           "study-planner", "SKILL.md")
        with open(_p, "r", encoding="utf-8") as _f:
            return _f.read()
    except Exception:
        return ""


def design_phases(inputs: PlanInputs, resources: List[Resource],
                  learner, llm) -> List[Phase]:
    """LLM 主导：基于确定性骨架（阶段数+模板+资源清单+画像）生成里程碑内容。

    返回 Phase 列表（每阶段含 2-4 个里程碑 + 每个里程碑的 deliverables/checkpoint）。
    """
    _tk = select_phase_template(inputs.topic, inputs.subject)
    _phase_names = _PHASE_TEMPLATES[_tk]
    _n = decide_phase_count(
        (inputs.deadline and (_dt.date.fromisoformat(inputs.deadline) - _dt.date.today()).days)
        if inputs.deadline else None,
        inputs.weekly_hours)
    # 阶段名裁剪/扩充到 _n 个
    if len(_phase_names) >= _n:
        _names = _phase_names[:_n]
    else:
        _names = _phase_names + [f"深化进阶{i}" for i in range(1, _n - len(_phase_names) + 1)]

    _res_str = "\n".join(f"- {r.title}（{r.source}）" for r in resources[:6]) or "- 暂无"
    _skill = _load_study_planner_skill()
    _grade = getattr(learner, "grade_level", "high_school")
    _mastery = getattr(learner, "subjects_mastery", None) or {}
    _mastery_str = "、".join(f"{k}:{v:.2f}" for k, v in list(_mastery.items())[:5]) or "未知"

    system = (
        "你是 Émile Novis，一位精通教育学的学习规划师。请为学习者设计一份学习计划的阶段内容。\n"
        f"用户原话：{inputs.raw_input or inputs.topic}\n"
        f"主题：{inputs.topic}；学科：{inputs.subject}；目标：{inputs.goal}；学段：{_grade}\n"
        f"每周可用：{inputs.weekly_hours:.0f}h；画像掌握度：{_mastery_str}\n"
        f"已有基础/自述：{(inputs.prior_knowledge[:150] or '未提供')}\n"
        f"可用资源：\n{_res_str}\n\n"
        f"阶段骨架（共 {_n} 个阶段）：{', '.join(_names)}\n"
        "请严格输出 JSON 数组，每个阶段："
        '{"name": 阶段名, "goal": 阶段目标(20-40字), "duration_days": 天数, "weekly_hours": 每周小时, '
        '"milestones": [{"title": 里程碑(15-30字), "deliverables": [3-4个可检验交付物], '
        '"hours_estimate": 小时数, "checkpoint": 检验方式}]}\n'
        "每阶段 2-3 个里程碑。时长分配：基础阶段略长，实战阶段略短。"
        "输出必须是合法 JSON 数组，不要输出任何其他文字。"
    )
    if _skill:
        system = f"参考技能：\n{_skill}\n\n" + system

    _user = f"请为这个学习请求设计 {_n} 阶段学习计划：{inputs.raw_input or inputs.topic}"
    _phases: List[Phase] = []
    try:
        from subagents import _safe_chat
        # v0.68 重试机制：DeepSeek 偶发空响应（已知 4/5 成功率），重试 3 次
        # v0.68 放开 max_tokens：思考型模型需要大 token 空间（思考链+内容），4000 保障完整输出
        _raw = ""
        for _attempt in range(3):
            _raw = _safe_chat(llm, system, _user, max_tokens=4000)
            if _raw and _raw.strip():
                break
            if _attempt < 2:
                import time as _t
                _t.sleep(1)
        _parsed = _try_parse_json(_raw)
        for _i, _ph in enumerate(_parsed or []):
            if not isinstance(_ph, dict):
                continue
            _ms = []
            for _j, _m in enumerate(_ph.get("milestones") or []):
                if not isinstance(_m, dict):
                    continue
                _ms.append(Milestone(
                    id=f"m{_i+1}.{_j+1}",
                    title=str(_m.get("title") or f"里程碑{_j+1}"),
                    deliverables=[str(x) for x in (_m.get("deliverables") or [])][:4],
                    hours_estimate=float(_m.get("hours_estimate") or 2.0),
                    checkpoint=str(_m.get("checkpoint") or "自测"),
                ))
            _phases.append(Phase(
                id=f"phase_{_i+1}",
                name=str(_ph.get("name") or _names[_i] if _i < len(_names) else f"阶段{_i+1}"),
                goal=str(_ph.get("goal") or f"{_names[_i]}阶段的核心目标"),
                duration_days=int(_ph.get("duration_days") or 14),
                weekly_hours=float(_ph.get("weekly_hours") or inputs.weekly_hours),
                milestones=_ms or [Milestone(id=f"m{_i+1}.1", title=f"{_names[_i]}核心任务",
                                             deliverables=["建立该阶段基础"], checkpoint="自测")],
            ))
    except Exception as _e:
        print(f"[planner] design_phases LLM 失败，回退确定性模板: {_e}")
    # 兜底：LLM 失败 → 确定性阶段
    if not _phases:
        _phases = _fallback_phases(_names, inputs)
    return _phases


def _try_parse_json(raw: str):
    """宽松解析 LLM 输出的 JSON 数组（容忍代码围栏/前后缀）。"""
    import json
    if not raw:
        return None
    t = raw.strip()
    t = re.sub(r"^```(json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    # 截取第一个 [ 到最后一个 ]
    a, b = t.find("["), t.rfind("]")
    if a >= 0 and b > a:
        t = t[a:b + 1]
    try:
        return json.loads(t)
    except Exception:
        # 容错：逐对象解析
        try:
            import ast
            return ast.literal_eval(t)
        except Exception:
            return None


def _fallback_phases(names: List[str], inputs: PlanInputs) -> List[Phase]:
    """确定性兜底阶段（LLM 失败时）。"""
    _phases = []
    for _i, _n in enumerate(names):
        _phases.append(Phase(
            id=f"phase_{_i+1}", name=_n,
            goal=f"{_n}阶段：掌握{inputs.topic}的核心基础",
            duration_days=14 if _i == 0 else 10,
            weekly_hours=inputs.weekly_hours,
            milestones=[Milestone(id=f"m{_i+1}.1", title=f"{_n}核心任务",
                                  deliverables=[f"完成{_n}阶段学习", "做一次自测"], checkpoint="自测 80%")],
        ))
    return _phases


# ---------------------------------------------------------------------------
# 汇总：构建完整学习计划
# ---------------------------------------------------------------------------

def build_study_plan(text: str, learner, subject: str = "", llm=None) -> StudyPlan:
    """主入口：输入 → 学习计划（含 summary_md 供前端渲染）。"""
    _inputs = extract_plan_inputs(text, learner, subject)
    _resources = aggregate_resources(_inputs.topic, _inputs.subject, learner, llm)
    _phases = design_phases(_inputs, _resources, learner, llm)

    _total_days = sum(p.duration_days for p in _phases)
    _weeks = max(1, round(_total_days / 7))
    _plan = StudyPlan(
        plan_id=uuid.uuid4().hex[:12],
        learner_id=str(getattr(learner, "id", "")),
        topic=_inputs.topic,
        subject=_inputs.subject,
        goal=_inputs.goal,
        deadline=_inputs.deadline,
        grade_level=str(getattr(learner, "grade_level", "high_school")),
        total_weeks=_weeks,
        weekly_hours=_inputs.weekly_hours,
        phases=_phases,
        created_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    # 个性化备注
    _notes = []
    _m = getattr(learner, "subjects_mastery", None) or {}
    if _m.get(_inputs.subject, 0) >= 0.7:
        _notes.append(f"你在{_inputs.subject}基础较好，前段可适当加速")
    elif _m.get(_inputs.subject, 0) and _m.get(_inputs.subject) < 0.4:
        _notes.append(f"你在{_inputs.subject}基础较薄弱，建议基础阶段多分配时间")
    if _inputs.goal == "备考":
        _notes.append("备考导向：真题与模拟在实战阶段占比提高")
    _plan.personalization_notes = _notes
    _plan.summary_md = _render_summary_md(_plan)
    return _plan


def _render_summary_md(plan: StudyPlan) -> str:
    """渲染 markdown 摘要（前端 marked 渲染）。"""
    _lines = [
        f"## 学习计划：{plan.topic}",
        "",
        f"> 目标：{plan.goal} · 周期约 {plan.total_weeks} 周 · 每周约 {plan.weekly_hours:.0f} 小时"
        + (f" · 截止：{plan.deadline}" if plan.deadline else ""),
        "",
    ]
    for _i, _ph in enumerate(plan.phases):
        _lines.append(f"### 阶段 {_i+1}：{_ph.name}（{_ph.duration_days} 天）")
        _lines.append(f"**目标**：{_ph.goal}")
        _lines.append("")
        for _m in _ph.milestones:
            _lines.append(f"- **{_m.title}**")
            for _d in _m.deliverables:
                _lines.append(f"  - {_d}")
            _lines.append(f"  - 检验：{_m.checkpoint}")
        _lines.append("")
    if plan.personalization_notes:
        _lines.append("### 个性化备注")
        for _n in plan.personalization_notes:
            _lines.append(f"- {_n}")
        _lines.append("")
    _lines.append("> 想开始某一阶段的学习？点对应里程碑的「开始学习」按钮，我会为你讲解。")
    return "\n".join(_lines)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

__all__ = [
    "Resource", "Milestone", "Phase", "StudyPlan", "PlanInputs",
    "extract_plan_inputs", "decide_phase_count", "select_phase_template",
    "aggregate_resources", "design_phases", "build_study_plan",
    "is_study_plan_intent",  # 从 meta_router re-export（供 handler 统一入口）
]


def is_study_plan_intent(text: str, learner=None) -> bool:
    """re-export meta_router.is_study_plan_intent（避免 handler 双导入）。"""
    from meta_router import is_study_plan_intent as _f
    return _f(text, learner)
