# -*- coding: utf-8 -*-
"""
v0.28 P0 端点测试盲区补齐：26 个长期 0 pytest 覆盖的 Flask 端点。

按用途分组：
  A. 基础信息（health / subject-tree / meta-log / quote）
  B. 注册 / 登录 / 画像（register + login + profile GET/PUT）
  C. 文件上传（upload + avatar）
  D. 会话（conversations GET 列表/GET 单条/DELETE）
  E. 自更新（self-update/status + self-update/run）
  F. 其他（skills + batch）

每个测试都通过 Flask test_client 真实调用，**不依赖外部 server**；
涉及外部依赖（用户注册/上传）都用 tmp 文件 / 唯一邮箱避免污染。
"""
import os
import sys
import time
import uuid
import shutil
import tempfile
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────
# 公共 helper
# ─────────────────────────────────────


def _client():
    from server import app
    return app.test_client()


def _unique_email(tag: str) -> str:
    """生成不与历史用户冲突的唯一测试邮箱（包含时间戳 + uuid 前缀）。"""
    return f"v028_{tag}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}@paeg.test"


def _register_and_login(client, tag="x") -> dict:
    """注册并登录，返回 {"user_id", "nickname", "token"}。
    注：login 当前端点不返回 token 字段（用 user_id 标识）。"""
    email = _unique_email(tag)
    password = "TestPwd_123"
    nickname = f"测试_{tag}"

    r = client.post("/api/register", json={
        "identifier": email, "password": password, "nickname": nickname,
    })
    assert r.status_code == 200, f"注册失败: {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    assert body.get("ok") is True, f"注册 ok=False: {body}"
    user_id = body["user_id"]
    token = f"email:{email}"  # 本项目无 token 机制；自造占位以与 register/login 测试呼应

    r2 = client.post("/api/login", json={"identifier": email, "password": password})
    assert r2.status_code == 200, f"登录失败: {r2.status_code} {r2.get_data(as_text=True)}"
    body2 = r2.get_json()
    assert body2.get("ok") is True, f"登录 ok=False: {body2}"
    assert body2.get("user_id") == user_id
    return {"user_id": user_id, "nickname": nickname, "email": email, "token": token}


# ─────────────────────────────────────
# A. 基础信息端点
# ─────────────────────────────────────


def test_health_returns_full_status():
    """GET /api/health 应返回 200 + status/version/kb_stats/mcp/skill_count 等字段。"""
    r = _client().get("/api/health")
    assert r.status_code == 200, f"应 200，实际 {r.status_code}"
    body = r.get_json()
    assert body.get("status") == "ok", f"status 应为 ok，实际 {body}"
    for f in ("version", "llm_provider", "kb_stats", "mcp", "skill_count", "timestamp"):
        assert f in body, f"/api/health 缺字段 {f}，body={list(body.keys())}"
    # kb_stats 应包含若干计数字段
    kb_stats = body["kb_stats"]
    assert isinstance(kb_stats, dict)
    assert "total" in kb_stats
    print(f"[OK] /api/health 字段齐全：version={body['version']}, skills={body['skill_count']}")


def test_subject_tree_returns_grades_and_subjects():
    """GET /api/subject-tree 应返回 grades + grade_cn + subjects 三字段。"""
    r = _client().get("/api/subject-tree")
    assert r.status_code == 200, f"应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    assert "grades" in body and isinstance(body["grades"], list) and len(body["grades"]) >= 3, \
        f"grades 应为非空 list，实际 {body.get('grades')}"
    assert "subjects" in body and isinstance(body["subjects"], dict), \
        f"subjects 应为 dict，实际 {type(body.get('subjects'))}"
    # 至少应包含 math/physics
    subs = body["subjects"]
    assert "math" in subs, f"subjects 应含 'math'，实际 keys={list(subs)[:10]}"
    # math 至少有 grades 字段
    math_node = subs["math"]
    assert "label" in math_node and "grades" in math_node, \
        f"math 节点应含 label/grades，实际 {math_node}"
    print(f"[OK] /api/subject-tree grades={len(body['grades'])} subjects={len(body['subjects'])}")


