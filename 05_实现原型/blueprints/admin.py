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
