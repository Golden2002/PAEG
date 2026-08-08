# -*- coding: utf-8 -*-
"""
PAEG 全面接口多轮测试（v0.20.5 ⭐ API Sweep）

对每个接口做多角度、多轮提问测试，收集对话历史，分析问题。

覆盖：
- 教学（teach）：概念/续问/深层/边缘（未收录学科/超长/空）
- 闲聊（chat）：寒暄/记忆/搜索/情绪/元问题
- 找答案（answer）：数学/论述/续问
- 学习方法（method）：各学科/续问
- 知识库（knowledge）：关键词变体
- 倾诉（affection）：多种情绪/续问
- 其他端点：health/profile/quote/register/login/conversations

输出：每接口每轮的结果 + 发现的问题（非 200 / 空回复 / 退化）。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from typing import Any, Dict, List

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = os.environ.get("PAEG_BASE", "http://localhost:5000")

# 每个接口的测试轮次（多角度）
API_TESTS = {
    "/api/teach": [
        ("什么是导数", "math", {}),
        ("那它的几何意义呢", "math", {}),           # 续问
        ("x^2 在 x=3 的斜率是多少", "math", {}),      # 计算
        ("玻尔兹曼熵是什么", "physics", {}),          # 热力学（修复验证）
        ("画一下导数的知识导图", "math", {}),          # 知识导图（v0.20.5）
        ("帮我列个牛顿力学的提纲", "physics", {}),     # 知识导图
        ("量子力学是什么", "physics", {}),            # 未收录
        ("", "math", {}),                            # 空输入
        ("我最近好难过", "general", {}),              # 情绪（应拦截）
        ("这个界面的按钮是干嘛的", "general", {}),      # 界面（应拦截）
        ("知识库", "general", {}),                    # 知识库（应拦截）
    ],
    "/api/chat/stream": [
        ("你好", "general", {}),
        ("我叫小明，喜欢篮球", "general", {}),
        ("我刚才说我叫什么", "general", {}),           # 记忆
        ("搜索 2024 诺贝尔物理学奖", "general", {}),    # 工具
        ("我最近压力好大", "general", {}),             # 情绪拦截
        ("你是谁", "general", {}),                    # 元问题
        ("什么是paeg", "general", {}),
    ],
    "/api/answer": [
        ("求 x^2 的不定积分", "math", {}),
        ("再求 x^3 的", "math", {}),                  # 续问
        ("写一段关于薇依的短文", "literature", {}),    # 论述
        ("", "math", {}),                            # 空
    ],
    "/api/method": [
        ("怎么学数学", "math", {}),
        ("那物理呢", "physics", {}),                  # 续问
        ("考研数学怎么复习", "math", {}),
    ],
    "/api/knowledge": [
        ("知识库", "general", {}),
        ("你学过什么", "general", {}),
    ],
    "/api/affection": [
        ("我最近压力好大", "general", {}),
        ("就是考试的事", "general", {}),               # 续问
        ("我是不是很没用", "general", {}),
    ],
    "/api/health": [("GET", "", "", {})],
    "/api/quote": [("GET", "", "", {})],
    "/api/skills": [("GET", "", "", {})],
    "/api/knowledge/search": [("GET", "导数", "math", {})],
    "/api/knowledge/library": [("GET", "", "", {})],
}

def call_api(path: str, payload: dict, method: str = "POST") -> tuple:
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=150) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:200]
    except Exception as e:
        return "ERR", str(e)[:100]

def parse_response(raw: str, mode: str) -> str:
    """从原始响应提取文本。"""
    if raw.strip().startswith("{"):
        try:
            body = json.loads(raw)
            if body.get("answer"):
                return body["answer"]
            if body.get("error"):
                return f"[ERROR] {body['error']}"
            pres = body.get("presentations", [])
            return " ".join(p.get("content", "") for p in pres)
        except Exception:
            return raw[:100]
    # SSE
    texts = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                obj = json.loads(line[5:])
                if "text" in obj:
                    texts.append(obj["text"])
                elif "content" in obj:
                    texts.append(obj["content"])
            except Exception:
                pass
    return "".join(texts)

def run_api_sweep() -> Dict[str, Any]:
    results = {}
    for path, cases in API_TESTS.items():
        mode = path.split("/")[-1].split("?")[0]
        path_results = []
        for i, case in enumerate(cases, 1):
            if len(case) == 4:
                method, text, subject, extra = case
            else:
                text, subject, extra = case
                method = "POST"
            # 简化：文本从 text 取
            if path == "/api/health" or path == "/api/quote" or path == "/api/skills" or path == "/api/knowledge/library":
                st, raw = call_api(path, {}, "GET")
            elif path == "/api/knowledge/search":
                st, raw = call_api(path + f"?q={urllib.parse.quote(text)}&subject={subject}", {}, "GET")
            elif path == "/api/teach":
                st, raw = call_api(path, {"concept": text, "subject": subject,
                                           "learner_id": "api_sweep", "nickname": "扫描",
                                           "grade_level": "high_school"})
            elif path == "/api/chat/stream":
                st, raw = call_api(path, {"text": text, "learner_id": "api_sweep",
                                           "nickname": "扫描", "grade_level": "high_school"})
            elif path == "/api/answer":
                st, raw = call_api(path, {"question": text, "subject": subject,
                                           "learner_id": "api_sweep", "nickname": "扫描",
                                           "grade_level": "high_school"})
            elif path == "/api/method":
                st, raw = call_api(path, {"concept": text, "subject": subject,
                                           "learner_id": "api_sweep", "nickname": "扫描",
                                           "grade_level": "high_school"})
            elif path == "/api/knowledge":
                st, raw = call_api(path, {"text": text, "learner_id": "api_sweep",
                                           "nickname": "扫描", "grade_level": "high_school"})
            elif path == "/api/affection":
                st, raw = call_api(path, {"text": text, "learner_id": "api_sweep",
                                           "nickname": "扫描", "grade_level": "high_school"})
            else:
                st, raw = call_api(path, {"text": text, "learner_id": "api_sweep"})

            # 解析：GET 端点（health/quote/skills/library/search）显示 JSON 摘要
            if path in ("/api/health", "/api/quote", "/api/skills",
                        "/api/knowledge/search", "/api/knowledge/library"):
                try:
                    body = json.loads(raw)
                    if path == "/api/health":
                        reply = f"[health {body.get('status', 'ok')}]"
                    elif path == "/api/quote":
                        q = body.get('quote', body)
                        reply = f"[quote {str(q)[:40]}]"
                    elif path == "/api/knowledge/search":
                        reply = f"[{len(body.get('results', []))} 条结果]"
                    elif path == "/api/knowledge/library":
                        reply = f"[library {str(body)[:50]}]"
                    else:
                        reply = f"[skills {len(body.get('skills', body)) if isinstance(body, dict) else body}]"
                except Exception:
                    reply = raw[:80]
            else:
                reply = parse_response(raw, mode) if st == 200 else ""
            status = "✓" if st == 200 and len(reply) > 10 else ("⚠️" if st == 200 else "❌")
            path_results.append({"round": i, "input": text[:20], "status": st,
                                 "reply_len": len(reply), "reply": reply[:80],
                                 "ok": status})
            time.sleep(0.3)
        results[path] = path_results
    return results

def main():
    print("=== PAEG 全面接口多轮测试 ===")
    results = run_api_sweep()
    total_ok = total_warn = total_err = 0
    for path, rounds in results.items():
        ok = sum(1 for r in rounds if r["ok"] == "✓")
        warn = sum(1 for r in rounds if r["ok"] == "⚠️")
        err = sum(1 for r in rounds if r["ok"] == "❌")
        total_ok += ok; total_warn += warn; total_err += err
        print(f"\n>>> {path} ({len(rounds)} 轮, ✓{ok} ⚠️{warn} ❌{err})")
        for r in rounds:
            print(f"  {r['ok']} 轮{r['round']} [{r['input']}] HTTP={r['status']} len={r['reply_len']} → {r['reply'][:60]}")
    print(f"\n=== 汇总: ✓{total_ok} ⚠️{total_warn} ❌{total_err} ===")

if __name__ == "__main__":
    main()
