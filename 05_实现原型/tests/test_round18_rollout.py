# -*- coding: utf-8 -*-
"""Round 12 ⭐ Rollout 持久化测试（test_round18_rollout.py）。

Codex Harness 借鉴（§3.85 P0）：教学六阶段状态持久化——崩溃可恢复/审计回放。
守护：
1. begin_run 创建 run id + run_start 事件
2. record_event 各阶段事件 append-only（stage_enter/stage_exit/material_emitted/...）
3. save_state / get_state 快照恢复（崩溃恢复核心）
4. list_events 回放（顺序/数量）
5. recent_runs 运维视图
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.rollout as rl


class TestRollout:
    def test_begin_run_creates_id(self):
        rid = rl.begin_run("u1", "什么是导数")
        assert rid
        assert len(rid) == 12

    def test_record_events_append_only(self):
        rid = rl.begin_run("u1", "概念")
        rl.record_event(rid, "diagnosis", "stage_enter")
        rl.record_event(rid, "plan", "stage_enter")
        rl.record_event(rid, "presentation", "material_emitted",
                        {"step": 1, "len": 100})
        evs = rl.list_events(rid)
        types = [e["event_type"] for e in evs]
        assert types[0] == "run_start"
        assert "stage_enter" in types and "material_emitted" in types
        assert len(evs) == 4, f"应 4 事件（run_start+3），got {len(evs)}"

    def test_save_get_state_roundtrip(self):
        rid = rl.begin_run("u1", "概念")
        state = {"stage": "presentation", "step_index": 2,
                 "plan": {"steps": [1, 2, 3]}}
        assert rl.save_state(rid, "u1", "概念", state)
        got = rl.get_state(rid)
        assert got is not None
        assert got["stage"] == "presentation"
        assert got["step_index"] == 2
        assert got["plan"]["steps"] == [1, 2, 3]

    def test_get_state_unknown_none(self):
        assert rl.get_state("no-such-run") is None

    def test_state_overwrite(self):
        rid = rl.begin_run("u1", "概念")
        rl.save_state(rid, "u1", "概念", {"stage": "diagnosis"})
        rl.save_state(rid, "u1", "概念", {"stage": "plan"})
        assert rl.get_state(rid)["stage"] == "plan"

    def test_recent_runs(self):
        rl.begin_run("u-rec", "概念A")
        rl.begin_run("u-rec", "概念B")
        runs = rl.recent_runs(limit=5)
        assert len(runs) >= 2
        concepts = {r["concept"] for r in runs}
        assert "概念B" in concepts

    def test_events_preserve_payload(self):
        rid = rl.begin_run("u1", "概念")
        rl.record_event(rid, "presentation", "material_emitted",
                        {"step": 3, "content_len": 500})
        evs = rl.list_events(rid)
        me = [e for e in evs if e["event_type"] == "material_emitted"]
        assert me and me[0]["payload"].get("step") == 3

    def test_empty_rid_noop(self):
        assert rl.record_event("", "x", "y") is False
        assert rl.save_state("", "u", "c", {}) is False
        assert rl.get_state("") is None
        assert rl.list_events("") == []
