# -*- coding: utf-8 -*-
"""
v0.27 综合测试盲区修复 ⭐ 注册用户画像字段完整性

反思：综合测试未测出 /api/profile/<u_id> 漏传 subjects_mastery 的 bug——
本测试覆盖：注册用户（u 前缀）profile GET 返回的每个字段与 UserStore 一致。
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _get_test_user():
    """找一个有数据的注册用户（u 前缀）。"""
    from user_store import UserStore
    us = UserStore()
    data = json.load(open(us.data_path, encoding="utf-8"))
    for ident, u in data.get("users", {}).items():
        uid = u.get("user_id", "")
        if uid.startswith("u") and (u.get("learner") or {}).get("subjects_mastery"):
            return uid
    return None


def test_profile_returns_full_fields_for_registered_user():
    """/api/profile/<u_id> 应返回 subjects_mastery（此前漏传 → 空）。"""
    uid = _get_test_user()
    if not uid:
        print("[SKIP] 无带掌握度的注册用户，跳过（用匿名测试保证链路）")
        return
    from server import app
    client = app.test_client()
    r = client.get(f"/api/profile/{uid}")
    assert r.status_code == 200, f"profile GET 失败: {r.status_code}"
    body = r.get_json()
    # 核心断言：subjects_mastery 必须非空（注册用户有掌握度记录时）
    mastery = body.get("subjects_mastery") or {}
    from user_store import UserStore
    ld = UserStore().load_learner(uid) or {}
    stored = ld.get("subjects_mastery") or {}
    assert mastery, f"profile 漏传 subjects_mastery（UserStore 有 {len(stored)} 条）"
    assert set(mastery.keys()) == set(stored.keys()), \
        f"掌握度不一致: profile={list(mastery.keys())} store={list(stored.keys())}"
    # 其他字段完整性
    for field in ["id", "nickname", "grade_level", "self_description"]:
        assert field in body, f"profile 缺字段 {field}"
    print(f"[OK] profile 字段完整（uid={uid}, mastery={list(mastery.keys())}）")


def test_profile_refresh_restores_mastery():
    """模拟刷新：SESSIONS 清空后（重启场景）profile 仍返回掌握度。"""
    uid = _get_test_user()
    if not uid:
        print("[SKIP] 无注册用户，跳过")
        return
    from server import app
    import server as srv
    # 清掉 SESSIONS 里的 learner（模拟刷新/重启）
    saved = srv.SESSIONS.pop(f"learner_{uid}", None)
    try:
        client = app.test_client()
        r = client.get(f"/api/profile/{uid}")
        body = r.get_json()
        mastery = body.get("subjects_mastery") or {}
        assert mastery, "刷新后 subjects_mastery 应为非空（从 UserStore 恢复）"
        print(f"[OK] 刷新恢复掌握度（{list(mastery.keys())}）")
    finally:
        if saved:
            srv.SESSIONS[f"learner_{uid}"] = saved
