# -*- coding: utf-8 -*-
"""PAEG 约束引擎（v0.70 §3.29 ⭐ MCP 化 · Oracle 设计）

把 prompts.py 的 L0-L8 分层动态约束系统暴露为标准接口（MCP tool + 内部函数双面）。

6 API（对应需求文档 §3.29 Oracle 方案）：
- constraint_layer_get(layer)      → 读某层放开组/规则
- constraint_layer_set(session, layer) → 动态切换约束层（教学/考试/自由）
- constraint_compose(parts[])      → 任意提示词块组合拼接
- constraint_always_active(names[])→ 永远保持激活的提示词（不随层放开）
- constraint_self_evolve(insight)  → 约束系统自我演化（LLM 提炼新规则入层）
- constraint_feedback_adjust(feedback, target) → 反馈调强/调弱约束

数据化：约束层/组规则可外置 data/constraint_layers.json（动态加载），
缺失时回退 prompts.py 内嵌（幂等容错）。

用法：
    from constraint_engine import constraint_layer_get, constraint_layer_set, ...
    # 或经 tool_registry.execute_tool("constraint_layer_get", {...})
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────
# 数据加载（外部 JSON 优先，内嵌回退）
# ─────────────────────────────────────

_CONSTRAINT_DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "constraint_layers.json")

_EXTRA_ACTIVE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "always_active.json")


def _load_ext_data(path: str) -> dict:
    """读外部数据文件（缺失/损坏 → 空 dict，不抛异常）。"""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_ext_data(path: str, data: dict) -> bool:
    """写外部数据文件。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _get_prompts_constants() -> Optional[dict]:
    """惰性导入 prompts.py 常量（避免启动期循环 import）。"""
    try:
        from prompts import (CONSTRAINT_LAYERS, L0_RESERVED_RULES,
                             _GROUP_RULES, _GROUP_NAMES, _build_constraint_layers)
        return {
            "layers": CONSTRAINT_LAYERS,
            "l0": L0_RESERVED_RULES,
            "group_rules": _GROUP_RULES,
            "group_names": _GROUP_NAMES,
            "build": _build_constraint_layers,
        }
    except Exception:
        return None


# ─────────────────────────────────────
# 外部层覆盖（数据化：用户可在 JSON 中扩展/修改层定义）
# ─────────────────────────────────────

def _merged_layers() -> dict:
    """内嵌层 + 外部覆盖合并（外部同名层整体替换 config）。"""
    c = _get_prompts_constants()
    layers = dict(c["layers"]) if c else {i: frozenset() for i in range(8)}
    ext = _load_ext_data(_CONSTRAINT_DATA_PATH).get("layers")
    if isinstance(ext, dict):
        for k, v in ext.items():
            try:
                layers[int(k)] = frozenset(v or [])
            except Exception:
                continue
    return layers


def _merged_groups() -> dict:
    """内嵌组规则 + 外部覆盖合并。"""
    c = _get_prompts_constants()
    groups = dict(c["group_rules"]) if c else {}
    ext = _load_ext_data(_CONSTRAINT_DATA_PATH).get("group_rules")
    if isinstance(ext, dict):
        for k, v in ext.items():
            if isinstance(v, list):
                groups[k] = v
    return groups


def _merged_always_active() -> list:
    """永远激活项 = 内嵌 L0 保底 + 外部 always_active.json。"""
    c = _get_prompts_constants()
    base = list(c["l0"]) if c else []
    ext = _load_ext_data(_EXTRA_ACTIVE_PATH).get("rules", [])
    merged = list(base)
    for r in ext:
        if isinstance(r, str) and r and r not in merged:
            merged.append(r)
    return merged


def _max_layer() -> int:
    """动态最大层号 = 合并后层定义的最大键（内嵌 0-7 + 外部可扩展 L8+）。"""
    layers = _merged_layers()
    if not layers:
        return 7
    return max(int(k) for k in layers)


def _clamp_layer(layer: int) -> int:
    """层号 clamp 到 [0, _max_layer()]（框架化：支持外部扩展任意层）。"""
    try:
        layer = int(layer)
    except Exception:
        layer = 4
    return max(0, min(_max_layer(), layer))


