# -*- coding: utf-8 -*-
"""services/session_helpers.py —— 会话辅助函数（§3.46.2 Phase 2 拆分）

从 server.py 迁出（原 L283-340）：
- _append_chat_hist：统一对话历史写回（method/knowledge/affection 三端点共用）
- _set_constraint_flags：统一设置 learner 约束掩码（3 位掩码）

迁移理由：modes 蓝图需要这些函数，但蓝图禁止反向依赖入口模块（audit L521 单向依赖检查），
故下沉到 services/ 供 server 与 blueprints 共用；server.py 顶部 re-export 保既有符号。
"""
from __future__ import annotations

from typing import Any

# §3.46.2 Phase 3 ⭐ LLM trait 规范化符号自 server.py 下沉（chat/teach_stream 共用）
# 教训：LLM 建模直接输出英文枚举（visual/neutral 等）或越界长句，
# 原样写入 user_modeling → 前端显示"风 visual / 情 neutral"等奇怪词。
# 统一在写入端规范化：枚举→中文映射，长句截断（≤16 字）。
_TRAIT_LS_CN = {
    "visual": "视觉型", "auditory": "听觉型", "reading": "读写型",
    "kinesthetic": "动觉型", "mixed": "混合型",
}
_TRAIT_EMO_CN = {
    "anxious": "焦虑", "engaged": "投入", "neutral": "平静",
    "withdrawn": "退缩", "unknown": "未知",
}


def _norm_trait_scalar(value, mapping):
    """LLM trait 标量规范化：英文枚举→中文；未知/空→''；长句截断 16 字。"""
    if not isinstance(value, str):
        return ""
    v = value.strip()
    if not v or v in ("unknown", "null", "None"):
        return ""
    if v in mapping:
        return mapping[v]
    # v0.42.1 ⭐ P1 修复：LLM 可能输出组合值（如 "neutral_curiosity"）——
    # 精确映射失败时做子串匹配（含 "neutral" → "平静"），杜绝英文枚举残留进 meta-log。
    for k, cn in mapping.items():
        if k in v:
            return cn
    return v[:16] + ("…" if len(v) > 16 else "")


def _append_chat_hist(learner_id: str, user_content: str, assistant_content: str = "") -> None:
    """v0.42.3 ⭐ P0 修复：统一对话历史写回（method/knowledge/affection 三端点共用）。

    - 此前这 3 个端点只读 chat_hist 不写回（或完全不写），续问丢上文（"她"→"妈妈"回指失败）
    - 统一窗口 20 条（10 轮），与 teach/chat/answer 对齐
    """
    try:
        from infra.sessions import SESSIONS
        _ch = SESSIONS.setdefault(f"chat_hist_{learner_id}", [])
        if isinstance(_ch, list):
            _ch.append({"role": "user", "content": user_content})
            if assistant_content:
                _ch.append({"role": "assistant", "content": assistant_content})
            SESSIONS[f"chat_hist_{learner_id}"] = _ch[-20:]
    except Exception as _che:
        print(f"[PAEG] {learner_id} 写回 chat_hist 失败: {_che}")


def _set_constraint_flags(learner: Any, user_text: str, mode: str, affection: bool = False) -> None:
    """v0.43 ⭐ 统一设置 learner 的约束掩码（3 位掩码，各端点共用）。

    从用户输入/问卷检测 DIRECT/EMOTION/PREF → 存入 learner._constraint_flags，
    供 build_presenter_system/build_general_chat_system 的 constraint_flags 消费。
    """
    # v0.45 ⭐ E2E 修复：learner 可能为 None（未注册用户，SESSIONS 无该 id）——
    # 此前 except 分支 learner._constraint_flags=() 对 None 抛 AttributeError → answer 500。
    if learner is None:
        return
    try:
        from utils.constraint_signals import detect_constraint_flags
        _cf = detect_constraint_flags(
            user_text=user_text, key_need="", mode=mode,
            profile={"questionnaire_answers": getattr(learner, "questionnaire_answers", {}) or {}},
            affection_signal=affection,
        )
        learner._constraint_flags = _cf  # type: ignore[attr-defined]
    except Exception:
        try:
            learner._constraint_flags = ()  # type: ignore[attr-defined]
        except Exception:
            pass


__all__ = ["_append_chat_hist", "_set_constraint_flags",
           "_norm_trait_scalar", "_TRAIT_LS_CN", "_TRAIT_EMO_CN"]
