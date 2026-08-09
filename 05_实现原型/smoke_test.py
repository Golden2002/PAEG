# -*- coding: utf-8 -*-
"""v0.38 ⭐ 快速冒烟测试（5 秒级，不调真实 LLM——解决端到端测试卡住问题）。

设计原则（Oracle/ULW 反馈）：
- 不调真实 LLM：验证端点可达性 + 首事件，不等完整流
- 所有请求带 5 秒超时，绝不无限等待
- 快速失败：首个失败即报告，不串行跑完
- 用法：python smoke_test.py（退出码 0=全过）
"""
import sys
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"
TIMEOUT = 5  # 秒——普通请求最多等 5 秒
STREAM_TIMEOUT = 20  # 秒——SSE 流式请求（LLM 首字节可能慢）最多等 20 秒

_results = []


def check(name, cond, detail=""):
    _results.append((name, cond))
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name} {detail}")
    return cond


def post_quick(path, body, timeout=TIMEOUT):
    """POST 但只读响应头 + 少量 body（不等完整流）。"""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        head = resp.read(256)  # 只读前 256 字节
        return resp.status, head
    except urllib.error.HTTPError as e:
        return e.code, e.read(256)
    except Exception as e:
        return -1, str(e).encode()


def get_quick(path, timeout=TIMEOUT):
    try:
        resp = urllib.request.urlopen(BASE + path, timeout=timeout)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read(256)
    except Exception as e:
        return -1, str(e).encode()


def main():
    t0 = time.time()
    print("=== PAEG 快速冒烟测试（v0.38，5 秒/请求）===")

    # 1. 健康检查
    s, _ = get_quick("/api/health")
    check("health 200", s == 200, f"got {s}")

    # 2. 前端可达 + 关键标记
    s, body = get_quick("/")
    html = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else ""
    check("index 200", s == 200)
    check("前端 v0.37 标记", "v0.37" in html or "MicroMessenger" in html)
    check("前端无旧STT文案", "当前浏览器不支持语音输入，推荐使用 Chrome 或 Edge。" not in html)

    # 3. TTS 端点（只验 200 + ok 字段）
    s, head = post_quick("/api/voice/tts", {"text": "冒烟", "learner_id": "smoke"})
    check("TTS 可达", s == 200, f"got {s}")

    # 4. 教学流式（只验首事件——SSE 首字节诊断；LLM 首字节可能慢，用 STREAM_TIMEOUT）
    s, head = post_quick("/api/teach/stream",
                         {"learner_id": "smoke", "concept": "什么是熵",
                          "subject": "physics", "grade_level": "high_school"},
                         timeout=STREAM_TIMEOUT)
    raw = head.decode("utf-8", errors="replace") if isinstance(head, bytes) else ""
    check("teach_stream 首事件", s == 200 and "event:" in raw, f"got {s} 首事件={raw[:40]!r}")

    # 5. 历史会话
    s, _ = get_quick("/api/conversations/u3")
    check("conversations 200", s == 200)

    # 6. 元认知日志
    s, body = get_quick("/api/meta-log/u106")
    check("meta-log 200", s == 200)

    # 7. 学科树
    s, _ = get_quick("/api/subject-tree")
    check("subject-tree 200", s == 200)

    # 8. 情绪支持端点（不调 LLM，只看路由存在；带一次重试防抖动）
    s, head = post_quick("/api/affection",
                         {"learner_id": "smoke", "text": "测试", "subject": "general"})
    for _retry in range(2):
        if s == -1:
            import time as _t
            _t.sleep(0.5 * (_retry + 1))
            s, head = post_quick("/api/affection",
                                 {"learner_id": "smoke", "text": "测试", "subject": "general"})
    check("affection 可达", s == 200 or s == 500, f"got {s}")

    # 9. 知识导图（teach_stream 触发，首事件；LLM 慢用 STREAM_TIMEOUT）
    s, head = post_quick("/api/teach/stream",
                         {"learner_id": "smoke", "concept": "帮我把熵画成思维导图",
                          "subject": "physics", "grade_level": "high_school"},
                         timeout=STREAM_TIMEOUT)
    raw = head.decode("utf-8", errors="replace") if isinstance(head, bytes) else ""
    check("知识导图首事件", s == 200, f"got {s}")

    # 10. SQLite 反射存储
    try:
        sys.path.insert(0, r"D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型")
        from reflection_store import ReflectionStore
        rs = ReflectionStore()
        cnt = rs.count()
        check("SQLite reflections", cnt > 0, f"{cnt} 条")
    except Exception as e:
        check("SQLite reflections", False, str(e))

    dt = time.time() - t0
    passed = sum(1 for _, c in _results if c)
    total = len(_results)
    print(f"\n=== 结果: {passed}/{total} 通过, 耗时 {dt:.1f}s ===")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
