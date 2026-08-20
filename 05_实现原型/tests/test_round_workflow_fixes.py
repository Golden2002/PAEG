# -*- coding: utf-8 -*-
"""§3.79 物料工作流联通修复测试（planner 签名适配 + knowledge_map/keyword_doc 工具兜底）。

真实运行发现：teach_materials 工作流 outline 步 Planner.run 签名不匹配、
knowledge_map/keyword_doc 工具未注册——修复后全部联通（失败检测 False）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import workflows_hub
from workflows_hub import WorkflowsHub


class _Step:
    """最小 WorkflowStep 替身。"""

    def __init__(self, stype, agent="", tool="", config=None, skill=""):
        self.type = stype
        self.agent = agent
        self.tool = tool
        self.skill = skill
        self.config = config or {}


def test_planner_signature_adapted(monkeypatch):
    """outline 步：planner.run 以正确签名调用（diagnosis={} + concept=input）。"""
    _calls = {}

    class _FakePlanner:
        def run(self, **kw):
            _calls.update(kw)
            return {"content": "大纲"}

    class _FakePaeg:
        planner = _FakePlanner()

    import infra.runtime as _rt
    monkeypatch.setattr(_rt, "get_paeg", lambda: _FakePaeg)
    monkeypatch.setattr(_rt, "get_llm", lambda: None)
    hub = WorkflowsHub(dir_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "workflows"))
    _r = hub._run_subagent(_Step("subagent", agent="planner",
                                 config={"input": "函数单调性"}), {"topic": "函数单调性"}, {})
    assert "大纲" in str(_r)
    assert _calls.get("diagnosis") == {}
    assert _calls.get("concept") == "函数单调性"


def test_knowledge_map_tool_fallback(monkeypatch):
    """knowledge_map 工具：优先 handle_knowledge_map，失败回退 LLM。"""
    hub = WorkflowsHub(dir_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "workflows"))
    import infra.runtime as _rt
    monkeypatch.setattr(_rt, "get_llm", lambda: None)
    import knowledge_map as _km
    monkeypatch.setattr(_km, "handle_knowledge_map",
                        lambda *a, **k: {"content": "## 知识导图：函数单调性\n- 定义\n  - 递增"})
    _r = hub._workflow_knowledge_map({"topic": "函数单调性", "stage": "high"}, {})
    assert "知识导图" in _r

    # 路径 2：handle_knowledge_map 异常 → LLM 兜底
    monkeypatch.setattr(_km, "handle_knowledge_map", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))

    def _fake_safe_chat(llm, sys, usr, **k):
        return "- 函数单调性\n  - 定义"

    import subagents as _sa
    monkeypatch.setattr(_sa, "_safe_chat", _fake_safe_chat)
    _r2 = hub._workflow_knowledge_map({"topic": "函数单调性", "stage": "high"}, {})
    assert "函数单调性" in _r2


def test_keyword_doc_tool_fallback(monkeypatch):
    """keyword_doc 工具：LLM 生成讲义。"""
    hub = WorkflowsHub(dir_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "workflows"))

    def _fake_safe_chat(llm, sys, usr, **k):
        return ("# 讲义：函数单调性\n\n## 一、学习目标\n理解单调性。\n\n"
                "## 二、核心内容\n定义与机制。\n\n## 三、典型例题\n例题。\n\n"
                "## 四、巩固练习\n练习。\n\n## 五、小结\n小结。")

    import subagents as _sa
    monkeypatch.setattr(_sa, "_safe_chat", _fake_safe_chat)
    import infra.runtime as _rt
    monkeypatch.setattr(_rt, "get_llm", lambda: None)
    _r = hub._workflow_keyword_doc({"topic": "函数单调性", "stage": "high",
                                    "outline": "单调性定义/判定"}, {})
    assert "讲义" in _r
    assert len(_r) > 60


def test_workflow_list_contains_teach_materials():
    hub = WorkflowsHub()
    _ids = {w["id"] for w in hub.list().get("workflows", [])}
    assert "teach_materials" in _ids
