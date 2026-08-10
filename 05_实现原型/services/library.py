# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ services/library.py

用户专属资料库读取（v0.21.4 从 server.py 迁出）。
"""
from __future__ import annotations


def get_user_library(learner_id: str) -> str:
    """v0.21.4：读取用户专属资料库内容（供 Agent 注入回答上下文）。

    路径：Library/usr_knowledge/<learner_id>/（规范）
          同时向兼容扫 Library/user_<learner_id>/ 及嵌套子目录
    返回：可注入 system 的资料摘要文本；无资料返回 ""。
    """
    try:
        from lib import library_store
        return library_store.read_user_corpus(learner_id, max_files=5, per_file=500)
    except Exception:
        return ""
