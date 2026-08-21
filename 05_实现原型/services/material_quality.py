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

    §3.79 Round 11 ⭐ 增强（张宇扬课件特征：真实数据例题）：讲义还应含
    具体例题（含数据/公式/数字）与练习/思考引导（宽松防误伤，仅作质量提示项）。

    Returns: {"passed", "errors", "sections_found", "has_concrete_example", "has_practice", "checked"}
    """
    text = str(markdown or "")
    errors: List[str] = []
    _sections = ["学习目标", "核心内容", "典型例题", "巩固练习", "小结"]
    _found = [s for s in _sections if s in text]
    if len(_found) < 3:
        errors.append(f"讲义结构不完整：仅命中 {len(_found)}/5 节（应含≥3：{_found or '无'}）")
    if len(text.strip()) < 60:
        errors.append("讲义过短（<60 字）")
    # Round 11 ⭐ 真实数据例题（含数字/公式/具体数值）
    _has_concrete = bool(re.search(r"\d|例题|例\s*[0-9一二三四五六七八九十]|例如|如：|=", text))
    # 练习/思考引导
    _has_practice = bool(re.search(r"练习|巩固|思考|试一试|你来", text))
    if not _has_concrete:
        errors.append("讲义缺具体例题（含数据/公式/数值的例证，张宇扬课件特征）")
    if not _has_practice:
        errors.append("讲义缺练习/思考引导（节末应有可操作练习或思考题）")
    if re.search(r"待补充|\(写|（写|占位|TODO", text):
        errors.append("存在占位残留（待补充/（写…/TODO 等）")
    return _base(not errors, errors, sections_found=_found,
                 has_concrete_example=_has_concrete, has_practice=_has_practice)


def check_lecture_script(markdown: str) -> Dict[str, object]:
    """讲稿结构检查：开场/主体/小结 + 时长标注（秒/分钟）。

    §3.79 Round 11 ⭐ 增强（张宇扬课件特征：口语化教学）：讲稿还应含
    口语过渡句（好/那么/接下来/我们）与生活化例子（宽松防误伤）。

    注意与 visual_script_validator.validate_lesson_script（视频脚本）区分。

    Returns: {"passed", "errors", "has_open,has_body,has_close,has_duration",
              "has_transition", "has_example", "checked"}
    """
    text = str(markdown or "")
    errors: List[str] = []
    _has_open = bool(re.search(r"开场|引入|导入|同学们好|开始", text))
    _has_body = bool(re.search(r"主体|环节|新授|讲解|展开", text))
    _has_close = bool(re.search(r"小结|总结|回顾|收尾|结束", text))
    _has_duration = bool(re.search(r"秒|分钟|min|minute", text))
    # Round 11 ⭐ 口语过渡句 + 生活化例子
    _has_transition = bool(re.search(r"好，|那么|接下来|我们|大家|你看|注意", text))
    _has_example = bool(re.search(r"例子|例如|比如|类比|生活|就像", text))
    if not (_has_open and _has_body and _has_close):
        errors.append("讲稿缺少 开场/主体/小结 三段结构"
                      f"（open={_has_open} body={_has_body} close={_has_close}）")
    if not _has_duration:
        errors.append("讲稿缺少时长标注（秒/分钟）")
    if not _has_transition:
        errors.append("讲稿缺口语过渡句（好/那么/接下来/我们 等，讲稿是“说”出来的）")
    if not _has_example:
        errors.append("讲稿缺生活化例子（举例/类比让抽象概念落地）")
    if len(text.strip()) < 80:
        errors.append("讲稿过短（<80 字）")
    if re.search(r"待补充|\(写|（写|占位|TODO", text):
        errors.append("存在占位残留（待补充/（写…/TODO 等）")
    return _base(not errors, errors,
                 has_open=_has_open, has_body=_has_body,
                 has_close=_has_close, has_duration=_has_duration,
                 has_transition=_has_transition, has_example=_has_example)


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


def check_ppt_outline(markdown: str) -> Dict[str, object]:
    """PPT 大纲检查（§3.79 Round 11 ⭐ 新增——物料检查对称补齐 PPT）：

    真实 PPT 大纲应满足：
      - 分页结构（## 第N页 / --- / 页标题行）
      - 每页有要点（列表项 ≥1）
      - 覆盖 5 页左右（封面/引入/定义/例子/小结）
      - 无占位残留

    Returns: {"passed", "errors", "pages", "items_per_page", "checked"}
    """
    text = str(markdown or "")
    errors: List[str] = []
    # 分页识别：## 页 / --- 分隔 / 行尾冒号标题
    _lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    _pages = []
    _cur: List[str] = []
    for _ln in _lines:
        if re.match(r"^(#{2,4} |---|幻灯片|第\s*[0-9一二三四五六七八九十]+\s*页)", _ln):
            if _cur:
                _pages.append(_cur)
            _cur = [_ln]
        else:
            _cur.append(_ln)
    if _cur:
        _pages.append(_cur)
    _n_pages = len(_pages)
    if _n_pages < 3:
        errors.append(f"PPT 大纲分页过少（{_n_pages} < 3 页：封面/主体/小结）")
    _items_total = 0
    _items_per_page: List[int] = []
    for _pg in _pages:
        _n = sum(1 for _l in _pg if re.match(r"^\s*[-*+]\s+\S", _l))
        _items_per_page.append(_n)
        _items_total += _n
    if _items_total < 6:
        errors.append(f"PPT 大纲要点过少（共 {_items_total} < 6 条要点）")
    if _n_pages >= 3 and any(_n == 0 for _n in _items_per_page[:3]):
        errors.append("PPT 大纲存在空页（无任何要点）")
    if re.search(r"待补充|\(写|（写|占位|TODO|此处插入|图片\s*[（(]?\s*$", text):
        errors.append("存在占位残留（待补充/（写…/TODO/空图片占位 等）")
    if len(text.strip()) < 60:
        errors.append("PPT 大纲过短（<60 字）")
    return _base(not errors, errors, pages=_n_pages,
                 items_per_page=_items_per_page)


__all__ = ["check_handout", "check_lecture_script", "check_mindmap",
           "check_ppt_outline"]
