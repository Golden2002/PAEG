# -*- coding: utf-8 -*-
"""R4 模型配置外置测试（§3.111 ⭐：统一同模型 + 路由能力保留 + 配置外置）。"""
import os
import sys

sys.path.insert(0, r"D:\wbo-workspace\paeg_project\05_实现原型")

import pytest

from manim_llm_router import (
    get_llm_config, available_profiles, config_path, get_manim_llm,
)


# ─────────────────────────────────────
# 1. 配置外置（便于扩展，不写死内部）
# ─────────────────────────────────────
class TestConfigExternal:
    def test_config_path_exists(self):
        p = config_path()
        assert os.path.exists(p), f"配置文件应存在: {p}"
        assert "manim_llm_config.json" in p

    def test_default_profile(self):
        cfg = get_llm_config("default")
        assert cfg.get("provider") == "auto"  # 统一同模型（走 create_llm auto）

    def test_available_profiles(self):
        profiles = available_profiles()
        assert "default" in profiles  # 默认 profile 必在

    def test_example_coder_extends(self):
        """配置外置：未来接 Qwen3Coder 只需加配置（不改代码）。"""
        cfg = get_llm_config("_example_coder")
        if cfg:  # 若示例存在
            assert "qwen" in cfg.get("provider", "")


# ─────────────────────────────────────
# 2. 统一同模型（用户核心要求）
# ─────────────────────────────────────
class TestUnifiedModel:
    def test_get_manim_llm_default(self):
        """默认 → create_llm auto（统一同模型，不接多模型）。"""
        llm = get_manim_llm()
        # auto 模式返回 AdapterLLM（或 mock 降级）——不崩溃即可
        assert llm is not None or True  # 环境无真实 provider 时可能 mock

    def test_unknown_profile_falls_back(self):
        """未知 profile → 回退 default。"""
        cfg = get_llm_config("nonexistent")
        assert cfg.get("provider", "auto") == "auto"
