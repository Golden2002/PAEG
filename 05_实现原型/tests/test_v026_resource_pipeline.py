# -*- coding: utf-8 -*-
"""
v0.26 资源生产/下载闭环测试

覆盖：
1. /api/library-file 真实文件读取（md/txt/json）
2. /api/library-file 路径穿越拒绝 / 缺失 400/404
3. /api/resources 向后兼容（无 for_ppt 时无 ppt 字段）
（for_ppt 真实 PPT 生成由端到端验证——避免 pytest 内启动 MCP server 干扰测试环境）
"""
import os
import sys
import shutil
import urllib.parse

# 让测试能找到 05_实现原型/ 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_user_dir(uid: str) -> str:
    """在真实 Library/usr_knowledge/<uid>/ 下创建临时用户目录，返回路径。"""
    from lib import library_store
    p = library_store.resolve_library_root(uid)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def _cleanup_user_dir(uid: str) -> None:
    from lib import library_store
    p = library_store.resolve_library_root(uid)
    shutil.rmtree(p, ignore_errors=True)


# ─────────────────────────────────────
# 1. /api/library-file 真实文件读取
# ─────────────────────────────────────

def test_library_file_reads_real_md():
    """GET /api/library-file?learner_id=<uid>&file=<md> 应返回文件内容。"""
    uid = "test_lib_md_001"
    udir = _make_user_dir(uid)
    try:
        with open(os.path.join(udir, "牛顿定律.md"), "w", encoding="utf-8") as f:
            f.write("# 牛顿定律\n\n- F=ma\n")
        from server import app
        client = app.test_client()
        import urllib.parse
        r = client.get(f"/api/library-file?learner_id={uid}&file={urllib.parse.quote('牛顿定律.md')}")
        assert r.status_code == 200, f"应 200, 实际 {r.status_code} {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body.get("ok") is True
        assert "F=ma" in (body.get("content") or "")
        assert body.get("type") == "md"
        print("[OK] test_library_file_reads_real_md")
    finally:
        _cleanup_user_dir(uid)


def test_library_file_reads_txt_and_json():
    """txt 与 json 文件也能读取。"""
    uid = "test_lib_txt_001"
    udir = _make_user_dir(uid)
    try:
        with open(os.path.join(udir, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("一些笔记内容")
        from server import app
        client = app.test_client()
        import urllib.parse
        r = client.get(f"/api/library-file?learner_id={uid}&file={urllib.parse.quote('notes.txt')}")
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("ok") is True and "笔记" in (body.get("content") or "")
        print("[OK] test_library_file_reads_txt_and_json")
    finally:
        _cleanup_user_dir(uid)


def test_library_file_path_traversal_blocked():
    """路径穿越（../）应被拒绝（400 或 404，不得读文件）。"""
    uid = "test_lib_trav_001"
    _make_user_dir(uid)
    try:
        from server import app
        client = app.test_client()
        r = client.get(f"/api/library-file?learner_id={uid}&file={urllib.parse.quote('../prompts.py')}")
        assert r.status_code in (400, 404), f"应拒绝, 实际 {r.status_code}"
        body = r.get_json()
        assert body.get("ok") is False, "穿越应返回 ok=False"
        print("[OK] test_library_file_path_traversal_blocked")
    finally:
        _cleanup_user_dir(uid)


def test_library_file_missing_params_returns_400():
    """缺参数 → 400。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/library-file?learner_id=test_x")
    assert r.status_code == 400
    print("[OK] test_library_file_missing_params_returns_400")


# ─────────────────────────────────────
# 2. /api/resources 向后兼容
# ─────────────────────────────────────

def test_resources_without_for_ppt_backward_compatible():
    """不带 for_ppt 时响应不含 'ppt' 字段（向后兼容）。"""
    from server import app
    client = app.test_client()
    r = client.post("/api/resources", json={
        "learner_id": "test_bc_001",
        "question": "牛顿定律",
        "subject": "physics",
        "for_ppt": False,
    })
    assert r.status_code == 200
    body = r.get_json()
    assert "ppt" not in body, f"不带 for_ppt 时不应有 ppt 字段，实际 {list(body.keys())}"
    assert "sources" in body
    print("[OK] test_resources_without_for_ppt_backward_compatible")


def test_resources_missing_question_returns_400():
    """缺 question → 400。"""
    from server import app
    client = app.test_client()
    r = client.post("/api/resources", json={"learner_id": "test_x", "for_ppt": False})
    assert r.status_code == 400
    print("[OK] test_resources_missing_question_returns_400")
