# -*- coding: utf-8 -*-
"""Gap B：library_loader._scan 对 .md/.txt/.docx 内容的索引测试。

此前 _scan 只登记 .md/.txt/.json 的 name/category（无 content，search_facts 无法命中），
且完全跳过 .docx/.doc（只有 .pptx/.pdf 才做文本提取）。结果 Library/Linguistics/*.md
与 Simone Weil/*.docx 存在但不可检索。本测试守护：
  1. .md/.txt 内容入 raw_files（content 非空）
  2. search_facts 能命中 .md 内容关键词
  3. python-docx 可用时 .docx 内容也被提取
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from library_loader import KnowledgeLibrary


def _has_docx():
    try:
        import docx  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture
def lib(tmp_path):
    """构造最小 Library 目录（无课件缓存 → 走 os.walk 扫描路径）。"""
    ling = tmp_path / "Linguistics"
    ling.mkdir()
    (ling / "vocab.md").write_text(
        "# 词汇\n\n光合作用是植物把光能转化为化学能的过程。\n", encoding="utf-8")
    (ling / "notes.txt").write_text(
        "量子纠缠是粒子间的一种关联现象。\n", encoding="utf-8")
    if _has_docx():
        try:
            import docx
            d = docx.Document()
            d.add_paragraph("薇依：扎根是最重要而最被忽略的需求。")
            weil = tmp_path / "Simone Weil"
            weil.mkdir()
            d.save(str(weil / "weil.docx"))
        except Exception:
            pass
    return KnowledgeLibrary(base_dir=str(tmp_path))


def test_md_content_loaded(lib):
    entry = next((e for e in lib.raw_files if e.get("name") == "vocab.md"), None)
    assert entry is not None, "vocab.md 应被索引进 raw_files"
    assert entry.get("content"), "vocab.md 的 content 不应为空"
    assert "光合作用" in entry["content"]


def test_search_facts_finds_md_keyword(lib):
    hits = lib.search_facts("光合作用", top_k=3)
    assert hits, "search_facts 应能检索到 .md 内容中的关键词"
    assert any("vocab.md" in str(h.get("source")) for h in hits)


def test_txt_content_loaded(lib):
    entry = next((e for e in lib.raw_files if e.get("name") == "notes.txt"), None)
    assert entry is not None
    assert "量子纠缠" in (entry.get("content") or "")


@pytest.mark.skipif(not _has_docx(), reason="python-docx 不可用")
def test_docx_content_extracted(lib):
    entry = next((e for e in lib.raw_files
                  if str(e.get("name", "")).endswith(".docx")), None)
    assert entry is not None, ".docx 应被索引进 raw_files"
    assert entry.get("content"), ".docx 内容应被提取"
    assert "薇依" in entry["content"]
