# -*- coding: utf-8 -*-
"""v0.25 压力测试 · 多轮对话实验（按 subagent 功能 + 链路 + MCP）

覆盖（用户要求）：
- 各 subagent 功能完整性/真实性检测
- 注意力丧失 / 答非所问检测（多轮金句-干扰-追问）
- 多轮上下文保持（个体化画像持续生效）
- v0.25 新功能：3 新学科 / 学段联动 / PPT MCP / SelfUpdateAgent 执行器
- MCP 连接真实性与链路
"""
import sys, io, os, json, time, re, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.environ.get("PAEG_BASE", "http://localhost:5000")

def _req(url, payload, timeout=120):
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8')
    except Exception as e:
        return 0, f"[ERR] {e}"

def _get(url, timeout=30):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

def call_stream(text, mode, uid, subject="math", grade="high_school"):
    """调用端点返回文本。"""
    url, payload = None, None
    if mode == "teach":
        url = f"{BASE}/api/teach/stream"
        payload = {"concept": text, "subject": subject, "learner_id": uid,
                   "nickname": "测试", "grade_level": grade}
    elif mode == "answer":
        url = f"{BASE}/api/answer"
        payload = {"question": text, "subject": subject, "learner_id": uid,
                   "nickname": "测试", "grade_level": grade}
    elif mode == "affection":
        url = f"{BASE}/api/affection"
        payload = {"text": text, "learner_id": uid, "nickname": "测试", "grade_level": grade}
    elif mode == "chat":
        url = f"{BASE}/api/chat/stream"
        payload = {"text": text, "learner_id": uid, "nickname": "测试", "grade_level": grade}
    elif mode == "knowledge":
        url = f"{BASE}/api/knowledge"
        payload = {"text": text, "learner_id": uid, "grade_level": grade}
    if url and payload:
        st, body = _req(url, payload)
        if st == 200 and body:
            return body
        return f"[ERR:http{st}]"
    return "[ERR:no_endpoint]"

def _has_any(text, keywords):
    return sum(1 for k in keywords if k and k.lower() in (text or "").lower())

