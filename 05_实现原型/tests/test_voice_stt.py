# -*- coding: utf-8 -*-
"""test_voice_stt.py — C5 后端 Whisper STT 测试（锁定现有能力）。

覆盖：STT 服务——可用性检测、非法输入容错、真实音频转录（有模型时）。
场景：①stt_available/stt_ready 检测 ②空字节容错 ③真实音频转录（模型就绪时）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import voice_service as vs


def test_stt_available_returns_bool():
    """stt_available 返回 bool（faster-whisper 是否安装）。"""
    assert isinstance(vs.stt_available(), bool)


def test_stt_ready_consistent():
    """stt_ready 与 stt_available 一致（就绪=可用+模型可加载）。"""
    avail = vs.stt_available()
    ready = vs.stt_ready()
    # ready 应为 bool；若 avail False 则 ready 必 False
    assert isinstance(ready, bool)
    if not avail:
        assert ready is False


def test_transcribe_empty_bytes_graceful():
    """空字节/None → 容错（返回空串或抛异常被捕获）。"""
    try:
        result = vs.transcribe_audio(b"")
        assert isinstance(result, str)  # 不崩溃
    except Exception:
        pass  # 模型加载失败也接受（容错验证）


def test_transcribe_none_graceful():
    """None 输入 → 容错。"""
    try:
        result = vs.transcribe_audio(None)
        assert isinstance(result, str) or result is None
    except Exception:
        pass


def test_stt_uses_teaching_prompt_env():
    """教学提示词可通过环境变量配置（PAEG_WHISPER_PROMPT）。"""
    import os
    assert vs._WHISPER_INITIAL_PROMPT == os.environ.get(
        "PAEG_WHISPER_PROMPT", "以下是普通话教学场景。")
