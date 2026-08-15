# -*- coding: utf-8 -*-
"""services/rag_config.py —— config/rag.json 懒加载读取器（B1 RAG 配置化）。

职责：
- 读取 ``config/rag.json``（BM25 参数 / chunker 参数 / 语义开关等）
- 缺键回退到内置默认值（永不抛异常）
- 单例缓存；提供 :func:`reset_rag_config_cache` 给测试与热重载使用

设计要点：
1. **懒加载**：第一次 :func:`get_rag_config` 时读盘 + 解析；后续命中缓存。
2. **缺键兜底**：用 deep-merge 把文件覆盖层与内置默认合并——文件有就用文件的，
   文件没有就用默认，schema 演进安全。
3. **故障兜底**：文件缺失 / JSON 损坏 / 非 dict 顶层 → 返回全默认，
   上游调用方拿到的是结构完整但值全默认的 dict，不会被静默异常穿透。
4. **可测试**：``_CONFIG_PATH`` 是模块级属性，monkeypatch 可重定向到 tmp_path；
   ``reset_rag_config_cache()`` 清空缓存让下一次调用重新读盘。
5. **零依赖**：仅依赖标准库；``lib/ingest`` 可放心 import。

为什么放在 services/ 而不是 config.py？
- ``config.py`` 是纯环境变量读取层（无副作用、无 I/O）
- JSON 配置属于"数据文件"层，与运行时 secrets 是不同职责
- services/ 已有同类的 ``config_schema.py``，职责一致
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 模块级状态：缓存 + 文件路径 + 内置默认值
# ---------------------------------------------------------------------------

# 单例缓存：None 表示未加载
_cached: Optional[Dict[str, Any]] = None

# config/rag.json 默认路径（services/rag_config.py → 05_实现原型/config/rag.json）
_CONFIG_PATH: Path = Path(__file__).resolve().parent.parent / "config" / "rag.json"

# 内置默认值（与 config/rag.json schema 对齐；缺键回退用）
_DEFAULTS: Dict[str, Any] = {
    "chunker": {"max_chars": 400, "overlap": 50},
    "retrieval": {"top_k": 5, "bm25_k1": 1.5, "bm25_b": 0.75, "rrf_k": 60},
    "dedup": {"key": "subject+concept"},
    "semantic": {"enabled": False},
}


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def _deep_merge(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并 ``defaults`` 与 ``overrides``，overrides 同名字段覆盖 defaults。

    返回新 dict，不修改入参。
    """
    out = deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _load_from_disk() -> Dict[str, Any]:
    """读取 ``_CONFIG_PATH`` 指向的 JSON 文件。

    异常分支（FileNotFoundError / JSONDecodeError / OSError / 顶层非 dict）
    → 返回 ``{}``，让 :func:`_deep_merge` 把整棵 defaults 兜回去。
    """
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.debug("config/rag.json 不存在（%s），回退全默认", _CONFIG_PATH)
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("config/rag.json 解析失败（%s），回退全默认", exc)
        return {}

    if not isinstance(data, dict):
        logger.warning(
            "config/rag.json 顶层不是 dict（实际 %s），回退全默认",
            type(data).__name__,
        )
        return {}
    return data


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------
def get_rag_config() -> Dict[str, Any]:
    """读取 ``config/rag.json`` 并与内置默认值 deep-merge，返回最终 dict。

    返回结构（顶层 dict，四节）：
    - ``chunker``：``{"max_chars": int, "overlap": int}``
    - ``retrieval``：``{"top_k": int, "bm25_k1": float, "bm25_b": float, "rrf_k": int}``
    - ``dedup``：``{"key": str}``
    - ``semantic``：``{"enabled": bool}``

    永不抛异常；文件缺失/损坏时返回 ``_DEFAULTS`` 的拷贝。

    Returns:
        合并后的配置 dict。
    """
    global _cached
    if _cached is None:
        file_data = _load_from_disk()
        _cached = _deep_merge(_DEFAULTS, file_data)
    return _cached


def reset_rag_config_cache() -> None:
    """清空单例缓存，让下一次 :func:`get_rag_config` 重新读盘。

    用途：
    - 测试间隔离（每个 test 写自己的 tmp config 后 reset 再读）
    - 未来热重载 config/rag.json（admin 端点改完文件后调用一次）
    """
    global _cached
    _cached = None


def get_rag_config_path() -> Path:
    """返回当前生效的 config/rag.json 路径（便于诊断 + 测试 monkeypatch）。"""
    return _CONFIG_PATH


__all__ = [
    "get_rag_config",
    "reset_rag_config_cache",
    "get_rag_config_path",
]