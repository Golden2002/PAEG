# -*- coding: utf-8 -*-
"""test_checkpoint_policy.py —— §3.42 W9 ⭐ session-checkpoint-policy 测试

需求（§3.38.2 新模块，借鉴 deepseek-harness session-checkpoint-policy）：
- CheckpointPolicy 4 模式：auto（每 N 事件）/ manual（显式 API）/
  time（每 T 秒）/ hybrid（组合）
- 失败发 checkpoint/failed 事件（可重试）
- 强制崩溃后能从 checkpoint 恢复会话

设计要点：
- TDD 先行：先写 RED，跑通后实现
- 策略纯函数判定 + 落盘副作用分离
- checkpoint 存到 tmp（每个测试隔离）
"""
from __future__ import annotations

import json
import os
import time

import pytest


# ────────────────────────────────────────────────────────────
# 公共 helper：events.jsonl 备份/还原（避免跨测试污染）
# ────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _clean_events():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ev_path = os.path.join(base, "events.jsonl")
    backup = None
    if os.path.exists(ev_path):
        with open(ev_path, encoding="utf-8") as f:
            backup = f.read()
        os.remove(ev_path)
    yield
    if backup is not None:
        with open(ev_path, "w", encoding="utf-8") as f:
            f.write(backup)


def _read_events():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "events.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


@pytest.fixture
def tmp_checkpoint_dir(tmp_path, monkeypatch):
    """每个测试用独立 tmp 目录作为 checkpoint 落盘根（隔离生产数据）。"""
    import infra.checkpoint as _cp
    monkeypatch.setattr(_cp, "CHECKPOINT_BASE_DIR", str(tmp_path))
    # 立即验证 monkeypatch 已生效
    assert _cp.CHECKPOINT_BASE_DIR == str(tmp_path), \
        f"monkeypatch 未生效：{_cp.CHECKPOINT_BASE_DIR} != {tmp_path}"
    return tmp_path


@pytest.fixture
def broken_save(monkeypatch):
    """注入落盘失败（仅当测试需要时显式使用——会污染其他测试的 _save_payload）。"""
    import infra.checkpoint as _cp

    def _broken_save(session_id, payload):
        raise IOError("disk full (test injected)")

    monkeypatch.setattr(_cp, "_save_payload", _broken_save)
    return _broken_save


# ────────────────────────────────────────────────────────────
# 测试 1：auto 模式每 N 事件触发
# ────────────────────────────────────────────────────────────
def test_policy_auto_event_count(tmp_checkpoint_dir):
    """auto 模式：每 N 事件触发一次 checkpoint。

    设计：
    - mode='auto', max_events=3
    - 喂入 5 个事件 → 应触发 1 次（事件 3 触发清零），再加 2 次应再触发 1 次（事件 3）
    - 实际：5 个事件 → 触发 2 次（事件 3 + 事件 3 重新累计）
    """
    from infra.checkpoint import CheckpointPolicy

    policy = CheckpointPolicy(mode="auto", max_events=3)
    session_id = "auto_test_session"

    triggers = []
    for i in range(5):
        if policy.record_event(session_id):
            triggers.append(i)

    # 事件 0,1,2 → 事件 3 触发 → 清零 → 事件 4,5,6 → 事件 3(累计3) 触发
    # 等等：record_event 增加计数到 3 时触发，然后清零
    # 5 个事件：counter=1,2,3 触发清零, 4,5(此时3) 再次触发清零 → 2 次触发
    assert len(triggers) >= 1, f"auto 模式每 N 事件应触发，实际触发 {len(triggers)} 次"
    # 验证触发位置：触发应在第 3 个事件（counter 达到 max_events）
    assert 2 in triggers, f"auto 模式应在事件 3（index=2）触发，实际 triggers={triggers}"


# ────────────────────────────────────────────────────────────
# 测试 2：manual 模式仅显式调用触发
# ────────────────────────────────────────────────────────────
def test_policy_manual_explicit(tmp_checkpoint_dir):
    """manual 模式：仅显式 trigger_manual() 触发；普通事件不触发。"""
    from infra.checkpoint import CheckpointPolicy

    policy = CheckpointPolicy(mode="manual", max_events=2)
    session_id = "manual_test_session"

    # 喂 10 个事件——manual 模式下 record_event 永远不触发
    for _ in range(10):
        triggered = policy.record_event(session_id)
        assert triggered is False, "manual 模式下 record_event 不应触发"

    # 显式调用 trigger_manual 才触发
    assert policy.trigger_manual(session_id) is True, \
        "manual 模式 trigger_manual 应返回 True（已触发）"

    # 多次显式调用都触发（manual 不限次数）
    assert policy.trigger_manual(session_id) is True
    assert policy.trigger_manual(session_id) is True