def test_meta_log_returns_logs_and_total():
    """GET /api/meta-log/<id> 应返回 logs + total（learner_id 无历史时 logs=[]）。"""
    r = _client().get("/api/meta-log/test_v028_meta_001?limit=5")
    assert r.status_code == 200
    body = r.get_json()
    assert "logs" in body and isinstance(body["logs"], list)
    assert "total" in body and isinstance(body["total"], int)
    assert body["total"] == 0, f"新 learner_id 应无历史日志，实际 total={body['total']}"
    print(f"[OK] /api/meta-log 返回 logs/total（空用户 total=0）")


def test_quote_returns_text_author():
    """GET /api/quote 应返回 text/author/date 字段（每日一句）。"""
    r = _client().get("/api/quote")
    assert r.status_code == 200
    body = r.get_json()
    for f in ("text", "author"):
        assert f in body and body[f], f"quote 缺字段或为空 {f}：{body}"
    assert isinstance(body["text"], str) and len(body["text"]) > 0
    print(f"[OK] /api/quote → {body['author']}: {body['text'][:30]}...")


# ─────────────────────────────────────
# B. 注册 / 登录 / 画像
# ─────────────────────────────────────


def test_register_creates_user_with_user_id():
    """POST /api/register 应创建 u<id> 用户，body 含 ok/user_id/nickname。"""
    email = _unique_email("reg")
    r = _client().post("/api/register", json={
        "identifier": email, "password": "TestPwd_123", "nickname": "注册测试",
    })
    assert r.status_code == 200, f"应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    assert body.get("ok") is True
    uid = body.get("user_id", "")
    assert uid.startswith("u") and uid[1:].isdigit(), f"user_id 应为 u<数字>，实际 {uid!r}"
    assert body.get("nickname") == "注册测试"
    print(f"[OK] 注册成功 → user_id={uid}")


def test_register_duplicate_returns_error():
    """重复注册同邮箱 → ok=False（400）。"""
    email = _unique_email("dup")
    client = _client()
    r1 = client.post("/api/register", json={
        "identifier": email, "password": "TestPwd_123", "nickname": "第一次",
    })
    assert r1.status_code == 200 and r1.get_json().get("ok") is True
    r2 = client.post("/api/register", json={
        "identifier": email, "password": "TestPwd_456", "nickname": "第二次",
    })
    assert r2.status_code == 400, f"重复注册应 400，实际 {r2.status_code}"
    body2 = r2.get_json()
    assert body2.get("ok") is False
    assert "已注册" in (body2.get("error") or ""), \
        f"错误信息应含'已注册'，实际 {body2.get('error')!r}"
    print(f"[OK] 重复注册被拒绝：{body2['error']}")


def test_register_invalid_email_returns_error():
    """无效邮箱/手机号 → 400 + ok=False。"""
    r = _client().post("/api/register", json={
        "identifier": "not_an_email", "password": "TestPwd_123", "nickname": "x",
    })
    assert r.status_code == 400
    body = r.get_json()
    assert body.get("ok") is False
    print(f"[OK] 无效邮箱被拒绝：{body.get('error')}")


def test_register_short_password_returns_error():
    """密码 < 6 位 → 400。"""
    email = _unique_email("pwd")
    r = _client().post("/api/register", json={
        "identifier": email, "password": "123", "nickname": "x",
    })
    assert r.status_code == 400
    body = r.get_json()
    assert body.get("ok") is False
    assert "密码" in (body.get("error") or ""), f"错误应含'密码'，实际 {body.get('error')!r}"
    print(f"[OK] 短密码被拒绝：{body['error']}")


def test_login_returns_user_id_and_nickname():
    """POST /api/login 成功 → 返回 ok + user_id + nickname。"""
    email = _unique_email("login")
    password = "TestPwd_123"
    client = _client()
    r1 = client.post("/api/register", json={
        "identifier": email, "password": password, "nickname": "登录测试",
    })
    uid = r1.get_json()["user_id"]

    r2 = client.post("/api/login", json={"identifier": email, "password": password})
    assert r2.status_code == 200, f"登录应 200，实际 {r2.status_code} {r2.get_data(as_text=True)}"
    body = r2.get_json()
    assert body.get("ok") is True
    assert body.get("user_id") == uid
    assert body.get("nickname") == "登录测试"
    print(f"[OK] 登录成功 → user_id={body['user_id']}, nickname={body['nickname']}")


def test_login_wrong_password_returns_error():
    """错误密码 → 401 + ok=False。"""
    email = _unique_email("wpwd")
    client = _client()
    client.post("/api/register", json={
        "identifier": email, "password": "TestPwd_123", "nickname": "x",
    })
    r = client.post("/api/login", json={"identifier": email, "password": "WRONG_PWD"})
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("ok") is False
    print(f"[OK] 错误密码 → 401：{body.get('error')}")


