# -*- coding: utf-8 -*-
"""services/presentation_quality.py —— §3.79 ⭐ 教学输出质量信号（总需求 Q6 落地）

教学对话输出质量的可观测化：对每步 presentation 内容做确定性信号计算
（无 LLM、无延迟、可测试），写入 transcript（item_type="quality_signal"），
供 E1 指标管道与教学质量看板消费；前端可显示"质量徽章"。

维度（score 满分 1.0）：
  - 长度（0.4）：>= 80 字（完整讲解而非碎片）
  - 具体性（0.3）：含 例子/类比/举例 等具体化标记（对应 NEW-9 防幻觉 + 生活化示例要求）
  - 结构（0.3）：含结构标记（**加粗**标签/序号/首先其次最后/步骤/小结）
"""
from __future__ import annotations

import re
from typing import Any, Dict

_EXAMPLE_PAT = re.compile(r"例子|例如|比如|类比|举例|实例|案例|生活")
_STRUCT_PAT = re.compile(
    r"\*\*|^\s*[一二三四五六七八九十\d]+[、.．)）]|首先|其次|最后|步骤|小结|一、|二、|三、",
    re.M,
)


def signal_presentation(content: Any, step_type: str = "teach",
                        subject: str = "") -> Dict[str, Any]:
    """教学输出确定性质量信号。

    Returns: {length_ok, has_examples, has_structure, score, chars, step_type}
    """
    text = str(content or "").strip()
    _chars = len(text)
    _length_ok = _chars >= 80
    _has_example = bool(_EXAMPLE_PAT.search(text))
    _has_struct = bool(_STRUCT_PAT.search(text))
    _score = round(
        (0.4 if _length_ok else 0.0)
        + (0.3 if _has_example else 0.0)
        + (0.3 if _has_struct else 0.0),
        2,
    )
    return {
        "length_ok": _length_ok,
        "has_examples": _has_example,
        "has_structure": _has_struct,
        "score": _score,
        "chars": _chars,
        "step_type": str(step_type),
        "subject": str(subject),
    }


def aggregate_signals(signals: list) -> Dict[str, Any]:
    """一批教学信号的聚合（会话级质量摘要）。"""
    if not signals:
        return {"n": 0, "avg_score": None, "low_quality_steps": 0}
    _scores = [float(s.get("score") or 0) for s in signals]
    return {
        "n": len(signals),
        "avg_score": round(sum(_scores) / len(_scores), 3),
        "low_quality_steps": sum(1 for s in _scores if s < 0.5),
    }


__all__ = ["signal_presentation", "aggregate_signals"]
