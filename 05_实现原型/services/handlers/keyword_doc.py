# -*- coding: utf-8 -*-
"""v0.42 ⭐ services/handlers/keyword_doc.py

关键词触发文档生成（v0.19.5 从 server.py 迁出）。

用户输入特定词时，把当前主题/回复整理成对应格式的文档：
- "讲义" → 授课式讲义（标题/引言/正文/例题/小结）
- "要点" → 知识要点清单（大纲式）
- "例题" → 配套例题 + 详解
- "笔记" → 学生笔记版（简化 + 留白）

返回 {"type", "filename", "md_url"} 或 None（未触发）。
"""
from __future__ import annotations


def handle_keyword_doc(user_text: str, reply: str, learner, data: dict):
    """v0.19.5：关键词触发文档生成。

    依赖全部函数体内 import（避免循环）；llm 从 infra.runtime 懒加载。
    """
    import re as _re
    import os as _os
    t = user_text or ""
    # 关键词 → 文档类型
    kw_map = [
        (r'讲义|授课|课件|handout', '讲义'),
        (r'要点|提纲|大纲|outline', '要点'),
        (r'例题|习题|题目|练习题', '例题'),
        (r'笔记|note|notes', '笔记'),
    ]
    doc_type = None
    for pat, dtype in kw_map:
        if _re.search(pat, t):
            doc_type = dtype
            break
    if not doc_type:
        return None

    from subagents import _safe_chat
    from infra.runtime import get_llm
    llm = get_llm()
    grade = getattr(learner, "grade_level", "high_school")
    grade_cn = {"middle_school": "初中", "high_school": "高中",
                "undergraduate": "大学本科", "graduate_exam": "考研"}.get(grade, grade)
    subject = data.get("subject", "通用")
    try:
        from prompts import get_style
        subject_cn = get_style(subject)["label"]
    except Exception:
        subject_cn = subject

    # 主题：优先用教学主题（data.concept），否则从用户输入提取，再否则用回复
    topic = (data.get("concept") or "").strip()
    if not topic or len(topic) < 2:
        topic = _re.sub(r'讲义|授课|课件|要点|提纲|大纲|例题|习题|题目|笔记|note|notes|给|我|把|这个|主题|做成|生成|一份|下载', '', t).strip()
    if not topic or len(topic) < 2:
        topic = (reply or "本次讨论").strip()[:30]
    topic = topic[:30]

    # 各类型文档的生成指令
    sys_tpl = {
        '讲义': "你是 Émile Novis，一位有学术功底的教育者。请把主题「{topic}」写成一份**规范的教学讲义**（{grade}·{subject}），结构：\n"
                "# {topic}\n\n## 引言（为什么值得学）\n## 正文（由浅入深：概念→机制→例子→深入）\n## 典型例题\n## 小结\n"
                "要求：公式用 LaTeX（$...$ / $$...$$），层次清晰，内容详实，像大学教授的讲义。",
        '要点': "把主题「{topic}」整理成**知识要点清单**（{grade}·{subject}）：用简洁的要点式结构列出核心概念、关键公式、易错点、记忆技巧。公式用 $...$。",
        '例题': "针对主题「{topic}」出 **3 道典型例题**（{grade}·{subject}），每道含：题目、完整解答（LaTeX 公式）、考查点说明。",
        '笔记': "把主题「{topic}」整理成**学生笔记版**（{grade}·{subject}）：比讲义更简洁，保留核心框架和公式，关键处留出思考留白的提示。",
    }
    system = sys_tpl[doc_type].format(topic=topic, grade=grade_cn, subject=subject_cn)
    doc_content = _safe_chat(llm, system, f"请生成{doc_type}文档。", max_tokens=1800)
    if not doc_content:
        doc_content = f"# {topic}\n\n（生成失败，请重试）"

    # 保存并返回下载链接
    try:
        from file_generator import FileGenerator
        fgen = None
        try:
            from infra.runtime import get_file_generator
            fgen = get_file_generator()
        except Exception:
            fgen = None
        if fgen is None:
            fgen = FileGenerator(llm)
        title = f"{subject_cn}{doc_type}：{topic[:20]}"
        _md, _html = fgen.save_answer(doc_content, title, subject_cn)
        from urllib.parse import quote
        return {
            "type": doc_type,
            "topic": topic[:30],
            "filename": _os.path.basename(_md),
            "md_url": "/api/download/" + quote(_os.path.basename(_md)),
            "html_url": "/api/download/" + quote(_os.path.basename(_html)),
        }
    except Exception as e:
        return {"type": doc_type, "error": str(e)}
