# -*- coding: utf-8 -*-
"""v0.68+ ⭐ hooks_hub.py —— PAEG 钩子模块（独立成套配置接口体系 · 阶段 2 升级版）

用户需求：智能体有独立的成套接口配置 hooks（钩子）。本模块：
- config/hooks.json 声明钩子（event + module:function + priority + enabled + match）
- 动态 import 加载（改 json 即生效，无需改代码）
- 事件驱动：session.start/end、message.before/after、tool.before/after、llm.before/after

v0.68+ ⭐ 升级（借鉴 deepseek-harness Cordis 事件模型）：
- **waterfall + next() 链式**：每个 listener 收到 (ctx, next_fn)，调用 next_fn(ctx) 才让出；
  不调用 = 主动短路（"我否决"）
- **matcher 引擎**：match 字段（tool/path/subject/learner_id）支持 * / glob / 字面量，
  invalid pattern 永不匹配（不抛）
- **most-restrictive 合并**：verdict deny > ask > allow（never downgrade）；context 累积；
  continue_chain=False 触发 sticky（上游不能 unblock 下游否决）
- **legacy_adapter**：兼容旧签名 (ctx) -> dict 的钩子（自动检测参数数）
- **runHook 永不抛**：任何异常降级为透传（next_fn）

接入点：config_hub.execute_tool() 的 tool.before/after；会话生命周期由调用方插入。
"""
from __future__ import annotations

import fnmatch
import importlib
import inspect
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional


# 合法钩子事件（约束配置准确性）
VALID_EVENTS = {
    "session.start", "session.end",
    "message.before_user", "message.after_user",
    "message.before_assistant", "message.after_assistant",
    "tool.before", "tool.after",
    "llm.before", "llm.after",
}

# verdict 等级（most-restrictive）
VERDICT_RANK = {"allow": 0, "ask": 1, "deny": 2}


# ─── 模块级线程池（钩子超时隔离，复用） ───
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hook")


# ─── matcher 引擎（借鉴 deepseek-harness matcher.ts） ───

@lru_cache(maxsize=512)
def _compile_matcher(pattern: str) -> Callable[[Any], bool]:
    """编译匹配器：None/'*' → 恒 True；含 glob 字符 → fnmatch；否则字面量。
    invalid pattern → 恒 False（不抛，运行时安全）。"""
    if pattern is None or pattern == "*":
        return lambda v: True
    if any(c in pattern for c in "*?["):
        try:
            _r = re.compile(fnmatch.translate(pattern))
            return lambda v: bool(v) and _r.match(str(v)) is not None
        except re.error:
            return lambda v: False
    return lambda v: str(v) == pattern


def _matches(spec: Optional[dict], ctx: dict) -> bool:
    """match 字段 AND 匹配（任一不匹配 = 整体不匹配）。空 spec = 始终匹配。"""
    if not spec:
        return True
    for _k, _pat in spec.items():
        if not _compile_matcher(_pat)(ctx.get(_k, "")):
            return False
    return True


# ─── HookResult（合并契约） ───

@dataclass
class HookResult:
    """钩子返回值契约（用户钩子可返回 dict 或 HookResult）。"""
    verdict: str = "allow"        # allow | ask | deny
    context: dict = field(default_factory=dict)   # 累积字段（merge 到下一链 ctx）
    continue_chain: bool = True   # False = sticky 短路
    reason: str = ""

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "context": self.context,
                "continue_chain": self.continue_chain, "reason": self.reason}


def _merge(result: dict, ctx: dict) -> dict:
    """most-restrictive 合并：verdict deny>ask>allow（never downgrade）；
    context 浅 merge；continue_chain False → sticky。

    兼容两种输入格式：
    - HookResult 风格：{"verdict": ..., "context": {...}, "continue_chain": ...}
    - 已展开风格（adapter 返回）：{"__verdict": ..., "blocked": True, ...}
    """
    # 提取 verdict：优先已展开的 __verdict，其次 verdict 字段
    _new_v = result.get("verdict") or result.get("__verdict") or "allow"
    _ctx_merge = result.get("context") if isinstance(result.get("context"), dict) else {}
    out = {**ctx, **result.get("context", {})}
    # 若 result 已含 __verdict 展开（adapter 风格），不再重复合并
    if "__verdict" in result:
        out = {**ctx, **result}
    _cur_v = out.get("__verdict", "allow")
    if VERDICT_RANK.get(_new_v, 0) > VERDICT_RANK.get(_cur_v, 0):
        out["__verdict"] = _new_v
        out["__reason"] = result.get("reason", "") or result.get("__reason", "")
    if not result.get("continue_chain", True):
        out["__sticky_deny"] = True
    return out


