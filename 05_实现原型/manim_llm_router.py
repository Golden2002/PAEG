# -*- coding: utf-8 -*-
"""manim_llm_router.py — Manim 模型路由（§3.111 ⭐ R4 用户修正）

用户要求：
1. **当前统一接入同一个模型**（不接多模型）
2. **保留接入不同模型的能力**（路由能力在，默认同一模型）
3. **模型配置外置**（便于扩展，不写死内部）——config 文件驱动

设计：
- 读取 config/manim_llm_config.json（外置配置，便于扩展）
- 默认 profile="default" → 走主项目 create_llm("auto")（统一同模型）
- 配置可声明不同 profile（如 "coder" 用 Qwen3Coder）——未来接入只需改配置
- 不改代码即可换模型（配置外置 ⭐）

用法：
    from manim_llm_router import get_manim_llm
    llm = get_manim_llm()  # 默认统一同模型（create_llm auto）
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

# 配置路径（外置，便于扩展）
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "config", "manim_llm_config.json")
# env 覆盖
_ENV_CONFIG = os.environ.get("MANIM_LLM_CONFIG", "")


def _load_config() -> dict:
    """读取外置配置（缺失 → 默认统一同模型）。"""
    path = _ENV_CONFIG or _CONFIG_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # 默认：统一同模型（无独立 coder 模型）
    return {
        "default_profile": "default",
        "profiles": {
            "default": {
                "provider": "auto",      # 走主项目 create_llm("auto")——统一同模型
                "model": None,           # None = 用 provider 默认
                "note": "统一使用主项目当前模型（DeepSeek 等）",
            },
        },
    }


def get_llm_config(profile: Optional[str] = None) -> dict:
    """获取某 profile 的模型配置（默认 default_profile）。"""
    cfg = _load_config()
    profile = profile or cfg.get("default_profile", "default")
    profiles = cfg.get("profiles", {})
    return profiles.get(profile, profiles.get("default", {}))


def get_manim_llm(profile: Optional[str] = None):
    """获取 Manim 使用的 LLM（R4 ⭐）。

    - 默认（无 profile / default）：走主项目 create_llm("auto")——**统一同模型**
    - 配置了其他 profile：按配置创建（未来接 Qwen3Coder 只需改 config，不改代码）
    """
    cfg = get_llm_config(profile)
    provider = cfg.get("provider", "auto")
    model = cfg.get("model")
    try:
        from llm_adapter import create_llm
        return create_llm(provider, model)
    except Exception:
        # 兜底：auto
        try:
            from llm_adapter import create_llm
            return create_llm("auto")
        except Exception:
            return None


def available_profiles() -> list:
    """配置外置的可用模型 profile（供 MCP 自省）。"""
    cfg = _load_config()
    return list(cfg.get("profiles", {}).keys())


def config_path() -> str:
    """配置路径（供文档/健康检查）。"""
    return _ENV_CONFIG or _CONFIG_PATH


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("可用 profiles:", available_profiles())
    print("配置路径:", config_path())
    print("默认配置:", get_llm_config())
