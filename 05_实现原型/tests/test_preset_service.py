# -*- coding: utf-8 -*-
"""test_preset_service.py — #8 PresetService 测试（Harness 30 项 P0，§3.46.2）

覆盖：PresetService 完整 API（mount/list/resolve/recompose/copy/remove），
基于 #7 teaching_presets 扩展——预设管理服务化。
dsh Harness 借鉴（ctx.agentPresets，commit 47f9438）：
preset 可 mount（挂载）/list（列出）/resolve（解析）/recompose（重组）/copy（复制）/remove（移除）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_preset_service_list_builtin():
    """PresetService.list 列出 4 内置预设（继承 #7 teaching_presets）。"""
    from services.preset_service import PresetService
    svc = PresetService()
    presets = svc.list()
    for name in ("standard", "minimal", "code-mode", "weil-classical"):
        assert name in presets, f"缺内置预设 {name}"


def test_preset_service_resolve():
    """PresetService.resolve 解析预设为可执行配置（联动权限档+persona）。"""
    from services.preset_service import PresetService
    svc = PresetService()
    r = svc.resolve("minimal")
    assert r["teaching_mode"] == "easy"
    assert r["permission_preset"] == "read_only"
    assert r["allow_write"] is False
    assert len(r["persona_body"]) > 0


def test_preset_service_mount():
    """PresetService.mount 挂载新预设（幂等注册）。"""
    from services.preset_service import PresetService
    svc = PresetService()
    svc.mount("test_mounted", {
        "desc": "挂载测试",
        "teaching_mode": "deep",
        "permission_preset": "full",
        "persona": "weil",
    })
    try:
        assert "test_mounted" in svc.list()
        assert svc.resolve("test_mounted")["teaching_mode"] == "deep"
    finally:
        svc.remove("test_mounted")


def test_preset_service_copy():
    """PresetService.copy 复制预设为新名（继承原配置）。"""
    from services.preset_service import PresetService
    svc = PresetService()
    svc.copy("minimal", "minimal_copy")
    try:
        assert "minimal_copy" in svc.list()
        r = svc.resolve("minimal_copy")
        assert r["teaching_mode"] == "easy"
        assert r["permission_preset"] == "read_only"
    finally:
        svc.remove("minimal_copy")


def test_preset_service_recompose():
    """PresetService.recompose 重组预设（覆盖部分字段生成新预设）。"""
    from services.preset_service import PresetService
    svc = PresetService()
    svc.recompose("code-mode", "code_deep", {"desc": "深度编程"})
    try:
        r = svc.resolve("code_deep")
        assert r["teaching_mode"] == "deep"      # 继承 code-mode
        assert r["permission_preset"] == "full"  # 继承 code-mode
        assert svc.get("code_deep")["desc"] == "深度编程"  # 覆盖
    finally:
        svc.remove("code_deep")


def test_preset_service_remove():
    """PresetService.remove 移除预设（不存在容错）。"""
    from services.preset_service import PresetService
    svc = PresetService()
    svc.mount("temp_remove", {"desc": "临时", "teaching_mode": "normal",
                              "permission_preset": "standard", "persona": "weil"})
    assert "temp_remove" in svc.list()
    svc.remove("temp_remove")
    assert "temp_remove" not in svc.list()
    svc.remove("no_such_preset")  # 不存在不抛异常


def test_preset_service_get_unknown_returns_none():
    """PresetService.get 未知预设返回 None（容错）。"""
    from services.preset_service import PresetService
    svc = PresetService()
    assert svc.get("no_such_preset") is None
