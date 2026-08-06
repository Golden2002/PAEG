# -*- coding: utf-8 -*-
"""
PAEG 三层记忆系统（v0.19）

P0-2：短期/中期/长期记忆分层（对标 Claude Code CLAUDE.md / Codex memory）：
- 短期记忆（short_term）：当前对话消息列表（内存）
- 中期记忆（mid_term）：当前会话内学习状态（内存 + 会话文件）
- 长期记忆（long_term）：跨会话学生画像 + 对话摘要（users_data/<id>/ 持久化）

摘要压缩（compress）：当短期记忆超阈值时，用 LLM 把早期消息压成摘要，
保留最近 N 条原文——参考 LangChain ConversationSummaryBufferMemory。

用法：
    mem = MemorySystem(user_id, llm)
    mem.add("user", "我想学导数")
    mem.add("assistant", "我们先看变化…")
    context = mem.build_context()      # 注入 LLM 的上下文字符串
    mem.compress_if_needed()           # 超过阈值自动压缩
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class MemorySystem:
    """三层记忆。"""

    def __init__(self, user_id: str = "anonymous", llm=None,
                 short_term_limit: int = 12, summary_path: Optional[str] = None):
        self.user_id = user_id
        self.llm = llm
        self.short_term_limit = short_term_limit   # 超过则触发压缩
        self.short_term: List[Dict[str, str]] = []  # 当前对话消息
        self.summary: str = ""                      # 早期对话摘要（压缩产物）
        # 长期记忆路径（会话摘要文件）
        if summary_path is None:
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'users_data', user_id)
            summary_path = os.path.join(base, 'memory_summary.json')
        self.summary_path = summary_path
        self._load_summary()

    # ─── 长期记忆持久化（摘要） ───
    def _load_summary(self):
        try:
            with open(self.summary_path, encoding='utf-8') as f:
                self.summary = json.load(f).get("summary", "")
        except Exception:
            self.summary = ""

    def _save_summary(self):
        try:
            os.makedirs(os.path.dirname(self.summary_path), exist_ok=True)
            with open(self.summary_path, 'w', encoding='utf-8') as f:
                json.dump({"user_id": self.user_id, "summary": self.summary,
                           "updated_at": time.time()}, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    # ─── 短期记忆操作 ───
    def add(self, role: str, content: str):
        """添加一条消息到短期记忆。"""
        self.short_term.append({"role": role, "content": content})
        if len(self.short_term) > self.short_term_limit:
            self.compress_if_needed()

    def clear_short(self):
        """清空短期记忆（新会话时）。"""
        self.short_term = []

    # ─── 摘要压缩 ───
    def compress_if_needed(self, force: bool = False):
        """短期记忆超限时，把最旧的若干条压缩进 summary。"""
        if len(self.short_term) <= self.short_term_limit and not force:
            return
        # 保留最近 half_limit 条，更早的压缩
        keep = max(6, self.short_term_limit // 2)
        if len(self.short_term) <= keep:
            return
        old = self.short_term[:-keep]
        recent = self.short_term[-keep:]

        if self.llm is not None and old:
            try:
                from subagents import _safe_chat
                old_text = "\n".join(
                    f"{'学生' if m['role']=='user' else 'Émile'}: {m['content'][:200]}"
                    for m in old[-8:])
                new_summary = _safe_chat(
                    self.llm,
                    "你是 PAEG 的记忆整理器。把下面的对话压缩成 2-3 句摘要，"
                    "保留：学生问过的主题、掌握/薄弱点、情感状态。只输出摘要本身。",
                    f"历史对话：\n{old_text}\n\n摘要：", max_tokens=200)
                if new_summary and len(new_summary) > 10:
                    merged = (self.summary + "；" + new_summary.strip()) if self.summary else new_summary.strip()
                    self.summary = merged[-800:]  # 限制长度
            except Exception:
                pass  # 压缩失败不阻塞

        self.short_term = recent
        self._save_summary()

    # ─── 构造注入 LLM 的上下文 ───
    def build_context(self, max_recent: int = 10) -> str:
        """返回注入 LLM 的上下文字符串（摘要 + 最近消息）。"""
        parts = []
        if self.summary:
            parts.append(f"【此前对话摘要】{self.summary}")
        recent = self.short_term[-max_recent:]
        if recent:
            conv = "\n".join(
                f"{'学生' if m['role']=='user' else 'Émile'}: {m['content'][:300]}"
                for m in recent)
            parts.append(f"【最近对话】\n{conv}")
        return "\n\n".join(parts)

    # ─── 长期画像注入（复用 user_store） ───
    def get_long_term(self) -> str:
        """加载长期记忆（学生画像 + 历史洞察）。"""
        parts = []
        try:
            from user_store import UserStore
            store = UserStore()
            learner = store.load_learner(self.user_id)
            if learner:
                desc = learner.get("self_description", "")
                if desc:
                    parts.append(f"【学生的自我描述】{desc}")
                mastery = learner.get("subjects_mastery") or {}
                if mastery:
                    parts.append(f"【掌握度】{json.dumps(mastery, ensure_ascii=False)}")
        except Exception:
            pass
        try:
            from user_store import ConversationStore
            cs = ConversationStore()
            stats = cs.stats(self.user_id)
            if stats.get("conversations"):
                parts.append(f"【历史会话】共 {stats['conversations']} 个，{stats['messages']} 条消息")
        except Exception:
            pass
        return "\n".join(parts)

    def stats(self) -> dict:
        return {"short_term": len(self.short_term),
                "summary_len": len(self.summary),
                "has_summary": bool(self.summary)}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    m = MemorySystem("test_user", llm=None)
    for i in range(20):
        m.add("user", f"问题 {i}")
        m.add("assistant", f"回答 {i}")
    print("短期记忆长度:", len(m.short_term))
    print("摘要:", m.summary[:100] or "(无 LLM，未压缩)")
    print("上下文预览:", m.build_context()[:200])
