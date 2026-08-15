# -*- coding: utf-8 -*-
"""subagent_registry.py —— §3.42 W3 ⭐ PAEG subagent provider registry

借鉴 deepseek-harness subagent registry 设计：声明式注册、配置驱动启用/禁用、
运行时可替换 provider（注册自定义类）。本文件**只增加注册层**，不修改
``subagents.py`` 中 9 个 subagent 类本身（ratchet：行为不变）。

设计要点：
- 9 个内置 subagent：diagnostor / planner / presenter / evaluator / adapter /
  answer_solver / affection_supportor / individuality / resource_librarian
- ``self_update_agent`` 不在本 registry（PAEG 已有 ``_get_self_update_agent``
  懒加载机制——v0.42 P1 修复，避免教学路径上的僵尸实例）
- 每个 entry 含：name / cls / factory(llm, kb, cfg) → 实例 / enabled
- ``agents_config``（config/agents.json）含 ``enabled`` 字段时按配置 disable
- 进程级 default registry 单例（``get_default_registry()``）便于 PAEG 直接复用
- 自定义 provider 通过 ``register()`` 注入，运行时可替换内置实现
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

# ────────────────────────────────────────────────────────────
# 类型别名
# ────────────────────────────────────────────────────────────

Factory = Callable[[Any, Any, dict], Any]
"""Factory 签名：factory(llm, kb, agent_cfg) → subagent 实例。

- llm: 该 subagent 专用的 LLM（已按 agents.json provider/model 配置注入，
  调用方需自取，例如 ``self._llm_for(name)``）
