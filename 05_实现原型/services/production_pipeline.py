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
    from manim_service import is_manim_subject

    errors: List[str] = []

    # ── 1. 解析大纲 → IR ──
    try:
        pages = parse_outline_with_slots(outline)
    except Exception as e:
        return {"ok": False, "error": f"大纲解析失败: {e}"}
    if not pages:
        return {"ok": False, "error": "大纲为空"}

    # ── 2. 学科类型分派（用户需求核心）──
    _manim_ok = is_manim_subject(subject)
    _manim_slots = manim_slots(pages) if _manim_ok else []
    if manim_slots(pages) and not _manim_ok:
        errors.append(f"学科 '{subject}' 非可视化类，manim 动画占位已忽略（纯讲解视频）")
    _asset_slots = asset_slots(pages)

    # ── 3. 预渲染 manim 片段（白名单学科 + 占位存在时）──
    manim_results: dict = {}
    if _manim_slots:
        from manim_service import generate_manim_video
        for slot in _manim_slots:
            topic_slot = slot.get("topic") or ""
            try:
                r = generate_manim_video(topic_slot, subject=subject, learner_id=learner_id)
                if r.get("ok") and r.get("path"):
                    manim_results[topic_slot] = r["path"]
                else:
                    errors.append(f"manim 渲染失败({topic_slot}): {r.get('error', '')[:100]}")
            except Exception as e:
                errors.append(f"manim 异常({topic_slot}): {str(e)[:100]}")

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

    # ── 5. 融合视频合成 ──
    ir = {"topic": topic, "pages": pages}
    try:
        result = compose_with_slots(
            topic, ir, manim_results, asset_results, learner_id=learner_id)
    except Exception as e:
        return {"ok": False, "error": f"视频合成异常: {e}", "errors": errors}
    result["errors"] = errors
    if not result.get("ok"):
        result["errors"] = errors
        return result

    # ── 6. 可选：同步生成 PPT（含动画占位页）──
    ppt_url = ""
    try:
        from pptx_mcp_server import generate_ppt as _gen_ppt
        _pr = _gen_ppt(topic, outline, sources="", uid=str(learner_id), style=style)
        if _pr.get("ok"):
            ppt_url = _pr.get("url") or _pr.get("path") or ""
    except Exception as e:
        errors.append(f"PPT 生成失败(不影响视频): {str(e)[:100]}")

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
