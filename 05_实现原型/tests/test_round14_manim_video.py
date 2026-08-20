# -*- coding: utf-8 -*-
"""§3.79 Round 4 ⭐ manim 数学视频链路修复回归测试。

probe_manim_video 真实抽查暴露：
  1. render_manim 的 subprocess.run(text=True) 未指定 encoding →
     Windows GBK 解码 manim UTF-8 输出 UnicodeDecodeError（运维 bug）
  2. 输出目录匹配漏 -qml/-ql 对应（仅 480p15/720p30/1080p60）

守卫：
  - validate_manim_code：安全代码通过 / 危险 import 拒绝 / 缺 construct 拒绝
  - render_manim：subprocess 调用带 encoding='utf-8'（防 GBK 崩溃）
  - 输出目录覆盖 5 档质量
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

SAFE_CODE = '''from manim import *
class S(Scene):
    def construct(self):
        self.play(Create(Circle()), run_time=1)
'''

EVIL_CODE = '''import os
os.system("rm -rf /")
class S(Scene):
    def construct(self):
        pass
'''


def test_validate_safe_code_passes():
    from manim_service import validate_manim_code
    ok, err = validate_manim_code(SAFE_CODE)
    assert ok, err


def test_validate_blocks_dangerous_import():
    from manim_service import validate_manim_code
    ok, err = validate_manim_code(EVIL_CODE)
    assert not ok
    assert "Blocked import" in err


def test_validate_blocks_no_construct():
    from manim_service import validate_manim_code
    code = "from manim import *\nclass S(Scene):\n    pass\n"
    ok, err = validate_manim_code(code)
    assert not ok
    assert "construct" in err


def test_render_uses_utf8_encoding(monkeypatch):
    """render_manim 的 subprocess 调用必须显式 encoding='utf-8'（Round 4 运维修复）。"""
    import manim_service as ms

    captured = {}

    class FakeResult:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, **kw):
        captured["kw"] = kw
        return FakeResult()

    # 同时 monkeypatch 输出目录存在性：直接伪造成功路径
    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    monkeypatch.setattr(os.path, "exists", lambda p: True)

    path, err = ms.render_manim(SAFE_CODE, quality="-ql", timeout=30)
    kw = captured.get("kw", {})
    assert kw.get("encoding") == "utf-8", f"缺少 utf-8 encoding: {kw}"
    assert kw.get("errors") == "replace", f"缺少 errors=replace: {kw}"


def test_quality_output_dirs_covered():
    """输出目录匹配覆盖 5 档质量（-ql/-qm/-qh/-qp/-qk 对应 480p15…2160p60）。"""
    import manim_service as ms
    import inspect

    src = inspect.getsource(ms.render_manim)
    for q in ("480p15", "720p30", "1080p60", "1440p60", "2160p60"):
        assert q in src, f"输出目录匹配缺 {q}"
