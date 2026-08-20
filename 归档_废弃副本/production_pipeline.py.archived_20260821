# -*- coding: utf-8 -*-
"""制作流水线编排器（v1.0 ⭐）：讲义 → PPT → 融合视频（含 manim 片段 + 资源）。

用户需求：
1. 讲义/PPT 制作时要为视频预留 manim 演示动画空间（[[manim: …]] 占位）
2. 视频制作时把 manim 片段剪辑进时间轴（ffmpeg 合成，非另发）
3. 视频能使用资源：manim 产物 + Library 用户物料（usr_knowledge）+ 公共模板（ppt_templates）
4. **主题类型分派**：仅可视化类学科（数学/物理等）插入 manim 动画；
   其他学科（语文/历史等）走纯讲解 + 资源叠图，不插 manim
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional, List

_BASE = Path(__file__).resolve().parents[1]
_SYS = os.sys.path  # noqa

# v0.66 ⭐ 结构化日志（诊断用：含 pid/线程，区分并发/进程问题）
import logging as _logging
import threading as _threading
import os as _os_mod
_log = _logging.getLogger("production_pipeline")
if not _log.handlers:
    _h = _logging.StreamHandler()
    _h.setFormatter(_logging.Formatter(
        f"[%(asctime)s][pid={_os_mod.getpid()}][%(name)s] %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(_logging.INFO)


def _log_info(msg: str):
    try:
        _log.info(f"[tid={_threading.get_ident()}] {msg}")
    except Exception:
        print(f"[production_pipeline] {msg}")


def _auto_outline(topic: str, subject: str, learner_id: str = "anon",
                  deep_think: bool = False) -> str:
    """v0.66 ⭐ LLM 生成完整教学大纲（无 outline 时自动）。

    - 结构：完整教学循环（导入→新授→巩固→复习→总结→提高），5-7 章
    - 可视化类主题（数学/物理，含主题关键词推断）在关键章节后插
      [[manim: 主题]] 占位 → 融合管线渲染 manim 动画并剪辑进时间轴
    - LLM 失败 → 规则兜底大纲（保底可出片）
    """
    from manim_service import infer_manim_suitability
    _manim_ok = infer_manim_suitability(topic, subject)
    _outline = ""
    try:
        from subagents import _safe_chat
        _sys = (
            "你是资深教学设计专家。为下面的教学主题设计一份**全过程教学大纲**。\n"
            "要求：\n"
            "1. 覆盖完整教学循环：导入（激发兴趣/联系旧知）→ 新授（核心概念与原理）"
            "→ 巩固（典型例题）→ 复习（要点回顾）→ 总结（知识结构）→ 提高（拓展思考）\n"
            "2. 5-7 个章节，每章 2-3 个要点，内容具体有深度（含概念定义、原理阐释、"
            "生活化例子、推导过程或应用场景）\n"
            "3. 格式严格：每章一行 '## 章节名'，要点每行 '- 要点内容'\n"
            "4. 章节间逻辑递进、衔接自然（直觉 → 定义 → 例子 → 应用 → 深化）\n"
            "5. 只输出大纲文本，不要解释"
        )
        if _manim_ok:
            _sys += (
                "\n6. 在最适合动画演示的章节后插入 [[manim: 该动画演示的主题]]"
                "（如函数图像/几何变换/变化过程/空间关系），整份大纲至少 1 个、最多 2 个"
                "；动画主题要具体（如'正弦曲线的动态生成与相位平移'而非'正弦函数'）"
            )
        _u = f"主题：{topic}\n学科：{subject or '通用'}\n生成全过程教学大纲"
        # v0.66 ⭐ API 偶发空响应：重试 2 次（DeepSeek 波动时仍能拿到大纲）
        for _attempt in range(3):
            _r = _safe_chat(_sys, _u, max_tokens=800)
            if _r and "##" in _r:
                _outline = _r.strip()
                break
            import time as _t
            _t.sleep(1.0)
    except Exception:
        _outline = ""

    if not _outline:
        # 规则兜底（保底可出片）
        _outline = (
            f"## {topic}：从直觉到理解\n"
            f"- 认识 {topic} 的基本概念\n"
            f"- 直观理解 {topic} 的核心思想\n"
            f"## 深入 {topic}\n"
            f"- {topic} 的关键定义与原理\n"
            f"- 典型例子讲解\n"
            f"## 应用与小结\n"
            f"- {topic} 的实际应用\n"
            f"- 小结与思考练习\n"
        )
        if _manim_ok:
            _outline += f"\n[[manim: {topic} 的可视化演示]]\n"
    return _outline


def _outline_from_handout(handout_md: str, topic: str, subject: str) -> str:
    """v0.66 ⭐ 从讲义 markdown 抽取视频大纲（## 章节 + - 要点）。

    讲义是单一事实源：视频/PPT 的大纲来自讲义结构，
    避免各环节各编各的（用户核心需求：链路联动）。
    """
    from manim_service import infer_manim_suitability
    _manim_ok = infer_manim_suitability(topic, subject)
    _lines = []
    _cur = None
    for line in (handout_md or "").split("\n"):
        s = line.strip()
        if s.startswith("## "):
            _cur = s
            _lines.append(s)
        elif s.startswith("- ") or s.startswith("* ") or s.startswith("1. ") \
                or s.startswith("2. ") or s.startswith("3. "):
            if _cur:
                _lines.append("- " + s.lstrip("-*123. ").strip()[:60])
    if not _lines:
        _lines = [f"## {topic}：从直觉到理解",
                  f"- 认识 {topic} 的基本概念",
                  f"## 深入 {topic}",
                  f"- {topic} 的关键定义与原理"]
    if _manim_ok and "[[manim:" not in "\n".join(_lines):
        _lines.append(f"\n[[manim: {topic} 的可视化演示]]\n")
    return "\n".join(_lines)


def produce_lesson_video(topic: str, outline: str, learner_id: str = "anon",
                         subject: str = "", style: str = "paeg_standard",
                         deep_think: bool = False) -> dict:
    """主入口：大纲（含 [[manim:…]] 占位）→ PPT + 融合视频。

    流程：
      1. outline_ir.parse_outline_with_slots → pages（含 slots）
      2. 学科门控：subject 非可视化类 → 忽略 manim 占位（不渲染不插入）
      3. manim 占位（白名单学科内）→ manim_service 渲染（失败降级静态帧）
      4. asset 占位 → asset_loader 解析（防路径穿越）
      5. video_service.compose_with_slots → 融合 mp4
      6. 可选：同步生成 PPT（含动画占位页）

    返回 {ok, video_url, video_path, slides, duration, manim_count,
          errors[], handout_id?, ppt_url?}
    """
    from outline_ir import parse_outline_with_slots, manim_slots, asset_slots
    from video_service import compose_with_slots
    from manim_service import infer_manim_suitability

    errors: List[str] = []

    # ── 0. 讲义/大纲生成（v0.66 ⭐ 讲义是源头）──
    # 优先 generate_handout（完整教学讲义）→ 从讲义抽大纲；讲义失败 → _auto_outline
    _log_info(f"[enter] topic={topic} subject={subject} learner={learner_id} outline_len={len(outline or '')}")
    _handout = None
    if not outline or not outline.strip():
        try:
            from file_generator import FileGenerator
            from infra.runtime import get_llm
            _fg = FileGenerator(get_llm())
            # learner 从会话取（尽量构造）
            _learner = None
            try:
                from services._learner_session import ensure_learner_session
                from infra.sessions import SESSIONS
                _learner = ensure_learner_session(learner_id, {}, SESSIONS)
            except Exception:
                pass
            _content, _fname, _handout = _fg.generate_handout(
                _learner, subject or "通用", topic, length="medium")
            _log_info(f"[handout] 讲义生成 len={len(_content)} sections={len(_handout.get('sections', []))}")
            # 从讲义抽大纲（章节标题 → ## + 要点）
            outline = _outline_from_handout(_handout.get("content") or _content, topic, subject)
            _log_info(f"[handout→outline] len={len(outline)}")
        except Exception as _he:
            _log_info(f"[handout] 生成失败，降级自动大纲: {str(_he)[:80]}")
            _handout = None

    if not outline or not outline.strip():
        outline = _auto_outline(topic, subject, learner_id, deep_think)
        _log_info(f"[auto_outline] len={len(outline)} has_manim_mark={'[[manim:' in outline}")
    # v0.66 ⭐ 需求6 短指令补全：若主题仍过短/泛化，用推断上下文增强大纲
    try:
        from services.intent_inference import infer_context, build_assumption_note
        _ictx = infer_context(topic, explicit_subject=subject)
        if _ictx["topic"] and _ictx["topic"] != topic:
            _log_info(f"[intent] 主题补全: {topic} -> {_ictx['topic']} ({_ictx['subject']}/{_ictx['grade']})")
    except Exception:
        pass

    # ── 1. 解析大纲 → IR ──
    try:
        pages = parse_outline_with_slots(outline)
    except Exception as e:
        return {"ok": False, "error": f"大纲解析失败: {e}"}
    if not pages:
        return {"ok": False, "error": "大纲为空"}
    _log_info(f"[parse] pages={len(pages)} manim_slots={len(manim_slots(pages))}")

    # ── 2. 学科类型分派（用户需求核心）──
    # v0.66 ⭐ 用 infer_manim_suitability：显式学科 + 主题内容推断取并集
    # （用户不选学科时，仅凭"行列式"等关键词也能识别为可视化主题）
    _manim_ok = infer_manim_suitability(topic, subject)
    _manim_slots = manim_slots(pages) if _manim_ok else []
    _log_info(f"[gate] subject={subject} topic={topic[:20]} manim_ok={_manim_ok} slots={len(_manim_slots)}")
    if manim_slots(pages) and not _manim_ok:
        errors.append(f"学科 '{subject}' 非可视化类，manim 动画占位已忽略（纯讲解视频）")
    _asset_slots = asset_slots(pages)

    # ── 3. 预渲染 manim 片段（白名单学科 + 占位存在时）──
    manim_results: dict = {}
    if _manim_slots:
        from manim_service import generate_manim_video
        for slot in _manim_slots:
            topic_slot = slot.get("topic") or ""
            _log_info(f"[manim] rendering slot: {topic_slot}")
            try:
                r = generate_manim_video(topic_slot, subject=subject, learner_id=learner_id)
                _log_info(f"[manim] result ok={r.get('ok')} err={r.get('error', '')[:80]}")
                if r.get("ok") and r.get("path"):
                    manim_results[topic_slot] = r["path"]
                else:
                    errors.append(f"manim 渲染失败({topic_slot}): {r.get('error', '')[:100]}")
            except Exception as e:
                errors.append(f"manim 异常({topic_slot}): {str(e)[:100]}")
    _log_info(f"[manim] rendered {len(manim_results)}/{len(_manim_slots)}")

    # ── 4. 解析 asset 占位（路径安全）──
    asset_results: dict = {}
    if _asset_slots:
        from asset_loader import load_user_asset
        for slot in _asset_slots:
            p = load_user_asset(learner_id, slot.get("path") or "")
            if p:
                # 默认叠图到该页角落（v1 简化：inline）
                key = f"{slot.get('_page_idx', 0)}:inline"
                asset_results[key] = p
            else:
                errors.append(f"资源缺失或路径越界: {slot.get('path', '')[:60]}")

    # ── 4.5 讲稿生成（v0.66 ⭐ 讲稿驱动：PPT 页 + manim 段各配 narration）──
    _script = None
    try:
        from services.script_service import generate_full_script
        _script = generate_full_script(outline, topic=topic, subject=subject,
                                       learner_id=learner_id)
        _log_info(f"[script] sections={len(_script.sections)}")
    except Exception as _se:
        _log_info(f"[script] 生成失败，降级要点拼接: {str(_se)[:80]}")
        _script = None

    # ── 4.6 PPT 前置生成（v0.66 ⭐ 用户要求顺序：讲稿→PPT→manim→视频）──
    # B3 ⭐ Oracle 连通性修复：PPT 与讲稿同一事实源——用讲稿 key_points 增强 PPT 内容
    ppt_url = ""
    try:
        from pptx_mcp_server import generate_ppt as _gen_ppt
        # 剥离 manim 占位行（PPT 里不渲染占位符）
        _clean_outline = "\n".join(
            l for l in (outline or "").split("\n") if "[[manim:" not in l)
        # B3 ⭐ 把讲稿的 key_points 并入 outline（PPT 与讲稿内容一致，不各编各的）
        if _script is not None:
            _ppt_extra = []
            for _sec in _script.sections:
                if _sec.key_points:
                    _ppt_extra.append(f"- {'，'.join(str(k) for k in _sec.key_points[:3])}")
            if _ppt_extra:
                _clean_outline += "\n\n## 要点补充（讲稿同源）\n" + "\n".join(_ppt_extra)
        _pr = _gen_ppt(topic, _clean_outline, sources="", uid=str(learner_id), style=style)
        if _pr.get("ok"):
            ppt_url = _pr.get("url") or _pr.get("path") or ""
            _log_info(f"[ppt] 生成成功 url={ppt_url[:60]}")
        else:
            errors.append(f"PPT 生成失败: {str(_pr.get('error', ''))[:100]}")
    except Exception as e:
        errors.append(f"PPT 生成失败(不影响视频): {str(e)[:100]}")

    # ── 5. 融合视频合成（讲稿驱动配音）──
    ir = {"topic": topic, "pages": pages}
    try:
        result = compose_with_slots(
            topic, ir, manim_results, asset_results, learner_id=learner_id,
            script=_script)
    except Exception as e:
        return {"ok": False, "error": f"视频合成异常: {e}", "errors": errors}
    result["errors"] = errors
    if not result.get("ok"):
        result["errors"] = errors
        return result

    result["ppt_url"] = ppt_url
    return result


if __name__ == "__main__":
    # 自测：含 manim 占位的大纲（数学）→ 融合视频
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    demo = (
        "## 二次函数的最大值\n"
        "- 二次函数 y = ax² + bx + c 的顶点\n"
        "- 顶点公式：x = -b/(2a)\n\n"
        "[[manim: 二次函数的抛物线图像与顶点]]\n\n"
        "## 实例\n"
        "- 求 y = x² - 4x + 3 的顶点\n"
        "- 开口方向与最值判断\n"
    )
    r = produce_lesson_video("二次函数的最大值", demo, learner_id="demo",
                             subject="math")
    print(r)
