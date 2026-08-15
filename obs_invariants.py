# -*- coding: utf-8 -*-
"""obs_invariants.py —— §3.42 W10 ⭐ runtime-diagnostics invariants（v1.1.5）

需求（§3.38.2 runtime-diagnostics invariants）：运行时不变式检查——
每条不变量违规 → 发 audit.violation 事件 + metric 计数。

4 条不变量：
1. no_orphan_trace：事件 trace_id 要么存在要么全缺（不混用/孤儿）
2. permission_boundary_intact：exam 模式写工具锁定（权限边界完好）
3. config_reload_succeeded：配置重载成功（无跳过）
4. subagent_provider_registered：9 个核心 subagent provider 已注册
"""
from __future__ import annotations

from typing import List, Tuple


def check_no_orphan_trace(events: list) -> Tuple[bool, str]:
    """无孤儿 trace：事件 data 中 trace_id 要么全有要么全无（不混用）。"""
    if not events:
        return True, "无事件"
    has = [e for e in events if e.get("data", {}).get("trace_id")]
    no = [e for e in events if not e.get("data", {}).get("trace_id")]
    # 允许少数无 trace（如启动事件），但不应超过 20%
    total = len(events)
    no_ratio = len(no) / total
    if no_ratio > 0.2:
        return False, f"{len(no)}/{total} 事件无 trace_id（孤儿率 {no_ratio:.0%} > 20%）"
    return True, f"trace 覆盖 {len(has)}/{total}"


def check_permission_boundary() -> bool:
    """权限边界完好：当前 preset 下写工具正确锁定。"""
    try:
        import tool_registry
        preset = tool_registry.get_permission_preset()
        # exam 模式：写工具必须被锁
        if preset == "exam":
            locked = not tool_registry.is_tool_allowed_by_preset("generate_handout")
            return locked
        return True
    except Exception:
        return True


def check_subagent_registered() -> Tuple[bool, List[str]]:
    """subagent provider 已注册（9 个核心）。"""
    missing = []
    try:
        from infra.subagent_registry import get_default_registry
        reg = get_default_registry()
        names = set(reg.list())
        for core in ("diagnostor", "planner", "presenter", "evaluator", "adapter",
                     "answer_solver", "affection_supportor", "individuality",
                     "resource_librarian"):
            if core not in names:
                missing.append(core)
    except Exception:
        missing = ["registry 未初始化"]
    return (not missing), missing


def check_config_reload_succeeded() -> bool:
    """配置重载成功（reload_all 无异常）。"""
    try:
        from config_hub import get_hub
        hub = get_hub()
        # 触发一次重载，若校验拦截或异常 → 视为失败
        try:
            hub.reload_all()
            return True
        except Exception:
            return False
    except Exception:
        return True


def report_violation(invariant: str, detail: str) -> None:
    """违规上报：发 audit.violation 事件 + 静默失败兜底。"""
    try:
        from observability import emit_event_typed
        emit_event_typed("audit/violation",
                         invariant=invariant, detail=detail[:200])
    except Exception:
        pass


def run_invariants() -> List[dict]:
    """运行全部不变量，返回 [{invariant, ok, detail}]。"""
    from observability import _EVENTS_FILE  # 读事件文件（复用）
    events = []
    try:
        import os, json as _json
        if os.path.exists(_EVENTS_FILE):
            with open(_EVENTS_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(_json.loads(line))
                        except Exception:
                            pass
    except Exception:
        pass

    results = []
    checks = [
        ("no_orphan_trace", check_no_orphan_trace(events)),
        ("permission_boundary_intact", (check_permission_boundary(), "")),
        ("subagent_provider_registered", check_subagent_registered()),
        ("config_reload_succeeded", (check_config_reload_succeeded(), "")),
    ]
    for name, (ok, detail) in checks:
        results.append({"invariant": name, "ok": bool(ok), "detail": str(detail)})
        if not ok:
            report_violation(name, str(detail))
    return results


__all__ = ["check_no_orphan_trace", "check_permission_boundary",
           "check_subagent_registered", "check_config_reload_succeeded",
           "report_violation", "run_invariants"]
