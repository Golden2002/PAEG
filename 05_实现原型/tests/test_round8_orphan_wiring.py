# -*- coding: utf-8 -*-
"""§3.79 Round 8 孤儿接线测试：condition_eval→hooks when + agent_scope→manifest 校验。

覆盖：
  condition_eval 接线（hooks_hub 支持 when 条件启停）：
    - when 表达式为真 → 钩子 enabled
    - when 表达式为假 → 钩子 disabled
    - 无 when → 保持原 enabled（ratchet）
  agent_scope 接线（subagent_manifest.validate_scopes）：
    - manifest 声明的 10 个 subagent 均有默认作用域
  hooks_hub 既有测试兼容（无 when 的钩子不受影响）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import hooks_hub
import services.subagent_manifest as sm


# ────────────────────────────────────────────
# condition_eval → hooks_hub when
# ────────────────────────────────────────────
def test_hook_when_true_enabled(tmp_path, monkeypatch):
    _cfg = tmp_path / "hooks.json"
    _cfg.write_text(json.dumps({"hooks": [
        {"id": "h_when_true", "event": "session.start", "module": "hooks_hub",
         "function": "log_hook", "when": "platform() == 'win' or platform() == 'linux'"},
    ]}), encoding="utf-8")
    hub = hooks_hub.HooksHub(config_path=str(_cfg))
    _h = hub.hooks[0]
    assert _h.enabled is True


def test_hook_when_false_disabled(tmp_path, monkeypatch):
    _cfg = tmp_path / "hooks.json"
    _cfg.write_text(json.dumps({"hooks": [
        {"id": "h_when_false", "event": "session.start", "module": "hooks_hub",
         "function": "log_hook", "when": "env('NO_SUCH_VAR_PAEG_TEST') == '1'"},
    ]}), encoding="utf-8")
    hub = hooks_hub.HooksHub(config_path=str(_cfg))
    assert hub.hooks[0].enabled is False


def test_hook_no_when_keeps_enabled(tmp_path):
    """无 when 的钩子保持原 enabled（ratchet）。"""
    _cfg = tmp_path / "hooks.json"
    _cfg.write_text(json.dumps({"hooks": [
        {"id": "h_plain", "event": "session.start", "module": "hooks_hub",
         "function": "log_hook", "enabled": False},
    ]}), encoding="utf-8")
    hub = hooks_hub.HooksHub(config_path=str(_cfg))
    assert hub.hooks[0].enabled is False


# ────────────────────────────────────────────
# agent_scope → subagent_manifest
# ────────────────────────────────────────────
def test_manifest_scopes_all_registered():
    """manifest 声明的 10 个 subagent 均应有默认作用域（孤儿 agent_scope 接线）。"""
    _missing = sm.validate_scopes()
    assert _missing == [], f"缺作用域: {_missing}"


def test_agent_scope_has_lesson_prep():
    from services.agent_scope import DEFAULT_AGENT_SCOPES
    assert "lesson_prep" in DEFAULT_AGENT_SCOPES
    assert "resource_librarian" in DEFAULT_AGENT_SCOPES


# ────────────────────────────────────────────
# 既有 hooks 测试兼容（默认配置无 when）
# ────────────────────────────────────────────
def test_hooks_existing_config_still_loads():
    """默认 config/hooks.json（无 when）加载正常。"""
    hub = hooks_hub.HooksHub()
    assert isinstance(hub.hooks, list)
