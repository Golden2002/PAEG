# v0.38 STT Backend Deployment Notes

## Pitfalls
1. av <12.3.0 has no wheel for Py3.14. Use av 18.0.0 (cp311-abi3 wheel).
2. HF mirror xet fails (401). Use HF_HUB_DISABLE_XET=1.
3. WhisperModel still hits hub. Use scan_cache_dir() to find local snapshot dir.
4. ctranslate2 Whisper ctor needs str(path), not WindowsPath.

## Model
- Repo: Systran/faster-whisper-small
- Local: C:\Users\<user>\.cache\huggingface\models--Systran--faster-whisper-small\snapshots\<hash>
- Size: 463.7 MB
- Load: ~2s CPU int8

## /api/voice/stt contract
- POST multipart field: audio
- 200: {text: str}
- 400: {error: missing audio file}
- 503: {error: model loading, please wait}
- 503: {error: STT unavailable, use keyboard}
- 500: {error: STT unavailable, use keyboard}

## voice_service.py new API
- transcribe_audio(bytes, suffix=.wav) -> str|None
- stt_available() -> bool
- stt_ready() -> bool
- stt_transcribe(bytes, lang) -> dict (back-compat)

## Env vars
- PAEG_WHISPER_MODEL  = Systran/faster-whisper-small
- PAEG_WHISPER_DEVICE = cpu
- PAEG_WHISPER_COMPUTE_TYPE = int8
- PAEG_WHISPER_LANG = zh
- PAEG_WHISPER_BEAM = 5
- PAEG_WHISPER_PROMPT = mandarin teaching prompt

## E2E test PASSED
- import voice_service OK
- WhisperModel load OK (~2s)
- POST /api/voice/stt with synthetic wav -> 200 Chinese text OK
- POST without audio field -> 400 missing audio OK
- POST before model ready -> 503 model loading OK
