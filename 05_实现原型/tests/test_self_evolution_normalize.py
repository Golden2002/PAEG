# -*- coding: utf-8 -*-
"""
B4 · _normalize_node + schema_version 测试（自进化节点标准化）

TDD 阶段：RED（先写失败测试，固定期望行为）
- test_normalize_node_fills_defaults：缺 tags/importance/grade_level → 输出有默认值
- test_normalize_node_bumps_schema_version：产出含 schema_version="2025.08.v2"
- test_normalize_node_is_idempotent：normalize(normalize(x)) == normalize(x)
"""
from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from self_evolution import SelfEvolution


SCHEMA_VERSION = "2025.08.v2"


# ─────────────────────────────────────
# Fixtures
# ─────────────────────────────────────
@pytest.fixture
def se():
    """构造一个 SelfEvolution（无 LLM）——仅用于测试 _normalize_node 纯函数路径。"""
    return SelfEvolution(llm=None, verbose=False)


# ─────────────────────────────────────
# 改动 1 / 测试 1：缺省字段填充
# ─────────────────────────────────────
def test_normalize_node_fills_defaults(se):
    """缺 tags/importance/grade_level → 输出有默认值（tags=[], importance='medium', grade_level='high_school'）。"""
    raw = {
        "id": "evolved.math.test",
        "subject": "math",
        "concept": "测试概念",
        "definition": "一个简短定义。",
        "intuition": "一段直觉解释。",
    }
    out = se._normalize_node(raw)

    assert out["tags"] == []
    assert out["importance"] == "medium"
    assert out["grade_level"] == "high_school"
    print("✓ test_normalize_node_fills_defaults")


# ─────────────────────────────────────
# 改动 1 / 测试 2：schema_version 写入
# ─────────────────────────────────────
def test_normalize_node_bumps_schema_version(se):
    """产出节点含 schema_version='2025.08.v2'。"""
    raw = {
        "id": "evolved.math.test",
        "subject": "math",
        "concept": "测试概念",
        "definition": "一个简短定义。",
        "intuition": "一段直觉解释。",
    }
    out = se._normalize_node(raw)

    assert out.get("schema_version") == SCHEMA_VERSION
    print("✓ test_normalize_node_bumps_schema_version")


# ─────────────────────────────────────
# 改动 1 / 测试 3：幂等性
# ─────────────────────────────────────
def test_normalize_node_is_idempotent(se):
    """normalize(normalize(x)) == normalize(x)——重复归一化不会改字段。"""
    raw = {
        "id": "evolved.physics.test",
        "subject": "physics",
        "concept": "测试概念",
        "definition": "定义文本",
        "intuition": "直觉文本",
        # 已包含部分字段
        "tags": ["物理学", "基础"],
        "importance": "high",
        "grade_level": "middle_school",
    }
    once = se._normalize_node(raw)
    twice = se._normalize_node(once)

    assert once == twice
    # 同时应当保留用户显式给的 tags/importance/grade_level（不被覆盖）
    assert twice["tags"] == ["物理学", "基础"]
    assert twice["importance"] == "high"
    assert twice["grade_level"] == "middle_school"
    print("✓ test_normalize_node_is_idempotent")


if __name__ == "__main__":
    # 直跑模式（与项目内其他测试一致）
    se_obj = SelfEvolution(llm=None, verbose=False)
    # 把 fixture 替换成手动调用
    se_obj._normalize_node({
        "id": "x", "subject": "math", "concept": "c",
        "definition": "d", "intuition": "i"
    })
    test_normalize_node_fills_defaults(_obj_se())
    test_normalize_node_bumps_schema_version(_obj_se())
    test_normalize_node_is_idempotent(_obj_se())
    print("\n所有测试通过 ✓")


def _obj_se():
    class _Box:
        _normalize_node = SelfEvolution(llm=None, verbose=False)._normalize_node
    return _Box()