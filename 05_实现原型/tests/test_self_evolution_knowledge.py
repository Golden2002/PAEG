# -*- coding: utf-8 -*-
"""
A1 · _extract_knowledge Schema+CoT 升级测试

TDD 阶段：RED（先写失败测试，固定期望行为）
- test_extract_knowledge_includes_metadata_fields：mock LLM 返回新 schema（含 type/tags/importance/grade）→ 节点保留这些字段
- test_extract_knowledge_rejects_legacy_schema：旧 schema 缺字段 → 兜底默认值（type='concept'、tags=[]、importance='medium'）而非报错

mock 策略：用 monkeypatch 替换 ``subagents._safe_chat`` 为可控函数，
避开真实 LLM（与项目内既有测试一致，如 test_self_update_agent.py）。
"""
from __future__ import annotations

import sys
import os
import json
import types
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import subagents as _sa
from self_evolution import SelfEvolution


# ─────────────────────────────────────
# Helpers
# ─────────────────────────────────────
def _mock_session(concept: str = "熵", subject: str = "physics"):
    """构造一个 Session 替身：含 history + evaluations（avg>=0.7）。"""
    sess = types.SimpleNamespace()
    sess.concept = concept
    sess.subject = subject
    sess.session_id = "test_session_001"
    sess.history = [
        {"role": "user", "content": f"请讲讲{concept}"},
        {"role": "assistant", "content": f"{concept} 是物理学核心概念..."},
        {"role": "user", "content": "能再具体点吗"},
        {"role": "assistant", "content": "我用生活中散乱的房间举例..."},
    ]
    # 让 avg_score >= 0.7 通过前置过滤
    sess.evaluations = [{"score": 0.85}, {"score": 0.9}, {"score": 0.8}]
    return sess


def _patch_safe_chat(monkeypatch, response_text: str):
    """替换 subagents._safe_chat 为返回 response_text 的 mock。"""
    monkeypatch.setattr(
        _sa, "_safe_chat",
        lambda *args, **kwargs: response_text,
    )


# ─────────────────────────────────────
# 改动 2 / 测试 1：新 schema 含 metadata 字段
# ─────────────────────────────────────
def test_extract_knowledge_includes_metadata_fields(monkeypatch, tmp_path):
    """Mock LLM 返回新 schema（含 type/tags/importance/grade）→ _extract_knowledge 输出保留这些字段。"""
    # 用 tmp_path 隔离 evolved_*.json 写入（防污染真实 Library）
    se = SelfEvolution(llm=None, verbose=False)
    se.evolved_dir = str(tmp_path / "subjects")
    os.makedirs(se.evolved_dir, exist_ok=True)

    new_schema = {
        "concept": "熵",
        "topic": "热力学",
        "definition": "系统无序度的度量。",
        "intuition": "想象一个房间越来越乱——熵在增大。",
        "level": "high_school",
        "subject": "physics",
        "grade": "high_school",
        "type": "concept",
        "tags": ["物理学", "热力学", "状态量"],
        "importance": "high",
    }
    _patch_safe_chat(monkeypatch, json.dumps(new_schema, ensure_ascii=False))

    sess = _mock_session("熵", "physics")
    node = se._extract_knowledge("熵", "physics", sess)

    assert node is not None, "_extract_knowledge 不应返回 None（新 schema 合规）"
    # 关键 metadata 字段被保留
    assert node.get("type") == "concept"
    assert node.get("tags") == ["物理学", "热力学", "状态量"]
    assert node.get("importance") == "high"
    # grade 兼容（既允许 grade 也允许 grade_level）
    assert node.get("grade") == "high_school" or node.get("grade_level") == "high_school"
    # schema_version 也被注入（B4 联合作用）
    assert node.get("schema_version") == "2025.08.v2"
    print("✓ test_extract_knowledge_includes_metadata_fields")


# ─────────────────────────────────────
# 改动 2 / 测试 2：旧 schema 缺字段 → 兜底默认值
# ─────────────────────────────────────
def test_extract_knowledge_rejects_legacy_schema(monkeypatch, tmp_path):
    """旧 schema（仅含 concept/topic/definition/intuition/level，无 type/tags/importance）
    → _extract_knowledge 不报错，输出经 _normalize_node 兜底默认值。

    关键行为：不能因字段缺失而抛出/返回 None；type='concept'、tags=[]、importance='medium'
    """
    se = SelfEvolution(llm=None, verbose=False)
    se.evolved_dir = str(tmp_path / "subjects")
    os.makedirs(se.evolved_dir, exist_ok=True)

    legacy_schema = {
        "concept": "极限",
        "topic": "数学分析基础",
        "definition": "描述变量趋近某固定值的数学概念。",
        "intuition": "一根绳子每天剪一半，永远到不了 0——极限就是用来精确描述这种'无限逼近'的数学语言。",
        "level": "high_school",
    }
    _patch_safe_chat(monkeypatch, json.dumps(legacy_schema, ensure_ascii=False))

    sess = _mock_session("极限", "math")
    node = se._extract_knowledge("极限", "math", sess)

    assert node is not None, "旧 schema 缺字段也应兜底，不应返回 None"
    # 兜底默认值
    assert node.get("type") == "concept", f"缺 type 应默认 concept，实际 {node.get('type')}"
    assert node.get("tags") == [], f"缺 tags 应默认 []，实际 {node.get('tags')}"
    assert node.get("importance") == "medium", f"缺 importance 应默认 medium，实际 {node.get('importance')}"
    # grade 兜底 high_school
    assert node.get("grade_level") == "high_school"
    # schema_version 注入
    assert node.get("schema_version") == "2025.08.v2"
    print("✓ test_extract_knowledge_rejects_legacy_schema")


if __name__ == "__main__":
    test_extract_knowledge_includes_metadata_fields()
    test_extract_knowledge_rejects_legacy_schema()
    print("\n所有测试通过 ✓")