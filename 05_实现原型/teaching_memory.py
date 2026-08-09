# -*- coding: utf-8 -*-
"""
PAEG 可编辑教学记忆（v0.19）

P2-9：对标 CLAUDE.md——教学约定文件，可被维护者/老师编辑，
每次对话自动加载注入 system prompt。

加载优先级：
1. memory/PAEG_PEDAGOGY.md     教学方法论（默认）
2. memory/improvements.md     自我改进建议（P2-8 生成，追加）
3. memory/teacher_notes.md    老师自定义笔记（可选，可创建）

用法：
    from teaching_memory import load_teaching_memory
    extra = load_teaching_memory()   # 返回注入 system 的文本
"""
from __future__ import annotations

import os
from typing import List


def _read(path: str, limit: int = 2000) -> str:
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()[:limit]
    except Exception:
        return ""


def load_teaching_memory() -> str:
    """加载全部教学记忆（拼接注入 system prompt）。"""
    base = os.path.dirname(os.path.abspath(__file__))
    mem_dir = os.path.join(base, 'memory')

    parts: List[str] = []
    # 1. 教学方法论
    ped = _read(os.path.join(mem_dir, 'PAEG_PEDAGOGY.md'))
    if ped:
        parts.append(ped)
    # 2. 自我改进建议（P2-8 生成）
    imp = _read(os.path.join(mem_dir, 'improvements.md'), limit=800)
    if imp:
        parts.append(f"## 近期教学改进建议（自动生成，参考）\n{imp}")
    # 3. 老师自定义笔记（可选）
    notes = _read(os.path.join(mem_dir, 'teacher_notes.md'), limit=1500)
    if notes:
        parts.append(f"## 老师自定义教学约定\n{notes}")
    # v0.19.22：自进化——学科提示词补丁（战术/战略，自动提炼）
    patches = _read(os.path.join(mem_dir, 'subject_patches.md'), limit=2000)
    if patches:
        parts.append(f"## 近期自动提炼的学科教学改进（自进化，供参考）\n{patches}")
    # v0.19.22：自进化——工具使用经验
    tlessons = _read(os.path.join(mem_dir, 'tool_lessons.md'), limit=1000)
    if tlessons:
        parts.append(f"## 工具使用经验（自进化，供参考）\n{tlessons}")

    if not parts:
        return ""
    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    m = load_teaching_memory()
    print("教学记忆长度:", len(m))
    print(m[:300])
