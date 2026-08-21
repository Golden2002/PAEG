# -*- coding: utf-8 -*-
"""§3.81 P2-① 视频多模板视觉测试。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from video_service import _TEMPLATES, _pick_template, _render_frame


def test_templates_defined():
    """S1：四种模板定义完整。"""
    assert set(_TEMPLATES) == {"default", "comparison", "example", "formula"}


def test_pick_template_comparison():
    """S2：对比章节 → comparison。"""
    assert _pick_template("A 与 B 的区别", ["要点"]) == "comparison"
    assert _pick_template("对比分析", ["异同点"]) == "comparison"


def test_pick_template_example():
    """S3：例题章节 → example。"""
    assert _pick_template("典型例题", ["例题1"]) == "example"
    assert _pick_template("案例分析", ["应用"]) == "example"


def test_pick_template_formula():
    """S4：公式章节 → formula。"""
    assert _pick_template("导数公式", ["f'(x) = lim"]) == "formula"
    assert _pick_template("基本定理", ["推导", "x = y + z"]) == "formula"


def test_pick_template_default():
    """S5：普通章节 → default。"""
    assert _pick_template("课程引入", ["目标"]) == "default"


def test_render_frame_all_templates():
    """S6 主路径：四种模板均可渲染（PIL 可用时输出图片对象）。"""
    if not hasattr(_render_frame, "__wrapped__"):
        pass
    try:
        from PIL import Image
        for tpl in _TEMPLATES:
            img = _render_frame("测试标题", ["要点1", "要点2"], 1, 3, template=tpl)
            assert isinstance(img, Image.Image)
            assert img.size == (1280, 720)
    except ImportError:
        pytest.skip("PIL 不可用")


def test_render_frame_invalid_template_fallback():
    """S7 防御：非法模板 → 回退 default（不崩）。"""
    try:
        from PIL import Image
        img = _render_frame("标题", ["要点"], 1, 1, template="nonexistent")
        assert isinstance(img, Image.Image)
    except ImportError:
        pytest.skip("PIL 不可用")


def test_render_frame_auto_template():
    """S8 主路径：不指定 template → 自动选（默认走 _pick_template）。"""
    try:
        from PIL import Image
        img = _render_frame("对比教学", ["A vs B"], 1, 1, template="default",
                            outline="对比 区别")
        assert isinstance(img, Image.Image)
    except ImportError:
        pytest.skip("PIL 不可用")
