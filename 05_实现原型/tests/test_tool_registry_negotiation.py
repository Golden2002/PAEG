# -*- coding: utf-8 -*-
"""test_tool_registry_negotiation.py — #14 Tool Registry 能力协商测试（Harness 30 项 P1）

覆盖：metadata 级懒加载（先 name/desc，按需完整 def）/ 变更追踪（listChanged 语义）。
dsh Harness 借鉴（defer_loading + listChanged，commit 47f9438）：
工具元数据先注入 name/desc，完整定义按需加载——减少上下文占用，变更可追踪。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_get_tool_metadata_returns_names():
    """get_tool_metadata 返回工具名列表（metadata 级，不含完整 parameters）。"""
    from tool_registry import get_tool_metadata
    meta = get_tool_metadata()
    assert isinstance(meta, list)
    # 每个条目含 name/description（轻量）
    for item in meta:
        assert "name" in item
        assert "description" in item
    # 至少含核心工具
    names = {m["name"] for m in meta}
    assert "web_search" in names


def test_metadata_is_lightweight():
    """metadata 不含完整 parameters（懒加载——避免上下文膨胀）。"""
    from tool_registry import get_tool_metadata
    meta = get_tool_metadata()
    for item in meta:
        # metadata 级不携带 parameters（完整定义按需取）
        assert "parameters" not in item, f"metadata 不应含完整 parameters: {item.get('name')}"


def test_get_full_def_on_demand():
    """get_tool_full_def(name) 按需返回完整定义（含 parameters）。"""
    from tool_registry import get_tool_full_def
    full = get_tool_full_def("web_search")
    assert full is not None
    fn = full.get("function", {})
    assert fn.get("name") == "web_search"
    assert "parameters" in fn
    assert "properties" in fn.get("parameters", {})


def test_get_full_def_missing_returns_none():
    """未知工具完整定义返回 None（容错）。"""
    from tool_registry import get_tool_full_def
    assert get_tool_full_def("no_such_tool") is None


def test_list_changed_since_tracks_changes():
    """list_changed_since(seq) 返回新增/变更工具（dsh listChanged 语义）。"""
    from tool_registry import get_tool_revision, list_changed_since
    rev = get_tool_revision()
    assert isinstance(rev, int)
    # 全量变更（从 0）包含核心工具
    changed = list_changed_since(0)
    assert "web_search" in changed
    # 从当前 rev → 无变更（或仅新增）
    changed_now = list_changed_since(rev)
    assert isinstance(changed_now, list)


def test_metadata_and_full_consistent():
    """metadata 中的 name 都能取到完整定义（一致性）。"""
    from tool_registry import get_tool_metadata, get_tool_full_def
    for item in get_tool_metadata()[:5]:
        name = item["name"]
        full = get_tool_full_def(name)
        assert full is not None, f"{name} metadata 有但完整定义缺失"