def constraint_layer_scope() -> str:
    """v0.70 ⭐ 框架自省：约束层级系统是框架化的——其他开发者可
    ① 更换每层内容（外部 JSON 覆盖 constraint_layers.json）② 拓展更多层级（任意 L8+）。
    返回当前层范围、每层来源、可用组、如何扩展。"""
    c = _get_prompts_constants()
    inner = dict(c["layers"]) if c else {}
    ext_data = _load_ext_data(_CONSTRAINT_DATA_PATH)
    ext_layers = ext_data.get("layers", {}) if isinstance(ext_data, dict) else {}
    ext_groups = ext_data.get("group_rules", {}) if isinstance(ext_data, dict) else {}
    all_layers = _merged_layers()
    max_l = _max_layer()
    names = dict(c["group_names"]) if c else {}
    groups = _merged_groups()

    lines = [
        f"[约束层级框架] 当前层范围 L0-L{max_l}（{len(all_layers)} 层）",
        "",
        "── 内嵌层（prompts.py CONSTRAINT_LAYERS，不可改源码）──",
    ]
    for k in sorted(inner):
        opened = sorted(inner[k])
        lines.append(f"  L{k}: 放开组 {opened if opened else '（无=全约束）'}")
    if ext_layers:
        lines.append("── 外部扩展层（data/constraint_layers.json，可增可改）──")
        for k in sorted(ext_layers):
            opened = sorted(ext_layers[k])
            lines.append(f"  L{k}: 放开组 {opened if opened else '（无=全约束）'}")
    else:
        lines.append("  （暂无外部扩展层）")
    lines.append("")
    lines.append("── 可用约束组（M节奏/R修辞/T温度/D教学法深度/S学科教学法/P哲学框架 + 可新增）──")
    for g in sorted(groups):
        src = "外部" if g in ext_groups else "内嵌"
        lines.append(f"  组[{g}]{names.get(g, g)}（{len(groups[g])} 条规则，{src}）")
    lines.append("")
    lines.append("── 框架扩展指南 ──")
    lines.append("a. 更换每层内容：编辑 data/constraint_layers.json 的 layers（如 {\"5\": [\"M\",\"R\"]}）整体替换该层 config")
    lines.append("b. 拓展更多层级：在 layers 加新键（如 \"8\": [\"M\",\"R\",\"T\",\"D\",\"S\",\"P\"]）→ constraint_layer_set(layer=8) 立即生效")
    lines.append("c. 新增约束组：在 group_rules 加新组（如 \"X\": [\"规则1\"]）→ 层定义引用 X 即可")
    lines.append("d. 永远激活：data/always_active.json 的 rules 不随任何层放开")
    return "\n".join(lines)


# ─────────────────────────────────────
# 6 API 实现
# ─────────────────────────────────────

def constraint_layer_get(layer: int) -> str:
    """读某层（0-Lmax，支持外部扩展层）放开组与规则。返回结构化的层描述。"""
    layer = _clamp_layer(layer)
    layers = _merged_layers()
    groups = _merged_groups()
    names = _get_prompts_constants()["group_names"] if _get_prompts_constants() else {}
    opened = layers.get(layer, frozenset())
    lines = [f"[约束层 L{layer}] 放开组：{len(opened)} 个"]
    if not opened:
        lines.append("  无放开组（本层保持全部约束）")
    for g in sorted(opened):
        gname = names.get(g, g)
        rules = groups.get(g, [])
        lines.append(f"  - 组[{g}]{gname}（{len(rules)} 条规则）")
        for r in rules[:3]:
            lines.append(f"      · {r[:50]}")
        if len(rules) > 3:
            lines.append(f"      · …（共 {len(rules)} 条）")
    active = _merged_always_active()
    lines.append(f"[L0 保底] 永远激活 {len(active)} 条")
    return "\n".join(lines)


