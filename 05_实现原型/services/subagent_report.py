# -*- coding: utf-8 -*-
"""services/subagent_report.py —— #22 Subagent Report/Continuable 协议（Harness 30 项 P1，§3.46.2，2026-08-16）

dsh Harness 借鉴（subagent-control/report，commit 47f9438）：
子代理完成任务后回报结果（report）；父代理可发消息继续驱动（continuable——多轮协作）。

设计（与 #1/#11/#21/#30 衔接成完整 subagent 体系）：
- make_report(agent, status, result)：构造子代理回报（含 ts 时间戳）
- make_instruction(to, instruction)：构造父发消息（continuable 语义）
- ReportRegistry：报告注册表（add_report/get_reports/list_all，线程安全）
  - add_report(agent, status, result)：存储一次回报
  - get_reports(agent)：按 agent 查询回报列表（未知 → [] 容错）
  - list_all()：按 agent 分组返回全部
- 与 #11 契约层（ServiceProvider.execute 返回 result）衔接：回报即 execute 结果

与既有机制关系：
- #1 services/subagent_loader.py：9 subagent 装扮层（persona/prompt 配置）
- #11 services/agent_trirole.py：服务契约层（Definition/Provider/Consumer）
- #21 infra/subagent_registry.py：provider 注册表（in-process/external-script/llm-call）
- #30 services/service_registry.py：统一服务注册表（ctx.<key>）
- 本模块：子代理回报 + 父发消息（多轮协作协议）
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────
# 消息构造
# ─────────────────────────────────────
def make_report(agent: str, status: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """构造子代理回报消息（report 契约）。

    Args:
        agent: subagent 名
        status: completed / failed
        result: 执行结果（失败时含 error 字段）

    Returns:
        {agent, status, result, ts}
    """
    return {
        "agent": agent,
        "status": status,
        "result": result or {},
        "ts": time.time(),
    }


def make_instruction(to: str, instruction: str) -> Dict[str, Any]:
    """构造父发消息（continuable 语义——父可继续驱动子代理多轮协作）。

    Args:
        to: 目标 subagent 名
        instruction: 继续执行的指令

    Returns:
        {to, instruction, ts}
    """
    return {
        "to": to,
        "instruction": instruction,
        "ts": time.time(),
    }


# ─────────────────────────────────────
# 报告注册表
# ─────────────────────────────────────
class ReportRegistry:
    """子代理报告注册表（线程安全）。

    存储各 subagent 的回报，供父代理查询/多轮协作。
    """

    def __init__(self, max_per_agent: int = 20):
        self._reports: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._max_per_agent = max_per_agent

    def add_report(self, agent: str, status: str, result: Dict[str, Any]) -> None:
        """存储一次子代理回报（保留最近 max_per_agent 条）。"""
        with self._lock:
            lst = self._reports.setdefault(agent, [])
            lst.append(make_report(agent, status, result))
            if len(lst) > self._max_per_agent:
                del lst[:-self._max_per_agent]

    def get_reports(self, agent: str) -> List[Dict[str, Any]]:
        """按 agent 查询回报列表；未知 → []（容错）。"""
        with self._lock:
            return list(self._reports.get(agent, []))

    def list_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """返回全部回报（按 agent 分组）。"""
        with self._lock:
            return {k: list(v) for k, v in self._reports.items()}

    def clear(self, agent: Optional[str] = None) -> None:
        """清空报告（agent 为空清全部）。"""
        with self._lock:
            if agent is None:
                self._reports.clear()
            else:
                self._reports.pop(agent, None)


# 进程级默认报告注册表单例
_DEFAULT_REGISTRY: Optional[ReportRegistry] = None
_DEFAULT_LOCK = threading.Lock()


def get_report_registry() -> ReportRegistry:
    """获取进程级默认报告注册表（懒初始化）。"""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        with _DEFAULT_LOCK:
            if _DEFAULT_REGISTRY is None:
                _DEFAULT_REGISTRY = ReportRegistry()
    return _DEFAULT_REGISTRY


__all__ = [
    "make_report", "make_instruction",
    "ReportRegistry", "get_report_registry",
]
