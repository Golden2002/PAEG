# -*- coding: utf-8 -*-
"""Round 11 ⭐ 张宇扬课件知识库接线测试（test_round18_courseware_library.py）。

守护（用户小需求：张宇扬课件作为公共知识库）：
1. Library/common/张宇扬课件/ 存在且被 KnowledgeLibrary 索引（raw_files）
2. 课件 PDF 文本提取成功（content 非空）
3. search_facts 能检索到课件内容（真实知识可检索）
4. 检索消费端（services.library collect_all_resources）接入课件检索
"""
from __future__ import annotations

import os
import sys

import pytest

# 项目根 = 本文件(tests/) 上三级（tests → 05_实现原型 → 项目根）
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJ, "05_实现原型"))

from library_loader import KnowledgeLibrary

ZYY_DIR = os.path.join(PROJ, "Library", "common", "张宇扬课件")


@pytest.fixture(scope="module")
def kl():
    """模块级单例（课件 PDF 提取较重，进程内只提取一次）。"""
    return KnowledgeLibrary._get_instance()


class TestCoursewareIndexed:
    def test_zyy_dir_exists(self):
        assert os.path.isdir(ZYY_DIR), "张宇扬课件目录缺失（Library/common/张宇扬课件/）"

    def test_zyy_files_in_raw(self, kl):
        raw = kl.raw_files or []
        zyy = [f for f in raw
               if "张宇扬" in str(f.get("path") or "")
               or "Yuyang" in str(f.get("name") or "")
               or "YoungZhang" in str(f.get("name") or "")]
        # 张宇扬课件目录下：README + 演化(2 pdf) + 生态(2) + 生物信息(2) + 实验设计(2) + 生统(2) + 遗传(3+) + AT(5+) ...
        assert len(zyy) >= 5, f"张宇扬课件索引过少（{len(zyy)} < 5，应覆盖演化/生态/生物信息等）"

    def test_pdf_content_extracted(self, kl):
        raw = kl.raw_files or []
        with_content = [f for f in raw if f.get("content")]
        assert with_content, "无任何课件文本被提取（PDF/PPTX 提取失败）"

    def test_search_facts_hits_courseware(self, kl):
        r = kl.search_facts("遗传", top_k=3)
        hits = [h for h in r if h.get("kind") == "courseware"]
        assert hits, "课件检索未命中（search_facts 未接入 raw_files content）"

    def test_search_evolution_topic(self, kl):
        r = kl.search_facts("生态位", top_k=2)
        assert r, "生态位检索无结果（演化课件应含生态位内容）"


class TestConsumerWiring:
    def test_collect_all_resources_calls_search_facts(self):
        # services.library 消费端调 search_facts（课件检索进入教学资源块）
        from services import library as _lib_mod
        src = open(_lib_mod.__file__, encoding="utf-8").read()
        assert "search_facts" in src, "collect_all_resources 未调用 search_facts（课件检索未接入消费端）"