def test_register_login_token_round_trip():
    """完整链路：注册 → 登录 → 验证 user_id/nickname 一致。"""
    client = _client()
    info = _register_and_login(client, tag="round")
    assert info["user_id"].startswith("u")
    assert info["nickname"].startswith("测试_")
    print(f"[OK] 注册+登录闭环通过 user_id={info['user_id']}")


def test_profile_put_updates_and_get_reflects():
    """PUT /api/profile/<u_id> 后 GET 应反映最新字段。"""
    client = _client()
    info = _register_and_login(client, tag="profile")
    uid = info["user_id"]

    # PUT 更新
    r_put = client.put(f"/api/profile/{uid}", json={
        "nickname": "新昵称",
        "grade_level": "undergraduate",
        "self_description": "我是测试学生",
        "cognitive_style": "reading",
    })
    assert r_put.status_code == 200, f"PUT 应 200，实际 {r_put.status_code} {r_put.get_data(as_text=True)}"
    body_put = r_put.get_json()
    assert body_put.get("ok") is True
    assert body_put["learner"]["nickname"] == "新昵称"
    assert body_put["learner"]["grade_level"] == "undergraduate"

    # GET 应反映
    r_get = client.get(f"/api/profile/{uid}")
    assert r_get.status_code == 200
    body_get = r_get.get_json()
    assert body_get["nickname"] == "新昵称"
    assert body_get["grade_level"] == "undergraduate"
    assert body_get["self_description"] == "我是测试学生"
    assert body_get["cognitive_style"] == "reading"
    # 必备字段完整性
    for f in ("id", "nickname", "grade_level", "age", "cognitive_style", "self_description"):
        assert f in body_get, f"profile GET 缺字段 {f}"
    print(f"[OK] profile PUT→GET 一致：nickname={body_get['nickname']}, grade={body_get['grade_level']}")


