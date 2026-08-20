# -*- coding: utf-8 -*-
"""§3.79 第 5 轮测试：间隔重复接线(srs_sm2) + PII 脱敏 + 严格队列坚持率（2026-08-20）。

覆盖：
  SRS 接线（services/srs_service + /api/srs/*）：
    - add_card → SM-2 初始调度（interval=1）→ due_cards 命中
    - review_card 答对 → interval 增长；答错 → 重置
    - 端点 /api/srs/status、/api/srs/review
  PII 脱敏（services/privacy）：
    - 手机号/邮箱/身份证/长数字串
  E1 严格队列（conversations.json 首末消息）
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import services.effect_metrics as em
import services.privacy as priv
import services.srs_service as srs


# ────────────────────────────────────────────
# SRS 间隔重复接线
# ────────────────────────────────────────────
def test_srs_add_and_due(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "_srs_path", lambda uid: str(tmp_path / f"{uid}_srs.json"))
    _c = srs.add_card("u_srs1", "导数", "math", quality=5)
    assert _c is not None
    assert _c["interval"] == 1  # SM-2 首次答对 → 1 天
    # SM-2 语义：学完当天不立即到期（明天复习）；复习反馈后才推进
    assert len(srs.due_cards("u_srs1")) == 0
    assert srs.card("u_srs1", "导数")["repetition"] == 1


def test_srs_review_growth_and_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "_srs_path", lambda uid: str(tmp_path / f"{uid}_srs.json"))
    srs.add_card("u_srs2", "量子纠缠", "physics", quality=5)
    # 答对（q=5）：repetition 2 → interval 6
    _c = srs.review_card("u_srs2", "量子纠缠", 5)
    assert _c["repetition"] == 2
    assert _c["interval"] == 6
    # 答错（q=0）：重置
    _c2 = srs.review_card("u_srs2", "量子纠缠", 0)
    assert _c2["repetition"] == 0
    assert _c2["interval"] == 0


def test_srs_persist_roundtrip(tmp_path, monkeypatch):
    """卡写入 users_data/<uid>/srs.json（原子写）。"""
    monkeypatch.setattr(srs, "_srs_path", lambda uid: str(tmp_path / f"{uid}_srs.json"))
    srs.add_card("u_srs3", "光合作用", "biology", quality=5)
    _p = str(tmp_path / "u_srs3_srs.json")
    assert os.path.isfile(_p)
    with open(_p, encoding="utf-8") as _fh:
        _d = json.load(_fh)
    assert "光合作用" in _d["cards"]


def test_srs_api_endpoints():
    """/api/srs/status + /api/srs/review。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/srs/status?learner_id=u_srs_api")
    assert r.status_code == 200
    body = r.get_json()
    assert "due" in body and "total" in body
    r2 = client.post("/api/srs/review", json={"learner_id": "u_srs_api",
                                              "concept": "不存在概念", "quality": 5})
    assert r2.status_code == 404  # 卡不存在


# ────────────────────────────────────────────
# PII 脱敏
# ────────────────────────────────────────────
def test_mask_pii_phone_email_idcard():
    _t = "联系方式 13812348000，邮箱 test123@example.com，证件 110101199003071234"
    _m = priv.mask_pii(_t)
    assert "138****8000" in _m
    assert "13812348000" not in _m
    assert "test***@example.com" in _m
    assert "1101**********1234" in _m


def test_mask_pii_long_number():
    _m = priv.mask_pii("银行卡号 6222021234567890123")
    assert "6222****0123" in _m
    assert "6222021234567890123" not in _m


def test_mask_pii_normal_text_unchanged():
    _t = "导数是一门重要的数学概念，我们来讲讲它的几何意义。"
    assert priv.mask_pii(_t) == _t


# ────────────────────────────────────────────
# E1 严格队列坚持率（conversations 首末消息）
# ────────────────────────────────────────────
def test_persistence_strict_cohort(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "_PROJ", str(tmp_path))
    _udir = tmp_path / "users_data"
    _day = 86400
    _now = time.time()
    # u_a：首活跃 20 天前（前段），末活跃 5 天前（后段）→ cohort ∩ retained
    _a = _udir / "u_a"
    _a.mkdir(parents=True)
    (_a / "profile.json").write_text("{}", encoding="utf-8")
    (_a / "conversations.json").write_text(json.dumps({
        "conversations": [{"messages": [
            {"role": "user", "content": "x", "ts": _now - 20 * _day},
            {"role": "assistant", "content": "y", "ts": _now - 5 * _day},
        ]}]}), encoding="utf-8")
    # u_b：首活跃 20 天前，末活跃 20 天前（未续用）→ cohort 但不 retained
    _b = _udir / "u_b"
    _b.mkdir(parents=True)
    (_b / "profile.json").write_text("{}", encoding="utf-8")
    (_b / "conversations.json").write_text(json.dumps({
        "conversations": [{"messages": [
            {"role": "user", "content": "x", "ts": _now - 20 * _day},
        ]}]}), encoding="utf-8")
    r = em.compute_persistence_rate(window_days=30)
    assert r["status"] == "strict_cohort"
    assert r["cohort"] == 2
    assert r["retained"] == 1
    assert r["value"] == 0.5
