# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ 属性测试（Property-based Testing）。

针对 v0.41.7 教训（模块化重构误删 subtopic 定义 → NameError → 教学不输出，
静态检查 + 端点冒烟均漏检）设计的"性质不变量"测试：
- 任何合法教学输入，teach_stream 流必须完整结束（含 done 事件）
- 任何合法教学输入，流内不得出现服务器错误/NameError 痕迹

这是"测试强度 ≥ 改动风险"方法论中"运行时语义正确"一层的自动执行。
用法：python -m pytest tests/test_properties.py -q
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

BASE = "http://127.0.0.1:5000"
STREAM_TIMEOUT = 75  # 教学流完整读（与 smoke_test 4b 一致）


def _teach_stream_full(concept, subject="math", learner_id="smoke", mode="teach"):
    """完整读取 teach_stream SSE 流，返回 (status, text)。"""
    data = json.dumps({
        "learner_id": learner_id, "concept": concept,
        "subject": subject, "grade_level": "high_school", "mode": mode,
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/api/teach/stream", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=STREAM_TIMEOUT)
        return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, str(e)


# ── 性质 1：教学流必须完整结束 ──────────────────────────────
def test_teach_stream_always_completes():
    """性质：任何合法概念提问，teach_stream 必须含 event: done（流完整结束）。"""
    cases = [
        "什么是质数", "为什么负负得正", "帮我理解矩阵", "什么是导数",
        "什么是光合作用", "什么是勾股定理", "解释相对论", "什么是化学键",
    ]
    failures = []
    for concept in cases:
        s, text = _teach_stream_full(concept)
        has_done = "event: done" in text
        has_pres = "event: presentation" in text
        has_error = ("Error on request" in text or "Traceback" in text
                     or "NameError" in text or "Internal Server" in text)
        if s != 200 or not has_done or not has_pres or has_error:
            failures.append(f"{concept}: status={s} done={has_done} "
                            f"pres={has_pres} err={has_error}")
    assert not failures, f"教学流不完整: {failures}"


# ── 性质 2：完整教学流无服务器错误痕迹 ────────────────────────
def test_teach_stream_no_server_error():
    """性质：完整教学流文本中不得出现服务器端错误痕迹。"""
    s, text = _teach_stream_full("什么是素数")
    assert s == 200, f"HTTP {s}"
    assert "NameError" not in text, "流中出现 NameError（重构误删变量！）"
    assert "Traceback" not in text, "流中出现 Traceback"
    assert "Error on request" not in text, "流中出现服务器错误"


# ── 性质 3：subtopic 传递（三级学科选择不破坏教学）─────────────
def test_teach_stream_with_subtopic():
    """性质：带 subtopic（三级学科选择）的教学请求也必须完整结束。
    直接对应 v0.41.7 事故——subtopic 定义被删导致 NameError。
    """
    data = json.dumps({
        "learner_id": "smoke", "concept": "什么是导数",
        "subject": "math", "grade_level": "high_school",
        "mode": "teach", "subtopic": "导数的定义",
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/api/teach/stream", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=STREAM_TIMEOUT)
        text = resp.read().decode("utf-8", errors="replace")
        assert "event: done" in text, "带 subtopic 的教学流未完整结束"
        assert "NameError" not in text, "带 subtopic 出现 NameError"
    except urllib.error.HTTPError as e:
        pytest.fail(f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except Exception as e:
        pytest.fail(f"异常: {e}")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
