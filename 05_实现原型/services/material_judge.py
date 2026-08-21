# -*- coding: utf-8 -*-
"""services/material_judge.py —— §3.81 ⭐ 物料内容准确性评审门（P0-① + P0-②）

质量盲区 ①：现有 14 个检查器全是"结构/形式"，无"内容准确性"——
LLM 把导数讲成"变化率"不提极限定义，能 100% 通过所有检查器。
本模块补齐"血肉"：LLM-as-judge 对教案/讲义/PPT 大纲做内容评审。

质量盲区 ②：12 硬检中 5 条 LLM 评审项（人物绑定/文献引用/跨学科/真实数据/类比）
恒标 unverified——本模块把这些维度实际落地为可观测评分。

设计原则（参照 quality_gate._llm_score 模式）：
  1. 5 维评分：factuality / correctness / completeness / relevance / pedagogy（1-5）
  2. 5 条深检 yes/no：person_binding / literature / cross_subject / real_data / analogy
  3. 防御式：LLM 失败 → 默认分 + reason 标注（不阻塞主流程）
  4. 异步友好：judge_material() 可在线程池调用，结果落 jsonl
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

# ── 路径 ──
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JUDGE_LOG = os.path.join(_PROJ, "evolve_data", "material_judge.jsonl")

# ── 5 维评分维度（1-5）──
DIMS = {
    "factuality": "事实是否正确、有无幻觉/编造（最关键）",
    "correctness": "概念/公式/结论是否准确，有无逻辑错误",
    "completeness": "是否覆盖该主题的核心知识点（不遗漏关键定义/机制）",
    "relevance": "内容是否紧扣主题、无跑题/无关内容",
    "pedagogy": "教学价值：是否由浅入深、有例子/类比、适合目标学段",
}

# ── 5 条深检（对应 _score_12_hard_checks 的 unverified 项）──
DEEP_CHECKS = {
    "person_binding": "核心概念是否绑定至少 1 位相关人物（提出者/贡献者）？",
    "literature": "是否有文献/来源引用（教材/论文/权威资料）？",
    "cross_subject": "是否与相关学科建立联系（如数学→物理的应用）？",
    "real_data": "是否包含真实数据/实例（非凭空编造）？",
    "analogy": "是否有类比/隐喻帮助理解（生活化类比）？",
}


def judge_material(content: str, subject: str, grade: str = "",
                   material_type: str = "lesson_plan", llm=None) -> Dict[str, Any]:
    """LLM-as-judge 内容评审（5 维评分 + 5 条深检）。

    Args:
        content: 物料文本（教案/讲义/PPT 大纲等）
        subject: 学科（如 math/biology）
        grade: 学段（初中/高中/本科/考研）
        material_type: 物料类型（lesson_plan/handout/ppt_outline/...）
        llm: LLM 实例（None → 仅默认分）

    Returns:
        {"dims": {dim: score}, "deep_checks": {name: bool|None},
         "overall": float, "reason": str, "checked": bool}
    """
    result: Dict[str, Any] = {
        "dims": {}, "deep_checks": {}, "overall": 0.0,
        "reason": "", "checked": False,
    }
    _c = str(content or "")[:1500]
    if not _c.strip():
        result["reason"] = "空内容"
        return result

    if llm is None:
        result["reason"] = "无 LLM，跳过评审"
        return result

    try:
        from subagents import _safe_chat
        _dim_lines = "\n".join(f"{i+1}. {k}：{v}" for i, (k, v) in enumerate(DIMS.items()))
        _deep_lines = "\n".join(f"- {k}：{v}" for k, v in DEEP_CHECKS.items())
        system = (
            "你是资深学科教研评审员。对以下教学物料按维度评审。\n"
            f"学科：{subject} 学段：{grade} 物料类型：{material_type}\n\n"
            f"【5 维评分（每维 1-5 整数）】\n{_dim_lines}\n\n"
            f"【5 条深检（每项 true/false，无法判断则 null）】\n{_deep_lines}\n\n"
            '只输出 JSON：{"dims": {"factuality": N, "correctness": N, "completeness": N, '
            '"relevance": N, "pedagogy": N}, '
            '"deep_checks": {"person_binding": true|false|null, "literature": true|false|null, '
            '"cross_subject": true|false|null, "real_data": true|false|null, "analogy": true|false|null}}'
        )
        user = f"教学物料内容：\n{_c}"
        r = _safe_chat(llm, system, user, max_tokens=300)
        if not r:
            result["reason"] = "LLM 无返回"
            return result
        m = re.search(r"\{.*\}", r, re.S)
        if not m:
            result["reason"] = "LLM 返回非 JSON"
            return result
        parsed = json.loads(m.group(0))
        dims = {k: int(v) for k, v in (parsed.get("dims") or {}).items() if k in DIMS}
        deeps = {k: v for k, v in (parsed.get("deep_checks") or {}).items() if k in DEEP_CHECKS}
        if not dims:
            result["reason"] = "JSON 无 dims"
            return result
        result["dims"] = dims
        result["deep_checks"] = deeps
        result["overall"] = round(sum(dims.values()) / len(dims), 2)
        result["checked"] = True
        result["reason"] = "OK"
    except Exception as _je:
        result["reason"] = f"评审异常: {_je}"
    return result


def log_judge(run_id: str, topic: str, result: Dict[str, Any]) -> None:
    """评审结果落盘 evolve_data/material_judge.jsonl（可观测/聚合）。"""
    try:
        os.makedirs(os.path.dirname(_JUDGE_LOG), exist_ok=True)
        with open(_JUDGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": __import__("datetime").datetime.now().isoformat(),
                "run_id": run_id,
                "topic": topic,
                "result": result,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def aggregate_judges(limit: int = 200) -> Dict[str, Any]:
    """聚合评审日志（P1-② 反馈面板的数据源）。"""
    rows = []
    try:
        if os.path.isfile(_JUDGE_LOG):
            with open(_JUDGE_LOG, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        pass
    rows = rows[-limit:]
    if not rows:
        return {"total": 0, "avg_dims": {}, "avg_overall": 0.0, "deep_pass_rate": {}}

    # 聚合 dims
    dim_sums: Dict[str, float] = {}
    dim_cnt: Dict[str, int] = {}
    overalls = []
    deep_pass: Dict[str, int] = {}
    deep_cnt: Dict[str, int] = {}
    for row in rows:
        res = row.get("result") or {}
        dims = res.get("dims") or {}
        for k, v in dims.items():
            dim_sums[k] = dim_sums.get(k, 0) + float(v)
            dim_cnt[k] = dim_cnt.get(k, 0) + 1
        if res.get("overall"):
            overalls.append(float(res["overall"]))
        for k, v in (res.get("deep_checks") or {}).items():
            if v is True:
                deep_pass[k] = deep_pass.get(k, 0) + 1
            if v is not None:
                deep_cnt[k] = deep_cnt.get(k, 0) + 1
    return {
        "total": len(rows),
        "avg_dims": {k: round(dim_sums[k] / dim_cnt[k], 2) for k in dim_sums},
        "avg_overall": round(sum(overalls) / len(overalls), 2) if overalls else 0.0,
        "deep_pass_rate": {k: round(deep_pass.get(k, 0) / deep_cnt[k], 2) for k in deep_cnt},
    }


if __name__ == "__main__":
    import io as _io
    _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import sys
    # 自测：无 LLM 时降级
    r = judge_material("导数定义：f'(x0) = lim (f(x)-f(x0))/(x-x0)", "math", "高中", "lesson_plan", None)
    print("llm=None:", r["reason"], "| checked:", r["checked"])
