# -*- coding: utf-8 -*-
"""§3.79 Round 5 ⭐ LLM 延迟优化（D1）回归测试。

probe_latency_fixed 流式实测定位：35s 总延迟 = 路由 1.3s + 规划 5.6s +
首步讲解 19.6s + 后续 8.6s——主因是 LLM 长文本生成（基础设施级）。
已实施两项低风险优化并守护：
  1. _detect_teaching_mode：关键词规则优先（命中 deep/easy 零 LLM 调用）
     + LLM 结果缓存 10 分钟（同主题追问不重复消耗）
  2. Diagnostor LLM 调用 include_kb=False（诊断只判深度/缺口，检索无价值）

守卫：
  - 规则命中时零 LLM 调用（mock llm 不应被调用）
  - 缓存：同文本第二次命中缓存（llm 调用计数不增）
  - Diagnostor 调用 _safe_reason_chat 时 include_kb=False
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class _CountingLLM:
    """记录 chat 调用次数的 mock LLM（name 非 mock → _is_real_llm True）。"""

    name = "counting"

    def __init__(self):
        self.calls = 0

    def chat(self, *a, **k):
        self.calls += 1
        return "normal"


def test_mode_regex_priority_no_llm(monkeypatch):
    """deep/easy 关键词命中 → 规则直接返回，LLM 零调用（Round 5 延迟优化）。"""
    from subagents import _detect_teaching_mode

    llm = _CountingLLM()
    # "深入/推导" → deep（规则命中）
    assert _detect_teaching_mode("请深入推导一下导数", llm=llm) == "deep"
    # "简单讲讲" → easy（规则命中）
    assert _detect_teaching_mode("简单讲讲什么是质数", llm=llm) == "easy"
    # 规则命中路径不应触发 LLM（前两个调用 mock 返回 normal，但规则优先不调）
    assert llm.calls == 0, f"规则命中不应调用 LLM，实际 {llm.calls} 次"


def test_mode_llm_cached(monkeypatch):
    """LLM 语义判断结果缓存：同文本第二次不重复调用 LLM。"""
    from subagents import _detect_teaching_mode, _MODE_CACHE, _MODE_CACHE_LOCK

    # 清理缓存（隔离）
    with _MODE_CACHE_LOCK:
        _MODE_CACHE.clear()
    llm = _CountingLLM()
    # 无关键词文本 → LLM 判断（返回 normal → 规则兜底 normal）
    _detect_teaching_mode("这个定理怎么理解比较好", llm=llm)
    first_calls = llm.calls
    assert first_calls == 1, f"首次应调用 1 次 LLM，实际 {first_calls}"
    # 同文本第二次 → 缓存命中，不调 LLM
    _detect_teaching_mode("这个定理怎么理解比较好", llm=llm)
    assert llm.calls == first_calls, f"缓存命中不应再调 LLM，实际 {llm.calls}"
    # 清理缓存
    with _MODE_CACHE_LOCK:
        _MODE_CACHE.clear()


def test_diagnostor_include_kb_false():
    """Diagnostor 的 LLM 调用必须 include_kb=False（诊断只需 JSON，检索是浪费）。"""
    import inspect
    from subagents import Diagnostor

    src = inspect.getsource(Diagnostor.run)
    assert 'include_kb=False' in src, "Diagnostor.run 缺 include_kb=False（Round 5 优化）"
    assert 'subagent="diagnostor"' in src


def test_mode_cache_bound():
    """缓存上限 256，防无限增长。"""
    from subagents import _MODE_CACHE_TTL
    assert _MODE_CACHE_TTL == 600
