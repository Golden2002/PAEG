# -*- coding: utf-8 -*-
"""services/teach_strategy.py —— PTC-5 ⭐ 主循环可观测 + 可替换策略（§3.46.2 PTC-5，2026-08-16）

dsh Harness 借鉴（core/agent-loop 可替换策略，commit 47f9438）：
- TeachStrategy 抽象：paeg.teach 主循环可替换（默认 DefaultTeachStrategy 行为不变）
- STRATEGY_REGISTRY：注册/获取策略（未注册回退默认）
- PTC-5 收官：PTC-1~4 已完成（programmatic/session_mode_lock/tool_observability/model_routing），
  本模块补"主循环可替换 + 可观测"最后一块

设计（ratchet 铁律）：
- DefaultTeachStrategy.run 委托 paeg.teach 原有核心逻辑（行为字节级不变）
- paeg.teach 入口：strategy = get_strategy(config 或默认) → strategy.run(...)
- 观测复用既有机制：_subagent_run 事件发射（W7）+ tool_observability.record_call（PTC-3）
  + obs_trace.trace_id（W2）——本模块不重复造轮子
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("paeg")


class TeachStrategy:
    """教学主循环策略抽象基类。

    子类实现 run() 即可替换 PAEG 的教学主循环（诊断→计划→呈现→评估→调整→反思）。
    默认策略 = DefaultTeachStrategy（委托 paeg.teach 原逻辑，行为不变）。
    """

    def __init__(self, paeg: Any = None):
        self.paeg = paeg

    def run(self, paeg: Any, learner: Any, question: str, subject: str, **kwargs) -> Dict[str, Any]:
        """执行一次教学。返回 dict（含 summary 等，对齐 paeg.teach 返回契约）。

        Args:
            paeg: PAEG 主实例
            learner: LearnerProfile
            question: 学生提问
            subject: 学科
            **kwargs: 透传（subtopic 等）
        """
        raise NotImplementedError("TeachStrategy.run 必须由子类实现")


class DefaultTeachStrategy(TeachStrategy):
    """默认教学策略：委托 paeg.teach 原核心逻辑（ratchet：行为字节级不变）。

    PTC-5 只做"可替换"抽象，不改变默认教学行为——测试/部署零感知。
    """

    def run(self, paeg: Any, learner: Any, question: str, subject: str, **kwargs) -> Dict[str, Any]:
        return paeg.teach(learner, question, subject, **kwargs)


# ─────────────────────────────────────
# 策略注册表
# ─────────────────────────────────────
STRATEGY_REGISTRY: Dict[str, type] = {"default": DefaultTeachStrategy}


def register_strategy(name: str, strategy_cls: type) -> None:
    """注册自定义教学策略。

    Args:
        name: 策略名（config/agents.json 的 teach_strategy 字段引用）
        strategy_cls: TeachStrategy 子类
    """
    STRATEGY_REGISTRY[name] = strategy_cls
    logger.info("[teach_strategy] 注册策略: %s", name)


def get_strategy(name: Optional[str] = None) -> type:
    """获取策略类；未注册/为空 → 回退默认 DefaultTeachStrategy。

    Args:
        name: 策略名；None 或未注册 → 默认
    """
    if not name:
        return DefaultTeachStrategy
    return STRATEGY_REGISTRY.get(name, DefaultTeachStrategy)


def build_strategy(name: Optional[str] = None, paeg: Any = None) -> TeachStrategy:
    """构造策略实例（注入 paeg 引用）。

    Args:
        name: 策略名（config 驱动）；None → 默认
        paeg: PAEG 主实例（策略需要时用）
    """
    cls = get_strategy(name)
    try:
        return cls(paeg=paeg)
    except TypeError:
        # 兼容无需 paeg 的简单策略
        return cls()


__all__ = [
    "TeachStrategy", "DefaultTeachStrategy",
    "STRATEGY_REGISTRY", "register_strategy", "get_strategy", "build_strategy",
]
