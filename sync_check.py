# -*- coding: utf-8 -*-
"""PAEG 三处一致性校验脚本（本地目录 ↔ GitHub ↔ Release）
用法: python sync_check.py [--fix]
--fix: 自动推送本地差异文件到 GitHub（本地为权威源）
敏感文件（users.json/users_data/uploads/data 等运行时数据）不参与校验。
注意：token 从环境变量 GH_TOKEN 读取（勿硬编码密钥到脚本）。
"""
import sys, os, json, base64, hashlib, urllib.request, urllib.parse, datetime

TOKEN = os.environ.get("GH_TOKEN", "")
if not TOKEN:
    print("[WARN] 未设置 GH_TOKEN 环境变量——将以只读模式校验（跳过推送）")
    FIX_MODE = False
else:
    FIX_MODE = "--fix" in sys.argv
REPO = "Golden2002/PAEG"
BRANCH = "main"
BASE = r"D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目"
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"} if TOKEN else {"Accept": "application/vnd.github+json"}
# 敏感/运行时数据——不参与"互为备份"（非代码资产）
SENSITIVE_FILES = {"users.json", "profile.json", "conversations.json", "reflections.json", "history.jsonl", "insights.json"}

def api(url, method="GET", body=None):
    req = urllib.request.Request(url, method=method, headers=HEADERS)
    data = json.dumps(body).encode("utf-8") if body else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": e.code, "msg": e.read().decode("utf-8")[:150]}

def build_local_map():
    m = {}
    for fn in os.listdir(BASE):
        p = os.path.join(BASE, fn)
        if os.path.isfile(p) and (fn.endswith(".md") or fn.endswith(".py") or fn.endswith(".txt")):
            m[fn] = p
    for fn in os.listdir(os.path.join(BASE, "09_GUI前端")):
        p = os.path.join(BASE, "09_GUI前端", fn)
        if os.path.isfile(p) and (fn.endswith(".html") or fn.endswith(".js") or fn.endswith(".css") or fn.endswith(".json")):
            m[f"09_GUI前端/{fn}"] = p
    proto = os.path.join(BASE, "05_实现原型")
    for fn in os.listdir(proto):
        if fn in SENSITIVE_FILES: continue
        p = os.path.join(proto, fn)
        if os.path.isfile(p) and (fn.endswith(".py") or fn.endswith(".json") or fn.endswith(".txt") or fn.endswith(".md")):
            m[f"05_实现原型/{fn}"] = p
    tdir = os.path.join(proto, "tests")
    if os.path.isdir(tdir):
        for fn in os.listdir(tdir):
            if fn.endswith(".py"):
                m[f"05_实现原型/tests/{fn}"] = os.path.join(tdir, fn)
    return m

def sha_of_file(local):
    raw = open(local, "rb").read()
    text = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8")
    return hashlib.sha1(("blob %d\0" % len(text.encode("utf-8"))).encode() + text.encode("utf-8")).hexdigest()

def main():
    tree = api(f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1")
    if "error" in tree:
        print(f"[FAIL] 无法获取 GitHub tree: {tree}"); sys.exit(1)
    gh = {i["path"]: i["sha"] for i in tree.get("tree", []) if i["type"] == "blob"}
    local = build_local_map()
    ok, missing, diff = 0, [], []
    for gpath, lpath in sorted(local.items()):
        if not os.path.exists(lpath):
            print(f"  [本地缺失] {gpath}"); continue
        lsha = sha_of_file(lpath)
        gsha = gh.get(gpath)
        if gsha is None:
            missing.append(gpath); print(f"  [GH缺失] {gpath}")
        elif gsha == lsha:
            ok += 1
        else:
            diff.append(gpath); print(f"  [差异] {gpath}")
    print(f"\n=== 本地↔GitHub: 一致 {ok} / GH缺失 {len(missing)} / 差异 {len(diff)} ===")
    if missing: print(f"GitHub缺失: {missing}")
    if diff and FIX_MODE and TOKEN:
        print("[FIX] 推送差异文件（本地为权威）...")
        for gpath in diff:
            path = urllib.parse.quote(gpath, safe="")
            cur = api(f"https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}")
            raw = open(local[gpath], "rb").read()
            text = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8")
            body = {"message": "sync: 三处一致性备份", "content": base64.b64encode(text.encode("utf-8")).decode("ascii"), "branch": BRANCH}
            if cur.get("sha"): body["sha"] = cur["sha"]
            r = api(f"https://api.github.com/repos/{REPO}/contents/{path}", method="PUT", body=body)
            print(f"  {'OK' if 'error' not in r else 'FAIL'} {gpath}")
    rel = api(f"https://api.github.com/repos/{REPO}/releases/tags/v0.26")
    if "error" not in rel:
        print(f"=== Release: {rel['name']} (tag v0.26) ===")
        print(f"  更新: {rel['published_at']}")
    else:
        print("[WARN] Release 查询失败")
    print(f"校验完成 @ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
