# -*- coding: utf-8 -*-
"""
PAEG RALPH 循环子系统（v0.69+ T5，Oracle 设计）

自我指涉开发循环：围绕一个"改进任务"做"执行→验证→承诺→续触发"的迭代，
直到任务完成（DONE）或触发防呆终止（ABORT）。

设计（Oracle 2026-08-14）：
- 循环机制：任务执行循环（非周度调度增强）——独立子系统，位于 periodic_self_update 之上
- 完成判定：三层（L0 QualityGate + L1 任务指标 + L2 改进证据）
- 终止条件：达标 ∨ 轮次上限 ∨ 防呆触发 ∨ 用户中断
- 反教条：五道防线（轮次硬上限/收益递减/质量回退/人类确认/资源熔断）
"""
from .contracts import Verdict, ImprovementTask, Criterion, RoundOutput, LoopResult
from .task_registry import TaskRegistry, get_task_registry
from .loop_controller import LoopController, get_loop_controller
from .termination_guard import TerminationGuard
from .completion_evaluator import CompletionEvaluator

__all__ = [
    "Verdict", "ImprovementTask", "Criterion", "RoundOutput", "LoopResult",
    "TaskRegistry", "get_task_registry",
    "LoopController", "get_loop_controller",
    "TerminationGuard", "CompletionEvaluator",
]