def _legacy_adapter(old_fn: Callable) -> Callable:
    """兼容旧签名 (ctx) -> dict / (ctx) -> None 的钩子（自动适配为 (ctx, next)）。"""
    try:
        _params = len(inspect.signature(old_fn).parameters)
    except (TypeError, ValueError):
        _params = 1

    def _adapted(ctx: dict, next_fn: Callable[[dict], dict]) -> dict:
        if _params >= 2:
            _r = old_fn(ctx, next_fn)
        else:
            _r = old_fn(ctx)  # 旧式：可能返回 None / ctx / dict
            # 旧式不主动调用 next——若返回了新的 ctx 视为"处理并让出"，
            # 但无法区分"短路"与"让出"；约定：旧式返回 dict 即让出（透传）
        if _r is None:
            return next_fn(ctx)
        if isinstance(_r, dict):
            # 若包含 verdict/context 结构 → 作为结果合并
            if "verdict" in _r or "context" in _r:
                return _merge(_r, ctx)
            # 否则视为"替换 ctx"并让出
            return next_fn({**ctx, **_r})
        return next_fn(ctx)

    return _adapted


class Hook:
    """单个钩子：module:function + 优先级 + matcher + blocking。"""

    def __init__(self, hook_id: str, event: str, module: str, function: str,
                 priority: int = 100, enabled: bool = True, blocking: bool = False,
                 match: Optional[dict] = None, timeout: Optional[int] = None):
        self.id = hook_id
        self.event = event
        self.module = module
        self.function = function
        self.priority = priority
        self.enabled = enabled
        self.blocking = blocking       # 兼容：blocking=True → continue_chain 默认 False
        self.match = match or {}
        self.timeout = timeout
        self._fn: Optional[Callable] = None
        self._loaded = False

    def resolve(self) -> Optional[Callable]:
        """动态 import module:function；失败返回 None（不抛）。"""
        if not self._loaded:
            self._loaded = True
            try:
                _raw = getattr(importlib.import_module(self.module), self.function)
                self._fn = _legacy_adapter(_raw)  # 自动兼容新旧签名
            except Exception as e:
                print(f"[hooks_hub] 钩子 {self.id} 加载失败 ({self.module}.{self.function}): {e}")
                self._fn = None
        return self._fn


