# -*- coding: utf-8 -*-
"""services/material_bridge.py — PAEG ↔ paeg-teaching-materials 插件接入桥（§3.110 ⭐）。

设计目标（对标 infra/lang_plugin_bridge.py 语言规范插件模式）：
1. **宿主实现注入**：把 PAEG 内部对象（_safe_chat / paeg.refiner / library）注入插件
2. **零破坏回退**：插件未安装 → 静默回退 PAEG 原物料实现（旧文件永不删除）
3. **可及性**：主项目启动时调 install_material_plugin() 一次即可

用法（server.py 启动时）：
    from services.material_bridge import install_material_plugin
    install_material_plugin()
"""
from __future__ import annotations

import json
import os

# 插件可用标记（模块级缓存）
_plugin = None
_plugin_ready = False
_tried = False

# 灰度开关（§3.112 ⭐）：PAEG_USE_MATERIAL_PLUGIN 默认 1，0 走旧路径
_USE_PLUGIN_CACHE = None


def _use_plugin() -> bool:
    """读取灰度开关（缓存）。"""
    global _USE_PLUGIN_CACHE
    if _USE_PLUGIN_CACHE is None:
        _USE_PLUGIN_CACHE = os.environ.get("PAEG_USE_MATERIAL_PLUGIN", "1") == "1"
    return _USE_PLUGIN_CACHE


class BridgeError(Exception):
    """插件桥接错误（触发自动回退旧实现）。"""


def bridge_status() -> dict:
    """桥健康信息（供 /health 端点）。"""
    return {
        "active": plugin_active(),
        "version": getattr(_load_plugin(), "__version__", ""),
        "use_plugin": _use_plugin(),
    }


def _load_plugin():
    """尝试加载教学物料插件；失败 → None（静默回退）。"""
    global _plugin, _plugin_ready, _tried
    if _tried:
        return _plugin if _plugin_ready else None
    _tried = True
    try:
        import paeg_teaching_materials as _p
        _plugin = _p
        _plugin_ready = True
        return _plugin
    except Exception:
        _plugin = None
        _plugin_ready = False
        return None


def plugin_active() -> bool:
    """教学物料插件是否已挂载。"""
    return _load_plugin() is not None


def install_material_plugin() -> bool:
    """把 PAEG 宿主实现注入教学物料插件（主项目启动时调一次）。

    注入：
    - LLM：subagents._safe_chat（PAEG 统一 LLM 调用）
    - Refiner：paeg.refiner（语言规范 L2 深度矫正）
    - ResourceProvider：services.library.collect_all_resources

    Returns: 插件是否成功安装。
    """
    p = _load_plugin()
    if p is None:
        return False

    # ── LLM 适配（subagents._safe_chat）──
    def _paeg_llm(system: str, user: str, *, max_tokens: int = 2000,
                  temperature: float = 0.7) -> str:
        try:
            from subagents import _safe_chat
            from llm_adapter import create_llm
            llm = create_llm("auto")
            return _safe_chat(llm, system, user, max_tokens=max_tokens)
        except Exception as e:
            return f"（LLM 调用失败: {str(e)[:100]}）"

    # ── Refiner 适配（paeg.refiner）──
    class _PaegRefiner:
        def detect_ai_tells(self, text: str):
            try:
                from infra.runtime import get_paeg
                paeg = get_paeg()
                if paeg is not None and paeg.refiner is not None:
                    return paeg.refiner.detect_ai_tells(text)
            except Exception:
                pass
            return []

        def refine(self, text: str, context: str = ""):
            try:
                from infra.runtime import get_paeg
                paeg = get_paeg()
                if paeg is not None and paeg.refiner is not None:
                    return paeg.refiner.refine(text, context=context)
            except Exception:
                pass
            return text

    # ── ResourceProvider 适配（services.library）──
    class _PaegResources:
        def collect_all_resources(self, topic: str, subject: str):
            try:
                from services.library import collect_all_resources
                return collect_all_resources(topic, subject)
            except Exception:
                return []

        def search(self, query: str, k: int = 5):
            try:
                from services.library import collect_all_resources
                return collect_all_resources(query, "通用")
            except Exception:
                return []

    # 注入
    try:
        p.MaterialRegistry.inject(
            llm=_paeg_llm,
            refiner=_PaegRefiner(),
            resources=_PaegResources(),
        )
        return True
    except Exception:
        return False


def execute(name: str, arguments: dict = None) -> str:
    """统一执行入口（插件可用 → 插件；否则 → 回退空 JSON 错误）。"""
    p = _load_plugin()
    if p is not None:
        return p.execute(name, arguments or {})
    return '{"ok": false, "error": "教学物料插件未安装（paeg-teaching-materials）"}'


def execute_typed(name: str, arguments: dict = None) -> dict:
    """执行并返回 dict（供 _gen_* 双轨消费，§3.112 ⭐）。

    插件不可用 / 抛异常 → 抛 BridgeError（调用方回退旧实现）。
    """
    if not _use_plugin():
        raise BridgeError("PAEG_USE_MATERIAL_PLUGIN=0（灰度关闭，走旧路径）")
    p = _load_plugin()
    if p is None:
        raise BridgeError("教学物料插件未安装（paeg-teaching-materials）")
    try:
        raw = p.execute(name, arguments or {})
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return {"ok": False, "error": raw[:200]}
        return dict(raw)
    except BridgeError:
        raise
    except Exception as e:
        raise BridgeError(f"插件执行失败: {str(e)[:200]}")


def execute_generator(name: str, arguments: dict = None):
    """SSE 生成器适配（§3.112 ⭐）：插件结果 → SSE 事件流（与旧 _gen_* 契约一致）。

    旧 material_router._gen_* 返回 SSE 事件迭代器（fmt_presentation/fmt_done），
    插件 execute 返回 JSON——此处转换为等价事件流（保持字节级契约）。
    """
    try:
        result = execute_typed(name, arguments)
    except BridgeError:
        raise
    # 转换为 SSE 事件（兼容 material_router 的 sse_presenter 契约）
    try:
        from sse_presenter import fmt_done, fmt_presentation
    except Exception:
        fmt_done = fmt_presentation = None
    if result.get("ok"):
        _output = result.get("output") or result.get("summary_md") or ""
        if fmt_presentation is not None:
            yield fmt_presentation(1, str(_output)[:2000],
                                   name.replace("generate_", ""))
        if fmt_done is not None:
            yield fmt_done(name.replace("generate_", ""),
                           result.get("url") or result.get("path") or "")
    else:
        # 失败 → 抛 BridgeError 触发回退
        raise BridgeError(f"插件生成失败: {result.get('error', '')}")
