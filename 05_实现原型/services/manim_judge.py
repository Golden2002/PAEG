# -*- coding: utf-8 -*-
"""services/manim_judge.py —— §3.81 P2-② ⭐ Manim 教学叙事复核

盲区：Manim 动画生成后无"是否清晰表达概念"的评审——渲染成功 ≠ 教学有效。
本模块：LLM 评审动画方案（代码 + 主题），判断叙事是否达标，供后续修复回路。

设计原则（与 material_judge 同构）：
  1. 4 维评分：clarity（动画是否清晰）/ pedagogy（是否助理解）/ correctness（数学正确）/ focus（是否聚焦主题）
  2. 防御式：LLM 失败 → checked=False（不阻塞动画主流程）
  3. 结果可落盘 evolve_data/manim_judge.jsonl（可观测）
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JUDGE_LOG = os.path.join(_PROJ, "evolve_data", "manim_judge.jsonl")

DIMS = {
    "clarity": "动画是否清晰表达了核心概念（视觉呈现清楚）",
    "pedagogy": "是否有教学价值（动画帮助理解而非炫技）",
    "correctness": "数学/内容是否正确（无错误符号/逻辑）",
    "focus": "是否聚焦主题（无无关内容）",
}


def judge_manim_narrative(topic: str, subject: str, code: str,
                          video_path: str, llm=None) -> Dict[str, Any]:
    """LLM 评审 Manim 动画教学叙事。

    Args:
        topic: 动画主题（如"导数"）
        subject: 学科
        code: Manim 代码（评审动画设计依据）
        video_path: 渲染产物路径
        llm: LLM 实例（None → 跳过）

    Returns:
        {"checked": bool, "dims": {...}, "overall": float,
         "verdict": "pass"|"review"|"fail", "reason": str}
    """
    result: Dict[str, Any] = {
        "checked": False, "dims": {}, "overall": 0.0,
        "verdict": "review", "reason": "",
    }
    _c = str(code or "")[:1200]
    if not _c.strip():
        result["reason"] = "空代码"
        return result
    if llm is None:
        result["reason"] = "无 LLM，跳过评审"
        return result

    try:
        from subagents import _safe_chat
        _dim_lines = "\n".join(f"{i+1}. {k}：{v}" for i, (k, v) in enumerate(DIMS.items()))
        system = (
            "你是数学动画评审员（3Blue1Brown 风格标准）。评审以下 Manim 动画方案。\n"
            f"主题：{topic} 学科：{subject}\n\n"
            f"【4 维评分（每维 1-5 整数）】\n{_dim_lines}\n\n"
            '只输出 JSON：{"dims": {"clarity": N, "pedagogy": N, "correctness": N, "focus": N}, '
            '"verdict": "pass"|"review"|"fail"}'
            "（verdict：pass=可直接用 / review=需小改 / fail=需重做）"
        )
        user = f"Manim 动画代码：\n{_c}"
        r = _safe_chat(llm, system, user, max_tokens=200)
        if not r:
            result["reason"] = "LLM 无返回"
            return result
        m = re.search(r"\{.*\}", r, re.S)
        if not m:
            result["reason"] = "LLM 返回非 JSON"
            return result
        parsed = json.loads(m.group(0))
        dims = {k: int(v) for k, v in (parsed.get("dims") or {}).items() if k in DIMS}
        if not dims:
            result["reason"] = "JSON 无 dims"
            return result
        result["dims"] = dims
        result["overall"] = round(sum(dims.values()) / len(dims), 2)
        result["verdict"] = parsed.get("verdict") if parsed.get("verdict") in (
            "pass", "review", "fail") else "review"
        result["checked"] = True
        result["reason"] = "OK"
        _log(topic, result)
    except Exception as _je:
        result["reason"] = f"评审异常: {_je}"
    return result


def _log(topic: str, result: Dict[str, Any]) -> None:
    """评审结果落盘（可观测/聚合）。"""
    try:
        import datetime
        os.makedirs(os.path.dirname(_JUDGE_LOG), exist_ok=True)
        with open(_JUDGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.datetime.now().isoformat(),
                "topic": topic,
                "result": result,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    import io as _io
    _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import sys
    r = judge_manim_narrative("导数", "math", "class M(Scene): pass", "/tmp/x.mp4", None)
    print("llm=None:", r["reason"], "| checked:", r["checked"])
