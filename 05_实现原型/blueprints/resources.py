"""resources.py — 资料检索蓝图（v0.26 ResourceLibrarian + PPT 联动）。

§3.46.2 Phase 2（W9）拆分：自 server.py 迁出（原 L2749-2859），行为字节级不变。
依赖注入：paeg/llm 经 infra.runtime 懒加载（与 server 模块级全局同引用）、
SESSIONS（infra.sessions）、ensure_learner_session/_hydrate_learner（services/_learner_session + utils）。
"""
from __future__ import annotations

import os
import urllib.parse

from flask import Blueprint, jsonify, request

from infra.runtime import get_llm, get_paeg
from infra.sessions import SESSIONS
from module_registry import require_module
from services._learner_session import ensure_learner_session
from utils import _anon_learner_id, _hydrate_learner

bp = Blueprint("resources", __name__)


@bp.route("/api/resources", methods=["POST"])
@require_module("knowledge")
def resource_lookup():
    """v0.26 ⭐ 需求C：资料检索（ResourceLibrarian）。

    请求：{learner_id, question, subject, grade_level, scope?, include_web?, for_ppt?}
    响应：
      - for_ppt=False（默认）：{"sources": [...], "scope", "keywords", "ppt_outline", "learner_id"}
      - for_ppt=True：上方 + "ppt": {"ok", "path", "url", "slides"}
        url 指向 /api/download/&lt;filename&gt;（DOWNLOAD_DIR/ppt/ 子目录）
    前端可点击链接获取资料，或联动 PPT 制作。
    """
    data = request.get_json(force=True)
    learner_id = data.get("learner_id") or _anon_learner_id(data)
    # v0.42 ⭐ 重构提取至 services/_learner_session.py（等价原 L2582 内联，无 elif）
    learner = ensure_learner_session(learner_id, data, SESSIONS)
    _hydrate_learner(learner, data)  # v0.32 ⭐ 每次请求同步学段（修复缓存陈旧）
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    subject = data.get("subject") or getattr(learner, "_current_subject", "") or "default"
    for_ppt = bool(data.get("for_ppt", False))
    try:
        # v0.43 ⭐ P0-C 提升：复用主 agent 全局持有的 ResourceLibrarian（替代每请求 new）
        _paeg = get_paeg()
        _llm = get_llm()
        _rl = _paeg.resource_librarian
        _result = _rl.run(
            question, learner=learner, llm=_llm, subject=subject,
            scope=data.get("scope", "all"),
            include_web=bool(data.get("include_web", True)),
            for_ppt=for_ppt,
        )
        response = {**_result, "learner_id": learner_id}

        # v0.26 ⭐ 需求C：for_ppt=True 时联动 pptx_mcp_server.generate_ppt 真正生成 PPT
        if for_ppt:
            ppt_meta = _generate_ppt_from_outline(
                question=question,
                outline=_result.get("ppt_outline") or "",
                sources=_result.get("sources") or [],
                learner_id=learner_id,
            )
            response["ppt"] = ppt_meta

        return jsonify(response)
    except Exception as e:
        return jsonify({"error": f"资料检索失败: {e}", "sources": []}), 500


def _generate_ppt_from_outline(
    question: str,
    outline: str,
    sources: list,
    learner_id: str,
) -> dict:
    """v0.26 ⭐ 需求C：把 ResourceLibrarian 的 ppt_outline 喂给 pptx_mcp_server 生成真实 PPT。

    返回 {"ok": bool, "path": str, "url": str, "slides": int, "error": str}
    """
    try:
        import pptx_mcp_server
        # 整理 sources 摘要
        src_titles = [
            (s.get("title") or "").strip()
            for s in (sources or [])
            if (s.get("title") or "").strip()
        ][:8]
        sources_blob = "、".join(src_titles) if src_titles else ""

        # 主题：question 截前 30 字符，去掉路径分隔符
        import re as _re
        topic = _re.sub(r'[\\/:*?"<>|\r\n]+', " ", question).strip()[:60] or "学习资料"

        ppt_res = pptx_mcp_server.generate_ppt(
            topic=topic,
            outline=outline or "",
            sources=sources_blob,
            uid=str(learner_id or ""),
        )
        if not ppt_res.get("ok"):
            return {
                "ok": False,
                "path": "",
                "url": "",
                "slides": 0,
                "error": ppt_res.get("error") or "生成失败",
            }

        # path 在 OUT_DIR = .../downloads/ppt/&lt;fname&gt;
        # 把 ppt 文件路径映射到 /api/download/&lt;rel&gt; —— /api/download/<path:filename>
        # Flask 下载端点指向 DOWNLOAD_DIR；pptx_mcp 用的是其自身的 OUT_DIR。
        # 兼容策略：把 pptx 文件复制到全局 DOWNLOAD_DIR（如果不同），并用统一 /api/download 下载。
        full_path = ppt_res.get("path") or ""
        slides = int(ppt_res.get("slides") or 0)
        if not full_path or not os.path.isfile(full_path):
            return {"ok": False, "path": full_path, "url": "", "slides": slides, "error": "PPT 文件未生成"}

        # 计算相对于 DOWNLOAD_DIR/ppt 的文件名（pptx 自身写到 downloads/ppt/）
        try:
            from pathlib import Path as _P
            url_path = f"/api/download/ppt/{urllib.parse.quote(_P(full_path).name)}"
        except Exception:
            url_path = f"/api/download/ppt/{urllib.parse.quote(os.path.basename(full_path))}"

        return {
            "ok": True,
            "path": full_path,
            "url": url_path,
            "slides": slides,
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "path": "", "url": "", "slides": 0, "error": f"PPT 生成异常: {e}"}
