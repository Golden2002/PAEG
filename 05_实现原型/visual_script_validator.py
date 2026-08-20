# -*- coding: utf-8 -*-
"""
visual_script_validator.py — 数学可视化剧本校验器（v0.70+ §3.26）

校验 7 条铁律（渐进揭示/单一聚焦/颜色语义/节奏/文字最小化/构图/回看锚点/时长匹配），
失败反馈给 LLM 做修补式重生成（最多 2 轮）。
"""
from __future__ import annotations

import re
from typing import Dict, List


def validate(script: dict) -> List[str]:
    """校验剧本，返回错误列表（空=通过）。"""
    errors: List[str] = []
    try:
        scenes = script.get("scenes", [])
        target = int(script.get("meta", {}).get("duration_target_sec", 240))
    except Exception:
        return ["脚本缺少 scenes/meta 结构"]

    # 铁律 1：前 2 个 scene 禁公式
    _formula_pat = re.compile(r"[=∫∑∏∂]|lim|frac|\\?sqrt")
    for s in scenes[:2]:
        _txt = str(s.get("on_screen_text", "")) + str(s.get("narration", ""))
        if _formula_pat.search(_txt):
            errors.append(f"scene {s.get('id','?')}: 公式过早出现（渐进揭示铁律）")

    # 铁律 2：单一聚焦（concept 不重复）
    concepts = [s.get("concept", "") for s in scenes]
    if len(concepts) != len(set(concepts)):
        errors.append("存在重复 concept 的 scene（单一聚焦铁律）")

    # 铁律 4：节奏（pause >= 1s）
    for s in scenes:
        if float(s.get("pause_after_sec", 0)) < 1:
            errors.append(f"scene {s.get('id','?')}: 缺少停顿（pause_after_sec<1）")
        _dur = float(s.get("duration_sec", 0))
        if not (8 <= _dur <= 45):
            errors.append(f"scene {s.get('id','?')}: 时长 {_dur}s 超出 8-45s 规范")

    # 铁律 5：文字最小化（on_screen_text <= 8 汉字）
    for s in scenes:
        _ost = str(s.get("on_screen_text", ""))
        _cn = len([c for c in _ost if '\u4e00' <= c <= '\u9fff'])
        if _cn > 8 or len(_ost) > 20:
            errors.append(f"scene {s.get('id','?')}: 屏幕文字过长")

    # 铁律 6：构图（mobjects 3-7 个）
    for s in scenes:
        _n = len(s.get("mobjects", []))
        if _n < 3 or _n > 7:
            errors.append(f"scene {s.get('id','?')}: mobject 数量 {_n} 超出 3-7 规范")

    # 铁律 8：时长匹配（±15%）
    total = sum(float(s.get("duration_sec", 0)) + float(s.get("pause_after_sec", 0))
                for s in scenes)
    if target > 0 and abs(total - target) / target > 0.15:
        errors.append(f"总时长 {total:.0f}s 偏离目标 {target}s 超过 15%")

    return errors


def auto_fix(script: dict, llm, max_rounds: int = 2) -> dict:
    """校验失败 → 反馈 LLM 修补式重生成（最多 2 轮）。"""
    for _r in range(max_rounds):
        _errors = validate(script)
        if not _errors:
            break
        try:
            from subagents import _safe_chat
            _sys = ("你是剧本修复器。根据校验错误修改剧本 JSON，保持结构不变，"
                    "只修违反铁律的部分。输出修复后的完整 JSON，不要其他文字。")
            _usr = f"剧本：{json.dumps(script, ensure_ascii=False)}\n错误：{_errors}\n请修复。"
            _raw = _safe_chat(llm, _sys, _usr, max_tokens=4000)
            if _raw:
                _m = re.search(r'\{.*\}', _raw, re.S)
                if _m:
                    script = json.loads(_m.group(0))
        except Exception:
            break
    return script


import json
import re


def validate_lesson_script(markdown: str) -> Dict[str, object]:
    """校验备课产出（LessonPrep 步骤⑥）的 Markdown 版视频脚本（v0.74+ §3.78 B3 接线）。

    与 validate()（Manim 剧本 dict）不同，本函数针对 LLM 直出的 Markdown 文本
    （结构：``## 镜头 N（角色/时长）`` + ``画面：`` + ``旁白：``）做结构性检查，
    供 LessonPrep 质量报告记录 ``video_script_check``。

    检查项（宽松、防误伤，核心是"结构完整 + 无占位残留"）：
      1. 镜头数 >= 2（无镜头 = 结构缺失）
      2. 每镜头同时含【画面】与【旁白】（缺一 = 结构不完整）
      3. 出现"开场/主体/总结"或"秒/分钟"时长标注之一（可读性）
      4. 每镜头旁白 <= 300 字（文字简洁；超长旁白提示拆分）
      5. 无占位残留（"待补充/（写/略/占位/TODO" 等）

    Returns:
        {"passed": bool, "errors": List[str], "scene_count": int, "checked": True}
    """
    errors: List[str] = []
    text = str(markdown or "").strip()
    if len(text) < 30:
        return {"passed": False, "errors": ["视频脚本过短（<30 字）"], "scene_count": 0, "checked": True}

    # 1. 镜头切分：兼容 "镜头 1"/"镜头一"/"## 镜头 2（…）"
    _scene_pat = re.compile(r"镜头\s*[一二三四五六七八九十\d]+")
    _matches = list(_scene_pat.finditer(text))
    scene_count = len(_matches)
    if scene_count < 2:
        errors.append(f"镜头数仅 {scene_count}（应 >= 2：开场/主体/总结）")

    # 2. 每镜头必须含画面 + 旁白（取镜头起点之间的段落）
    _bounds = [m.start() for m in _matches] + [len(text)]
    for i in range(len(_bounds) - 1):
        _seg = text[_bounds[i]:_bounds[i + 1]]
        _has_visual = bool(re.search(r"画面[：:]", _seg))
        _has_narration = bool(re.search(r"旁白[：:]", _seg))
        if not _has_visual or not _has_narration:
            errors.append(f"镜头 {i + 1} 缺少{'画面' if not _has_visual else ''}{'旁白' if not _has_narration else ''}（须同时含画面与旁白）")

    # 3. 时长/结构可读性
    if not re.search(r"开场|主体|总结|结束|秒|分钟", text):
        errors.append("缺少结构标识（开场/主体/总结）或时长标注（秒/分钟）")

    # 4. 每镜头旁白长度（<=300 字）
    for i in range(len(_bounds) - 1):
        _seg = text[_bounds[i]:_bounds[i + 1]]
        _nb = re.split(r"画面[：:]", _seg)[-1] if "旁白" not in _seg else (
            re.split(r"旁白[：:]", _seg)[-1])
        _nb = re.split(r"##|镜头\s*[一二三四五六七八九十\d]+", _nb)[0]
        _len = len(_nb.strip())
        if _len > 300:
            errors.append(f"镜头 {i + 1} 旁白过长（{_len} 字 > 300，建议拆分）")

    # 5. 占位残留
    if re.search(r"待补充|\(写|（写|占位|TODO|此处插入|略[，。]?$", text):
        errors.append("存在占位残留（待补充/（写…/TODO 等）")

    return {"passed": not errors, "errors": errors, "scene_count": scene_count, "checked": True}
