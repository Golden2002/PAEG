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

    import asyncio
    _VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    _h = hashlib.sha1((topic + str(time.time())).encode("utf-8")).hexdigest()[:10]
    _out_dir = _VIDEO_DIR / str(learner_id)
    _out_dir.mkdir(parents=True, exist_ok=True)
    _out_mp4 = _out_dir / f"{_h}.mp4"

    tmp = Path(tempfile.mkdtemp(prefix="paeg_video_"))
    try:
        # 1. 每页：绘制帧 + 生成音频 + 测音频时长
        frame_files, audio_files, durations = [], [], []
        for i, sl in enumerate(slides):
            title = sl.get("title") or "未命名页"
            points = sl.get("points") or []
            frame = _render_frame(title, points, i + 1, len(slides))
            fp = tmp / f"frame_{i:03d}.png"
            frame.save(fp)
            frame_files.append(str(fp))

            # 讲解文本：标题 + 要点（自然拼接成解说词）
            narration = f"{title}。{'，'.join(points[:4])}" if points else f"{title}。"
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
            "url": f"/api/download/video/{_h}.mp4",
            "slides": len(slides),
            "duration": round(total_dur, 1),
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
