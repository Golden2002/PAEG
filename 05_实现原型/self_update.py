"""
自我更新机制（v0.5 - JSON 持久化版）。

v0.1：仅内存记录。
v0.5：每次会话后原子写入 data/ 目录（UTF-8 JSON）：
  - data/reflections.json   反思历史
  - data/strategies.json    发现的教学策略
  - data/profiles.json      学习者画像快照
  - data/versions/          版本化快照（保留最近 10 版，支持回滚）

阈值常量（沿用 v0.2 设计）：
  MIN_EVIDENCE_FOR_STRATEGY = 3       策略提炼最少证据数
  MIN_CONFIDENCE_FOR_KNOWLEDGE = 0.8  新知识入库最低可信度
  PROFILE_EMA_ALPHA = 0.3             画像 EMA 平滑系数
  ROLLBACK_WINDOW_DAYS = 7            回滚窗口（天）
"""
from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

MIN_EVIDENCE_FOR_STRATEGY = 3
MIN_CONFIDENCE_FOR_KNOWLEDGE = 0.8
PROFILE_EMA_ALPHA = 0.3
ROLLBACK_WINDOW_DAYS = 7
# v0.37.2 ⭐ Oracle 扩展性：10→3 版快照（每份 5.3MB，10 份=53MB 写放大；3 份足够回滚）
VERSION_KEEP = 3

# v0.37.2 ⭐ Oracle P0-A 修复：进程内文件写锁（跨实例共享）。
# Windows 下 _save() 的 tmp.replace() 无锁时并发抛 WinError 32（多测试/多 SSE 流实测复现）。
import threading as _threading
_SAVE_LOCK = _threading.Lock()


