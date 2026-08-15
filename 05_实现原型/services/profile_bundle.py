# -*- coding: utf-8 -*-
"""services/profile_bundle.py —— §3.38 H-2 ⭐ Profile Bundle 分层（v1.1.3）

Harness 模式（packages/boot/app-boot/src/profile.ts，commit 47f9438）：
- Profile = 目录（paeg_profiles/<name>/），含 profile.json（bundles 列表）+ user_overrides（用户 patch 层）
- Bundle = manifest 含 patch 声明（继承自默认配置）
- 堆叠顺序（低→高 precedence）：默认 → bundle1 → bundle2 → ... → profile.json → user_overrides
- 稀疏 patch：用户只写想改的键，其余继承 defaults（深度合并，非整层覆盖）
- dump_config_tree：对齐 dsh --dump-config（完整可 patch 配置树导出）

场景：教学 preset（standard 默认 / exam 考试 / weil 薇依人格）——教师一键切场景，
不改代码；学生只覆 user_overrides 层。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

# §3.42 W12 ⭐ LRU+TTL 缓存接入（行为透明——相同 profile_name 返回相同结果）
try:
    from infra.cache import cached as _cached
except Exception:  # noqa: BLE001 — infra.cache 不可用时回退到无缓存版本
    _cached = None  # type: ignore[assignment]


def _make_cached_get_effective_config():
    """构造带缓存的 get_effective_config（infra.cache 不可用时回退到直传）。"""
    def _impl(profile_name: str = "standard") -> dict:
        prof = load_profile(profile_name)
        bundles = load_bundles(prof.get("bundles", []))
        user_patch = load_user_patch()
        return compose_profile(prof, bundles=bundles, user_patch=user_patch)
    if _cached is None:
        return _impl
    # §3.42 W12：profile_bundle 命名空间，TTL 5 分钟（profile 切换稀疏）
    return _cached(namespace="profile_bundle", ttl=300.0)(_impl)


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROFILES_DIR = os.path.join(_BASE_DIR, "paeg_profiles")

# 默认 profile 清单（教学场景预设）
DEFAULT_PROFILE_CFG: dict = {
    "version": 1,
    "name": "standard",
    "description": "标准教学预设（默认）",
    "bundles": [
        "base",
    ],
}

# 内置 bundle 声明（paeg_profiles/bundles/ 目录可覆盖）
_BUILTIN_BUNDLES: Dict[str, dict] = {
    "base": {"name": "base", "patch": {}},  # 基座：无额外 patch，继承全部默认
    "exam": {"name": "exam", "patch": {
        "permission": {"preset": "exam"},
    }},
    "weil": {"name": "weil", "patch": {
        "global": {"default_style": "weil"},
    }},
}

# 用户 patch 层（全局）
_USER_PATCH_PATH = os.path.join(_BASE_DIR, "config", "user_overrides.json")


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并：override 的键覆盖 base，未触及的键保留（稀疏 patch 语义）。"""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def list_profiles() -> List[str]:
    """列出可用 profile（内置 standard + paeg_profiles/ 目录中的自定义）。"""
    names = ["standard"]
    try:
        if os.path.isdir(_PROFILES_DIR):
            for d in sorted(os.listdir(_PROFILES_DIR)):
                if os.path.isdir(os.path.join(_PROFILES_DIR, d)) and not d.startswith("."):
                    names.append(d)
    except Exception:
        pass
    return names


def load_profile(name: str) -> dict:
    """加载 profile 配置（内置 standard 或 paeg_profiles/<name>/profile.json）。"""
    if name == "standard" or not name:
        return dict(DEFAULT_PROFILE_CFG)
    path = os.path.join(_PROFILES_DIR, name, "profile.json")
    if not os.path.isfile(path):
        return {"name": name, "bundles": [], "error": f"profile 不存在: {name}"}
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.setdefault("name", name)
        cfg.setdefault("bundles", [])
        return cfg
    except Exception as e:
        return {"name": name, "bundles": [], "error": str(e)}


def load_bundles(bundle_names: List[str]) -> Dict[str, dict]:
    """加载 bundle 声明（内置 + paeg_profiles/bundles/<name>.json 覆盖）。"""
    out: Dict[str, dict] = {}
    for name in bundle_names:
        # 1. 目录覆盖（项目可自定义 bundle）
        path = os.path.join(_PROFILES_DIR, "bundles", f"{name}.json")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    out[name] = json.load(f)
                continue
            except Exception:
                pass
        # 2. 内置
        if name in _BUILTIN_BUNDLES:
            out[name] = dict(_BUILTIN_BUNDLES[name])
    return out