def constraint_layer_set(session: Optional[str] = None, layer: int = 4,
                         reason: str = "") -> str:
    """动态切换约束层（教学/考试/自由，支持外部扩展层）。session 可指定会话级覆盖；
    未指定则返回"当前层配置段"（供拼接进 system prompt）。"""
    layer = _clamp_layer(layer)
    c = _get_prompts_constants()
    # 外部扩展层（>内嵌最大层）→ 用本引擎自拼（prompts._build_constraint_layers 内部 clamp 到 7）
    inner_max = max((int(k) for k in (c["layers"] if c else {})), default=7)
    if layer > inner_max:
        opened = sorted(_merged_layers().get(layer, set()))
        groups = _merged_groups()
        names = dict(c["group_names"]) if c else {}
        opened_rules = []
        for g in opened:
            opened_rules.extend(groups.get(g, []))
        parts = [f"## 输出效果约束（外部扩展层 · 当前 L{layer}）",
                 "L0 保底规则全部保留（语言规范/公式/反AI腔/安全）——永不放开。"]
        if opened_rules:
            parts.append("本层放开规则：")
            parts.extend(f"- {r}" for r in opened_rules[:10])
        else:
            parts.append("本层无放开组（保持全部约束）。")
        parts.append(f"放开组：{', '.join(f'{g}({names.get(g, g)})' for g in opened) if opened else '无'}")
        return "\n".join(parts)
    # 构建约束段（复用 prompts._build_constraint_layers 拼装逻辑）
    if c is not None:
        try:
            return c["build"](constraint_flags=(), layer=layer, crisis_signal=False)
        except Exception:
            pass
    # 回退：简单声明
    return f"## 输出效果约束（当前 L{layer}）\n保留 L0 保底规则，本层放开：{sorted(_merged_layers().get(layer, set()))}"


def constraint_compose(parts: List[str], title: str = "组合提示词") -> str:
    """任意提示词块组合拼接（parts 为提示词块列表或块名）。"""
    if not isinstance(parts, list) or not parts:
        return ""
    resolved = []
    for p in parts:
        if not isinstance(p, str):
            continue
        p = p.strip()
        if not p:
            continue
        resolved.append(p)
    if not resolved:
        return ""
    sep = "\n\n"
    body = sep.join(resolved)
    return f"## {title}\n{body}"


def constraint_always_active(action: str = "list", rule: str = "") -> str:
    """永远激活提示词管理（list/add/remove，落盘 data/always_active.json）。
    这些规则不随约束层放开，任何层都保留。"""
    data = _load_ext_data(_EXTRA_ACTIVE_PATH)
    rules = data.setdefault("rules", [])
    action = (action or "list").strip().lower()
    if action == "add":
        r = (rule or "").strip()
        if not r:
            return "参数错误：add 需要 rule"
        if r not in rules:
            rules.append(r)
            if _save_ext_data(_EXTRA_ACTIVE_PATH, data):
                return f"已添加永远激活规则（共 {len(rules)} 条外部 + 内嵌 L0）"
            return "写入失败"
        return f"该规则已在外部清单中（共 {len(rules)} 条）"
    if action == "remove":
        r = (rule or "").strip()
        if r in rules:
            rules.remove(r)
            if _save_ext_data(_EXTRA_ACTIVE_PATH, data):
                return f"已移除（剩余 {len(rules)} 条外部）"
            return "写入失败"
        return f"「{r}」不在外部清单（仅可移除外部添加项）"
    # list
    active = _merged_always_active()
    lines = [f"[永远激活] 共 {len(active)} 条（内嵌 L0 {max(0, len(active) - len(rules))} + 外部 {len(rules)}）"]
    for i, r in enumerate(active, 1):
        lines.append(f"  {i}. {r[:60]}")
    return "\n".join(lines)


