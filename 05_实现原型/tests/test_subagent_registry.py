# -*- coding: utf-8 -*-
"""test_subagent_registry.py —— §3.42 W3 ⭐ subagent provider registry 测试

借鉴 deepseek-harness subagent registry：声明式注册（config 驱动启用/禁用/替换），
不破坏现有调用（ratchet：10 个（含 §3.69 lesson_prep） subagent 类不动）。

测试覆盖：
- test_registry_lists_all_subagents：registry 列出 10 个（含 §3.69 lesson_prep） subagent（name）
- test_registry_get_by_name：get("presenter") 返回 Presenter 类实例
- test_registry_enable_disable：config 禁用某 subagent → get 返回 None
- test_registry_custom_provider：注册自定义 provider 替换内置
- test_registry_paeg_integration：PAEG 构造用 registry 获取（不破坏现有 teach）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

# 确保 05_实现原型 根目录在 sys.path（与 conftest.py 一致的导入约定）
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ────────────────────────────────────────────────────────────
# 10 个（含 §3.69 lesson_prep） subagent 类（import 自 subagents.py，ratchet：类本身不动）
# ────────────────────────────────────────────────────────────
from subagents import (
    Diagnostor, Planner, Presenter, Evaluator, Adapter,
    AnswerSolver, AffectionSupportor, Individuality, ResourceLibrarian,
)


# 任务约定的 10 个（含 §3.69 lesson_prep） subagent name（registry 默认注册的全部）
TEN_SUBAGENT_NAMES = (
    "diagnostor",
    "planner",
    "presenter",
    "evaluator",
    "adapter",
    "answer_solver",
    "affection_supportor",
    "individuality",
    "resource_librarian",
    "lesson_prep",
)


class _MockLLM:
    """Mock LLM：避免真实调用，name != 'mock' 让 _is_real_llm 判 True。"""
    name = "mock_llm"

    def messages_create(self, **kw):
        return {"content": [{"text": "演示回答"}]}

    def chat(self, **kw):
        return "演示回答"


# ────────────────────────────────────────────────────────────
# 1. registry 列出 10 个（含 §3.69 lesson_prep） subagent（name）
# ────────────────────────────────────────────────────────────

def test_registry_lists_all_subagents():
    """registry.list() 应返回全部 10 个（含 §3.69 lesson_prep） subagent 的 name。"""
    from infra.subagent_registry import Registry

    reg = Registry()
    names = set(reg.list())

    # 任务约定的 10 个（含 §3.69 lesson_prep）必须全在
    for n in TEN_SUBAGENT_NAMES:
        assert n in names, f"registry 缺少 {n}，实际有 {names}"

    # 必须恰好 10 个（含 §3.69 lesson_prep）（ratchet：不偷偷加新的）
    assert len(names) == 10, f"registry 应恰好 10 个 subagent，实际 {len(names)}: {names}"


# ────────────────────────────────────────────────────────────
# 2. get(name) 返回对应类的实例
# ────────────────────────────────────────────────────────────

def test_registry_get_by_name():
    """get('presenter') 返回 Presenter 类的实例。"""
    from infra.subagent_registry import Registry

    reg = Registry()
    llm = _MockLLM()

    # 5 个需要 (model, kb) 的 subagent
    p = reg.get("presenter", llm=llm, kb=None)
    assert isinstance(p, Presenter), f"presenter 应对应 Presenter 类，实际 {type(p).__name__}"

    d = reg.get("diagnostor", llm=llm, kb=None)
    assert isinstance(d, Diagnostor)

    pl = reg.get("planner", llm=llm, kb=None)
    assert isinstance(pl, Planner)

    ev = reg.get("evaluator", llm=llm, kb=None)
    assert isinstance(ev, Evaluator)

    ad = reg.get("adapter", llm=llm, kb=None)
    assert isinstance(ad, Adapter)

    # 3 个无参构造的 subagent（不需要传 llm/kb 也行）
    ans = reg.get("answer_solver", llm=None, kb=None)
    assert isinstance(ans, AnswerSolver), f"answer_solver 应返回 AnswerSolver，实际 {type(ans).__name__}"

    aff = reg.get("affection_supportor", llm=None, kb=None)
    assert isinstance(aff, AffectionSupportor)

    ind = reg.get("individuality", llm=None, kb=None)
    assert isinstance(ind, Individuality)

    # resource_librarian 用 keyword
    rl = reg.get("resource_librarian", llm=llm, kb=None)
    assert isinstance(rl, ResourceLibrarian)

    # 不存在的 name → None
    assert reg.get("non_existent_subagent", llm=llm, kb=None) is None


# ────────────────────────────────────────────────────────────
# 3. config 禁用 → get 返回 None
# ────────────────────────────────────────────────────────────

def test_registry_enable_disable():
    """config 禁用某 subagent → get 返回 None；运行时 disable/enable 同样生效。"""
    from infra.subagent_registry import Registry

    # 3a) 通过 config 禁用：affection_supportor.enabled = false
    cfg = {
        "agents": {
            "affection_supportor": {"enabled": False, "provider": "auto", "model": None},
        },
    }
    reg = Registry(agents_config=cfg)
    assert reg.get("affection_supportor", llm=_MockLLM(), kb=None) is None, \
        "config 禁用后 get 应返回 None"

    # 其他未禁用的仍能拿到（证明是细粒度 disable，不是全停）
    assert isinstance(reg.get("presenter", llm=_MockLLM(), kb=None), Presenter)

    # 3b) 运行时 disable/enable
    reg2 = Registry()
    assert reg2.get("presenter", llm=_MockLLM(), kb=None) is not None
    reg2.disable("presenter")
    assert reg2.get("presenter", llm=_MockLLM(), kb=None) is None
    reg2.enable("presenter")
    assert reg2.get("presenter", llm=_MockLLM(), kb=None) is not None


# ────────────────────────────────────────────────────────────
# 4. 自定义 provider 替换内置
# ────────────────────────────────────────────────────────────

def test_registry_custom_provider():
    """register 自定义类 → get 返回自定义实例，而非内置。"""
    from infra.subagent_registry import Registry

    class _CustomPresenter:
        """自定义 Presenter 实现（测试用——必须区别于内置）。"""
        def __init__(self, *args, **kwargs):
            self.custom_marker = "I_AM_CUSTOM"
            self.args_received = (args, kwargs)

        def run(self, *a, **kw):
            return {"content": "custom answer", "custom": True}

    reg = Registry()
    # 替换内置 presenter
    reg.register("presenter", _CustomPresenter, factory=lambda llm, kb, cfg: _CustomPresenter(llm, kb))
    inst = reg.get("presenter", llm=_MockLLM(), kb=None)
    assert isinstance(inst, _CustomPresenter), "应返回自定义类实例"
    assert inst.custom_marker == "I_AM_CUSTOM"

    # list() 仍然包含 presenter（不被替换出 registry）
    assert "presenter" in reg.list()

    # 其他 subagent 不受影响
    assert isinstance(reg.get("diagnostor", llm=_MockLLM(), kb=None), Diagnostor)


# ────────────────────────────────────────────────────────────
# 5. PAEG 集成：用 registry 获取 subagent，teach() 不破坏
# ────────────────────────────────────────────────────────────

def test_registry_paeg_integration():
    """PAEG 构造用 registry 获取 subagent；teach() 仍正常；8 个核心 subagent 非 None。"""
    from infra.subagent_registry import Registry, get_default_registry
    from paeg import PAEG
    from knowledge_base import KnowledgeBase
    from paeg import LearnerProfile

    # 5a) 默认 registry 与 PAEG 配合：现有 PAEG(...) 仍持有 8 个核心 subagent
    paeg = PAEG(_MockLLM(), KnowledgeBase(), enable_self_update=False, enable_refiner=False)
    for name, cls in [
        ("diagnostor", Diagnostor),
        ("planner", Planner),
        ("presenter", Presenter),
        ("evaluator", Evaluator),
        ("adapter", Adapter),
        ("answer_solver", AnswerSolver),
        ("affection_supportor", AffectionSupportor),
        ("individuality", Individuality),
        ("resource_librarian", ResourceLibrarian),
    ]:
        assert hasattr(paeg, name), f"PAEG 缺少 {name}"
        obj = getattr(paeg, name)
        assert obj is not None, f"PAEG.{name} 不应为 None"
        assert isinstance(obj, cls), f"PAEG.{name} 不是 {cls.__name__} 实例（{type(obj).__name__}）"

    # 5b) teach() 仍能正常运行（端到端不抛错）
    learner = LearnerProfile(
        id="u001", nickname="测试", grade_level="high_school", age=16,
        cognitive_style="visual",
    )
    out = paeg.teach(learner, "什么是熵？", "physics")
    assert out is not None
    assert out.get("session") is not None or out.get("summary", {}).get("mode") == "affection_bypass"

    # 5c) get_default_registry() 返回单例且包含 10 个（含 §3.69 lesson_prep） subagent
    default_reg = get_default_registry()
    assert default_reg is not None
    assert len(default_reg.list()) == 10

    # 5d) 用 config 禁用某个 subagent → PAEG 该属性为 None（兼容 getattr 默认值语义）
    from infra.subagent_registry import configure_global_registry
    custom_cfg = {
        "agents": {
            "affection_supportor": {"enabled": False},
        },
    }
    custom_reg = configure_global_registry(custom_cfg)
    paeg2 = PAEG(_MockLLM(), KnowledgeBase(), enable_self_update=False, enable_refiner=False)
    assert paeg2.affection_supportor is None, "禁用后 PAEG.affection_supportor 应为 None"
    assert paeg2.presenter is not None, "其他未禁用 subagent 不应受影响"

    # 清理：恢复默认 registry（避免污染后续测试）
    configure_global_registry(None)


# ────────────────────────────────────────────────────────────
# 入口（直接跑 pytest 也可）
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call([sys.executable, "-m", "pytest",
                              os.path.abspath(__file__), "-v",
                              "--tb=short"]))