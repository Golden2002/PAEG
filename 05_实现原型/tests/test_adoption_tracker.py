# -*- coding: utf-8 -*-
"""§3.82 E1 自我更新采纳事件埋点测试。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.adoption_tracker import record_adoption, compute_acceptance


def test_record_adoption_writes(tmp_path, monkeypatch):
    """S1 主路径：记录采纳事件 → 落盘。"""
    import services.adoption_tracker as at
    at._EVENTS_LOG = str(tmp_path / "adoption_events.jsonl")
    ok = record_adoption("quality_gate.promote", True, "导数讲解优化")
    assert ok is True
    assert os.path.isfile(at._EVENTS_LOG)


def test_record_rejection(tmp_path, monkeypatch):
    """S2 主路径：记录拒绝事件。"""
    import services.adoption_tracker as at
    at._EVENTS_LOG = str(tmp_path / "adoption_events.jsonl")
    record_adoption("periodic.weekly", False, "过时建议")
    a = compute_acceptance()
    assert a["total"] == 1
    assert a["adopted"] == 0
    assert a["rejected"] == 1


def test_compute_acceptance_mixed(tmp_path, monkeypatch):
    """S3 主路径：多条事件 → 精确采纳率。"""
    import services.adoption_tracker as at
    at._EVENTS_LOG = str(tmp_path / "adoption_events.jsonl")
    record_adoption("quality_gate.promote", True, "洞察A")
    record_adoption("quality_gate.promote", True, "洞察B")
    record_adoption("periodic.weekly", False, "建议C")
    a = compute_acceptance()
    assert a["total"] == 3
    assert a["adopted"] == 2
    assert a["rejected"] == 1
    assert a["acceptance_rate"] == pytest.approx(0.67, abs=0.01)
    assert "quality_gate.promote" in a["by_source"]
    assert a["by_source"]["quality_gate.promote"]["adopted"] == 2


def test_compute_acceptance_empty(tmp_path, monkeypatch):
    """S4 边界：无事件 → 空结构（rate=None 诚实标注）。"""
    import services.adoption_tracker as at
    at._EVENTS_LOG = str(tmp_path / "nonexistent.jsonl")
    a = compute_acceptance()
    assert a["total"] == 0
    assert a["acceptance_rate"] is None
    assert "暂无" in a["note"]


def test_compute_acceptance_window(tmp_path, monkeypatch):
    """S5 边界：窗口过滤（30 天内）。"""
    import services.adoption_tracker as at
    import json
    import datetime
    at._EVENTS_LOG = str(tmp_path / "adoption_events.jsonl")
    # 写一条 60 天前的旧事件
    old_ts = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
    with open(at._EVENTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": old_ts, "source": "old", "adopted": True}, ensure_ascii=False) + "\n")
    record_adoption("quality_gate.promote", True, "新洞察")
    a = compute_acceptance(window_days=30)
    assert a["total"] == 1  # 仅新事件
    assert a["adopted"] == 1