def constraint_self_evolve(insight: str, target_layer: int = 4,
                           group: str = "D") -> str:
    """约束系统自我演化：把一条教学洞察提炼为约束规则，写入目标层对应组。
    数据化落盘 data/constraint_layers.json（不修改内嵌代码）。"""
    if not insight or not insight.strip():
        return "参数错误：insight 不能为空"
    data = _load_ext_data(_CONSTRAINT_DATA_PATH)
    layers = data.setdefault("layers", {})
    groups = data.setdefault("group_rules", {})
    try:
        layer = max(0, min(7, int(target_layer)))
    except Exception:
        layer = 4
    group = (group or "D").strip().upper()
    # 把 insight 包装为一条约束规则（可后续接 LLM 提炼，此处模板化）
    rule = f"【自演化 v0.70】{insight.strip()}"
    glist = groups.setdefault(group, [])
    if rule not in glist:
        glist.append(rule)
    # 把该组加入目标层（若未含）
    layer_key = str(layer)
    lset = layers.setdefault(layer_key, [])
    if group not in lset:
        lset.append(group)
    if _save_ext_data(_CONSTRAINT_DATA_PATH, data):
        return (f"自演化完成：洞察已写入 L{layer} 组[{group}]"
                f"（外部层 {len(layers)} 个，组规则 {sum(len(v) for v in groups.values())} 条）")
    return "写入失败"


def constraint_feedback_adjust(feedback: str, target: str = "layer") -> str:
    """反馈调强/调弱约束：根据用户反馈调整目标（layer 层 / group 组 / active 激活项）。
    feedback 含"太啰嗦/太直接/太机械/太严厉"等信号 → 映射到调整动作（记录到 feedback_log.jsonl）。"""
    if not feedback or not feedback.strip():
        return "参数错误：feedback 不能为空"
    # 信号词 → 调整动作映射（确定性规则，可复现）
    target = (target or "layer").strip().lower()
    action = "hold"
    notes = []
    fb = feedback.strip()
    if any(w in fb for w in ("太啰嗦", "啰嗦", "太长", "废话", "重复")):
        action = "loosen_m"          # 放宽节奏（缩短）
        notes.append("检测到『啰嗦』→ 建议放宽节奏组(M)")
    if any(w in fb for w in ("太直接", "直接", "生硬", "冷漠", "没温度")):
        action = "tighten_t"         # 收紧温度（更温柔）
        notes.append("检测到『太直接/冷漠』→ 建议收紧温度组(T)")
    if any(w in fb for w in ("太机械", "机械", "模板化", "套路", "千篇一律")):
        action = "loosen_s"          # 放宽学科教学法（更灵活）
        notes.append("检测到『太机械』→ 建议放宽学科教学法组(S)")
    if any(w in fb for w in ("太严厉", "严厉", "凶", "骂", "指责")):
        action = "tighten_t"
        notes.append("检测到『太严厉』→ 建议收紧温度组(T)")
    if any(w in fb for w in ("太浅", "肤浅", "不够深", "没讲透")):
        action = "loosen_d"          # 放宽深度限制（允许深入）
        notes.append("检测到『太浅』→ 建议放宽深度组(D)")
    if any(w in fb for w in ("太深", "太难", "听不懂", "跟不上")):
        action = "tighten_d"         # 收紧深度（浅显化）
        notes.append("检测到『太深/听不懂』→ 建议收紧深度组(D)")
    if action == "hold":
        notes.append("未识别明确调整信号（可尝试更具体反馈，如『太啰嗦』『太深』）")
    # 记录反馈（feedback_log.jsonl 追加）
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "constraint_feedback_log.jsonl")
        import time
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "feedback": fb[:200],
                "target": target,
                "action": action,
                "notes": notes,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return "；".join(notes) + f"\n[记录] 反馈已落盘 constraint_feedback_log.jsonl（action={action}）"


