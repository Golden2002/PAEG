# -*- coding: utf-8 -*-
"""§3.78 B1-B5 连通性断点修复测试（2026-08-15）。

覆盖（对应技术全景 §10.21 断点清单）：
  B1 备课未接联网检索 → _lesson_web_materials（素材注入 run 输出 materials.web）
  B2 备课未接用户资料库 → _lesson_user_materials（BM25 命中 usr_knowledge）
  B3 备课视频脚本未过脚本检查 → validate_lesson_script 接入 quality_report
  B4 查资料未接联网检索 → services/file_operation._web_fallback_chunks + 接线标志
  B5 倾诉未接真实知识库 → _retrieve_affection_kb（信号门 + KB 命中注入）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import knowledge_base as _kb_mod
import lib.ingest.readers as _readers_mod
import subagents
from subagents import (
    LessonPrep,
    LessonPlanInput,
    _lesson_user_materials,
    _lesson_web_materials,
    _retrieve_affection_kb,
)
from visual_script_validator import validate_lesson_script
from services import file_operation


class MockLLM:
    """模拟真实 LLM（name 非 'mock'），记录最近一次 user 消息供断言。"""

    name = "test_llm"
    last_user = ""

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kwargs):
        if messages:
            u = messages[-1].get("content", "") if isinstance(messages[-1], dict) else str(messages[-1])
        elif user:
            u = str(user)
        else:
            u = ""
        MockLLM.last_user = u
        if "教学骨架" in u or "教案" in u or "完整教案" in u:
            return json.dumps({
                "framework": "5E",
                "objectives_3d": {"knowledge": ["能列举"], "ability": ["能分析"], "literacy": ["能设计"]},
                "key_points": ["k1", "k2"],
                "difficulties": ["d1"],
                "student_analysis": "学情分析",
                "sections": [{"id": i, "name": f"环节{i}", "duration_min": 5,
                              "stage": ("pre" if i == 1 else ("post" if i == 6 else "during")),
                              "case_teaching": "案例", "interaction": "互动"} for i in range(1, 7)],
                "blackboard": "板书",
                "reflection": "反思",
            }, ensure_ascii=False)
        if "PPT" in u or "ppt" in u:
            return json.dumps([{"slide": 1, "title": "t", "points": ["a"]}], ensure_ascii=False)
        return "这是备课内容。" if "备课" in u else "这是讲义内容。"


class MockKB:
    pass


class FakeLearner:
    id = "u_b1b5_test"


@pytest.fixture
def lesson_prep():
    # 预算隔离：_LESSON_PLAN_BUDGET_USED 是模块级累计全局（25000 上限），
    # 其它测试文件的多次 run 会耗尽它导致本文件 run 走静态兜底（MockLLM.chat 不被调用）。
    from subagents import _reset_lesson_plan_budget
    _reset_lesson_plan_budget()
    return LessonPrep(model=MockLLM(), kb=MockKB())


# ────────────────────────────────────────────────────────────
# B1 备课联网检索素材
# ────────────────────────────────────────────────────────────
def test_lesson_web_materials_gate_off(monkeypatch):
    """PAEG_LESSON_NO_WEB=1（测试默认）→ 不联网，返回空。"""
    monkeypatch.setenv("PAEG_LESSON_NO_WEB", "1")
    assert _lesson_web_materials("光合作用", "biology", MockLLM()) == ""


def test_lesson_web_materials_failure_returns_empty(monkeypatch):
    """should_search 通过但检索抛异常 → 空串（备课不中断）。"""
    monkeypatch.delenv("PAEG_LESSON_NO_WEB", raising=False)
    import web_search_tool as _wst
    monkeypatch.setattr(_wst, "should_search", lambda q: True)

    def _boom(*a, **k):
        raise RuntimeError("网络失败")
    monkeypatch.setattr(_wst, "web_search_multi", _boom)
    assert _lesson_web_materials("光合作用", "biology", MockLLM()) == ""


def test_lesson_web_materials_formats_hits(monkeypatch):
    """检索命中 → 素材块含来源标题（数据化注入，可引用）。"""
    monkeypatch.delenv("PAEG_LESSON_NO_WEB", raising=False)
    import web_search_tool as _wst
    monkeypatch.setattr(_wst, "should_search", lambda q: True)
    monkeypatch.setattr(
        _wst, "web_search_multi",
        lambda *a, **k: [{"title": "光合作用原理", "url": "https://x.example/1",
                          "content": "光反应与暗反应的过程详解"}],
    )
    block = _lesson_web_materials("光合作用", "biology", MockLLM())
    assert "联网课程素材" in block
    assert "光合作用原理" in block
    assert "https://x.example/1" in block


def test_lesson_run_web_materials_injected(lesson_prep, monkeypatch):
    """B1 接线：联网素材块应进入备课各步骤的 user 提示词（syllabus 步验证）。"""
    monkeypatch.setattr(subagents, "_lesson_web_materials",
                        lambda topic, subject, llm: "【联网课程素材】fake-web")
    monkeypatch.setattr(subagents, "_lesson_user_materials",
                        lambda learner, topic: "")
    inp = LessonPlanInput(topic="光合作用", subject="biology", grade="high_school")
    res = lesson_prep.run(inp)
    assert res["materials"]["web"] is True
    assert "【联网课程素材】fake-web" in MockLLM.last_user


# ────────────────────────────────────────────────────────────
# B2 备课用户资料库
# ────────────────────────────────────────────────────────────
def test_lesson_user_materials_no_learner():
    assert _lesson_user_materials(None, "光合作用") == ""


def test_lesson_user_materials_no_corpus(monkeypatch):
    monkeypatch.setattr(_readers_mod, "read_corpus_full", lambda uid: [])
    assert _lesson_user_materials(FakeLearner(), "光合作用") == ""


def test_lesson_user_materials_bm25_hits(monkeypatch):
    """用户资料库 BM25 命中 → 素材块含文件名与片段（备课输入）。"""
    _text = "光合作用是植物利用光能合成有机物的过程。光反应与暗反应是两个主要阶段。"
    monkeypatch.setattr(
        _readers_mod, "read_corpus_full",
        lambda uid: [{"name": "植物学讲义.md", "path": "Library/usr_knowledge/u/植物学讲义.md",
                      "type": "md", "text": _text, "ok": True, "chars": len(_text)}],
    )
    block = _lesson_user_materials(FakeLearner(), "光合作用")
    assert "用户资料库素材" in block
    assert "植物学讲义.md" in block
    assert "光合作用" in block


def test_lesson_run_user_materials_meta(lesson_prep, monkeypatch):
    """B2 接线：run 输出 materials.user_library 反映用户资料检索状态。"""
    monkeypatch.setattr(subagents, "_lesson_user_materials",
                        lambda learner, topic: "【用户资料库素材】fake-usr")
    monkeypatch.setattr(subagents, "_lesson_web_materials",
                        lambda topic, subject, llm: "")
    inp = LessonPlanInput(topic="光合作用", subject="biology", grade="high_school")
    res = lesson_prep.run(inp)
    assert res["materials"]["user_library"] is True
    assert "【用户资料库素材】fake-usr" in MockLLM.last_user


# ────────────────────────────────────────────────────────────
# B3 备课视频脚本过脚本检查
# ────────────────────────────────────────────────────────────
def test_validate_lesson_script_pass():
    ok = "## 镜头 1（开场 30 秒）\n画面：生活场景\n旁白：引入主题。\n\n" \
         "## 镜头 2（主体 60 秒）\n画面：动画示意图\n旁白：核心机制拆解。\n\n" \
         "## 镜头 3（总结 20 秒）\n画面：回顾要点\n旁白：要点复述。"
    r = validate_lesson_script(ok)
    assert r["passed"] is True
    assert r["checked"] is True
    assert r["scene_count"] >= 3


def test_validate_lesson_script_missing_parts():
    bad = ("## 镜头 1（开场 30 秒）\n画面：生活场景，人物入场。\n\n"
           "## 镜头 2（主体 60 秒）\n画面：动画演示核心机制。\n")  # 两个镜头都缺旁白
    r = validate_lesson_script(bad)
    assert r["passed"] is False
    assert any("旁白" in e or "镜头数" in e for e in r["errors"])


def test_lesson_run_video_script_check_wired(lesson_prep):
    """B3 接线：video_script 过校验并写入 quality_report + 返回契约。"""
    inp = LessonPlanInput(topic="光合作用", subject="biology", grade="high_school")
    res = lesson_prep.run(inp)
    assert "video_script_check" in res
    assert res["video_script_check"]["checked"] is True
    assert "video_script_check" in res["quality_report"]
    assert res["quality_report"]["video_script_check"]["checked"] is True


# ────────────────────────────────────────────────────────────
# B4 查资料 BM25 无匹配 → 联网兜底
# ────────────────────────────────────────────────────────────
def test_web_fallback_chunks_offline_empty(monkeypatch):
    monkeypatch.delenv("PAEG_LESSON_NO_WEB", raising=False)
    import web_search_tool as _wst
    monkeypatch.setattr(_wst, "should_search", lambda q: False)
    assert file_operation._web_fallback_chunks("量子力学", None) == []


def test_web_fallback_chunks_formats(monkeypatch):
    monkeypatch.delenv("PAEG_LESSON_NO_WEB", raising=False)
    import web_search_tool as _wst
    monkeypatch.setattr(_wst, "should_search", lambda q: True)
    monkeypatch.setattr(
        _wst, "web_search_multi",
        lambda *a, **k: [{"title": "量子力学入门", "url": "https://q.example/1",
                          "content": "波函数描述量子态"}],
    )
    chunks = file_operation._web_fallback_chunks("量子力学", MockLLM(), top_k=2)
    assert len(chunks) >= 1
    assert chunks[0]["doc_name"].startswith("联网检索_")
    assert "量子力学入门" in chunks[0]["text"]


def test_try_file_operation_web_fallback_wired(monkeypatch):
    """B4 接线：本地 BM25 无匹配 → 联网兜底启用（done 事件 web_fallback=true）。"""
    # 用户语料仅含"导数"，查询"量子力学"→ BM25 必然无匹配（read_corpus_full 真实形状）
    _text = "导数是函数在某点的瞬时变化率。导数用于描述变化快慢。"
    monkeypatch.setattr(
        _readers_mod, "read_corpus_full",
        lambda uid: [{"name": "数学讲义.md", "path": "Library/usr_knowledge/u/数学讲义.md",
                      "type": "md", "text": _text, "ok": True, "chars": len(_text)}],
    )
    monkeypatch.setattr(
        file_operation, "_web_fallback_chunks",
        lambda text, llm, top_k=3: [{"doc_name": "联网检索_1_测试", "chunk_index": 0,
                                     "text": "[联网检索] 测试\nURL: u\n内容", "score": 0.0}],
    )

    class _LLM:
        name = "test_llm"

        def chat(self, *a, **k):
            return "这是联网补充的回答。"

    resp = file_operation._try_file_operation("u_b4_test", "我的讲义里有量子力学的内容吗", _LLM())
    assert resp is not None, "文件操作应命中"
    events = "".join(
        c if isinstance(c, str) else c.decode("utf-8", errors="ignore")
        for c in resp.response
    )
    assert "web_fallback" in events
    assert "true" in events.lower()


# ────────────────────────────────────────────────────────────
# B5 倾诉选择性接入真实知识库
# ────────────────────────────────────────────────────────────
def test_retrieve_affection_kb_no_signal():
    """无学习内容信号 → 不检索（v0.22.1 防噪音原则保留）。"""
    assert _retrieve_affection_kb("我很难过，感觉撑不下去了") == ""


def test_retrieve_affection_kb_signal_no_hit(monkeypatch):
    """有学习信号但 KB 无命中 → 空串。"""

    class _FakeKB:
        def search(self, *a, **k):
            return []

    monkeypatch.setattr(_kb_mod, "KnowledgeBase", _FakeKB)
    assert _retrieve_affection_kb("我考试没考好，特别难受，导数也不会") == ""


def test_retrieve_affection_kb_with_hit(monkeypatch):
    """情绪+学习并存 → KB 命中注入"可参考的准确资料"块。"""

    class _FakeKB:
        def search(self, *a, **k):
            return [{"concept_id": "导数", "snippet": "函数在某点的瞬时变化率"}]

    monkeypatch.setattr(_kb_mod, "KnowledgeBase", _FakeKB)
    block = _retrieve_affection_kb("我考试没考好，特别难受，导数也不会")
    assert "可参考的准确资料" in block
    assert "导数" in block


# ────────────────────────────────────────────────────────────
# 总需求落地：/api/metrics 指标端点（D1/B3 基础）
# ────────────────────────────────────────────────────────────
def test_api_metrics_endpoint():
    """§3.78 /api/metrics：uptime + 观测性指标聚合 + 事件计数（SLO 看板基础）。"""
    from server import app
    client = app.test_client()
    r = client.get("/api/metrics")
    assert r.status_code == 200, f"status={r.status_code} {r.get_data(as_text=True)[:200]}"
    body = r.get_json()
    assert "uptime_seconds" in body
    assert "metrics" in body
    assert "events_count" in body
    assert body["status"] == "ok"
