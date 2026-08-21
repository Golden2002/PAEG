# -*- coding: utf-8 -*-
"""§3.81 P1-② 备课反馈聚合面板测试。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.feedback_aggregator import (
    aggregate_feedback, feedback_to_prompt_patch, DIMS,
)


class FakeRow:
    """构造一条反馈数据。"""

    @staticmethod
    def make(run_id="r1", scores=None, notes="", ts="2026-08-21T10:00:00"):
        import json
        return json.dumps({
            "ts": ts,
            "run_id": run_id,
            "scores": scores or {"lesson_plan": 4, "handout": 3,
                                 "video_script": 2, "ppt_outline": 4, "hard_checks": 5},
            "notes": notes,
        }, ensure_ascii=False)


def _write_feedback(tmp_path, lines):
    """写临时 feedback jsonl，monkeypatch 路径。"""
    import services.feedback_aggregator as fa
    p = tmp_path / "lesson_prep_feedback.jsonl"
    p.write_text("\n".join(lines), encoding="utf-8")
    fa._FEEDBACK_LOG = str(p)


def test_dims_defined():
    """S1：反馈维度与端点契约一致。"""
    assert set(DIMS) == {"lesson_plan", "handout", "video_script", "ppt_outline", "hard_checks"}


def test_aggregate_empty():
    """S2 边界：无反馈 → 空结构（不崩，明确标注 total=0）。"""
    import services.feedback_aggregator as fa
    fa._FEEDBACK_LOG = "/nonexistent/path.jsonl"
    a = aggregate_feedback()
    assert a["total"] == 0
    assert a["avg_by_dim"] == {}
    assert a["overall"] == 0.0


def test_aggregate_single(tmp_path):
    """S3 主路径：单条反馈 → 维度均分/overall/低分主题正确。"""
    _write_feedback(tmp_path, [FakeRow.make(run_id="r1",
                                            scores={"lesson_plan": 4, "handout": 3,
                                                    "video_script": 2, "ppt_outline": 4,
                                                    "hard_checks": 5},
                                            notes="教案不错 但视频脚本太啰嗦")])
    a = aggregate_feedback()
    assert a["total"] == 1
    assert a["avg_by_dim"]["lesson_plan"] == 4.0
    assert a["avg_by_dim"]["video_script"] == 2.0
    assert a["overall"] == pytest.approx(3.6, abs=0.01)
    # 低分主题（video_script=2 < 3）
    assert len(a["low_score_topics"]) == 1
    assert a["low_score_topics"][0]["run_id"] == "r1"
    assert "video_script" in a["low_score_topics"][0]["low_dims"]


def test_aggregate_multiple_avg(tmp_path):
    """S4 主路径：多条反馈 → 均分正确。"""
    _write_feedback(tmp_path, [
        FakeRow.make(run_id="r1", scores={"lesson_plan": 4, "handout": 4,
                                          "video_script": 4, "ppt_outline": 4, "hard_checks": 4}),
        FakeRow.make(run_id="r2", scores={"lesson_plan": 2, "handout": 2,
                                          "video_script": 2, "ppt_outline": 2, "hard_checks": 2}),
    ])
    a = aggregate_feedback()
    assert a["total"] == 2
    assert a["avg_by_dim"]["lesson_plan"] == 3.0
    assert a["overall"] == pytest.approx(3.0, abs=0.01)
    # 低分主题：仅 r2（全维度 2）命中；r1（全维度 4）不命中
    assert len(a["low_score_topics"]) == 1
    assert a["low_score_topics"][0]["run_id"] == "r2"


def test_aggregate_corrupt_rows(tmp_path):
    """S5 防御：损坏行跳过（不崩）。"""
    _write_feedback(tmp_path, ["{invalid json", FakeRow.make(run_id="r_ok")])
    a = aggregate_feedback()
    assert a["total"] == 1
    assert a["avg_by_dim"]["lesson_plan"] == 4.0


def test_feedback_to_prompt_patch(tmp_path):
    """S6 反哺：低分维度 → 结构化补丁建议。"""
    _write_feedback(tmp_path, [
        FakeRow.make(run_id="r1", scores={"lesson_plan": 2, "handout": 4,
                                          "video_script": 4, "ppt_outline": 4, "hard_checks": 4}),
    ])
    p = feedback_to_prompt_patch()
    assert p["patches"], "应产生至少 1 条补丁（lesson_plan=2 < 3.5）"
    dims = [x["dim"] for x in p["patches"]]
    assert "lesson_plan" in dims
    assert "条反馈" in p["summary"]


def test_feedback_to_prompt_patch_empty():
    """S7 边界：无反馈 → 空补丁 + 明确 summary。"""
    import services.feedback_aggregator as fa
    fa._FEEDBACK_LOG = "/nonexistent/path.jsonl"
    p = feedback_to_prompt_patch()
    assert p["patches"] == []
    assert "暂无" in p["summary"]
