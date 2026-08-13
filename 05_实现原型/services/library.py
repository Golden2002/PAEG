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


def collect_all_resources(uid: str, topic: str = "", llm=None,
                          subject: str = "", include_web: bool = True) -> dict:
    """v0.66 ⭐ 统一资源门面（Oracle 连通性修复）。

    打通：生成模块 ← 联网检索 + 知识库 + Library（用户物料/公共模板/资产/facts）。
    供所有生成模块（manim/讲义/讲稿/PPT/视频/思维导图）复用——不再各查各的。

    返回：
    {
      "user_assets": str,   # Library/usr_knowledge/<uid>/ 物料摘要
      "kb_hits": str,       # KnowledgeBase 检索结果
      "web_hits": str,      # 联网检索结果
      "facts": str,         # Library/KnowledgeBase/facts/*.md 事实资料
      "block": str,         # 拼好的完整资源块（直接注入 system prompt）
      "has_any": bool,
    }
    """
    _parts = []
    _has = False

    # ① 用户物料（Library/usr_knowledge/<uid>/）
    # v0.66+ ⭐ Bug2 修复：除列文件名外，必须读入正文片段（max_files=3, per_file=800），
    # 否则 LLM 看不到习题册内容，讲不出基于用户资料的例题。
    # 保留原文件名摘要做兜底；append 上 read_user_corpus 抽出的正文片段。
    _ua = ""
    try:
        from asset_loader import list_user_assets
        _assets = list_user_assets(uid)
        if _assets:
            _names = "、".join(str(a).split("usr_knowledge")[-1].lstrip("\\/")[:40] for a in _assets[:5])
            _ua = f"用户资料库有 {len(_assets)} 个文件（如：{_names}）。"
            _parts.append("【用户资料库】" + _ua)
            _has = True
            # Bug2 修复：接通习题册正文（读前 3 个文件 × 每文件 800 字）
            try:
                from lib.library_store import read_user_corpus
                _ua_corpus = read_user_corpus(uid, max_files=3, per_file=800)
                if _ua_corpus:
                    _parts.append("【用户资料库正文片段（用于讲解基于用户上传资料）】\n" + _ua_corpus)
            except Exception:
                pass
    except Exception:
        pass

    # ② 知识库检索（KnowledgeBase）
    _kb = ""
    if topic:
        try:
            from infra.runtime import get_kb
            _kb_obj = get_kb()
            if _kb_obj is not None:
                _hits = _kb_obj.search_subjects(topic, subject=subject or None) \
                    if hasattr(_kb_obj, "search_subjects") else None
                if _hits:
                    _kb = "；".join(str(h.get("snippet") or h.get("title") or "")[:100] for h in _hits[:3])
                    _parts.append(f"【知识库】与「{topic}」相关：{_kb}")
                    _has = True
        except Exception:
            pass

    # ③ facts 事实资料（KnowledgeBase/facts/*.md）
    _facts = ""
    if topic:
        try:
            from infra.runtime import get_library
            _lib = get_library()
            if _lib is not None and hasattr(_lib, "search_facts"):
                _fh = _lib.search_facts(topic, top_k=2)
                if _fh:
                    _facts = "；".join(str(f.get("snippet") or f.get("content") or "")[:120] for f in _fh[:2])
                    _parts.append(f"【事实资料】{_facts}")
                    _has = True
        except Exception:
            pass

    # ④ 联网检索（web_search_multi）
    _web = ""
    if include_web and topic:
        try:
            from web_search_tool import web_search_multi
            # v0.68 修复：web_search_multi 签名是 (question, llm, subject, n_queries, per_query, max_total)
            # 此前误传 n=2 → TypeError 被吞 → web_hits 恒空。改用 max_total=2。
            _wr = web_search_multi(topic, llm=llm, subject=subject, max_total=2)
            _items = (_wr if isinstance(_wr, list) else (_wr or {}).get("results") or (_wr or {}).get("items") or [])
            if _items:
                # v0.68+ ⭐ 改进：title + 摘要片段（此前只取 title 太单薄）
                _first = _items[0]
                _t = str(_first.get("title") or "")
                _c = str(_first.get("content") or _first.get("snippet") or "")[:120]
                _web = f"{_t}：{_c}" if _c else _t
                _web = _web[:150]
                _parts.append(f"【网络检索】补充：{_web}")
                _has = True
        except Exception:
            pass

    _block = "\n\n".join(_parts) if _parts else ""
    return {
        "user_assets": _ua, "kb_hits": _kb, "web_hits": _web, "facts": _facts,
        "block": _block, "has_any": _has,
    }
