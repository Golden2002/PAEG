# -*- coding: utf-8 -*-
"""fixers_lib.py —— §3.89 Step5 ⭐ 通用修复策略库（material_extensions/fixers 落地）

对标 Oracle 框架设计：三类修复策略适配 material_pipeline v2.0 fix_strategy 槽位。
签名：(stage_name, content, ctx, errors) -> new_content
- retry：同级重生成（LLM 按错误重做）
- escalate：ScopeRefine 三级升级（L1 场景内 → L2 重写 → L3 全重生）
- regenerate：整体重跑（重新调用 plan/draft）
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

Fixer = Callable[[str, Any, Dict[str, Any], List[str]], Any]


# ═══════════════════════════════════════════════════════════
# retry：同级重生成
# ═══════════════════════════════════════════════════════════
def make_retry_fixer(instructions: str = "") -> Fixer:
    """retry 修复器：LLM 按错误同级重生成内容。

    Args:
        instructions: 追加的修复指令（如物料类型专属约束）
    """

    def _fixer(stage_name, content, ctx, errors):
        llm = ctx.get("llm")
        if llm is None:
            return content
        try:
            from subagents import _safe_chat
            _mtype = ctx.get("material_type", "物料")
            _sys = (f"你是{_mtype}修复器。根据校验错误重写内容，"
                    f"保持主题与结构，只修违反项。{instructions}"
                    "输出修复后的完整内容。")
            _usr = (f"原内容：{str(content)[:3000]}\n"
                    f"错误：{errors}\n请修复。")
            _raw = _safe_chat(llm, _sys, _usr, max_tokens=4000)
            if _raw and str(_raw).strip():
                return _raw
            return content
        except Exception:
            return content

    return _fixer


# ═══════════════════════════════════════════════════════════
# escalate：ScopeRefine 三级升级
# ═══════════════════════════════════════════════════════════
def make_escalate_fixer(max_level: int = 3) -> Fixer:
    """escalate 修复器：按失败次数升级修复范围（L1→L2→L3）。

    依赖 manim_extensions.scope_refine；ctx 记录当前 level（跨轮升级）。
    """

    def _fixer(stage_name, content, ctx, errors):
        from manim_extensions import scope_refine
        _key = f"_fix_level_{stage_name}"
        _level = min(ctx.get(_key, 1), max_level)
        ctx[_key] = _level + 1  # 下次升级
        return scope_refine(content, errors, llm=ctx.get("llm"), level=_level)

    return _fixer


# ═══════════════════════════════════════════════════════════
# regenerate：整体重跑
# ═══════════════════════════════════════════════════════════
def make_regenerate_fixer() -> Fixer:
    """regenerate 修复器：整体重新生成（重新跑 plan+draft）。

    注意：需 ctx 携带 stages 引用；若不可用则退化 retry。
    """

    def _fixer(stage_name, content, ctx, errors):
        llm = ctx.get("llm")
        stages = ctx.get("stages")
        if llm is None or not isinstance(stages, dict):
            return make_retry_fixer()(stage_name, content, ctx, errors)
        try:
            _topic = ctx.get("topic", "主题")
            _subject = ctx.get("subject", "通用")
            _learner = ctx.get("learner_id", "anon")
            _spec = stages["plan"](llm, _topic, _subject, _learner)
            if not _spec:
                return content
            _draft = stages["draft"](llm, _spec, _topic, _subject, _learner)
            return _draft or content
        except Exception:
            return content

    return _fixer


# ═══════════════════════════════════════════════════════════
# 注册表
# ═══════════════════════════════════════════════════════════
FIXER_REGISTRY: Dict[str, Fixer] = {
    "retry": make_retry_fixer(),
    "escalate": make_escalate_fixer(),
    "regenerate": make_regenerate_fixer(),
}


def get_fixer(name: str) -> Optional[Fixer]:
    """按名取修复策略（retry/escalate/regenerate）。"""
    return FIXER_REGISTRY.get(name)


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("fixers_lib 修复策略库就绪")
    print("策略:", list(FIXER_REGISTRY.keys()))
    # 冒烟：retry 无 LLM 保持原样
    r = FIXER_REGISTRY["retry"]("draft", "内容", {}, ["错误"])
    print("retry(无LLM) 冒烟:", "OK" if r == "内容" else "FAIL")
    # escalate 无 LLM：L1 保持原样（dict，需非空 scenes）
    r2 = FIXER_REGISTRY["escalate"]("draft", {"scenes": [{"id": "s1"}]}, {}, ["err"])
    print("escalate(无LLM) 冒烟:", "OK" if isinstance(r2, dict) else f"FAIL {type(r2)}")
    # escalate 空剧本 → None（触发重生）
    r3 = FIXER_REGISTRY["escalate"]("draft", {"scenes": []}, {}, ["err"])
    print("escalate(空剧本→None) 冒烟:", "OK" if r3 is None else f"FAIL {type(r3)}")
