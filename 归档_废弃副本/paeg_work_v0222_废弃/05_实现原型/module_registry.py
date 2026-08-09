# -*- coding: utf-8 -*-
"""
PAEG 功能模块注册机制（v0.21 ⭐ 模块化元技能）

借鉴 opencode 的插件加载 + Codex 的模块化设计：
- 每个功能模块（天气/知识导图/MCP/自我更新/闲聊/找答案）可独立启用/禁用
- server 启动时按配置挂载路由
- 上架 = 启用配置；下架 = 禁用配置（不改代码）

配置：paeg_modules.json（JSONC 风格，支持 {env:VAR}）

用法：
    from module_registry import MODULES, is_enabled, register_module
    if is_enabled("weather"):
        from weather_routes import weather_bp
        app.register_blueprint(weather_bp)
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

# 模块清单（id → 元信息）
MODULE_CATALOG: Dict[str, Dict[str, Any]] = {
    "teach":    {"desc": "学科教学（核心）", "default": True},
    "chat":     {"desc": "闲聊（核心）", "default": True},
    "answer":   {"desc": "找答案", "default": True},
    "method":   {"desc": "学习方法", "default": True},
    "knowledge": {"desc": "知识库", "default": True},
    "affection": {"desc": "倾诉（情绪支持）", "default": True},
    "knowledge_map": {"desc": "知识导图", "default": True},
    "weather":  {"desc": "气象页面（Windy）", "default": True},
    "mcp":      {"desc": "MCP 双向工具网关", "default": True},
    "self_update": {"desc": "周期自我更新", "default": True},
    "file_gen": {"desc": "文件生成（讲义/练习题）", "default": True},
    "history":  {"desc": "历史会话", "default": True},
}


def _load_config() -> Dict[str, bool]:
    """加载 paeg_modules.json（不存在则全默认）。"""
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'paeg_modules.json')
    try:
        with open(cfg_path, encoding='utf-8') as f:
            raw = f.read()
        # {env:VAR} 替换
        import re
        raw = re.sub(r'\{env:([A-Z_]+)\}', lambda m: os.environ.get(m.group(1), ""), raw)
        data = json.loads(raw)
        if isinstance(data, dict):
            return {k: bool(v) for k, v in data.items() if isinstance(v, bool)}
    except Exception:
        pass
    return {}


def is_enabled(module_id: str) -> bool:
    """判断模块是否启用（默认启用，除非配置显式 false）。"""
    cfg = _load_config()
    if module_id in cfg:
        return cfg[module_id]
    return MODULE_CATALOG.get(module_id, {}).get("default", True)


def enabled_modules() -> List[str]:
    """返回所有启用模块 id。"""
    return [mid for mid in MODULE_CATALOG if is_enabled(mid)]


def module_status() -> Dict[str, Dict[str, Any]]:
    """返回全部模块状态（供 /api/modules 查询）。"""
    return {
        mid: {"enabled": is_enabled(mid), "desc": info["desc"]}
        for mid, info in MODULE_CATALOG.items()
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("=== 模块状态 ===")
    for mid, st in module_status().items():
        print(f"  {'✅' if st['enabled'] else '❌'} {mid}: {st['desc']}")
