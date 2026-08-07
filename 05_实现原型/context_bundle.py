# -*- coding: utf-8 -*-
"""
PAEG 统一上下文打包器（v0.20.3 ⭐ ContextBundle）

解决"对话上下文回传不完整"的系统性问题：
- 各端点注入不一致（chat_stream 完整，affection/knowledge/method/answer 缺失画像/BDI）
- teach_stream 主循环漏 user_model 推断
- 用户建模（BDI）、自我陈述、模式/学科/学段信息未统一注入

本模块提供：
1. build_user_model_bundle(history, description) —— 推断 user_model + BDI
2. build_learner_context(learner) —— 从 learner 提取画像段（昵称/学段/自我陈述/掌握度）
3. assemble_messages(history, current_text, max_history=10) —— 构造多轮 messages 列表
4. inject_user_model(learner, history) —— 给 learner 补 _user_model（懒推断）

用法：
    from context_bundle import build_user_model_bundle, build_learner_context, assemble_messages
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_user_model_bundle(history: list, description: str = "") -> Dict[str, Any]:
    """推断用户模型 + BDI（对象意识核心）。失败返回空 dict。"""
    try:
        from agent_core import infer_user_model, infer_bdi
        um = infer_user_model(history or [], description or "")
        try:
            um["bdi"] = infer_bdi(history or [], description or "")
        except Exception:
            um["bdi"] = {}
        return um
    except Exception:
        return {}


def inject_user_model(learner, history: list, description: str = "") -> Dict[str, Any]:
    """给 learner 补 _user_model（懒推断——若已有则不重复）。"""
    if getattr(learner, "_user_model", None):
        return learner._user_model
    um = build_user_model_bundle(history, description or getattr(learner, "self_description", ""))
    if um:
        learner._user_model = um
    return um


def build_learner_context(learner) -> str:
    """从 learner 提取画像上下文段（昵称/学段/自我陈述/掌握度）。"""
    if learner is None:
        return ""
    parts = []
    grade = getattr(learner, "grade_level", "high_school")
    grade_cn = {"middle_school": "初中", "high_school": "高中",
                "undergraduate": "大学本科", "graduate_exam": "考研"}.get(grade, grade)
    nickname = getattr(learner, "nickname", "学生") or "学生"
    parts.append(f"【学生画像】{grade_cn}学生（昵称 {nickname}）")
    desc = getattr(learner, "self_description", "") or ""
    if desc.strip():
        parts.append(f"【学生自我陈述（TA 亲笔写的，请始终尊重）】{desc.strip()}")
    # 掌握度
    mastery = getattr(learner, "subjects_mastery", None) or {}
    if mastery:
        m_str = "、".join(f"{k}:{v.get('mastery', 0):.2f}" for k, v in list(mastery.items())[:6])
        parts.append(f"【学科掌握度】{m_str}")
    # BDI（对象意识）
    um = getattr(learner, "_user_model", None)
    if um:
        bdi = um.get("bdi") or {}
        if bdi.get("summary"):
            parts.append(f"【我感觉到】{bdi['summary']}（请据此调整方式）")
        if bdi.get("beliefs"):
            parts.append(f"【可能的信念】{str(bdi['beliefs'])[:120]}")
        if bdi.get("desires"):
            parts.append(f"【可能的愿望】{str(bdi['desires'])[:120]}")
        if bdi.get("intentions"):
            parts.append(f"【可能的意图】{str(bdi['intentions'])[:120]}")
    return "\n".join(parts)


def build_meta_context(mode: str = "chat", subject: str = "default",
                       grade_level: str = "high_school") -> str:
    """构造模式/学科/学段元信息段（用户当前设定）。"""
    mode_cn = {"teach": "学科教学", "chat": "闲聊", "answer": "找答案",
               "method": "学习方法", "knowledge": "知识库", "affection": "倾诉"}.get(mode, mode)
    grade_cn = {"middle_school": "初中", "high_school": "高中",
                "undergraduate": "大学本科", "graduate_exam": "考研"}.get(grade_level, grade_level)
    parts = [f"【当前设定】对话模式：{mode_cn}；学段：{grade_cn}"]
    if subject and subject != "default":
        try:
            from prompts import get_style
            parts.append(f"学科：{get_style(subject)['label']}")
        except Exception:
            parts.append(f"学科：{subject}")
    return "；".join(parts)


def assemble_messages(history: list, current_text: str, max_history: int = 10) -> List[dict]:
    """构造多轮 messages 列表：[历史 user/assistant, ..., 当前 user]。

    history 元素形如 {"role": "user"/"assistant", "content": str}
    """
    msgs: List[dict] = []
    for h in (history or [])[-max_history:]:
        role = h.get("role", "user")
        content = h.get("content", "")
        if not content:
            continue
        msgs.append({"role": "assistant" if role == "assistant" else "user",
                     "content": content})
    msgs.append({"role": "user", "content": current_text})
    return msgs


def extract_user_facts(history: list, limit: int = 8) -> list:
    """v0.21.8：从用户消息中提取关键个人事实（偏好/身份/经历/承诺）。

    解决"多轮注意力丧失"——用户第 1 轮说"我喜欢蓝绿色"，
    第 7 轮追问时 LLM 必须还能看到。原理：把用户陈述的
    具体事实显式提取出来，注入 system prompt（而非只靠对话历史隐式携带）。

    提取规则（确定性，不依赖 LLM）：
    - 用户消息含"我喜欢/我爱/我讨厌/我最爱/我最喜欢/我养/我叫/我的" → 整句截取
    - 排除问题句（含？）和过短句（<6 字）
    """
    facts: list = []
    markers = ("我喜欢", "我爱", "我讨厌", "我最爱", "我最喜欢", "我养",
               "我叫", "我的名字", "我家的", "我最爱的", "我有个", "我有一只",
               "我住", "我的生日", "我下", "我准备", "我打算", "我的目标",
               "顺便告诉你", "告诉你", "记得", "我最近", "我下周",
               "I like", "I love", "I prefer", "My favorite", "I hate", "I am from",
               "my name is", "I have a", "I study", "I want to")
    seen = set()
    for msg in history or []:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content or "?" in content or len(content) < 6:
            continue
        for marker in markers:
            idx = content.find(marker)
            if idx >= 0:
                fact = content[max(0, idx):idx + 60]
                if fact not in seen:
                    seen.add(fact)
                    facts.append(fact)
                break
        if len(facts) >= limit:
            break
    return facts


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    # 自检
    msgs = assemble_messages(
        [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好呀"}],
        "我今天心情不好")
    print("messages:", msgs)
    print("meta:", build_meta_context("affection", "default", "high_school"))