def test_profile_put_creates_if_missing():
    """PUT /api/profile/<新 id>（未在 SESSIONS）应按需创建（不报错）。"""
    client = _client()
    new_id = f"web_v028_new_{int(time.time())}"
    r = client.put(f"/api/profile/{new_id}", json={
        "nickname": "首次创建",
        "grade_level": "high_school",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    print(f"[OK] profile PUT 按需创建：id={new_id}")


def test_profile_get_creates_anon_if_missing():
    """GET /api/profile/<新匿名 id> 应自动创建默认画像（不返回 404）。"""
    client = _client()
    new_id = f"web_v028_anon_{int(time.time())}"
    r = client.get(f"/api/profile/{new_id}")
    assert r.status_code == 200, f"GET 应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    assert body["id"] == new_id
    assert "nickname" in body and "grade_level" in body
    print(f"[OK] profile GET 自动创建匿名画像")


# ─────────────────────────────────────
# C. 文件上传
# ─────────────────────────────────────


def test_upload_chat_image_returns_url():
    """POST /api/upload（multipart，image）应返回 ok + filename + url。"""
    client = _client()
    uid = f"v028_upload_{int(time.time())}"
    # 构造临时 PNG
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="v028_")
    tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    tmp.close()
    try:
        with open(tmp.name, "rb") as f:
            r = client.post(
                "/api/upload",
                data={"learner_id": uid, "file": (f, os.path.basename(tmp.name), "image/png")},
                content_type="multipart/form-data",
            )
        assert r.status_code == 200, f"上传应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body.get("ok") is True
        assert "filename" in body and "url" in body
        assert body["url"].startswith("/uploads/")
        # 验证文件确实落盘
        uploads_dir = os.path.join(
            os.path.dirname(os.path.abspath(os.path.join(__file__, ".."))),
            "uploads", uid,
        )
        saved_files = os.listdir(uploads_dir) if os.path.isdir(uploads_dir) else []
        assert any(f.endswith(".png") for f in saved_files), \
            f"上传文件未落盘到 uploads/{uid}/，实际文件={saved_files}"
    finally:
        os.unlink(tmp.name)
        # 清理真实上传目录
        uploads_dir = os.path.join(
            os.path.dirname(os.path.abspath(os.path.join(__file__, ".."))),
            "uploads", uid,
        )
        shutil.rmtree(uploads_dir, ignore_errors=True)
    print(f"[OK] /api/upload (image) → {body['url']}")


def test_upload_unsupported_extension_returns_400():
    """上传不允许的扩展名 → 400。"""
    client = _client()
    uid = f"v028_upbad_{int(time.time())}"
    tmp = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
    tmp.write(b"x")
    tmp.close()
    try:
        with open(tmp.name, "rb") as f:
            r = client.post(
                "/api/upload",
                data={"learner_id": uid, "file": (f, "evil.exe", "application/octet-stream")},
                content_type="multipart/form-data",
            )
        assert r.status_code == 400, f".exe 应 400，实际 {r.status_code}"
        body = r.get_json()
        assert "不支持的格式" in (body.get("error") or ""), \
            f"错误信息应含'不支持的格式'，实际 {body}"
    finally:
        os.unlink(tmp.name)
    print(f"[OK] 上传非法扩展名被拒绝：{body['error']}")


def test_upload_library_purpose_saves_to_usr_knowledge():
    """purpose=library 应把文件存到 Library/usr_knowledge/<uid>/ 下。"""
    client = _client()
    uid = f"v028_lib_{int(time.time())}"
    tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
    tmp.write("# 测试资料\n\n这是测试内容。\n".encode("utf-8"))
    tmp.close()
    try:
        with open(tmp.name, "rb") as f:
            r = client.post(
                "/api/upload",
                data={
                    "learner_id": uid,
                    "purpose": "library",
                    "file": (f, "test_doc.md", "text/markdown"),
                },
                content_type="multipart/form-data",
            )
        assert r.status_code == 200, f"library 上传应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body.get("ok") is True
        assert "library_path" in body
        assert "usr_knowledge" in body["library_path"]
        # 实际文件应存在
        from lib import library_store
        lib_dir = library_store.resolve_library_root(uid)
        files = os.listdir(lib_dir) if lib_dir.exists() else []
        assert any(f.endswith(".md") for f in files), \
            f"library 文件未落盘到 {lib_dir}，实际={files}"
    finally:
        os.unlink(tmp.name)
        # 清理资料目录
        from lib import library_store
        shutil.rmtree(library_store.resolve_library_root(uid), ignore_errors=True)
    print(f"[OK] /api/upload (library) → {body['library_path']}")


def test_avatar_upload_returns_url_and_saves_file():
    """POST /api/avatar 应保存头像到 uploads/avatar/ 并返回 url。"""
    client = _client()
    uid = f"v028_avatar_{int(time.time())}"
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="v028_avatar_")
    tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    tmp.close()
    try:
        with open(tmp.name, "rb") as f:
            r = client.post(
                "/api/avatar",
                data={"learner_id": uid, "avatar": (f, "avatar.png", "image/png")},
                content_type="multipart/form-data",
            )
        assert r.status_code == 200, f"avatar 上传应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body.get("ok") is True
        assert body["url"].startswith("/uploads/avatar/avatar_")
        # 文件应存在
        project_root = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
        avatar_path = os.path.join(project_root, "uploads", "avatar",
                                    f"avatar_{uid}.png")
        assert os.path.isfile(avatar_path), f"头像文件应存在：{avatar_path}"
    finally:
        os.unlink(tmp.name)
        project_root = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            p = os.path.join(project_root, "uploads", "avatar", f"avatar_{uid}{ext}")
            if os.path.isfile(p):
                os.unlink(p)
    print(f"[OK] /api/avatar → {body['url']}")


def test_avatar_rejects_non_image_extension():
    """/api/avatar 拒绝 .exe/.txt 等非图片扩展。"""
    client = _client()
    uid = f"v028_avbad_{int(time.time())}"
    tmp = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
    tmp.write(b"x")
    tmp.close()
    try:
        with open(tmp.name, "rb") as f:
            r = client.post(
                "/api/avatar",
                data={"learner_id": uid, "avatar": (f, "evil.exe", "application/octet-stream")},
                content_type="multipart/form-data",
            )
        assert r.status_code == 400
        body = r.get_json()
        assert "头像仅支持" in (body.get("error") or ""), \
            f"错误信息应含'头像仅支持'，实际 {body}"
    finally:
        os.unlink(tmp.name)
    print(f"[OK] 头像非图片扩展被拒绝：{body['error']}")


# ─────────────────────────────────────
# D. 会话端点
# ─────────────────────────────────────


