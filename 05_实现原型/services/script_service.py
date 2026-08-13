# -*- coding: utf-8 -*-
"""讲稿生成服务（v0.66 ⭐ Oracle 讲稿驱动视频链路 Stage 1）

用户需求：视频 = 讲义/讲稿 → PPT → manim → 合成；每段（PPT 页 + manim 动画）
都要有对应的讲解讲稿（narration），配音跟随画面。

本模块：从大纲（含 [[manim:…]] 占位）生成全篇结构化讲稿。
每段独立 narration（PPT 页讲稿 + manim 段讲稿），供后续 TTS 配音。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Optional

_BASE = Path(__file__).resolve().parents[1]
_CACHE_DIR = _BASE / "downloads" / "scripts"

# 语速估算：中文约 4 字/秒
_CHARS_PER_SEC = 4.0


class ScriptSection:
    """一段讲稿（PPT 页 或 manim 动画段）。"""

    def __init__(self, section_id: str, stype: str, title: str,
                 narration: str, key_points: List[str],
                 est_duration_s: float = 0.0, manim_topic: str = ""):
        self.id = section_id
        self.type = stype          # "ppt" | "manim"
        self.title = title
        self.narration = narration
        self.key_points = key_points or []
        self.est_duration_s = est_duration_s
        self.manim_topic = manim_topic

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "title": self.title,
            "narration": self.narration, "key_points": self.key_points,
            "est_duration_s": self.est_duration_s, "manim_topic": self.manim_topic,
        }


class Script:
    """全篇讲稿：按大纲顺序的 section 列表。"""

    def __init__(self, lesson_id: str, sections: List[ScriptSection]):
        self.lesson_id = lesson_id
        self.sections = sections

    def to_dict(self) -> dict:
        return {"lesson_id": self.lesson_id,
                "sections": [s.to_dict() for s in self.sections]}


def _parse_outline_plan(outline: str) -> List[dict]:
    """从大纲文本解析分段计划（PPT 页 + manim 占位，按出现顺序）。

    返回 [{order, type, title, key_points, manim_topic?}]
    """
    from outline_ir import parse_outline_with_slots

    plan = []
    try:
        pages = parse_outline_with_slots(outline)
    except Exception:
        return plan

    order = 0
    for p in pages:
        # PPT 页
        order += 1
        plan.append({
            "order": order, "type": "ppt",
            "title": p.get("title") or "未命名",
            "key_points": p.get("points") or [],
        })
        # 该页的 manim 占位 → manim 段
        for slot in p.get("slots") or []:
            if slot.get("kind") == "manim":
                order += 1
                plan.append({
                    "order": order, "type": "manim",
                    "title": f"动画演示：{slot.get('topic', '')}",
                    "key_points": [slot.get("description") or "（动态演示）"],
                    "manim_topic": slot.get("topic") or "",
                })
    return plan


def _estimate_duration(text: str) -> float:
    """估算文本朗读时长（中文约 4 字/秒）。"""
    return max(3.0, len(text or "") / _CHARS_PER_SEC)


def _gen_ppt_narration(title: str, key_points: List[str], target_s: float) -> str:
    """PPT 页讲稿：LLM 生成**授课式**口语化讲解（对学生说话，非要点拼接）。

    v0.66 ⭐ 用户核心需求：讲稿必须"对着学生说话"——称呼/引导提问/过桥句/
    互动标记，禁止要点拼接兜底。
    """
    # v0.66 ⭐ 统一资源门面：讲稿基于 KB/用户物料/网络事实（不凭空讲）
    _res_block = ""
    try:
        from services.library import collect_all_resources
        _res = collect_all_resources(learner_id, title, llm=_safe_chat,
                                     subject="", include_web=False)
        if _res.get("has_any"):
            _res_block = "\n## 本页可用资料（讲稿应基于这些事实）\n" + _res["block"] + "\n"
    except Exception:
        pass
    try:
        from subagents import _safe_chat
        _target_chars = int(target_s * _CHARS_PER_SEC)
        _sys = (
            "你是{学段}{学科}老师，正在录一段授课视频。这一页的标题是《%s》。\n\n"
            "【关键规则——你必须做到】\n"
            "1. 必须像对着学生说话：称呼/引导（'同学们''大家''你'）、过渡过桥"
            "（'上一节我们……这一节……''讲到这里，可能有人会问……'）、"
            "引导提问（'你注意到了吗？''想想看，这是为什么？'）、"
            "互动标记（'（停顿）''记下来'）\n"
            "2. 口语化：用'我们来看''接下来''好''对'等自然语；"
            "禁用'让我们踏上''众所周知''显而易见'\n"
            "3. 逻辑：本页要点 → 1-2 个过渡 → 1 个例子或类比 → 收尾留钩子给下页\n"
            "4. 不照搬标题：解释变量/符号含义，不念标题\n"
            "5. 长度：%d 字（朗读约 %.0f 秒）\n"
            "6. 语言规范（L1）：口语自然，不用'首先/其次/最后'三段式、"
            "不用'总之''总而言之'，不堆破折号；一句一个意思，不啰嗦\n\n"
            "【本页标题】%s\n"
            "【本页要点】\n%s\n\n"
            "【输出】只输出讲稿文本（一段连贯口语）。\n"
            "【禁止】纯要点拼接（如'标题。要点1，要点2。'）——这是失败品，绝不能出现。"
        ) % (title, _target_chars, target_s, title,
             "\n".join(f"- {k}" for k in key_points))
        _u = f"标题：{title}\n要点：\n" + "\n".join(f"- {k}" for k in key_points)
        if _res_block:
            _u += "\n\n" + _res_block
        _r = _safe_chat(_sys, _u, max_tokens=400)
        # v0.66 ⭐ L0+L2 语言规范：讲稿过语言守门（AI 味/省略句/薇依语料矫正）
        if _r and len(_r.strip()) > 30:
            try:
                from services.lang_gate import lang_gate_short
                _r = lang_gate_short(_r, context=f"narration:{title}")
            except Exception:
                pass
            return _r.strip()
    except Exception:
        pass
    # v0.66 ⭐ 授课式兜底（不再"标题+逗号拼接"）
    return _fallback_narration(title, key_points)


def _fallback_narration(title: str, key_points: List[str]) -> str:
    """v0.66 ⭐ 授课式兜底讲稿：即使 LLM 失败也有称呼/引导/过桥。"""
    pts = key_points or []
    if not pts:
        return (f"同学们，我们这一节来看{title}。请先想一想，{title}对你意味着什么？"
                f"我们一步步来理解。")
    kp = str(pts[0])
    rest = "、".join(str(p) for p in pts[1:3])
    if rest:
        return (f"同学们，我们这一节的主题是{title}。先看一个核心问题：{kp}。"
                f"（停顿）我们从{rest}这几个角度来展开。请大家带着这个思考，我们继续往下看。")
    return (f"同学们，我们这一节的主题是{title}。先看一个核心问题：{kp}。"
            f"请大家带着这个思考，我们继续往下看。")


def _gen_manim_narration(manim_topic: str, target_s: float) -> str:
    """manim 动画段讲稿：LLM 生成**描述+引导+提问**三段式同步讲解。

    v0.66 ⭐ 用户需求：动画跟随讲解——描述画面、引导观察、提问总结。
    """
    try:
        from subagents import _safe_chat
        _target_chars = int(target_s * _CHARS_PER_SEC)
        _sys = (
            "你是{学段}{学科}老师，正在配合一段动画演示同步讲解。\n\n"
            "【关键规则】\n"
            "1. 描述+引导+提问三段式：\n"
            "   - 描述：'现在我们看到……（动画内容）'\n"
            "   - 引导观察：'注意看，这里发生了……''你看，这个量在……'\n"
            "   - 提问/总结：'这是为什么呢？因为……''到这里你发现规律了吗？'\n"
            "2. 与动画同步感：用'正在''逐渐''同时'等现在进行时\n"
            "3. 承接上下文：为下一节内容做铺垫\n"
            "4. 长度：%d 字（约 %.0f 秒）\n\n"
            "【动画主题】%s\n\n"
            "【输出】只输出讲稿文本。\n"
            "【禁止】'让我们通过动画来直观理解……'（空洞套话）。"
        ) % (_target_chars, target_s, manim_topic)
        _r = _safe_chat(_sys, f"动画主题：{manim_topic}", max_tokens=300)
        # v0.66 ⭐ L0+L2 语言规范
        if _r and len(_r.strip()) > 20:
            try:
                from services.lang_gate import lang_gate_short
                _r = lang_gate_short(_r, context=f"manim_narration:{manim_topic[:20]}")
            except Exception:
                pass
            return _r.strip()
    except Exception:
        pass
    # 授课式兜底
    return (f"同学们，现在我们看到{manim_topic}的动画演示。注意看，"
            f"这个变化正在逐渐展开——你发现其中的规律了吗？我们把这个问题记在心里，继续往下看。")


def generate_full_script(outline: str, topic: str = "",
                         subject: str = "", learner_id: str = "anon",
                         use_cache: bool = True) -> Script:
    """Stage 1 ⭐ 生成全篇讲稿（PPT 页 + manim 段，按大纲顺序）。

    每段独立 narration：PPT 页讲稿（目标 40s）+ manim 段讲稿（目标 30s）。
    结果按 outline hash 缓存（避免重复 LLM 调用）。
    """
    # 缓存
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _h = hashlib.md5((outline or "").encode("utf-8")).hexdigest()[:12]
    _cache_fp = _CACHE_DIR / f"{_h}.json"
    if use_cache and _cache_fp.exists():
        try:
            _d = json.loads(_cache_fp.read_text(encoding="utf-8"))
            return Script(
                lesson_id=_d.get("lesson_id", _h),
                sections=[ScriptSection(
                    section_id=s["id"], stype=s["type"], title=s["title"],
                    narration=s["narration"], key_points=s["key_points"],
                    est_duration_s=s.get("est_duration_s", 0.0),
                    manim_topic=s.get("manim_topic", ""),
                ) for s in _d.get("sections", [])],
            )
        except Exception:
            pass

    plan = _parse_outline_plan(outline)
    sections: List[ScriptSection] = []
    for item in plan:
        _sid = f"{item['order']:02d}_{item['type']}"
        if item["type"] == "manim":
            _target = 30.0
            _narration = _gen_manim_narration(item.get("manim_topic", ""), _target)
            sections.append(ScriptSection(
                section_id=_sid, stype="manim",
                title=item.get("title", "动画演示"),
                narration=_narration,
                key_points=item.get("key_points", []),
                est_duration_s=_estimate_duration(_narration),
                manim_topic=item.get("manim_topic", ""),
            ))
        else:
            _target = 40.0
            _narration = _gen_ppt_narration(
                item.get("title", "未命名"), item.get("key_points", []), _target)
            sections.append(ScriptSection(
                section_id=_sid, stype="ppt",
                title=item.get("title", "未命名"),
                narration=_narration,
                key_points=item.get("key_points", []),
                est_duration_s=_estimate_duration(_narration),
            ))

    script = Script(lesson_id=_h, sections=sections)
    # 缓存
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_fp.write_text(
            json.dumps(script.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass
    return script


def align_narration_to_animation(narration: str, target_duration_s: float) -> str:
    """v0.66 ⭐ 按动画实际时长对齐讲稿（粗对齐：字符估算裁剪/扩展）。

    - 差异 < 2s：直接用
    - 讲稿偏长：按比例截断 + 收尾句
    - 讲稿偏短：保留原文（合成时用 -shortest 截断动画，或静音填充）
    """
    if not narration:
        return narration
    est = _estimate_duration(narration)
    if abs(est - target_duration_s) < 2.0:
        return narration
    if est > target_duration_s:
        ratio = target_duration_s / est
        cut = int(len(narration) * ratio * 0.9)
        return narration[:cut].rstrip("。，, ") + "。我们继续看后面的内容。"
    return narration
