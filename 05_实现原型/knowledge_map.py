# -*- coding: utf-8 -*-
"""
知识导图处理器（v0.20.5 ⭐ Knowledge Map）

用户说"画知识导图/列提纲/思维导图/知识结构/知识脉络/知识系统"时，
走专门的"知识导图"输出——生成结构化、分层的知识地图。

机制：
1. meta_router 检测关键词（is_knowledge_map_request）
2. 命中 → _handle_knowledge_map（本模块）加载 knowledge-map skill 指令
   + 注入学科画像 + 调用 LLM 输出结构化导图
3. 输出含"知识定位/主干结构/知识关联/学习路径"的结构化 Markdown
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

# 触发关键词（绑定：提纲/思维导图/知识结构/脉络/系统/图谱/脑图）
MAP_KEYWORDS = [
    "知识导图", "思维导图", "知识结构", "知识脉络", "知识系统",
    "列提纲", "画导图", "知识地图", "框架图", "知识框架",
    "知识图谱", "知识树", "概念图", "脑图", "认知地图", "mindmap",
    "全景图", "总览", "鸟瞰", "体系图",
    "提纲", "的结构", "的分支", "的体系", "的脉络", "的框架",
]
# 动词限定：必须含"画/列/整理/梳理/给我"等请求动词，避免误触发
MAP_VERBS = ["画", "列", "整理", "梳理", "给我", "看看", "帮我", "做", "讲一下", "介绍"]

COMPILED = [re.compile(k) for k in MAP_KEYWORDS]


def is_knowledge_map_request(text: str) -> bool:
    """判断是否请求知识导图/提纲/知识结构。"""
    t = (text or "").strip()
    if not t or len(t) > 80:
        return False
    # 至少命中一个关键词
    hit_kw = [k for k, c in zip(MAP_KEYWORDS, COMPILED) if c.search(t)]
    if not hit_kw:
        return False
    # 且有请求意图（动词）
    if any(v in t for v in MAP_VERBS):
        return True
    # 或本身就是"XX知识结构/XX思维导图"的明确请求
    if any(k in t for k in ["知识导图", "思维导图", "知识结构", "知识脉络", "知识系统", "列提纲", "知识地图", "框架图"]):
        return True
    return False


def _load_skill_instructions() -> str:
    """加载 knowledge-map 技能指令（SKILL.md）。"""
    try:
        import os
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'skills', 'knowledge-map', 'SKILL.md')
        with open(p, encoding='utf-8') as f:
            return f.read()[:3000]
    except Exception:
        return ""


def _extract_topic(text: str) -> str:
    """从请求中提取要画导图的知识点。"""
    # 去掉请求动词和关键词，剩下的是知识点
    for kw in ["知识导图", "思维导图", "知识结构", "知识脉络", "知识系统",
               "列提纲", "画导图", "知识地图", "框架图", "知识框架",
               "知识图谱", "知识树", "概念图", "脑图", "认知地图", "mindmap",
               "全景图", "总览", "鸟瞰", "体系图",
               "画", "列", "整理", "梳理", "给我", "看看", "帮我", "做", "讲一下", "介绍",
               "一下", "一个", "的", "关于", "请", "帮我"]:
        text = text.replace(kw, "")
    text = re.sub(r'[，。！？、\s]', '', text)
    return text.strip() or "这个知识点"


def handle_knowledge_map(concept: str, subject: str, learner, llm, history: list = None) -> Dict[str, Any]:
    """生成知识导图（结构化输出）。

    v0.21.1：新增 history 参数——"先问知识点再问知识框架图"时 LLM 需要上文。
    返回 {"content": str, "step_type": "knowledge_map"}
    """
    topic = _extract_topic(concept)
    skill_instructions = _load_skill_instructions()

    # 学科信息
    subject_cn = subject
    try:
        from prompts import get_style
        subject_cn = get_style(subject)["label"]
    except Exception:
        pass

    # 学生画像（对象意识）
    learner_ctx = ""
    try:
        from context_bundle import build_learner_context, inject_user_model
        if not getattr(learner, "_user_model", None):
            inject_user_model(learner, [{"content": concept}],
                              getattr(learner, "self_description", ""))
        learner_ctx = build_learner_context(learner)
    except Exception:
        pass

    # B4 ⭐ Oracle 连通性修复：思维导图注入三路资源（用户物料 + KB + 网络检索）
    _res_block = ""
    try:
        _res_parts = []
        # ① 用户物料（Library/usr_knowledge/<uid>/）
        try:
            from asset_loader import list_user_assets
            _uid = str(getattr(learner, "id", "") or "")
            _assets = list_user_assets(_uid)
            if _assets:
                _names = "、".join(_assets[:5])
                _res_parts.append(f"【用户资料库】有 {len(_assets)} 个文件（如：{_names}）。"
                                  f"若主题与其中内容相关，可引用。")
        except Exception:
            pass
        # ② 知识库检索（KnowledgeBase）
        try:
            from infra.runtime import get_kb
            _kb = get_kb()
            if _kb is not None:
                _r = _kb.search_subjects(topic, top_k=3) if hasattr(_kb, "search_subjects") else None
                if _r:
                    _res_parts.append(f"【知识库检索】与「{topic}」相关：{str(_r)[:200]}")
        except Exception:
            pass
        # ③ 网络检索（联网补充）
        try:
            from web_search_tool import web_search_multi
            _web = web_search_multi(topic, llm=llm, subject=subject, n=2)
            _items = (_web or {}).get("results") or (_web or {}).get("items") or []
            if _items:
                _snippet = str(_items[0].get("title") or _items[0].get("content") or "")[:150]
                _res_parts.append(f"【网络检索】补充：{_snippet}")
        except Exception:
            pass
        if _res_parts:
            _res_block = "\n\n".join(_res_parts) + "\n\n"
    except Exception:
        pass

    system = (
        "你是 Émile Novis，一位擅长把知识讲清楚的老师。学生要求生成知识导图/知识结构图。\n\n"
        f"【学生画像】{learner_ctx if learner_ctx else '（无画像）'}\n"
        f"【当前学科】{subject_cn}\n\n"
        f"【可用资源（B4 ⭐ 导图应基于这些而非凭空生成）】\n{_res_block}\n"
        f"【知识导图技能指令（必须遵循）】\n{skill_instructions}\n\n"
        "## 要求\n"
        "1. 严格按 SKILL.md 的输出规范（知识定位→主干结构→知识关联→一句话总结→学习路径）\n"
        "2. 主干结构用嵌套 Markdown 列表呈现知识树（分层清晰）\n"
        "3. 结合学生画像调整深度（高中/本科/考研）\n"
        "4. 语言克制、完整主谓宾（遵守全局语言规范）\n"
        "5. 公式用 LaTeX（$...$）\n"
        "6. 直接输出导图，不要解释你在做什么"
    )
    user = f"请为「{topic}」生成知识导图（学科：{subject_cn}）。"
    from subagents import _safe_chat
    # v0.21.1：若有历史（先问知识点再问导图），传真 messages 让 LLM 记住上文
    # v0.66 ⭐ 重试 2 次（DeepSeek 偶发空响应 → 否则兜底"生成失败"）
    reply = None
    for _attempt in range(3):
        if history:
            from context_bundle import assemble_messages
            msgs = assemble_messages(history, user)
            reply = _safe_chat(llm, system, messages=msgs, max_tokens=1200)
        else:
            reply = _safe_chat(llm, system, user, max_tokens=1200)
        if reply and len(reply.strip()) > 20:
            break
        import time as _t
        _t.sleep(1.0)
    if not reply:
        reply = f"我试着为「{topic}」整理知识导图，但生成失败了，请再试一次。"
    return {"content": reply, "step_type": "knowledge_map"}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    tests = [
        "画一下导数的知识导图",
        "帮我列个牛顿力学的提纲",
        "思维导图：热力学",
        "知识结构：线性代数",
        "什么是导数",           # 不应触发
        "你今天怎么样",          # 不应触发
    ]
    for t in tests:
        print(f'{"✅" if is_knowledge_map_request(t) else "❌"} {t}')
