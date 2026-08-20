# -*- coding: utf-8 -*-
"""§3.79 第 6 轮测试：概念图谱接线 + SRS 复习提醒 + 运维脚本（2026-08-20）。

覆盖：
  孤儿 concept_graph 接线：
    - ConceptGraph.prerequisites/successors 可用（内置种子）
    - Presenter 注入点存在（subagents.py 含 概念定位 注入代码）
  SRS 复习提醒（build_reminder）：
    - 到期卡 → 提醒文本；无到期卡 → 空串；同 subject 优先
  运维友好：ops/checkup.ps1 存在
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import services.srs_service as srs
from services.concept_graph import ConceptGraph


# ────────────────────────────────────────────
# 孤儿 concept_graph 接线
# ────────────────────────────────────────────
def test_concept_graph_builtin_prereqs():
    cg = ConceptGraph()
    assert "极限" in (cg.prerequisites("导数") or [])
    assert "导数" in (cg.successors("极限") or [])


def test_concept_graph_missing_node_tolerant():
    cg = ConceptGraph()
    assert cg.prerequisites("不存在的概念xyz") in (None, [])
    assert cg.successors("不存在的概念xyz") in (None, [])


def test_presenter_has_graph_injection_point():
    """Presenter 概念定位注入代码存在（subagents.py）。"""
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "subagents.py")
    src = open(_p, encoding="utf-8").read()
    assert "概念定位（知识图谱）" in src
    assert "ConceptGraph" in src


# ────────────────────────────────────────────
# SRS 复习提醒
# ────────────────────────────────────────────
def _force_due(uid, concept, days=1):
    """把卡 due 改为过去（模拟到期）。"""
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "users_data", uid, "srs.json")
    _d = json.load(open(_p, encoding="utf-8"))
    _d["cards"][concept]["due"] = (time.strftime("%Y-%m-%d"))
    json.dump(_d, open(_p, "w", encoding="utf-8"), ensure_ascii=False)


def test_build_reminder_with_due(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "_srs_path", lambda uid: str(tmp_path / f"{uid}_srs.json"))
    srs.add_card("u_rem1", "导数", "math", quality=5)
    # 强制到期
    _d = json.load(open(str(tmp_path / "u_rem1_srs.json"), encoding="utf-8"))
    _d["cards"]["导数"]["due"] = time.strftime("%Y-%m-%d")
    json.dump(_d, open(str(tmp_path / "u_rem1_srs.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    _t = srs.build_reminder("u_rem1", subject="math")
    assert "导数" in _t
    assert "复习" in _t
    # 无到期卡（新建卡 due=明天）→ 空串
    srs.add_card("u_rem2", "积分", "math", quality=5)
    assert srs.build_reminder("u_rem2", subject="math") == ""


def test_build_reminder_subject_priority(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "_srs_path", lambda uid: str(tmp_path / f"{uid}_srs.json"))
    srs.add_card("u_rem3", "导数", "math", quality=5)
    srs.add_card("u_rem3", "光合作用", "biology", quality=5)
    for _f in ("导数", "光合作用"):
        _d = json.load(open(str(tmp_path / "u_rem3_srs.json"), encoding="utf-8"))
        _d["cards"][_f]["due"] = time.strftime("%Y-%m-%d")
        json.dump(_d, open(str(tmp_path / "u_rem3_srs.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
    _t = srs.build_reminder("u_rem3", subject="biology")
    assert "光合作用" in _t
    assert "导数" not in _t  # 同 subject 优先


# ────────────────────────────────────────────
# 运维友好
# ────────────────────────────────────────────
def test_ops_checkup_script_exists():
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "..", "ops", "checkup.ps1")
    assert os.path.isfile(_p), "缺 ops/checkup.ps1"
    src = open(_p, encoding="utf-8").read()
    assert "api/health" in src and "api/metrics" in src
