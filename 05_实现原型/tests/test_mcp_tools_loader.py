# -*- coding: utf-8 -*-
"""test_mcp_tools_loader.py —— §3.36 MCP 工具可移植性：配置驱动加载器测试

需求：config/mcp_tools.json 声明的工具（name/description/risk/module/function/params）
必须真正接入工具注册表——**改配置即生效**（改 description 反映到 get_all_tool_defs()、
增删工具条目反映到工具表）。当前（v1.1）断链：JSON 声明了但无加载器，改配置不影响行为。

测试策略（TDD：先 RED 后 GREEN）：
1. test_json_declared_tools_visible：JSON 声明的工具 description 应覆盖/反映到工具表
   （当前失败——实际表用硬编码 description，与 JSON 不一致）
2. test_add_tool_entry_changes_table：往 JSON 加一条新工具声明 → 工具表应多一个工具
   （当前失败——无加载器，工具表不随 JSON 变化）
3. test_remove_tool_entry_changes_table：删 JSON 条目 → 工具表应少一个工具
   （当前失败）
4. test_config_drive_change_description：改 JSON description → 工具表 description 变化
   （当前失败）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG = os.path.join(_PROJ_ROOT, "config", "mcp_tools.json")


@pytest.fixture(autouse=True)
def _restore_cfg(request):
    """测试前后还原 config/mcp_tools.json 原样（防止测试污染真实配置）。"""
    _orig = None
    if os.path.isfile(_CFG):
        with open(_CFG, encoding="utf-8") as f:
            _orig = f.read()
    yield
    if _orig is not None:
        with open(_CFG, "w", encoding="utf-8") as f:
            f.write(_orig)
    else:
        if os.path.isfile(_CFG):
            os.remove(_CFG)


def _load_json_cfg() -> dict:
    with open(_CFG, encoding="utf-8") as f:
        return json.load(f)


def _tool_names(defs) -> set:
    return {d.get("function", {}).get("name", "") for d in defs}


def _tool_desc(defs, name: str) -> str:
    for d in defs:
        if d.get("function", {}).get("name") == name:
            return d.get("function", {}).get("description", "")
    return ""


def test_json_declared_tools_visible():
    """JSON 声明的 14 个工具的 description 应覆盖/反映到工具表（改配置即生效）。"""
    from config_hub import get_hub
    cfg = _load_json_cfg()
    assert "tools" in cfg and len(cfg["tools"]) > 0, "配置应有 tools 列表"
    defs = get_hub().get_all_tool_defs()
    table = _tool_names(defs)
    # 每个 JSON 声明工具都应已注册
    for t in cfg["tools"]:
        assert t["name"] in table, f"JSON 声明工具 {t['name']} 未注册到工具表"
        # 关键断言：配置的 description 应反映到工具表（配置驱动）
        assert _tool_desc(defs, t["name"]) == t["description"], (
            f"工具 {t['name']} 的 description 未按配置生效："
            f"JSON='{t['description'][:40]}' 实际='{_tool_desc(defs, t['name'])[:40]}'"
        )


def test_add_tool_entry_changes_table():
    """往 JSON 加一条新工具声明 → 工具表应多一个工具。"""
    from config_hub import get_hub
    cfg = _load_json_cfg()
    before = len(_tool_names(get_hub().get_all_tool_defs()))
    # 新增一个工具声明（指向一个真实存在且安全的函数）
    cfg["tools"].append({
        "name": "paeg_probe_tool",
        "description": "测试探针工具（加载器验证用）",
        "risk": "read",
        "module": "tool_registry",
        "function": "is_tool_allowed",
        "params": {},
    })
    with open(_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    # 重新加载后工具表应包含新工具
    get_hub().reload_all()
    names = _tool_names(get_hub().get_all_tool_defs())
    assert "paeg_probe_tool" in names, "新增 JSON 条目后工具表未包含新工具（加载器未生效）"
    assert len(names) > before, "新增配置条目后工具总数未增加"


def test_remove_tool_entry_changes_table():
    """删 JSON 条目 → 工具表应少一个工具（可配置下架）。"""
    from config_hub import get_hub
    cfg = _load_json_cfg()
    # 找一个非内置、纯配置声明的工具（加一条临时的再删）
    cfg["tools"].append({
        "name": "paeg_tmp_remove_me",
        "description": "临时工具（删除验证）",
        "risk": "read",
        "module": "tool_registry",
        "function": "is_tool_allowed",
        "params": {},
    })
    with open(_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    get_hub().reload_all()
    names = _tool_names(get_hub().get_all_tool_defs())
    assert "paeg_tmp_remove_me" in names, "前提失败：临时工具未加载"
    # 删除后应消失
    cfg["tools"] = [t for t in cfg["tools"] if t["name"] != "paeg_tmp_remove_me"]
    with open(_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    get_hub().reload_all()
    names = _tool_names(get_hub().get_all_tool_defs())
    assert "paeg_tmp_remove_me" not in names, "删除 JSON 条目后工具表仍包含（加载器未生效）"


def test_config_drive_change_description():
    """改 JSON description → 工具表 description 应变（改配置即生效）。"""
    from config_hub import get_hub
    cfg = _load_json_cfg()
    target = cfg["tools"][0]["name"]
    new_desc = "【配置驱动验证】新描述 " + target
    cfg["tools"][0]["description"] = new_desc
    with open(_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    get_hub().reload_all()
    defs = get_hub().get_all_tool_defs()
    assert _tool_desc(defs, target) == new_desc, (
        f"改 JSON description 后工具表未更新（加载器未生效）：{target}"
    )


def test_write_risk_tools_locked_in_exam():
    """JSON 声明 risk=write 的工具应自动进入写工具黑名单（exam 模式锁定）。"""
    from config_hub import get_hub
    import tool_registry
    cfg = _load_json_cfg()
    write_tools = [t for t in cfg["tools"] if t.get("risk") == "write"]
    assert write_tools, "配置中应有 write 风险工具"
    # 加载后，write 工具应被 exam 模式拦截
    get_hub().reload_all()
    tool_registry.set_permission_preset("exam")
    try:
        for t in write_tools:
            assert not tool_registry.is_tool_allowed_by_preset(t["name"]), (
                f"JSON 声明 write 工具 {t['name']} 在 exam 模式未被锁定"
            )
    finally:
        tool_registry.set_permission_preset("standard")