class HooksHub:
    """钩子注册中心：加载/重载/触发（waterfall + next() 链式）。"""

    def __init__(self, config_path: Optional[str] = None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.config_path = config_path or os.path.join(base, "config", "hooks.json")
        self.hooks: List[Hook] = []
        self._agent_state: Dict[str, dict] = {}   # per-learner 状态（P1）
        self._lock = threading.RLock()
        self.reload()

    def reload(self):
        """读 config/hooks.json → 重建钩子表。"""
        with self._lock:
            self.hooks = []
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    _cfg = json.load(f)
                for _h in (_cfg.get("hooks") if isinstance(_cfg, dict) else []) or []:
                    _event = str(_h.get("event") or "")
                    if _event not in VALID_EVENTS:
                        print(f"[hooks_hub] 跳过未知事件 {_event}（钩子 {_h.get('id')}）")
                        continue
                    _h2 = Hook(
                        hook_id=str(_h.get("id") or f"{_event}_{len(self.hooks)}"),
                        event=_event,
                        module=str(_h.get("module") or ""),
                        function=str(_h.get("function") or ""),
                        priority=int(_h.get("priority") or 100),
                        enabled=bool(_h.get("enabled", True)),
                        blocking=bool(_h.get("blocking", False)),
                        match=_h.get("match"),
                        timeout=_h.get("timeout"),
                    )
                    _h2.resolve()
                    self.hooks.append(_h2)
            except Exception as e:
                print(f"[hooks_hub] 加载失败: {e}")

    # ─── 触发（waterfall + next() 链式） ───
    def run_hook(self, event: str, ctx: dict) -> dict:
        """触发事件。返回合并后的 ctx（必含 __verdict/__sticky_deny 字段）。

        构造闭包链（逆序），每个 listener 调 next_fn(ctx) 才让出；
        不调 = 短路（blocking）。most-restrictive 合并结果。
        """
        ctx = {**ctx, "__verdict": "allow", "__sticky_deny": False}
        with self._lock:
            _listeners = [h for h in self.hooks
                          if h.enabled and h.event == event and _matches(h.match, ctx)]
        _listeners.sort(key=lambda h: h.priority)

        def _terminal(c: dict) -> dict:
            return c

        _chain = _terminal
        for _h in reversed(_listeners):
            _prev = _chain
            _chain = (lambda c, _h2=_h, _p=_prev: self._invoke(_h2, c, _p))

        return _chain(ctx)

    def _invoke(self, h: Hook, ctx: dict, next_fn: Callable[[dict], dict]) -> dict:
        """执行单个钩子；永不抛（异常降级为透传）。

        P1-7 超时机制：
        - timeout=None/0：直接同步调用（无线程开销）
        - timeout>0：submit 到模块级 ThreadPoolExecutor，future.result(timeout)
          超时则 print 警告 + 返回 next_fn(ctx)（让出，不阻断主流程）
        """
        if h._fn is None or ctx.get("__sticky_deny"):
            return next_fn(ctx)
        _t0 = time.time()
        # 无超时：同步直接调
        if not h.timeout or h.timeout <= 0:
            return self._run_hook_fn(h, ctx, next_fn, _t0)
        # 有超时：线程池隔离
        try:
            _future = _executor.submit(self._run_hook_fn, h, ctx, next_fn, _t0)
            _r = _future.result(timeout=h.timeout)
            return _r
        except FutureTimeoutError:
            print(f"[hooks_hub] 钩子 {h.id} 超时（>{h.timeout}s），已跳过")
            return next_fn(ctx)
        except Exception as e:
            print(f"[hooks_hub] 钩子 {h.id} 异常: {e}")
            return next_fn(ctx)

    @staticmethod
    def _run_hook_fn(h: Hook, ctx: dict, next_fn: Callable[[dict], dict], _t0: float) -> dict:
        """钩子实际执行体（被 _invoke 调用，线程安全）。"""
        try:
            _r = h._fn(ctx, next_fn)
            if _r is None:
                _r = HookResult().to_dict()
            elif not isinstance(_r, dict):
                _r = HookResult(verdict=str(_r)).to_dict()
            _out = _merge(_r, ctx)
            if h.blocking and _out.get("__verdict") in ("deny", "ask"):
                _out["__sticky_deny"] = True
            return _out
        except Exception as e:
            print(f"[hooks_hub] 钩子 {h.id} 异常: {e}")
            return next_fn(ctx)

    # ─── per-learner 状态（P1，隔离钩子内部状态） ───
    def agent_state(self, learner_id: str) -> dict:
        with self._lock:
            return self._agent_state.setdefault(str(learner_id), {
                "repeat_guard": {},
                "tool_calls": [],
            })

    # ─── 动态管理 ───
    def add_hook(self, hook_def: dict):
        _event = str(hook_def.get("event") or "")
        if _event not in VALID_EVENTS:
            raise ValueError(f"未知事件: {_event}")
        _h = Hook(
            hook_id=str(hook_def.get("id") or f"{_event}_{len(self.hooks)}"),
            event=_event,
            module=str(hook_def.get("module") or ""),
            function=str(hook_def.get("function") or ""),
            priority=int(hook_def.get("priority") or 100),
            enabled=bool(hook_def.get("enabled", True)),
            blocking=bool(hook_def.get("blocking", False)),
            match=hook_def.get("match"),
            timeout=hook_def.get("timeout"),
        )
        _h.resolve()
        with self._lock:
            self.hooks.append(_h)

    def remove_hook(self, hook_id: str):
        with self._lock:
            self.hooks = [h for h in self.hooks if h.id != hook_id]

    def list(self) -> dict:
        with self._lock:
            return {
                "hooks": [{"id": h.id, "event": h.event, "module": h.module,
                           "function": h.function, "priority": h.priority,
                           "enabled": h.enabled, "blocking": h.blocking,
                           "match": h.match, "loaded": h._fn is not None}
                          for h in self.hooks],
            }

    def stats(self) -> dict:
        with self._lock:
            return {"hooks": len(self.hooks),
                    "by_event": {ev: sum(1 for h in self.hooks if h.event == ev)
                                 for ev in VALID_EVENTS}}


# ─── 全局单例 ───
_hooks_hub = None
_hooks_lock = threading.Lock()


def get_hooks_hub() -> HooksHub:
    """全局 HooksHub 单例。"""
    global _hooks_hub
    with _hooks_lock:
        if _hooks_hub is None:
            _hooks_hub = HooksHub()
        return _hooks_hub


__all__ = ["HooksHub", "Hook", "HookResult", "get_hooks_hub", "VALID_EVENTS"]
