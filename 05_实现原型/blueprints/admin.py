"""admin.py — 管理蓝图（v0.68 配置热重载 / §3.38 配置树导出）。

§3.45 架构拆分 P1-3：自 server.py 迁出（原 L2604-2641），行为字节级不变。
依赖注入：config_hub / hooks_hub / profile_bundle 懒加载（无 server 全局依赖）。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

bp = Blueprint("admin", __name__)


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


@bp.route("/api/admin/modules", methods=["POST"])
def admin_modules_set():
    """§3.79 D9 ⭐ 远程模块切换（kill switch 60s 止损的可执行化）。

    请求：{"module": "ppt", "enabled": false} 或 {"modules": {"ppt": false, "history": true}}
    行为：改写 paeg_modules.json（原子写）→ module_registry 热重载即时生效（无需重启）
    审计：切换写入 observability 事件（module/toggle，含操作者/前后状态）——
    §灰度回滚规范 二 kill switch 落地。
    """
    data = request.get_json(force=True) or {}
    _module = str(data.get("module") or "").strip()
    _toggle = data.get("modules")
    if _module and "enabled" in data:
        _toggle = {_module: bool(data.get("enabled"))}
    if not isinstance(_toggle, dict) or not _toggle:
        return jsonify({"ok": False, "error": "需 {module, enabled} 或 {modules: {...}}"}), 400
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
