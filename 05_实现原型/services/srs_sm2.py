# -*- coding: utf-8 -*-
"""services/srs_sm2.py —— C1 间隔重复 SRS（SM-2 算法，P2，§3.54）

借鉴来源：
source:  Anki SM-2 算法（SuperMemo-2 改良版）
adapted: 纯函数式实现（无状态存储，状态由调用方持 JSON 持久化）
since:   PAEG v0.73 §3.54 C1

SM-2 调度规则（Anki 标准）：
- q=0..5 质量评分（5=完全回忆，0=完全遗忘）
- q<3 → repetition 归零，interval 归 0
- q>=3 → repetition+1；repetition=1→1天；repetition=2→6天；之后 interval*EF
- EF' = EF + (0.1 - (5-q)*(0.08+(5-q)*0.02))，下限 1.3
"""
from __future__ import annotations

from typing import Any, Dict

MIN_EASINESS = 1.3


def sm2_review(state: Dict[str, Any], quality: int) -> Dict[str, Any]:
    """SM-2 单次复习调度。

    Args:
        state: {"interval": 天, "repetition": 连续正确次数, "easiness": EF}
        quality: 0-5 质量评分

    返回：更新后的 state（interval/repetition/easiness）
    """
    interval = int(state.get("interval", 0))
    repetition = int(state.get("repetition", 0))
    easiness = float(state.get("easiness", 2.5))
    q = int(quality)

    # EF 更新（Anki 公式）
    easiness = easiness + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if easiness < MIN_EASINESS:
        easiness = MIN_EASINESS

    if q < 3:
        # 答错 → 重置
        return {"interval": 0, "repetition": 0, "easiness": easiness}

    # 答对 → 间隔增长
    repetition += 1
    if repetition == 1:
        interval = 1
    elif repetition == 2:
        interval = 6
    else:
        interval = round(interval * easiness)

    return {"interval": interval, "repetition": repetition, "easiness": easiness}


__all__ = ["sm2_review", "MIN_EASINESS"]
