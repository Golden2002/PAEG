# -*- coding: utf-8 -*-
"""services/rollout.py —— §3.85 ⭐ Rollout 持久化（Codex Harness 借鉴 P0）

背景（Oracle 策略 §3.85）：Codex Harness 的 Rollout 机制——agent 执行过程
（事件流+状态快照）可暂停/恢复/分支。PAEG teach_stream 六阶段状态在内存，
崩溃即丢、无分支。本模块：阶段流转包装为 Rollout 事件 + SQLite append-only
+ RunState 快照——教学可审计回放、崩溃可恢复。

设计：
- rollouts 表（append-only 事件流）：(id, learner_id, concept, stage,
  event_type, payload_json, ts)
- run_state 表（RunState 快照）：(id, learner_id, concept, state_json,
  updated_ts) —— 最新快照覆盖写（恢复用）
- 事件类型（对齐 §3.85 schema）：stage_enter / stage_exit / material_emitted /
  student_response / error / done
- 只读查询：list_events(id) 回放；get_state(id) 恢复

零依赖（sqlite3 标准库），线程安全（每操作独立连接）。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_PROJ, "evolve_data", "rollout.db")
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rollouts (
    id TEXT NOT NULL,
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id TEXT,
    concept TEXT,
    stage TEXT,
    event_type TEXT,
    payload_json TEXT,
    ts REAL
);
CREATE INDEX IF NOT EXISTS idx_rollouts_id ON rollouts(id);
CREATE TABLE IF NOT EXISTS run_state (
    id TEXT PRIMARY KEY,
    learner_id TEXT,
    concept TEXT,
    state_json TEXT,
    updated_ts REAL
);
"""


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init() -> None:
    with _LOCK:
        try:
            conn = _conn()
            conn.executescript(_SCHEMA)
            conn.commit()
            conn.close()
        except Exception as _e:
            print(f"[PAEG][rollout] 初始化失败: {_e}")


def begin_run(learner_id: str, concept: str, initial_state: Optional[dict] = None) -> str:
    """开始一次教学 Rollout，返回 run id。"""
    _init()
    rid = uuid.uuid4().hex[:12]
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO rollouts (id, learner_id, concept, stage, event_type, payload_json, ts) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, learner_id, concept[:200], "", "run_start",
             json.dumps({"state": initial_state or {}}, ensure_ascii=False), time.time()))
        conn.commit()
        conn.close()
    return rid


def record_event(rid: str, stage: str, event_type: str,
                 payload: Optional[dict] = None) -> bool:
    """记录一个 Rollout 事件（append-only）。"""
    if not rid:
        return False
    try:
        with _LOCK:
            conn = _conn()
            conn.execute(
                "INSERT INTO rollouts (id, learner_id, concept, stage, event_type, "
                "payload_json, ts) VALUES (?,?,?,?,?,?,?)",
                (rid, None, None, stage or "", event_type,
                 json.dumps(payload or {}, ensure_ascii=False), time.time()))
            conn.commit()
            conn.close()
        return True
    except Exception as _e:
        print(f"[PAEG][rollout] 事件记录失败: {_e}")
        return False


def save_state(rid: str, learner_id: str, concept: str, state: dict) -> bool:
    """保存 RunState 快照（覆盖写，崩溃恢复用）。"""
    if not rid:
        return False
    try:
        with _LOCK:
            conn = _conn()
            conn.execute(
                "INSERT INTO run_state (id, learner_id, concept, state_json, updated_ts) "
                "VALUES (?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET learner_id=excluded.learner_id, "
                "concept=excluded.concept, state_json=excluded.state_json, "
                "updated_ts=excluded.updated_ts",
                (rid, learner_id, concept[:200],
                 json.dumps(state, ensure_ascii=False), time.time()))
            conn.commit()
            conn.close()
        return True
    except Exception as _e:
        print(f"[PAEG][rollout] 快照保存失败: {_e}")
        return False


def get_state(rid: str) -> Optional[dict]:
    """恢复 RunState 快照（崩溃恢复）。"""
    if not rid:
        return None
    try:
        conn = _conn()
        row = conn.execute("SELECT state_json FROM run_state WHERE id=?",
                           (rid,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def list_events(rid: str, limit: int = 500) -> List[dict]:
    """回放 Rollout 事件流（审计/回放）。"""
    if not rid:
        return []
    try:
        conn = _conn()
        rows = conn.execute(
            "SELECT stage, event_type, payload_json, ts FROM rollouts "
            "WHERE id=? ORDER BY seq LIMIT ?", (rid, limit)).fetchall()
        conn.close()
        return [{"stage": r[0], "event_type": r[1],
                 "payload": json.loads(r[2]) if r[2] else {},
                 "ts": r[3]} for r in rows]
    except Exception:
        return []


def recent_runs(limit: int = 20) -> List[dict]:
    """最近 Rollout 运行（运维审计视图）。"""
    try:
        conn = _conn()
        rows = conn.execute(
            "SELECT id, learner_id, concept, ts FROM rollouts "
            "WHERE event_type='run_start' ORDER BY seq DESC LIMIT ?",
            (limit,)).fetchall()
        conn.close()
        return [{"id": r[0], "learner_id": r[1], "concept": r[2], "ts": r[3]}
                for r in rows]
    except Exception:
        return []


__all__ = ["begin_run", "record_event", "save_state", "get_state",
           "list_events", "recent_runs"]
