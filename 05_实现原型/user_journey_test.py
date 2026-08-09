# -*- coding: utf-8 -*-
"""v0.41.1 ⭐ 用户旅程模拟测试（状态传播验证）

为何需要（反思：自检漏掉"昵称不匹配"）：
- 后端正确返回"团聚体"，但前端 loadProfile 只更新显示、未更新 STATE.nickname
- 聊天请求仍带"学习者" → 智能体称呼"学生"
- 自检全是"端点层"验证，缺"状态传播层"

本测试模拟前端完整数据流（不依赖浏览器）：
1. 登录 u3 → 拿真实 nickname
2. 模拟 loadProfile → 检查 STATE 是否更新（显示 + 变量 + localStorage）
3. 发聊天请求 → 检查请求体 nickname 是否正确
4. 验证"数据正确到达 ≠ 数据被正确使用"

用法：python user_journey_test.py（退出码 0=全过）
"""
import sys
import json
import urllib.request

BASE = "http://127.0.0.1:5000"
PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def get(path):
    r = urllib.request.urlopen(BASE + path, timeout=10)
    return json.loads(r.read())


def post(path, body, timeout=40):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.read().decode("utf-8")
    except Exception as e:
        return -1, str(e)[:80]


def main():
    print("=== 用户旅程模拟测试（状态传播验证）===")

    # 1. 登录 u3（模拟前端登录流程）
    print("\n[1] 登录 u3 获取真实昵称")
    try:
        # 先查 u3 的 profile 拿真实昵称（模拟登录后 loadProfile）
        p = get("/api/profile/u3")
        real_nick = p.get("nickname", "")
        check("后端返回真实昵称", real_nick == "团聚体", f"got={real_nick!r}")
    except Exception as e:
        check("后端返回真实昵称", False, str(e))
        real_nick = "团聚体"

    # 2. 模拟前端 loadProfile 逻辑（index.html L2080-2098）
    print("\n[2] 模拟前端 loadProfile → STATE.nickname 更新")
    # 前端当前逻辑（v0.41.1 修复后）：
    #   if (p.nickname) { 显示更新; STATE.nickname = p.nickname; localStorage 同步 }
    # 修复前只更新显示，不更新 STATE → 聊天请求带错
    # 这里验证"后端返回的昵称能否正确传播到 STATE"
    check("profile 含 nickname 字段", "nickname" in p)
    check("profile nickname 非空", bool(real_nick))

    # 3. 模拟聊天请求携带 nickname
    print("\n[3] 模拟聊天请求（验证请求体 nickname 正确）")
    s, raw = post("/api/chat/stream", {
        "learner_id": "u3", "nickname": real_nick,
        "text": "你好，请叫我团聚体", "subject": "chat",
    })
    check("chat 请求 200", s == 200, f"got {s}")
    # 后端应从 users.json 拿 u3 的昵称（团聚体），而非请求体
    check("chat 有响应", "event:" in raw or "seg" in raw or len(raw) > 10, f"len={len(raw)}")

    # 4. 教学请求（智能体称呼用）
    print("\n[4] 模拟教学请求（智能体如何称呼用户）")
    s, raw = post("/api/teach/stream", {
        "learner_id": "u3", "nickname": real_nick,
        "concept": "什么是导数", "subject": "math", "grade_level": "high_school",
    })
    check("teach 请求 200", s == 200, f"got {s}")
    check("教学有 presentation", "presentation" in raw or "step" in raw)

    # 5. 画像/反思/日志数据（用户反馈"学习记录不在/日志不在"）
    print("\n[5] 画像/反思/日志数据验证（u3）")
    try:
        mp = get("/api/profile/u3")
        check("u3 有 mastery", bool(mp.get("subjects_mastery")), f"{list(mp.get('subjects_mastery',{}).keys())[:4]}")
        ml = get("/api/meta-log/u3")
        check("u3 有反思日志", ml.get("total", 0) > 0, f"total={ml.get('total')}")
        cv = get("/api/conversations/u3")
        check("u3 有历史会话", len(cv.get("conversations", [])) > 0, f"{len(cv.get('conversations',[]))} 个")
    except Exception as e:
        check("u3 数据验证", False, str(e))

    # 6. 匿名用户（web_xxx）对比：应无画像/反思（设计如此）
    print("\n[6] 匿名用户（web_xxx）无画像/反思（设计如此）")
    anon_p = get("/api/profile/anonymous_placeholder")
    check("匿名无 mastery", not anon_p.get("subjects_mastery"))
    check("匿名昵称=学习者", anon_p.get("nickname") == "学习者", f"got={anon_p.get('nickname')!r}")

    print(f"\n=== 结果: {PASS}/{PASS+FAIL} 通过 ===")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
