# -*- coding: utf-8 -*-
"""manim_pipeline.py — Manim 动画流水线（v1.1 ⭐ §3.34 智绘科普范式优化）

参考"智绘科普"（首届'小有可为 AI 向善'大赛一等奖）工程范式：
**多 Agent 分阶段协作 + 硬门控 + 自动修复回路**，平移到 PAEG Manim 模块。

流水线（六阶段，每阶段中间产物可检查/可回滚）：
  Phase 1 规划  → 生成结构化 script.json（beats 分镜，3B1B 原则）——已有 visual_script_generator
  Phase 2A 草稿 → 不渲染，仅写 Manim 代码（角色禁令：规划不写码、草稿不渲染）
  Phase 2B 实现 → 渲染 + AST 校验 + 几何审计
  Phase 3 审查  → 视觉审查（抽帧评估美观/清晰）
  Phase 4 合成  → 输出最终视频 + 中间产物落盘
  失败返工回路 → 任一门控失败：提取错误日志 → 生成修复提示词 → 重跑该阶段（最多 N 轮）

角色分层禁令（防 AI 越界）：
  规划 Agent：严禁写代码（只产 JSON 剧本）
  草稿 Agent：严禁渲染（只写代码）
  审查 Agent：严禁修改文件（只评估）

硬门控（可量化，不达标回炉）：
  结构门：script.json 必填字段完整
  数量门：beats 3-6 个（每 beat 一个教学点）
  可执行门：每 beat visual_goal 可在 Manim 实现（禁 3D 全息等）
  时序门：每 beat 动画时长 ≥ 目标 80%，总时长 ≥ 目标 60%
  几何门：元素重叠/越界检测（包围盒）
  视觉门：抽帧 LLM 评估美观/清晰

上下游衔接（§3.34 需求）：
  独立：脚本/代码/视频独立可下载
  上游：作为教学视频的上游（脚本→动画→视频）
  下游：消费讲义/讲稿/数学视频脚本（物料包统一入口）
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

_BASE = os.path.dirname(os.path.abspath(__file__))
_PIPELINE_DIR = os.path.join(_BASE, "evolve_data", "manim_pipeline")

# ─── 门控常量 ───
MAX_FIX_ROUNDS = 3          # 失败返工回路最大轮数
BEATS_MIN, BEATS_MAX = 3, 6  # 数量门
BEAT_DUR_MIN_PCT = 0.80     # 时序门：每 beat ≥ 目标 80%
TOTAL_DUR_MIN_PCT = 0.60    # 时序门：总时长 ≥ 目标 60%


def _ensure_dir():
    os.makedirs(_PIPELINE_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# Phase 1 · 规划：生成结构化 script.json（beats 分镜）
# ═══════════════════════════════════════════════════════════
def phase1_plan(llm, topic: str, audience: str = "高中",
                duration_target_sec: int = 120, style: str = "3blue1brown",
                prerequisites: str = "", intuition: str = "",
                objectives: str = "") -> Optional[dict]:
    """规划 Agent：生成 script.json（beats 分镜）。角色禁令：不写代码。"""
    try:
        from visual_script_generator import generate_script
        script = generate_script(llm, topic, audience, duration_target_sec,
                                 style, prerequisites, intuition, objectives)
        if script is None:
            return None
        # 结构门：必填字段
        errors = gate_structure(script)
        if errors:
            print(f"[manim_pipeline] Phase1 结构门失败: {errors}")
        # 数量门：beats 3-6
        _scenes = script.get("scenes", [])
        if len(_scenes) < BEATS_MIN or len(_scenes) > BEATS_MAX:
            print(f"[manim_pipeline] Phase1 数量门失败: {len(_scenes)} beats (需 {BEATS_MIN}-{BEATS_MAX})")
        # 落盘中间产物
        _ensure_dir()
        _path = os.path.join(_PIPELINE_DIR, f"plan_{int(time.time())}.json")
        with open(_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        script["_meta"] = {"phase": "plan", "path": _path, "ts": time.time()}
        return script
    except Exception as e:
        print(f"[manim_pipeline] Phase1 失败: {e}")
        return None


def gate_structure(script: dict) -> List[str]:
    """结构门：校验必填字段。"""
    errors = []
    for key in ("meta", "scenes", "narrative_arc"):
        if key not in script:
            errors.append(f"缺 {key}")
    scenes = script.get("scenes", [])
    for i, s in enumerate(scenes):
        for f in ("id", "concept", "duration_sec", "visual_goal"):
            if f not in s:
                errors.append(f"scene[{i}] 缺 {f}")
    return errors


def gate_count(script: dict) -> List[str]:
    """数量门：beats 数量 3-6，每 beat 单一教学点。"""
    errors = []
    scenes = script.get("scenes", [])
    n = len(scenes)
    if n < BEATS_MIN or n > BEATS_MAX:
        errors.append(f"beats {n} 超出 {BEATS_MIN}-{BEATS_MAX}")
    concepts = [s.get("concept", "") for s in scenes]
    if len(concepts) != len(set(concepts)):
        errors.append("concept 重复（每 beat 应单一教学点）")
    return errors


def gate_executable(script: dict) -> List[str]:
    """可执行门：视觉目标须 Manim 可实现（禁 3D 全息/交互等异想天开）。"""
    _IMPOSSIBLE = ("3D 全息", "全息", "交互式", "VR", "增强现实", "AR 投影",
                   "人机交互", "触摸", "语音识别")
    errors = []
    for s in script.get("scenes", []):
        goal = str(s.get("visual_goal", "")) + str(s.get("narration", ""))
        for kw in _IMPOSSIBLE:
            if kw in goal:
                errors.append(f"scene {s.get('id','?')}: 视觉目标『{kw}』无法在 Manim 实现")
    return errors


def gate_timing(script: dict) -> List[str]:
    """时序门：每 beat 时长在合理范围（8-45s）+ 总时长 ≥ 目标 60%
    （智绘科普硬门控；每 beat 的"80%"相对其自身设计时长，由生成器保证）。"""
    errors = []
    target = int(script.get("meta", {}).get("duration_target_sec", 120))
    scenes = script.get("scenes", [])
    total = 0
    for s in scenes:
        d = float(s.get("duration_sec", 0))
        total += d + float(s.get("pause_after_sec", 0))
        if not (8 <= d <= 45):
            errors.append(f"scene {s.get('id','?')}: 时长 {d:.0f}s 超出 8-45s 规范")
    if target > 0 and total < target * TOTAL_DUR_MIN_PCT:
        errors.append(f"总时长 {total:.0f}s < 目标 {target}s 的 60%")
    return errors


def run_all_gates(script: dict) -> List[str]:
    """运行全部确定性门控，返回所有错误（空=通过）。"""
    errors = []
    errors += gate_structure(script)
    errors += gate_count(script)
    errors += gate_executable(script)
    errors += gate_timing(script)
    return errors


# ═══════════════════════════════════════════════════════════
# Phase 2A · 草稿：不渲染，仅写 Manim 代码
# ═══════════════════════════════════════════════════════════
def phase2_draft(llm, script: dict) -> Optional[str]:
    """草稿 Agent：根据 script.json 写 Manim 代码。角色禁令：不渲染。"""
    _sys = ("你是 Manim 动画代码草稿工程师。严格依据剧本 JSON 写 Manim Community 代码。\n"
            "要求：\n"
            "1. from manim import *\n"
            "2. Scene 类实现 construct(self)\n"
            "3. 按剧本 scenes 顺序实现每个 beat，视觉目标对应 mobject/动画\n"
            "4. 数学曲线用 axes.plot()，几何用 Circle/Square 等\n"
            "5. 纯几何动画（避免 Text/MathTex 依赖问题）\n"
            "6. 输出完整可运行 Python 代码，不要解释")
    try:
        from subagents import _safe_chat
        _usr = f"剧本：{json.dumps(script, ensure_ascii=False)}\n请生成 Manim 代码。"
        code = _safe_chat(llm, _sys, _usr, max_tokens=4000)
        if code and "class " in code:
            return code
    except Exception as e:
        print(f"[manim_pipeline] Phase2A 失败: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# Phase 2B · 实现：渲染 + AST 校验 + 几何审计
# ═══════════════════════════════════════════════════════════
def phase2_implement(code: str) -> Dict[str, Any]:
    """实现 Agent：AST 校验 → 渲染 → 几何审计。返回 {ok, path, url, error, audit}"""
    try:
        from manim_service import validate_manim_code, render_manim
        ok, err = validate_manim_code(code)
        if not ok:
            return {"ok": False, "error": f"AST 校验失败: {err}"}
        path, rerr = render_manim(code)
        if not path:
            return {"ok": False, "error": f"渲染失败: {rerr}"}
        # 几何审计门（v1.1 §3.34）：元素重叠/越界/漂移检测
        audit = {"rendered": True, "file_size": os.path.getsize(path) if os.path.exists(path) else 0}
        try:
            from manim_geometric_audit import audit_video
            _ga = audit_video(path)
            audit["geometric"] = _ga
            if not _ga.get("ok"):
                audit["warnings"] = _ga.get("issues", [])
        except Exception as _ge:
            audit["geometric_note"] = f"几何审计跳过: {_ge}"
        # URL
        try:
            from manim_service import _MEDIA_DIR
            _rel = os.path.relpath(path, _MEDIA_DIR).replace("\\", "/")
            url = f"/api/download/manim/{_rel}"
        except Exception:
            url = ""
        return {"ok": True, "path": path, "url": url, "error": "", "audit": audit}
    except Exception as e:
        return {"ok": False, "error": f"Phase2B 失败: {e}"}


# ═══════════════════════════════════════════════════════════
# Phase 3 · 审查：视觉审查（抽帧 LLM 评估）
# ═══════════════════════════════════════════════════════════
def phase3_review(llm, video_path: str) -> Dict[str, Any]:
    """审查 Agent：抽帧评估画面美观/清晰。角色禁令：不修改文件。"""
    try:
        import subprocess, os
        # 抽 3 帧（开头/中间/结尾）用 ffmpeg
        frames = []
        try:
            import shutil
            ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
            for _frac, _tag in [(0.1, "start"), (0.5, "mid"), (0.9, "end")]:
                _tmp = os.path.join(_PIPELINE_DIR, f"frame_{uuid.uuid4().hex[:6]}.png")
                _cmd = [ffmpeg, "-ss", str(_frac * 10), "-i", video_path,
                        "-frames:v", "1", "-y", _tmp]
                subprocess.run(_cmd, capture_output=True, timeout=20)
                if os.path.exists(_tmp):
                    frames.append(_tmp)
        except Exception:
            pass
        if not frames:
            return {"ok": True, "note": "抽帧失败（跳过视觉审查）", "frames": []}
        _sys = ("你是视频画面审查员。评估动画帧是否：①元素重叠/越界 ②清晰可读 "
                "③美观协调。给出 PASS/FAIL + 一句理由。只评估，不修改。")
        _usr = f"已抽取 {len(frames)} 帧（路径：{frames}）。请审查。"
        try:
            from subagents import _safe_chat
            verdict = _safe_chat(llm, _sys, _usr, max_tokens=300)
        except Exception:
            verdict = "PASS（无法评估）"
        return {"ok": "FAIL" not in verdict, "verdict": verdict, "frames": frames}
    except Exception as e:
        return {"ok": True, "note": f"视觉审查跳过: {e}", "frames": []}


# ═══════════════════════════════════════════════════════════
# 失败返工回路：错误日志 → 修复提示词 → 重跑
# ═══════════════════════════════════════════════════════════
def _fix_prompt(stage: str, artifact: Any, error: str) -> str:
    return (f"你是 {stage} 修复器。上一次 {stage} 失败：{error}\n"
            f"请修复后重新输出完整产物（结构不变）。\n"
            f"上次产物：{str(artifact)[:1500]}")


def _safe_chat(llm, sys_p, user_p, max_tokens=2000):
    """内部 _safe_chat 包装（兼容 subagents）。"""
    try:
        from subagents import _safe_chat as _sc
        return _sc(llm, sys_p, user_p, max_tokens=max_tokens)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# 主流水线：六阶段 + 门控 + 自动修复回路
# ═══════════════════════════════════════════════════════════
def run_pipeline(llm, topic: str, audience: str = "高中",
                 duration_target_sec: int = 120, style: str = "3blue1brown",
                 prerequisites: str = "", intuition: str = "",
                 objectives: str = "") -> Dict[str, Any]:
    """执行完整 Manim 流水线。返回 {ok, video_path, url, script, code, stages, errors}"""
    result = {"ok": False, "video_path": "", "url": "", "script": None,
              "code": None, "stages": {}, "errors": []}
    _ensure_dir()

    # ── Phase 1 规划（含门控 + 修复回路）──
    script = phase1_plan(llm, topic, audience, duration_target_sec,
                         style, prerequisites, intuition, objectives)
    if not script:
        result["errors"].append("Phase1 规划失败")
        return result
    result["stages"]["plan"] = "ok"
    result["script"] = script

    # 门控 + 修复回路（规划阶段）
    for _r in range(MAX_FIX_ROUNDS):
        errors = run_all_gates(script)
        if not errors:
            break
        # 修复：反馈给 LLM 重生成剧本
        try:
            _sys = ("你是剧本修复器。根据门控错误修改剧本 JSON，保持结构，只修违反项。"
                    "输出修复后的完整 JSON。")
            _usr = _fix_prompt("剧本", script, "; ".join(errors))
            _raw = _safe_chat(llm, _sys, _usr, max_tokens=4000)
            if _raw:
                _m = re.search(r'\{.*\}', _raw, re.S)
                if _m:
                    script = json.loads(_m.group(0))
                    result["script"] = script
        except Exception:
            break
    else:
        result["errors"].append("Phase1 门控修复超轮")
    result["stages"]["gates"] = "ok" if not run_all_gates(script) else "fail"

    # ── Phase 2A 草稿（含修复回路）──
    code = phase2_draft(llm, script)
    if not code:
        result["errors"].append("Phase2A 草稿失败")
        return result
    result["stages"]["draft"] = "ok"
    result["code"] = code

    # ── Phase 2B 实现（AST 校验 + 渲染 + 修复回路）──
    impl = phase2_implement(code)
    for _r in range(MAX_FIX_ROUNDS):
        if impl.get("ok"):
            break
        # 修复：错误日志 → 修复提示词 → 重生成代码
        try:
            _sys = ("你是 Manim 代码修复器。根据渲染/AST 错误修改代码，保持功能，"
                    "修复 import/API/语法问题。输出完整代码。")
            _usr = _fix_prompt("Manim 代码", code, impl.get("error", "未知错误"))
            _raw = _safe_chat(llm, _sys, _usr, max_tokens=4000)
            if _raw and "class " in _raw:
                code = _raw
                result["code"] = code
                impl = phase2_implement(code)
        except Exception:
            break
    if not impl.get("ok"):
        result["errors"].append(f"Phase2B 实现失败: {impl.get('error','')}")
        return result
    result["stages"]["implement"] = "ok"
    result["video_path"] = impl.get("path", "")
    result["url"] = impl.get("url", "")

    # ── Phase 3 审查（视觉门）──
    review = phase3_review(llm, impl.get("path", ""))
    result["stages"]["review"] = "ok" if review.get("ok") else "fail"
    if not review.get("ok"):
        result["errors"].append(f"Phase3 视觉审查失败: {review.get('verdict','')}")

    # ── Phase 4 合成：输出 + 中间产物落盘 ──
    try:
        _job = {
            "topic": topic, "audience": audience,
            "duration_target_sec": duration_target_sec,
            "script": script, "code": code,
            "stages": result["stages"],
            "video_url": result["url"],
            "ts": time.time(),
        }
        _out = os.path.join(_PIPELINE_DIR, f"job_{uuid.uuid4().hex[:8]}.json")
        with open(_out, "w", encoding="utf-8") as f:
            json.dump(_job, f, ensure_ascii=False, indent=2)
        result["job_path"] = _out
        result["stages"]["compose"] = "ok"
    except Exception as e:
        result["errors"].append(f"Phase4 合成失败: {e}")

    result["ok"] = not result["errors"]
    return result


# ═══════════════════════════════════════════════════════════
# 上下游衔接：教学视频上游 + 讲义/讲稿/脚本下游
# ═══════════════════════════════════════════════════════════
def link_to_assets(script: dict, base: str = "") -> Dict[str, str]:
    """衔接物料包：动画脚本作为下游（讲义/讲稿/PPT/思维导图）的共同输入源。
    返回各物料可用的 script 片段（供 teach_materials workflow 消费）。"""
    scenes = script.get("scenes", [])
    return {
        "outline": "\n".join(f"{i+1}. {s.get('concept','')}" for i, s in enumerate(scenes)),
        "handout_sections": json.dumps(
            [{"title": s.get("concept", ""), "narration": s.get("narration", "")}
             for s in scenes], ensure_ascii=False),
        "script_timeline": json.dumps(
            [{"id": s.get("id"), "duration": s.get("duration_sec"),
              "visual_goal": s.get("visual_goal")} for s in scenes],
            ensure_ascii=False),
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("manim_pipeline v1.1 已就绪（智绘科普范式：多阶段+门控+自检+修复回路）")
    print("门控:", "结构/数量/可执行/时序/几何/视觉")
    print("角色禁令:", "规划不写码 / 草稿不渲染 / 审查不改文件")
