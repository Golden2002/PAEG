# -*- coding: utf-8 -*-
"""RALPH 循环器（v0.69+ T5）：主循环——pull→execute→evaluate→decide→persist→guard→next。"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .contracts import ImprovementTask, LoopResult, RoundOutput, Verdict
from .completion_evaluator import CompletionEvaluator
from .termination_guard import TerminationGuard


class LoopController:
    """RALPH 主循环器（任务执行循环，非周度调度）。"""

    def __init__(self, executor: Optional[Callable] = None,
                 evaluator: Optional[CompletionEvaluator] = None,
                 guard: Optional[TerminationGuard] = None,
                 logger: Optional[Callable] = None):
        """executor: Callable(task, prev_round) -> RoundOutput（执行本轮改进）"""
        self.executor = executor or self._default_executor
        self.evaluator = evaluator or CompletionEvaluator()
        self.guard = guard or TerminationGuard()
        self._logger = logger or print
        self._lock = threading.RLock()
        self._running: Dict[str, bool] = {}
        base = os.path.dirname(os.path.abspath(__file__))
        self.state_dir = os.path.join(base, "..", "evolve_data", "ralph_state")
        self.log_path = os.path.join(base, "..", "evolve_data", "ralph_log.jsonl")
        os.makedirs(self.state_dir, exist_ok=True)

    def _default_executor(self, task: ImprovementTask, prev: Optional[RoundOutput]) -> RoundOutput:
        """默认执行器：调用 SelfUpdateAgent 生成改进建议（可被业务注入覆盖）。"""
        _summary = ""
        try:
            from self_update_agent import SelfUpdateAgent  # type: ignore
            _agent = SelfUpdateAgent()
            _r = _agent.run(task.goal, extra_context=task.context)
            _summary = str(_r)[:500]
        except Exception as e:
            _summary = f"[ralph] 默认执行器不可用({str(e)[:80]})——任务目标: {task.goal[:100]}"
        return RoundOutput(round_idx=0, summary=_summary,
                           snapshot={"content": _summary, "entry_type": "insight", "subject": ""})

    def run(self, task_id: str, max_rounds: Optional[int] = None) -> LoopResult:
        """运行一个任务直到 DONE/ABORT/PAUSE。"""
        from .task_registry import get_task_registry
        _reg = get_task_registry()
        task = _reg.get(task_id)
        if task is None:
            return LoopResult(task_id=task_id, verdict=Verdict.ABORT, rounds=0,
                              reason="任务不存在")
        _max = max_rounds or task.max_rounds
        _history: List[RoundOutput] = []
        _prev: Optional[RoundOutput] = None
        self._running[task_id] = True
        try:
            for rnd in range(1, _max + 1):
                if not self._running.get(task_id, True):
                    return LoopResult(task_id=task_id, verdict=Verdict.ABORT, rounds=rnd,
                                      reason="用户中断", summary=self._history_summary(_history))
                # 1. 执行本轮
                _out = self.executor(task, _prev)
                _out.round_idx = rnd
                _history.append(_out)
                # 2. 完成判定
                _v = self.evaluator.evaluate(task, _out)
                # 3. 持久化（状态快照）
                self._persist(task, rnd, _v, _out)
                self._log(task, rnd, _v, _out)
                # 4. 防呆
                if _v == Verdict.CONTINUE:
                    _g = self.guard.check(task, _history)
                    if _g in (Verdict.ABORT, Verdict.PAUSE):
                        _v = _g
                _prev = _out
                if _v == Verdict.DONE:
                    _reg.mark(task_id, "done", "DONE")
                    return LoopResult(task_id=task_id, verdict=Verdict.DONE, rounds=rnd,
                                      reason="达标", summary=self._history_summary(_history))
                if _v == Verdict.ABORT:
                    _reg.mark(task_id, "aborted", "ABORT")
                    return LoopResult(task_id=task_id, verdict=Verdict.ABORT, rounds=rnd,
                                      reason="防呆/资源/上限触发", summary=self._history_summary(_history))
                if _v == Verdict.PAUSE:
                    _reg.mark(task_id, "paused", "PAUSE")
                    return LoopResult(task_id=task_id, verdict=Verdict.PAUSE, rounds=rnd,
                                      reason="需人类确认（高风险任务）", summary=self._history_summary(_history))
            # 轮次上限（防呆兜底）
            _reg.mark(task_id, "aborted", "ABORT")
            return LoopResult(task_id=task_id, verdict=Verdict.ABORT, rounds=_max,
                              reason="轮次上限", summary=self._history_summary(_history))
        finally:
            self._running[task_id] = False

    def abort(self, task_id: str):
        self._running[task_id] = False

    def _persist(self, task: ImprovementTask, rnd: int, v: Verdict, out: RoundOutput):
        try:
            _p = os.path.join(self.state_dir, f"{task.id}.round{rnd}.json")
            with open(_p, "w", encoding="utf-8") as f:
                json.dump({
                    "task_id": task.id, "round": rnd, "verdict": v.value,
                    "summary": out.summary, "scores": out.scores,
                    "ts": datetime.now().isoformat(),
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _log(self, task: ImprovementTask, rnd: int, v: Verdict, out: RoundOutput):
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": datetime.now().isoformat(), "task_id": task.id,
                    "round": rnd, "verdict": v.value,
                    "summary": out.summary[:300], "scores": out.scores,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

    @staticmethod
    def _history_summary(history: List[RoundOutput]) -> str:
        return " | ".join(f"R{h.round_idx}:{h.summary[:60]}" for h in history[:5])


_controller: Optional[LoopController] = None
_ctrl_lock = threading.Lock()


def get_loop_controller(executor: Optional[Callable] = None) -> LoopController:
    global _controller
    with _ctrl_lock:
        if _controller is None:
            _controller = LoopController(executor=executor)
        return _controller
