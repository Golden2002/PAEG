# -*- coding: utf-8 -*-
"""tts_parallel.py — TTS 预合成并行化（§3.111 ⭐ R6 顶尖化）

基于 manim-mcp 的 speculative TTS pre-synthesis 模式：
- 渲染视频的同时，**并行**预合成旁白 MP3（TTS 与渲染重叠）
- 渲染完成后直接 ffmpeg mux（无需等待 TTS）
- 失败不阻塞渲染（静默降级为无旁白视频）

设计：
- `pre_synthesize(scenes, voice)`：并行合成各 scene 旁白 → 落盘 MP3（dict scene_id → path）
- `mux_with_pre_synth(video, tts_map, narration)`：用预合成 MP3 快速 mux
- `ParallelTTSSynthesizer`：线程池并行合成（多 scene 同时 TTS）

用法：
    from tts_parallel import ParallelTTSSynthesizer
    tts = ParallelTTSSynthesizer()
    tts.start(scenes)          # 渲染前启动（后台线程）
    ... 渲染 ...
    tts.join()                 # 渲染完成等待
    path = tts.mux(video)      # 快速合成
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from typing import Dict, List, Optional


class ParallelTTSSynthesizer:
    """并行 TTS 预合成（渲染与 TTS 重叠，节省端到端时间）。"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", max_workers: int = 4):
        self.voice = voice
        self.max_workers = max_workers
        self._threads: List[threading.Thread] = []
        self._results: Dict[str, str] = {}  # scene_id → mp3 path
        self._errors: List[str] = []
        self._tmp_dir = tempfile.mkdtemp(prefix="paeg_tts_par_")
        self._started = False

    def _synth_one(self, scene_id: str, text: str):
        """合成单个 scene 旁白。"""
        try:
            import asyncio
            import edge_tts
            audio = os.path.join(self._tmp_dir, f"{scene_id}.mp3")
            async def _synth():
                comm = edge_tts.Communicate(str(text)[:800], self.voice)
                await comm.save(audio)
            asyncio.run(_synth())
            if os.path.isfile(audio) and os.path.getsize(audio) > 0:
                self._results[scene_id] = audio
        except Exception as e:
            self._errors.append(f"{scene_id}: {str(e)[:80]}")

    def start(self, scenes: List[dict]) -> None:
        """渲染前启动并行 TTS（后台线程）。

        scenes: [{id, narration, ...}]——每 scene 的旁白。
        """
        if self._started:
            return
        self._started = True
        for sc in scenes:
            sid = str(sc.get("id", ""))
            narration = str(sc.get("narration", "") or "").strip()
            if not sid or not narration:
                continue
            t = threading.Thread(target=self._synth_one, args=(sid, narration),
                                 daemon=True)
            self._threads.append(t)
            t.start()

    def join(self, timeout: float = 30.0) -> None:
        """等待全部 TTS 完成（渲染完成时调用）。"""
        for t in self._threads:
            t.join(timeout=timeout)

    def mux(self, manim_video: str, narration: str = "",
            out_path: Optional[str] = None) -> Optional[str]:
        """用预合成 MP3 快速 mux（比串行快，因 TTS 已并行完成）。"""
        if not manim_video or not os.path.isfile(manim_video):
            return None
        # 优先用预合成音频；无则即时合成
        audio_path = None
        if self._results:
            # 拼接所有 scene 音频（简单串接）
            audio_path = os.path.join(self._tmp_dir, "combined.mp3")
            parts = [self._results[k] for k in sorted(self._results.keys())
                     if os.path.isfile(self._results.get(k, ""))]
            if parts:
                try:
                    # 用 ffmpeg concat 合并
                    _list = os.path.join(self._tmp_dir, "concat.txt")
                    with open(_list, "w", encoding="utf-8") as f:
                        for p in parts:
                            f.write(f"file '{p}'\n")
                    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                                    "-i", _list, "-c:a", "aac", audio_path],
                                   capture_output=True, timeout=120)
                    if not os.path.isfile(audio_path):
                        audio_path = parts[0]  # 合并失败用第一个
                except Exception:
                    audio_path = parts[0]
        if audio_path is None and narration:
            # 降级：即时合成（串行兜底）
            try:
                from manim_extensions import tts_mux
                return tts_mux(manim_video, narration, out_path, self.voice)
            except Exception:
                return None
        if audio_path is None:
            return None
        try:
            out = out_path or (manim_video.replace(".mp4", "_tts.mp4"))
            cmd = ["ffmpeg", "-y", "-i", manim_video, "-i", audio_path,
                   "-c:v", "copy", "-c:a", "aac", "-shortest", out]
            subprocess.run(cmd, capture_output=True, timeout=120)
            return out if os.path.isfile(out) else None
        except Exception:
            return None

    def cleanup(self) -> None:
        """清理临时文件。"""
        import shutil
        try:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        except Exception:
            pass


def pre_synthesize(scenes: List[dict], voice: str = "zh-CN-XiaoxiaoNeural",
                   join: bool = True) -> ParallelTTSSynthesizer:
    """便捷入口：预合成（返回已 start 的 synthesizer；join=True 时同步完成）。"""
    synth = ParallelTTSSynthesizer(voice=voice)
    synth.start(scenes)
    if join:
        synth.join()
    return synth
