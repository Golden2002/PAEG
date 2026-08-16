# -*- coding: utf-8 -*-
"""services/formula_ocr.py —— C6 手写公式识别接口预留（P2，§3.54）

借鉴来源：
source:  pix2tex / LaTeX-OCR（https://github.com/lukas-blecher/LaTeX-OCR）
adapted: 接口预留——pix2tex/torch 为可选重依赖（纪律 33：默认不装防 Docker 镜像膨胀），
         依赖缺失时 extract_latex 返回 None，调用方降级到 verify_math 文本路径
since:   PAEG v0.73 §3.54 C6

设计：
- is_formula_ocr_available()：pix2tex + torch 是否可用
- FormulaOCR.extract_latex(image_bytes)：图片公式 → LaTeX 字符串；不可用/失败 → None
- 对接：与 verify_math 串联（图片→LaTeX→SymPy 验证），形成"拍照做题"闭环
- 安装方式（可选）：pip install pix2tex（自动带 torch，~2GB）——需求文档 §3.54.6 记录
"""
from __future__ import annotations

from typing import Optional


def is_formula_ocr_available() -> bool:
    """pix2tex + torch 是否可用（重依赖，默认未安装）。"""
    try:
        import pix2tex  # noqa: F401
        import torch  # noqa: F401
        return True
    except Exception:
        return False


class FormulaOCR:
    """手写公式识别服务（接口预留 + 降级）。"""

    def __init__(self):
        self._model: Optional[object] = None
        if is_formula_ocr_available():
            self._init_model()

    def _init_model(self) -> bool:
        """初始化 pix2tex 模型（失败保持 None）。"""
        try:
            from pix2tex.cli import LatexOCR
            self._model = LatexOCR()
            return True
        except Exception:
            self._model = None
            return False

    def extract_latex(self, image_bytes: Optional[bytes]) -> Optional[str]:
        """图片公式 → LaTeX 文本。

        Args:
            image_bytes: 公式图片二进制

        返回：LaTeX 字符串；依赖缺失/输入非法/识别失败 → None
        """
        if not image_bytes or self._model is None:
            return None
        try:
            import io as _io
            from PIL import Image

            img = Image.open(_io.BytesIO(image_bytes))
            result = self._model(img)
            return str(result) if result else None
        except Exception:
            return None


__all__ = ["FormulaOCR", "is_formula_ocr_available"]
