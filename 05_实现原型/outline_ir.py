# -*- coding: utf-8 -*-
"""大纲中间表示（IR）：讲义/PPT 大纲 → 带 manim/asset 占位符的结构化页面（v1.0 ⭐）。

用户需求：讲义/PPT 制作时要为视频预留 manim 演示动画的空间；视频制作时把
manim 片段剪辑进时间轴。本模块定义占位标记语法 + 解析器，供
production_pipeline / video_service / pptx_mcp_server 共用。

占位标记语法（在 "## 标题" 页的要点行中）：
- `[[manim: 主题描述]]`          → 独立动画页（视频中替换为 manim 片段）
- `[[manim: 主题描述 | 描述文本]]` → 带副文本的动画占位
- `[[asset: 类型: 路径]]`        → 资源引用（image 等，视频页叠图/背景）
"""
from __future__ import annotations

import re
from typing import List, Dict, Optional

# 匹配 [[manim: ...]] / [[asset: ...]]，支持 "|" 副文本
_SLOT_RE = re.compile(r"\[\[(manim|asset):\s*([^|\]]+?)(?:\|\s*([^\]]+))?\]\]")


def _build_slot(m: re.Match) -> dict:
    kind = m.group(1)
    if kind == "manim":
        return {
            "kind": "manim",
            "topic": m.group(2).strip(),
            "description": (m.group(3) or "").strip(),
            "placement": "page",  # v1: 独立动画页
        }
    # asset
    path = m.group(2).strip()
    asset_type = "image"
    if ":" in path:
        asset_type, _, path = path.partition(":")
        path = path.strip()
    return {
        "kind": "asset",
        "asset_type": asset_type.strip() or "image",
        "path": path,
        "description": (m.group(3) or "").strip(),
    }


def parse_outline_with_slots(outline: str) -> List[dict]:
    """解析大纲为 pages 列表；每页 points 中的 [[…]] 拆为 slots。

    返回结构（与 video_service._parse_outline 兼容 + slots 字段）：
    [{"title": str, "points": [str, ...], "slots": [{kind,topic/path,...}, ...]}]
    """
    from video_service import _parse_outline  # 复用既有分页逻辑

    pages = _parse_outline(outline)
    for p in pages:
        slots: List[dict] = []
        plain: List[str] = []
        for line in p.get("points") or []:
            # 整行是占位符
            m_full = _SLOT_RE.fullmatch(str(line).strip())
            if m_full:
                slots.append(_build_slot(m_full))
                continue
            # 行内混入占位符（"要点文本 [[manim: …]] 后续"）
            m_inline = _SLOT_RE.search(str(line))
            if m_inline:
                pre = str(line)[: m_inline.start()].strip()
                post = str(line)[m_inline.end():].strip()
                if pre:
                    plain.append(pre)
                slots.append(_build_slot(m_inline))
                if post:
                    plain.append(post)
            else:
                plain.append(str(line))
        p["points"] = plain
        p["slots"] = slots
    return pages


def has_manim_slots(pages: List[dict]) -> bool:
    """是否含 manim 占位（决定走融合管线还是旧纯讲解路径）。"""
    return any(
        s.get("kind") == "manim" for p in pages for s in p.get("slots") or []
    )


def manim_slots(pages: List[dict]) -> List[dict]:
    """收集全部 manim 占位。"""
    return [s for p in pages for s in p.get("slots") or [] if s.get("kind") == "manim"]


def asset_slots(pages: List[dict]) -> List[dict]:
    """收集全部 asset 占位。"""
    return [s for p in pages for s in p.get("slots") or [] if s.get("kind") == "asset"]
