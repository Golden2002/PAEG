# -*- coding: utf-8 -*-
"""v0.41.9 ⭐ 考研×语言学科端到端组合测试（补 test_grade_matrix 的静态缺口）。

test_grade_matrix.py 只验证静态查表（subject_available_for_grade），
但**没有端到端 teach_stream 测试**走 graduate_exam × french 真实流程——
探索报告确认这是最危险缺口（静态修复了，运行时可能仍崩）。

本测试用 parametrize 穷举 考研/本科 × 语言类学科，真实调 teach_stream，
断言：流完整结束（done）、无 grade_blocked（考研学外语合理）。

用法：python -m pytest tests/test_graduate_corner_matrix.py -q
"""
import json
import sys
import urllib.error
import urllib.request

import pytest

BASE = "http://127.0.0.1:5000"
TIMEOUT = 75


def _teach_stream_full(concept, subject, grade):
    data = json.dumps({"learner_id": "u106", "concept": concept,
                       "subject": subject, "grade_level": grade,
                       "mode": "teach"}).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/api/teach/stream", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, str(e)


# ── 考研/本科 × 语言类学科 端到端矩阵 ─────────────────────
@pytest.mark.parametrize("subject,concept", [
    ("french", "考研法语阅读理解怎么做"),
    ("french", "法语中介词的用法"),
    ("german", "考研德语二外怎么准备"),
    ("japanese", "N1 备考策略"),
    ("english", "考研英语阅读长难句分析"),
])
@pytest.mark.parametrize("grade", ["undergraduate", "graduate_exam"])
def test_graduate_language_e2e(subject, concept, grade):
    """性质：考研/本科 + 语言学科，teach_stream 必须完整结束且不误判 grade_blocked。"""
    s, text = _teach_stream_full(concept, subject, grade)
    has_done = "event: done" in text
    has_pres = "event: presentation" in text
    blocked = "grade_blocked" in text and "True" in text
    assert s == 200, f"HTTP {s} for {subject}@{grade}"
    assert has_done, f"{subject}@{grade} 流未完整结束（{concept}）"
    assert has_pres, f"{subject}@{grade} 无教学输出（{concept}）"
    assert not blocked, f"{subject}@{grade} 被误判 grade_blocked（v0.41.9 bug 回归！）"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
