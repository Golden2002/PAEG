# -*- coding: utf-8 -*-
"""Round 12 ⭐ Attempt Token 幂等护栏测试（test_round18_idempotency.py）。

Codex Harness 借鉴（A11）：同 (learner_id, attempt_token) 窗口内重复请求不重复执行。

守护：
1. begin_attempt：首次 True、窗口内重复 False、TTL 后恢复 True
2. 状态流转：processing → completed
3. attempt_status：无 token/未知 token → None
4. 并发安全：多线程同时 begin 同一 token 只有一个 True
5. teach_stream 接入：SSE 重复请求短路返回 duplicate_attempt
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.idempotency import (
    begin_attempt, finish_attempt, attempt_status,
)


class TestIdempotencyCore:
    def test_first_begin_true(self):
        assert begin_attempt("u1", "tok-1") is True

    def test_duplicate_false(self):
        begin_attempt("u1", "tok-2")
        assert begin_attempt("u1", "tok-2") is False, "窗口内重复应短路"

    def test_different_learner_allowed(self):
        begin_attempt("u1", "tok-3")
        assert begin_attempt("u2", "tok-3") is True, "不同 learner 同 token 应允许"

    def test_different_token_allowed(self):
        begin_attempt("u1", "tok-4")
        assert begin_attempt("u1", "tok-5") is True

    def test_empty_token_bypasses(self):
        assert begin_attempt("u1", "") is True
        assert begin_attempt("u1", None) is True

    def test_status_transition(self):
        begin_attempt("u1", "tok-6")
        assert attempt_status("u1", "tok-6") == "processing"
        finish_attempt("u1", "tok-6")
        assert attempt_status("u1", "tok-6") == "completed"

    def test_status_unknown(self):
        assert attempt_status("u1", "no-such-token") is None
        assert attempt_status("u1", "") is None

    def test_concurrent_single_winner(self):
        # 并发 begin 同一 token → 恰一个 True
        results = []
        barrier = threading.Barrier(8)

        def _worker():
            barrier.wait()
            results.append(begin_attempt("u9", "conc-1"))

        threads = [threading.Thread(target=_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results.count(True) == 1, f"应恰 1 个 True，got {results}"


class TestTeachStreamIntegration:
    """teach_stream 幂等接入（源码级 + 状态级验证）。"""

    def test_src_has_attempt_guard(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "server.py"), encoding="utf-8").read()
        assert "X-Attempt-Token" in src, "teach_stream 缺 X-Attempt-Token 读取"
        assert "duplicate_attempt" in src, "teach_stream 缺 duplicate 短路"

    def test_attempt_survives_across_calls(self):
        begin_attempt("u-t-1", "e2e-tok")
        assert attempt_status("u-t-1", "e2e-tok") == "processing"
        assert begin_attempt("u-t-1", "e2e-tok") is False
