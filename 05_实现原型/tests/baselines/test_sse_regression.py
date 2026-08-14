"""字节级回归：teach_stream 输出与基线一致（事件顺序/字段名/必含字段）。

SSE 重构（P1-P4）后必须跑：python -m pytest tests/baselines/test_sse_regression.py -q
注意：不调用真实 LLM，只解析已录制的基线文件做结构断言。
"""
import json
import os
import re

BASELINE_DIR = os.path.join(os.path.dirname(__file__), "raw_streams")
REQUIRED_EVENTS = [
    "diagnosis", "plan", "step", "presentation", "evaluation",
    "adjustment", "reflection", "self_update", "summary", "done",
]


def _parse_sse(text: str):
    """解析 SSE 文本为事件列表 [{event, data, data_raw}]。"""
    events = []
    cur = {}
    for line in text.splitlines():
        if line.startswith("event: "):
            if cur:
                events.append(cur)
                cur = {}
            cur["event"] = line[7:].strip()
        elif line.startswith("data: "):
            try:
                cur["data"] = json.loads(line[6:])
            except Exception:
                cur["data_raw"] = line[6:]
    if cur:
        events.append(cur)
    return events


def _baseline_files():
    if not os.path.isdir(BASELINE_DIR):
        return []
    return [f for f in os.listdir(BASELINE_DIR) if f.endswith(".sse")]


def test_baseline_exists():
    """至少有一条基线（重构前必须已录制）。

    v0.69+：无基线时 skip 而非 fail（新克隆环境未录制基线是预期状态，
    避免整个套件因前置缺失阻塞；录制方法见 record_teach_stream.py）。
    """
    import pytest
    files = _baseline_files()
    if not files:
        pytest.skip(f"无基线文件（{BASELINE_DIR} 为空）——先跑 record_teach_stream.py 录制")
    assert files, f"无基线文件（{BASELINE_DIR} 为空）——先跑 record_teach_stream.py"


def test_event_order_baseline():
    """每个基线案例的事件顺序必须与 REQUIRED_EVENTS 严格对齐。"""
    for fn in _baseline_files():
        text = open(os.path.join(BASELINE_DIR, fn), encoding="utf-8").read()
        events = _parse_sse(text)
        ev_names = [e["event"] for e in events]
        # 必需事件都必须出现
        missing = [e for e in REQUIRED_EVENTS if e not in ev_names]
        assert not missing, f"{fn}: 缺失事件 {missing}"
        # 相对顺序正确
        last_idx = -1
        for req in REQUIRED_EVENTS:
            idx = ev_names.index(req)
            assert idx > last_idx, f"{fn}: 事件 {req} 顺序错乱"
            last_idx = idx


def test_data_is_json():
    """data 字段必须可解析为 JSON（前端契约：按字段名取数）。"""
    for fn in _baseline_files():
        text = open(os.path.join(BASELINE_DIR, fn), encoding="utf-8").read()
        for ev in _parse_sse(text):
            if "data_raw" in ev:
                raise AssertionError(f"{fn}: 事件 {ev['event']} 的 data 非合法 JSON: {ev['data_raw'][:80]}")