def _seed_conversation(user_id: str, title: str = "测试会话", n_msgs: int = 2) -> str:
    """直接通过 server.SESSIONS/CONV_STORE 植入一条会话，返回 conv_id。"""
    from server import CONV_STORE
    cid = CONV_STORE.add_message(user_id, "chat", title, "user", "你好")
    for i in range(n_msgs - 1):
        CONV_STORE.add_message(user_id, "chat", title, "assistant", f"回复 {i}", conv_id=cid)
    return cid


def test_conversations_list_empty_for_new_user():
    """新注册用户（无会话）→ list 返回空数组。"""
    client = _client()
    info = _register_and_login(client, tag="clist")
    uid = info["user_id"]
    r = client.get(f"/api/conversations/{uid}")
    assert r.status_code == 200
    body = r.get_json()
    assert "conversations" in body and isinstance(body["conversations"], list)
    assert body["conversations"] == [], \
        f"新用户应无会话，实际 {body['conversations']}"
    print(f"[OK] /api/conversations 空列表（uid={uid}）")


def test_conversations_list_returns_seeded_conversation():
    """植入一条会话后，list 应返回该会话（含 id/title/mode/message_count）。"""
    client = _client()
    info = _register_and_login(client, tag="clist2")
    uid = info["user_id"]
    cid = _seed_conversation(uid, title="测试历史", n_msgs=2)
    try:
        r = client.get(f"/api/conversations/{uid}")
        assert r.status_code == 200
        body = r.get_json()
        convs = body["conversations"]
        assert any(c["id"] == cid for c in convs), \
            f"植入会话应在列表里，实际 ids={[c['id'] for c in convs]}"
        c = next(c for c in convs if c["id"] == cid)
        assert c["title"] == "测试历史"
        assert c["mode"] == "chat"
        assert c["message_count"] >= 1
    finally:
        # 清理
        from server import CONV_STORE
        CONV_STORE.clear_all(uid)
    print(f"[OK] /api/conversations 列表含植入会话（{cid}）")


def test_conversations_get_single_returns_full_messages():
    """GET /api/conversations/<uid>/<cid> 应返回包含 messages 字段的完整会话。"""
    client = _client()
    info = _register_and_login(client, tag="cget")
    uid = info["user_id"]
    cid = _seed_conversation(uid, title="单条测试", n_msgs=3)
    try:
        r = client.get(f"/api/conversations/{uid}/{cid}")
        assert r.status_code == 200, f"GET 应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body.get("id") == cid
        assert body.get("title") == "单条测试"
        assert "messages" in body and isinstance(body["messages"], list) and len(body["messages"]) >= 2
        for m in body["messages"]:
            assert "role" in m and "content" in m, f"消息字段不全：{m}"
    finally:
        from server import CONV_STORE
        CONV_STORE.clear_all(uid)
    print(f"[OK] /api/conversations/<cid> 返回完整消息")


def test_conversations_get_missing_returns_404():
    """不存在的 conv_id → 404。"""
    client = _client()
    info = _register_and_login(client, tag="cmiss")
    uid = info["user_id"]
    r = client.get(f"/api/conversations/{uid}/c_nonexistent_xyz")
    assert r.status_code == 404, f"不存在会话应 404，实际 {r.status_code}"
    print(f"[OK] /api/conversations 不存在 → 404")


def test_conversations_get_requires_registered():
    """未注册 learner_id（不以 u 开头）→ 401。"""
    client = _client()
    r = client.get("/api/conversations/web_v028_anon/c_xyz")
    assert r.status_code == 401, f"匿名 ID 应 401，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    assert "请先登录" in (body.get("error") or ""), \
        f"错误信息应含'请先登录'，实际 {body}"
    print(f"[OK] /api/conversations 匿名 ID → 401")


def test_conversations_delete_single():
    """DELETE /api/conversations/<uid>/<cid> 应成功删除该会话。"""
    client = _client()
    info = _register_and_login(client, tag="cdel")
    uid = info["user_id"]
    cid = _seed_conversation(uid, title="待删会话", n_msgs=1)
    try:
        r = client.delete(f"/api/conversations/{uid}/{cid}")
        assert r.status_code == 200, f"DELETE 应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body.get("ok") is True
        # 再次 GET → 404
        r2 = client.get(f"/api/conversations/{uid}/{cid}")
        assert r2.status_code == 404, f"删除后 GET 应 404，实际 {r2.status_code}"
    finally:
        from server import CONV_STORE
        CONV_STORE.clear_all(uid)
    print(f"[OK] DELETE /api/conversations/<cid> 成功 + 再查 404")


