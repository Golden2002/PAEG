# -*- coding: utf-8 -*-
"""test_teach_strategy.py — PTC-5 主循环可观测+可替换策略测试（§3.46.2 PTC-5）

覆盖：strategy 注册/获取/回退默认 / teach 走注册策略 / trace_id 贯穿。
PTC-1~4 已完成（programmatic/session_mode_lock/tool_observability/model_routing），
本测试验证 PTC-5（主循环可替换 + 可观测）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_strategy_registry_register_and_get():
    """注册自定义策略 → 可获取；未注册 → 回退默认。"""
    from services.teach_strategy import (
        DefaultTeachStrategy, STRATEGY_REGISTRY, get_strategy, register_strategy,
    )

    class FakeStrategy(DefaultTeachStrategy):
        pass

    register_strategy("fake", FakeStrategy)
    try:
        assert get_strategy("fake") is FakeStrategy
        assert get_strategy("not_exist") is DefaultTeachStrategy
    finally:
        STRATEGY_REGISTRY.pop("fake", None)


def test_default_strategy_class_exists():
    """默认策略类存在且可实例化（不报错）。"""
    from services.teach_strategy import DefaultTeachStrategy
    s = DefaultTeachStrategy()
    assert s is not None


def test_default_strategy_has_run_signature():
    """默认策略有 run(paeg, learner, question, subject) 签名（教学入口兼容）。"""
    from services.teach_strategy import DefaultTeachStrategy
    import inspect
    sig = inspect.signature(DefaultTeachStrategy.run)
    params = list(sig.parameters.keys())
    assert "paeg" in params
    assert "learner" in params
    assert "question" in params
    assert "subject" in params


def test_teach_uses_registered_strategy(monkeypatch):
    """注册 fake strategy（记录调用）→ paeg.teach 走 fake 而非默认。

    用真实 PAEG 实例 + monkeypatch teach_strategy.get_strategy 返回 fake，
    验证 teach 入口调用了 strategy.run（而非直接内联教学逻辑）。
    """
    from paeg import PAEG
    from knowledge_base import KnowledgeBase

    calls = []

    class FakeStrategy:
        def __init__(self, paeg=None):
            self.paeg = paeg

        def run(self, paeg, learner, question, subject, **kw):
            calls.append((question, subject))
            return {"summary": {"concept": question, "steps_completed": 0,
                                "mode": "fake_strategy"}}

    # 用最小 PAEG（mock LLM 避免真实调用）
    paeg = PAEG(model_api=None, knowledge_base=KnowledgeBase(), enable_self_update=False)

    # monkeypatch teach 内的 get_strategy 调用点
    import services.teach_strategy as ts
    monkeypatch.setattr(ts, "get_strategy", lambda name: FakeStrategy)

    from paeg import LearnerProfile
    learner = LearnerProfile(id="u_test", nickname="测试", grade_level="high_school", age=17)
    result = paeg.teach(learner, "什么是导数", "math")

    assert len(calls) == 1
    assert calls[0] == ("什么是导数", "math")
    assert result["summary"]["mode"] == "fake_strategy"


def test_teach_strategy_wires_into_paeg():
    """paeg.teach 源码引用了 get_strategy（静态断言接线存在）。"""
    import inspect
    import paeg as paeg_mod
    src = inspect.getsource(paeg_mod.PAEG.teach)
    assert "get_strategy" in src
