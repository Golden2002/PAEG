# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ SSE 增强测试：首事件时延 + 断连鲁棒性。

针对 Oracle 建议的 SSE 测试盲区（首事件时延、断连清理）——
用可控超时验证流式体验与鲁棒性，不用真实模型吞掉时序问题。
用法：python -m pytest tests/test_sse_enhanced.py -q
"""
import json
import sys
import time
import urllib.request

import pytest

BASE = "http://127.0.0.1:5000"


def _stream_teach(concept="什么是质数", read_bytes=4096, timeout=90):
    """发起 teach_stream，读 read_bytes 字节后停止（模拟首事件/断连）。"""
    data = json.dumps({"learner_id": "u106", "concept": concept,
                       "subject": "math", "grade_level": "high_school",
                       "mode": "teach"}).encode()
    req = urllib.request.Request(BASE + "/api/teach/stream", data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=timeout)
    first_bytes = resp.read(read_bytes)
    elapsed = time.time() - t0
    resp.close()
    return first_bytes, elapsed


# ── 1. 首事件时延：连接建立 + 首字节应在合理预算内 ─────────
def test_first_event_arrives_reasonably():
    """性质：teach_stream 首字节（含首个事件）应在 60s 内到达（LLM 冷启动容忍）。"""
    first_bytes, elapsed = _stream_teach(read_bytes=512)
    assert first_bytes, "无首字节（连接失败）"
    assert elapsed < 60, f"首字节耗时 {elapsed:.0f}s 过长（LLM 冷启动超预算）"


# ── 2. 断连鲁棒性：客户端断开后服务端不 hang、不 500 ──────
def test_client_disconnect_mid_stream():
    """性质：读一部分就断开，服务端不应因此崩溃（后续请求仍正常）。"""
    # 读 2KB 后断开
    try:
        _stream_teach(read_bytes=2048, timeout=30)
    except Exception:
        pass  # 断开可能抛异常，可接受
    # 断开后服务端应仍健康
    try:
        s = urllib.request.urlopen(BASE + "/api/health", timeout=10).status
        assert s == 200, f"断连后 health {s}"
    except Exception as e:
        pytest.fail(f"断连后服务不可用: {e}")


# ── 3. 连续请求稳定性（防 SSE 中断导致状态污染）────────────
def test_consecutive_streams_stable():
    """性质：连续 2 次教学流都应完整结束（done 事件），状态不污染。"""
    import re
    for i in range(2):
        data = json.dumps({"learner_id": "u106", "concept": "什么是素数",
                           "subject": "math", "grade_level": "high_school",
                           "mode": "teach"}).encode()
        req = urllib.request.Request(BASE + "/api/teach/stream", data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            raw = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", errors="replace")
            assert "event: done" in raw, f"第 {i+1} 次流未完整结束"
        except Exception as e:
            pytest.fail(f"第 {i+1} 次流异常: {e}")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

