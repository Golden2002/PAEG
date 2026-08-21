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
    # 必须位于主循环 presenter.run 之前（骨架先行于 19.6s 生成）
    # §3.79 Round 11 ⭐ 精确匹配主循环调用（paeg.presenter.run）——后台预生成 worker
    # 的 `_pg_presenter.run(` 也含 ".run("，旧断言 src.index("presenter.run") 会
    # 误命中 worker 调用（worker 在 step 事件之前定义）→ 假失败
    idx_step = src.index("event: step")
    idx_presenter = src.index("paeg.presenter.run(")
    assert idx_step < idx_presenter, "step 骨架应在主循环 presenter.run 之前"


def test_frontend_shows_step_topic():
    """前端 step 事件显示 topic（正在讲解第 N 步：xxx）。"""
    html = open(GUI, encoding="utf-8").read()
    assert "正在讲解第" in html, "前端缺'正在讲解第 N 步'提示"
    assert "obj.topic" in html, "前端未读取 step 事件的 topic"


def test_step_topic_truncated():
    """topic 截断 40 字（防超长骨架撑爆事件）。"""
    src = open(SERVER, encoding="utf-8").read()
    assert "[:40]" in src, "topic 应截断 40 字"


def test_frontend_done_clears_abort():
    """§3.79 Round 8 ⭐ 前端 done 事件清 _genAbort（防下一条被吞——E2E 找茬发现）。"""
    html = open(GUI, encoding="utf-8").read()
    assert "_genAbort = null" in html, "前端缺 _genAbort 清理"
    # done 事件处理内清 _genAbort：找第一个 done 事件块内是否含 abort 清理
    idx_done = html.index("event === 'done'")
    # 从 done 事件块到下一个 '} else if' 之间应含 _genAbort 清理（或 __e2eDone 钩子）
    _seg = html[idx_done:idx_done + 1200]
    assert "_genAbort = null" in _seg or "__e2eDone" in _seg, \
        "done 事件块缺 abort 清理/观测钩子"


def test_subagents_imports_sys():
    """§3.79 Round 8 ⭐ subagents.py 顶层 import sys（Planner 异常路径 file=sys.stderr）。

    此前缺 import → LLM 动态规划 JSON 解析失败时，降级 print 抛 NameError
    中断教学流（test_teach_stream_always_completes 暴露，运维友好性 bug）。
    """
    src = open(os.path.join(PROJ, "subagents.py"), encoding="utf-8").read()
    assert re.search(r"^import sys\b", src, re.M), "subagents.py 缺顶层 import sys"
    # file=sys.stderr 用法必须能被 sys import 支撑
    assert "file=sys.stderr" in src
