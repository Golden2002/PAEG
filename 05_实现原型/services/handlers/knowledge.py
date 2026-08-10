# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ services/handlers/knowledge.py

知识库查询（v0.19.15 从 server.py 迁出）。

用户问"你学过什么/你的知识库/你懂哪些"时，扫描 Library 文件夹，按领域列出
已收录内容，并提示用户可以上传资料让 Agent 更精通。返回**纯 dict**（不 jsonify），
调用方自行决定序列化方式——生成器（SSE 流）里没有 Flask app context。
"""
from __future__ import annotations

import os


def _handle_knowledge_query(learner, subject):
    """v0.19.15：知识库查询——汇总 Library 已收录的知识 + 提示上传。"""
    proj_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    lib_root = os.path.join(proj_root, 'Library')

    # 收集 Library 各领域的文件
    areas = []
    if os.path.isdir(lib_root):
        for name in sorted(os.listdir(lib_root)):
            d = os.path.join(lib_root, name)
            if os.path.isdir(d) and not name.startswith('.'):
                files = [f for f in os.listdir(d)
                         if not f.startswith('.') and os.path.isfile(os.path.join(d, f))]
                if files:
                    areas.append((name, files))

    # 用户上传的资料（单独列出）
    learner_id = getattr(learner, 'id', '')
    from services.library import get_user_library
    user_lib = get_user_library(learner_id) if learner_id else ""

    # 构建已收录内容清单（读取所有文件的真实内容，让 LLM 真正基于内容总结）
    inventory = []
    if areas:
        inventory.append("【Library 资料库收录（以下是每个文件的真实内容摘要，务必基于这些总结）】")
        for name, files in areas:
            inventory.append(f"## 领域：{name}（{len(files)} 份）")
            for f in files:
                fpath = os.path.join(lib_root, name, f)
                content_snippet = ""
                if f.endswith(('.md', '.txt', '.json')):
                    try:
                        with open(fpath, encoding='utf-8', errors='replace') as _f:
                            content_snippet = _f.read(800).strip()
                    except Exception:
                        content_snippet = ""
                elif f.endswith('.pdf'):
                    # 尝试提取 PDF 文本（用 pypdf 若可用）
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(fpath)
                        content_snippet = ""
                        for page in reader.pages[:3]:
                            content_snippet += (page.extract_text() or "") + " "
                        content_snippet = content_snippet.strip()[:800]
                    except Exception:
                        content_snippet = "（PDF，未能提取文本，仅知道文件名）"
                if content_snippet:
                    inventory.append(f"### 文件：{f}\n{content_snippet}")
                else:
                    inventory.append(f"### 文件：{f}\n（内容不可读，仅文件名）")
    if user_lib:
        inventory.append("【用户上传的专属资料】")
        inventory.append(user_lib)

    inventory_text = "\n".join(inventory) if inventory else "（Library 目前没有收录资料）"

    # v0.19.19：用 LLM 严格基于知识库实际内容总结（不得凭训练知识自由发挥）
    from subagents import _safe_chat
    from infra.runtime import get_llm
    from utils import _build_learner_ctx_str
    llm = get_llm()
    system = (
        "你是 Émile Novis。学生问你'你的知识库/你学过什么'。\n\n"
        f"{('【学生画像】' + _build_learner_ctx_str(learner) + '\n\n') if learner else ''}"
        "**最重要：你只能基于下面【Library 资料库收录】里的实际文件内容来回答**——"
        "这些是你真正'拥有'的资料。逐份介绍它们具体讲了什么（从内容摘要里提炼）。\n\n"
        "规则：\n"
        "1. 严格基于给出的文件内容总结，不要说你知识库里没有的东西\n"
        "2. 每份资料提到时，说它实际讲什么（如《数理统计讲义》从概率基础讲到假设检验、回归分析）\n"
        "3. 按领域分组介绍，像一位老师清点自己的藏书\n"
        "4. 如果有用户上传的资料，特别提到'我还保存着你上传的XXX'\n"
        "5. 结尾自然引导：**明确告诉学生以后只要问'知识库'/'你学过什么'，我就会为你打开这份资料清单**。"
        "同时邀请 ta 问我这些领域的任何问题；想让更精通某领域就上传资料（点书本图标）\n"
        "6. 语言像认真备课的老师，主谓宾完整\n"
        "7. 如果某文件内容不可读，如实说'这份是 PDF，我存着但还没细读内容'\n"
        "8. 如果清单是空的，就说'目前我的资料库还比较空，你可以先问我任何问题，或者上传资料让我更擅长'"
    )
    user = f"【Library 资料库实际内容】\n{inventory_text}\n\n请逐份基于这些内容，用老师式的语言总结你掌握的知识。"
    llm_answer = _safe_chat(llm, system, user, max_tokens=900)
    answer = llm_answer or ("我目前的知识库里收录了这些领域的资料，你可以问我相关问题，也可以上传资料让我更擅长。")

    return {
        "session_id": f"kb_{learner.id}",
        "summary": {"avg_score": 0},
        "worldview_used": "weil",
        "tone_ratio": 0,
        "presentations": [
            {"step_id": 1, "content": answer, "step_type": "knowledge"}
        ],
        "evaluations": [],
        "diagnosis": {},
        "plan": {"steps": []},
        "reflections": [],
        "learner": {
            "id": learner.id,
            "nickname": learner.nickname,
            "grade_level": learner.grade_level,
            "subjects_mastery": learner.subjects_mastery,
        },
    }
