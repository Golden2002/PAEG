# -*- coding: utf-8 -*-
"""test_config_schema.py —— §3.42 W11 ⭐ 配置深化：schema 校验测试

需求（§3.42 W11）：config/*.json 加 schema 校验——热重载时校验，
无效配置拒绝且不改变运行时状态；校验失败发 config.invalid 事件。
"""
from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def validator():
    from services.config_schema import ConfigValidator
    return ConfigValidator()


def test_valid_hooks_config_passes(validator):
    """合法 hooks.json → 校验通过。"""
    valid = {
        "hooks": [
            {"id": "log1", "event": "tool.before", "module": "hooks_hub", "function": "log_hook"}
        ]
    }
    ok, errs = validator.validate("hooks.json", valid)
    assert ok is True, f"合法配置应通过: {errs}"


def test_invalid_hooks_config_rejected(validator):
    """非法 hooks.json（缺 event/module）→ 校验拒绝。"""
    invalid = {"hooks": [{"id": "bad", "function": "log_hook"}]}  # 缺 event+module
    ok, errs = validator.validate("hooks.json", invalid)
    assert ok is False, "非法配置应拒绝"
    assert errs, "应返回错误详情"


def test_invalid_json_rejected(validator):
    """非 JSON → 校验拒绝。"""
    ok, errs = validator.validate("agents.json", "not-a-dict")
    assert ok is False


def test_unknown_config_skipped(validator):
    """未知配置文件 → 跳过（不报错）。"""
    ok, errs = validator.validate("unknown_file.json", {"x": 1})
    assert ok is True


def test_agents_config_enabled_bool(validator):
    """agents.json enabled 字段必须布尔。"""
    bad = {"agents": {"presenter": {"enabled": "yes"}}}  # 字符串非布尔
    ok, errs = validator.validate("agents.json", bad)
    assert ok is False, "enabled 应为布尔，字符串应拒绝"
