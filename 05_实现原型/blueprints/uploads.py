"""uploads.py — 文件上传蓝图（v0.19 资料/图片上传 + v0.26 头像）。

§3.45 架构拆分 P1-5：自 server.py 迁出（原 L2684-2752 / L2754-2794），行为字节级不变。

⚠ __file__ 修正：本文件位于 blueprints/ 子目录，项目根需上溯 parent.parent
（原 server.py 中 `os.path.dirname(os.path.abspath(__file__))` 即项目根 05_实现原型/，
迁入 blueprints/ 后必须改为 _SRV_ROOT = dirname(dirname(...))，否则上传落盘目录错位）。
依赖注入：lib.library_store 懒加载（无 server 全局依赖）。
"""
from __future__ import annotations

import os as _os

from flask import Blueprint, jsonify, request

bp = Blueprint("uploads", __name__)

# §3.45 ⭐ __file__ 修正：blueprints/uploads.py → 项目根需上溯两级
_SRV_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))


@bp.route("/api/upload", methods=["POST"])
def upload_file():
    """v0.19 P2-10：图片/文件上传 + v0.19.11 资料上传。

    请求：multipart/form-data, file + learner_id + purpose(可选: library=资料库)
          + library_root(可选: "usr_knowledge" 存到 Library/usr_knowledge/<id>/，
                         默认 "user" 存到 Library/user_<id>/，向后兼容)
    响应：{"url", "filename"} 或 {"library": 资料列表}
    """
    learner_id = request.form.get("learner_id", "anonymous")
    f = request.files.get("file")
    purpose = request.form.get("purpose", "chat")
    # v0.21.4：资料库根目录选择；默认 "usr_knowledge"（规范路径 Library/usr_knowledge/<id>/），
    # 旧值 "user" 仍兼容（内部统一存到规范路径，读取时双读旧路径保持向后兼容）
    library_root = request.form.get("library_root", "usr_knowledge")

    # v0.19.11：资料上传 → Library/用户id/
    if purpose == "library":
        if not f or not f.filename:
            return jsonify({"error": "no file"}), 400
        allowed = (".pdf", ".md", ".txt", ".docx", ".csv", ".json", ".png", ".jpg")
        ext = _os.path.splitext(f.filename)[1].lower()
        if ext not in allowed:
            return jsonify({"error": f"不支持的格式 {ext}"}), 400
        try:
            # v0.21.4：统一通过 lib.library_store 决定保存目录（规范路径）
            from lib import library_store
            lib_root_path = library_store.upload_save_dir(learner_id, library_root)
            lib_root = str(lib_root_path)
            sub_dir = library_store.CANONICAL_DIRNAME  # 始终是 "usr_knowledge"
            note_text = "资料已存入 usr_knowledge，回答时会自动参考"
            _os.makedirs(lib_root, exist_ok=True)
            from datetime import datetime
            safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{_os.path.basename(f.filename)}"
            f.save(_os.path.join(lib_root, safe_name))
            return jsonify({
                "ok": True, "filename": safe_name,
                "url": f"/Library/{sub_dir}/{learner_id}/{safe_name}",
                "library_root": "usr_knowledge",
                "library_path": f"Library/{sub_dir}/{learner_id}/{safe_name}",
                "note": note_text,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if not f or not f.filename:
        return jsonify({"error": "no file"}), 400
    # 限制类型（图片为主）
    allowed = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".md", ".txt")
    ext = _os.path.splitext(f.filename)[1].lower()
    if ext not in allowed:
        return jsonify({"error": f"不支持的格式 {ext}"}), 400
    try:
        base = _os.path.join(_SRV_ROOT, 'uploads', learner_id)
        _os.makedirs(base, exist_ok=True)
        from datetime import datetime
        safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{_os.path.basename(f.filename)}"
        f.save(_os.path.join(base, safe_name))
        from urllib.parse import quote
        return jsonify({
            "ok": True,
            "filename": safe_name,
            "url": f"/uploads/{learner_id}/{quote(safe_name)}",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/avatar", methods=["POST"])
def upload_avatar():
    """v0.26 ⭐ 用户自定义头像上传 + v0.36 P0-03 错误响应加 ok:False（前端 `!j.ok` 双重校验更稳）。

    请求：multipart/form-data, avatar(图片) + learner_id
    响应：{"ok": True, "url": "/uploads/avatar/<learner_id>.<ext>"}
    覆盖式保存（每用户单头像），存 uploads/avatar/<learner_id>.<ext>。
    """
    learner_id = (request.form.get("learner_id") or "anonymous").strip()
    if not learner_id or learner_id in (".", "..") or "/" in learner_id or "\\" in learner_id:
        return jsonify({"ok": False, "error": "非法用户标识"}), 400
    f = request.files.get("avatar")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "no avatar file"}), 400
    ext = _os.path.splitext(f.filename)[1].lower()
    allowed = (".png", ".jpg", ".jpeg", ".gif", ".webp")
    if ext not in allowed:
        return jsonify({"ok": False, "error": f"头像仅支持 {'/'.join(allowed)}"}), 400
    try:
        base = _os.path.join(_SRV_ROOT, 'uploads', 'avatar')
        _os.makedirs(base, exist_ok=True)
        # 覆盖式：固定文件名 avatar_<learner_id><ext>（换头像自动覆盖旧图）
        fname = f"avatar_{learner_id}{ext}"
        f.save(_os.path.join(base, fname))
        # 清理同用户旧扩展名头像（避免残留）
        for _old_ext in allowed:
            if _old_ext != ext:
                _old = _os.path.join(base, f"avatar_{learner_id}{_old_ext}")
                if _os.path.exists(_old):
                    try:
                        _os.remove(_old)
                    except Exception as _e:
                        print(f"[PAEG][blueprints/uploads.py] upload_avatar 异常忽略: {_e}")
                        pass
        from urllib.parse import quote
        return jsonify({"ok": True, "url": f"/uploads/avatar/{quote(fname)}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
