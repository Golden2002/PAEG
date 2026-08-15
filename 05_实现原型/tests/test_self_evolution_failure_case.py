# -*- coding: utf-8 -*-
"""
A3 · _failure_case_distill 失败案例提炼测试

TDD 阶段：RED（先写失败测试，固定期望行为）
- test_failure_case_distill_produces_anti_pattern_node：mock LLM 返回 →
  节点 type=="failure_case"、importance=="high"，且过 QualityGate 后写入 evolved_*.json

设计要点：
- 把失败教学提炼为 anti-pattern 节点（type="failure_case"）
- 复用 _extract_knowledge 类似结构但 type 不同
- 过 QualityGate 后写入 evolved_*.json（复用 _append_evolved_node）

mock 策略：用 monkeypatch 替换 subagents._safe_chat（同 A1 测试一致）。
"""
from __future__ import annotations

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import subagents as _sa
from self_evolution import SelfEvolution


def _patch_safe_chat(monkeypatch, response_text: str):
    """替换 subagents._safe_chat 为返回 response_text 的 mock。"""
    monkeypatch.setattr(
        _sa, "_safe_chat",
        lambda *args, **kwargs: response_text,
    )


def _patch_reload_library(monkeypatch):
    """屏蔽 reload_library 副作用（避免污染真实 KB / 抛异常）。"""
    try:
        from infra import runtime
        monkeypatch.setattr(runtime, "reload_library", lambda: 0)
    except Exception:
        pass


# ─────────────────────────────────────
# 改动 3 / 测试 1：失败案例提炼为 anti-pattern 节点
# ─────────────────────────────────────
def test_failure_case_distill_produces_anti_pattern_node(monkeypatch, tmp_path):
    """Mock LLM 返回 failure_reason + corrective_strategy → 节点 type=='failure_case'、importance=='high'，
    且过 QualityGate 后写入 evolved_*.json。"""
    se = SelfEvolution(llm=None, verbose=False)
    # 隔离 evolved_*.json 写入
    se.evolved_dir = str(tmp_path / "subjects")
    os.makedirs(se.evolved_dir, exist_ok=True)
    _patch_reload_library(monkeypatch)

    # LLM 返回结构（与 _extract_knowledge 风格一致，但 type 改 failure_case）
    failure_payload = {
        "concept": "极限",
        "topic": "数学分析基础",
        "definition": "（失败案例）教师用纯形式化 ε-N 定义开场，未给出任何直觉铺垫，导致学生当场卡壳。",
        "intuition": "失败模式：先形式、后直觉——'极限'是高度直觉概念，直接甩定义违背认知规律。",
        "failure_reason": "未先建立'无限趋近但永远不到'的几何直觉，直接给出 ε-N 形式化定义，学生无法建立心理表征。",
        "corrective_strategy": "先用一个生活/几何例子（如'绳子每天剪一半、永远到不了 0'）建立直觉，再引出 ε-N 形式化。",
        "level": "high_school",
        "subject": "math",
        "grade": "high_school",
        "type": "failure_case",     # ⭐ 关键：与正常 concept 节点不同
        "tags": ["极限", "反例", "教学顺序"],
        "importance": "high",        # ⭐ 关键：失败案例高优先级（避免重蹈覆辙）
    }
    _patch_safe_chat(monkeypatch, json.dumps(failure_payload, ensure_ascii=False))

    # 调用：失败案例提炼
    result = se._failure_case_distill(
        concept="极限",
        subject="math",
        failure_note=(
            "学生反馈听不懂极限——我用 ε-N 定义开场，学生听不懂就走神了。"
            "反思：应该先讲直觉再讲形式。"
        ),
    )

    # 1) 节点关键字段断言
    assert "node" in result, "返回值应包含 node 字段（写入的节点内容）"
    node = result["node"]
    assert node["type"] == "failure_case", \
        f"anti-pattern 节点的 type 应为 'failure_case'，实际 {node.get('type')}"
    assert node["importance"] == "high", \
        f"anti-pattern 节点的 importance 应为 'high'，实际 {node.get('importance')}"
    assert "failure_reason" in node, "节点应含 failure_reason 字段"
    assert "corrective_strategy" in node, "节点应含 corrective_strategy 字段"
    # subject/id/schema_version（B4 联合作用）
    assert node["subject"] == "math"
    assert node["id"] == "evolved.math.极限"
    assert node.get("schema_version") == "2025.08.v2"

    # 2) 写入断言：distilled >= 1
    assert result.get("distilled", 0) >= 1 or result.get("recorded", 0) >= 1, \
        f"提炼结果应表示成功入库，实际 {result}"

    # 3) 文件落盘断言
    fname = "evolved_" + __import__("datetime").datetime.now().strftime("%Y%m%d") + ".json"
    fpath = os.path.join(se.evolved_dir, fname)
    assert os.path.isfile(fpath), f"evolved_*.json 应已落盘到 {fpath}"
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)
    assert any(
        v.get("type") == "failure_case" and v.get("subject") == "math"
        for v in data.values()
    ), "落盘文件中应存在 type=='failure_case' 的节点"

    print("✓ test_failure_case_distill_produces_anti_pattern_node")


if __name__ == "__main__":
    # 直跑模式：提供一个简化 monkeypatch 替代
    se_obj = SelfEvolution(llm=None, verbose=False)
    import tempfile
    tmp = tempfile.mkdtemp()
    se_obj.evolved_dir = os.path.join(tmp, "subjects")
    os.makedirs(se_obj.evolved_dir, exist_ok=True)

    _patch_reload_library_safe()

    payload = json.dumps({
        "concept": "极限",
        "topic": "数学分析",
        "definition": "失败案例：纯形式化 ε-N 定义开场",
        "intuition": "失败模式：先形式、后直觉",
        "failure_reason": "未先建立几何直觉",
        "corrective_strategy": "先生活例子再建 ε-N 形式化",
        "level": "high_school",
        "subject": "math",
        "grade": "high_school",
        "type": "failure_case",
        "tags": ["极限", "反例"],
        "importance": "high",
    }, ensure_ascii=False)

    orig_chat = _sa._safe_chat
    _sa._safe_chat = lambda *a, **kw: payload
    try:
        result = se_obj._failure_case_distill(
            concept="极限", subject="math",
            failure_note="学生反馈听不懂极限"
        )
        print("result:", result)
        assert result["node"]["type"] == "failure_case"
        assert result["node"]["importance"] == "high"
        print("\n所有测试通过 ✓")
    finally:
        _sa._safe_chat = orig_chat


def _patch_reload_library_safe():
    try:
        from infra import runtime
        runtime.reload_library = lambda: 0
    except Exception:
        pass