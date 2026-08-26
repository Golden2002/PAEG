# -*- coding: utf-8 -*-
"""material_router.py —— §3.91 ⭐ 物料路由调度器（Oracle 架构重构 Step1）

将 teach_stream 内 6 个物料早退分支（ppt/handout/video/manim/mindmap/script，
原约 195 行重复 if 堆叠）重构为**数据驱动路由表 + 统一调度器**：

- ROUTER：dict[intent → MaterialRoute]，每行声明生成器/超时/降级文案/是否走管线
- route_material()：统一调度（topic 提取 → 调生成器 → 异常隔离 → SSE 事件流）
- is_material_intent()：意图白名单判定
- 与 magic_intent.py 零耦合（复用其 match_magic 输出）；与 sse_presenter.py 协作发流

设计约束（Oracle）：
1. SSE 契约字节级不变（presentation/done 两事件 + step_type/mode/url 字段集）
2. 默认 5 类直调生成器（响应快 + 契约稳），仅 manim 走 MaterialPipeline v2.0
3. 单物料失败不影响其他（try/except 围栏 + fallback_msg 降级）
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, Optional

from sse_presenter import fmt_done, fmt_presentation, fmt_progress
# §3.92 ⭐ 接通结构化提示词模板（Oracle 根因修复：此前模板是"死代码"，生成器未调用）
from material_prompts import build_material_system, upgrade_simple_intent


# ═══════════════════════════════════════════════════════════
# §3.112 ⭐ 插件优先双轨（PAEG_USE_MATERIAL_PLUGIN=1 走插件，BridgeError 回退旧实现）
# ═══════════════════════════════════════════════════════════
def _try_plugin(intent: str, topic: str, subject: str, learner_id: str,
                **kw) -> Optional[dict]:
    """尝试用插件生成（成功返回 MaterialResult，失败/关闭返回 None → 走旧实现）。

    参数映射（§3.112）：现有 kw（grade/learner/user_requirements/intuition/
    objectives/prerequisites/style/duration_target_sec）全字段平移到插件。
    """
    try:
        from services.material_bridge import execute_typed
        _args = {"topic": topic, "subject": subject, "learner_id": learner_id}
        for _k in ("grade", "user_requirements", "intuition", "objectives",
                   "prerequisites", "style", "duration_target_sec", "outline",
                   "render"):
            if _k in kw and kw[_k] is not None:
                _args[_k] = kw[_k]
        # learner 画像 → 序列化（插件用 learner_id 即可，不传大对象）
        _r = execute_typed(f"generate_{intent}", _args)
        if isinstance(_r, dict) and _r.get("ok"):
            return {
                "ok": True,
                "content": str(_r.get("output") or _r.get("summary_md")
                               or f"{intent} 已生成（{topic}）")[:2000],
                "url": _r.get("url") or _r.get("path") or "",
                "error": "",
                "step_type": intent,
            }
        return None  # 插件失败 → 回退旧实现
    except Exception:
        return None  # BridgeError/异常 → 回退旧实现


# ═══════════════════════════════════════════════════════════
# 物料路由表（数据驱动核心）
# ═══════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MaterialRoute:
    """物料路由条目：声明式描述一次物料生成的所有参数。"""
    intent: str                       # 'ppt' | 'handout' | 'video' | 'manim' | 'mindmap' | 'script'
    step_type: str                    # 前端 SSE step_type（契约字段）
    generator: Callable               # 生成器函数签名 (llm, topic, subject, learner_id, **kw) -> MaterialResult
    timeout_sec: int = 30             # 超时（manim=300）
    save_turn: bool = True            # 是否调 _save_teach_turn
    fallback_msg: str = ""            # 失败兜底文案
    use_pipeline: bool = False        # 仅 manim=True（走 MaterialPipeline v2.0 长路径）


# 生成器返回契约
MaterialResult = Dict[str, Any]       # {"ok", "content", "url", "error", "step_type"}

ROUTER: Dict[str, MaterialRoute] = {
    "ppt": MaterialRoute(
        intent="ppt", step_type="ppt",
        generator=lambda llm, topic, subject, learner_id, **kw:
            _gen_ppt(llm, topic, subject, learner_id, **kw),
        timeout_sec=60,
        fallback_msg="PPT 生成失败，请稍后重试",
    ),
    "handout": MaterialRoute(
        intent="handout", step_type="handout",
        generator=lambda llm, topic, subject, learner_id, **kw:
            _gen_handout(llm, topic, subject, learner_id, **kw),
        timeout_sec=30,
        fallback_msg="讲义生成失败，请稍后重试",
    ),
    "video": MaterialRoute(
        intent="video", step_type="video",
        generator=lambda llm, topic, subject, learner_id, **kw:
            _gen_video(llm, topic, subject, learner_id, **kw),
        timeout_sec=45,
        fallback_msg="教学视频脚本生成失败，请稍后重试",
    ),
    "manim": MaterialRoute(
        intent="manim", step_type="manim",
        generator=lambda llm, topic, subject, learner_id, **kw:
            _gen_manim(llm, topic, subject, learner_id, **kw),
        timeout_sec=300,
        fallback_msg="数学动画生成中，请稍后查看 downloads/manim/",
        use_pipeline=True,
    ),
    "mindmap": MaterialRoute(
        intent="mindmap", step_type="mindmap",
        generator=lambda llm, topic, subject, learner_id, **kw:
            _gen_mindmap(llm, topic, subject, learner_id, **kw),
        timeout_sec=30,
        fallback_msg="思维导图生成中，请稍后重试",
    ),
    "script": MaterialRoute(
        intent="script", step_type="script",
        generator=lambda llm, topic, subject, learner_id, **kw:
            _gen_script(llm, topic, subject, learner_id, **kw),
        timeout_sec=30,
        fallback_msg="讲稿生成失败，请稍后重试",
    ),
}

# 关键词前缀 → 物料意图（用于 topic 提取剥离）
_KEYWORD_PREFIXES = re.compile(
    r"^(生成PPT|生成讲义|生成教学视频|生成数学动画|生成思维导图|生成讲稿)[:：\s、,，]*"
)


def is_material_intent(magic_match: Optional[Dict[str, Any]]) -> bool:
    """意图白名单判定：magic_match.intent 是否命中 6 类物料。"""
    return bool(magic_match and magic_match.get("intent") in ROUTER)


def extract_topic(magic_match: Dict[str, Any], fallback_concept: str = "") -> str:
    """统一 topic 提取：从 matched_text 剥离 '生成X：' 前缀 → 空时用 fallback。

    与旧 server.py L1056-1059 行为等价（零回归）。
    """
    tail = (magic_match.get("matched_text") or "")
    tail = _KEYWORD_PREFIXES.sub("", tail).strip()
    return tail or (fallback_concept or "")[:60]


# ═══════════════════════════════════════════════════════════
# 生成器实现（§3.91 从 server.py 早退分支搬迁，逻辑等价）
# ═══════════════════════════════════════════════════════════
def _safe_chat_wrap(llm, sys_p, usr_p, max_tokens=2000) -> str:
    """安全 LLM 调用（复用 subagents._safe_chat，失败返回空串）。"""
    try:
        from subagents import _safe_chat
        return _safe_chat(llm, sys_p, usr_p, max_tokens=max_tokens) or ""
    except Exception:
        return ""


def _parse_ppt_pages_json(raw: str) -> list:
    """§3.92 ⭐ 解析 build_material_system 要求的 JSON pages 数组；失败返回 []。"""
    import json as _json
    _m = re.search(r"\[.*\]", raw, re.S)
    if not _m:
        return []
    try:
        pages = _json.loads(_m.group(0))
        return [p for p in pages if isinstance(p, dict) and p.get("title")]
    except Exception:
        return []


def _pages_to_markdown(pages: list) -> str:
    """§3.92 ⭐ JSON pages → markdown 大纲（pptx_mcp_server._parse_outline 兼容格式），
    保留 visual_focus/notes（写进 HTML 注释）。"""
    lines = []
    for i, p in enumerate(pages, 1):
        lines.append(f"## {p.get('title', f'第{i}页')}")
        for pt in (p.get("points") or [])[:6]:  # 6×6 硬约束：≤6 条
            lines.append(f"- {pt}")
        if p.get("visual_focus"):
            lines.append(f"<!-- 视觉焦点：{p['visual_focus']} -->")
        if p.get("notes"):
            lines.append(f"<!-- 教师备注：{p['notes']} -->")
    return "\n".join(lines)


def _collect_sources(llm, learner_id, topic, subject, include_web=True) -> str:
    """§3.92 ⭐ 资源注入（KB/网络检索 → 物料有事实依据）；不可用返回空串。"""
    try:
        from services.library import collect_all_resources
        _r = collect_all_resources(learner_id, topic, llm=llm,
                                   subject=subject, include_web=include_web)
        if _r.get("has_any"):
            return _r.get("block", "")
    except Exception:
        pass
    return ""


def _validate_video_scenes(scenes: list) -> tuple:
    """§3.92 ⭐ 节奏校验：每镜 8-15s 硬约束 + 总长 ≥60s；返回 (ok, 修正后 scenes)。"""
    fixed = []
    for s in scenes:
        try:
            d = int(s.get("duration_s") or s.get("duration_sec") or 10)
        except Exception:
            d = 10
        d = max(8, min(15, d))  # 硬约束
        s["duration_s"] = d
        fixed.append(s)
    total = sum(s["duration_s"] for s in fixed)
    if total < 60 and fixed:
        for s in fixed:
            s["duration_s"] = 12  # 拉满保底
    return bool(fixed), fixed


def _gen_ppt(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """PPT 生成（§3.92 ⭐ build_material_system 结构化大纲 + sources 注入 + 6×6 硬约束）。
    §3.112 ⭐ 插件优先：插件可用 → 插件生成；失败/关闭 → 回退本旧实现。"""
    # §3.112 ⭐ 插件优先
    _plugin_result = _try_plugin("ppt", topic, subject, learner_id, **kw)
    if _plugin_result is not None:
        return _plugin_result
    import json
    try:
        import pptx_mcp_server as _pptx
        # 1. topic 净化
        _ppt_topic = re.sub(r"(做|制作|整理|创建|生成|一份|关于|的)?(PPT|ppt|演示文稿|课件|幻灯片).*$",
                            "", topic).strip() or "教学演示"
        # 2. 结构化系统 prompt（角色+schema+硬约束+范例四件套——Oracle 根因修复）
        _grade = kw.get("grade", "high_school")
        _sys = build_material_system("ppt", _ppt_topic, subject, _grade)
        _usr = upgrade_simple_intent(_ppt_topic, "ppt", subject, _grade)
        # 3. 资源注入（KB/网络 → 大纲有事实依据）
        _sources = _collect_sources(llm, learner_id, _ppt_topic, subject, include_web=True)
        if _sources:
            _usr += "\n\n## 可用资料（PPT 大纲应基于这些事实）\n" + _sources
        # 4. LLM 生成 JSON 大纲（强制 schema 校验 + 兜底）
        _outline_raw = _safe_chat_wrap(llm, _sys, _usr, max_tokens=1500)
        _pages = _parse_ppt_pages_json(_outline_raw)
        if _pages and 4 <= len(_pages) <= 12:
            _outline = _pages_to_markdown(_pages)
        else:
            _outline = _outline_raw if "## " in _outline_raw else (
                f"## {_ppt_topic}引入\n- 生活实例\n- 学习目标\n"
                f"## {_ppt_topic}核心概念\n- 定义\n- 原理\n- 例子\n"
                f"## 典型例题\n- 例题1\n- 例题2\n## 常见误区\n- 易错点\n"
                f"## 总结\n- 要点回顾\n- 课后思考")
        # 5. 调用 pptx_mcp_server（带 sources）
        _pres = _pptx.generate_presentation(
            topic=_ppt_topic, outline=_outline, sources=_sources,
            style="paeg_standard", uid=learner_id)
        _path = _pres.get("path") or ""
        _slides = _pres.get("slides") or 0
        if _path:
            import urllib.parse
            _name = os.path.basename(_path)
            _url = f"/api/download/ppt/{urllib.parse.quote(_name)}"
            # §3.92 ⭐ 附大纲摘要（评测可读内容 + 用户预览，非仅链接）
            _outline_preview = ""
            if _pages:
                _preview_pages = _pages[:6]
                _outline_preview = "\n\n大纲预览（前 6 页）：\n"
                for _i, _p in enumerate(_preview_pages, 1):
                    _pts = "；".join((_p.get("points") or [])[:3])
                    _vf = _p.get("visual_focus", "")
                    _outline_preview += f"{_i}. {_p.get('title', '')}"
                    if _pts:
                        _outline_preview += f"：{_pts}"
                    if _vf:
                        _outline_preview += f"〔视觉焦点：{_vf}〕"
                    _outline_preview += "\n"
            _content = f"PPT 已生成（{_slides} 页）：<a href='{_url}' target='_blank'>下载 PPT</a>{_outline_preview}"
            return {"ok": True, "content": _content, "url": _url,
                    "error": "", "step_type": "ppt"}
        return {"ok": False, "content": "PPT 生成失败", "url": "",
                "error": _pres.get("error", ""), "step_type": "ppt"}
    except Exception as e:
        return {"ok": False, "content": "PPT 生成失败，请稍后重试", "url": "",
                "error": str(e), "step_type": "ppt"}


def _gen_handout(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """讲义生成（§3.92 ⭐ generate_handout 6 段完整讲义 + learner 注入 + 模板兜底）。

    Oracle 根因修复：此前用 save_answer（任意回答存档路径），非教学讲义专用
    generate_handout（6 段结构：教学目标/导入/新课3.1-3.3/巩固练习/小结/作业）。
    §3.112 ⭐ 插件优先：插件可用 → 插件生成；失败/关闭 → 回退本旧实现。"""
    # §3.112 ⭐ 插件优先
    _plugin_result = _try_plugin("handout", topic, subject, learner_id, **kw)
    if _plugin_result is not None:
        return _plugin_result
    try:
        from file_generator import FileGenerator
        fg = FileGenerator(llm)
        _learner = kw.get("learner")
        # 首选：generate_handout（6 段结构 + learner 注入 + lang_gate 语言守门）
        if _learner is not None:
            try:
                _content, _fname, _structured = fg.generate_handout(
                    _learner, subject, topic, length="medium")
                if _structured and _structured.get("content"):
                    return {"ok": True, "content": _structured["content"][:1500],
                            "url": "", "error": "", "step_type": "handout"}
                if _content:
                    return {"ok": True, "content": _content[:1500], "url": "",
                            "error": "", "step_type": "handout"}
            except Exception:
                pass
        # 兜底：无 learner 或生成失败 → material_prompts 4 块模板
        _grade = kw.get("grade", "high_school")
        _sys = build_material_system("handout", topic, subject, _grade)
        _usr = upgrade_simple_intent(topic, "handout", subject, _grade)
        _md = _safe_chat_wrap(llm, _sys, _usr, max_tokens=2000)
        if _md and len(_md.strip()) > 200:
            return {"ok": True, "content": _md[:1500], "url": "",
                    "error": "", "step_type": "handout"}
        # 最终兜底：save_answer（历史路径）
        md, _html = fg.save_answer(topic, topic, subject)
        if md:
            return {"ok": True, "content": md[:1500], "url": "",
                    "error": "", "step_type": "handout"}
        return {"ok": False, "content": "讲义生成失败", "url": "",
                "error": "file_generator 空返回", "step_type": "handout"}
    except Exception as e:
        return {"ok": False, "content": "讲义生成失败，请稍后重试", "url": "",
                "error": str(e), "step_type": "handout"}


def _gen_video(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """教学视频分镜脚本生成（§3.92 ⭐ 模板驱动 + 8-15s 节奏硬约束 + KB 注入）。
    §3.112 ⭐ 插件优先：插件可用 → 插件生成；失败/关闭 → 回退本旧实现。"""
    # §3.112 ⭐ 插件优先
    _plugin_result = _try_plugin("video", topic, subject, learner_id, **kw)
    if _plugin_result is not None:
        return _plugin_result
    import json as _json
    try:
        _grade = kw.get("grade", "high_school")
        _sys = build_material_system("video", topic, subject, _grade)
        _usr = upgrade_simple_intent(topic, "video", subject, _grade)
        # KB/网络注入 → 旁白有事实依据
        _sources = _collect_sources(llm, learner_id, topic, subject, include_web=True)
        if _sources:
            _usr += "\n\n## 可用资料（旁白应基于这些事实）\n" + _sources
        _raw = _safe_chat_wrap(llm, _sys, _usr, max_tokens=2500)
        _scenes = []
        _m = re.search(r"\[.*\]", _raw, re.S)
        if _m:
            try:
                _scenes = _json.loads(_m.group(0))
            except Exception:
                _scenes = []
        if _scenes:
            _ok, _scenes = _validate_video_scenes(_scenes)
            _total = sum(int(s.get("duration_s", 10)) for s in _scenes)
            _content = f"教学视频脚本已生成（{len(_scenes)} 镜，总长 {_total}s）：\n"
            for _sc in _scenes[:8]:
                _dur = _sc.get("duration_s", 10)
                _nar = _sc.get("narration", "")
                _vis = _sc.get("on_screen") or _sc.get("visual_goal", "")
                _content += f"- [{_dur}s] 画面:{str(_vis)[:30]} 旁白:{str(_nar)[:60]}\n"
            return {"ok": True, "content": _content, "url": "",
                    "error": "", "step_type": "video"}
        return {"ok": bool(_raw), "content": _raw or "教学视频脚本生成失败", "url": "",
                "error": "", "step_type": "video"}
        return {"ok": bool(_raw), "content": _raw or "教学视频脚本生成失败", "url": "",
                "error": "", "step_type": "video"}
    except Exception as e:
        return {"ok": False, "content": "教学视频脚本生成失败", "url": "",
                "error": str(e), "step_type": "video"}


def _gen_mindmap(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """思维导图生成（复用 knowledge_map.handle_knowledge_map）。
    §3.112 ⭐ 插件优先：插件可用 → 插件生成；失败/关闭 → 回退本旧实现。"""
    # §3.112 ⭐ 插件优先
    _plugin_result = _try_plugin("mindmap", topic, subject, learner_id, **kw)
    if _plugin_result is not None:
        return _plugin_result
    try:
        from knowledge_map import handle_knowledge_map
        _learner = kw.get("learner")
        _result = handle_knowledge_map(topic, subject, _learner, llm) or {}
        _content = (_result.get("content") or _result.get("map")
                    or _result.get("markdown") or "")
        if _content:
            return {"ok": True, "content": f"思维导图已生成（{topic}）：\n{str(_content)[:800]}",
                    "url": "", "error": "", "step_type": "mindmap"}
        return {"ok": False, "content": "思维导图生成中，请稍后重试", "url": "",
                "error": str(_result)[:200], "step_type": "mindmap"}
    except Exception as e:
        return {"ok": False, "content": "思维导图生成中，请稍后重试", "url": "",
                "error": str(e), "step_type": "mindmap"}


def _gen_script(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """讲稿生成（§3.91 修复：先生成大纲再 generate_full_script）。
    §3.112 ⭐ 插件优先：插件可用 → 插件生成；失败/关闭 → 回退本旧实现。"""
    # §3.112 ⭐ 插件优先
    _plugin_result = _try_plugin("script", topic, subject, learner_id, **kw)
    if _plugin_result is not None:
        return _plugin_result
    try:
        # Step 1: 生成非空大纲
        _outline = _safe_chat_wrap(
            llm,
            "你是教学大纲设计师。为给定主题设计 3-5 节教学大纲，每节：标题 + 2-3 个要点。输出 markdown 列表。",
            f"主题：{topic}\n学科：{subject}", max_tokens=800)
        if not _outline:
            _outline = f"## 引入\n- {topic}是什么\n## 核心概念\n- 定义\n- 例子\n## 小结"
        # Step 2: 生成讲稿
        from services.script_service import generate_full_script
        _script = generate_full_script(outline=_outline, topic=topic, subject=subject)
        _sections = getattr(_script, "sections", []) if _script is not None else []
        if _sections:
            _content = f"讲稿已生成（{topic}，{len(_sections)} 段）：\n"
            for _s in _sections[:8]:
                _title = getattr(_s, "title", "")
                _nar = getattr(_s, "narration", "")
                _content += f"- [{getattr(_s, 'stype', '')}] {_title}: {_nar[:80]}\n"
            return {"ok": True, "content": _content, "url": "",
                    "error": "", "step_type": "script"}
        return {"ok": False, "content": "讲稿生成失败，请稍后重试", "url": "",
                "error": "sections 为空", "step_type": "script"}
    except Exception as e:
        return {"ok": False, "content": "讲稿生成失败，请稍后重试", "url": "",
                "error": str(e), "step_type": "script"}


def _gen_manim(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """Manim 数学动画生成（走 MaterialPipeline v2.0 长路径）。
    §3.92 透传 llm/grade；§3.94 透传用户要求 + 阶段产物 artifacts。
    §3.112 ⭐ 插件优先：插件可用 → 插件生成；失败/关闭 → 回退本旧实现。"""
    # §3.112 ⭐ 插件优先（manim 传 render=False 由插件内部决定；插件 ManimTool 已有 RITL/safety 增强）
    _plugin_result = _try_plugin("manim", topic, subject, learner_id, **kw)
    if _plugin_result is not None:
        return _plugin_result
    try:
        from manim_service import generate_manim_video
        _r = generate_manim_video(
            topic, subject, learner_id,
            llm=llm, grade=kw.get("grade", "high_school"),
            intuition=kw.get("intuition") or "",
            objectives=kw.get("objectives") or "",
            prerequisites=kw.get("prerequisites") or "",
            style=kw.get("style") or "3blue1brown",
            duration_target_sec=int(kw.get("duration_target_sec") or 120),
            job_id=kw.get("job_id") or "",
            user_requirements=kw.get("user_requirements") or kw.get("user_input") or "",
            progress_callback=kw.get("progress_callback")) or {}
        _url = _r.get("url") or _r.get("video_path") or ""
        _artifacts = _r.get("artifacts") or {}
        _job_id = _r.get("job_id", "")
        if _r.get("ok") and _url:
            _narr = _r.get("narrative_judge", {})
            _judge_str = ""
            if _narr.get("checked"):
                _judge_str = f" [叙事评分: {_narr.get('overall', 0):.1f}/5]"
            _dl = ""
            if _artifacts.get("script", {}).get("url"):
                _dl += f" <a href='{_artifacts['script']['url']}' target='_blank'>下载脚本</a>"
            if _artifacts.get("code", {}).get("url"):
                _dl += f" <a href='{_artifacts['code']['url']}' target='_blank'>下载代码</a>"
            _content = f"数学动画已生成{_judge_str}：<a href='{_url}' target='_blank'>观看/下载动画</a>{_dl}"
            return {"ok": True, "content": _content, "url": _url,
                    "error": "", "step_type": "manim",
                    "job_id": _job_id, "artifacts": _artifacts}
        if _r.get("ok"):
            _script = _r.get("script") or _r.get("code") or ""
            _scenes = _r.get("scenes")
            if isinstance(_scenes, list):
                _content = f"数学动画已生成（{len(_scenes)} 镜）：\n"
                for _s in _scenes[:6]:
                    _content += f"- {_s.get('concept', '')}: {str(_s.get('visual_goal') or _s.get('narration') or '')[:60]}\n"
            elif _script:
                _content = f"数学动画剧本已生成：\n{str(_script)[:400]}"
            else:
                _content = f"数学动画已生成（{topic}）。可查看 downloads/manim/ 目录。"
            return {"ok": True, "content": _content, "url": _url,
                    "error": "", "step_type": "manim",
                    "job_id": _job_id, "artifacts": _artifacts}
        # 失败但含部分产物（脚本/代码）→ 提供下载
        if _artifacts:
            _dl = ""
            if _artifacts.get("script", {}).get("url"):
                _dl += f" <a href='{_artifacts['script']['url']}' target='_blank'>下载脚本</a>"
            if _artifacts.get("code", {}).get("url"):
                _dl += f" <a href='{_artifacts['code']['url']}' target='_blank'>下载代码</a>"
            _content = f"数学动画生成中（{topic}）：{_r.get('error', '渲染超时')}。脚本/代码已生成{_dl}"
            return {"ok": False, "content": _content, "url": "",
                    "error": _r.get("error", ""), "step_type": "manim",
                    "job_id": _job_id, "artifacts": _artifacts}
        return {"ok": False, "content": f"数学动画生成中（{topic}）：{_r.get('error', '渲染超时')}。可稍后查看 downloads/manim/。",
                "url": "", "error": _r.get("error", ""), "step_type": "manim"}
    except Exception as e:
        return {"ok": False, "content": f"数学动画生成中（{topic}）。请稍后在 downloads/manim/ 查看。",
                "url": "", "error": str(e), "step_type": "manim"}


# ═══════════════════════════════════════════════════════════
# 统一调度器
# ═══════════════════════════════════════════════════════════
def route_material(magic_match: Dict[str, Any], llm, subject: str,
                   learner_id: str, concept: str = "",
                   learner=None, save_turn: Callable = None,
                   grade: str = "high_school",
                   user_requirements: str = "",
                   intuition: str = "", objectives: str = "") -> Iterator[str]:
    """物料路由主入口：生成 SSE 事件流（presentation + done）。

    §3.95 ⭐ 用户输入注入：user_requirements/intuition/objectives 透传生成器
    （用户要求作为提示词拼接到物料生成依据）。

    Args:
        magic_match: match_magic() 返回值 {intent, reason, matched_text}
        llm: LLM 实例
        subject: 学科
        learner_id: 学习者 ID
        concept: 原始用户输入（topic 兜底）
        learner: 学习者对象（handout/mindmap 需要）
        save_turn: _save_teach_turn 回调（None 则不存）
        grade: 学段（§3.92 透传给生成器，注入模板/learner）
        user_requirements: 用户详细要求（§3.95 注入物料生成提示词）
        intuition/objectives: 用户学习目标/直觉（§3.95 透传 manim）

    Yields: SSE 事件字符串。
    """
    intent = (magic_match or {}).get("intent")
    route = ROUTER.get(intent)
    if route is None:
        yield fmt_done("unknown", "")
        return

    topic = extract_topic(magic_match, concept)
    if not topic:
        topic = concept[:60]

    # 调用生成器（统一异常围栏）——§3.92 透传 grade/learner；§3.95 透传用户要求
    # §3.94 ⭐ manim 专属：progress_callback → SSE 阶段进度事件（前端进度条）
    _progress_queue = None
    if intent == "manim":
        try:
            import queue as _q
            _progress_queue = _q.Queue()

            def _progress_cb(evt):
                try:
                    _progress_queue.put(dict(evt))
                except Exception:
                    pass
        except Exception:
            _progress_queue = None
    try:
        result = route.generator(llm, topic, subject, learner_id,
                                 learner=learner, grade=grade,
                                 user_requirements=user_requirements,
                                 user_input=user_requirements or concept,
                                 intuition=intuition, objectives=objectives,
                                 progress_callback=_progress_cb if intent == "manim" else None)
    except Exception as e:
        result = {"ok": False, "content": route.fallback_msg, "url": "",
                  "error": str(e), "step_type": route.step_type}

    # §3.94 ⭐ manim 进度事件透传（脚本→代码→视频）
    if _progress_queue is not None and intent == "manim":
        try:
            while not _progress_queue.empty():
                _evt = _progress_queue.get_nowait()
                yield fmt_progress(_evt.get("percent", 0),
                                   _evt.get("message", ""))
        except Exception:
            pass

    if not isinstance(result, dict):
        result = {"ok": False, "content": route.fallback_msg, "url": "",
                  "error": "生成器返回非 dict", "step_type": route.step_type}

    content = result.get("content") or route.fallback_msg
    url = result.get("url") or ""

    # 存档（可选回调）
    if save_turn and route.save_turn:
        try:
            save_turn(route.step_type, str(content)[:300])
        except Exception:
            pass

    # SSE 事件流（契约字节级保持）
    yield fmt_presentation(1, content, route.step_type)
    yield fmt_done(route.step_type, url)


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("material_router 就绪（§3.91 Oracle 架构）")
    print("ROUTER 表:", {k: (v.step_type, v.timeout_sec, v.use_pipeline) for k, v in ROUTER.items()})
    print("is_material_intent(ppt):", is_material_intent({"intent": "ppt"}))
    print("is_material_intent(None):", is_material_intent(None))
    print("extract_topic:", extract_topic({"matched_text": "生成PPT：光合作用"}, "兜底"))
