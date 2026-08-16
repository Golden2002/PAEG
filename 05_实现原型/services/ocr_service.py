# -*- coding: utf-8 -*-
"""services/ocr_service.py —— C4 OCR 工具（P1，§3.54）

借鉴来源：
source:  RapidOCR（rapidocr-onnxruntime，PaddleOCR 的 ONNX 精简版）
repo:    https://github.com/RapidAI/RapidOCR
adapted: 服务封装——懒加载引擎 + 依赖缺失降级（返回空，不抛异常）
since:   PAEG v0.73 §3.54 C4

设计：
- is_ocr_available()：OCR 依赖是否可用（rapidocr-onnxruntime 已安装）
- OCRService.extract_text(image_bytes)：图片字节 → 识别文本
- 依赖缺失/加载失败 → 返回 ""（ratchet：能力降级，不崩溃）
- 对接场景：学生拍照上传作业/笔记（当前图片被拒，OCR 后进入知识库检索）
"""
from __future__ import annotations

from typing import Optional


def is_ocr_available() -> bool:
    """OCR 依赖是否可用。"""
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


class OCRService:
    """OCR 文字识别服务（懒加载 + 降级）。"""

    def __init__(self):
        self._engine: Optional[object] = None
        if is_ocr_available():
            self._init_engine()

    def _init_engine(self) -> bool:
        """初始化 RapidOCR 引擎（失败保持 None）。"""
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
            return True
        except Exception:
            self._engine = None
            return False

    def extract_text(self, image_bytes: Optional[bytes]) -> str:
        """从图片字节提取文字。

        Args:
            image_bytes: 图片二进制内容（PNG/JPG 等）

        返回：识别文本（失败/无依赖 → 空字符串）
        """
        if not image_bytes or self._engine is None:
            return ""
        try:
            import numpy as np
            from PIL import Image
            import io as _io

            img = Image.open(_io.BytesIO(image_bytes))
            arr = np.asarray(img)
            result, _elapse = self._engine(arr)
            if not result:
                return ""
            # result: [[box, text, score], ...]
            lines = [str(item[1]) for item in result if len(item) >= 2 and item[1]]
            return "\n".join(lines)
        except Exception:
            return ""


__all__ = ["OCRService", "is_ocr_available"]