def load_user_patch() -> dict:
    """加载用户 patch 层（config/user_overrides.json，稀疏覆盖）。"""
    if not os.path.isfile(_USER_PATCH_PATH):
        return {}
    try:
        with open(_USER_PATCH_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def compose_profile(profile_cfg: dict, bundles: Optional[Dict[str, dict]] = None,
                    user_patch: Optional[dict] = None) -> dict:
    """按堆叠顺序合并（低→高 precedence）：默认 → bundles → profile → user_patch。

    Args:
        profile_cfg: profile 配置（含 bundles 列表）
        bundles: bundle 声明 dict（name → {patch}）
        user_patch: 用户 patch 层（最高优先）

    Returns:
        合并后的完整配置树
    """
    merged: dict = {"version": 1, "profile": profile_cfg.get("name", "standard")}
    # 1. 默认配置基座（来自 config_loader DEFAULTS 或内置）
    try:
        from config_loader import DEFAULTS as _defaults
        merged = _deep_merge(merged, json.loads(json.dumps(_defaults)))
    except Exception:
        pass
    # 2. bundle 层（按声明顺序堆叠）
    for bname in profile_cfg.get("bundles", []):
        b = (bundles or {}).get(bname) or {}
        if b.get("patch"):
            merged = _deep_merge(merged, b["patch"])
    # 3. profile 自有覆盖
    if profile_cfg.get("patch"):
        merged = _deep_merge(merged, profile_cfg["patch"])
    # 4. 用户 patch 层（最高优先）
    if user_patch:
        merged = _deep_merge(merged, user_patch)
    return merged


# §3.42 W12 ⭐ get_effective_config 接入 LRU+TTL 缓存
get_effective_config = _make_cached_get_effective_config()


def get_effective_config_uncached(profile_name: str = "standard") -> dict:
    """get_effective_config 的无缓存版本（测试 / 调试 / 配置热重载旁路用）。

    与 get_effective_config 行为完全一致，只是不走缓存——便于在 invalidate 后
    强制重新计算，或在单测里做"无缓存基线"对照（性能测试）。
    """
    prof = load_profile(profile_name)
    bundles = load_bundles(prof.get("bundles", []))
    user_patch = load_user_patch()
    return compose_profile(prof, bundles=bundles, user_patch=user_patch)


def dump_config_tree() -> dict:
    """H-13 ⭐ 配置树导出（对齐 dsh --dump-config）：完整可 patch 配置树。"""
    tree: dict = {
        "version": 1,
        "profiles": list_profiles(),
        "bundles": {k: v for k, v in _BUILTIN_BUNDLES.items()},
        "user_patch": load_user_patch(),
    }
    try:
        from config_loader import DEFAULTS
        tree["agents"] = DEFAULTS.get("agents", {})
    except Exception:
        tree["agents"] = {}
    try:
        from config_hub import get_hub
        hub = get_hub()
        tree["tools"] = {
            "total": len(hub.get_all_tool_defs()),
            "mcp": hub.list_all().get("mcp", {}),
        }
    except Exception:
        tree["tools"] = {}
    # 当前生效配置（standard）
    eff = get_effective_config("standard")
    tree["effective"] = {"profile": eff.get("profile", "standard")}
    if eff.get("permission"):
        tree["effective"]["permission"] = eff["permission"]
    return tree


# ─── 全局单例 ───
_service: Optional["ProfileBundleService"] = None
_service_lock = threading.Lock()


class ProfileBundleService:
    """Profile Bundle 服务：切换 profile / 导出配置树。"""

    def __init__(self):
        self._current = "standard"
        self._lock = threading.RLock()

    def set_profile(self, name: str) -> bool:
        if name not in list_profiles():
            return False
        with self._lock:
            self._current = name
        return True

    def get_profile(self) -> str:
        with self._lock:
            return self._current

    def effective(self) -> dict:
        return get_effective_config(self.get_profile())


def get_profile_service() -> ProfileBundleService:
    global _service
    with _service_lock:
        if _service is None:
            _service = ProfileBundleService()
        return _service


__all__ = [
    "ProfileBundleService", "get_profile_service", "get_effective_config",
    "get_effective_config_uncached",
    "list_profiles", "load_profile", "load_bundles", "load_user_patch",
    "compose_profile", "dump_config_tree", "DEFAULT_PROFILE_CFG",
]
