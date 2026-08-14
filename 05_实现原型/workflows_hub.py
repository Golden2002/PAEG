# -*- coding: utf-8 -*-
"""v0.68+ ⭐ workflows_hub.py —— PAEG 工作流模块（独立成套配置接口体系 · 阶段 3 MVP）

用户需求：智能体有独立的成套接口配置 workflows（工作流）。本模块：
- config/workflows/*.json 声明工作流（步骤 + 依赖）
- 步骤类型：subagent（调 9 个子代理）/ tool（调 PAEG 工具）/ skill（激活 skill）/ llm（直接 LLM）
- 接入 config_hub.execute_tool() 的 run_workflow__* 路由

v0.68+ ⭐ MVP（借鉴 deepseek-harness plain-JS workflow 思想，声明式 JSON 版）：
- 教学流水线声明化：诊断 → 计划 → 呈现 → 评估（可扩展）
- 步骤可依赖（DAG 拓扑排序执行）
- 每步可观测（结果记录，供重放）

后续扩展方向（对应 deepseek-harness 五原语）：
- agent(prompt, opts)   → subagent 步骤
- parallel(thunks)      → 并行步骤（future）
- pipeline(items, ...)  → 流水线步骤（future）
- phase(title)          → 阶段分组（future）
- log(msg)              → 步骤日志
"""
from __future__ import annotations

import importlib
import json
import os
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional


class WorkflowStep:
    """工作流单步。"""

    def __init__(self, step_id: str, step_type: str, agent: str = "",
                 tool: str = "", skill: str = "", config: Optional[dict] = None,
                 depends_on: Optional[List[str]] = None):
        self.id = step_id
        self.type = step_type          # subagent | tool | skill | llm
        self.agent = agent             # subagent 名（diagnostor/planner/presenter/...）
        self.tool = tool               # tool 名（run_agent_loop 等）
        self.skill = skill             # skill 名
        self.config = config or {}
        self.depends_on = depends_on or []


class Workflow:
    """一个工作流：DAG 步骤 + 拓扑执行。"""

    def __init__(self, wf_id: str, description: str = "", steps: Optional[List[dict]] = None):
        self.id = wf_id
        self.description = description
        self.steps: List[WorkflowStep] = []
        self._by_id: Dict[str, WorkflowStep] = {}
        for _s in steps or []:
            self.add_step(_s)

    def add_step(self, s: dict):
        _st = WorkflowStep(
            step_id=str(s.get("id") or f"s{len(self.steps)+1}"),
            step_type=str(s.get("type") or "subagent"),
            agent=str(s.get("agent") or ""),
            tool=str(s.get("tool") or ""),
            skill=str(s.get("skill") or ""),
            config=s.get("config") or {},
            depends_on=s.get("depends_on") or [],
        )
        self.steps.append(_st)
        self._by_id[_st.id] = _st

    def topo_order(self) -> List[WorkflowStep]:
        """拓扑排序（依赖在前）。返回执行顺序。"""
        _done: set = set()
        _order: List[WorkflowStep] = []
        _max_iter = len(self.steps) * len(self.steps) + 1

        def _visit(st: WorkflowStep, depth: int = 0):
            if st.id in _done or depth > _max_iter:
                return
            for _dep in st.depends_on:
                _d = self._by_id.get(_dep)
                if _d:
                    _visit(_d, depth + 1)
            if st.id not in _done:
                _done.add(st.id)
                _order.append(st)

        for _st in self.steps:
            _visit(_st)
        return _order

    def to_dict(self) -> dict:
        return {"id": self.id, "description": self.description,
                "steps": [{"id": s.id, "type": s.type, "agent": s.agent,
                           "tool": s.tool, "skill": s.skill, "depends_on": s.depends_on}
                          for s in self.steps]}


