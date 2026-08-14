# -*- coding: utf-8 -*-
"""RALPH 任务注册表（v0.69+ T5）：改进任务队列 + 持久化。"""
from __future__ import annotations

import json
import os
import threading
from typing import Dict, List, Optional

from .contracts import ImprovementTask


class TaskRegistry:
    """改进任务注册/队列（持久化 JSON，崩溃可恢复）。"""

    def __init__(self, path: Optional[str] = None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.path = path or os.path.join(base, "..", "evolve_data", "ralph_tasks.json")
        self._lock = threading.RLock()
        self.tasks: Dict[str, ImprovementTask] = {}
        self._load()

    def _load(self):
        try:
            if os.path.isfile(self.path):
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
                for tid, td in data.items():
                    try:
                        self.tasks[tid] = ImprovementTask(
                            id=tid,
                            source=td.get("source", "manual"),
                            goal=td.get("goal", ""),
                            acceptance_criteria=[
                                Criterion_metric(c.get("metric", ""), c.get("threshold", 0),
                                                 c.get("current", 0), c.get("source", ""))
                                for c in td.get("acceptance_criteria", [])
                            ],
                            context=td.get("context", {}),
                            max_rounds=int(td.get("max_rounds", 10)),
                            high_risk=bool(td.get("high_risk", False)),
                            status=td.get("status", "pending"),
                            verdict=td.get("verdict"),
                        )
                    except Exception:
                        continue
        except Exception:
            self.tasks = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            data = {}
            for tid, t in self.tasks.items():
                data[tid] = {
                    "source": t.source, "goal": t.goal,
                    "acceptance_criteria": [
                        {"metric": c.metric, "threshold": c.threshold,
                         "current": c.current, "source": c.source}
                        for c in t.acceptance_criteria
                    ],
                    "context": t.context, "max_rounds": t.max_rounds,
                    "high_risk": t.high_risk, "status": t.status, "verdict": t.verdict,
                }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ralph] 任务持久化失败: {e}")

    def submit(self, task: ImprovementTask) -> str:
        with self._lock:
            self.tasks[task.id] = task
            self._save()
            return task.id

    def pull_next(self) -> Optional[ImprovementTask]:
        """取下一 pending 任务（优先级：用户反馈 > 质量门禁拒绝 > 周度 > 手动）。"""
        with self._lock:
            _prio = {"feedback": 0, "qg_reject": 1, "weekly": 2, "manual": 3}
            pend = [t for t in self.tasks.values() if t.status == "pending"]
            if not pend:
                return None
            pend.sort(key=lambda t: (_prio.get(t.source, 9), t.created_at))
            t = pend[0]
            t.status = "running"
            self._save()
            return t

    def mark(self, task_id: str, status: str, verdict: Optional[str] = None):
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = status
                if verdict:
                    self.tasks[task_id].verdict = verdict
                self._save()

    def get(self, task_id: str) -> Optional[ImprovementTask]:
        return self.tasks.get(task_id)

    def list(self) -> List[ImprovementTask]:
        return list(self.tasks.values())


def Criterion_metric(metric: str, threshold: float, current: float = 0.0, source: str = ""):
    from .contracts import Criterion
    return Criterion(metric=metric, threshold=threshold, current=current, source=source)


_registry: Optional[TaskRegistry] = None
_reg_lock = threading.Lock()


def get_task_registry() -> TaskRegistry:
    global _registry
    with _reg_lock:
        if _registry is None:
            _registry = TaskRegistry()
        return _registry
