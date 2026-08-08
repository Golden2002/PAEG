# -*- coding: utf-8 -*-
"""v0.36 ⭐ 语音服务（STT + TTS）——纯 I/O adapter，不进 subagent 调度。

v1 方案（Oracle 评审）：免 key 双端
  - TTS: edge-tts（免费，中文女声 zh-CN-XiaoxiaoNeural）→ 写 uploads/voice/<learner_id>/<sha1>.mp3
  - STT: 浏览器 Web Speech API（前端完成，后端仅保留契约）
未来 v2：替换 provider（讯飞 WS / Azure Speech）不改接口。
"""
from __future__ import annotations
import hashlib, os, time
from pathlib import Path
from typing import Optional

# edge-tts 懒加载（未安装时优雅降级）
try:
    import edge_tts
    EDGE_TTS_OK = True
except ImportError:
    EDGE_TTS_OK = False

_BASE_DIR = Path(__file__).parent
_VOICE_DIR = _BASE_DIR / "uploads" / "voice"

def _voice_path(learner_id: str, text_hash: str) -> Path:
    d = _VOICE_DIR / str(learner_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{text_hash}.mp3"

def tts_synthesize(text: str, voice: str = "zh-CN-XiaoxiaoNeural",
                   learner_id: str = "anon") -> Optional[str]:
    """文本转语音 → 返回可访问 URL（/uploads/voice/<id>/<hash>.mp3）或 None。
    edge-tts 未安装 / 生成失败 → None（前端按钮变灰，不报错）。"""
    if not EDGE_TTS_OK or not text:
        return None
    try:
        text_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        path = _voice_path(learner_id, text_hash)
        if path.exists():  # 缓存命中（同文本只生成一次）
            return f"/uploads/voice/{learner_id}/{text_hash}.mp3"
        import asyncio
        async def _gen():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(path))
        asyncio.run(_gen())
        if path.exists():
            return f"/uploads/voice/{learner_id}/{text_hash}.mp3"
        return None
    except Exception:
        return None

def stt_transcribe(audio_bytes: bytes, lang: str = "zh-CN") -> dict:
    """STT 契约占位（v1 由浏览器 Web Speech API 完成，不走后端）。
    未来 v2 替换 provider 时实现此函数。"""
    return {"ok": False, "hint": "v1 语音识别由浏览器 Web Speech API 完成（前端）", "text": ""}

def voice_available() -> bool:
    """TTS 是否可用（edge-tts 已安装）。"""
    return EDGE_TTS_OK