# ────────────────────────────────────────────────────────────
# 测试 3：time 模式每 T 秒触发
# ────────────────────────────────────────────────────────────
def test_policy_time_interval(tmp_checkpoint_dir):
    """time 模式：每 T 秒触发（与事件数无关）。"""
    from infra.checkpoint import CheckpointPolicy

    # interval_sec=1：每秒触发（用 _time_override 注入时间）
    policy = CheckpointPolicy(mode="time", interval_sec=1)
    session_id = "time_test_session"

    # 注入假时钟：初始 t=1000
    fake_now = [1000.0]
    policy._time_fn = lambda: fake_now[0]

    # 喂事件：在 t=1000 时 → 0 秒未超 → 不触发
    policy.record_event(session_id)
    triggered_at_t1000 = policy._should_checkpoint_internal(session_id)
    assert triggered_at_t1000 is False, "time 模式初始不应触发"

    # 时间推进 1.5 秒 → 应触发
    fake_now[0] = 1001.5
    triggered_after = policy._should_checkpoint_internal(session_id)
    assert triggered_after is True, \
        f"time 模式过 T 秒后应触发，实际 triggered={triggered_after}"

    # 验证：time 模式触发不依赖事件数（仅喂 1 个事件也应触发）
    # 再开新会话，验证时间触发
    fake_now[0] = 1003.0
    sid2 = "time_test_session_2"
    policy.record_event(sid2)  # 1 个事件
    # 推进时间：last_ts=1003（刚 record 时记录），现 t=1004.5 → 应触发
    fake_now[0] = 1004.5
    triggered_after2 = policy._should_checkpoint_internal(sid2)
    assert triggered_after2 is True, \
        f"time 模式独立事件流应触发，实际 triggered={triggered_after2}"


# ────────────────────────────────────────────────────────────
# 测试 4：hybrid 模式组合时间 + 事件数
# ────────────────────────────────────────────────────────────
def test_policy_hybrid_combines(tmp_checkpoint_dir):
    """hybrid 模式：时间 OR 事件数任一触发。"""
    from infra.checkpoint import CheckpointPolicy

    policy = CheckpointPolicy(mode="hybrid", max_events=5, interval_sec=2)
    session_id = "hybrid_test_session"

    fake_now = [2000.0]
    policy._time_fn = lambda: fake_now[0]

    # 场景 A：事件触发（时间未到）
    # 喂 5 个事件 → 事件 5 应触发
    triggers_event = []
    for i in range(5):
        if policy.record_event(session_id):
            triggers_event.append(i)
    assert 4 in triggers_event, \
        f"hybrid 模式应被事件数触发，实际 triggers={triggers_event}"

    # 场景 B：时间触发（事件未达阈值）
    sid2 = "hybrid_test_session_2"
    fake_now[0] = 3000.0
    policy.record_event(sid2)  # 1 个事件（远未到 5）
    # 推进时间 2.5 秒 → 时间触发
    fake_now[0] = 3002.5
    triggered = policy._should_checkpoint_internal(sid2)
    assert triggered is True, \
        f"hybrid 模式应被时间触发（事件数未达），实际 triggered={triggered}"


