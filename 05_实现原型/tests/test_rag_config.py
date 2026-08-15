# -*- coding: utf-8 -*-
"""test_rag_config.py —— config/rag.json 懒加载读取器测试 (B1 RAG 配置化)。

需求：
1. config/rag.json 缺键 → 回退内置默认值
2. lib/ingest/chunker.py 的 chunk_text 默认值从 get_rag_config() 读
3. config/rag.json 缺失 → get_rag_config() 返回全默认，不抛异常

设计要点：
- 用 monkeypatch 把 services.rag_config._CONFIG_PATH 重定向到 tmp_path，
  避免污染真实 config/rag.json
- 用 reset_rag_config_cache() 在每个测试间清空单例缓存
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture：隔离 config 路径 + 重置缓存
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_rag_config(tmp_path, monkeypatch):
    """重定向 services.rag_config._CONFIG_PATH 到 tmp_path/rag.json，并清空缓存。

    测试结束后再次清空缓存（防止后续测试读脏数据）。
    """
    import services.rag_config as rc

    cfg_path = tmp_path / "rag.json"
    monkeypatch.setattr(rc, "_CONFIG_PATH", cfg_path)
    rc.reset_rag_config_cache()
    yield cfg_path
    rc.reset_rag_config_cache()


def _write_cfg(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# 测试 1：文件缺键 → 回退默认
# ---------------------------------------------------------------------------
def test_rag_config_loads_defaults(isolated_rag_config):
    """文件缺 chunker.max_chars 键 → 回退默认 400；其他文件键正常读出。"""
    from services.rag_config import get_rag_config

    _write_cfg(isolated_rag_config, {
        # chunker 故意缺 max_chars（应回退 400），仅保留 overlap
        "chunker": {"overlap": 80},
        "retrieval": {"top_k": 7, "bm25_k1": 1.5, "bm25_b": 0.75, "rrf_k": 60},
        "dedup": {"key": "subject+concept"},
        "semantic": {"enabled": False},
    })

    cfg = get_rag_config()

    # 缺键回退默认
    assert cfg["chunker"]["max_chars"] == 400, (
        f"缺 max_chars 应回退到默认 400，实际 {cfg['chunker']['max_chars']}"
    )
    # 文件里有的键应正常读出
    assert cfg["chunker"]["overlap"] == 80
    assert cfg["retrieval"]["top_k"] == 7
    # 其他顶级节缺键也应回退默认
    assert cfg["retrieval"]["bm25_b"] == 0.75


# ---------------------------------------------------------------------------
# 测试 2：chunker 默认值从 get_rag_config() 读
# ---------------------------------------------------------------------------
def test_chunker_uses_config_max_chars(isolated_rag_config):
    """get_rag_config() 返回 max_chars=300 时，chunk_text() 默认按 300 切。"""
    from services.rag_config import get_rag_config
    from lib.ingest.chunker import chunk_text

    _write_cfg(isolated_rag_config, {
        "chunker": {"max_chars": 300, "overlap": 0},
        "retrieval": {"top_k": 5, "bm25_k1": 1.5, "bm25_b": 0.75, "rrf_k": 60},
        "dedup": {"key": "subject+concept"},
        "semantic": {"enabled": False},
    })

    # 先确认 config 真的被读了
    cfg = get_rag_config()
    assert cfg["chunker"]["max_chars"] == 300

    # 构造带句末标点的文本（每 4 chars 一句：'一二三。'）：
    # 400 chars / max_chars=300 → 第一块 = 300 chars（75 句），
    # 第二块 = 100 chars（25 句）。overlap=0 → 第一块长度严格 ≤ 300。
    text = "一二三。" * 100  # 400 chars（4 chars × 100）
    chunks = chunk_text(text)  # 不显式传 max_chars → 走 config 默认

    # 关键断言：第一块 ≤ config 给的 max_chars（300）。
    # 若 chunker 没读 config（仍用硬编码 400），则第一块会是 400 chars，此断言失败。
    assert len(chunks) >= 2, (
        f"400 字文本在 max_chars=300 下应至少 2 块，实际 {len(chunks)} 块"
    )
    assert len(chunks[0]) <= 300, (
        f"第一块应 ≤ config.max_chars=300，实际 {len(chunks[0])} chars。"
        "若 =400 则 chunker 没读 config，仍走硬编码默认。"
    )
    # 反向断言：chunk[0] 应接近 max_chars（贪心打包直到恰好 300）
    assert len(chunks[0]) == 300, (
        f"贪心打包下第一块应恰好 300 chars（75 句 × 4），实际 {len(chunks[0])} chars"
    )


# ---------------------------------------------------------------------------
# 测试 3：文件缺失 → 全默认不崩
# ---------------------------------------------------------------------------
def test_rag_config_missing_file_returns_defaults(isolated_rag_config):
    """config/rag.json 不存在时，get_rag_config() 返回全默认结构，不抛异常。"""
    from services.rag_config import get_rag_config

    # 确认文件确实不存在
    assert not isolated_rag_config.exists()

    # 必须不抛异常
    cfg = get_rag_config()

    # 全默认结构存在
    assert cfg["chunker"]["max_chars"] == 400
    assert cfg["chunker"]["overlap"] == 50
    assert cfg["retrieval"]["top_k"] == 5
    assert cfg["retrieval"]["bm25_k1"] == 1.5
    assert cfg["retrieval"]["bm25_b"] == 0.75
    assert cfg["retrieval"]["rrf_k"] == 60
    assert cfg["dedup"]["key"] == "subject+concept"
    assert cfg["semantic"]["enabled"] is False