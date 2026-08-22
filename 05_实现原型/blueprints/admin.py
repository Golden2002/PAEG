"""admin.py — 管理蓝图（v0.68 配置热重载 / §3.38 配置树导出）。

§3.45 架构拆分 P1-3：自 server.py 迁出（原 L2604-2641），行为字节级不变。
依赖注入：config_hub / hooks_hub / profile_bundle 懒加载（无 server 全局依赖）。
§3.79 Round 12 ⭐ admin rate-limit 二道防线：写操作（模块切换）加 IP 频率限制——
与 PAEG_ADMIN_TOKEN 认证叠加，防 token 爆破/恶意高频切换（kill switch 被滥用止损）。
"""
from __future__ import annotations

import os
import threading
import time

from flask import Blueprint, jsonify, request

bp = Blueprint("admin", __name__)

# ── §3.79 Round 12 ⭐ admin 写操作限频（二道防线）──
# 设计：每 IP 滑动窗口限频（默认 10 次/分钟）——token 爆破（暴力尝试）与高频误操作
# （脚本死循环切模块）都被挡下；配合 token 认证（第一道防线：401 安全默认）。
# 内存实现（无新依赖，进程内），窗口滑动，线程安全。
_ADMIN_WRITE_LIMIT = int(os.environ.get("PAEG_ADMIN_RATE_LIMIT", "10"))
_ADMIN_WINDOW = 60  # 秒
_admin_hits: dict = {}  # ip -> [ts...]
_admin_lock = threading.Lock()


def _admin_write_allowed() -> bool:
    """滑动窗口限频检查：返回 False 表示超限（429）。"""
    _ip = request.remote_addr or "unknown"
    _now = time.time()
    with _admin_lock:
        _hits = _admin_hits.setdefault(_ip, [])
        # 清理窗口外记录
        while _hits and _now - _hits[0] > _ADMIN_WINDOW:
            _hits.pop(0)
        if len(_hits) >= _ADMIN_WRITE_LIMIT:
            return False
        _hits.append(_now)
        return True


def _admin_authorized() -> bool:
    """§3.79 Round 8 ⭐ admin 权限保护：写操作需 PAEG_ADMIN_TOKEN。

    安全默认：未配置 PAEG_ADMIN_TOKEN → 拒绝写操作（防任意访客 kill switch）。
    配置后：请求需带 `X-Admin-Token` 头（或 ?token= 查询参数）且匹配。
    读操作（GET 状态）保持开放（无害审计视图，运维排查可用）。
    """
    _token = os.environ.get("PAEG_ADMIN_TOKEN", "").strip()
    if not _token:
        return False  # 未配置 → 写操作禁用（安全默认）
    _provided = request.headers.get("X-Admin-Token") or request.args.get("token") or ""
    return _provided == _token


@bp.route("/api/admin/reload", methods=["POST"])
def admin_reload():
    """v0.68+ P0-4（Step4）：运行时重载 config_hub（MCP/skills/hooks/workflows 配置热更新）。
    改 config/*.json 后调用此端点即时生效，无需重启服务器。"""
    try:
        from config_hub import get_hub
        _hub = get_hub()
        if _hub is None:
            return jsonify({"ok": False, "error": "config_hub 未初始化"}), 500
        _hub.reload_all()
        _extra = {}
        try:
            from hooks_hub import get_hooks_hub
            _hh = get_hooks_hub()
            _extra["hooks"] = [{"id": h.id, "event": h.event, "loaded": h._fn is not None}
                               for h in getattr(_hh, "hooks", [])]
        except Exception as _hx:
            _extra["hooks_error"] = str(_hx)
        return jsonify({"ok": True,
                        "message": "config_hub 已重载（MCP/skills/hooks/workflows）",
                        **_extra})
    except Exception as _re_e:
        return jsonify({"ok": False, "error": str(_re_e)}), 500


@bp.route("/api/admin/dump-config", methods=["GET"])
def admin_dump_config():
    """§3.38 H-13 ⭐ 配置树导出（对齐 dsh --dump-config）。

    返回完整可 patch 配置树：profiles/bundles/agents/tools/effective——
    用于调试、审计、外部 agent 理解 PAEG 配置结构。
    """
    try:
        from services.profile_bundle import dump_config_tree
        _tree = dump_config_tree()
        return jsonify(_tree)
    except Exception as _dc_e:
        return jsonify({"ok": False, "error": str(_dc_e)}), 500


@bp.route("/api/admin/modules", methods=["GET"])
def admin_modules_status():
    """§3.79 D9 ⭐ 模块门控状态（kill switch 审计视图）。

    返回全部模块 enabled 状态（module_registry.module_status），
    供运维/灰度观察当前哪些功能在线（配合 deploy/canary.ps1）。
    """
    try:
        from module_registry import module_status
        _st = module_status()
        return jsonify({"ok": True, "modules": _st})
    except Exception as _me:
        return jsonify({"ok": False, "error": str(_me)}), 500


