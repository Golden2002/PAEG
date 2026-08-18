# -*- coding: utf-8 -*-
"""
PAEG 测试隔离 conftest（P0-1 根治测试状态污染）

设计目标：
1. 隔离测试数据目录（tmp_path + 用户数据文件 users.json / users_data/<uid>/）——
   避免不同测试共享同一份真实用户数据造成的污染。
2. 防御性恢复模块级 monkey-patch —— 某些测试模块在 import 时直接重写
   ``subagents._safe_chat`` / ``subagents.Individuality``，这些重写会污染
   所有后续测试。用 autouse fixture 在每个测试前把原始符号恢复回来。
3. 防御性清空 ``meta_router._INTENT_CACHE`` 系列缓存（保持原 dict 对象身份，
   避免破坏其它 fixture 已经 import 的同名引用）。

公开 fixture：
- ``tmp_data_dir``：每个测试拿独立 tmp 目录做用户数据根目录，配合
  ``tmp_users_json`` / ``tmp_users_data`` 使用。
- ``isolated_subagents``：显式 fixture，恢复 subagents 关键符号。

autouse fixture：
- ``_restore_module_globals``：恢复 subagents 关键符号 + 还原 stdout。
- ``_clean_meta_caches``：清空 meta_router 三个意图缓存（保持对象身份）。
- ``_snapshot_real_users_json``：测试结束后还原真实 users.json（兜底）。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# v0.69+：确保 05_实现原型 根目录在 sys.path（从任意目录跑 pytest 均可 import 项目模块）
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)


# ────────────────────────────────────────────────────────────
# 关键：在 pytest 开始收集 test_* 前，先把"原始"模块符号快照下来
# ────────────────────────────────────────────────────────────
# 注：conftest.py 在 test_*.py 之前被加载，所以这里能拿到未被污染的版本
import subagents as _sa
import meta_router as _mr
import user_store as _us

# 1) subagents：保存原始 _safe_chat / Individuality / _is_leaky_reply
_ORIG_SAFE_CHAT = _sa._safe_chat
_ORIG_INDIVIDUALITY = _sa.Individuality
_ORIG_IS_LEAKY = _sa._is_leaky_reply

# 2) 进程级资源：保存原始 stdout（test_individuality_v023.py 第 10 行
#    会调 ``sys.stdout.reconfigure(encoding="utf-8")``，需要恢复）
_ORIG_STDOUT = sys.stdout
_ORIG___STDOUT__ = sys.__stdout__

# 3) meta_router 三个意图缓存（保存对象身份，autouse 时只 .clear()）
_INTENT_CACHE_OBJ = _mr._INTENT_CACHE
_IS_INTENT_CACHE_OBJ = _mr._IS_INTENT_CACHE
_INTENT_CACHE_V2_OBJ = _mr._INTENT_CACHE_V2

# 4) 真实数据目录（用于"快照-还原"兜底）
_PROJ_ROOT = os.path.dirname(os.path.abspath(__file__))  # tests/conftest.py → tests/
_PROJ_ROOT = os.path.dirname(_PROJ_ROOT)  # → 05_实现原型/
_REAL_USERS_JSON = os.path.join(_PROJ_ROOT, "users.json")


def _snapshot_real_data() -> dict:
    """快照真实 users.json 内容（仅快照，不复制大目录）。"""
    if not os.path.isfile(_REAL_USERS_JSON):
        return {"users": {}, "next_id": 1}
    try:
        with open(_REAL_USERS_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}, "next_id": 1}


def _restore_real_data(snapshot: dict) -> None:
    """把真实 users.json 还原成快照（保证测试不污染生产数据）。"""
    try:
        with open(_REAL_USERS_JSON, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ────────────────────────────────────────────────────────────
# Fixture：临时数据目录隔离（核心）
# ────────────────────────────────────────────────────────────
@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """每个测试拿独立的 tmp 目录作为 UserStore 的 data_path。

    返回 dict：
    - ``root``：tmp 根目录（Path）
    - ``users_json``：tmp/users.json 路径（传给 ``UserStore(data_path=...)``）
    - ``users_data``：tmp/users_data 目录
    - ``store``：已绑定到 tmp users.json 的 ``UserStore()`` 实例

    同时通过 ``monkeypatch.setattr`` 把 ``user_store.user_data_paths`` 重定向
    到 tmp 目录，让 ``users_data/<uid>/`` 也写到 tmp 而不是真实生产目录。
    """
    root = Path(tmp_path) / "paeg_data"
    users_json = root / "users.json"
    users_data = root / "users_data"
    root.mkdir(parents=True, exist_ok=True)
    users_data.mkdir(parents=True, exist_ok=True)
    # 初始化 users.json（空模板）
    users_json.write_text(
        json.dumps({"users": {}, "next_id": 1}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    # Monkeypatch：让 ``user_data_paths(uid)`` 返回 tmp 里的路径。
    def _patched_user_data_paths(uid: str) -> dict:
        u = str(users_data / uid)
        return {
            "profile": os.path.join(u, "profile.json"),
            "history": os.path.join(u, "history.jsonl"),
            "notes": os.path.join(u, "notes"),
            "self_description": os.path.join(u, "self_description.json"),
            "feedback": os.path.join(u, "feedback"),
        }

    monkeypatch.setattr(_us, "user_data_paths", _patched_user_data_paths)

    # 直接给一个绑定到 tmp 的 UserStore 实例（最常用入口）
    store = _us.UserStore(data_path=str(users_json))

    return {
        "root": root,
        "users_json": users_json,
        "users_data": users_data,
        "store": store,
    }


# ────────────────────────────────────────────────────────────
# Fixture：autouse 防御性恢复（关键）
# ────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _restore_module_globals(monkeypatch):
    """每个测试前自动恢复被其他测试模块污染的全局符号。

    覆盖：
    - ``subagents._safe_chat`` → 原始实现
    - ``subagents.Individuality`` → 原始类
    - ``subagents._is_leaky_reply`` → 原始实现
    - ``sys.stdout`` / ``sys.__stdout__`` → 原始（pytest capsys 需要）
    """
    # 1) subagents：恢复 _safe_chat / Individuality / _is_leaky_reply
    monkeypatch.setattr(_sa, "_safe_chat", _ORIG_SAFE_CHAT)
    monkeypatch.setattr(_sa, "Individuality", _ORIG_INDIVIDUALITY)
    monkeypatch.setattr(_sa, "_is_leaky_reply", _ORIG_IS_LEAKY)

    # 2) sys.stdout：恢复（test_individuality_v023.py 第 10 行的
    #    ``sys.stdout.reconfigure(encoding="utf-8")`` 会让 capsys 在后续测试失灵）
    monkeypatch.setattr(sys, "stdout", _ORIG_STDOUT)
    monkeypatch.setattr(sys, "__stdout__", _ORIG___STDOUT__)

    yield


@pytest.fixture(autouse=True)
def _clean_meta_caches():
    """每个测试前清空 meta_router 三个意图缓存（保持对象身份不变）。

    重要：不能用 ``monkeypatch.setattr(_mr, "_INTENT_CACHE", {})`` 替换对象，
    因为 test_routing_v024.py 在模块顶部已经 ``from meta_router import _INTENT_CACHE``
    拿到了原对象引用；替换对象会让 test 的 local 名字指向旧 dict，导致
    ``_INTENT_CACHE.clear()`` 与 ``is_teaching_intent()`` 内部访问的不是同一个 dict，
    缓存清理失败。
    """
    _INTENT_CACHE_OBJ.clear()
    _IS_INTENT_CACHE_OBJ.clear()
    _INTENT_CACHE_V2_OBJ.clear()
    yield


@pytest.fixture(autouse=True)
def _snapshot_real_users_json():
    """每个测试结束后把真实 users.json 还原成测试开始前的内容（兜底）。"""
    snapshot = _snapshot_real_data()
    yield
    _restore_real_data(snapshot)


# ────────────────────────────────────────────────────────────
# Fixture：明确告知用户怎么用
# ────────────────────────────────────────────────────────────
@pytest.fixture
def isolated_subagents(monkeypatch):
    """显式 fixture：把 subagents 的关键符号恢复到原始（防止被 stub 顶替）。

    用法（在测试里 ``def test_xxx(isolated_subagents):``）：
        自动生效，等价于 ``_restore_module_globals``。
    """
    monkeypatch.setattr(_sa, "_safe_chat", _ORIG_SAFE_CHAT)
    monkeypatch.setattr(_sa, "Individuality", _ORIG_INDIVIDUALITY)
    monkeypatch.setattr(_sa, "_is_leaky_reply", _ORIG_IS_LEAKY)
    return _sa