class WorkflowsHub:
    """工作流注册中心：扫描 config/workflows/*.json → DAG 执行。"""

    def __init__(self, dir_path: Optional[str] = None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.dir_path = dir_path or os.path.join(base, "config", "workflows")
        self.workflows: Dict[str, Workflow] = {}
        self._lock = threading.RLock()
        self.reload()

    def reload(self):
        """扫描 config/workflows/*.json → 加载工作流。"""
        with self._lock:
            self.workflows.clear()
            if not os.path.isdir(self.dir_path):
                return
            for _f in sorted(os.listdir(self.dir_path)):
                if not _f.endswith(".json"):
                    continue
                _p = os.path.join(self.dir_path, _f)
                try:
                    with open(_p, encoding="utf-8") as _fh:
                        _data = json.load(_fh)
                    _wf = Workflow(
                        wf_id=str(_data.get("id") or _f[:-5]),
                        description=str(_data.get("description") or ""),
                        steps=_data.get("steps") or [],
                    )
                    self.workflows[_wf.id] = _wf
                except Exception as e:
                    print(f"[workflows_hub] 加载 {_f} 失败: {e}")

    # ─── 工具定义（LLM 可见：run_workflow__<id>） ───
    def tool_defs(self) -> List[dict]:
        return [{
            "type": "function",
            "function": {
                "name": f"run_workflow__{wf.id}",
                "description": f"运行工作流「{wf.id}」：{wf.description}",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        } for wf in self.workflows.values()]

    # ─── 执行 ───
    def invoke(self, wf_id: str, args: dict = None) -> str:
        """执行工作流（DAG 拓扑序）。返回结果摘要。"""
        with self._lock:
            _wf = self.workflows.get(wf_id)
        if _wf is None:
            return f"工作流不存在: {wf_id}"
        _args = args or {}
        _order = _wf.topo_order()
        _results: Dict[str, Any] = {}
        _log = []
        for _st in _order:
            _r = self._run_step(_st, _args, _results)
            _results[_st.id] = _r
            _log.append(f"✓ {_st.id} ({_st.type}): {str(_r)[:60]}")
        return "\n".join(_log) + f"\n[workflow {wf_id} 完成]"

    def _run_step(self, st: WorkflowStep, args: dict, results: dict) -> str:
        """执行单步（subagent/tool/skill/llm）。"""
        try:
            if st.type == "subagent":
                return self._run_subagent(st, args, results)
            if st.type == "tool":
                return self._run_tool(st, args, results)
            if st.type == "skill":
                return self._run_skill(st, args, results)
            if st.type == "llm":
                return self._run_llm(st, args, results)
            return f"未知步骤类型: {st.type}"
        except Exception as e:
            return f"步骤 {st.id} 失败: {e}"

    def _run_subagent(self, st: WorkflowStep, args: dict, results: dict) -> str:
        """调 9 个子代理（diagnostor/planner/presenter/evaluator/adapter/...）。"""
        from infra.runtime import get_llm, get_paeg
        _llm = get_llm()
        _paeg = get_paeg()
        _agent_name = st.agent
        # v0.70+ §3.27：占位符替换（config 里 {step_id}/{param}）
        _cfg = self._resolve_placeholders(dict(st.config or {}), results, args)
        _sub = getattr(_paeg, _agent_name, None)
        if _sub is None:
            # 尝试 subagents 模块
            try:
                import subagents as _sa
                _sub = getattr(_sa, _agent_name, None)
            except Exception:
                _sub = None
        if _sub is None:
            return f"子代理不存在: {_agent_name}"
        # 调用子代理（presenter.run / diagnostor.run 等）
        _cfg = dict(st.config or {})
        _input = str(_cfg.get("input") or args.get("concept") or args.get("topic") or "")
        try:
            _r = _sub.run(_llm, _input, learner=args.get("learner"),
                          subject=args.get("subject") or "general")
            if isinstance(_r, dict):
                return str(_r.get("content") or _r.get("presentation") or json.dumps(_r, ensure_ascii=False)[:200])
            return str(_r)[:300]
        except TypeError:
            # 子代理签名不同：尝试通用调用
            try:
                _r = _sub.run(_llm, _input)
                return str(_r)[:300]
            except Exception as e:
                return f"子代理 {_agent_name} 调用失败: {e}"

    def _run_tool(self, st: WorkflowStep, args: dict, results: dict) -> str:
        from tool_registry import execute_tool
        _tool = st.tool
        _targs = self._resolve_placeholders(dict(st.config or {}), results, args)
        return execute_tool(_tool, _targs)

    # v0.70+ §3.27：统一占位符替换——{step_id} 从 results 取，{param} 从 args 取
    def _resolve_placeholders(self, cfg: dict, results: dict, args: dict = None) -> dict:
        import re as _re
        _args = args or {}
        _out = {}
        for _k, _v in cfg.items():
            if isinstance(_v, str):
                def _sub(m):
                    _key = m.group(1)
                    if _key in results:
                        _rv = results[_key]
                        return _rv if isinstance(_rv, str) else str(_rv)
                    return str(_args.get(_key, m.group(0)))
                _out[_k] = _re.sub(r"\{([a-zA-Z0-9_]+)\}", _sub, _v)
            elif isinstance(_v, dict):
                _out[_k] = self._resolve_placeholders(_v, results, _args)
            else:
                _out[_k] = _v
        return _out

    def _run_skill(self, st: WorkflowStep, args: dict, results: dict) -> str:
        from skill_registry import SkillRegistry
        _reg = SkillRegistry()
        return _reg.activate(st.skill)

    def _run_llm(self, st: WorkflowStep, args: dict, results: dict) -> str:
        from infra.runtime import get_llm
        from subagents import _safe_chat
        _llm = get_llm()
        _cfg = dict(st.config or {})
        _sys = str(_cfg.get("system") or "你是一位老师。")
        _user = str(_cfg.get("user") or args.get("concept") or "")
        return _safe_chat(_llm, _sys, _user, max_tokens=800) or "(空响应)"

    # ─── 管理 ───
    def list(self) -> dict:
        with self._lock:
            return {"workflows": [wf.to_dict() for wf in self.workflows.values()]}

    def stats(self) -> dict:
        with self._lock:
            return {"count": len(self.workflows),
                    "ids": sorted(self.workflows.keys())}


# ─── 全局单例 ───
_wf_hub = None
_wf_lock = threading.Lock()


def get_workflows_hub() -> WorkflowsHub:
    global _wf_hub
    with _wf_lock:
        if _wf_hub is None:
            _wf_hub = WorkflowsHub()
        return _wf_hub


__all__ = ["WorkflowsHub", "Workflow", "WorkflowStep", "get_workflows_hub"]
