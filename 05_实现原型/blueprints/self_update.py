"""self_update.py — 自我更新蓝图（v0.38 内部 API + v0.21.4 反馈入口）。

§3.46.2 Phase 2（W9）拆分：自 server.py 迁出（原 L4263-4402），行为字节级不变。
依赖注入：PERIODIC_UPDATER 经 infra.runtime.get_periodic_updater 懒加载（同引用）、
SESSIONS（infra.sessions）、_is_registered（services/_learner_session）、llm（infra.runtime）。

⚠ __file__ 修正：本文件位于 blueprints/ 子目录，项目根需上溯 parent.parent
（原 server.py 中 dirname(abspath(__file__)) = 05_实现原型/，迁入后必须改为 _SRV_ROOT）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request

from infra.runtime import get_llm, get_periodic_updater
from infra.sessions import SESSIONS
from module_registry import require_module
from services._learner_session import _is_registered

bp = Blueprint("self_update", __name__)

# §3.46.2 ⭐ __file__ 修正：blueprints/self_update.py → 项目根需上溯两级
_SRV_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@bp.route("/api/self-update/run", methods=["POST"])
@require_module("self_update")
def run_self_update():
    # v0.38 内部 API（自我进化后台任务，由调度器触发）
    """手动触发一次周度自我更新（洞察提取 + 批处理 + 失败分析）。"""
    try:
        result = get_periodic_updater().run_now()
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/self-update/status", methods=["GET"])
@require_module("self_update")
def self_update_status():
    # v0.38 内部 API（自我进化状态查询，供运维）
    """查看调度器状态。"""
    _pu = get_periodic_updater()
    return jsonify({
        "ok": True,
        "thread_alive": _pu._thread is not None and _pu._thread.is_alive(),
        "interval_hours": _pu.interval / 3600,
        "last_weekly": _pu.last_weekly,
        "last_activity": _pu.last_activity,
    })


@bp.route("/api/self-update/from-feedback", methods=["POST"])
@require_module("self_update")
def self_update_from_feedback():
    # v0.38 内部 API（自我进化反馈入口，供外部）
    """v0.21.4：从反馈/反思生成自我更新建议（第 8 个子代理 SelfUpdateAgent）。

    请求：{"text": str, "learner_id": str, "include_insights": bool(默认true),
            "include_feedback_files": bool(默认true)}
    流程：读取经过 QualityGate 过滤的洞察（evolve_data/insights.json）+
          外部反馈文件（users_data/<uid>/feedback/ 或 Library/usr_knowledge/<uid>/feedback/）
          → SelfUpdateAgent 驱动 LLM 生成结构化更新建议 → 追加到 memory/self_update_suggestions.jsonl
    响应：{"ok": true, "result": {"suggestions": [...], "summary": str, "sources_used": [...], "mode": "self_update"}}
    """
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    learner_id = data.get("learner_id") or "anonymous"
    if not text:
        return jsonify({"ok": False, "error": "缺少 text 字段"}), 400
    # v0.37.1 ⭐ Oracle P1-4 修复：任意 learner_id 可触发反馈提取 → 校验注册/匿名合法性
    if not _is_registered(learner_id):
        return jsonify({"ok": False, "error": "非法用户标识"}), 401

    try:
        from subagents import SelfUpdateAgent
        _su = SelfUpdateAgent()

        # 1) 读取过滤后的反思洞察（QualityGate promote 后落盘的 insights.json）
        insights = []
        if data.get("include_insights", True):
            try:
                _evolve_dir = os.path.join(_SRV_ROOT, "evolve_data")
                _ins_path = os.path.join(_evolve_dir, "insights.json")
                if os.path.exists(_ins_path):
                    _ins = json.load(open(_ins_path, encoding="utf-8"))
                    if isinstance(_ins, list):
                        insights = [{"content": i.get("content", "") if isinstance(i, dict) else str(i),
                                     "subject": i.get("subject", "") if isinstance(i, dict) else "",
                                     "helped": i.get("helped", True) if isinstance(i, dict) else True}
                                    for i in _ins if i]
            except Exception as _e:
                print(f"[PAEG] 读取 insights.json 失败: {_e}")

        # 2) 读取外部反馈文件（线下用户测试反馈）
        # v0.24 增强：
        #   - 不仅枚举路径，还在 server 侧预读前 2000 字符作为兜底（即使 SelfUpdateAgent 内部读失败也有内容）
        #   - 在 result 中暴露 feedback_files_preview（运维/测试可见的反馈文本前 200 字）
        library_paths = []
        feedback_text_aggregate = ""
        if data.get("include_feedback_files", True):
            _base = _SRV_ROOT
            _cands = [
                os.path.join(_base, "users_data", learner_id, "feedback"),
                os.path.join(_base, "..", "Library", "usr_knowledge", learner_id, "feedback"),
            ]
            for _fd in _cands:
                _fd = os.path.normpath(_fd)
                if os.path.isdir(_fd):
                    for _f in sorted(os.listdir(_fd)):
                        if _f.endswith((".md", ".txt", ".jsonl", ".json")):
                            library_paths.append(os.path.join(_fd, _f))
            # v0.24：预读反馈文件前 2000 字符，给 SelfUpdateAgent 当兜底原料
            # 同时拼到反馈文本里（避免依赖 subagents 的内部实现细节）
            for _fp in library_paths[:5]:
                try:
                    with open(_fp, encoding='utf-8') as _fb:
                        _content = _fb.read()[:2000]
                    if _content:
                        feedback_text_aggregate += f"\n\n--- 反馈文件: {_fp} ---\n{_content}\n--- end ---\n"
                except Exception:
                    continue

        # 3) 调用 SelfUpdateAgent 驱动 LLM
        # v0.22.1：传 learner + chat_hist（原 learner=None/history=[] 导致画像上下文丢失）
        # v0.24：把预读的反馈文件内容并入 text（双保险：既传 library_paths 让子代理读，
        #                  又把内容直接拼到 text 上，避免依赖子代理内部实现细节）
        _su_learner = SESSIONS.get(f"learner_{learner_id}") if learner_id else None
        _su_hist = SESSIONS.get(f"chat_hist_{learner_id}", []) if learner_id else []
        _combined_text = text
        if feedback_text_aggregate:
            _combined_text = text + "\n\n## 用户提供的反馈文件原文（v0.24 预读）\n" + \
                             feedback_text_aggregate
        _llm = get_llm()
        result = _su.run(_llm, _combined_text, learner=_su_learner, history=_su_hist,
                         insights=insights, library_paths=library_paths)
        # v0.24：把预读的反馈原文前 200 字塞到 result，便于运维/测试观察实际读取情况
        if feedback_text_aggregate:
            try:
                result["feedback_files_preview"] = feedback_text_aggregate[:200]
                result["feedback_files_loaded"] = [
                    p for p in library_paths
                    if os.path.isfile(p)
                ][:5]
            except Exception as _e:
                print(f"[PAEG][server.py] self_update_from_feedback 异常忽略: {_e}")
                pass

        # 4) 追加建议记录（供人工/调度器后续处理）
        try:
            _mem_dir = os.path.join(_SRV_ROOT, "memory")
            os.makedirs(_mem_dir, exist_ok=True)
            _log_path = os.path.join(_mem_dir, "self_update_suggestions.jsonl")
            with open(_log_path, "a", encoding="utf-8") as _f:
                _f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "learner_id": learner_id,
                    "text": text,
                    "library_paths_count": len(library_paths),
                    "feedback_bytes": len(feedback_text_aggregate),
                    "suggestions": result.get("suggestions", []),
                    "sources_used": result.get("sources_used", []),
                }, ensure_ascii=False) + "\n")
        except Exception as _e:
            print(f"[PAEG] 写入 self_update_suggestions.jsonl 失败: {_e}")

        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
