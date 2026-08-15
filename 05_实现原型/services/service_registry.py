# -*- coding: utf-8 -*-
"""services/service_registry.py —— #30 Cordis 式 Service Registry（Harness 30 项 P1，§3.46.2，2026-08-16）

dsh Harness 借鉴（ctx.<key> Service，commit 47f9438）："一切皆 ctx"——
llm/sessions/agents/tools/subagents 等经统一服务注册表获取，可注册可替换。

设计（与 infra/runtime.py 衔接，低风险新增）：
- ServiceRegistry：统一服务注册表（register/get/has/list/override）
  - 工厂懒加载（注册 factory，get 时构造）——对齐 infra.runtime 懒加载单例
  - 未知服务 → None（容错）
  - 覆盖已注册服务（dsh 一切皆插件：可替换）
- DEFAULT_SERVICES：预注册核心服务（llm/sessions/paeg/conv_store/...）——
  懒加载关联 infra.runtime.get_*（与 server 模块级全局同引用）
- get_service_registry()：进程级默认注册表单例

与既有机制关系：
- infra/runtime.py：12+ 懒加载 getter（get_llm/get_paeg/...）——本模块统一包一层 ctx 语义
- 业务代码经 ctx.<key> 取依赖，不感知实现与切换
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional


class ServiceRegistry:
    """统一服务注册表（"一切皆 ctx"——dsh Cordis 语义）。

    用法：
        reg = ServiceRegistry()
        reg.register("my_svc", lambda: MyService())   # 注册工厂（懒加载）
        svc = reg.get("my_svc")                       # 获取实例
        reg.override("my_svc", lambda: NewService())  # 可替换
    """

    def __init__(self):
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._lock = threading.RLock()

    def register(self, name: str, factory: Callable[[], Any]) -> None:
        """注册服务工厂（懒加载——get 时构造）。"""
        with self._lock:
            self._factories[name] = factory

    def override(self, name: str, factory: Callable[[], Any]) -> None:
        """覆盖已注册服务（dsh 一切皆插件：服务可替换）。"""
        self.register(name, factory)

    def get(self, name: str) -> Optional[Any]:
        """获取服务实例（工厂懒加载）；未知 → None（容错）。"""
        with self._lock:
            factory = self._factories.get(name)
        if factory is None:
            return None
        try:
            return factory()
        except Exception as e:
            print(f"[service_registry] 服务 {name} 构造失败: {e}")
            return None

    def has(self, name: str) -> bool:
        """服务是否已注册。"""
        with self._lock:
            return name in self._factories

    def list(self) -> List[str]:
        """返回已注册服务名列表。"""
        with self._lock:
            return list(self._factories.keys())


# ─────────────────────────────────────
# 默认核心服务（懒加载关联 infra.runtime）
# ─────────────────────────────────────
DEFAULT_SERVICES: Dict[str, Callable[[], Any]] = {}


def _register_default_services() -> None:
    """预注册核心服务（幂等）——经 infra.runtime.get_*（与 server 同引用）。"""
    _runtime_fns = {
        "llm": "get_llm",
        "paeg": "get_paeg",
        "conv_store": "get_conv_store",
        "user_store": "get_user_store",
        "evolver": "get_evolver",
        "agent_engine": "get_agent_engine",
        "skill_registry": "get_skill_registry",
        "periodic_updater": "get_periodic_updater",
        "session_log": "get_session_log",
        "file_generator": "get_file_generator",
        "library": "get_library",
        "kb": "get_kb",
    }
    for _name, _fn in _runtime_fns.items():
        if _name in DEFAULT_SERVICES:
            continue
        DEFAULT_SERVICES[_name] = (lambda _f=_fn: _lazy_runtime(_f))


def _lazy_runtime(fn_name: str) -> Any:
    """懒加载 infra.runtime.get_*（import 期零副作用）。"""
    from infra.runtime import get_llm, get_paeg, get_conv_store, get_user_store
    from infra.runtime import get_evolver, get_agent_engine, get_skill_registry
    from infra.runtime import get_periodic_updater, get_session_log
    from infra.runtime import get_file_generator, get_library, get_kb
    _map = {
        "get_llm": get_llm, "get_paeg": get_paeg, "get_conv_store": get_conv_store,
        "get_user_store": get_user_store, "get_evolver": get_evolver,
        "get_agent_engine": get_agent_engine, "get_skill_registry": get_skill_registry,
        "get_periodic_updater": get_periodic_updater, "get_session_log": get_session_log,
        "get_file_generator": get_file_generator, "get_library": get_library,
        "get_kb": get_kb,
    }
    fn = _map.get(fn_name)
    return fn() if fn is not None else None


# #30 ⭐ 模块加载即注册默认服务
_register_default_services()

# 进程级默认注册表单例
_DEFAULT_REGISTRY: Optional[ServiceRegistry] = None
_DEFAULT_LOCK = threading.Lock()


def get_service_registry() -> ServiceRegistry:
    """获取进程级默认服务注册表（懒初始化，含默认核心服务）。"""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        with _DEFAULT_LOCK:
            if _DEFAULT_REGISTRY is None:
                _reg = ServiceRegistry()
                for _name, _factory in DEFAULT_SERVICES.items():
                    _reg.register(_name, _factory)
                _DEFAULT_REGISTRY = _reg
    return _DEFAULT_REGISTRY


__all__ = [
    "ServiceRegistry", "DEFAULT_SERVICES", "get_service_registry",
]
