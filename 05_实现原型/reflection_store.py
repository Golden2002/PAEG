# -*- coding: utf-8 -*-
"""v0.38 ⭐ SQLite 反思存储层（Oracle 扩展性方案批次1）。

解决：reflections.json 每次 chat 全量重写（5.3MB 写放大 + 版本快照 53MB）。
替代为 SQLite append-only（单条 <1KB IO）。

- 表 reflections(ts, learner_id, concept, subject, reflection_json)
- 启动时若 paeg.db 不存在，自动从 data/reflections.json 迁移历史数据
- 向后兼容：SelfUpdater.history 仍维护内存列表（读点不变），仅写路径走 SQLite
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

_DB_LOCK = threading.Lock()
_DB_PATH_ENV = "PAEG_DB_PATH"


class ReflectionStore:
    """SQLite 反思存储（append-only，WAL 模式支持并发读）。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else Path(
            os.environ.get(_DB_PATH_ENV, "") or
            (Path(__file__).parent / "data" / "paeg.db"))
        self._init_schema()

    def _init_schema(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with _DB_LOCK, sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    learner_id TEXT NOT NULL,
                    concept TEXT DEFAULT '',
                    subject TEXT DEFAULT '',
                    reflection_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reflections_learner_ts "
                         "ON reflections(learner_id, ts DESC)")
            conn.commit()

    def append(self, learner_id: str, reflection: dict,
               concept: str = "", subject: str = "") -> None:
        """追加一条反思（append-only）。"""
        with _DB_LOCK, sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO reflections (ts, learner_id, concept, subject, reflection_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), str(learner_id), str(concept or "")[:60],
                 str(subject or ""), json.dumps(reflection, ensure_ascii=False)),
            )
            conn.commit()

    def append_many(self, learner_id: str, reflections: List[dict],
                    concept: str = "", subject: str = "") -> None:
        """批量追加（事务内一次提交）。"""
        if not reflections:
            return
        with _DB_LOCK, sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                "INSERT INTO reflections (ts, learner_id, concept, subject, reflection_json) "
                "VALUES (?, ?, ?, ?, ?)",
                [(datetime.now().isoformat(), str(learner_id), str(concept or "")[:60],
                  str(subject or ""), json.dumps(r, ensure_ascii=False))
                 for r in reflections],
            )
            conn.commit()

    def query(self, learner_id: str, limit: int = 20) -> List[dict]:
        """查询用户最近反思（倒序，供 meta-log 端点）。learner_id="*" 查全量（启动加载用）。"""
        with _DB_LOCK, sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if learner_id == "*":
                rows = conn.execute(
                    "SELECT ts, learner_id, concept, subject, reflection_json "
                    "FROM reflections ORDER BY ts ASC, id ASC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT ts, learner_id, concept, subject, reflection_json "
                    "FROM reflections WHERE learner_id=? "
                    "ORDER BY ts DESC, id DESC LIMIT ?",
                    (str(learner_id), limit),
                ).fetchall()
        result = []
        for r in rows:
            try:
                ref = json.loads(r["reflection_json"])
            except (json.JSONDecodeError, TypeError):
                ref = {}
            result.append({
                "timestamp": r["ts"],
                "learner_id": r["learner_id"],
                "concept": r["concept"],
                "subject": r["subject"],
                "reflection": ref,
            })
        return result

    def count(self, learner_id: Optional[str] = None) -> int:
        with _DB_LOCK, sqlite3.connect(str(self.db_path)) as conn:
            if learner_id:
                row = conn.execute(
                    "SELECT COUNT(*) FROM reflections WHERE learner_id=?",
                    (str(learner_id),)).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()
            return int(row[0]) if row else 0

    def migrate_from_json(self, json_path: Optional[str] = None) -> int:
        """从旧 reflections.json 迁移历史（幂等：已存在则跳过）。"""
        if self.count() > 0:
            return 0
        src = Path(json_path) if json_path else (
            Path(__file__).parent / "data" / "reflections.json")
        if not src.is_file():
            return 0
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0
        if not isinstance(data, list):
            return 0
        migrated = 0
        with _DB_LOCK, sqlite3.connect(str(self.db_path)) as conn:
            for item in data:
                if not isinstance(item, dict):
                    continue
                try:
                    conn.execute(
                        "INSERT INTO reflections (ts, learner_id, concept, subject, reflection_json) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (str(item.get("timestamp", datetime.now().isoformat())),
                         str(item.get("learner_id", "")),
                         str(item.get("concept", ""))[:60],
                         str(item.get("subject", "")),
                         json.dumps(item.get("reflection", item), ensure_ascii=False)),
                    )
                    migrated += 1
                except Exception:
                    continue
            conn.commit()
        return migrated
