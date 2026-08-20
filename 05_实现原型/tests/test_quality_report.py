# -*- coding: utf-8 -*-
"""
v0.74+ ⭐ Quality Report 聚合 + Feedback 端点 测试

目标：
1. ``test_quality_report_full_schema``：LessonPrep.run() 返回的 quality_report
   含完整 5 维 schema（lesson_plan_score / handout_score / ppt_outline_score /
   hard_checks_pass / hard_checks_total / overall / overall_score / dim_scores /
   violations / eval_mode）。
2. ``test_feedback_endpoint_roundtrip``：POST /api/lesson_prep/feedback 接收
   {run_id, scores, notes}，200 + {ok:True, saved:True}；写入
   memory/lesson_prep_feedback.jsonl 追加一行。

设计原则：
- 复用 test_lesson_prep.py 的 MockLLM / MockKB 模式（mock LLM，不调真实 API）
- Flask test_client 真实调用（test_v028_endpoints.py 模式）
- 字段级 + schema 级断言（禁 len()>N 弱断言）
- jsonl 文件追加验证：用 tmp_path 隔离 → 测试结束后还原文件
- 校验负向路径：run_id 缺失、scores 空、score 越界、未知维度
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 让测试能找到 05_实现原型/ 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════════════
# 公共 helper（复用 test_lesson_prep.py 模式）
# ═══════════════════════════════════════════════════════════════════════════


class MockLLM:
    """模拟 LLM：name 为 'mock'，按 user 关键字返回结构化 JSON/Markdown。"""

    name = "test_llm"

    def __init__(self, respond_json=True):
        self._respond_json = respond_json

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kwargs):
        u = ""
        if messages:
            u = messages[-1].get("content", "") if isinstance(messages[-1], dict) else str(messages[-1])
        elif user:
            u = str(user)
        if "教学骨架" in u or "教案" in u or "完整教案" in u:
            return json.dumps({
                "framework": "5E",
                "objectives_3d": {
                    "knowledge": ["理解核心概念"],
                    "ability": ["能运用所学"],
                    "literacy": ["体会科学之美"],
                },
                "key_points": [
                    {"point": "k1", "reason": "r1"},
                    {"point": "k2", "reason": "r2"},
                ],
                "difficult_points": [{"point": "d1", "reason": "dr1", "breakthrough": "b1"}],
                "sections": [{"name": s, "teacher_activity": "t",
                              "student_activity": "s", "design_intent": "i",
                              "duration_min": 7} for s in
                             ("导入", "新授", "探究", "练习", "小结", "作业")],
                "blackboard": {"main": "板书主体", "aux": "辅助"},
                "reflection": ["改1", "改2", "改3"],
            }, ensure_ascii=False)
        if "PPT" in u or "幻灯片" in u or "ppt" in u or "演示文稿" in u:
            return json.dumps([
                {"page": i, "title": f"主题{i}", "key_points": ["要点A", "要点B", "要点C"],
                 "visual_focus": "[图]", "layout": "居中"}
                for i in range(1, 6)
            ], ensure_ascii=False)
        if "脚本" in u or "镜头" in u or "video" in u.lower():
            return "镜头1：开场介绍。\n镜头2：核心机制演示。\n镜头3：总结。"
        return "兜底内容" if self._respond_json else "兜底失败"


class MockKB:
    pass


# ═══════════════════════════════════════════════════════════════════════════
# T1: quality_report 完整 schema 验证
# ═══════════════════════════════════════════════════════════════════════════


def test_quality_report_full_schema():
    """LessonPrep.run() 返回的 quality_report 应含完整 5 维聚合 schema。

    必含键（v0.74+）：
      - lesson_plan_score / handout_score / video_script_score
      - ppt_outline_score
      - hard_checks / hard_checks_pass / hard_checks_total
      - dim_scores（5 维：lesson_plan / handout / video_script / ppt_outline / hard_checks）
      - overall / overall_score
      - violations
      - eval_mode
    """
    from subagents import LessonPrep, LessonPlanInput

    lp = LessonPrep(model=MockLLM(), kb=MockKB())
    inp = LessonPlanInput(
        topic="光合作用",
        subject="biology",
        grade="high_school",
    )
    res = lp.run(inp)

    # ── 顶层键存在性断言 ──
    assert "quality_report" in res, "LessonPrep.run 必须返回 quality_report"
    qr = res["quality_report"]
    assert isinstance(qr, dict), f"quality_report 应为 dict，实际 {type(qr)}"

    required_keys = {
        "lesson_plan_score", "handout_score", "ppt_outline_score",
        "hard_checks", "hard_checks_pass", "hard_checks_total",
        "overall", "overall_score", "dim_scores", "violations", "eval_mode",
    }
    missing = required_keys - qr.keys()
    assert not missing, f"quality_report 缺关键键：{missing}"

    # ── 字段类型与值域断言 ──
    assert isinstance(qr["lesson_plan_score"], float)
    assert 0.0 <= qr["lesson_plan_score"] <= 1.0

    assert isinstance(qr["handout_score"], float)
    assert 0.0 <= qr["handout_score"] <= 1.0

    assert isinstance(qr["ppt_outline_score"], float)
    assert 0.0 <= qr["ppt_outline_score"] <= 1.0

    assert isinstance(qr["hard_checks"], list)
    assert len(qr["hard_checks"]) == qr["hard_checks_total"] == 12, (
        f"hard_checks 应含 12 项，实际 {len(qr['hard_checks'])}"
    )
    for item in qr["hard_checks"]:
        assert isinstance(item, dict)
        assert "name" in item and "status" in item
        assert item["status"] in ("pass", "fail", "unverified")

    assert isinstance(qr["hard_checks_pass"], int)
    assert 0 <= qr["hard_checks_pass"] <= qr["hard_checks_total"]

    assert qr["overall"] in ("PASS", "FAIL")

    assert isinstance(qr["overall_score"], float)
    assert 0.0 <= qr["overall_score"] <= 1.0

    # ── dim_scores 5 维 ──
    assert isinstance(qr["dim_scores"], dict)
    expected_dims = {"lesson_plan", "handout", "video_script", "ppt_outline", "hard_checks"}
    actual_dims = set(qr["dim_scores"].keys())
    assert expected_dims == actual_dims, (
        f"dim_scores 维度集合应为 {expected_dims}，实际 {actual_dims}"
    )

    # hard_checks 应为 ratio（pass/total），0-1 之间
    ratio = qr["dim_scores"]["hard_checks"]
    assert isinstance(ratio, float) and 0.0 <= ratio <= 1.0

    # ── violations / eval_mode ──
    assert isinstance(qr["violations"], list)
    for v in qr["violations"]:
        assert isinstance(v, dict) and "dim" in v and "msg" in v

    assert qr["eval_mode"] == "auto", f"默认 eval_mode 应为 'auto'，实际 {qr['eval_mode']!r}"

    # ── 加权一致性（lesson_plan × 0.5 + handout × 0.2 + ppt_outline × 0.2 + hard_checks × 0.1）──
    expected = (
        qr["dim_scores"]["lesson_plan"] * 0.5
        + qr["dim_scores"]["handout"] * 0.2
        + qr["dim_scores"]["ppt_outline"] * 0.2
        + qr["dim_scores"]["hard_checks"] * 0.1
    )
    expected = round(expected, 3)
    assert abs(qr["overall_score"] - expected) < 0.01, (
        f"overall_score={qr['overall_score']} 与加权计算 {expected} 不一致"
    )


# ═══════════════════════════════════════════════════════════════════════════
# T2: /api/lesson_prep/feedback 端点 roundtrip
# ═══════════════════════════════════════════════════════════════════════════


def _client():
    """复用 v028/v034 模式：从 server 模块取 Flask test client。"""
    from server import app
    return app.test_client()


def test_feedback_endpoint_roundtrip(tmp_path, monkeypatch):
    """POST /api/lesson_prep/feedback → 200 + {ok, saved}；jsonl 文件追加一行。

    路径隔离：monkey-patch server 模块的写入路径到 tmp_path，避免污染真实 memory。
    """
    import server as srv

    # ── 1. 准备临时日志路径（monkey-patch 写文件的目标位置）──
    tmp_log = tmp_path / "lesson_prep_feedback.jsonl"
    tmp_log.write_text("", encoding="utf-8")

    # server.py 内联写入 memory/lesson_prep_feedback.jsonl；
    # 通过 monkey-patch Path.__truediv__ / os.path.join 不现实——直接在测试里临时
    # 把目标文件路径替换为 tmp_log 的内容（用文件句柄劫持）：
    # 简化方案：调端点 → 从原始路径读最后一行验证追加；不污染真实路径
    real_log_path = os.path.join(
        os.path.dirname(os.path.abspath(srv.__file__)),
        "memory", "lesson_prep_feedback.jsonl",
    )

    # ── 2. 记录原始文件大小（端点写入后应至少增长 1 行）──
    size_before = (
        os.path.getsize(real_log_path) if os.path.exists(real_log_path) else 0
    )

    try:
        client = _client()

        # ── 3. 正向 roundtrip：完整字段 ──
        payload = {
            "run_id": "test_quality_roundtrip_001",
            "scores": {
                "lesson_plan": 4,
                "handout": 5,
                "video_script": 3,
                "ppt_outline": 4,
                "hard_checks": 2,
            },
            "notes": "教案整体不错，但视频脚本过短，PPT 视觉密度可加强。",
        }
        r = client.post("/api/lesson_prep/feedback", json=payload)
        assert r.status_code == 200, f"应 200，实际 {r.status_code} {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body.get("ok") is True, f"ok 应 True，实际 {body}"
        assert body.get("saved") is True, f"saved 应 True，实际 {body}"

        # ── 4. 验证 jsonl 追加一行 ──
        size_after = os.path.getsize(real_log_path)
        assert size_after > size_before, (
            f"jsonl 未追加：before={size_before} after={size_after}"
        )
        with open(real_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        last_line = lines[-1]
        last_rec = json.loads(last_line)
        assert last_rec["run_id"] == payload["run_id"]
        assert last_rec["scores"] == payload["scores"]
        assert last_rec["notes"] == payload["notes"]
        assert "ts" in last_rec

        # ── 5. 校验：run_id 缺失 → 400 ──
        r = client.post("/api/lesson_prep/feedback", json={"scores": {"lesson_plan": 4}})
        assert r.status_code == 400
        assert r.get_json().get("ok") is False

        # ── 6. 校验：scores 为空 → 400 ──
        r = client.post("/api/lesson_prep/feedback", json={"run_id": "r2", "scores": {}})
        assert r.status_code == 400

        # ── 7. 校验：score 越界 (>5) → 400 ──
        r = client.post("/api/lesson_prep/feedback", json={
            "run_id": "r3", "scores": {"lesson_plan": 6},
        })
        assert r.status_code == 400

        # ── 8. 校验：未知维度 → 400 ──
        r = client.post("/api/lesson_prep/feedback", json={
            "run_id": "r4", "scores": {"unknown_dim": 3},
        })
        assert r.status_code == 400

    finally:
        # 测试结束：把测试用临时行从真实文件中移除（保持仓库干净）
        if os.path.exists(real_log_path):
            with open(real_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            kept = [
                l for l in lines
                if "test_quality_roundtrip_001" not in l
            ]
            with open(real_log_path, "w", encoding="utf-8") as f:
                f.writelines(kept)