# -*- coding: utf-8 -*-
"""§3.79 Q2/Q6/Q7 质量标准落地测试（2026-08-20 目标模式 Round 2）。

覆盖：
  Q2 App Factory（server.create_app，Oracle I1）：
    - create_app 存在且返回 Flask 实例
    - config 注入 PAEG_ENV=production → SESSION_COOKIE_SECURE
    - 模块级 app = create_app()（from server import app 兼容）且路由注册完整
  Q6 教学输出质量信号（services/presentation_quality）：
    - signal_presentation 长度/例子/结构三维 + score
    - aggregate_signals 聚合
  Q7 物料结构检查（services/material_quality）：
    - check_handout / check_lecture_script / check_mindmap 通过/失败用例
    - LessonPrep.run 的 quality_report 含 handout_check/script_check/mindmap_check
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services import material_quality as mq
from services import presentation_quality as pq


# ────────────────────────────────────────────
# Q2 App Factory
# ────────────────────────────────────────────
def test_create_app_factory_exists_and_returns_flask():
    import server
    assert callable(getattr(server, "create_app", None))
    _app2 = server.create_app()
    assert _app2 is not None
    assert _app2.name == "server"  # Flask(__name__) 语义保持


def test_create_app_config_injection():
    import server
    _prod = server.create_app({"PAEG_ENV": "production"})
    assert _prod.config.get("SESSION_COOKIE_SECURE") is True
    assert _prod.config.get("SESSION_COOKIE_HTTPONLY") is True
    _dev = server.create_app({})
    assert _dev.config.get("SESSION_COOKIE_SECURE") is not True


def test_module_level_app_is_factory_instance_with_routes():
    """from server import app 兼容 + 关键路由注册完整（ratchet 铁律）。"""
    import server
    assert server.app is not None
    _urls = [str(r) for r in server.app.url_map.iter_rules()]
    for _u in ("/api/health", "/api/metrics", "/api/metrics/effects",
               "/api/preset/list", "/api/preset/apply", "/api/teach/stream"):
        assert _u in _urls, f"路由缺失: {_u}"


# ────────────────────────────────────────────
# Q6 教学输出质量信号
# ────────────────────────────────────────────
def test_signal_presentation_full():
    s = pq.signal_presentation(
        "这是一段完整的讲解，我们先把概念讲清楚：导数是函数在某一点的瞬时变化率。"
        "首先我们看一个具体的例子，比如生活中的速度计：汽车速度表显示的瞬时速度。"
        "**关键概念**：变化率。其次我们看几何意义，即切线斜率。最后我们小结一下。", "teach", "physics")
    assert s["length_ok"] is True
    assert s["has_examples"] is True
    assert s["has_structure"] is True
    assert s["score"] == 1.0


def test_signal_presentation_sparse():
    s = pq.signal_presentation("好", "teach")
    assert s["length_ok"] is False
    assert s["has_examples"] is False
    assert s["score"] < 0.5


def test_aggregate_signals():
    ag = pq.aggregate_signals([
        {"score": 1.0}, {"score": 0.0}, {"score": 0.8},
    ])
    assert ag["n"] == 3
    assert ag["avg_score"] == 0.6
    assert ag["low_quality_steps"] == 1
    ag2 = pq.aggregate_signals([])
    assert ag2["n"] == 0 and ag2["avg_score"] is None


# ────────────────────────────────────────────
# Q7 物料结构检查
# ────────────────────────────────────────────
def test_check_handout_pass():
    md = ("# 讲义：光合作用\n\n## 一、学习目标\n理解光合作用。\n\n"
          "## 二、核心内容\n光反应与暗反应。\n\n## 三、典型例题\n例题一。\n\n"
          "## 四、巩固练习\n练习一。\n\n## 五、小结\n要点回顾。")
    r = mq.check_handout(md)
    assert r["passed"] is True
    assert len(r["sections_found"]) >= 3


def test_check_handout_fail_sparse():
    r = mq.check_handout("只有一句话。")
    assert r["passed"] is False
    assert any("结构不完整" in e or "过短" in e for e in r["errors"])


def test_check_lecture_script_pass():
    md = ("# 讲稿\n\n## 开场（约 2 分钟）\n同学们好，今天我们学习导数。\n\n"
          "## 主体（约 35 分钟）\n首先讲定义，其次讲几何意义，最后讲应用。\n\n"
          "## 小结（约 3 分钟）\n核心要点回顾。")
    r = mq.check_lecture_script(md)
    assert r["passed"] is True


def test_check_lecture_script_fail():
    r = mq.check_lecture_script("没有结构的短文本")
    assert r["passed"] is False
    assert any("开场/主体/小结" in e or "时长" in e or "过短" in e for e in r["errors"])


def test_check_mindmap_pass():
    md = "- 导数\n  - 定义\n    - 瞬时变化率\n  - 几何意义\n    - 切线斜率\n  - 应用\n    - 最值问题"
    r = mq.check_mindmap(md)
    assert r["passed"] is True
    assert r["list_items"] >= 3
    assert len(r["levels"]) >= 2


def test_check_mindmap_fail():
    r = mq.check_mindmap("没有列表的纯文本")
    assert r["passed"] is False


def test_lesson_prep_quality_report_has_material_checks():
    """LessonPrep.run 的 quality_report 含 handout/script/mindmap 检查（Q7 接线）。"""
    from subagents import LessonPrep, LessonPlanInput

    class _MockLLM:
        name = "test_llm"

        def chat(self, system=None, user=None, messages=None, max_tokens=512, **kwargs):
            u = ""
            if messages:
                u = messages[-1].get("content", "") if isinstance(messages[-1], dict) else str(messages[-1])
            elif user:
                u = str(user)
            if "教学骨架" in u or "教案" in u or "完整教案" in u:
                return json.dumps({
                    "framework": "5E",
                    "objectives_3d": {"knowledge": ["能列举"], "ability": ["能分析"], "literacy": ["能设计"]},
                    "key_points": ["k1", "k2"], "difficulties": ["d1"],
                    "student_analysis": "学情分析",
                    "sections": [{"id": i, "name": f"环节{i}", "duration_min": 5,
                                  "stage": ("pre" if i == 1 else ("post" if i == 6 else "during")),
                                  "case_teaching": "案例", "interaction": "互动"} for i in range(1, 7)],
                    "blackboard": "板书", "reflection": "反思",
                }, ensure_ascii=False)
            if "PPT" in u or "ppt" in u:
                return json.dumps([{"slide": 1, "title": "t", "points": ["a"]}], ensure_ascii=False)
            return "这是备课内容。" if "备课" in u else "这是讲义内容。"

    lp = LessonPrep(model=_MockLLM(), kb=None)
    inp = LessonPlanInput(topic="光合作用", subject="biology", grade="high_school")
    res = lp.run(inp)
    qr = res["quality_report"]
    for _k in ("video_script_check", "handout_check", "script_check", "mindmap_check"):
        assert _k in qr, f"quality_report 缺 {_k}"
        assert qr[_k]["checked"] is True
