# -*- coding: utf-8 -*-
"""test_profile_bundle.py —— §3.38 H-2 ⭐ Profile Bundle 分层测试

Harness 模式（packages/boot/app-boot/src/profile.ts，commit 47f9438）：
- Profile = 目录，含 profile.json（bundles 列表）+ user_overrides.yaml（用户 patch 层）
- Bundle = manifest 含 patch 声明（继承自 config/agents.json 等）
- 堆叠顺序（低→高 precedence）：bundle1 → bundle2 → ... → profile.json → user_overrides
- 稀疏 patch：用户只写想改的键，其余继承 defaults
"""
from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def profile_dir(tmp_path):
    """构造临时 profile 目录结构。"""
    (tmp_path / "profiles").mkdir()
    return tmp_path


def test_default_profile_exists():
    """默认 profile（standard）应存在且含 bundles 列表。"""
    from services.profile_bundle import list_profiles, load_profile
    profiles = list_profiles()
    assert "standard" in profiles, f"默认 standard profile 应存在，实际: {profiles}"
    prof = load_profile("standard")
    assert "bundles" in prof, "profile 应含 bundles 列表"
    assert prof.get("name") == "standard"


def test_bundle_layering_order(profile_dir):
    """bundle 堆叠：后声明的 bundle 覆盖先声明的（稀疏 patch）。"""
    from services.profile_bundle import compose_profile
    # 构造两个 bundle + profile
    (profile_dir / "bundles").mkdir(exist_ok=True)
    bundle_a = {"name": "bundle_a", "patch": {"agents": {"presenter": {"max_tokens": 100}}}}
    bundle_b = {"name": "bundle_b", "patch": {"agents": {"presenter": {"max_tokens": 200},
                                                         "planner": {"enabled": False}}}}
    profile_cfg = {"name": "test_profile", "bundles": ["bundle_a", "bundle_b"]}
    composed = compose_profile(profile_cfg, bundles={"bundle_a": bundle_a, "bundle_b": bundle_b})
    # bundle_b 后声明 → presenter.max_tokens = 200（覆盖 a）
    assert composed["agents"]["presenter"]["max_tokens"] == 200
    # bundle_b 独有键保留
    assert composed["agents"]["planner"]["enabled"] is False
    # bundle_a 独有键在 b 未覆盖时保留
    # （b 覆盖了 presenter.max_tokens，但 a 无其他独有键，此处验证合并深度）


def test_user_overrides_highest_precedence(profile_dir):
    """用户 patch 层优先级最高（覆盖所有 bundle）。"""
    from services.profile_bundle import compose_profile
    bundle_a = {"name": "bundle_a", "patch": {"agents": {"presenter": {"max_tokens": 100}}}}
    profile_cfg = {"name": "p", "bundles": ["bundle_a"]}
    user_patch = {"agents": {"presenter": {"max_tokens": 999}}}
    composed = compose_profile(profile_cfg, bundles={"bundle_a": bundle_a}, user_patch=user_patch)
    assert composed["agents"]["presenter"]["max_tokens"] == 999, "用户 patch 应最高优先"


def test_sparse_patch_preserves_defaults(profile_dir):
    """稀疏 patch：只改想改的键，其余继承 defaults（不整层覆盖）。"""
    from services.profile_bundle import compose_profile, DEFAULT_PROFILE_CFG
    # 只用默认配置 + 一个稀疏用户 patch
    user_patch = {"agents": {"presenter": {"max_tokens": 512}}}
    composed = compose_profile(DEFAULT_PROFILE_CFG, bundles={}, user_patch=user_patch)
    # presenter 被覆盖，其他 agent 保留默认
    assert composed["agents"]["presenter"]["max_tokens"] == 512
    assert composed["agents"]["planner"]["enabled"] is True  # 未被 patch 触及


def test_dump_config_tree():
    """配置树导出：dump 后含 profiles/bundles/agents 等完整树。"""
    from services.profile_bundle import dump_config_tree
    tree = dump_config_tree()
    assert "profiles" in tree, "配置树应含 profiles"
    assert "agents" in tree, "配置树应含 agents"
    assert "version" in tree


def test_dump_config_endpoint():
    """H-13：/api/admin/dump-config 端点返回配置树（server 集成）。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/admin/dump-config")
    assert r.status_code == 200, f"端点应 200，实际 {r.status_code}: {r.data[:200]}"
    data = r.get_json()
    assert "profiles" in data, "配置树应含 profiles"
    assert "bundles" in data
    assert "agents" in data
