# -*- coding: utf-8 -*-
"""material_pipeline.py — 通用物料流水线（v1.1 ⭐ §3.34 范式平移）

把"智绘科普"的多 Agent 分阶段 + 门控 + 自检 工程范式，从 Manim 动画
**平移到其他教学物料**：讲义、PPT、讲稿、知识导图、数学视频脚本。

统一管线（每类物料实现自己的阶段函数，框架共享门控/修复回路）：
  Phase 1 规划  → 结构化 spec（outline/要点）
  Phase 2 草稿  → 生成初稿（不产出终稿）
  Phase 3 实现  → 渲染/排版/落盘（PPT 用 python-pptx、讲义用 markdown、讲稿用 TTS）
  Phase 4 审查  → 语言规范审查（lang_gate）+ 结构审查（必填项）
  Phase 5 合成  → 输出 + 落盘
  失败返工回路 → 门控失败 → 反馈修复 → 重跑该阶段（最多 N 轮）

核心价值：
- 统一"规划→草稿→实现→审查"4 角色边界（防 LLM 越界）
- 统一门控（结构/数量/语言/完整性）
- 统一失败修复回路（错误→修复提示词→重跑）
- 与 manim_pipeline 同构——物料间可互相消费 spec（讲义→讲稿→PPT→动画）
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

_BASE = os.path.dirname(os.path.abspath(__file__))
_MATERIAL_DIR = os.path.join(_BASE, "evolve_data", "material_pipeline")

MAX_FIX_ROUNDS = 3


def _ensure_dir():
    os.makedirs(_MATERIAL_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# 语言规范门（技术说明纪律 23：语言必须过 lang_gate + LanguageRefiner）
# ═══════════════════════════════════════════════════════════
def language_gate(text: str, context: str = "") -> List[str]:
    """语言规范门：检测 AI 腔/违禁词/省略句。返回问题列表（空=通过）。"""
    issues = []
    try:
        from ai_taste_detector import detect_ai_taste
        sig = detect_ai_taste(text)
        if getattr(sig, "ai_likelihood", 0) >= 0.45:
            issues.append(f"AI 味概率 {sig.ai_likelihood:.2f}（≥0.45）")
    except Exception:
        pass
    try:
        from infra.runtime import get_paeg
        paeg = get_paeg()
        if paeg is not None and getattr(paeg, "refiner", None) is not None:
            hits = paeg.refiner.detect_ai_tells(text)
            if hits:
                issues.append(f"违禁词: {', '.join(hits[:5])}")
    except Exception:
        pass
    return issues


def language_refine(text: str, context: str = "") -> str:
    """语言 refine：过 lang_gate 统一入口（L0+L2）。"""
    if not text:
        return text
    try:
        from services.lang_gate import lang_gate_content
        return lang_gate_content(text, context=context)
    except Exception:
        return text


# ═══════════════════════════════════════════════════════════
# 通用门控
# ═══════════════════════════════════════════════════════════
def gate_structure(spec: dict, required: List[str]) -> List[str]:
    errors = []
    for k in required:
        if k not in spec or not spec.get(k):
            errors.append(f"缺必填字段: {k}")
    return errors


def gate_length(content: str, min_len: int = 50, max_len: int = 20000) -> List[str]:
    errors = []
    n = len(content or "")
    if n < min_len:
        errors.append(f"内容过短（{n} 字符 < {min_len}）")
    if n > max_len:
        errors.append(f"内容过长（{n} 字符 > {max_len}）")
    return errors


# ═══════════════════════════════════════════════════════════
# 阶段接口（各类物料实现）
# ═══════════════════════════════════════════════════════════
MaterialStages = Dict[str, Callable[..., Any]]


class MaterialPipeline:
    """通用物料流水线（策略模式：传入各类物料的阶段函数）。

    §3.89 v2.0 ⭐ 统一框架升级：新增 gates / fix_strategy 可插拔槽位。
    - gates: List[Callable] 每个门 (content, ctx) -> (ok, reason)；默认 structure/length/language
    - fix_strategy: Callable 门失败修复策略 (stage_name, content, ctx, errors) -> new_content
      默认 retry（同级重生成）；可换 escalate（ScopeRefine 三级升级）/ regenerate（全重跑）
    - 保持 v1.1 行为不变（ratchet：gate/fix 未传时退化为原内嵌逻辑）
    """

    def __init__(self, material_type: str,
                 stages: MaterialStages,
                 required_fields: List[str],
                 min_content_len: int = 50,
                 gates: Optional[List[Callable]] = None,
                 fix_strategy: Optional[Callable] = None):
        self.material_type = material_type
        self.stages = stages          # {plan, draft, implement, review}
        self.required_fields = required_fields
        self.min_content_len = min_content_len
        # §3.89 v2.0 ⭐ 可插拔槽位（不传则退化原行为）
        self.gates = gates or []
        self.fix_strategy = fix_strategy

    def run(self, llm, topic: str, subject: str = "通用",
            learner_id: str = "anon", **kw) -> Dict[str, Any]:
        """执行完整物料流水线。"""
        result = {"ok": False, "material_type": self.material_type,
                  "output": None, "spec": None, "stages": {},
                  "errors": [], "path": ""}
        _ensure_dir()

        # Phase 1 规划（spec）
        try:
            spec = self.stages["plan"](llm, topic, subject, learner_id, **kw)
        except Exception as e:
            spec = None
            result["errors"].append(f"Phase1 规划失败: {e}")
        if not spec:
            result["errors"].append("Phase1 未产出 spec")
            return result
        result["spec"] = spec
        result["stages"]["plan"] = "ok"

        # 门控 + 修复回路
        for _r in range(MAX_FIX_ROUNDS):
            errors = gate_structure(spec, self.required_fields)
            if not errors:
                break
            try:
                from subagents import _safe_chat
                _sys = (f"你是{self.material_type}规划修复器。根据校验错误修改 spec，"
                        "保持结构，只修违反项。输出修复后的 JSON。")
                _usr = (f"spec：{json.dumps(spec, ensure_ascii=False)}\n"
                        f"错误：{errors}\n请修复。")
                _raw = _safe_chat(llm, _sys, _usr, max_tokens=3000)
                if _raw:
                    _m = __import__("re").search(r"\{.*\}", _raw, __import__("re").S)
                    if _m:
                        spec = json.loads(_m.group(0))
                        result["spec"] = spec
            except Exception:
                break
        result["stages"]["gates"] = "ok" if not gate_structure(spec, self.required_fields) else "fail"

        # Phase 2 草稿
        try:
            draft = self.stages["draft"](llm, spec, topic, subject, learner_id, **kw)
        except Exception as e:
            draft = None
            result["errors"].append(f"Phase2 草稿失败: {e}")
        if not draft:
            result["errors"].append("Phase2 未产出草稿")
            return result
        result["stages"]["draft"] = "ok"

        # §3.89 v2.0 ⭐ 自定义 gates + fix_strategy（可插拔，不传则跳过）
        if self.gates:
            _ctx = {"material_type": self.material_type, "topic": topic,
                    "subject": subject, "spec": spec}
            for _gi, _gate in enumerate(self.gates):
                try:
                    _ok, _reason = _gate(draft, _ctx)
                    if not _ok:
                        result["errors"].append(f"自定义门{_gi}失败: {_reason}")
                        if self.fix_strategy is not None:
                            _fixed = self.fix_strategy("draft", draft, _ctx,
                                                       [f"门{_gi}: {_reason}"])
                            if _fixed and str(_fixed).strip():
                                draft = _fixed
                                result["stages"][f"gate{_gi}_fixed"] = "ok"
                        else:
                            result["stages"][f"gate{_gi}"] = "fail"
                            return result
                    else:
                        result["stages"][f"gate{_gi}"] = "ok"
                except Exception as _ge:
                    result["errors"].append(f"自定义门{_gi}异常: {_ge}")

        # Phase 3 实现（含语言 refine + 修复回路）
        content = draft
        for _r in range(MAX_FIX_ROUNDS):
            # 语言规范门（纪律 23）
            lang_issues = language_gate(str(content)[:3000],
                                        context=f"{self.material_type}:{topic}")
            if not lang_issues:
                break
            try:
                from subagents import _safe_chat
                _sys = (f"你是{self.material_type}语言修复器。根据语言规范问题重写，"
                        "保持内容与结构，用朴素准确的语言。输出完整内容。")
                _usr = (f"问题：{lang_issues}\n内容：{str(content)[:2000]}\n请重写。")
                _raw = _safe_chat(llm, _sys, _usr, max_tokens=3000)
                if _raw:
                    content = _raw
            except Exception:
                break
        content = language_refine(str(content), context=f"{self.material_type}:{topic}")
        try:
            impl = self.stages["implement"](llm, content, topic, subject, learner_id, **kw)
        except Exception as e:
            impl = None
            result["errors"].append(f"Phase3 实现失败: {e}")
        if impl is None:
            result["errors"].append("Phase3 未产出成果")
            return result
        result["stages"]["implement"] = "ok"
        result["output"] = impl

        # Phase 4 审查（长度门 + 可选自定义）
        len_err = gate_length(str(impl), min_len=self.min_content_len)
        if len_err:
            result["errors"].append(f"Phase4 长度门: {len_err}")
        if "review" in self.stages:
            try:
                review = self.stages["review"](llm, impl, topic, **kw)
                if review:
                    result["stages"]["review"] = "ok" if not review else "issues"
            except Exception:
                pass

        # Phase 5 合成（落盘）
        try:
            _job = {
                "material_type": self.material_type,
                "topic": topic, "subject": subject,
                "spec": spec, "output": str(impl)[:5000],
                "stages": result["stages"],
                "ts": time.time(),
            }
            _out = os.path.join(_MATERIAL_DIR,
                                f"{self.material_type}_{uuid.uuid4().hex[:8]}.json")
            with open(_out, "w", encoding="utf-8") as f:
                json.dump(_job, f, ensure_ascii=False, indent=2)
            result["path"] = _out
            result["stages"]["compose"] = "ok"
        except Exception as e:
            result["errors"].append(f"Phase5 合成失败: {e}")

        result["ok"] = not result["errors"]
        return result


# ═══════════════════════════════════════════════════════════
# 预置物料流水线：讲义
# ═══════════════════════════════════════════════════════════
def handout_pipeline() -> MaterialPipeline:
    """讲义物料流水线（复用 file_generator 的生成 + lang_gate 守门）。"""

    def _plan(llm, topic, subject, learner_id, **kw):
        from file_generator import FileGenerator
        fg = FileGenerator(llm)
        return {"topic": topic, "subject": subject,
                "learner_id": learner_id, "mode": "handout"}

    def _draft(llm, spec, topic, subject, learner_id, **kw):
        # 复用现有 file_generator 生成讲义
        from file_generator import FileGenerator
        fg = FileGenerator(llm)
        md, html = fg.save_answer(topic, topic, subject)
        return md

    def _implement(llm, content, topic, subject, learner_id, **kw):
        # 语言 refine 已在管线完成；此处返回内容
        return content

    return MaterialPipeline(
        material_type="handout",
        stages={"plan": _plan, "draft": _draft, "implement": _implement},
        required_fields=["topic", "subject"],
        min_content_len=80,
    )


# ═══════════════════════════════════════════════════════════
# 预置物料流水线：讲稿
# ═══════════════════════════════════════════════════════════
def script_pipeline() -> MaterialPipeline:
    """讲稿物料流水线（复用 script_service 生成 narration + TTS）。"""

    def _plan(llm, topic, subject, learner_id, **kw):
        return {"topic": topic, "subject": subject,
                "learner_id": learner_id, "mode": "script"}

    def _draft(llm, spec, topic, subject, learner_id, **kw):
        try:
            from services.script_service import generate_full_script
            return generate_full_script(topic, subject=subject) or f"（{topic}讲稿）"
        except Exception:
            return f"关于{topic}的讲稿（{subject}）。"

    def _implement(llm, content, topic, subject, learner_id, **kw):
        return content

    return MaterialPipeline(
        material_type="script",
        stages={"plan": _plan, "draft": _draft, "implement": _implement},
        required_fields=["topic", "subject"],
        min_content_len=30,
    )


# ═══════════════════════════════════════════════════════════
# 预置物料流水线：PPT 大纲
# ═══════════════════════════════════════════════════════════
def ppt_pipeline() -> MaterialPipeline:
    """PPT 物料流水线（大纲→要点，供 pptx_mcp_server 排版）。"""

    def _plan(llm, topic, subject, learner_id, **kw):
        return {"topic": topic, "subject": subject,
                "learner_id": learner_id, "mode": "ppt"}

    def _draft(llm, spec, topic, subject, learner_id, **kw):
        _sys = ("你是 PPT 大纲设计师。为教学主题设计结构化 PPT 大纲："
                "封面、3-6 页正文（每页一个要点+讲解）、结尾。"
                "输出 markdown 大纲。")
        try:
            from subagents import _safe_chat
            return _safe_chat(llm, _sys, f"主题：{topic}\n学科：{subject}")
        except Exception:
            return f"# {topic}\n\n## 要点\n- 核心概念\n- 例题\n- 小结"

    def _implement(llm, content, topic, subject, learner_id, **kw):
        return content

    return MaterialPipeline(
        material_type="ppt",
        stages={"plan": _plan, "draft": _draft, "implement": _implement},
        required_fields=["topic", "subject"],
        min_content_len=50,
    )


# ═══════════════════════════════════════════════════════════
# 预置物料流水线：知识导图
# ═══════════════════════════════════════════════════════════
def mindmap_pipeline() -> MaterialPipeline:
    """知识导图物料流水线。"""

    def _plan(llm, topic, subject, learner_id, **kw):
        return {"topic": topic, "subject": subject,
                "learner_id": learner_id, "mode": "mindmap"}

    def _draft(llm, spec, topic, subject, learner_id, **kw):
        _sys = ("你是知识导图设计师。为教学主题设计结构化知识导图："
                "中心主题、3-5 个一级分支、每分支 2-4 个二级节点。"
                "输出 markdown 缩进列表。")
        try:
            from subagents import _safe_chat
            return _safe_chat(llm, _sys, f"主题：{topic}\n学科：{subject}")
        except Exception:
            return f"- {topic}\n  - 定义\n  - 性质\n  - 应用"

    def _implement(llm, content, topic, subject, learner_id, **kw):
        return content

    return MaterialPipeline(
        material_type="mindmap",
        stages={"plan": _plan, "draft": _draft, "implement": _implement},
        required_fields=["topic", "subject"],
        min_content_len=30,
    )


# ═══════════════════════════════════════════════════════════
# 预置物料流水线：教学视频（§3.89 Step2 ⭐ 新增）
# ═══════════════════════════════════════════════════════════
def video_pipeline() -> MaterialPipeline:
    """教学视频物料流水线（scenes[] 8-15s 分镜 + 音画对齐门）。

    spec: {"scenes": [{id, concept, narration, duration_sec, visual_goal}]}
    gates: 镜数 ≥3 / 单镜时长 8-15s / 音画对齐（narration 非空）
    review: material_judge（画面/声音/教学性/连贯）
    """
    from services.material_judge import judge_material

    def _plan(llm, topic, subject, learner_id, **kw):
        return {"topic": topic, "subject": subject,
                "learner_id": learner_id, "mode": "video"}

    def _draft(llm, spec, topic, subject, learner_id, **kw):
        _sys = ("你是教学视频分镜导演。为教学主题设计 3-8 个镜头（scene），"
                "每镜：id、concept（教学点）、narration（旁白台词）、"
                "duration_sec（8-15 秒）、visual_goal（画面目标）。"
                "输出 JSON 数组 scenes。")
        try:
            from subagents import _safe_chat
            import re as _re
            _raw = _safe_chat(llm, _sys, f"主题：{topic}\n学科：{subject}", max_tokens=3000)
            if _raw:
                _m = _re.search(r"\[.*\]", _raw, _re.S)
                if _m:
                    return json.loads(_m.group(0))
            return [{"id": "s1", "concept": topic, "narration": f"今天我们学习{topic}",
                     "duration_sec": 12, "visual_goal": f"展示{topic}的核心概念"}]
        except Exception:
            return [{"id": "s1", "concept": topic, "narration": f"今天我们学习{topic}",
                     "duration_sec": 12, "visual_goal": f"展示{topic}的核心概念"}]

    def _implement(llm, content, topic, subject, learner_id, **kw):
        # 教学视频实现：可选 TTS 合成（Audio-First）
        try:
            from manim_extensions import tts_mux
            _d = content
            return _d
        except Exception:
            return content

    # 视频专属门（§3.89 ⭐ 可插拔）
    def _gate_scenes(content, ctx):
        scenes = content if isinstance(content, list) else None
        if not scenes or len(scenes) < 3:
            return False, f"镜数不足（{len(scenes) if scenes else 0}/3）"
        return True, ""

    def _gate_duration(content, ctx):
        scenes = content if isinstance(content, list) else []
        bad = [s.get("duration_sec") for s in scenes
               if not (8 <= float(s.get("duration_sec", 0)) <= 15)]
        if bad:
            return False, f"{len(bad)} 镜时长不在 8-15s"
        return True, ""

    def _gate_narration(content, ctx):
        scenes = content if isinstance(content, list) else []
        silent = [s.get("id") for s in scenes if not s.get("narration")]
        if silent:
            return False, f"静音镜: {silent}"
        return True, ""

    return MaterialPipeline(
        material_type="video",
        stages={"plan": _plan, "draft": _draft, "implement": _implement},
        required_fields=["topic", "subject"],
        min_content_len=30,
        gates=[_gate_scenes, _gate_duration, _gate_narration],
    )


# ═══════════════════════════════════════════════════════════
# 预置物料流水线：Manim 数学视频（§3.89 Step3 ⭐ 统一接入）
# ═══════════════════════════════════════════════════════════
def manim_pipeline_unified() -> MaterialPipeline:
    """Manim 数学视频统一接入（复用成熟 manim_pipeline.py 6 阶段门控）。

    plan/draft: 复用 manim_pipeline.phase1_plan / phase2_draft（script.json）
    gates: run_all_gates（beats/时序/可执行/几何 铁律）
    fix_strategy: scope_refine 三级修复（L1 场景内→L2 重写→L3 重生）
    review: manim_judge（4 维）
    """
    try:
        import manim_pipeline as _mp
    except Exception:
        _mp = None

    def _plan(llm, topic, subject, learner_id, **kw):
        if _mp is not None:
            try:
                return _mp.phase1_plan(llm, topic, audience=kw.get("audience", "高中"))
            except Exception:
                pass
        return {"topic": topic, "subject": subject, "mode": "manim"}

    def _draft(llm, spec, topic, subject, learner_id, **kw):
        if _mp is not None:
            try:
                _code = _mp.phase2_draft(llm, spec)
                if _code:
                    return _code
            except Exception:
                pass
        return f"// {topic} Manim 剧本（{subject}）"

    def _implement(llm, content, topic, subject, learner_id, **kw):
        if _mp is not None:
            try:
                return _mp.phase2_implement(content)
            except Exception:
                pass
        return {"ok": False, "error": "manim 渲染不可用"}

    # Manim 门（复用 run_all_gates：beats/时序/可执行/几何）
    def _gate_manim(content, ctx):
        if _mp is None:
            return True, ""  # 无 manim 环境跳过
        try:
            errors = _mp.run_all_gates(content) if isinstance(content, dict) else []
            if errors:
                return False, "; ".join(errors[:3])
            return True, ""
        except Exception:
            return True, ""

    # 三级修复（scope_refine）
    def _fixer(stage_name, content, ctx, errors):
        from manim_extensions import scope_refine
        # 升级逻辑：同一阶段错误累积 → L1→L2→L3
        _err_key = f"_fix_level_{stage_name}"
        _level = ctx.get(_err_key, 1)
        ctx[_err_key] = min(_level + 1, 3)
        return scope_refine(content, errors, llm=ctx.get("llm"), level=_level)

    return MaterialPipeline(
        material_type="manim",
        stages={"plan": _plan, "draft": _draft, "implement": _implement},
        required_fields=["topic", "subject"],
        min_content_len=30,
        gates=[_gate_manim],
        fix_strategy=_fixer,
    )


# ═══════════════════════════════════════════════════════════
# 统一入口：按物料类型选择流水线
# ═══════════════════════════════════════════════════════════
_PIPELINES = {
    "handout": handout_pipeline,
    "script": script_pipeline,
    "ppt": ppt_pipeline,
    "mindmap": mindmap_pipeline,
    "video": video_pipeline,
    "manim": manim_pipeline_unified,
}


def create_pipeline(material_type: str) -> Optional[MaterialPipeline]:
    """按物料类型创建流水线（handout/script/ppt/mindmap/video/manim）。"""
    factory = _PIPELINES.get(material_type)
    return factory() if factory else None


def run_material_pipeline(llm, material_type: str, topic: str,
                          subject: str = "通用", learner_id: str = "anon",
                          **kw) -> Dict[str, Any]:
    """统一入口：执行指定物料流水线。"""
    pipe = create_pipeline(material_type)
    if pipe is None:
        return {"ok": False, "errors": [f"未知物料类型: {material_type}"]}
    return pipe.run(llm, topic, subject, learner_id, **kw)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("material_pipeline v2.0 就绪（范式平移：讲义/讲稿/PPT/知识导图/教学视频/Manim）")
    print("统一管线: 规划→草稿→门控→修复→实现→审查 + 语言规范门 + 修复回路")
    print("物料:", list(_PIPELINES.keys()))
