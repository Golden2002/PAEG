# -*- coding: utf-8 -*-
"""Round 12 续 ⭐ Sandbox 治理测试（test_round18_sandbox.py）。

§3.85 A9（Codex Harness 借鉴）：工具执行前过 sandbox 判定——写/执行按角色 preset
拒绝；教学默认只读；备课放行物料写；admin 全量。
守护：
1. teaching preset：写工具拒绝、读工具放行、MCP 放行
2. lesson_prep preset：物料写放行、执行仍拒绝
3. admin preset：全量放行
4. preset_for_mode 映射（teach→teaching / lesson_prep→lesson_prep）
5. tool_registry 接入（execute_tool 对写工具返回 sandbox 拒绝）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sandbox import check, preset_for_mode


class TestSandbox:
    def test_teaching_read_allowed(self):
        ok, reason = check("get_time", "teaching")
        assert ok, reason
        ok, _ = check("web_search", "teaching")
        assert ok

    def test_teaching_write_rejected(self):
        ok, reason = check("generate_ppt", "teaching")
        assert not ok, "teaching 不应允许写工具"
        assert "写操作" in reason

    def test_teaching_exec_rejected(self):
        ok, reason = check("execute_python", "teaching")
        assert not ok, "teaching 不应允许执行"
        assert "执行操作" in reason

    def test_lesson_prep_write_allowed(self):
        ok, reason = check("generate_handout", "lesson_prep")
        assert ok, reason

    def test_lesson_prep_exec_rejected(self):
        ok, _ = check("execute_python", "lesson_prep")
        assert not ok, "备课不应允许任意执行"

    def test_admin_all(self):
        ok, _ = check("generate_ppt", "admin")
        assert ok
        ok, _ = check("execute_shell", "admin")
        assert ok

    def test_mcp_allowed(self):
        ok, _ = check("mcp__filesystem__read", "teaching")
        assert ok

    def test_unknown_tool_default_allow(self):
        ok, _ = check("some_future_tool", "teaching")
        assert ok  # 未知工具由 registry 处理，sandbox 不误伤


class TestPresetForMode:
    def test_teach_modes(self):
        for m in ("teach", "chat", "answer", "method", "knowledge", "affection"):
            assert preset_for_mode(m) == "teaching", m

    def test_lesson_prep_modes(self):
        assert preset_for_mode("lesson_prep") == "lesson_prep"
        assert preset_for_mode("lesson_prep_modify") == "lesson_prep"

    def test_default(self):
        assert preset_for_mode("") == "teaching"


class TestRegistryIntegration:
    def test_execute_tool_sandbox_blocks_write(self):
        from tool_registry import execute_tool
        r = execute_tool("generate_ppt", {"topic": "x"})
        assert "sandbox" in str(r).lower(), f"应被 sandbox 拒绝: {r}"
