# -*- coding: utf-8 -*-
"""test_formula_ocr.py — C6 手写公式识别测试（接口预留 + 降级）。

覆盖：公式 OCR 服务——pix2tex 依赖缺失时降级（不崩溃）、接口可用性检测。
场景：①is_formula_ocr_available 检测 ②依赖缺失降级返回 None ③非法输入容错。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.formula_ocr import FormulaOCR, is_formula_ocr_available


def test_availability_bool():
    """可用性检测返回 bool（pix2tex/torch 是否安装）。"""
    assert isinstance(is_formula_ocr_available(), bool)


def test_dependency_missing_fallback():
    """pix2tex 未安装（torch 重依赖默认不装）→ 提取返回 None（不抛异常）。"""
    s = FormulaOCR()
    assert s.extract_latex(b"fake_formula_image") is None


def test_invalid_input_graceful():
    """None/空字节 → None（容错）。"""
    s = FormulaOCR()
    assert s.extract_latex(None) is None
    assert s.extract_latex(b"") is None


def test_no_fallback_to_text():
    """接口语义：图片公式 → LaTeX；无法识别返回 None（供调用方降级到 verify_math 文本）。"""
    s = FormulaOCR()
    result = s.extract_latex(b"")
    # 空输入返回 None，调用方走文本验证路径
    assert result is None
