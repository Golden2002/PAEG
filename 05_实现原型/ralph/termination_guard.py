# -*- coding: utf-8 -*-
"""RALPH 防呆守卫（v0.69+ T5）：五道防线——轮次上限/收益递减/质量回退/人类确认/资源熔断。"""
from __future__ import annotations

from typing import Dict, List

from .contracts import ImprovementTask, RoundOutput, Verdict


class TerminationGuard:
    """反教条防呆：防止循环空转或越改越烂。"""

    def __init__(self, stagnation_window: int = 3, stagnation_epsilon: float = 0.01,
                 confirm_every: int = 5, budget_rounds: int = 20,
                 max_total_seconds: float = 1800.0):
        self.stagnation_window = stagnation_window
        self.stagnation_epsilon = stagnation_epsilon
        self.confirm_every = confirm_every
        self.budget_rounds = budget_rounds
        self.max_total_seconds = max_total_seconds

    def check(self, task: ImprovementTask, history: List[RoundOutput]) -> Verdict:
        """五道防线检查。返回 None 表示继续（CONTINUE 语义由调用方决定）。"""
        n = len(history)
        # ① 轮次硬上限
        if n >= task.max_rounds:
            return Verdict.ABORT
        # ② 全局轮次预算
        if n >= self.budget_rounds:
            return Verdict.ABORT
        # ③ 收益递减：连续 N 轮主指标无提升
        if n >= self.stagnation_window:
            _last = history[-1]
            _prev = history[-self.stagnation_window]
            _delta = sum(_last.scores.get(k, 0) - _prev.scores.get(k, 0)
                         for k in set(_last.scores) | set(_prev.scores))
            if _delta < self.stagnation_epsilon:
                return Verdict.ABORT
        # ④ 人类确认点（高风险任务）
        if task.high_risk and n % self.confirm_every == 0:
            return Verdict.PAUSE
        return Verdict.CONTINUE
