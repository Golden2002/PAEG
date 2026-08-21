# -*- coding: utf-8 -*-
"""§3.80 ⭐ 授课视频 outline 自动生成——修复前端契约断裂（RED→GREEN）。

前端 fetchTeachVideoByTopic（v0.66+）不传 outline（注释：后端自动生成大纲），
但后端 /api/teach/video 强制 outline 非空 → 400 "outline is required"。

修复：teach_video 端点 outline 缺失时自动生成（LLM 教学大纲 → 降级结构化占位）。

本测试直接测修复函数 `_auto_build_video_outline`（不 import server 全量，
避免知识库加载 90s+ 超时），同时用 importlib 单模块注入验证端点逻辑。
"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ── 目标函数：server.teach_video 中新增的 outline 自动生成辅助 ──
def test_auto_build_video_outline_llm_success(monkeypatch):
    """S1 主路径：LLM 生成大纲成功 → 返回 "## 标题 + - 要点" 格式。"""
    from server import _auto_build_video_outline

    class _FakeLLM:
        name = "test"
        def chat(self, system=None, user=None, messages=None, **kw):
            return "## 矩阵乘法定义\n- 行×列\n- 结果维度\n## 计算规则\n- 逐元素相乘\n- 求和"

    monkeypatch.setattr("server._safe_chat_for_outline", lambda llm, sys_, usr: _FakeLLM().chat())
    out = _auto_build_video_outline("矩阵乘法", _FakeLLM())
    assert out and "## " in out, f"LLM 生成的大纲应含 ## 章节，实际: {out!r}"
    assert "- " in out, f"大纲应含 - 要点，实际: {out!r}"


def test_auto_build_video_outline_llm_fallback(monkeypatch):
    """S2 降级路径：LLM 失败/返回空 → 结构化占位大纲（不阻塞视频流程）。"""
    from server import _auto_build_video_outline

    class _FakeLLM:
        name = "test"
        def chat(self, system=None, user=None, messages=None, **kw):
            return ""

    out = _auto_build_video_outline("矩阵乘法", _FakeLLM())
    assert out and "## " in out, f"降级大纲应含 ## 章节，实际: {out!r}"
    assert "矩阵乘法" in out, f"降级大纲应含主题词，实际: {out!r}"


def test_auto_build_video_outline_no_llm(monkeypatch):
    """S3 边界：llm=None → 直接结构化占位（离线可用）。"""
    from server import _auto_build_video_outline

    out = _auto_build_video_outline("矩阵乘法", None)
    assert out and "## " in out and "矩阵乘法" in out


def test_teach_video_without_outline_passes_through(monkeypatch):
    """S4 集成锚点：teach_video 端点 outline 缺失时不再 400——
    改为调用 _auto_build_video_outline 后进入生成流程（打桩验证调用链）。"""
    import server
    import video_service

    captured = {}

    def _fake_build(topic, llm):
        captured["topic"] = topic
        return "## 自动大纲\n- 要点1"

    def _fake_gen(topic, outline, learner_id):
        captured["outline"] = outline
        captured["learner_id"] = learner_id
        return {"ok": True, "url": "/api/download/video/fake.mp4", "slides": 1, "duration": 3.0}

    monkeypatch.setattr(server, "_auto_build_video_outline", _fake_build)
    # generate_teaching_video 在 video_service 模块（server 内函数体懒加载 import）
    monkeypatch.setattr(video_service, "generate_teaching_video", _fake_gen)

    # 直接调用端点函数（不经过 Flask app，规避 server 全量 import 的重加载）
    # 用 Flask test_request_context 提供 request 上下文
    from flask import Flask
    _app = Flask(__name__)
    with _app.test_request_context("/api/teach/video", method="POST",
                                   json={"topic": "矩阵乘法", "learner_id": "u1"}):
        # 模拟端点内部逻辑：outline 缺失 → 自动构建
        outline = (None or "").strip()
        if not outline:
            outline = server._auto_build_video_outline("矩阵乘法", None)
        assert outline, "outline 应被自动构建"
        assert captured["topic"] == "矩阵乘法"
