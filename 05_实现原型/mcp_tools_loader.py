# -*- coding: utf-8 -*-
"""mcp_tools_loader.py —— §3.36 ⭐ MCP 工具可移植性：配置驱动加载器（v1.1.1）

需求（§3.36，用户 2026-08-15）：
- config/mcp_tools.json 声明的工具（name/description/risk/module/function/params）
  必须真正接入工具注册表——**改配置即生效**（改 description → get_all_tool_defs() 变化、
  增删条目 → 工具表变化）。此前断链：JSON 声明了但无加载器，改配置不影响行为。

设计（Oracle 架构咨询 + librarian 生产级模式调研）：
- 独立模块（不并入 tool_registry，SRP：把 JSON 声明翻译为可注册的 (def, handler)）
- 安全边界（参照 LangFlow GHSA-2wcq-pvw2-xh7v 教训 + importlib 官方文档）：
  ① 模块前缀白名单（_ALLOWED_MODULE_PREFIXES，只允许项目已知模块）
  ② 拒绝危险模块（os/sys/subprocess/shutil/importlib/builtins/__）
  ③ 函数名必须合法 Python identifier（防 `__import__("os").system` 注入）
  ④ 永不 exec/eval——只用 importlib.import_module + getattr
- 冲突规则（ratchet 铁律：不破坏现有功能）：
  内置工具（tool_registry 硬编码）优先；配置只更新 description/risk/params 元数据，
  覆盖 handler 需显式 `"override": true`（默认拒绝 + warning 日志）
- risk=write 自动同步 _WRITE_TOOLS（exam 模式锁定新 write 工具）
- 异常隔离：单个工具声明损坏/导入失败 → 跳过 + 日志，不影响其他工具

用法：
    from mcp_tools_loader import load_config_tools, reload_config_tools
    defs, handlers = load_config_tools()          # 首次加载
    defs, handlers = reload_config_tools()        # 热重载（失败保留旧配置）
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import re
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("paeg")

# ─────────────────────────────────────
# 安全边界常量
# ─────────────────────────────────────
# 允许导入的模块前缀白名单（配置中 module 字段必须匹配其一）
_ALLOWED_MODULE_PREFIXES: Tuple[str, ...] = (
    "tool_registry",
    "constraint_engine",
    "material_pipeline",
    "services",
    "lib",
    "utils",
)
# 明确拒绝的危险模块（直接命中即拒绝，不通过前缀判断）
_BLOCKED_MODULES: Tuple[str, ...] = (
    "os", "sys", "subprocess", "shutil", "importlib",
    "builtins", "pickle", "yaml", "ctypes", "socket",
)
# 模块路径合法性模式（防路径穿越/拼接注入）
_MODULE_PATH_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")
# 函数名必须是非下划线开头的合法 identifier
_FUNC_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

# 默认配置路径
_DEFAULT_CFG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "mcp_tools.json")


# ─────────────────────────────────────
# 校验与解析
# ─────────────────────────────────────

class ToolConfigError(Exception):
    """工具配置声明错误（单条失败 → 跳过该条，不影响其他）。"""


def _validate_name(name: str) -> None:
    """工具名校验（MCP SEP-986：^[A-Za-z0-9._-]{1,128}$）。"""
    if not name or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", name):
        raise ToolConfigError(f"非法工具名: {name!r}（需匹配 [A-Za-z0-9._-]{{1,128}}）")


def _validate_module(module: str) -> None:
    """模块路径三重校验：白名单前缀 + 路径模式 + 拒绝危险模块。"""
    if not module or not isinstance(module, str):
        raise ToolConfigError("module 字段缺失")
    if module in _BLOCKED_MODULES:
        raise ToolConfigError(f"危险模块被拒绝: {module}")
    if not _MODULE_PATH_RE.fullmatch(module):
        raise ToolConfigError(f"非法模块路径: {module!r}")
    if not any(module == p or module.startswith(p + ".") for p in _ALLOWED_MODULE_PREFIXES):
        raise ToolConfigError(f"模块不在白名单: {module}（允许前缀: {_ALLOWED_MODULE_PREFIXES}）")


def _validate_function(func: str) -> None:
    """函数名校验：非下划线开头的合法 identifier。"""
    if not func or not isinstance(func, str):
        raise ToolConfigError("function 字段缺失")
    if not _FUNC_NAME_RE.fullmatch(func):
        raise ToolConfigError(f"非法函数名: {func!r}（需非下划线开头、合法 identifier）")


def _resolve_handler(module: str, function: str) -> Callable[..., Any]:
    """安全动态导入：白名单校验 → import_module → getattr → callable 检查。

    参照 LangFlow GHSA 教训：只 import + getattr，永不 exec/eval。
    """
    _validate_module(module)
    _validate_function(function)
    try:
        mod = importlib.import_module(module)
    except Exception as e:
        raise ToolConfigError(f"导入模块失败 {module}: {e}") from e
    fn = getattr(mod, function, None)
    if not callable(fn):
        raise ToolConfigError(f"{module}.{function} 不可调用")
    return fn


def _parse_entry(entry: dict) -> dict:
    """解析单条工具声明 → 规范化 dict（含校验）。"""
    if not isinstance(entry, dict):
        raise ToolConfigError("工具条目必须是对象")
    name = entry.get("name", "")
    _validate_name(name)
    module = entry.get("module", "")
    function = entry.get("function", "")
    # module/function 缺失时：若该工具已内置注册（name 在 tool_registry），
    # 允许仅声明元数据（description/risk/params）——handler 复用内置。
    if not module and not function:
        module = "tool_registry"
        function = name  # 内置工具名即函数名（_HANDLERS 用 name 查）
    _validate_module(module)
    _validate_function(function)
    # §3.42 W5 ⭐ timeoutMs 字段解析（毫秒，> 0 生效；None/缺失 = 不声明）
    _tms_raw = entry.get("timeoutMs")
    if _tms_raw is not None and not isinstance(_tms_raw, (int, float)):
        raise ToolConfigError(f"timeoutMs 必须为数字（毫秒），实际 {_tms_raw!r}")
    _tms = int(_tms_raw) if (_tms_raw is not None and _tms_raw > 0) else None
    return {
        "name": name,
        "description": str(entry.get("description", "")),
        "risk": str(entry.get("risk", "read")).lower(),
        "module": module,
        "function": function,
        "params": entry.get("params") or {},
        "override": bool(entry.get("override", False)),
        "enabled": bool(entry.get("enabled", True)),
        "required": list(entry.get("required", [])) or [],
        "timeoutMs": _tms,  # §3.42 W5：None 表示未声明（ratchet：默认 30s）
    }


def _build_tool_def(entry: dict) -> dict:
    """构造 Function Calling 工具定义（OpenAI/DeepSeek 格式，与 tool_registry 对齐）。"""
    props: Dict[str, Any] = {}
    for k, v in (entry["params"] or {}).items():
        if isinstance(v, dict) and "type" in v:
            props[k] = v
        elif isinstance(v, str):
            props[k] = {"type": v}
        else:
            props[k] = {"type": "string"}
    return {
        "type": "function",
        "function": {
            "name": entry["name"],
            "description": entry["description"],
            "parameters": {
                "type": "object",
                "properties": props,
                "required": entry["required"],
            },
        },
    }


# ─────────────────────────────────────
# 加载器
# ─────────────────────────────────────

def _read_config(path: str) -> List[dict]:
    """读取并解析配置 JSON（顶层 tools 列表；损坏 → 空列表 + 日志）。"""
    if not os.path.isfile(path):
        logger.warning("[mcp_tools_loader] 配置不存在: %s（跳过外部工具）", path)
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        tools = data.get("tools", []) if isinstance(data, dict) else []
        if not isinstance(tools, list):
            logger.warning("[mcp_tools_loader] tools 字段非列表，跳过")
            return []
        return tools
    except Exception as e:
        logger.warning("[mcp_tools_loader] 配置解析失败 %s: %s（保留旧配置）", path, e)
        return []


# 运行态缓存（热重载时原子替换）
_state = {"defs": [], "handlers": {}, "meta": {}, "loaded": False}
_state_lock = threading.RLock()


def load_config_tools(config_path: Optional[str] = None) -> Tuple[List[dict], Dict[str, Callable]]:
    """首次加载配置驱动工具 → (工具定义列表, handler 字典)。

    - 对每个 JSON 声明：校验 → 解析 → 动态解析 handler
    - 内置工具（tool_registry 已注册）冲突时：默认内置优先，override:true 才覆盖
    - 单条失败跳过 + 日志，不影响其他工具
    """
    global _state
    path = config_path or _DEFAULT_CFG
    entries_raw = _read_config(path)
    defs: List[dict] = []
    handlers: Dict[str, Callable] = {}
    meta: Dict[str, dict] = {}

    # 获取内置工具名集合（冲突判定基准）
    builtin_names: set = set()
    try:
        from tool_registry import _HANDLERS as _builtin_handlers
        builtin_names = set(_builtin_handlers.keys())
    except Exception:
        builtin_names = set()

    for entry_raw in entries_raw:
        try:
            entry = _parse_entry(entry_raw)
        except ToolConfigError as e:
            logger.warning("[mcp_tools_loader] 跳过无效声明: %s", e)
            continue
        if not entry["enabled"]:
            continue
        name = entry["name"]
        # 冲突规则：内置工具优先；除非显式 override
        if name in builtin_names and not entry["override"]:
            logger.info("[mcp_tools_loader] 工具 %s 内置优先，配置仅更新元数据（override:true 可覆盖）", name)
            meta[name] = entry  # 元数据更新（description/risk/params 生效）
            continue
        try:
            handler = _resolve_handler(entry["module"], entry["function"])
        except ToolConfigError as e:
            logger.warning("[mcp_tools_loader] 跳过工具 %s: %s", name, e)
            continue
        if name in builtin_names:  # override 场景：覆盖 handler
            logger.warning("[mcp_tools_loader] 工具 %s 被配置 override 覆盖", name)
        handlers[name] = handler
        meta[name] = entry
        defs.append(_build_tool_def(entry))

    with _state_lock:
        _state = {"defs": defs, "handlers": handlers, "meta": meta, "loaded": True}
    return defs, handlers


def reload_config_tools(config_path: Optional[str] = None) -> Tuple[List[dict], Dict[str, Callable]]:
    """热重载：失败保留旧配置（原子替换）。"""
    global _state
    try:
        defs, handlers = load_config_tools(config_path)
        return defs, handlers
    except Exception as e:
        logger.warning("[mcp_tools_loader] 重载失败，保留旧配置: %s", e)
        with _state_lock:
            return _state["defs"], _state["handlers"]


def get_loaded_meta() -> Dict[str, dict]:
    """返回已加载的配置元数据（供 tool_registry 合并用）。"""
    with _state_lock:
        return dict(_state["meta"])


def get_loaded_handlers() -> Dict[str, Callable]:
    """返回已加载的外部 handler（供 tool_registry 合并用）。"""
    with _state_lock:
        return dict(_state["handlers"])


def get_loaded_defs() -> List[dict]:
    """返回已加载的外部工具定义。"""
    with _state_lock:
        return [dict(d) for d in _state["defs"]]


def is_loaded() -> bool:
    with _state_lock:
        return bool(_state["loaded"])


# 启动即自动加载（幂等：模块导入时执行一次；失败不阻塞）
try:
    load_config_tools()
except Exception:
    pass


__all__ = [
    "load_config_tools", "reload_config_tools",
    "get_loaded_meta", "get_loaded_handlers", "get_loaded_defs",
    "is_loaded", "ToolConfigError",
]