- kb: KnowledgeBase 实例
- agent_cfg: 该 subagent 在 agents.json 中的配置 dict（可能为空）
"""


# ────────────────────────────────────────────────────────────
# Entry
# ────────────────────────────────────────────────────────────

class _SubagentEntry:
    """Registry 内部条目。外部 API 不暴露此类型。"""
    __slots__ = ("name", "cls", "factory", "enabled")

    def __init__(self, name: str, cls: type, factory: Factory, enabled: bool = True):
        self.name = name
        self.cls = cls
        self.factory = factory
        self.enabled = enabled

    def __repr__(self) -> str:
        return f"<SubagentEntry name={self.name!r} cls={self.cls.__name__} enabled={self.enabled}>"


# ────────────────────────────────────────────────────────────
# Registry
# ────────────────────────────────────────────────────────────

class Registry:
    """Subagent provider registry（可插拔）。

    用法：
        reg = Registry()                       # 默认 + agents.json
        reg.list()                              # ['diagnostor', ...]
        p = reg.get('presenter', llm=..., kb=...)  # Presenter 实例
        reg.disable('presenter')
        reg.register('presenter', MyPresenter)  # 自定义替换内置
    """

    # 任务约定的 9 个 subagent name（与 config/agents.json 的 keys 对齐）
    BUILTIN_NAMES: tuple = (
        "diagnostor",
        "planner",
        "presenter",
        "evaluator",
        "adapter",
        "answer_solver",
        "affection_supportor",
        "individuality",
        "resource_librarian",
    )

    def __init__(self, agents_config: Optional[dict] = None):
        """初始化 registry：注册 9 个内置 + 应用 config/agents.json 的 enabled 状态。

        Args:
            agents_config: config/agents.json 合并后内容；None 则视为空（全部 enabled）
        """
        self._entries: Dict[str, _SubagentEntry] = {}
        self._config: dict = agents_config or {}
        self._lock = threading.Lock()  # 多线程下 register/enable 原子性
        self._register_builtins()
        self._apply_config()

    # ───────── 公共 API ─────────

    def list(self) -> List[str]:
        """列出全部已注册的 subagent name（顺序按 BUILTIN_NAMES，自定义追加在末尾）。"""
        return list(self._entries.keys())

    def get(self, name: str, llm: Any = None, kb: Any = None) -> Optional[Any]:
        """按 name 获取 subagent 实例。禁用 / 不存在 → None。

        Args:
            name: subagent name
            llm: 该 subagent 专用的 LLM（部分 subagent 需要，部分不需要）
            kb: KnowledgeBase 实例

        Returns:
            subagent 实例；disabled / 不存在 / 构造失败 → None
        """
        entry = self._entries.get(name)
        if entry is None or not entry.enabled:
            return None
        agent_cfg = (self._config.get("agents") or {}).get(name) or {}
        try:
            return entry.factory(llm, kb, agent_cfg)
        except Exception as e:
            # ratchet：构造失败时返回 None，不破坏 PAEG 整体初始化
            # （测试可见，运行时调用方应处理 None；现有 paeg.py 用 getattr(..., None) 兼容）
            print(f"[subagent_registry] get({name!r}) 失败: {e}")
            return None

    def register(self, name: str, cls: type, factory: Optional[Factory] = None) -> None:
        """注册/替换一个 provider（自定义 subagent 类）。

        Args:
            name: subagent name（与 BUILTIN_NAMES 重名时替换内置）
            cls: subagent 类（用于类型断言 + 默认 factory）
            factory: 自定义构造逻辑；None 时默认 ``factory(llm, kb, _) = cls(llm, kb)``
        """
        if factory is None:
            # 默认 factory：把 llm, kb 作为位置参数传给 cls(llm, kb)
            def _default_factory(llm, kb, _cfg, _cls=cls):
                return _cls(llm, kb)
            factory = _default_factory
        with self._lock:
            self._entries[name] = _SubagentEntry(name, cls, factory, enabled=True)

    def enable(self, name: str) -> bool:
        """启用某 subagent。name 不存在 → False。"""
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                return False
            entry.enabled = True
            return True

    def disable(self, name: str) -> bool:
        """禁用某 subagent。get() 将返回 None。name 不存在 → False。"""
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                return False
            entry.enabled = False
            return True

    def reload(self, agents_config: Optional[dict]) -> None:
        """重载 config（重新应用 enabled 状态；自定义 provider 不丢失）。"""
        with self._lock:
            self._config = agents_config or {}
            self._apply_config()

    def is_enabled(self, name: str) -> bool:
        entry = self._entries.get(name)
        return bool(entry and entry.enabled)

    # ───────── 内部：内置注册 ─────────

    def _register_builtins(self) -> None:
        """注册 9 个内置 subagent（按 BUILTIN_NAMES 顺序；ratchet：类本身不动）。"""
        # 懒导入 subagents.py——避免 paeg.py → registry → subagents 循环
        from subagents import (
            Diagnostor, Planner, Presenter, Evaluator, Adapter,
            AnswerSolver, AffectionSupportor, Individuality, ResourceLibrarian,
        )

        # (name, cls, factory)
        # - 5 个用 (llm, kb) 位置参数
        # - 3 个无参构造（cls()）
        # - 1 个 ResourceLibrarian 用 keyword（model=, kb=）
        specs = [
            ("diagnostor", Diagnostor, lambda llm, kb, _c, _C=Diagnostor: _C(llm, kb)),
            ("planner", Planner, lambda llm, kb, _c, _C=Planner: _C(llm, kb)),
            ("presenter", Presenter, lambda llm, kb, _c, _C=Presenter: _C(llm, kb)),
            ("evaluator", Evaluator, lambda llm, kb, _c, _C=Evaluator: _C(llm, kb)),
            ("adapter", Adapter, lambda llm, kb, _c, _C=Adapter: _C(llm, kb)),
            ("answer_solver", AnswerSolver, lambda llm, kb, _c, _C=AnswerSolver: _C()),
            ("affection_supportor", AffectionSupportor,
             lambda llm, kb, _c, _C=AffectionSupportor: _C()),
            ("individuality", Individuality,
             lambda llm, kb, _c, _C=Individuality: _C()),
            # ResourceLibrarian.__init__(self, model=None, kb=None, web_search=None)
            # PAEG 原调用：ResourceLibrarian(model=self._llm_for("resource_librarian"),
            #                                 kb=knowledge_base)
            ("resource_librarian", ResourceLibrarian,
             lambda llm, kb, _c, _C=ResourceLibrarian: _C(model=llm, kb=kb)),
        ]

        for name, cls, factory in specs:
            self._entries[name] = _SubagentEntry(name, cls, factory, enabled=True)

    def _apply_config(self) -> None:
        """应用 config/agents.json 的 enabled 字段到每个 entry。"""
        agents_cfg = (self._config.get("agents") or {}) if isinstance(self._config, dict) else {}
        for name, entry in self._entries.items():
            agent_cfg = agents_cfg.get(name) or {}
            if isinstance(agent_cfg, dict):
                entry.enabled = bool(agent_cfg.get("enabled", True))


# ────────────────────────────────────────────────────────────
# 进程级默认 registry（单例）
# ────────────────────────────────────────────────────────────

_DEFAULT_REGISTRY: Optional[Registry] = None
_DEFAULT_LOCK = threading.Lock()


def get_default_registry() -> Registry:
    """获取进程级默认 registry（懒初始化）。"""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        with _DEFAULT_LOCK:
            if _DEFAULT_REGISTRY is None:
                _DEFAULT_REGISTRY = _build_registry_from_agents_json()
    return _DEFAULT_REGISTRY


def configure_global_registry(agents_config: Optional[dict]) -> Registry:
    """重置/替换进程级默认 registry。

    Args:
        agents_config: 配置 dict；None 时用 config_loader.load_agents_config() 重载

    Returns:
        新的默认 registry 实例
    """
    global _DEFAULT_REGISTRY
    with _DEFAULT_LOCK:
        if agents_config is None:
            try:
                from config_loader import load_agents_config
                agents_config = load_agents_config()
            except Exception as e:
                # config_loader 不可用 → 空配置（全部 enabled，行为等同旧 PAEG）
                print(f"[subagent_registry] load_agents_config 失败: {e}")
                agents_config = {}
        _DEFAULT_REGISTRY = Registry(agents_config=agents_config)
    return _DEFAULT_REGISTRY


def _build_registry_from_agents_json() -> Registry:
    """从 config/agents.json 构建默认 registry（静默失败 → 空配置）。"""
    cfg: dict = {}
    try:
        from config_loader import load_agents_config
        cfg = load_agents_config()
    except Exception as e:
        print(f"[subagent_registry] 默认 registry 配置加载失败（用空配置）: {e}")
    return Registry(agents_config=cfg)


# ────────────────────────────────────────────────────────────
# CLI 入口（手动调试用：python -m infra.subagent_registry）
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    reg = get_default_registry()
    print(f"=== Default Registry ===")
    print(f"names ({len(reg.list())}): {reg.list()}")
    print(f"enabled: {[(n, reg.is_enabled(n)) for n in reg.list()]}")

    # 调试：每个 subagent 的类
    print("\n=== Classes ===")
    for n in reg.list():
        entry = reg._entries[n]
        print(f"  {n:24s} → {entry.cls.__module__}.{entry.cls.__name__}")