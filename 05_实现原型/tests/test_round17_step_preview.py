# -*- coding: utf-8 -*-
"""§3.79 Round 7 ⭐ 首步先行体验优化回归测试。

背景：probe_latency_fixed 确认 presenter 首步 LLM 生成 19.6s 是延迟主因——
学生提交后 20s 无任何输出（UX 空白）。优化：step 事件携带 topic 骨架，
前端立即显示"正在讲解：xxx"，让学生感知进度。

守卫：
  - server.py step 事件含 topic 字段（骨架先行）
  - 前端 step 事件处理显示 topic（正在讲解第 N 步：xxx）
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(PROJ, "server.py")
GUI = os.path.join(os.path.dirname(PROJ), "09_GUI前端", "index.html")


def test_step_event_carries_topic():
    """step 事件必须携带 topic 骨架（首步先行优化核心）。"""
    src = open(SERVER, encoding="utf-8").read()
    # step 事件 yield 含 'topic'
    assert "'topic': str(step.get('topic')" in src, "step 事件缺 topic 字段"
    # 必须位于 presenter.run 之前（骨架先行于 19.6s 生成）
    idx_step = src.index("event: step")
    idx_presenter = src.index("presenter.run")
    assert idx_step < idx_presenter, "step 骨架应在 presenter.run 之前"


def test_frontend_shows_step_topic():
    """前端 step 事件显示 topic（正在讲解第 N 步：xxx）。"""
    html = open(GUI, encoding="utf-8").read()
    assert "正在讲解第" in html, "前端缺'正在讲解第 N 步'提示"
    assert "obj.topic" in html, "前端未读取 step 事件的 topic"


def test_step_topic_truncated():
    """topic 截断 40 字（防超长骨架撑爆事件）。"""
    src = open(SERVER, encoding="utf-8").read()
    assert "[:40]" in src, "topic 应截断 40 字"
