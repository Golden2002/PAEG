"""steering.py — Agent Steering：学科自动识别 / 未收录学科响应。

v0.43 提取自 server.py（v0.40.4 L364-505 原 _steer_subject + _steer_unknown_response）。

职责
----
1. `_steer_subject`：根据问题内容自动判断学科，覆盖用户手动设定。
   - 调用 `subject_detector.detect_subject` + `prompts.normalize_subject`。
   - 未收录学科时调用 `EVOLVER.record_subject_request` 记录需求。
   - 学段-学科联动（v0.25）：区分"学科需更高学段"与"真未收录"。
   - 识别到学科且 ≠ 用户设定 → steering 切换。

2. `_steer_unknown_response`：构造未收录学科的 SSE 流式响应
   （teach_stream/chat_stream 用，纯 dict）。

依赖
----
- `subject_detector.detect_subject`（函数体内 import）
- `prompts.normalize_subject` / `prompts.get_style`（函数体内 import）
- `infra.runtime.get_evolver`（函数体内懒加载）
- `flask.jsonify`（函数体内懒加载，仅 _steer_subject 走 Flask 路由上下文时用到）

行为
----
与 v0.40.4 内联实现 100% 等价：
- 全部异常静默忽略 + 返回默认 dict。
- 返回 dict 结构：`{"subject", "unknown", "unknown_name", "switched", "response"}`。
"""
from __future__ import annotations

from typing import Any, Dict


def _steer_subject(
    concept: str,
    subject: str,
    learner: Any,
    learner_id: str,
    *,
    llm: Any,
    evolver: Any = None,
) -> dict:
    """根据问题内容自动判断学科，覆盖用户手动设定。

    返回 `{"subject", "unknown", "unknown_name", "switched", "response"}`：
      - subject: 最终学科（未切换时保持传入值）。
      - unknown: True 表示未收录/被学段拦截。
      - unknown_name: 未收录学科的展示名。
      - switched: True 表示识别到新学科并已切换。
      - response: 仅 unknown/grade_blocked 时填充 Flask jsonify 响应对象。
    """
    try:
        from subject_detector import detect_subject
        from prompts import normalize_subject
        norm_subject = normalize_subject(subject)
        _grade = ""
        try:
            _grade = getattr(learner, "grade_level", "") or ""
        except Exception:
            _grade = ""
        det = detect_subject(concept, llm, user_subject=norm_subject, grade=_grade)

        # 未收录学科：记录需求 + 反馈用户
        if det.get("unknown"):
            uname = det.get("unknown_name") or "该学科"
            # v0.25 学段-学科联动：区分"学科需更高学段"与"真未收录"
            if det.get("grade_blocked"):
                need_grade = det.get("grade_name") or "大学本科"
                reply = (
                    f"我注意到你问的是「{uname}」领域的问题。\n\n"
                    f"「{uname}」通常需要<b>{need_grade}</b>及以上学段才适合系统学习，"
                    f"当前你的学段设置还未覆盖它。\n\n"
                    f"你可以：\n"
                    f"· 在<b>底部输入栏左侧</b>把学段切换为「{need_grade}」，就能正式学习这门学科\n"
                    f"· 或者先问我当前学段的<b>其他学科</b>（如物理、数学、语文……）\n"
                    f"· 或者把资料上传给我（点右下角输入栏旁的书本图标），我就能基于你给的资料回答\n\n"
                    f"教学讲究循序渐进，先把基础打牢，更高的学科随时欢迎你。"
                )
                # jsonify 仅在 Flask 路由上下文可用 — 懒加载。
                from flask import jsonify
                return {"subject": subject, "unknown": True, "unknown_name": uname,
                        "grade_blocked": True,
                        "switched": False, "response": jsonify({
                            "session_id": f"grade_blocked_{learner_id}",
                            "summary": {"avg_score": 0},
                            "worldview_used": "weil",
                            "tone_ratio": 0,
                            "presentations": [
                                {"step_id": 1, "content": reply,
                                 "step_type": "grade_blocked_subject"}
                            ],
                            "evaluations": [], "diagnosis": {}, "plan": {"steps": []},
                            "reflections": [],
                            "learner": {
                                "id": learner.id, "nickname": learner.nickname,
                                "grade_level": learner.grade_level,
                                "subjects_mastery": learner.subjects_mastery,
                            },
                            "grade_blocked": True,
                            "subject_requested": uname,
                            "required_grade": det.get("grade_name", ""),
                        })}
            if evolver is not None:
                try:
                    evolver.record_subject_request(uname, concept, learner_id)
                except Exception as _e:
                    print(f"[PAEG][services.steering] _steer_subject 异常忽略: {_e}")
                    pass
                    pass
            reply = (
                f"我注意到你问的是「{uname}」领域的问题。\n\n"
                f"目前我还没有把「{uname}」正式列入我的学科清单，"
                f"但**我已经把这条需求记下来**，后续会优先优化升级来覆盖它。\n\n"
                f"在此之前，你可以：\n"
                f"· 问我相关的**其他学科**（如物理、数学、哲学……）\n"
                f"· 或者把资料上传给我（点右下角输入栏旁的书本图标），我就能基于你给的资料回答\n\n"
                f"感谢你的反馈，这会让 PAEG 变得更好。"
            )
            # jsonify 仅在 Flask 路由上下文可用 — 懒加载。
            from flask import jsonify
            return {"subject": subject, "unknown": True, "unknown_name": uname,
                    "switched": False, "response": jsonify({
                        "session_id": f"unknown_{learner_id}",
                        "summary": {"avg_score": 0},
                        "worldview_used": "weil",
                        "tone_ratio": 0,
                        "presentations": [
                            {"step_id": 1, "content": reply, "step_type": "unregistered_subject"}
                        ],
                        "evaluations": [], "diagnosis": {}, "plan": {"steps": []},
                        "reflections": [],
                        "learner": {
                            "id": learner.id, "nickname": learner.nickname,
                            "grade_level": learner.grade_level,
                            "subjects_mastery": learner.subjects_mastery,
                        },
                        "unregistered_subject": True,
                        "subject_requested": uname,
                    })}

        # 识别到学科且 ≠ 用户设定 → steering 切换
        if det.get("switched"):
            new_subject = det["subject"]
            try:
                from prompts import get_style
                old_label = get_style(subject)["label"]
                new_label = get_style(new_subject)["label"]
                print(f"[PAEG][steering] {old_label} → {new_label}（问题: {concept[:30]}）")
            except Exception as _e:
                print(f"[PAEG][services.steering] _steer_subject 异常忽略: {_e}")
                pass
                pass
            return {"subject": new_subject, "unknown": False, "unknown_name": None,
                    "switched": True, "response": None}
    except Exception as _e:
        print(f"[PAEG][services.steering] _steer_subject 异常忽略: {_e}")
        pass
        pass
    return {"subject": subject, "unknown": False, "unknown_name": None,
            "switched": False, "response": None}


