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

import logging
logger = logging.getLogger(__name__)

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


def voice_available() -> bool:
    """TTS 是否可用（edge-tts 已安装）。"""
    return EDGE_TTS_OK

# ============ STT (v0.38) ============
# Faster-whisper local transcription (replaces Web Speech API blocked in CN)
# Model: Systran/faster-whisper-small (int8, CPU, ~460MB)
# Cache: ~/.cache/huggingface (default)
# Download: HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1
# Lazy-loaded on first /api/voice/stt call

import tempfile as _tempfile

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_OK = True
except ImportError:
    FASTER_WHISPER_OK = False
    WhisperModel = None  # type: ignore

_WHISPER_MODEL_ID = os.environ.get("PAEG_WHISPER_MODEL", "Systran/faster-whisper-small")
_WHISPER_DEVICE = os.environ.get("PAEG_WHISPER_DEVICE", "cpu")
_WHISPER_COMPUTE_TYPE = os.environ.get("PAEG_WHISPER_COMPUTE_TYPE", "int8")
_WHISPER_LANGUAGE = os.environ.get("PAEG_WHISPER_LANG", "zh")
_WHISPER_BEAM_SIZE = int(os.environ.get("PAEG_WHISPER_BEAM", "5"))
# Teaching-vocabulary prompt (default; override via env PAEG_WHISPER_PROMPT)
_WHISPER_INITIAL_PROMPT = os.environ.get("PAEG_WHISPER_PROMPT", "以下是普通话教学场景。")
_whisper_model = None  # lazy singleton
_whisper_loading = False  # guard against concurrent loads

def _load_whisper_model():
    """Lazy-load Whisper model. Raises on failure."""
    global _whisper_model, _whisper_loading
    if _whisper_model is not None:
        return _whisper_model
    if not FASTER_WHISPER_OK:
        raise RuntimeError("faster-whisper not installed")
    # Resolve local snapshot dir to skip hub metadata fetch (offline-friendly)
    _model_path = _WHISPER_MODEL_ID  # default: use repo_id (faster-whisper will download)
    try:
        from huggingface_hub import scan_cache_dir
        _info = scan_cache_dir(cache_dir=os.path.expanduser("~/.cache/huggingface"))
        for _repo in _info.repos:
            if _repo.repo_id == _WHISPER_MODEL_ID:
                _model_path = list(_repo.revisions)[0].snapshot_path
                break
        if not os.path.isdir(_model_path):
            _model_path = _WHISPER_MODEL_ID
    except Exception as _e:
        logger.warning("[stt] scan_cache_dir failed: %s, fallback to repo_id", _e)
        _model_path = _WHISPER_MODEL_ID
    _whisper_loading = True
    try:
        import time as _time
        _t0 = _time.time()
        logger.info("[stt] loading model=%s device=%s compute=%s", _model_path, _WHISPER_DEVICE, _WHISPER_COMPUTE_TYPE)
        _m = WhisperModel(str(_model_path), device=_WHISPER_DEVICE, compute_type=_WHISPER_COMPUTE_TYPE)
        logger.info("[stt] model loaded in %.1fs", _time.time() - _t0)
        _whisper_model = _m
        return _m
    finally:
        _whisper_loading = False

def _get_whisper_model():
    """Get cached model or None if loading/failed."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    if _whisper_loading:
        return None
    try:
        return _load_whisper_model()
    except Exception as e:
        logger.exception("[stt] load failed: %s", e)
        return None

def transcribe_audio(audio_bytes, suffix=".wav"):
    """Real STT: faster-whisper local transcription.
    audio_bytes: raw audio (MediaRecorder blob or file upload).
    suffix: extension for ffmpeg decode probe (.wav/.webm/.ogg/.mp3).
    Returns transcribed text (str) or None on failure."""
    if not audio_bytes:
        return None
    _model = _get_whisper_model()
    if _model is None:
        return None
    if not suffix.startswith("."):
        suffix = "." + suffix
    _tmp_path = None
    try:
        with _tempfile.NamedTemporaryFile(prefix="paeg_stt_", suffix=suffix, delete=False) as _tf:
            _tf.write(audio_bytes)
            _tmp_path = _tf.name
        _segments, _info = _model.transcribe(
            _tmp_path,
            language=_WHISPER_LANGUAGE,
            beam_size=_WHISPER_BEAM_SIZE,
            vad_filter=True,
            initial_prompt=_WHISPER_INITIAL_PROMPT,
        )
        _parts = []
        for _seg in _segments:
            _t = (_seg.text or "").strip()
            if _t:
                _parts.append(_t)
        _text = " ".join(_parts).strip()
        logger.info("[stt] lang=%s prob=%.2f text_len=%d",
                    getattr(_info, "language", "?"),
                    getattr(_info, "language_probability", 0.0),
                    len(_text))
        return _text or None
    except Exception as e:
        logger.exception("[stt] transcribe failed: %s", e)
        return None
    finally:
        if _tmp_path:
            try:
                os.unlink(_tmp_path)
            except Exception:
                pass

def stt_transcribe(audio_bytes, lang="zh-CN"):
    """STT contract shim (backward compatible).
    Returns {ok: bool, text: str, error?: str}"""
    if not audio_bytes:
        return {"ok": False, "error": "空音频", "text": ""}
    _text = transcribe_audio(audio_bytes, suffix=".wav")
    if _text is None:
        return {"ok": False, "error": "语音识别失败", "text": ""}
    return {"ok": True, "text": _text, "lang": lang}

def stt_available():
    """STT package available (model lazy-loaded on first call)."""
    return FASTER_WHISPER_OK

def stt_ready():
    """STT model already loaded into memory."""
    return _whisper_model is not None