# ─────────────────────────────────────
# 工具定义（Function Calling schema，供 tool_registry 暴露）
# ─────────────────────────────────────

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "constraint_layer_get",
            "description": "读取 L0-L8 约束层（0-7）当前放开组与规则。"
                           "当需要了解某约束层内容、或确认当前约束状态时调用。",
            "parameters": {"type": "object",
                           "properties": {"layer": {"type": "integer", "description": "层号 0-7（默认 4）"}},
                           "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constraint_layer_set",
            "description": "动态切换 L0-L8 约束层（教学/考试/自由）。返回该层约束配置段，"
                           "可拼接进 system prompt。当需要按场景调整约束严格度时调用。",
            "parameters": {"type": "object",
                           "properties": {
                               "layer": {"type": "integer", "description": "目标层 0-7（默认 4 标准新授）"},
                               "session": {"type": "string", "description": "会话标识（可选）"},
                               "reason": {"type": "string", "description": "切换原因（记录用）"}},
                           "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constraint_compose",
            "description": "任意提示词块组合拼接（如 WEIL_CORE+LANGUAGE_STYLE+约束段）。"
                           "当需要把多个提示词块合成一个 system prompt 时调用。",
            "parameters": {"type": "object",
                           "properties": {
                               "parts": {"type": "array", "items": {"type": "string"},
                                         "description": "提示词块列表"},
                               "title": {"type": "string", "description": "组合标题（默认'组合提示词'）"}},
                           "required": ["parts"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constraint_always_active",
            "description": "永远激活提示词管理（list/add/remove，落盘 always_active.json）。"
                           "这些规则不随约束层放开，任何层都保留。当需要固定某条规则永远生效时调用。",
            "parameters": {"type": "object",
                           "properties": {
                               "action": {"type": "string", "description": "操作：list / add / remove"},
                               "rule": {"type": "string", "description": "add/remove 的规则文本"}},
                           "required": ["action"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constraint_self_evolve",
            "description": "约束系统自我演化：把教学洞察提炼为约束规则写入指定层/组（数据化落盘）。"
                           "当从教学反思中发现可复用的约束改进时调用。",
            "parameters": {"type": "object",
                           "properties": {
                               "insight": {"type": "string", "description": "教学洞察/新规则文本"},
                               "target_layer": {"type": "integer", "description": "目标层 0-7（默认 4）"},
                               "group": {"type": "string", "description": "目标组 M/R/T/D/S/P（默认 D 教学法深度）"}},
                           "required": ["insight"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constraint_feedback_adjust",
            "description": "反馈调强/调弱约束：根据用户反馈（太啰嗦/太直接/太机械/太深等信号）"
                           "给出约束调整建议并记录。当用户对输出风格/深度不满时调用。",
            "parameters": {"type": "object",
                           "properties": {
                               "feedback": {"type": "string", "description": "用户反馈文本"},
                               "target": {"type": "string", "description": "调整目标 layer/group/active（默认 layer）"}},
                           "required": ["feedback"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constraint_layer_scope",
            "description": "约束层级框架自省：返回当前层范围（L0-Lmax）、内嵌层与外部扩展层来源、"
                           "可用约束组、以及如何扩展（更换层内容/拓展更多层级/新增组）。"
                           "当需要了解约束系统可扩展性或指导他人二次开发时调用。",
            "parameters": {"type": "object",
                           "properties": {},
                           "required": []},
        },
    },
]

# 执行映射
_HANDLERS = {
    "constraint_layer_get": lambda a: constraint_layer_get(a.get("layer", 4)),
    "constraint_layer_set": lambda a: constraint_layer_set(
        a.get("session"), a.get("layer", 4), a.get("reason", "")),
    "constraint_compose": lambda a: constraint_compose(
        a.get("parts", []), a.get("title", "组合提示词")),
    "constraint_always_active": lambda a: constraint_always_active(
        a.get("action", "list"), a.get("rule", "")),
    "constraint_self_evolve": lambda a: constraint_self_evolve(
        a.get("insight", ""), a.get("target_layer", 4), a.get("group", "D")),
    "constraint_feedback_adjust": lambda a: constraint_feedback_adjust(
        a.get("feedback", ""), a.get("target", "layer")),
    "constraint_layer_scope": lambda a: constraint_layer_scope(),
}


def execute(name: str, arguments: dict) -> str:
    """内部统一执行入口（供 tool_registry 转发）。"""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"未知约束工具: {name}"
    try:
        return str(handler(arguments or {}))
    except Exception as e:
        return f"约束工具 {name} 执行出错: {e}"


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("== constraint_layer_get(4) ==")
    print(constraint_layer_get(4))
    print("\n== constraint_compose ==")
    print(constraint_compose(["【块1】你好", "【块2】这是语言规范", "【块3】约束段"], "测试组合"))
    print("\n== constraint_feedback_adjust ==")
    print(constraint_feedback_adjust("你讲得太啰嗦了"))
