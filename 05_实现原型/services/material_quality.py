# -*- coding: utf-8 -*-
"""services/material_quality.py —— §3.79 ⭐ 物料确定性质量检查（总需求 Q7 落地）

对称补齐 LessonPrep 产出物的结构检查（video_script_check 已由
visual_script_validator.validate_lesson_script 提供，本模块补讲义/讲稿/思维导图）：

  - check_handout(markdown)：讲义 5 节结构（学习目标/核心内容/典型例题/巩固练习/小结）
  - check_lecture_script(markdown)：讲稿 开场/主体/小结 + 时长标注
  - check_mindmap(markdown)：思维导图缩进树（含列表项 + 层级 + 无占位残留）

原则：宽松防误伤（与 B3 一致），核心是"结构完整 + 无占位残留"；
全部确定性、无 LLM、可测试；结果写入 quality_report（结构化、可审计）。
"""
from __future__ import annotations

import re
from typing import Dict, List


def _base(passed: bool, errors: List[str], **extra) -> Dict[str, object]:
    return {"passed": passed, "errors": errors, "checked": True, **extra}


def check_handout(markdown: str) -> Dict[str, object]:
    """讲义结构检查：应含学习目标/核心内容/典型例题/巩固练习/小结（命中 >=3 节）。

    Returns: {"passed", "errors", "sections_found", "checked"}
    """
    text = str(markdown or "")
    errors: List[str] = []
    _sections = ["学习目标", "核心内容", "典型例题", "巩固练习", "小结"]
    _found = [s for s in _sections if s in text]
    if len(_found) < 3:
        errors.append(f"讲义结构不完整：仅命中 {len(_found)}/5 节（应含≥3：{_found or '无'}）")
    if len(text.strip()) < 60:
        errors.append("讲义过短（<60 字）")
    if re.search(r"待补充|\(写|（写|占位|TODO", text):
        errors.append("存在占位残留（待补充/（写…/TODO 等）")
    return _base(not errors, errors, sections_found=_found)


def check_lecture_script(markdown: str) -> Dict[str, object]:
    """讲稿结构检查：开场/主体/小结 + 时长标注（秒/分钟）。

    注意与 visual_script_validator.validate_lesson_script（视频脚本）区分。

    Returns: {"passed", "errors", "has_open,has_body,has_close,has_duration", "checked"}
    """
    text = str(markdown or "")
    errors: List[str] = []
    _has_open = bool(re.search(r"开场|引入|导入|同学们好|开始", text))
    _has_body = bool(re.search(r"主体|环节|新授|讲解|展开", text))
    _has_close = bool(re.search(r"小结|总结|回顾|收尾|结束", text))
    _has_duration = bool(re.search(r"秒|分钟|min|minute", text))
    if not (_has_open and _has_body and _has_close):
        errors.append("讲稿缺少 开场/主体/小结 三段结构"
                      f"（open={_has_open} body={_has_body} close={_has_close}）")
    if not _has_duration:
        errors.append("讲稿缺少时长标注（秒/分钟）")
    if len(text.strip()) < 80:
        errors.append("讲稿过短（<80 字）")
    if re.search(r"待补充|\(写|（写|占位|TODO", text):
        errors.append("存在占位残留（待补充/（写…/TODO 等）")
    return _base(not errors, errors,
                 has_open=_has_open, has_body=_has_body,
                 has_close=_has_close, has_duration=_has_duration)


def check_mindmap(markdown: str) -> Dict[str, object]:
    """思维导图检查：Markdown 缩进树（含列表项 + 至少 2 层缩进 + 无占位残留）。

    Returns: {"passed", "errors", "list_items,levels", "checked"}
    """
    text = str(markdown or "")
    errors: List[str] = []
    _items = [ln for ln in text.splitlines() if re.match(r"^\s*[-*+]\s+\S", ln)]
    _levels = set()
    for _ln in _items:
        _indent = len(_ln) - len(_ln.lstrip(" \t"))
        _levels.add(_indent // 2 if _indent else 0)
    if len(_items) < 3:
        errors.append(f"思维导图列表项过少（{len(_items)} < 3）")
    if len(_levels) < 2:
        errors.append(f"思维导图缺少层级（仅 {len(_levels)} 层，应 ≥2：根+分支）")
    if re.search(r"待补充|\(写|（写|占位|TODO|此处插入", text):
        errors.append("存在占位残留（待补充/（写…/TODO 等）")
    return _base(not errors, errors, list_items=len(_items), levels=sorted(_levels))


__all__ = ["check_handout", "check_lecture_script", "check_mindmap"]
