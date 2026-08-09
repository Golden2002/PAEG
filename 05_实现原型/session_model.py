# -*- coding: utf-8 -*-
"""
PAEG Thread/Turn/Item 三层会话模型（v0.21.1 ⭐ 借鉴 OpenAI Codex App Server）

Codex 的核心架构抽象：
- Thread：跨 turn 的持久容器（可 create/resume/fork/archive）——教学会话可跨课次恢复
- Turn：一次用户输入触发的完整工作单元——一道题的交互
- Item：原子 I/O 单位（user_message/agent_message/tool_call/tool_result）——每个 agent 输出

本模块提供三层模型 + JSONL 事件流（供前端 SSE 订阅 + 测试契约）。

用法：
    from session_model import ThreadStore
    ts = ThreadStore()
    tid = ts.create(student_id, subject)
    turn_id = ts.start_turn(tid, agent="tutor")
    ts.add_item(tid, turn_id, "user_message", {"content": "..."})
    ts.add_item(tid, turn_id, "agent_message", {"content": "..."})
    events = ts.events_since(tid, last_event_id)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

# 数据目录（与 users_data 同级，持久化）
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users_data')


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ThreadStore:
    """三层会话模型存储（JSON 持久化到 users_data/<student>/threads.json）。"""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or DATA_DIR

    def _path(self, student_id: str) -> str:
        d = os.path.join(self.base_dir, str(student_id))
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, 'threads.json')

    def _load(self, student_id: str) -> Dict[str, Any]:
        p = self._path(student_id)
        try:
            with open(p, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"threads": [], "next_event_id": 1}

    def _save(self, student_id: str, data: Dict[str, Any]):
        p = self._path(student_id)
        tmp = p + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)

    # ─── Thread 操作 ───
    def create(self, student_id: str, subject: str = "general",
               title: str = "") -> str:
        """创建 Thread（教学会话容器）。"""
        data = self._load(student_id)
        tid = _gen_id("thr")
        data["threads"].append({
            "id": tid, "student_id": student_id, "subject": subject,
            "title": title or subject, "status": "active",
            "parent_thread_id": None, "created_at": time.time(),
            "updated_at": time.time(), "last_event_id": 0,
            "turns": [],  # turn_id 列表
        })
        self._save(student_id, data)
        return tid

    def list(self, student_id: str) -> List[Dict[str, Any]]:
        """列出学生的所有 Thread（不含消息体）。"""
        data = self._load(student_id)
        return [{"id": t["id"], "subject": t["subject"], "title": t["title"],
                 "status": t["status"], "updated_at": t["updated_at"],
                 "turn_count": len(t.get("turns", []))}
                for t in data["threads"]]

    def get(self, student_id: str, tid: str) -> Optional[Dict[str, Any]]:
        data = self._load(student_id)
        for t in data["threads"]:
            if t["id"] == tid:
                return t
        return None

    def archive(self, student_id: str, tid: str) -> bool:
        data = self._load(student_id)
        for t in data["threads"]:
            if t["id"] == tid:
                t["status"] = "archived"
                self._save(student_id, data)
                return True
        return False

    def fork(self, student_id: str, tid: str) -> Optional[str]:
        """Fork：基于现有 Thread 创建新 Thread（Codex fork 语义）。"""
        t = self.get(student_id, tid)
        if not t:
            return None
        data = self._load(student_id)
        new_tid = _gen_id("thr")
        data["threads"].append({
            "id": new_tid, "student_id": student_id, "subject": t["subject"],
            "title": t["title"] + " (分支)", "status": "active",
            "parent_thread_id": tid, "created_at": time.time(),
            "updated_at": time.time(), "last_event_id": 0,
            "turns": list(t.get("turns", [])),
        })
        self._save(student_id, data)
        return new_tid

    # ─── Turn 操作 ───
    def start_turn(self, student_id: str, tid: str, agent: str = "tutor") -> Optional[str]:
        """创建 Turn（一次工作单元）。"""
        data = self._load(student_id)
        for t in data["threads"]:
            if t["id"] == tid:
                trn_id = _gen_id("trn")
                turn = {"id": trn_id, "agent": agent, "status": "running",
                        "started_at": time.time(), "completed_at": None,
                        "token_input": 0, "token_output": 0, "items": []}
                t.setdefault("turns", []).append(trn_id)
                # 存储 turn 详情（在 events 里）
                self._save(student_id, data)
                self.add_item(student_id, tid, trn_id, "turn_started",
                              {"agent": agent})
                return trn_id
        return None

    def complete_turn(self, student_id: str, tid: str, trn_id: str,
                      token_input: int = 0, token_output: int = 0) -> bool:
        data = self._load(student_id)
        for t in data["threads"]:
            if t["id"] == tid:
                t["updated_at"] = time.time()
                self._save(student_id, data)
                self.add_item(student_id, tid, trn_id, "turn_completed",
                              {"token_input": token_input, "token_output": token_output})
                return True
        return False

    # ─── Item / 事件流 ───
    def add_item(self, student_id: str, tid: str, trn_id: str,
                 item_type: str, payload: Dict[str, Any]) -> int:
        """添加原子 Item（写事件流，返回 event_id）。"""
        data = self._load(student_id)
        event_id = data.get("next_event_id", 1)
        data["next_event_id"] = event_id + 1
        # 找到 thread 更新 last_event_id
        for t in data["threads"]:
            if t["id"] == tid:
                t["last_event_id"] = event_id
                t.setdefault("events", []).append({
                    "event_id": event_id, "turn_id": trn_id,
                    "type": item_type, "payload": payload, "ts": time.time(),
                })
                # 限制事件长度
                t["events"] = t["events"][-500:]
                break
        self._save(student_id, data)
        return event_id

    def events_since(self, student_id: str, tid: str, last_event_id: int = 0) -> List[Dict[str, Any]]:
        """返回指定 Thread 自 last_event_id 后的事件（供 SSE 续传）。"""
        t = self.get(student_id, tid)
        if not t:
            return []
        return [e for e in t.get("events", []) if e["event_id"] > last_event_id]

    def stats(self, student_id: str) -> Dict[str, Any]:
        data = self._load(student_id)
        return {"threads": len(data["threads"]),
                "next_event_id": data.get("next_event_id", 1)}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    ts = ThreadStore()
    tid = ts.create("demo_student", "math", "导数的几何意义")
    trn = ts.start_turn("demo_student", tid, "tutor")
    ts.add_item("demo_student", tid, trn, "user_message", {"content": "什么是导数"})
    ts.add_item("demo_student", tid, trn, "agent_message", {"content": "导数是..."})
    ts.complete_turn("demo_student", tid, trn, token_input=100, token_output=50)
    print("Thread:", tid, "Turn:", trn)
    print("事件:", [e["type"] for e in ts.events_since("demo_student", tid)])
    print("列表:", ts.list("demo_student"))
