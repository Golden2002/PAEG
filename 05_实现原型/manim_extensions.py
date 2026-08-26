
# -*- coding: utf-8 -*-
"""manim_extensions.py —— §3.89 Step 4/5 ⭐ Manim 缺口修复扩展

对标 claude2video / Code2Video：
- scope_refine()：三级修复（L1 场景内修补 → L2 重写1-3场景 → L3 全剧本重生）
- tts_mux()：Audio-First TTS 同步（edge-tts 生成 narration → ffmpeg mux 到视频）
补 Manim 管线缺口 #1（Audio-First TTS）和 #3（ScopeRefine 三级修复）。
"""
from __future__ import annotations

"""
[LEGACY · 历史实现] 自 2026-08-26（§3.112）起冻结，仅供 PAEG_USE_MATERIAL_PLUGIN=0 兜底。
新代码必须使用插件 paeg-teaching-materials（material_router._gen_* → services.material_bridge.execute）。
禁止在新模块 import 本模块，违规将被 audit_check 拦截。
最后维护: PAEG Team · 关联: §3.110/§3.111/§3.112
"""

import json
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

def scope_refine(script: Dict[str, Any], errors: List[str],
                 llm=None, level: int = 1) -> Optional[Dict[str, Any]]:
    """三级修复：按错误严重度升级修复范围。

    Level 1（场景内修补）：保持 scene 结构，只修违反的字段
    Level 2（重写 1-3 场景）：重写报错的 scene
    Level 3（全剧本重生）：整体重新生成
    """
    if not script or not isinstance(script, dict):
        return None
    scenes = script.get("scenes") or []
    if not scenes:
        return None

    try:
        from subagents import _safe_chat

        if level <= 1:
            if llm is None:
                return script  # 无 LLM → 保持原样（调用方决定）
            # L1：场景内修补（保持结构，只修违反项）
            _sys = ("你是 Manim 剧本修复器。根据错误修改剧本，保持 scene 结构，"
                    "只修违反项，输出修复后的完整剧本 JSON。")
            _usr = (f"剧本：{json.dumps(script, ensure_ascii=False)[:3000]}\n"
                    f"错误：{errors}\n请修复。")
            _raw = _safe_chat(llm, _sys, _usr, max_tokens=3000)
            if _raw:
                _m = re.search(r"\{.*\}", _raw, re.S)
                if _m:
                    return json.loads(_m.group(0))
            return script  # 修复失败保留原样

        if level == 2 and llm is not None:
            # L2：重写报错 scene（识别含错误关键词的 scene）
            _bad_scenes = []
            for sc in scenes:
                _s = json.dumps(sc, ensure_ascii=False)
                if any(k in _s for k in errors):
                    _bad_scenes.append(sc)
            if not _bad_scenes:
                _bad_scenes = scenes[:2]  # 无法定位时重写前 2 个
            _sys = ("你是 Manim 剧本修复器。重写以下 scene，保持主题相关，"
                    "修复错误，输出修复后的 scene JSON 数组。")
            _usr = (f"需重写的 scene：{json.dumps(_bad_scenes, ensure_ascii=False)}\n"
                    f"错误：{errors}\n请重写。")
            _raw = _safe_chat(llm, _sys, _usr, max_tokens=3000)
            if _raw:
                _m = re.search(r"\[.*\]", _raw, re.S)
                if _m:
                    try:
                        new_scenes = json.loads(_m.group(0))
                        # 替换报错 scene（按索引尽量对齐）
                        _idx = 0
                        for sc in scenes:
                            _s = json.dumps(sc, ensure_ascii=False)
                            if any(k in _s for k in errors) and _idx < len(new_scenes):
                                sc.update(new_scenes[_idx])
                                _idx += 1
                        return script
                    except Exception:
                        pass
            return script

        # L3：全剧本重生
        return None  # 由调用方触发整体重生成
    except Exception:
        return script

def tts_mux(manim_video: str, narration: str, out_path: Optional[str] = None,
            voice: str = "zh-CN-XiaoxiaoNeural") -> Optional[str]:
    """Audio-First TTS 同步：edge-tts 生成旁白 MP3 → ffmpeg mux 到 Manim 视频。

    Args:
        manim_video: Manim 渲染的 mp4 路径
        narration: 旁白文本（中文）
        out_path: 输出 mp4 路径（None → 覆盖原视频旁）
        voice: edge-tts 音色

    Returns: 合成后 mp4 路径；失败返回 None（不阻塞原视频）。
    """
    if not manim_video or not os.path.isfile(manim_video):
        return None
    try:
        import asyncio
        import edge_tts
    except Exception:
        return None

    tmp_dir = tempfile.mkdtemp(prefix="paeg_tts_")
    audio_path = os.path.join(tmp_dir, "narration.mp3")
    try:
        async def _synth():
            comm = edge_tts.Communicate(str(narration)[:1000], voice)
            await comm.save(audio_path)

        asyncio.run(_synth())
        if not os.path.isfile(audio_path):
            return None
        # ffmpeg mux
        out = out_path or (manim_video.replace(".mp4", "_tts.mp4"))
        cmd = ["ffmpeg", "-y", "-i", manim_video, "-i", audio_path,
               "-c:v", "copy", "-c:a", "aac", "-shortest", out]
        subprocess.run(cmd, capture_output=True, timeout=120)
        return out if os.path.isfile(out) else None
    except Exception:
        return None

if __name__ == "__main__":
    # 冒烟测试
    script = {"scenes": [{"id": "s1", "concept": "导数", "duration_sec": 15}]}
    r = scope_refine(script, ["visual_goal 缺失"], None, level=1)
    print("scope_refine L1（无LLM保持原样）:", "OK" if isinstance(r, dict) else "FAIL")
    r3 = scope_refine(script, ["err"], None, level=3)
    print("scope_refine L3（无LLM→None触发重生）:", "OK" if r3 is None else "FAIL")
    r2 = tts_mux("/nonexistent/video.mp4", "测试旁白")
    print("tts_mux（无视频→None）:", "OK" if r2 is None else "FAIL")