def _steer_unknown_response(concept: str, learner: Any, learner_id: str,
                            unknown_name: str) -> dict:
    """构造未收录学科的 SSE 流式响应（teach_stream/chat_stream 用）。

    返回纯 dict（不 jsonify）——生成器（SSE 流）里没有 Flask app context，
    不能调 jsonify（与 _handle_knowledge_query 同约定）。
    """
    reply = (
        f"我注意到你问的是「{unknown_name}」领域的问题。\n\n"
        f"目前我还没有把「{unknown_name}」正式列入我的学科清单，"
        f"但**我已经把这条需求记下来**，后续会优先优化升级来覆盖它。\n\n"
        f"在此之前，你可以：\n"
        f"· 问我相关的**其他学科**（如物理、数学、哲学……）\n"
        f"· 或者把资料上传给我（点右下角输入栏旁的书本图标），我就能基于你给的资料回答\n\n"
        f"感谢你的反馈，这会让 PAEG 变得更好。"
    )
    return {
        "session_id": f"unknown_{learner_id}",
        "summary": {"avg_score": 0},
        "worldview_used": "weil",
        "tone_ratio": 0,
        "presentations": [
            {"step_id": 1, "content": reply, "step_type": "unregistered_subject"}
        ],
        "evaluations": [], "diagnosis": {}, "plan": {"steps": []},
        "reflections": [],
        "learner": {
            "id": learner.id, "nickname": learner.nickname,
            "grade_level": learner.grade_level,
            "subjects_mastery": learner.subjects_mastery,
        },
        "unregistered_subject": True,
        "subject_requested": unknown_name,
    }


# ─────────────────────────────────────
# v0.43 � 兼容别名：保持原 server.py 中调用点不变。
# 服务端 `from services.steering import _steer_subject, _steer_unknown_response`。
# ─────────────────────────────────────
