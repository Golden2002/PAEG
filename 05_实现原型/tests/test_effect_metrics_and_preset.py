# -*- coding: utf-8 -*-
"""§3.79 E1 效果指标管道 + C1 考试模式 Permission Preset 测试（2026-08-20）。

覆盖：
  E1 效果指标测量管道（services/effect_metrics.py）：
    - 四指标结构齐全（坚持率/保留率/元认知准确率/自我更新采纳率）
    - 保留率代理口径（transcripts evaluation 序列，monkeypatch _PROJ）
    - 坚持率代理口径（profile mtime，monkeypatch _PROJ）
    - 月报导出（json + md 落盘）
    - /api/metrics/effects 端点 200
  C1 考试模式 Permission Preset：
    - teaching_presets.exam 预设存在（permission_preset=exam）
    - resolve_preset("exam").allow_write=False（禁写）
    - /api/preset/list 含 exam
    - /api/preset/apply exam → tool_registry exam 激活 → generate_ppt 被禁（随后恢复 standard）
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import services.effect_metrics as em
import services.teaching_presets as tp
import tool_registry


# ────────────────────────────────────────────
# E1 效果指标管道
# ────────────────────────────────────────────
def test_compute_effect_metrics_structure():
    """四指标结构齐全（含 target/status/value/note）。"""
    res = em.compute_effect_metrics(window_days=30)
    assert set(res["metrics"].keys()) == {
        "persistence_rate", "retention_rate",
        "metacognition_accuracy", "self_update_acceptance",
    }
    for _k, _m in res["metrics"].items():
        assert "value" in _m and "status" in _m and "target" in _m and "note" in _m
    assert res["window_days"] == 30
    assert "computed_at" in res


def test_retention_rate_proxy(tmp_path, monkeypatch):
    """保留率代理：末次评估>=首次评估占比。"""
    monkeypatch.setattr(em, "_PROJ", str(tmp_path))
    _tdir = tmp_path / "transcripts"
    _tdir.mkdir()
    _now = time.time()
    # 会话 A：0.4 → 0.8（保留/提升）
    (_tdir / "ses_a.jsonl").write_text(
        json.dumps({"ts": _now, "session_id": "ses_a", "item_type": "evaluation",
                    "step_id": 1, "score": 0.4}) + "\n" +
        json.dumps({"ts": _now, "session_id": "ses_a", "item_type": "evaluation",
                    "step_id": 2, "score": 0.8}) + "\n",
        encoding="utf-8")
    # 会话 B：0.9 → 0.5（未保留）
    (_tdir / "ses_b.jsonl").write_text(
        json.dumps({"ts": _now, "session_id": "ses_b", "item_type": "evaluation",
                    "step_id": 1, "score": 0.9}) + "\n" +
        json.dumps({"ts": _now, "session_id": "ses_b", "item_type": "evaluation",
                    "step_id": 2, "score": 0.5}) + "\n",
        encoding="utf-8")
    # 会话 C：仅 1 次评估（不计入 eligible）
    (_tdir / "ses_c.jsonl").write_text(
        json.dumps({"ts": _now, "session_id": "ses_c", "item_type": "evaluation",
                    "step_id": 1, "score": 0.6}) + "\n",
        encoding="utf-8")
    r = em.compute_retention_rate(window_days=30)
    assert r["eligible_sessions"] == 2
    assert r["retained_sessions"] == 1
    assert r["value"] == 0.5


def test_retention_rate_no_data(tmp_path, monkeypatch):
    """无会话数据 → value=None（不编造达标）。"""
    monkeypatch.setattr(em, "_PROJ", str(tmp_path))
    r = em.compute_retention_rate(window_days=30)
    assert r["value"] is None
    assert r["status"] == "no_data"


def test_persistence_rate_proxy(tmp_path, monkeypatch):
    """坚持率代理：窗口内活跃画像中后 14 天仍活跃占比。"""
    monkeypatch.setattr(em, "_PROJ", str(tmp_path))
    _udir = tmp_path / "users_data"
    _u1 = _udir / "u1"
    _u2 = _udir / "u2"
    _u1.mkdir(parents=True)
    _u2.mkdir(parents=True)
    _now = time.time()
    _day = 86400
    # u1 活跃于 5 天前（后 14 天）→ recent_active
    (_u1 / "profile.json").write_text("{}", encoding="utf-8")
    os.utime(str(_u1 / "profile.json"), (_now - 5 * _day, _now - 5 * _day))
    # u2 活跃于 20 天前（窗口内但非后 14 天）
    (_u2 / "profile.json").write_text("{}", encoding="utf-8")
    os.utime(str(_u2 / "profile.json"), (_now - 20 * _day, _now - 20 * _day))
    r = em.compute_persistence_rate(window_days=30)
    assert r["window_active"] == 2
    assert r["recent_active"] == 1
    assert r["value"] == 0.5


def test_export_monthly_report(tmp_path, monkeypatch):
    """月报导出：json + md 落盘。"""
    monkeypatch.setattr(em, "_PROJ", str(tmp_path))
    _res = em.export_monthly_report(window_days=30)
    assert _res["ok"] is True
    assert os.path.isfile(_res["path_json"])
    assert os.path.isfile(_res["path_md"])
    with open(_res["path_md"], encoding="utf-8") as _fh:
        _md = _fh.read()
    assert "效果指标月报" in _md
    assert "persistence_rate" in _md or "坚持率" in _md


def test_api_metrics_effects_endpoint():
    """/api/metrics/effects 返回 200 + 四指标。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/metrics/effects")
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    body = r.get_json()
    assert set(body["metrics"].keys()) == {
        "persistence_rate", "retention_rate",
        "metacognition_accuracy", "self_update_acceptance",
    }