class SelfUpdater:
    def __init__(self, knowledge_base, data_dir: Optional[str] = None):
        self.kb = knowledge_base
        self.data_dir = Path(data_dir) if data_dir else (Path(__file__).parent / "data")
        self.history = []            # 反思历史（内存缓存，读点兼容）
        self.strategies_discovered = []  # 发现的新策略
        self.version = 0
        # v0.38 ⭐ Oracle 扩展性：SQLite 反思存储（append-only，消除 5.3MB 写放大）
        try:
            from reflection_store import ReflectionStore
            self._ref_store = ReflectionStore()
        except Exception:
            self._ref_store = None
        self._load()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def _ensure_dirs(self):
        (self.data_dir / "versions").mkdir(parents=True, exist_ok=True)

    def _load(self):
        """启动时加载持久化状态（不存在则从空开始）。"""
        self._ensure_dirs()
        # v0.38 ⭐ SQLite 优先：迁移旧 JSON → 读全部历史（保序）
        if self._ref_store is not None:
            try:
                _migrated = self._ref_store.migrate_from_json(
                    self.data_dir / "reflections.json")
                if _migrated:
                    print(f"[PAEG] reflections 已迁移 {_migrated} 条到 SQLite")
            except Exception as _me:
                print(f"[PAEG] reflections SQLite 迁移失败（用 JSON 兜底）: {_me}")
            try:
                self.history = self._ref_store.query("*", limit=10**6)
            except Exception:
                self.history = []
        if not self.history:
            try:
                refs = (self.data_dir / "reflections.json")
                if refs.is_file():
                    self.history = json.loads(refs.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.history = []
        try:
            strs = (self.data_dir / "strategies.json")
            if strs.is_file():
                self.strategies_discovered = json.loads(strs.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.strategies_discovered = []
        # 读取版本号
        ver = (self.data_dir / "version.txt")
        if ver.is_file():
            try:
                self.version = int(ver.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                self.version = 0

    def _save(self, _retries: int = 3):
        """原子写入 + 版本快照。

        v0.37.2 ⭐ Oracle P0-A 修复：进程内锁 + 重试——Windows 下 tmp.replace()
        在并发 _save() 时抛 PermissionError（WinError 32，多测试/多 SSE 流实测复现）。
        生产环境 chat 每轮都触发 _save()，无锁会丢数据。
        """
        import time as _time
        with _SAVE_LOCK:  # 进程内互斥（跨实例共享），杜绝并发写
            for _attempt in range(_retries):
                try:
                    self._ensure_dirs()
                    self.version += 1
                    # v0.38 ⭐ SQLite 优先：reflections 已由 append_reflection/append_many 增量写入，
                    # 此处不再全量重写 reflections.json（消除 5.3MB 写放大）。
                    # 仅当 SQLite 不可用时降级为 JSON 全量写（兼容）。
                    if self._ref_store is None:
                        for name, payload in (
                            ("reflections.json", self.history),
                            ("strategies.json", self.strategies_discovered),
                        ):
                            tmp = self.data_dir / (name + ".tmp")
                            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
                            tmp.replace(self.data_dir / name)
                    else:
                        # strategies 仍 JSON（小文件）；reflections 走 SQLite
                        tmp = self.data_dir / ("strategies.json.tmp")
                        tmp.write_text(json.dumps(self.strategies_discovered, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
                        tmp.replace(self.data_dir / "strategies.json")
                    (self.data_dir / "version.txt").write_text(str(self.version), encoding="utf-8")
                    # 版本快照（轻量：只存 strategies + 计数，不再复制 5MB reflections）
                    snap_dir = self.data_dir / "versions"
                    snap = snap_dir / f"v{self.version:04d}.json"
                    snap.write_text(json.dumps({
                        "version": self.version,
                        "timestamp": datetime.now().isoformat(),
                        "reflections_count": len(self.history),
                        "strategies": self.strategies_discovered,
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                    for old in sorted(snap_dir.glob("v*.json"))[:-VERSION_KEEP]:
                        old.unlink(missing_ok=True)
                    return  # 成功
                except (PermissionError, OSError) as _pe:
                    # Windows 文件占用：等待后重试
                    if _attempt < _retries - 1:
                        _time.sleep(0.05 * (_attempt + 1))
                        continue
                    print(f"[PAEG] self_update._save 写入失败（{_retries} 次重试后）: {_pe}")

    # ------------------------------------------------------------------
    # 更新
    # ------------------------------------------------------------------
    def incremental_update(self, session):
        """每次会话后的增量更新。"""
        # 1. 记录反思
        for reflection in session.reflections:
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "learner_id": session.learner.id,
                "concept": session.concept,
                "subject": getattr(session, "subject", ""),
                "reflection": reflection
            })
        # v0.38 ⭐ SQLite 增量写（append-only，单条 <1KB IO，替代全量重写）
        if self._ref_store is not None and session.reflections:
            try:
                self._ref_store.append_many(
                    session.learner.id, session.reflections,
                    concept=session.concept, subject=getattr(session, "subject", ""),
                )
            except Exception as _re:
                print(f"[PAEG] reflections SQLite 写入失败: {_re}")

        # 2. 如果教学成功，提炼模式
        if any(r.get('success', False) for r in session.reflections):
            for evaluation in session.evaluations:
                if evaluation.get('score', 0) > 0.85:
                    self.strategies_discovered.append({
                        "discovered_at": datetime.now().isoformat(),
                        "learner_profile": {
                            "grade_level": session.learner.grade_level,
                            "cognitive_style": session.learner.cognitive_style
                        },
                        "concept": session.concept,
                        "score": evaluation['score']
                    })

        # 3. 更新画像掌握度（EMA）
        if session.evaluations:
            avg_score = sum(e['score'] for e in session.evaluations) / len(session.evaluations)
            subject = session.subject
            if subject not in session.learner.subjects_mastery:
                session.learner.subjects_mastery[subject] = {"mastery": 0.5, "count": 0}
            old = session.learner.subjects_mastery[subject]["mastery"]
            new = PROFILE_EMA_ALPHA * avg_score + (1 - PROFILE_EMA_ALPHA) * old
            session.learner.subjects_mastery[subject]["mastery"] = round(new, 3)
            session.learner.subjects_mastery[subject]["count"] += 1

        # 4. 画像落盘
        self._save_profile(session.learner)
        self._save()

    def append_reflection(self, learner_id: str, reflection: dict,
                          concept: str = "", subject: str = "") -> None:
        """v0.37.1 ⭐ 单条反思落盘 API（chat_stream 等轻量路径用）。

        Oracle 审查 P0-1：此前 server.py 直接 append 到 self.history 但不调 _save()，
        元认知日志重启即丢。此 API 保证 append + 原子落盘 + 版本快照。
        v0.38 ⭐ SQLite 优先：增量 INSERT（<1KB），不再触发 5.3MB 全量 _save。
        """
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "learner_id": learner_id,
            "concept": str(concept or "")[:60],
            "subject": subject or "",
            "reflection": reflection,
        })
        if self._ref_store is not None:
            try:
                self._ref_store.append(learner_id, reflection, concept=concept, subject=subject)
                return  # SQLite 已落盘，跳过全量 _save
            except Exception as _re:
                print(f"[PAEG] reflections SQLite 写入失败（降级全量）: {_re}")
        try:
            self._save()
        except Exception:
            pass

    def _save_profile(self, learner):
        """画像快照落盘。"""
        profiles_path = self.data_dir / "profiles.json"
        data = {}
        if profiles_path.is_file():
            try:
                data = json.loads(profiles_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        data[learner.id] = {
            "nickname": learner.nickname,
            "grade_level": learner.grade_level,
            "age": learner.age,
            "cognitive_style": learner.cognitive_style,
            "subjects_mastery": learner.subjects_mastery,
            "world_view_blend": learner.world_view_blend,
            "target_exam": getattr(learner, "target_exam", None),
            "specialty_target": getattr(learner, "specialty_target", None),
            "updated_at": datetime.now().isoformat(),
        }
        tmp = profiles_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(profiles_path)

    def batch_update(self):
        """每周批处理：识别反复模式 + 清理过期快照。"""
        from collections import Counter
        concepts_seen = Counter(r['concept'] for r in self.history)
        # 清理超出回滚窗口的快照
        cutoff = datetime.now() - timedelta(days=ROLLBACK_WINDOW_DAYS)
        snap_dir = self.data_dir / "versions"
        if snap_dir.is_dir():
            for old in snap_dir.glob("v*.json"):
                try:
                    meta = json.loads(old.read_text(encoding="utf-8"))
                    ts = datetime.fromisoformat(meta.get("timestamp", ""))
                    if ts < cutoff and len(list(snap_dir.glob("v*.json"))) > 3:
                        old.unlink(missing_ok=True)
                except (ValueError, OSError, json.JSONDecodeError):
                    continue
        self._save()
        return {
            "recurring_concepts": concepts_seen.most_common(5),
            "total_sessions": len(self.history),
            "strategies_discovered_count": len(self.strategies_discovered),
            "version": self.version,
            "data_dir": str(self.data_dir),
        }

    def rollback_to_version(self, target_version: int) -> bool:
        """回滚到指定版本快照。"""
        snap = self.data_dir / "versions" / f"v{target_version:04d}.json"
        if not snap.is_file():
            return False
        try:
            data = json.loads(snap.read_text(encoding="utf-8"))
            self.history = data.get("history", [])
            self.strategies_discovered = data.get("strategies", [])
            self.version = data.get("version", target_version)
            self._save()
            return True
        except (OSError, json.JSONDecodeError):
            return False

    def add_knowledge(self, node: dict, source: str, confidence: float):
        """带可信度的新知识入库（v0.2 设计保留）。"""
        if confidence < MIN_CONFIDENCE_FOR_KNOWLEDGE:
            return False
        # 简化：写入 strategies（演示用途）
        self.strategies_discovered.append({
            "discovered_at": datetime.now().isoformat(),
            "source": source,
            "confidence": confidence,
            "node_id": node.get("id"),
        })
        self._save()
        return True


if __name__ == "__main__":
    su = SelfUpdater(None, data_dir="data")
    print(f"当前版本：{su.version}，历史 {len(su.history)} 条，策略 {len(su.strategies_discovered)} 条")