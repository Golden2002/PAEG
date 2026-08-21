# -*- coding: utf-8 -*-
"""§3.79 Round 7 ⭐ D9 admin 远程模块切换测试（kill switch 可执行化）。

覆盖：
  - GET /api/admin/modules：模块门控状态（kill switch 审计视图）
  - POST /api/admin/modules：远程切换（单模块 + 批量），原子写 paeg_modules.json
  - 热重载生效：切换后 module_registry.is_enabled 立即反映新状态（无需重启）
  - 审计事件：切换写 observability（module/toggle）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from server import app

client = app.test_client()

_CFG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "paeg_modules.json")

# §3.79 Round 8 ⭐ admin 权限保护：写操作需 PAEG_ADMIN_TOKEN
_ADMIN_TOKEN = "e2e_test_admin_token_round8"


@pytest.fixture(autouse=True)
def _admin_token_env(monkeypatch):
    """测试期间设置 PAEG_ADMIN_TOKEN（POST 鉴权用）。"""
    monkeypatch.setenv("PAEG_ADMIN_TOKEN", _ADMIN_TOKEN)
    yield


def _post_modules(payload):
    return client.post("/api/admin/modules", json=payload,
                       headers={"X-Admin-Token": _ADMIN_TOKEN})


@pytest.fixture()
def backup_cfg():
    """备份/恢复 paeg_modules.json（防测试污染真实门控）。"""
    _orig = None
    if os.path.exists(_CFG):
        with open(_CFG, encoding="utf-8") as f:
            _orig = f.read()
    yield
    if _orig is not None:
        with open(_CFG, "w", encoding="utf-8") as f:
            f.write(_orig)


def test_modules_status(backup_cfg):
    """GET 返回全部模块 enabled 状态。"""
    r = client.get("/api/admin/modules")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    mods = body.get("modules") or {}
    assert "teach" in mods and "chat" in mods
    assert isinstance(mods["teach"], dict) and "enabled" in mods["teach"]


def test_modules_toggle_single(backup_cfg):
    """POST 单模块切换 → 热重载生效 + 原子写。"""
    # 先读当前状态
    st = client.get("/api/admin/modules").get_json()["modules"]
    cur = st["voice"]["enabled"]
    r = _post_modules({"module": "voice", "enabled": not cur})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    body = r.get_json()
    assert body.get("ok") is True
    assert body["applied"][0]["module"] == "voice"
    assert body["applied"][0]["to"] == (not cur)
    # 热重载生效（module_registry 每次读文件）
    from module_registry import is_enabled
    assert is_enabled("voice") == (not cur), "切换后 is_enabled 应即时反映"
    # 文件已原子写
    with open(_CFG, encoding="utf-8") as f:
        data = json.load(f)
    assert data["voice"] == (not cur)


def test_modules_toggle_batch(backup_cfg):
    """POST 批量切换。"""
    r = _post_modules({"modules": {"weather": False, "history": True}})
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["applied"]) == 2
    from module_registry import is_enabled
    assert is_enabled("weather") is False
    assert is_enabled("history") is True


def test_modules_toggle_audit_event(backup_cfg):
    """切换写审计事件（module/toggle 落盘 JSONL）。"""
    import io
    from observability import _EVENTS_FILE
    # 记录切换前文件大小
    _before = os.path.getsize(_EVENTS_FILE) if os.path.exists(_EVENTS_FILE) else 0
    _post_modules({"module": "mcp", "enabled": False, "operator": "e2e_test"})
    # 读取切换后追加的行
    _lines = []
    if os.path.exists(_EVENTS_FILE):
        with io.open(_EVENTS_FILE, encoding="utf-8") as f:
            _lines = [l for l in f.readlines() if "module/toggle" in l]
    assert _lines, "module/toggle 审计事件未落盘"
    last = json.loads(_lines[-1])
    assert last.get("type") == "module/toggle"
    assert last.get("data", {}).get("module") == "mcp"


def test_modules_toggle_invalid(backup_cfg):
    """无参数 → 400（契约保护，带 token）。"""
    r = _post_modules({})
    assert r.status_code == 400


# ────────────────────────────────────────────
# §3.79 Round 8 ⭐ admin 权限保护（写操作需 token）
# ────────────────────────────────────────────
def test_modules_post_requires_token(backup_cfg, monkeypatch):
    """无 token → 401（安全默认：未配置 PAEG_ADMIN_TOKEN 时写操作禁用）。"""
    monkeypatch.delenv("PAEG_ADMIN_TOKEN", raising=False)
    r = client.post("/api/admin/modules", json={"module": "voice", "enabled": False})
    assert r.status_code == 401
    body = r.get_json()
    assert "PAEG_ADMIN_TOKEN" in body.get("error", "")


def test_modules_post_wrong_token(backup_cfg):
    """错误 token → 401。"""
    r = client.post("/api/admin/modules", json={"module": "voice", "enabled": False},
                    headers={"X-Admin-Token": "wrong_token"})
    assert r.status_code == 401


def test_modules_post_correct_token(backup_cfg):
    """正确 token → 200（X-Admin-Token 头）。"""
    r = _post_modules({"module": "voice", "enabled": False})
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


def test_modules_get_open(backup_cfg, monkeypatch):
    """GET 状态无需 token（只读审计视图开放）。"""
    monkeypatch.delenv("PAEG_ADMIN_TOKEN", raising=False)
    r = client.get("/api/admin/modules")
    assert r.status_code == 200
