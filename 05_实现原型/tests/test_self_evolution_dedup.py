# -*- coding: utf-8 -*-
"""
A2 · _append_evolved_node 确定性去重 + supersession 测试

TDD 阶段：RED（先写失败测试，固定期望行为）
- test_append_evolved_node_dedup_same_key：同 (subject, concept) 二次写入 → 仅 1 个 live 节点，旧节点 superseded

设计要点（spec）：
- 不依赖 embedding（PAEG 无 embedding 基础设施，用确定性键去重）
- 以 (subject, concept) 为键查当日文件既有节点
- 若已存在同键节点 → 旧节点标 status="superseded" + superseded_by=新id
- 新节点 status="live"
- 不重复插入同键
"""
from __future__ import annotations

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import subagents as _sa
from self_evolution import SelfEvolution


def _patch_reload_library(monkeypatch):
    """屏蔽 reload_library 副作用。"""
    try:
        from infra import runtime
        monkeypatch.setattr(runtime, "reload_library", lambda: 0)
    except Exception:
        pass


# ─────────────────────────────────────
# 改动 4 / 测试 1：同键去重 + 旧节点 superseded
# ─────────────────────────────────────
def test_append_evolved_node_dedup_same_key(monkeypatch, tmp_path):
    """同 (subject, concept) 二次写入 → 仅 1 个 live 节点，旧节点 superseded。

    流程：
    1) 写入 node_old (subject="math", concept="极限")
    2) 写入 node_new (subject="math", concept="极限")  ← 同键
    3) 读落盘文件 → 应有 2 个节点，但仅 1 个 status=="live"，另一个 status=="superseded"
    4) superseded 节点的 superseded_by 应指向新节点 id
    """
    se = SelfEvolution(llm=None, verbose=False)
    # 隔离 evolved_*.json 写入（防污染真实 Library）
    se.evolved_dir = str(tmp_path / "subjects")
    os.makedirs(se.evolved_dir, exist_ok=True)
    _patch_reload_library(monkeypatch)

    # 第一次写入（旧版本）
    node_old = {
        "id": "evolved.math.极限",
        "subject": "math",
        "concept": "极限",
        "definition": "旧版定义：极限是变量趋近某值的概念。",
        "intuition": "旧版直觉。",
        "content": "旧版定义 旧版直觉",
        # schema_version/tags/importance 等会由 _normalize_node 兜底
    }
    se._append_evolved_node(node_old, subject="math")

    # 第二次写入（同 subject+concept，新版本）
    node_new = {
        "id": "evolved.math.极限",
        "subject": "math",
        "concept": "极限",
        "definition": "新版定义：极限是描述变量无限趋近某固定值的数学概念。",
        "intuition": "新版直觉：绳子每天剪一半，永远到不了 0。",
        "content": "新版定义 新版直觉",
    }
    se._append_evolved_node(node_new, subject="math")

    # 读落盘文件
    import datetime as _dt
    fname = f"evolved_{_dt.datetime.now().strftime('%Y%m%d')}.json"
    fpath = os.path.join(se.evolved_dir, fname)
    assert os.path.isfile(fpath), f"应已落盘到 {fpath}"
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)

    # 关键断言 1：仅 1 个 live 节点
    live_nodes = [n for n in data.values() if n.get("status") == "live"]
    assert len(live_nodes) == 1, \
        f"仅 1 个 live 节点，实际 {len(live_nodes)} 个。全部状态：{[n.get('status') for n in data.values()]}"

    # 关键断言 2：旧节点被标 superseded + superseded_by 指向新 id
    superseded_nodes = [n for n in data.values() if n.get("status") == "superseded"]
    assert len(superseded_nodes) >= 1, \
        f"旧节点应被标 superseded，实际 {len(superseded_nodes)} 个"
    # 找到旧节点（通过 content 包含"旧版"）
    old = next((n for n in superseded_nodes if "旧版" in n.get("content", "")), None)
    assert old is not None, "应能找到旧版本节点（content 含「旧版」）"
    assert old.get("superseded_by") == "evolved.math.极限", \
        f"旧节点 superseded_by 应指向新节点 id，实际 {old.get('superseded_by')}"

    # 关键断言 3：新节点是 live（通过 content 包含"新版"）
    new_live = next((n for n in live_nodes if "新版" in n.get("content", "")), None)
    assert new_live is not None, "新版本节点应为 live 状态"

    print("✓ test_append_evolved_node_dedup_same_key")


if __name__ == "__main__":
    # 直跑模式（与项目内既有测试一致）
    import tempfile
    se_obj = SelfEvolution(llm=None, verbose=False)
    tmp = tempfile.mkdtemp()
    se_obj.evolved_dir = os.path.join(tmp, "subjects")
    os.makedirs(se_obj.evolved_dir, exist_ok=True)

    _patch_reload_library_safe()

    node_old = {
        "id": "evolved.math.极限", "subject": "math", "concept": "极限",
        "definition": "旧版定义", "intuition": "旧版直觉",
        "content": "旧版定义 旧版直觉",
    }
    se_obj._append_evolved_node(node_old, subject="math")

    node_new = {
        "id": "evolved.math.极限", "subject": "math", "concept": "极限",
        "definition": "新版定义", "intuition": "新版直觉",
        "content": "新版定义 新版直觉",
    }
    se_obj._append_evolved_node(node_new, subject="math")

    import datetime as _dt
    fname = f"evolved_{_dt.datetime.now().strftime('%Y%m%d')}.json"
    fpath = os.path.join(se_obj.evolved_dir, fname)
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)
    live = [n for n in data.values() if n.get("status") == "live"]
    superseded = [n for n in data.values() if n.get("status") == "superseded"]
    print(f"live={len(live)}, superseded={len(superseded)}")
    assert len(live) == 1
    assert len(superseded) >= 1
    print("\n所有测试通过 ✓")


def _patch_reload_library_safe():
    try:
        from infra import runtime
        runtime.reload_library = lambda: 0
    except Exception:
        pass