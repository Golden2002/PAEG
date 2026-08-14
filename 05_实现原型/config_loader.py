# -*- coding: utf-8 -*-
"""PAEG 配置化加载器（v0.71 §3.32 ⭐ sub agent 模型配置化 + 面向用户定制）

借鉴 opencode/codex/DeepSeek Harness/Claude Code 四项目最佳实践：
- **三层合并**（代码内置 defaults → 用户全局 ~/.paeg/agents.json → 项目 config/agents.json）
- **稀疏 patch**（用户只写想改的键，其余继承 defaults）
- **变量替换**（{env:KEY|默认} 环境变量 / {file:path} 文件内容）
- **per-subagent 模型注入**（每 subagent 可配 model/provider/temperature/max_tokens/thinking_level）

用法：
    from config_loader import load_agents_config
    cfg = load_agents_config()            # 合并后配置（AgentConfigs）
    llm = cfg.create_llm_for("presenter") # 为指定 subagent 创建 LLM（create_llm 工厂）

默认配置：本文件内置 DEFAULTS（与现有 paeg.py 行为一致），用户/项目可覆盖。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

# ─────────────────────────────────────
# 路径
# ─────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_CONFIG = os.path.join(_BASE_DIR, "config", "agents.json")
_USER_CONFIG = os.path.join(os.path.expanduser("~"), ".paeg", "agents.json")


# ─────────────────────────────────────
# 默认配置（与现有 paeg.py 行为一致——全部共用 model_api 的回退）
# ─────────────────────────────────────

DEFAULTS: dict = {
    "version": 1,
    "global": {
        "default_provider": "auto",
        "default_model": None,
    },
    "agents": {
        "diagnostor": {"provider": "auto", "model": None, "temperature": None,
                       "max_tokens": 200, "thinking_level": "B", "enabled": True},
        "planner": {"provider": "auto", "model": None, "temperature": None,
                    "max_tokens": None, "thinking_level": "OFF", "enabled": True},
        "presenter": {"provider": "auto", "model": None, "temperature": None,
                      "max_tokens": 512, "thinking_level": "A", "enabled": True},
        "evaluator": {"provider": "auto", "model": None, "temperature": None,
                      "max_tokens": None, "thinking_level": "OFF", "enabled": True},
        "adapter": {"provider": "auto", "model": None, "temperature": None,
                    "max_tokens": None, "thinking_level": "OFF", "enabled": True},
        "answer_solver": {"provider": "auto", "model": None, "temperature": None,
                          "max_tokens": 1800, "thinking_level": "A", "enabled": True},
        "affection_supportor": {"provider": "auto", "model": None, "temperature": None,
                                "max_tokens": 900, "thinking_level": "A", "enabled": True},
        "self_update_agent": {"provider": "auto", "model": None, "temperature": None,
                              "max_tokens": 1500, "thinking_level": "A", "enabled": True},
        "individuality": {"provider": "auto", "model": None, "temperature": None,
                          "max_tokens": 400, "thinking_level": "B", "enabled": True},
        "resource_librarian": {"provider": "auto", "model": None, "temperature": None,
                               "max_tokens": 800, "thinking_level": "OFF", "enabled": True},
    },
}


# ─────────────────────────────────────
# 变量替换
# ─────────────────────────────────────

_ENV_RE = re.compile(r"\{env:([^}|]+)(?:\|([^}]*))?\}")
_FILE_RE = re.compile(r"\{file:([^}]+)\}")


def _resolve_vars(value: Any) -> Any:
    """递归替换 {env:KEY|默认} 与 {file:path}。"""
    if isinstance(value, str):
        def _env_sub(m):
            key, default = m.group(1), m.group(2)
            return os.environ.get(key, default or "")
        value = _ENV_RE.sub(_env_sub, value)

        def _file_sub(m):
            p = m.group(1)
            if os.path.isabs(p):
                fp = p
            else:
                fp = os.path.join(_BASE_DIR, p)
            try:
                with open(fp, encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                return ""
        value = _FILE_RE.sub(_file_sub, value)
        return value
    if isinstance(value, dict):
        return {k: _resolve_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_vars(v) for v in value]
    return value


# ─────────────────────────────────────
# 深层合并（dict 递归合并；list/标量 上层覆盖下层）
# ─────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ─────────────────────────────────────
# 加载（三层合并 + 变量替换）
# ─────────────────────────────────────

def load_agents_config(project_path: Optional[str] = None,
                       user_path: Optional[str] = None) -> dict:
    """加载并合并三层配置（defaults → user → project）。返回解析后 dict。"""
    merged = _deep_merge({}, DEFAULTS)

    # Layer 2: 用户全局
    up = user_path or _USER_CONFIG
    if os.path.exists(up):
        try:
            with open(up, encoding="utf-8") as f:
                merged = _deep_merge(merged, json.load(f))
        except Exception as e:
            print(f"[config_loader] 用户配置加载失败（忽略）: {e}")

    # Layer 3: 项目级
    pp = project_path or _PROJECT_CONFIG
    if os.path.exists(pp):
        try:
            with open(pp, encoding="utf-8") as f:
                merged = _deep_merge(merged, json.load(f))
        except Exception as e:
            print(f"[config_loader] 项目配置加载失败（忽略）: {e}")

    # 变量替换
    merged = _resolve_vars(merged)
    return merged


# ─────────────────────────────────────
# per-subagent LLM 创建
# ─────────────────────────────────────

def create_llm_for(name: str, config: Optional[dict] = None,
                   fallback: Any = None) -> Any:
    """为指定 subagent 创建 LLM（按配置 provider/model）。

    Args:
        name: subagent 名（diagnostor/presenter/...）
        config: 合并后配置（load_agents_config 结果）；None 则自动加载
        fallback: 无配置/禁用时回退的 LLM 实例（默认 None → create_llm("auto")）

    Returns:
        LLM 实例（AdapterLLM / MockModelAPI / fallback）
    """
    if config is None:
        config = load_agents_config()
    agents = config.get("agents", {})
    agent_cfg = agents.get(name) or {}
    if not agent_cfg.get("enabled", True):
        return fallback
    provider = agent_cfg.get("provider") or config.get("global", {}).get("default_provider", "auto")
    model = agent_cfg.get("model") or config.get("global", {}).get("default_model")
    try:
        from llm_adapter import create_llm
        return create_llm(provider=provider, model=model)
    except Exception as e:
        print(f"[config_loader] create_llm_for({name}) 失败: {e}")
        return fallback


def get_agent_config(name: str, config: Optional[dict] = None) -> dict:
    """获取单个 subagent 配置（合并后，含 global 默认）。"""
    if config is None:
        config = load_agents_config()
    agent_cfg = dict(config.get("agents", {}).get(name) or {})
    agent_cfg.setdefault("provider", config.get("global", {}).get("default_provider", "auto"))
    agent_cfg.setdefault("model", config.get("global", {}).get("default_model"))
    return agent_cfg


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    cfg = load_agents_config()
    print("=== 合并后配置 agents 键 ===")
    print(list(cfg.get("agents", {}).keys()))
    print("\n=== presenter 配置 ===")
    import json as _j
    print(_j.dumps(get_agent_config("presenter", cfg), ensure_ascii=False, indent=1))
    print("\n=== create_llm_for(presenter) ===")
    llm = create_llm_for("presenter", cfg)
    print(f"type={type(llm).__name__} name={getattr(llm, 'name', '?')}")
