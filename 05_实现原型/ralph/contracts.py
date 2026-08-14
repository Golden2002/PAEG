# -*- coding: utf-8 -*-
"""RALPH 循环协议（v0.69+ T5）：Verdict/任务/轮次结果/循环结果 数据契约。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Verdict(str, Enum):
    """RALPH 每轮判定（承诺协议）。"""
    DONE = "DONE"            # 任务完成（达标）
    CONTINUE = "CONTINUE"    # 未达标，继续下一轮
    ABORT = "ABORT"          # 防呆/用户终止
    PAUSE = "PAUSE"          # 需人类确认（高风险任务）

    def __str__(self) -> str:
        return self.value


@dataclass
class Criterion:
    """任务验收指标。"""
    metric: str               # 指标名（如 strategy_f1 / factuality）
    threshold: float          # 达标阈值
    current: float = 0.0      # 当前值（每轮更新）
    source: str = ""          # 指标来源说明

    def met(self) -> bool:
        return self.current >= self.threshold


@dataclass
class ImprovementTask:
    """改进任务（RALPH 循环的输入）。"""
    id: str
    source: str                              # weekly / feedback / qg_reject / manual
    goal: str                                # 任务目标描述
    acceptance_criteria: List[Criterion] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    max_rounds: int = 10
    high_risk: bool = False                  # 涉及删除知识/重写策略 → 需人类确认
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"                  # pending / running / done / aborted
    verdict: Optional[str] = None

    def all_criteria_met(self) -> bool:
        return bool(self.acceptance_criteria) and all(c.met() for c in self.acceptance_criteria)


@dataclass
class RoundOutput:
    """单轮执行产出。"""
    round_idx: int
    summary: str = ""                        # 本轮做了什么
    scores: Dict[str, float] = field(default_factory=dict)   # L1 指标分数
    snapshot: Dict[str, Any] = field(default_factory=dict)   # 状态快照（可回滚）
    notes: List[str] = field(default_factory=list)


@dataclass
class LoopResult:
    """循环最终结果。"""
    task_id: str
    verdict: Verdict
    rounds: int
    reason: str = ""
    summary: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def promise(self) -> str:
        """承诺协议：<promise>DONE/CONTINUE/ABORT</promise>"""
        return f"<promise>{self.verdict.value}</promise>"
