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
