# -*- coding: utf-8 -*-
"""v0.45 ⭐ 授课视频生成服务（PPT 大纲 → 教学视频）。

用户需求：PPT 生成"真正内容的授课视频"——不是静态 PPT，而是
【每页画面 + 中文语音讲解 + 可播放的 mp4】。

技术链路：
  1. 输入：LLM 生成的 ppt_outline（"## 章节标题" + "- 要点" 结构）
  2. 每页 → PIL 绘制教学视频帧（品牌色标题条 + 要点排版，16:9 1280x720）
  3. 每页要点 → edge-tts 生成讲解音频（zh-CN-XiaoxiaoNeural）
  4. ffmpeg 合成：帧序列 + 音频 → 视频（每页停留 3s 基础 + 按音频时长自适应）

依赖：PIL（pillow）、edge-tts、imageio-ffmpeg（便携 ffmpeg）、python-pptx 无关。
输出：downloads/video/<learner_id>/<hash>.mp4（可经 /api/download 访问）。
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import time
import urllib.parse  # v0.66 ⭐ 视频 URL 含 learner_id 需 quote
from pathlib import Path
from typing import List, Optional

import logging
logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).parent
_VIDEO_DIR = _BASE_DIR / "downloads" / "video"

# ── 依赖懒加载（缺失时优雅降级）──────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import edge_tts
    _EDGE_OK = True
except ImportError:
    _EDGE_OK = False

_FFMPEG = None  # 懒加载 imageio-ffmpeg 的便携 ffmpeg


def _get_ffmpeg() -> Optional[str]:
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    try:
        import imageio_ffmpeg
        _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
        return _FFMPEG
    except Exception:
        return None


def _font(size: int):
    """中文字体（微软雅黑优先，降级 simhei/simsun）。"""
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc"):
        try:
            p = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", name)
            if os.path.isfile(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ── 帧绘制 ──────────────────────────────────────
def _wrap_text(text: str, draw, font, max_width: int) -> List[str]:
    """按像素宽度换行（中文按字符）。"""
    lines = []
    cur = ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def _render_frame(title: str, points: List[str], page_no: int, total: int,
                  width: int = 1280, height: int = 720) -> Image.Image:
    """绘制单页教学视频帧：品牌色标题条 + 要点列表 + 页脚。"""
    img = Image.new("RGB", (width, height), (250, 250, 250))
    d = ImageDraw.Draw(img)
    # 品牌色标题条（深蓝 #1a3a6b）
    bar_h = 110
    d.rectangle([0, 0, width, bar_h], fill=(26, 58, 107))
    d.rectangle([0, bar_h, width, bar_h + 6], fill=(230, 165, 40))  # 金色饰线
    # 标题（自动换行，最多两行）
    f_title = _font(44)
    t_lines = _wrap_text(title, d, f_title, width - 160)
    ty = 28
    for ln in t_lines[:2]:
        d.text((80, ty), ln, font=f_title, fill=(255, 255, 255))
        ty += 54
    # 要点区
    f_point = _font(30)
    f_sub = _font(24)
    y = bar_h + 50
    for pt in points[:6]:
        # 要点符号
        d.ellipse([90, y + 12, 106, y + 28], fill=(26, 58, 107))
        # 要点文本（换行，最多 3 行/条）
        for ln in _wrap_text(pt, d, f_point, width - 180)[:3]:
            d.text((130, y), ln, font=f_point, fill=(40, 40, 40))
            y += 44
        y += 14
    # 页脚（页码 + 课程标记）
    f_foot = _font(20)
    d.text((80, height - 45), f"PAEG 课堂 · 第 {page_no} 页 / 共 {total} 页",
           font=f_foot, fill=(120, 120, 120))
    return img


# ── 大纲解析（与 pptx_mcp_server._parse_outline 对齐）──────────
def _parse_outline(outline: str) -> List[dict]:
    """解析 ppt_outline 文本 → [{title, points}]。"""
    slides = []
    lines = [l.strip() for l in (outline or "").splitlines() if l.strip()]
    cur = None
    for ln in lines:
        m = re.match(r"^(#{1,4})\s+(.+)$", ln)
        if m:
            if cur:
                slides.append(cur)
            cur = {"title": m.group(2).strip(), "points": []}
            continue
        m = re.match(r"^[-*•]\s*(.+)$", ln)
        if m:
            if cur:
                cur["points"].append(m.group(1).strip())
            else:
                cur = {"title": "要点", "points": [m.group(1).strip()]}
            continue
        if cur:
            cur["points"].append(ln)
    if cur:
        slides.append(cur)
    if not slides:
        slides = [{"title": "授课内容", "points": ["（大纲为空，请补充内容）"]}]
    return slides


async def _tts_to_file(text: str, path: str) -> bool:
    """edge-tts 生成讲解音频（失败返回 False）。"""
    try:
        tts = edge_tts.Communicate(text[:1500], voice="zh-CN-XiaoxiaoNeural",
                                   rate="-5%")  # 略慢速，适合教学
        await tts.save(path)
        return os.path.isfile(path) and os.path.getsize(path) > 1000
    except Exception as e:
        logger.warning("TTS 生成失败: %s", e)
        return False


# ── 主入口 ──────────────────────────────────────
def _generate_teaching_script(topic: str, outline: str, llm=None) -> list:
    """v0.53 ⭐ Step 0：LLM 生成结构化教学演讲稿（Oracle pipeline 设计）。

    输入 topic + outline（原始教学意图），输出每页完整 narration（讲解词）。
    每页 narration 是视频的内容支撑——标题/画面/配音/字幕都从它派生。

    返回 [{title, points, narration}]；LLM 失败则用 outline 的标题+要点拼接兜底。
    """
    import json as _json
    _slides = _parse_outline(outline)
    if not _slides:
        return []
    if llm is not None:
        try:
            from subagents import _safe_chat
            _src = "\n".join(
                f"## {s.get('title', '')}\n" + "\n".join(f"- {p}" for p in (s.get('points') or [])[:3])
                for s in _slides[:6])
            _sys = (
                "你是资深教学视频撰稿人。为下面的教学主题/大纲撰写**结构化演讲稿**。\n"
                "要求：\n"
                "1. 每页输出完整讲解词（narration），口语化、适合朗读，逻辑递进\n"
                "2. 讲解顺序：问题引入 → 概念 → 例子 → 练习/总结\n"
                "3. 页与页之间有过渡语（'上一页我们知道了…接下来…'）\n"
                "4. 公式解释变量含义，不照搬标题/要点\n"
                "5. **每页输出 2-4 个画面要点（key_points）**——供视频画面展示的短语/短句\n"
                "6. 输出 JSON 数组：[{\"title\": \"页标题\", \"key_points\": [\"要点1\",\"要点2\"], \"narration\": \"完整讲解词\"}]\n"
                "7. 只输出 JSON，不要多余文字"
            )
            _u = f"主题：{topic}\n大纲：\n{_src}"
            _r = _safe_chat(llm, _sys, _u, max_tokens=1800)
            if _r:
                _clean = _r.strip()
                if _clean.startswith("```"):
                    _clean = _clean.split("```")[1]
                    if _clean.startswith("json"):
                        _clean = _clean[4:]
                _parsed = _json.loads(_clean.strip())
                if isinstance(_parsed, list) and _parsed:
                    _out = []
                    for _p in _parsed:
                        if isinstance(_p, dict) and _p.get("narration"):
                            # v0.53 ⭐ 修复：画面要点优先用 LLM key_points（否则帧空白）
                            _kp = _p.get("key_points") or _p.get("points") or []
                            if not _kp and len(_out) < len(_slides):
                                _kp = _slides[len(_out)].get("points") or []
                            _out.append({
                                "title": str(_p.get("title") or "未命名页"),
                                "points": [str(k)[:60] for k in _kp[:6]],
                                "narration": str(_p["narration"]),
                            })
                    if _out:
                        return _out
        except Exception as _se:
            print(f"[PAEG][video_service] 演讲稿生成失败，用大纲兜底: {_se}")
    # 兜底：标题 + 要点拼接（原有行为）
    for _s in _slides:
        _t = _s.get("title") or "未命名页"
        _pts = _s.get("points") or []
        _s["narration"] = f"{_t}。{'，'.join(_pts[:4])}" if _pts else f"{_t}。"
    return _slides


def generate_teaching_video(topic: str, outline: str,
                            learner_id: str = "anon") -> dict:
    """PPT 大纲 → 授课视频 mp4。

    返回 {"ok": bool, "path": str, "url": str, "slides": int, "duration": float, "error": str}
    """
    if not _PIL_OK or not _EDGE_OK:
        return {"ok": False, "path": "", "url": "", "slides": 0, "duration": 0,
                "error": "依赖缺失：需 pillow + edge-tts"}
    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        return {"ok": False, "path": "", "url": "", "slides": 0, "duration": 0,
                "error": "ffmpeg 不可用（安装 imageio-ffmpeg）"}

    slides = _parse_outline(outline)
    if not slides:
        return {"ok": False, "path": "", "url": "", "slides": 0, "duration": 0,
                "error": "大纲为空"}

    # v0.53 ⭐ Step 0：LLM 生成结构化演讲稿（每页 narration 驱动内容/时长/字幕）
    try:
        from infra.runtime import get_llm
        _vllm = get_llm()
    except Exception:
        _vllm = None
    slides = _generate_teaching_script(topic, outline, llm=_vllm)

    import asyncio
    _VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    _h = hashlib.sha1((topic + str(time.time())).encode("utf-8")).hexdigest()[:10]
    _out_dir = _VIDEO_DIR / str(learner_id)
    _out_dir.mkdir(parents=True, exist_ok=True)
    _out_mp4 = _out_dir / f"{_h}.mp4"

    tmp = Path(tempfile.mkdtemp(prefix="paeg_video_"))
    try:
        # 1. 每页：绘制帧 + 生成音频（narration 驱动）+ 测音频时长
        frame_files, audio_files, durations = [], [], []
        for i, sl in enumerate(slides):
            title = sl.get("title") or "未命名页"
            points = sl.get("points") or []
            frame = _render_frame(title, points, i + 1, len(slides))
            fp = tmp / f"frame_{i:03d}.png"
            frame.save(fp)
            frame_files.append(str(fp))

            # v0.53 ⭐ 讲解文本 = 演讲稿 narration（非标题+要点拼接）
            narration = (sl.get("narration") or "").strip() or \
                f"{title}。{'，'.join(points[:4])}" if points else f"{title}。"
            ap = tmp / f"audio_{i:03d}.mp3"
            ok = asyncio.run(_tts_to_file(narration, str(ap)))
            if ok:
                audio_files.append(str(ap))
                # 用 ffprobe 测时长
                try:
                    r = subprocess.run([ffmpeg, "-i", str(ap)], capture_output=True,
                                       text=True, errors="replace")
                    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
                    if m:
                        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                        durations.append(max(3.0, dur + 1.0))  # 至少 3s
                    else:
                        durations.append(4.0)
                except Exception:
                    durations.append(4.0)
            else:
                audio_files.append("")
                durations.append(4.0)

        # 2. 用 ffmpeg concat 合成：每页 [帧图片 + 音频] → 视频段 → 拼接
        segs = []
        for i in range(len(slides)):
            seg = tmp / f"seg_{i:03d}.mp4"
            dur = durations[i] if i < len(durations) else 4.0
            a_src = audio_files[i] if i < len(audio_files) and audio_files[i] else ""
            cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(frame_files[i]),
                   "-t", f"{dur:.2f}"]
            if a_src:
                cmd += ["-i", a_src, "-c:v", "libx264", "-tune", "stillimage",
                        "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
                        "-shortest"]
            else:
                cmd += ["-c:v", "libx264", "-tune", "stillimage",
                        "-pix_fmt", "yuv420p", "-an"]
            cmd.append(str(seg))
            r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
            if not os.path.isfile(seg) or os.path.getsize(seg) == 0:
                logger.warning("段 %d 生成失败: %s", i, r.stderr[-300:])
                continue
            segs.append(str(seg))

        if not segs:
            return {"ok": False, "path": "", "url": "", "slides": 0, "duration": 0,
                    "error": "视频段生成失败（ffmpeg 合成错误）"}

        # 3. concat 列表拼接
        concat_list = tmp / "concat.txt"
        with open(concat_list, "w", encoding="utf-8") as fh:
            for s in segs:
                fh.write(f"file '{s}'\n")
        r = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(_out_mp4)],
            capture_output=True, text=True, errors="replace")
        if not os.path.isfile(_out_mp4) or os.path.getsize(_out_mp4) == 0:
            return {"ok": False, "path": "", "url": "", "slides": 0, "duration": 0,
                    "error": "视频拼接失败: " + r.stderr[-300:]}

        total_dur = sum(durations)
        return {
            "ok": True,
            "path": str(_out_mp4),
            # v0.66 ⭐ 修复：URL 缺 learner_id 目录（文件在 video/<uid>/<hash>.mp4，
            # 此前只返回 video/<hash>.mp4 → 下载 404）。用 quote 处理 uid 特殊字符。
            "url": f"/api/download/video/{urllib.parse.quote(str(learner_id))}/{_h}.mp4",
            "slides": len(slides),
            "duration": round(total_dur, 1),
            "error": "",
        }
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════
# v1.0 ⭐ 融合视频：PPT 帧 + TTS + Manim 片段 + 资源叠图
# （用户需求：视频要能把 manim 演示动画和 Library 资源剪辑进来，
#   而不是简单的"PPT 讲解视频"。新增 compose_with_slots，旧函数保留。）
# ══════════════════════════════════════════════════════════════════════


def _probe_duration(ffmpeg: str, path: str) -> float:
    """用 ffprobe 测媒体时长（秒）。失败返回 4.0。"""
    try:
        r = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True,
                           text=True, errors="replace")
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 4.0


def _normalize_video(ffmpeg: str, src: str, dst: Path, target_dur: float) -> None:
    """把 manim 段统一转码为 1280x720 30fps yuv420p（concat 同规格硬约束）。"""
    subprocess.run(
        [ffmpeg, "-y", "-i", str(src),
         "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,"
                "fps=30,format=yuv420p",
         "-t", f"{target_dur:.2f}",
         "-c:v", "libx264", "-preset", "fast",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart",
         str(dst)],
        capture_output=True, text=True, errors="replace")


def _render_frame_with_overlay(seg, out_png: str) -> None:
    """绘制 PPT 帧（标题+要点），叠加 bg_image 作背景、inline_asset 角落。

    seg 为 dict（build_timeline 产物）或含同名属性的对象。
    """
    if not _PIL_OK:
        return
    seg_bg = seg["bg_image"] if isinstance(seg, dict) else getattr(seg, "bg_image", None)
    seg_inline = seg["inline_asset"] if isinstance(seg, dict) else getattr(seg, "inline_asset", None)
    seg_title = seg["title"] if isinstance(seg, dict) else getattr(seg, "title", "")
    seg_points = seg["points"] if isinstance(seg, dict) else getattr(seg, "points", [])
    base = Image.new("RGB", (1280, 720), (250, 250, 250))
    if seg_bg and os.path.isfile(seg_bg):
        try:
            bg = Image.open(seg_bg).convert("RGB").resize((1280, 720))
            from PIL import ImageEnhance
            base = ImageEnhance.Brightness(bg).enhance(0.7)
        except Exception:
            pass
    d = ImageDraw.Draw(base)
    # 标题条
    try:
        font_big = ImageFont.truetype("msyhbd.ttc", 42)
        font_pt = ImageFont.truetype("msyh.ttc", 30)
    except Exception:
        font_big = ImageFont.load_default()
        font_pt = font_big
    d.rectangle([0, 0, 1280, 96], fill=(59, 91, 219))
    d.text((48, 24), str(seg_title or "未命名"), font=font_big, fill=(255, 255, 255))
    y = 140
    for pt in (seg_points or [])[:6]:
        d.text((56, y), "· " + str(pt)[:50], font=font_pt, fill=(40, 40, 40))
        y += 46
    # 角落叠图
    if seg_inline and os.path.isfile(seg_inline):
        try:
            ic = Image.open(seg_inline).convert("RGBA")
            ic.thumbnail((280, 200))
            base.paste(ic, (970, 480), ic if ic.mode == "RGBA" else None)
        except Exception:
            pass
    base.save(out_png)


def _encode_frame_segment(ffmpeg: str, seg, out: Path) -> None:
    """静态帧段：循环帧 + 音频 → 段 mp4。seg 为 dict 或含同名属性对象。"""
    seg_dur = seg["duration"] if isinstance(seg, dict) else getattr(seg, "duration", 4.0)
    seg_frame = seg["frame_path"] if isinstance(seg, dict) else getattr(seg, "frame_path", None)
    seg_audio = seg["audio_path"] if isinstance(seg, dict) else getattr(seg, "audio_path", None)
    cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(seg_frame),
           "-t", f"{seg_dur:.2f}"]
    if seg_audio and os.path.isfile(seg_audio):
        cmd += ["-i", str(seg_audio), "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
                "-r", "30", "-shortest"]
    else:
        cmd += ["-c:v", "libx264", "-tune", "stillimage",
                "-pix_fmt", "yuv420p", "-r", "30", "-an"]
    cmd.append(str(out))
    subprocess.run(cmd, capture_output=True, text=True, errors="replace")


def build_timeline(pages: list, manim_results: dict, asset_results: dict,
                   script=None) -> list:
    """把 pages（含 slots）转为时间轴片段序列。

    - manim 占位 → 独立 TimelineSegment(kind="manim")；manim 渲染失败 → 降级静态帧
    - asset 占位 → 合并进所属页的 bg_image / inline_asset
    - v0.66 ⭐ script 参数：讲稿驱动——按顺序为每段注入真 narration
      （PPT 页讲稿 + manim 段讲稿），替代"标题+要点拼接"兜底
    """
    # 讲稿索引：script.sections 按顺序匹配
    _script_secs = list(script.sections) if script is not None else []
    _si = 0

    def _next_narration(fallback: str) -> str:
        nonlocal _si
        if _si < len(_script_secs):
            _n = _script_secs[_si].narration
            _si += 1
            return _n if _n and _n.strip() else fallback
        return fallback

    segs = []
    for i, p in enumerate(pages):
        bg = asset_results.get(f"{i}:bg")
        inline = asset_results.get(f"{i}:inline")
        fallback_narration = (p.get("narration") or "").strip() or \
            (f"{p.get('title', '')}。{'，'.join((p.get('points') or [])[:4])}"
             if p.get("points") else f"{p.get('title', '')}。")
        narration = _next_narration(fallback_narration)
        segs.append({
            "kind": "ppt_frame",
            "title": p.get("title") or "未命名",
            "points": p.get("points") or [],
            "bg_image": bg,
            "inline_asset": inline,
            "narration": narration,
            "frame_path": None,
            "audio_path": None,
            "duration": 0.0,
            "video_path": None,
        })
        for slot in p.get("slots") or []:
            if slot.get("kind") == "manim":
                vp = manim_results.get(slot.get("topic"))
                # v0.66 ⭐ manim 段讲稿（跟随讲解）：优先取 script narration
                _manim_narration = _next_narration("") if vp else ""
                segs.append({
                    "kind": "manim" if vp else "ppt_frame",
                    "title": f"动画演示：{slot.get('topic', '')}",
                    "points": [slot.get("description") or "（动态演示）"],
                    "bg_image": None, "inline_asset": None,
                    "narration": _manim_narration, "frame_path": None,
                    "audio_path": None,
                    "duration": 0.0, "video_path": vp,
                })
    return segs


def compose_with_slots(topic: str, ir: dict, manim_segments: dict,
                       asset_segments: dict, learner_id: str = "anon",
                       script=None) -> dict:
    """v1.0 ⭐ 融合视频：PPT 帧 + TTS + Manim 片段 + 资源叠图。

    输入 ir = {"pages": [...], "topic": str}（outline_ir.parse_outline_with_slots 输出）。
    manim_segments = {slot_topic: mp4_path}（预渲染结果，缺失 → 降级静态帧）。
    asset_segments = {"<i>:bg"/"<i>:inline": path}（可选）。
    script（可选）：讲稿驱动——每段（PPT 页 + manim 段）用真 narration 配音。
    返回 {ok, path, url, slides, duration, manim_count, error}。
    """
    if not _PIL_OK or not _EDGE_OK:
        return {"ok": False, "error": "依赖缺失：pillow + edge-tts"}
    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        return {"ok": False, "error": "ffmpeg 不可用"}

    timeline = build_timeline(ir.get("pages") or [], manim_segments,
                              asset_segments, script=script)
    if not timeline:
        return {"ok": False, "error": "时间轴为空"}

    _VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    _h = hashlib.sha1((topic + str(time.time())).encode("utf-8")).hexdigest()[:10]
    _out_dir = _VIDEO_DIR / str(learner_id)
    _out_dir.mkdir(parents=True, exist_ok=True)
    _out_mp4 = _out_dir / f"{_h}.mp4"
    tmp = Path(tempfile.mkdtemp(prefix="paeg_fuse_"))
    try:
        import asyncio
        segment_paths = []
        for idx, seg in enumerate(timeline):
            if seg["kind"] == "manim" and seg.get("video_path"):
                # ── manim 段：归一化 + 配音（v0.66 跟随讲解）──
                seg["duration"] = _probe_duration(ffmpeg, seg["video_path"])
                # manim 段讲稿 TTS（若 script 提供了 narration）
                if seg.get("narration"):
                    _map = tmp / f"audio_{idx:03d}.mp3"
                    if asyncio.run(_tts_to_file(seg["narration"], str(_map))):
                        seg["audio_path"] = str(_map)
                out = tmp / f"seg_{idx:03d}_manim.mp4"
                _normalize_video(ffmpeg, seg["video_path"], out, seg["duration"])
                if os.path.isfile(out) and os.path.getsize(out) > 0:
                    # 配音与动画合成（-shortest 对齐：配音短则动画截断，配音长则保留）
                    if seg.get("audio_path") and os.path.isfile(seg["audio_path"]):
                        _out_av = tmp / f"seg_{idx:03d}_manim_av.mp4"
                        subprocess.run(
                            [ffmpeg, "-y", "-i", str(out), "-i", str(seg["audio_path"]),
                             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                             "-shortest", str(_out_av)],
                            capture_output=True, text=True, errors="replace")
                        if os.path.isfile(_out_av) and os.path.getsize(_out_av) > 0:
                            out = _out_av
                    segment_paths.append(str(out))
                    continue
            # ── ppt_frame 段（含 manim 失败降级）──
            fp = tmp / f"frame_{idx:03d}.png"
            _render_frame_with_overlay(seg, str(fp))
            seg["frame_path"] = str(fp)
            ap = tmp / f"audio_{idx:03d}.mp3"
            ok = asyncio.run(_tts_to_file(seg["narration"], str(ap))) \
                if seg["narration"] else False
            if ok:
                seg["audio_path"] = str(ap)
                seg["duration"] = max(3.0, _probe_duration(ffmpeg, ap) + 1.0)
            else:
                seg["duration"] = 4.0
            out = tmp / f"seg_{idx:03d}_frame.mp4"
            _encode_frame_segment(ffmpeg, seg, out)
            if os.path.isfile(out) and os.path.getsize(out) > 0:
                segment_paths.append(str(out))

        if not segment_paths:
            return {"ok": False, "error": "视频段生成失败"}

        # ── concat 合成（同规格 copy；失败回退转码）──
        concat_list = tmp / "concat.txt"
        with open(concat_list, "w", encoding="utf-8") as fh:
            for s in segment_paths:
                fh.write(f"file '{s.replace(chr(92), '/')}'\n")
        r = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(_out_mp4)],
            capture_output=True, text=True, errors="replace")
        if not os.path.isfile(_out_mp4) or os.path.getsize(_out_mp4) == 0:
            r = subprocess.run(
                [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                 "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
                 str(_out_mp4)],
                capture_output=True, text=True, errors="replace")
            if not os.path.isfile(_out_mp4) or os.path.getsize(_out_mp4) == 0:
                return {"ok": False, "error": "视频拼接失败: " + r.stderr[-300:]}

        manim_count = sum(1 for t in timeline if t["kind"] == "manim")
        return {
            "ok": True,
            "path": str(_out_mp4),
            # v0.66 ⭐ 修复：URL 加 learner_id 目录（否则下载 404）
            "url": f"/api/download/video/{urllib.parse.quote(str(learner_id))}/{_h}.mp4",
            "slides": len([t for t in timeline if t["kind"] != "manim"]),
            "duration": round(sum(t["duration"] for t in timeline), 1),
            "manim_count": manim_count,
            "error": "",
        }
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    demo_outline = (
        "# 超导体的量子隧穿效应\n"
        "## 什么是超导\n- 超导：零电阻 + 完全抗磁性\n- 1911 年昂内斯发现汞的超导现象\n"
        "## 量子隧穿原理\n- 电子穿过势垒的量子行为\n- 约瑟夫森结的核心机制\n"
        "## 应用场景\n- 超导量子比特\n- SQUID 磁强计\n"
    )
    r = generate_teaching_video("超导体的量子隧穿效应", demo_outline, "demo")
    print(r)
