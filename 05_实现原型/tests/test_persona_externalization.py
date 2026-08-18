# -*- coding: utf-8 -*-
"""test_persona_externalization.py — #3 Persona 外置测试（Harness 30 项 P0，§3.46.2）

覆盖：WEIL_CORE 从 paeg_personas/weil.yml 加载 / 内容完整 / 缺失兜底 / 符号兼容。
dsh Harness 借鉴（packages/preset/persona shadowing，commit 47f9438）：
persona 外置为可编辑可替换的 yml 文件，prompts 模块加载时注入。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
PERSONAS_DIR = BASE / "paeg_personas"


def test_weil_yml_exists():
    """paeg_personas/weil.yml 存在（persona 已外置为可编辑文件）。"""
    assert (PERSONAS_DIR / "weil.yml").is_file(), "weil.yml 缺失"


def test_weil_yml_has_body_block():
    """weil.yml 含 body: | 块（persona 正文承载格式）。"""
    txt = (PERSONAS_DIR / "weil.yml").read_text(encoding="utf-8")
    assert "body: |" in txt
    assert "id: weil" in txt


def test_weil_core_loads_from_yml():
    """WEIL_CORE 从 yml 加载且内容完整（2443 字符 + 核心标记）。"""
    from prompts import WEIL_CORE
    assert len(WEIL_CORE) > 2000, f"WEIL_CORE 过短: {len(WEIL_CORE)}"
    assert "Émile Novis" in WEIL_CORE
    assert "薇依" in WEIL_CORE
    assert "教育哲学" in WEIL_CORE


def test_load_persona_matches_weil_core():
    """_load_persona('weil') 与 WEIL_CORE 一致（同一数据源）。"""
    from prompts import WEIL_CORE, _load_persona
    assert _load_persona("weil") == WEIL_CORE


def test_load_persona_missing_returns_empty():
    """缺失 persona 回退空串（不抛异常）。"""
    from prompts import _load_persona
    assert _load_persona("nonexistent_persona") == ""


def test_weil_core_symbol_importable():
    """既有 from prompts import WEIL_CORE 调用兼容（符号保留）。"""
    from prompts import WEIL_CORE  # noqa: F401
    assert True


def test_weil_yml_body_preserves_newlines():
    """yml 加载后保留换行结构（persona 正文多行格式不破坏）。"""
    from prompts import WEIL_CORE
    assert "\n" in WEIL_CORE
    assert "### " in WEIL_CORE  # 保留 Markdown 小节结构
