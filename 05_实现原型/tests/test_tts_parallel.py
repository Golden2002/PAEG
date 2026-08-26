# -*- coding: utf-8 -*-
"""R6 TTS 预合成并行化测试（§3.111 ⭐：渲染与 TTS 重叠）。"""
import os
import sys

sys.path.insert(0, r"D:\wbo-workspace\paeg_project\05_实现原型")

import pytest

from tts_parallel import ParallelTTSSynthesizer, pre_synthesize


# ─────────────────────────────────────
# 1. 预合成启动
# ─────────────────────────────────────
class TestPreSynthesize:
    def test_start_spawns_threads(self):
        """start 为每个有旁白的 scene 启动线程。"""
        s = ParallelTTSSynthesizer()
        scenes = [{"id": "s1", "narration": "第一段旁白"},
                  {"id": "s2", "narration": "第二段旁白"},
                  {"id": "s3", "narration": ""}]  # 无旁白 → 跳过
        s.start(scenes)
        assert len(s._threads) == 2  # 只有 s1/s2
        assert s._started is True

    def test_start_idempotent(self):
        """start 只执行一次。"""
        s = ParallelTTSSynthesizer()
        s.start([{"id": "s1", "narration": "旁白"}])
        n = len(s._threads)
        s.start([{"id": "s2", "narration": "旁白2"}])
        assert len(s._threads) == n  # 不重复启动

    def test_join_no_crash(self):
        """join 不崩溃（无真实 edge-tts 时线程静默失败）。"""
        s = ParallelTTSSynthesizer()
        s.start([{"id": "s1", "narration": "测试旁白"}])
        s.join(timeout=5)
        s.cleanup()


# ─────────────────────────────────────
# 2. mux 降级
# ─────────────────────────────────────
class TestMux:
    def test_mux_no_video(self):
        """无视频 → None（不崩溃）。"""
        s = ParallelTTSSynthesizer()
        assert s.mux("/nonexistent/video.mp4", "旁白") is None

    def test_mux_narration_fallback(self):
        """无预合成 + 有旁白 → 走 tts_mux 兜底（无 edge-tts 返回 None 不崩溃）。"""
        s = ParallelTTSSynthesizer()
        # 无 scene → 无预合成 → narration 触发 tts_mux 兜底 → 环境无 edge-tts 返回 None
        r = s.mux("/nonexistent/video.mp4", "测试旁白")
        assert r is None  # 不崩溃即可

    def test_pre_synthesize_helper(self):
        """便捷入口：pre_synthesize(join=True)。"""
        s = pre_synthesize([{"id": "s1", "narration": "测试"}], join=True)
        assert s._started is True
        s.cleanup()