@bp.route("/api/admin/health", methods=["GET"])
def admin_health():
    """§3.85 ⭐ A12 App Server 托管：管理面独立健康视图。

    Codex Harness App Server 借鉴——管理面（admin/kill switch/指标/图）与教学面
    分离托管：教学面故障不影响管理面可观测（运维可诊断）。本端点只依赖管理面
    组件（module_registry/subagent_graph），不触碰教学管线。
    """
    try:
        from module_registry import module_status
        _mods = module_status()
        _mgmt = {
            "ok": True,
            "management_plane": "alive",
            "modules": len(_mods),
            "modules_enabled": sum(1 for m in _mods.values()
                                   if isinstance(m, dict) and m.get("enabled")),
            "ts": time.time(),
        }
        # subagent 图视图（P1 声明图——管理面可视化）
        try:
            from services.subagent_graph import graph_view
            _mgmt["subagent_graph"] = graph_view()
        except Exception:
            _mgmt["subagent_graph"] = None
        return jsonify(_mgmt)
    except Exception as _ah_e:
        return jsonify({"ok": False, "management_plane": "degraded",
                        "error": str(_ah_e)}), 500


@bp.route("/api/admin/modules", methods=["POST"])
def admin_modules_set():
    """§3.79 D9 ⭐ 远程模块切换（kill switch 60s 止损的可执行化）。

    请求：{"module": "ppt", "enabled": false} 或 {"modules": {"ppt": false, "history": true}}
    行为：改写 paeg_modules.json（原子写）→ module_registry 热重载即时生效（无需重启）
    审计：切换写入 observability 事件（module/toggle，含操作者/前后状态）——
    §灰度回滚规范 二 kill switch 落地。
    """
    if not _admin_authorized():
        return jsonify({"ok": False,
                        "error": "需要 PAEG_ADMIN_TOKEN（请求头 X-Admin-Token 或 ?token=）"}), 401
    # §3.79 Round 12 ⭐ 二道防线：写操作限频（token 爆破/高频滥用防护）
    if not _admin_write_allowed():
        return jsonify({"ok": False,
                        "error": f"写操作过于频繁（限 {_ADMIN_WRITE_LIMIT} 次/{_ADMIN_WINDOW}s，"
                                 "可设 PAEG_ADMIN_RATE_LIMIT 调整）"}), 429
    data = request.get_json(force=True) or {}
    _module = str(data.get("module") or "").strip()
    _toggle = data.get("modules")
    if _module and "enabled" in data:
        _toggle = {_module: bool(data.get("enabled"))}
    if not isinstance(_toggle, dict) or not _toggle:
        return jsonify({"ok": False, "error": "需 {module, enabled} 或 {modules: {...}}"}), 400
    # §3.85 ⭐ Approval 审批流（Codex Harness 借鉴 A10）：**禁用模块（kill switch）是
    # 破坏性操作**——第一次请求（无 confirm）返回"需要确认"提示（不执行）；客户端带
    # confirm:true（或 X-Confirm:1 头）才真正执行。防误触 kill switch（运维事故防线，
    # 与 token 认证/限频叠加为第三道防线）。
    _disabling = any(not bool(v) for v in _toggle.values())
    _confirmed = bool(data.get("confirm")) or request.headers.get("X-Confirm") == "1"
    if _disabling and not _confirmed:
        return jsonify({
            "ok": False,
            "error": "该操作将禁用模块（kill switch 破坏性操作），需显式确认："
                     "请求体带 confirm:true 或请求头 X-Confirm:1 后重试",
            "needs_confirm": True,
            "modules": {k: bool(v) for k, v in _toggle.items()},
        }), 409
    import os
    from pathlib import Path
    _cfg_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "paeg_modules.json"
    try:
        import json as _json
        _cur = {}
        if _cfg_path.exists():
            _cur = _json.loads(_cfg_path.read_text(encoding="utf-8"))
        _before = dict(_cur)
        _applied = []
        for _mid, _en in _toggle.items():
            _mid = str(_mid).strip()
            if not _mid:
                continue
            _cur[_mid] = bool(_en)
            _applied.append({"module": _mid, "from": _before.get(_mid), "to": bool(_en)})
        # 原子写（tmp + os.replace）
        _tmp = _cfg_path.with_suffix(".json.tmp")
        _tmp.write_text(_json.dumps(_cur, ensure_ascii=False, indent=2), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_cfg_path))
        # 审计事件（模块切换写 observability——可追溯）
        try:
            from observability import emit_event_typed
            for _a in _applied:
                emit_event_typed("module/toggle", module=_a["module"],
                                 from_state=_a["from"], to_state=_a["to"],
                                 operator=str(data.get("operator") or "admin_api"))
        except Exception:
            pass
        return jsonify({"ok": True, "applied": _applied, "message": "模块门控已更新（热重载，无需重启）"})
    except Exception as _me2:
        return jsonify({"ok": False, "error": str(_me2)}), 500
