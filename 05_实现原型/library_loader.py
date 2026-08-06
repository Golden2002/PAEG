"""
PAEG 知识库扩展加载器（v0.11）

任务 C：为智能体留出"扩展接口 + 文件夹"，允许未来向 Library 中加入大量知识库，
为模型提供更多现实的事实支撑。

目录约定（Library/ 下）：
  Library/KnowledgeBase/subjects/  *.json  —— 学科知识节点（与 knowledge_base.py 同构）
  Library/KnowledgeBase/facts/     *.md    —— 事实性资料（现实数据/史实/原文摘录）
  Library/Language/   *.md         —— 词汇/语法（未来可索引）
  Library/Math/       *.pdf        —— 数学资料（未来可解析）
  Library/Philosophy/ *.pdf        —— 哲学文本（未来可解析）
  Library/Simone Weil/ *.docx/pdf  —— 薇依原文（未来可检索）

用法：
    from library_loader import KnowledgeLibrary
    kl = KnowledgeLibrary()          # 扫描并加载
    kl.register()                    # 把学科节点并入 KnowledgeBase
    kl.search_facts("光合作用")       # 检索事实资料
"""

from __future__ import annotations

import glob
import json
import os
from typing import Dict, List, Optional


class KnowledgeLibrary:
    """扫描 Library 目录，加载可用的知识源。"""

    def __init__(self, base_dir: Optional[str] = None):
        # 默认 Library 目录
        self.base_dir = base_dir or os.path.join(
            r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目', 'Library')
        self.subjects: Dict[str, dict] = {}   # 从 subjects/*.json 加载
        self.facts: List[dict] = {}           # 从 facts/*.md 加载（文件名->内容）
        self.raw_files: List[dict] = []       # 其他可索引的源文件
        self._scan()

    def _scan(self):
        """扫描目录结构。"""
        kb_dir = os.path.join(self.base_dir, 'KnowledgeBase')
        # 1. 学科节点 JSON
        for fp in glob.glob(os.path.join(kb_dir, 'subjects', '*.json')):
            try:
                with open(fp, encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for nid, node in data.items():
                        if isinstance(node, dict):
                            node.setdefault('id', nid)
                            self.subjects[nid] = node
            except Exception as e:
                print(f'[library] 加载学科节点失败 {fp}: {e}')
        # 2. 事实资料 MD（文件名作为标题）
        for fp in glob.glob(os.path.join(kb_dir, 'facts', '*.md')):
            name = os.path.splitext(os.path.basename(fp))[0]
            try:
                with open(fp, encoding='utf-8') as f:
                    content = f.read()
                self.facts[name] = content
            except Exception as e:
                print(f'[library] 加载事实资料失败 {fp}: {e}')
        # 3. 其他源文件（仅登记路径，未来接入解析）
        for root, dirs, files in os.walk(self.base_dir):
            if 'KnowledgeBase' in root:
                continue
            for f in files:
                if f.endswith(('.md', '.txt', '.json')):
                    fp = os.path.join(root, f)
                    self.raw_files.append({'path': fp, 'name': f,
                                           'category': os.path.basename(root)})

    def register(self, knowledge_base) -> int:
        """把加载的学科节点并入 PAEG 的 KnowledgeBase。返回新增节点数。"""
        added = 0
        for nid, node in self.subjects.items():
            if nid not in knowledge_base.subjects:
                knowledge_base.subjects[nid] = node
                added += 1
        return added

    def search_facts(self, query: str, top_k: int = 3) -> List[dict]:
        """在事实资料中检索关键词。返回匹配片段。"""
        q = query.lower()
        results = []
        for name, content in self.facts.items():
            if q in name.lower() or q in content.lower():
                # 找匹配段落
                for para in content.split('\n\n'):
                    if q in para.lower():
                        results.append({'source': name, 'snippet': para[:300]})
                        break
        return results[:top_k]

    def list_sources(self) -> List[dict]:
        """列出所有可用的知识源。"""
        return [
            {'type': 'subject', 'name': nid} for nid in self.subjects
        ] + [
            {'type': 'fact', 'name': name} for name in self.facts
        ] + self.raw_files

    def stats(self) -> dict:
        return {
            'subjects': len(self.subjects),
            'facts': len(self.facts),
            'raw_files': len(self.raw_files),
        }
