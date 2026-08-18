"""voice.py — 语音蓝图（v0.36 TTS / v0.38 STT）。

§3.45 架构拆分 P1-1：自 server.py 迁出（原 L2796-2811 / L2862-2902），行为字节级不变。
依赖注入：voice_service 懒加载（无 server 全局依赖）。
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from module_registry import require_module

bp = Blueprint("voice", __name__)


@bp.route("/api/voice/tts", methods=["POST"])
@require_module("voice")
def voice_tts():
    """v0.36 ⭐ 文本转语音（edge-tts，免 key）。请求 {text, learner_id} → {url}"""
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()[:2000]
    learner_id = data.get("learner_id") or "anon"
    if not text:
        return jsonify({"ok": False, "error": "空文本"}), 400
    from voice_service import tts_synthesize, voice_available
    if not voice_available():
        return jsonify({"ok": False, "error": "语音暂不可用（edge-tts 未安装）"}), 503
    url = tts_synthesize(text, learner_id=learner_id)
    if url:
        return jsonify({"ok": True, "url": url})
    return jsonify({"ok": False, "error": "语音合成失败"}), 500


@bp.route("/api/voice/stt", methods=["POST"])
@require_module("voice")
def voice_stt():
    """v0.38 ★ STT (faster-whisper local)."""
    """POST multipart field "audio" -> "{text: ...}" or 4xx/5xx."""
    from voice_service import transcribe_audio, stt_available, stt_ready
    if not stt_available():
        return jsonify({"error": "语音识别服务不可用，请改用键盘输入"}), 503
    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "缺少音频文件"}), 400
    # Infer suffix from filename or content_type
    _fname = (getattr(f, "filename", "") or "").lower()
    _ct = (f.content_type or "").lower()
    if _fname.endswith(".webm"):
        _suffix = ".webm"
    elif _fname.endswith(".ogg"):
        _suffix = ".ogg"
    elif _fname.endswith(".mp3"):
        _suffix = ".mp3"
    elif _fname.endswith(".m4a"):
        _suffix = ".m4a"
    elif "webm" in _ct or "opus" in _ct:
        _suffix = ".webm"
    elif "ogg" in _ct:
        _suffix = ".ogg"
    elif "mpeg" in _ct or "mp3" in _ct:
        _suffix = ".mp3"
    else:
        _suffix = ".wav"
    try:
        _text = transcribe_audio(f.read(), suffix=_suffix)
    except Exception:
        return jsonify({"error": "语音识别服务不可用，请改用键盘输入"}), 500
    if _text is None:
        if not stt_ready():
            return jsonify({"error": "模型加载中，请稍候"}), 503
        # v0.41 ⭐ 修复：无识别结果（静音/无语音）是正常场景 → 200 + 空文本
        # 此前返回 500 → 前端误报"服务不可用"，实际是"没识别到语音"
        return jsonify({"text": "", "ok": False, "error": "未识别到语音内容"})
    return jsonify({"text": _text, "ok": True})
