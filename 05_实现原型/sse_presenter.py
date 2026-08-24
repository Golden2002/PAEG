# -*- coding: utf-8 -*-
"""sse_presenter.py —— §3.91 ⭐ 统一 SSE 事件序列化（Oracle 架构重构 Step2）

将 6 个 gen_xxx_early 生成器（每个 yield presentation + done）收敛为 3 个格式化函数。

SSE 契约（字节级保持，前端零回归——09_GUI前端/index.html L2871-2897）：
- event: presentation  → {step_id, content, step_type}
- event: done          → {status, mode, url}
- event: progress      → {percent, message}（新增能力，前端可选监听）
"""
from __future__ import annotations

import json


def fmt_presentation(step_id: int, content: str, step_type: str) -> str:
    """presentation 事件（物料产物内容）。"""
    data = {"step_id": step_id, "content": content, "step_type": step_type}
    return f"event: presentation\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def fmt_done(mode: str, url: str = "") -> str:
    """done 事件（流程结束）。"""
    data = {"status": "completed", "mode": mode, "url": url}
    return f"event: done\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def fmt_progress(percent: float, message: str = "") -> str:
    """progress 事件（长任务进度心跳，manim 渲染用）。"""
    data = {"percent": round(percent, 1), "message": message}
    return f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def fmt_error(message: str, mode: str = "material") -> str:
    """error 事件（生成失败，前端可显式提示）。"""
    data = {"status": "error", "mode": mode, "message": message}
    return f"event: done\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    print(fmt_presentation(1, "PPT 已生成（8 页）：<a href='/api/download/ppt/x.pptx'>下载 PPT</a>", "ppt"))
    print(fmt_done("ppt", "/api/download/ppt/x.pptx"))
    print(fmt_progress(50, "渲染中..."))
