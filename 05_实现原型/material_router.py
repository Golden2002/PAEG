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


def _gen_ppt(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """PPT 生成（复用 pptx_mcp_server 排版，返回下载 URL）。"""
    import json
    try:
        import pptx_mcp_server as _pptx
        # PPT topic 净化（沿用旧 L1070）
        _ppt_topic = re.sub(r"(做|制作|整理|创建|生成|一份|关于|的)?(PPT|ppt|演示文稿|课件|幻灯片).*$",
                            "", topic).strip() or "教学演示"
        # 大纲：LLM 生成
        _outline = _safe_chat_wrap(
            llm,
            "你是教学 PPT 大纲生成器。为给定主题生成教学 PPT 大纲。严格使用以下格式：\n"
            "## 章节标题\n- 要点1\n- 要点2\n要求：5-7 个章节，每章 2-4 个要点；内容准确、有例子、由浅入深；只输出大纲。",
            f"主题：{_ppt_topic}", max_tokens=1200)
        if "## " not in _outline:
            _outline = (
                f"## {_ppt_topic}引入\n- 生活实例\n- 学习目标\n"
                f"## {_ppt_topic}核心概念\n- 定义\n- 原理\n- 例子\n"
                f"## 典型例题\n- 例题1\n- 例题2\n## 常见误区\n- 易错点\n"
                f"## 总结\n- 要点回顾\n- 课后思考")
        _pres = _pptx.generate_presentation(
            topic=_ppt_topic, outline=_outline, style="paeg_standard", uid=learner_id)
        _path = _pres.get("path") or ""
        _slides = _pres.get("slides") or 0
        if _path:
            import urllib.parse
            _name = os.path.basename(_path)
            _url = f"/api/download/ppt/{urllib.parse.quote(_name)}"
            _content = f"PPT 已生成（{_slides} 页）：<a href='{_url}' target='_blank'>下载 PPT</a>"
            return {"ok": True, "content": _content, "url": _url,
                    "error": "", "step_type": "ppt"}
        return {"ok": False, "content": "PPT 生成失败", "url": "",
                "error": _pres.get("error", ""), "step_type": "ppt"}
    except Exception as e:
        return {"ok": False, "content": "PPT 生成失败，请稍后重试", "url": "",
                "error": str(e), "step_type": "ppt"}


def _gen_handout(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """讲义生成（复用 file_generator.save_answer——与 material_pipeline.handout_pipeline 同路径）。"""
    try:
        from file_generator import FileGenerator
        fg = FileGenerator(llm)
        # save_answer 内部生成讲义内容（无需 learner 对象，旧分支同路径）
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
    """教学视频分镜脚本生成。"""
    import json as _json
    try:
        _raw = _safe_chat_wrap(
            llm,
            "你是教学视频编剧。为给定主题设计 3-8 个镜头（scene）的教学视频脚本，"
            "每镜：id、concept、narration（旁白台词）、duration_sec（8-15 秒）、visual_goal（画面目标）。"
            "总长 60-180 秒：引入（钩子）→主体→take-away 结尾。输出 JSON 数组 scenes。",
            f"主题：{topic}\n学科：{subject}", max_tokens=2000)
        _m = re.search(r"\[.*\]", _raw, re.S)
        if _m:
            _scenes = _json.loads(_m.group(0))
            _content = f"教学视频脚本已生成（{len(_scenes)} 镜）：\n"
            for _sc in _scenes[:8]:
                _content += f"- [{_sc.get('duration_sec', 10)}s] {_sc.get('concept', '')}: {_sc.get('narration', '')}\n"
            return {"ok": True, "content": _content, "url": "",
                    "error": "", "step_type": "video"}
        return {"ok": bool(_raw), "content": _raw or "教学视频脚本生成失败", "url": "",
                "error": "", "step_type": "video"}
    except Exception as e:
        return {"ok": False, "content": "教学视频脚本生成失败", "url": "",
                "error": str(e), "step_type": "video"}


def _gen_mindmap(llm, topic, subject, learner_id, **kw) -> MaterialResult:
    """思维导图生成（复用 knowledge_map.handle_knowledge_map）。"""
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
    """讲稿生成（§3.91 修复：先生成大纲再 generate_full_script）。"""
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
    """Manim 数学动画生成（走 MaterialPipeline v2.0 长路径）。"""
    try:
        from manim_service import generate_manim_video
        _r = generate_manim_video(topic, subject, learner_id) or {}
        _url = _r.get("url") or _r.get("video_path") or ""
        if _r.get("ok") and _url:
            _content = f"数学动画已生成：<a href='{_url}' target='_blank'>观看/下载动画</a>"
            return {"ok": True, "content": _content, "url": _url,
                    "error": "", "step_type": "manim"}
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
                    "error": "", "step_type": "manim"}
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
                   learner=None, save_turn: Callable = None) -> Iterator[str]:
    """物料路由主入口：生成 SSE 事件流（presentation + done）。

    Args:
        magic_match: match_magic() 返回值 {intent, reason, matched_text}
        llm: LLM 实例
        subject: 学科
        learner_id: 学习者 ID
        concept: 原始用户输入（topic 兜底）
        learner: 学习者对象（handout/mindmap 需要）
        save_turn: _save_teach_turn 回调（None 则不存）

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

    # 调用生成器（统一异常围栏）
    try:
        result = route.generator(llm, topic, subject, learner_id, learner=learner)
    except Exception as e:
        result = {"ok": False, "content": route.fallback_msg, "url": "",
                  "error": str(e), "step_type": route.step_type}

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