def test_conversations_delete_all_clears_list():
    """DELETE /api/conversations/<uid>（不带 cid）应清空全部会话。"""
    client = _client()
    info = _register_and_login(client, tag="cdelall")
    uid = info["user_id"]
    _seed_conversation(uid, title="会话A", n_msgs=1)
    _seed_conversation(uid, title="会话B", n_msgs=1)
    try:
        r = client.delete(f"/api/conversations/{uid}")
        assert r.status_code == 200
        assert r.get_json().get("ok") is True
        # 列表应为空
        r2 = client.get(f"/api/conversations/{uid}")
        body2 = r2.get_json()
        assert body2["conversations"] == [], \
            f"清空后会话应为空，实际 {body2['conversations']}"
    finally:
        from server import CONV_STORE
        CONV_STORE.clear_all(uid)
    print(f"[OK] DELETE /api/conversations/<uid> 清空全部")


# ─────────────────────────────────────
# E. 自更新端点
# ─────────────────────────────────────


def test_self_update_status_returns_scheduler_info():
    """GET /api/self-update/status 应返回 ok + thread_alive + interval_hours 等。"""
    r = _client().get("/api/self-update/status")
    assert r.status_code == 200, f"应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    for f in ("ok", "thread_alive", "interval_hours", "last_weekly", "last_activity"):
        assert f in body, f"/api/self-update/status 缺字段 {f}，body={list(body.keys())}"
    assert body["ok"] is True
    assert isinstance(body["thread_alive"], bool)
    assert isinstance(body["interval_hours"], (int, float))
    assert body["interval_hours"] > 0
    print(f"[OK] /api/self-update/status interval={body['interval_hours']}h, alive={body['thread_alive']}")


def test_self_update_run_executes_and_returns_result():
    """POST /api/self-update/run 应返回 ok=True + result 字段（不抛异常）。"""
    r = _client().post("/api/self-update/run")
    assert r.status_code == 200, f"应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    assert body.get("ok") is True
    assert "result" in body, f"应含 result 字段，body={list(body.keys())}"
    # result 是 PeriodicSelfUpdater.run_now 的返回值（dict）
    assert isinstance(body["result"], dict)
    print(f"[OK] /api/self-update/run → result keys={list(body['result'].keys())}")


# ─────────────────────────────────────
# F. 其他端点
# ─────────────────────────────────────


def test_skills_returns_non_empty_list():
    """GET /api/skills 应返回 skills 列表 + total + source。"""
    r = _client().get("/api/skills")
    assert r.status_code == 200, f"应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    for f in ("skills", "total", "source"):
        assert f in body, f"/api/skills 缺字段 {f}，body={list(body.keys())}"
    assert isinstance(body["skills"], list)
    assert body["total"] == len(body["skills"])
    assert body["total"] > 0, f"技能列表不应为空，实际 total={body['total']}"
    # 每个 skill 应含 id/name/definition
    s0 = body["skills"][0]
    for f in ("id", "name", "definition", "source"):
        assert f in s0, f"skill 缺字段 {f}，实际 {s0}"
    print(f"[OK] /api/skills → total={body['total']}, source={body['source']}")


def test_batch_returns_result():
    """POST /api/batch 应返回 batch_update 结果（recurring_concepts/total_sessions 等）。"""
    r = _client().post("/api/batch")
    assert r.status_code == 200, f"应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
    body = r.get_json()
    for f in ("recurring_concepts", "total_sessions", "strategies_discovered_count", "version"):
        assert f in body, f"/api/batch 缺字段 {f}，body={list(body.keys())}"
    assert isinstance(body["total_sessions"], int) and body["total_sessions"] >= 0
    assert isinstance(body["version"], int)
    print(f"[OK] /api/batch → total_sessions={body['total_sessions']}, version={body['version']}")


if __name__ == "__main__":
    funcs = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    fails = 0
    for n, f in funcs:
        try:
            f()
        except Exception as e:
            import traceback
            fails += 1
            print(f"[FAIL] {n}: {e}")
            traceback.print_exc()
    print(f"\n{len(funcs) - fails}/{len(funcs)} passed")