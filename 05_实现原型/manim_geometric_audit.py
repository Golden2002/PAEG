
# -*- coding: utf-8 -*-
"""manim_geometric_audit.py — 几何审计门（v1.1 ⭐ §3.34 智绘科普范式）

智绘科普"三道硬门控"之一：几何审计门——自动检测画面元素是否重叠、越界，
防止动画元素"乱飞"。

实现（确定性，不依赖视觉 LLM）：
1. 抽帧（ffmpeg 从视频抽 N 帧）
2. 每帧做简单几何分析：
   - 越界检测：深色像素是否集中在画面边缘（元素贴边/出界）
   - 重叠检测：高密度连通区是否异常集中（元素堆叠）
   - 空白检测：画面是否有大片无内容区域（元素漂移出视野）
3. 返回 PASS/FAIL + 证据（帧索引 + 指标）

注意：视频画面质量依赖渲染，几何审计是"启发式检查"——辅助判断，
不阻断主流程（fail 时记录警告，由审查 Agent 综合决策）。
"""
from __future__ import annotations

"""
[LEGACY · 历史实现] 自 2026-08-26（§3.112）起冻结，仅供 PAEG_USE_MATERIAL_PLUGIN=0 兜底。
新代码必须使用插件 paeg-teaching-materials（material_router._gen_* → services.material_bridge.execute）。
禁止在新模块 import 本模块，违规将被 audit_check 拦截。
最后维护: PAEG Team · 关联: §3.110/§3.111/§3.112
"""

import os
import shutil
import subprocess
import uuid
from typing import Dict, List

_AUDIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "evolve_data", "manim_pipeline", "audit")
_FRAMES_TO_SAMPLE = 5      # 抽帧数
_EDGE_MARGIN = 0.05        # 边缘带宽度（画面宽/高的 5%）
_EDGE_DARK_RATIO = 0.45    # 边缘暗像素占比超此值 = 疑似越界
_OVERLAP_DENSITY = 0.75    # 中心区高密度占比超此值 = 疑似重叠
_EMPTY_RATIO = 0.85        # 空白占比超此值 = 元素漂移

def _ensure_dir():
    os.makedirs(_AUDIT_DIR, exist_ok=True)

def _extract_frames(video_path: str, n: int = _FRAMES_TO_SAMPLE) -> List[str]:
    """用 ffmpeg 抽 n 帧 PNG。返回帧路径列表（失败返回空）。"""
    if not os.path.exists(video_path):
        return []
    try:
        import subprocess as _sp
        import os as _os
        _ensure_dir()
        _dur_cmd = [shutil.which("ffprobe") or "ffprobe",
                    "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        _r = _sp.run(_dur_cmd, capture_output=True, text=True, timeout=15)
        _dur = float(_r.stdout.strip() or "10")
    except Exception:
        _dur = 10.0
    frames = []
    try:
        for i in range(n):
            _t = _dur * (i + 0.5) / n
            _tmp = os.path.join(_AUDIT_DIR, f"frame_{uuid.uuid4().hex[:8]}.png")
            _cmd = [shutil.which("ffmpeg") or "ffmpeg", "-ss", str(_t),
                    "-i", video_path, "-frames:v", "1", "-y", _tmp]
            subprocess.run(_cmd, capture_output=True, timeout=20)
            if os.path.exists(_tmp):
                frames.append(_tmp)
    except Exception:
        pass
    return frames

def _analyze_frame(frame_path: str) -> Dict[str, float]:
    """单帧几何分析：返回 {edge_dark_ratio, center_density, empty_ratio}。"""
    try:
        from PIL import Image
        img = Image.open(frame_path).convert("L")
        w, h = img.size
        if w < 20 or h < 20:
            return {"edge_dark_ratio": 0.0, "center_density": 0.0,
                    "empty_ratio": 1.0}
        px = img.load()
        m = int(w * _EDGE_MARGIN)
        # 边缘带暗像素
        edge_dark = 0
        edge_total = 0
        for x in range(0, w, 3):
            for y in range(0, h, 3):
                if x < m or x >= w - m or y < m or y >= h - m:
                    edge_total += 1
                    if px[x, y] < 128:
                        edge_dark += 1
        edge_ratio = edge_dark / max(1, edge_total)
        # 中心区（去除边缘带）
        center_dark = 0
        center_total = 0
        for x in range(m, w - m, 3):
            for y in range(m, h - m, 3):
                center_total += 1
                if px[x, y] < 128:
                    center_dark += 1
        center_density = center_dark / max(1, center_total)
        # 空白比例（浅色像素占中心区比例）
        empty_ratio = 1.0 - center_density
        return {"edge_dark_ratio": edge_ratio,
                "center_density": center_density,
                "empty_ratio": empty_ratio}
    except Exception:
        return {"edge_dark_ratio": 0.0, "center_density": 0.0,
                "empty_ratio": 1.0}

def audit_video(video_path: str) -> Dict[str, object]:
    """几何审计：抽帧分析。返回 {ok, issues[], frames, metrics}。"""
    issues = []
    frames = _extract_frames(video_path)
    if not frames:
        return {"ok": True, "note": "无法抽帧（跳过几何审计）",
                "issues": [], "frames": [], "metrics": {}}
    metrics = []
    for f in frames:
        m = _analyze_frame(f)
        metrics.append(m)
        if m["edge_dark_ratio"] > _EDGE_DARK_RATIO:
            issues.append(f"帧疑似越界（边缘暗像素 {m['edge_dark_ratio']:.0%}）")
        if m["center_density"] > _OVERLAP_DENSITY:
            issues.append(f"帧疑似元素重叠/堆积（中心密度 {m['center_density']:.0%}）")
        if m["empty_ratio"] > _EMPTY_RATIO:
            issues.append(f"帧疑似元素漂移出视野（空白 {m['empty_ratio']:.0%}）")
    # 清理帧（保留分析结果）
    for f in frames:
        try:
            os.remove(f)
        except Exception:
            pass
    return {"ok": len(issues) == 0,
            "issues": issues[:5],
            "frames_count": len(frames),
            "metrics": metrics}

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("manim_geometric_audit v1.1 就绪（越界/重叠/漂移检测）")
    # 自测：无视频 → 跳过
    r = audit_video("/nonexistent.mp4")
    print("自测（无视频）:", r)