def _clean(text):
    """从 SSE 流或 JSON 提取内容文本（处理 unicode 转义）。"""
    if not text or text.startswith('['): return text or ''
    # 尝试 json.loads（JSON 响应如 affection）
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            for key in ['content', 'reply', 'answer']:
                if obj.get(key):
                    return str(obj[key])[:800]
            prs = obj.get('presentations') or []
            if prs and isinstance(prs[0], dict) and prs[0].get('content'):
                return str(prs[0]['content'])[:800]
    except Exception:
        pass
    # SSE 流：优先 text 字段（chat_stream seg 事件），再 content 字段
    for field in ['"text"', '"content"']:
        parts = re.findall(field + r'\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if parts:
            out = ''.join(parts)
            try:
                out = json.loads('"' + out.replace('"', '\\"') + '"')
            except Exception:
                pass
            out = out.replace('\\n', '\n').replace('\\"', '"')
            return out[:800]
    return text[:800]

def run_health():
    """T7: MCP 连接真实性"""
    h = _get(f"{BASE}/api/health")
    print("  /api/health:", {k: h.get(k) for k in ['mcp_connected', 'mcp_status', 'skill_count', 'agent_engine_ready'] if k in h})
    return {
        "mcp_connected": h.get("mcp_connected"),
        "skill_count": h.get("skill_count"),
        "pass": "3/3" in str(h.get("mcp_connected")) and h.get("skill_count") == 10,
    }

def run_attention_multi_turn():
    """T2: 注意力-上下文保持（埋金句→干扰→追问，检测答非所问）"""
    uid = "v25_att_1"
    results = []
    # 场景1: 教学闭环多轮
    r1 = _clean(call_stream("请给我讲一下什么是导数", "teach", uid, "math"))
    hit1 = _has_any(r1, ["导数", "斜率", "变化率"])
    # 干扰轮
    _clean(call_stream("顺便问一下今天天气如何", "chat", uid))
    _clean(call_stream("你能给我讲个笑话吗", "chat", uid))
    # 追问金句（应该回到导数）
    r2 = _clean(call_stream("刚才我们讲到哪里了？导数的核心是什么？", "teach", uid, "math"))
    hit2 = _has_any(r2, ["导数", "斜率", "变化率"])
    # 答非所问检测：追问应含导数相关内容而非笑话
    off_topic = _has_any(r2, ["笑话", "天气"]) > 0 and hit2 == 0
    results.append({
        "name": "教学多轮注意力", "setup_hit": hit1, "recall_hit": hit2,
        "off_topic": off_topic,
        "pass": hit1 > 0 and hit2 > 0 and not off_topic,
    })
    # 场景2: 聊天多轮上下文
    c1 = _clean(call_stream("我喜欢蓝绿色，还喜欢数学", "chat", uid))
    c2 = _clean(call_stream("我喜欢的颜色是什么？", "chat", uid))
    hit_c = _has_any(c2, ["蓝绿", "蓝绿色"])
    results.append({
        "name": "聊天上下文保持", "recall_hit": hit_c,
        "pass": hit_c > 0,
    })
    return results

def run_individuality_multi_turn():
    """T3: 个体化画像多轮持续生效"""
    uid = "v25_ind_1"
    results = []
    # 注册用户
    try:
        req = urllib.request.Request(f"{BASE}/api/profile/{uid}",
            data=json.dumps({"grade_level": "undergraduate", "self_description": "I am a French student, weak at algebra, prefer visual learning"}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='PUT')
        with urllib.request.urlopen(req, timeout=30): pass
    except Exception as e:
        print("  profile:", e)
    # 对话1：声明偏好
    _clean(call_stream("我代数很弱，喜欢用图形理解概念", "chat", uid, grade="undergraduate"))
    # 对话2：验证画像注入（问数学方法，应体现个体化）
    r = _clean(call_stream("给我讲讲如何学数学", "chat", uid, grade="undergraduate"))
    hit_visual = _has_any(r, ["图形", "图像", "visual", "可视化"])
    hit_algebra = _has_any(r, ["代数"])
    results.append({
        "name": "个体化画像持续注入", "hit_visual": hit_visual, "hit_algebra": hit_algebra,
        "pass": hit_visual > 0,
    })
    return results

def run_grade_linkage():
    """T4: 学段-学科联动（高中生/本科生用不同 uid 避免画像残留）"""
    results = []
    # 高中生问语言学 → 学段拦截（全新 uid）
    uid_h = "v25_grade_high_" + str(int(time.time() * 1000) % 100000)
    r = call_stream("什么是音位", "teach", uid_h, "linguistics", grade="high_school")
    blocked = "学段" in r or "本科" in r or "grade_blocked" in r
    results.append({"name": "高中生问语言学拦截", "blocked": blocked, "pass": blocked})
    # 本科生问语言学 → 正常（全新 uid）
    uid_u = "v25_grade_uni_" + str(int(time.time() * 1000) % 100000)
    r2 = call_stream("什么是音位", "teach", uid_u, "linguistics", grade="undergraduate")
    normal = _has_any(r2, ["音位"]) > 0
    results.append({"name": "本科生问语言学正常", "normal": normal, "pass": normal})
    return results

def run_new_subjects():
    """T5: 新学科教学功能"""
    uid = "v25_subj_1"
    results = []
    for subj, q, kws in [
        ("linguistics", "语言为什么是符号系统", ["符号", "任意"]),
        ("atmospheric_science", "为什么会出现台风", ["台风", "气压", "热带"]),
        ("qft", "什么是量子场论中的场", ["场", "量子", "激发"]),
    ]:
        r = _clean(call_stream(q, "teach", uid, subj, grade="undergraduate"))
        hit = _has_any(r, kws)
        results.append({"name": f"新学科[{subj}]", "hit": hit, "pass": hit > 0})
    return results

def run_intent_routing():
    """T6: 意图路由（答非所问检测）"""
    uid = "v25_route_1"
    results = []
    # 情绪 → 陪伴（不是讲题，全新 uid）
    r_aff_raw = call_stream("我今天好难过，感觉撑不住了", "affection", uid + "_" + str(int(time.time() * 1000) % 1000))
    r_aff = _clean(r_aff_raw)
    aff_hit = _has_any(r_aff, ["难过", "陪伴", "累", "撑", "撑不住"])
    results.append({"name": "情绪路由", "hit": aff_hit, "pass": aff_hit > 0})
    # 知识查询 → 知识库
    r_kb = call_stream("知识库里有导数的内容吗", "knowledge", uid)
    results.append({"name": "知识路由", "status": r_kb[:50], "pass": r_kb and not r_kb.startswith("[ERR")})
    return results

def run_self_update_link():
    """T8: 自我更新链路"""
    uid = "v25_su_1"
    results = []
    # 反馈 → SelfUpdateAgent 建议
    r = _req(f"{BASE}/api/self-update/from-feedback", {"feedback": "建议新增心理学学科", "learner_id": uid, "text": "建议新增心理学学科"})
    results.append({"name": "自我更新反馈链路", "status": r[0], "body": r[1][:150], "pass": r[0] == 200})
    return results

def main():
    print("=" * 60)
    print("PAEG v0.25 压力测试 · 多轮对话实验")
    print("=" * 60)
    summary = {}

    print("\n[T7] MCP 连接真实性:")
    h = run_health()
    summary["T7_MCP"] = h
    print("  →", "PASS" if h.get("pass") else "FAIL", h)

    print("\n[T2] 注意力-上下文保持（重点：答非所问检测）:")
    att = run_attention_multi_turn()
    for r in att:
        print("  ", r["name"], "→", "PASS" if r["pass"] else "FAIL", {k: v for k, v in r.items() if k != "name" and k != "pass"})
    summary["T2_attention"] = att

    print("\n[T3] 个体化画像多轮:")
    ind = run_individuality_multi_turn()
    for r in ind:
        print("  ", r["name"], "→", "PASS" if r["pass"] else "FAIL", {k: v for k, v in r.items() if k != "name" and k != "pass"})
    summary["T3_individuality"] = ind

    print("\n[T4] 学段-学科联动:")
    g = run_grade_linkage()
    for r in g:
        print("  ", r["name"], "→", "PASS" if r["pass"] else "FAIL", {k: v for k, v in r.items() if k != "name" and k != "pass"})
    summary["T4_grade"] = g

    print("\n[T5] 新学科教学:")
    ns = run_new_subjects()
    for r in ns:
        print("  ", r["name"], "→", "PASS" if r["pass"] else "FAIL", {k: v for k, v in r.items() if k != "name" and k != "pass"})
    summary["T5_subjects"] = ns

    print("\n[T6] 意图路由:")
    rt = run_intent_routing()
    for r in rt:
        print("  ", r["name"], "→", "PASS" if r["pass"] else "FAIL", {k: v for k, v in r.items() if k != "name" and k != "pass"})
    summary["T6_routing"] = rt

    print("\n[T8] 自我更新链路:")
    su = run_self_update_link()
    for r in su:
        print("  ", r["name"], "→", "PASS" if r["pass"] else "FAIL", r.get("status"), r.get("body", "")[:80])
    summary["T8_selfupdate"] = su

    # 汇总
    all_items = []
    for k, v in summary.items():
        if isinstance(v, list):
            all_items.extend(v)
        elif isinstance(v, dict) and "pass" in v:
            all_items.append(v)
    passed = sum(1 for x in all_items if x.get("pass"))
    total = len(all_items)
    print("\n" + "=" * 60)
    print(f"汇总: {passed}/{total} 项通过")
    print("=" * 60)
    return summary

if __name__ == "__main__":
    main()