# ────────────────────────────────────────────────────────────
# 测试 5：checkpoint 失败发 checkpoint/failed 事件
# ────────────────────────────────────────────────────────────
def test_checkpoint_failed_event(tmp_checkpoint_dir, broken_save):
    """checkpoint 落盘失败 → 发 checkpoint/failed 事件（含可重试信息）。"""
    from infra.checkpoint import CheckpointPolicy

    # broken_save fixture 已把 _save_payload 替换为抛异常的 stub
    policy = CheckpointPolicy(mode="auto", max_events=1, max_retries=2)
    session_id = "fail_test_session"

    # 触发 1 个事件（max_events=1 立即触发）→ save 应失败 → 发 failed 事件
    triggered = policy.record_event(session_id, payload={"state": "test"})
    assert triggered is True, "事件 1 应触发 checkpoint"

    # 验证：events.jsonl 应含 checkpoint/failed
    events = _read_events()
    failed = [e for e in events if e.get("type") == "checkpoint/failed"]
    assert failed, f"落盘失败应发 checkpoint/failed，实际事件: {[e.get('type') for e in events]}"

    # 验证事件内容：含 session_id / error / retryable 字段
    data = failed[-1].get("data", {})
    assert "session_id" in data, f"failed 事件应含 session_id，实际 {data}"
    assert data["session_id"] == session_id, \
        f"session_id 不匹配：应 {session_id}，实际 {data['session_id']}"
    assert "error" in data, f"failed 事件应含 error，实际 {data}"
    assert "retryable" in data, f"failed 事件应含 retryable 字段，实际 {data}"
    assert data["retryable"] is True, f"磁盘 IO 错误应标记可重试，实际 {data['retryable']}"


# ────────────────────────────────────────────────────────────
# 测试 6：强制崩溃后从 checkpoint 恢复会话
# ────────────────────────────────────────────────────────────
def test_session_recovery(tmp_checkpoint_dir):
    """进程崩溃（清空内存状态）后从磁盘恢复 checkpoint。

    场景：
    1. 创建一个 session，喂入若干事件，触发 checkpoint，保存关键 payload
    2. 模拟进程崩溃：丢弃内存状态（新建空 CheckpointPolicy 实例）
    3. 用同一 session_id recover → 应读到原 payload
    """
    from infra.checkpoint import CheckpointPolicy

    policy_a = CheckpointPolicy(mode="auto", max_events=2)
    session_id = "recovery_test_session"

    # 1. 喂 2 个事件（触发）保存 payload
    payload = {
        "learner_id": "u42",
        "subject": "physics",
        "history": [
            {"role": "user", "content": "什么是熵"},
            {"role": "assistant", "content": "�是..."},
        ],
        "turn_count": 2,
        "checkpoint_ts": time.time(),
    }
    policy_a.record_event(session_id, payload=payload)
    policy_a.record_event(session_id, payload={"turn_count": 3})  # 触发第二次

    # 验证：checkpoint 落盘文件存在
    cp_file = os.path.join(str(tmp_checkpoint_dir), f"{session_id}.json")
    assert os.path.exists(cp_file), f"checkpoint 文件未落盘: {cp_file}"

    # 2. 模拟进程崩溃：新建 policy 实例（旧实例引用丢弃）
    policy_b = CheckpointPolicy(mode="auto", max_events=2)
    # 内存状态应为空
    assert session_id not in policy_b._states, "新实例不应保留旧内存状态"

    # 3. 恢复
    recovered = policy_b.recover(session_id)
    assert recovered is not None, f"recover 应返回 payload，实际 None"
    assert recovered["learner_id"] == "u42"
    assert recovered["subject"] == "physics"
    assert recovered["turn_count"] == 3, \
        f"应恢复最新 payload（turn_count=3），实际 {recovered['turn_count']}"
    assert len(recovered["history"]) == 2, \
        f"history 应被保留，实际 {recovered['history']}"


# ────────────────────────────────────────────────────────────
# 测试 7（补充）：checkpoint/saved 事件在成功时发射
# ────────────────────────────────────────────────────────────
def test_checkpoint_saved_event(tmp_checkpoint_dir):
    """checkpoint 落盘成功时发 checkpoint/saved 事件。"""
    from infra.checkpoint import CheckpointPolicy

    policy = CheckpointPolicy(mode="manual", max_events=10)
    session_id = "saved_event_test"

    # 显式触发保存
    policy.trigger_manual(session_id, payload={"learner_id": "u7"})

    events = _read_events()
    saved = [e for e in events if e.get("type") == "checkpoint/saved"]
    assert saved, f"成功保存应发 checkpoint/saved，实际: {[e.get('type') for e in events]}"
    data = saved[-1].get("data", {})
    assert data.get("session_id") == session_id
    assert "bytes_written" in data, f"saved 事件应含 bytes_written，实际 {data}"
    assert data["bytes_written"] > 0, "bytes_written 应 > 0"