# ────────────────────────────────────────────
# C1 考试模式 Permission Preset
# ────────────────────────────────────────────
def test_teaching_preset_exam_exists():
    """exam 教学预设存在且联动 exam 权限档（禁写）。"""
    cfg = tp.get_teaching_preset("exam")
    assert cfg.get("permission_preset") == "exam"
    res = tp.resolve_preset("exam")
    assert res["allow_write"] is False
    assert res["permission_preset"] == "exam"


def test_preset_list_endpoint_contains_exam():
    """/api/preset/list 返回 exam（含 allow_write=False）。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/preset/list")
    assert r.status_code == 200
    body = r.get_json()
    names = [p.get("preset") for p in body.get("presets", [])]
    assert "exam" in names
    _exam = next(p for p in body["presets"] if p.get("preset") == "exam")
    assert _exam["allow_write"] is False


def test_preset_apply_exam_locks_write_tools():
    """应用 exam → generate_ppt 被 is_tool_allowed_by_preset 拦截；恢复 standard。"""
    from server import app
    client = app.test_client()
    # 基线：standard 下允许
    r = client.post("/api/preset/apply", json={"preset": "standard", "learner_id": "u_c1_test"})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert r.get_json()["allow_write"] is True
    assert tool_registry.is_tool_allowed_by_preset("generate_ppt") is True
    # 切 exam → 禁写
    r = client.post("/api/preset/apply", json={"preset": "exam", "learner_id": "u_c1_test"})
    assert r.status_code == 200
    _b = r.get_json()
    assert _b["allow_write"] is False
    assert tool_registry.is_tool_allowed_by_preset("generate_ppt") is False
    assert tool_registry.is_tool_allowed_by_preset("web_search") is True
    # 恢复 standard（防污染后续测试）
    client.post("/api/preset/apply", json={"preset": "standard"})
    assert tool_registry.is_tool_allowed_by_preset("generate_ppt") is True


def test_preset_apply_unknown_returns_400():
    """未知预设 → 400。"""
    from server import app
    client = app.test_client()
    r = client.post("/api/preset/apply", json={"preset": "no_such_preset"})
    assert r.status_code == 400
