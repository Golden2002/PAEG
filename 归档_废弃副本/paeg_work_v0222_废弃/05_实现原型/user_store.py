"""
PAEG 用户注册与画像持久化（v0.14）

任务3：用户注册系统（邮箱/手机号），保存基本信息和画像，保持个体性。
解决"刷新页面画像丢失"问题——用户登录后 learner_id 固定，画像持久化到磁盘。

数据存储：users.json（密码用 SHA-256 + salt 哈希，不存明文）

用法：
    from user_store import UserStore
    store = UserStore()
    store.register(email, password, nickname)  # 或 phone
    user = store.login(identifier, password)
    store.save_learner(user_id, learner_dict)  # 持久化画像
    store.load_learner(user_id)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from typing import Any, Dict, List, Optional


class UserStore:
    """用户存储：注册/登录/画像持久化。"""

    def __init__(self, data_path: Optional[str] = None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.data_path = data_path or os.path.join(base, 'users.json')
        self._load()

    def _load(self):
        try:
            with open(self.data_path, encoding='utf-8') as f:
                self._data = json.load(f)
        except Exception:
            self._data = {"users": {}, "next_id": 1}
        self._data.setdefault("users", {})
        self._data.setdefault("next_id", 1)

    def _save(self):
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=1)

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode('utf-8')).hexdigest()

    @staticmethod
    def _is_valid_identifier(identifier: str) -> bool:
        """邮箱或手机号。"""
        if re.match(r'^[\w.+-]+@[\w-]+\.[\w.]+$', identifier):
            return True
        if re.match(r'^1[3-9]\d{9}$', identifier):
            return True
        return False

    def register(self, identifier: str, password: str,
                 nickname: str = "") -> Dict[str, Any]:
        """注册新用户。identifier 为邮箱或手机号。"""
        identifier = identifier.strip().lower()
        if not self._is_valid_identifier(identifier):
            return {"ok": False, "error": "请输入有效的邮箱或手机号"}
        if len(password) < 6:
            return {"ok": False, "error": "密码至少 6 位"}
        if identifier in self._data["users"]:
            return {"ok": False, "error": "该账号已注册，请直接登录"}

        user_id = f"u{self._data['next_id']}"
        self._data["next_id"] += 1
        salt = secrets.token_hex(8)
        self._data["users"][identifier] = {
            "user_id": user_id,
            "identifier": identifier,
            "nickname": nickname or identifier.split('@')[0],
            "password_hash": self._hash_password(password, salt),
            "salt": salt,
            "learner": None,          # 持久化的学习者画像
            "created_at": time.time(),
            "last_login": time.time(),
        }
        self._save()
        return {"ok": True, "user_id": user_id, "nickname": self._data["users"][identifier]["nickname"]}

    def login(self, identifier: str, password: str) -> Dict[str, Any]:
        """登录。identifier 为邮箱或手机号。"""
        identifier = identifier.strip().lower()
        user = self._data["users"].get(identifier)
        if not user:
            return {"ok": False, "error": "账号不存在，请先注册"}
        if user["password_hash"] != self._hash_password(password, user["salt"]):
            return {"ok": False, "error": "密码错误"}
        user["last_login"] = time.time()
        self._save()
        return {"ok": True, "user_id": user["user_id"], "nickname": user["nickname"]}

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        for u in self._data["users"].values():
            if u["user_id"] == user_id:
                return u
        return None

    def save_learner(self, user_id: str, learner: Any) -> None:
        """持久化学习者画像（dataclass → dict）。"""
        from dataclasses import asdict
        try:
            learner_dict = asdict(learner)
        except Exception:
            learner_dict = dict(learner.__dict__) if hasattr(learner, '__dict__') else {}
        for u in self._data["users"].values():
            if u["user_id"] == user_id:
                u["learner"] = learner_dict
                self._save()
                return

    def load_learner(self, user_id: str) -> Optional[Dict[str, Any]]:
        """加载学习者画像。"""
        u = self.get_user(user_id)
        return u.get("learner") if u else None

    # ─── v0.15：每用户独立文件夹 ───
    def user_dir(self, user_id: str) -> Optional[str]:
        """获取/创建用户独立文件夹（profile.json + history/ + notes/）。

        结构：
        users_data/<user_id>/
        ├── profile.json      学习者画像（自我描述/掌握度/偏好）
        ├── history.jsonl     对话历史（追加）
        ├── notes/            用户笔记/生成文件
        └── insights.json     从该用户对话中提取的学习洞察
        """
        u = self.get_user(user_id)
        if not u:
            return None
        base = os.path.dirname(os.path.abspath(__file__))
        udir = os.path.join(base, 'users_data', user_id)
        os.makedirs(os.path.join(udir, 'notes'), exist_ok=True)
        # 初始化 profile.json（若不存在）
        profile_path = os.path.join(udir, 'profile.json')
        if not os.path.exists(profile_path):
            learner = u.get('learner') or {}
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(learner, f, ensure_ascii=False, indent=1)
        return udir

    def append_history(self, user_id: str, entry: dict) -> None:
        """追加一条对话历史到用户的 history.jsonl。"""
        udir = self.user_dir(user_id)
        if not udir:
            return
        with open(os.path.join(udir, 'history.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_history(self, user_id: str, limit: int = 20) -> List[dict]:
        """读取用户的最近对话历史。"""
        udir = self.user_dir(user_id)
        if not udir:
            return []
        path = os.path.join(udir, 'history.jsonl')
        if not os.path.exists(path):
            return []
        entries = []
        try:
            with open(path, encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
        except Exception:
            pass
        return entries[-limit:]

    def save_insight(self, user_id: str, insight: dict) -> None:
        """保存从该用户对话中提取的洞察。"""
        udir = self.user_dir(user_id)
        if not udir:
            return
        path = os.path.join(udir, 'insights.json')
        try:
            with open(path, encoding='utf-8') as f:
                insights = json.load(f)
        except Exception:
            insights = []
        insights.append(insight)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(insights, f, ensure_ascii=False, indent=1)

    def load_insights(self, user_id: str) -> List[dict]:
        """加载该用户的学习洞察。"""
        udir = self.user_dir(user_id)
        if not udir:
            return []
        path = os.path.join(udir, 'insights.json')
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def stats(self) -> dict:
        return {"users": len(self._data["users"])}


# ─── v0.21.5：usr/ 视图路径别名（SelfUpdateAgent 等外部消费者）───
def user_data_paths(uid: str) -> dict:
    """返回用户数据的逻辑路径别名（usr/ 视图 → 实际 users_data 目录）。

    给"usr/视图"等外部路径消费者使用：输入用户 ID，输出基于 user_store.py
    所在目录绝对路径的 5 个数据文件路径别名。

    返回键：profile / history / notes / self_description / feedback
    """
    base = os.path.dirname(os.path.abspath(__file__))
    users_data_dir = os.path.join(base, 'users_data', uid)
    return {
        "profile": os.path.join(users_data_dir, 'profile.json'),
        "history": os.path.join(users_data_dir, 'history.jsonl'),
        "notes": os.path.join(users_data_dir, 'notes'),
        "self_description": os.path.join(users_data_dir, 'self_description.json'),
        "feedback": os.path.join(users_data_dir, 'feedback'),
    }


class ConversationStore:
    """对话历史持久化（v0.18）。

    按用户保存多轮会话，支持：
    - 自动保存（每次 teach/chat 后追加）
    - 读取（前端恢复显示）
    - 用户删除（单会话/全部）
    - 定期清理（超过 retention_days 自动删除，惰性清理）

    存储：users_data/<user_id>/conversations.json
    {
      "conversations": [
        {"id": "c_xxx", "title": "什么是熵", "mode": "teach|chat",
         "created_at": 1234567890, "updated_at": ...,
         "messages": [{"role": "user|assistant", "content": "...", "ts": ...}]}
      ]
    }
    """

    def __init__(self, base_dir: Optional[str] = None, retention_days: int = 30,
                 max_conversations: int = 50):
        base = base_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'users_data')
        self.base_dir = base
        self.retention_days = retention_days
        self.max_conversations = max_conversations   # LRU 容量上限
        self._lock = threading.Lock()   # v0.18.1：并发写保护
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, user_id: str) -> str:
        return os.path.join(self.base_dir, user_id, 'conversations.json')

    def _load(self, user_id: str) -> dict:
        with self._lock:
            try:
                with open(self._path(user_id), encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {"conversations": []}

    def _save(self, user_id: str, data: dict) -> None:
        with self._lock:
            udir = os.path.join(self.base_dir, user_id)
            os.makedirs(udir, exist_ok=True)
            tmp = self._path(user_id) + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._path(user_id))  # 原子替换

    # ─── 保存 ───
    def add_message(self, user_id: str, mode: str, title: str,
                    role: str, content: str,
                    conv_id: Optional[str] = None) -> str:
        """追加一条消息。若 conv_id 给定则加入该会话，否则新建会话。

        返回会话 id。
        """
        data = self._load(user_id)
        convs = data["conversations"]
        now = time.time()
        if conv_id is None:
            conv_id = f"c_{int(now)}_{secrets.token_hex(3)}"
            convs.append({
                "id": conv_id, "title": title[:50], "mode": mode,
                "created_at": now, "updated_at": now, "messages": [],
            })
        conv = next((c for c in convs if c["id"] == conv_id), None)
        if conv is None:
            conv_id = f"c_{int(now)}_{secrets.token_hex(3)}"
            convs.append({
                "id": conv_id, "title": title[:50], "mode": mode,
                "created_at": now, "updated_at": now, "messages": [],
            })
            conv = convs[-1]
        conv["messages"].append({
            "role": role, "content": content[:20000], "ts": now,
        })
        conv["updated_at"] = now
        # 控制单会话消息上限（防止无限增长）
        conv["messages"] = conv["messages"][-100:]
        # v0.18.1：LRU 容量上限（保留最新 max_conversations 个会话）
        if len(convs) > self.max_conversations:
            convs.sort(key=lambda c: c.get("updated_at", 0), reverse=True)
            data["conversations"] = convs[:self.max_conversations]
        self._save(user_id, data)
        return conv_id

    def update_title(self, user_id: str, conv_id: str, title: str) -> None:
        data = self._load(user_id)
        for c in data["conversations"]:
            if c["id"] == conv_id:
                c["title"] = title[:50]
                break
        self._save(user_id, data)

    # ─── 读取 ───
    def list_conversations(self, user_id: str, limit: int = 50) -> List[dict]:
        """列出用户会话（不含消息体，按更新时间倒序）。"""
        data = self._load(user_id)
        convs = sorted(data["conversations"], key=lambda c: c.get("updated_at", 0), reverse=True)
        return [{
            "id": c["id"], "title": c.get("title", ""), "mode": c.get("mode", "chat"),
            "created_at": c.get("created_at", 0), "updated_at": c.get("updated_at", 0),
            "message_count": len(c.get("messages", [])),
        } for c in convs[:limit]]

    def get_conversation(self, user_id: str, conv_id: str) -> Optional[dict]:
        data = self._load(user_id)
        for c in data["conversations"]:
            if c["id"] == conv_id:
                return c
        return None

    # ─── 删除 ───
    def delete_conversation(self, user_id: str, conv_id: str) -> bool:
        data = self._load(user_id)
        before = len(data["conversations"])
        data["conversations"] = [c for c in data["conversations"] if c["id"] != conv_id]
        if len(data["conversations"]) != before:
            self._save(user_id, data)
            return True
        return False

    def clear_all(self, user_id: str) -> bool:
        """清空该用户全部会话。"""
        data = self._load(user_id)
        if data["conversations"]:
            data["conversations"] = []
            self._save(user_id, data)
            return True
        return False

    # ─── 定期清理 ───
    def cleanup(self, retention_days: Optional[int] = None) -> int:
        """清理所有用户超过保留期的会话。返回删除的会话数。"""
        days = retention_days or self.retention_days
        cutoff = time.time() - days * 86400
        removed = 0
        if not os.path.isdir(self.base_dir):
            return 0
        for uid in os.listdir(self.base_dir):
            udir = os.path.join(self.base_dir, uid)
            path = os.path.join(udir, 'conversations.json')
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
                before = len(data.get("conversations", []))
                data["conversations"] = [
                    c for c in data.get("conversations", [])
                    if c.get("updated_at", 0) >= cutoff
                ]
                removed += before - len(data["conversations"])
                if len(data["conversations"]) != before:
                    self._save(uid, data)
            except Exception:
                pass
        return removed

    def stats(self, user_id: str) -> dict:
        data = self._load(user_id)
        return {"conversations": len(data["conversations"]),
                "messages": sum(len(c.get("messages", [])) for c in data["conversations"])}
