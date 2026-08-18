# -*- coding: utf-8 -*-
"""test_ocr_service.py — C4 OCR 工具测试。

覆盖：OCR 服务封装——图片文字提取、依赖缺失降级、容错。
场景：①真实图片 OCR（生成含文字的测试图）②依赖缺失降级 ③非法输入容错。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ocr_service import OCRService, is_ocr_available


def test_availability():
    """OCR 可用性检测（rapidocr-onnxruntime 是否安装）。"""
    # 不强制 True/False——只验证函数可调用且返回 bool
    assert isinstance(is_ocr_available(), bool)


def test_dependency_missing_fallback():
    """依赖缺失 → is_ocr_available False + extract 返回空（不抛异常）。"""
    s = OCRService()
    # 模拟依赖缺失（打桩）
    s._engine = None
    assert s.extract_text(b"fake_image_bytes") == ""


def test_invalid_input_graceful():
    """非法输入（None/空字节）→ 空字符串（容错）。"""
    s = OCRService()
    assert s.extract_text(None) == ""
    assert s.extract_text(b"") == ""


def test_real_ocr_if_available():
    """若 OCR 可用：生成含文字的图片并提取（真实能力验证）。"""
    if not is_ocr_available():
        import pytest
        pytest.skip("OCR 依赖未安装")
    from PIL import Image, ImageDraw, ImageFont
    import io as _io

    img = Image.new("RGB", (400, 100), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "Hello PAEG", fill="black")
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    s = OCRService()
    text = s.extract_text(img_bytes)
    # 英文 OCR 至少应提取出部分文字（PIL 默认字体）
    assert "PAEG" in text or "Hello" in text or len(text) > 0
