# -*- coding: utf-8 -*-
"""Gap A：memory/feedback_log.jsonl 读者接线测试（test_feedback_log_reader.py）。

server.py /api/feedback 把用户反馈写入 memory/feedback_log.jsonl，schema：
    {"ts", "learner_id", "rating": "good|bad|neutral", "message", "context"}
但此前无人消费（write-only）。本测试守护 periodic_self_update 新增的读者：
load_bad_feedback() 读取负面（rating=="bad"）反馈，distill_feedback_improvements()
将其蒸馏为可写入 improvements.md 的改进建议（引用原始反馈内容）。
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from periodic_self_update import load_bad_feedback, distill_feedback_improvements


def _write_feedback(path, entries):
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def test_load_bad_feedback_returns_only_bad(tmp_path):
    fb = tmp_path / "feedback_log.jsonl"
    _write_feedback(str(fb), [
        {"ts": "2026-08-28T10:00:00", "learner_id": "u1", "rating": "bad",
         "message": "讲得太快了，跟不上", "context": "teach:导数"},
        {"ts": "2026-08-28T10:01:00", "learner_id": "u2", "rating": "good",
         "message": "很好", "context": ""},
        {"ts": "2026-08-28T10:02:00", "learner_id": "u3", "rating": "neutral",
         "message": "", "context": ""},
    ])
    bad = load_bad_feedback(str(fb))
    assert len(bad) == 1
    assert bad[0]["learner_id"] == "u1"
    assert bad[0]["rating"] == "bad"


def test_distill_feedback_references_message(tmp_path):
    fb = tmp_path / "feedback_log.jsonl"
    _write_feedback(str(fb), [
        {"ts": "2026-08-28T10:00:00", "learner_id": "u1", "rating": "bad",
         "message": "讲得太快了，跟不上", "context": "teach:导数"},
    ])
    bad = load_bad_feedback(str(fb))
    lines = distill_feedback_improvements(bad)
    assert lines, "蒸馏结果不应为空"
    joined = "\n".join(lines)
    assert "讲得太快了" in joined, "蒸馏结果应引用负面反馈内容"


def test_load_bad_feedback_missing_file_returns_empty(tmp_path):
    bad = load_bad_feedback(str(tmp_path / "nonexistent.jsonl"))
    assert bad == []
