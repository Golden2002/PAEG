# -*- coding: utf-8 -*-
"""§3.79 A3/D1/D2 第 4 轮测试（2026-08-20 目标模式 Round 4）。

覆盖：
  A3 subagent 声明化（config/agents.yaml + services/subagent_manifest）：
    - 声明 10 个 subagent，与 registry 一致（validate_against_registry 空差集）
    - get_manifest/agent_names；缺文件降级
  D1 token 埋点（llm 适配器 record_metric → slo_summary tokens）：
    - observability token 指标汇总进 slo total
  D2 灰度回滚基础（module_registry 门控 = kill switch）：
    - is_enabled/module_status 结构；deploy/灰度回滚规范.md 存在
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import services.slo_metrics as slo
import services.subagent_manifest as sm
from infra import subagent_registry


# ────────────────────────────────────────────
# A3 subagent 声明化
# ────────────────────────────────────────────
def test_manifest_loads_ten_agents():
    m = sm.get_manifest()
    assert isinstance(m.get("agents"), list)
    assert len(sm.agent_names(m)) == 10, f"声明应 10 个，实际 {len(sm.agent_names(m))}"


def test_manifest_matches_registry():
    """声明与注册层一致（ratchet：A3 只加描述层，不改调度）。"""
    errors = sm.validate_against_registry()
    assert errors == [], f"声明与注册不一致: {errors}"
    _declared = set(sm.agent_names())
    _registered = set(subagent_registry.get_default_registry().list())
    assert _declared == _registered


def test_manifest_required_fields():
    m = sm.get_manifest()
    for a in m["agents"]:
        for _f in ("id", "name", "role", "keywords"):
            assert _f in a, f"{a.get('id')} 缺字段 {_f}"


def test_manifest_missing_file_degrades(tmp_path, monkeypatch):
    """缺文件降级为空清单（不抛）。"""
    _r = sm._load_manifest_file(str(tmp_path / "no_such.yaml"))
    assert _r["agents"] == []


def test_validate_declaration_fields_ok():
    """A3 声明字段完整性校验：真实 manifest 全部通过（id/name/role/keywords）。"""
    bad = sm.validate_declaration_fields()
    assert bad == [], f"声明字段不完整: {bad}"


def test_validate_declaration_fields_detects_missing():
    """A3 校验能检出缺字段的声明（防声明退化）。"""
    fake = {"agents": [
        {"id": "ok", "name": "n", "role": "r", "keywords": ["k"]},
        {"id": "bad", "name": "n"},  # 缺 role/keywords
        {"id": "empty"},             # 仅 id
    ]}
    bad = sm.validate_declaration_fields(fake)
    assert any("bad" in b for b in bad), f"应检出 bad: {bad}"
    assert any("empty" in b for b in bad), f"应检出 empty: {bad}"


# ────────────────────────────────────────────
# D1 token 埋点 → SLO
# ────────────────────────────────────────────
def test_slo_tokens_from_observability():
    slo.reset_for_test()
    from observability import record_metric, _metrics
    _metrics.clear()
    record_metric("paeg.llm.tokens", 100.0)
    record_metric("paeg.llm.tokens", 250.0)
    s = slo.slo_summary()
    assert s["total"]["tokens"] == 350
    assert s["total"]["llm_calls"] == 2
    _metrics.clear()
    slo.reset_for_test()


# ────────────────────────────────────────────
# D2 灰度回滚基础（kill switch = module_registry 门控）
# ────────────────────────────────────────────
def test_module_registry_kill_switch_api(monkeypatch):
    """module_registry 门控即 kill switch（显式关闭生效；未知模块默认启用=opt-out）。"""
    import module_registry
    # 已知模块返回 bool；未知模块默认启用（opt-out 设计，除非 catalog 默认 false）
    assert isinstance(module_registry.is_enabled("teach"), bool)
    assert module_registry.is_enabled("no_such_module") is True  # opt-out：未显式关闭 = 启用
    # kill switch 语义：显式 false → 关闭
    monkeypatch.setattr(module_registry, "_load_config", lambda: {"teach": False})
    assert module_registry.is_enabled("teach") is False
    _st = module_registry.module_status()
    assert isinstance(_st, dict)
    # require_module 返回装饰器（无异常）
    _dec = module_registry.require_module("teach")
    assert callable(_dec)


def test_deploy_rollout_doc_exists():
    """灰度回滚规范文档存在（D2 规范定稿）。"""
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "..", "deploy", "灰度回滚规范.md")
    assert os.path.isfile(_p), "缺 deploy/灰度回滚规范.md"
