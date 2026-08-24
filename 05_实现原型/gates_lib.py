# -*- coding: utf-8 -*-
"""gates_lib.py —— §3.89 Step5 ⭐ 通用物料门库（material_extensions/gates 落地）

对标 Oracle 框架设计：5 类物料统一门控（结构/长度/密度/视觉焦点/分支）。
每门签名：(content, ctx) -> (ok: bool, reason: str)，适配 material_pipeline v2.0 gates 槽位。
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Tuple

Gate = Callable[[Any, Dict[str, Any]], Tuple[bool, str]]


# ═══════════════════════════════════════════════════════════
# 结构门（通用：dict/list 形状）
# ═══════════════════════════════════════════════════════════
def gate_structure_required(required_fields: List[str]) -> Gate:
    """结构门：content(dict) 必须含 required_fields。"""

    def _gate(content, ctx):
        if not isinstance(content, dict):
            return False, "内容不是 dict"
        missing = [f for f in required_fields if f not in content]
        if missing:
            return False, f"缺字段: {missing}"
        return True, ""

    return _gate


def gate_list_min(items_key: str = "scenes", min_count: int = 3) -> Gate:
    """列表数量门：content[items_key] 至少 min_count 项。"""

    def _gate(content, ctx):
        items = content.get(items_key) if isinstance(content, dict) else None
        if not isinstance(items, list):
            return False, f"缺少列表 {items_key}"
        if len(items) < min_count:
            return False, f"{items_key} 数量不足（{len(items)}/{min_count}）"
        return True, ""

    return _gate


# ═══════════════════════════════════════════════════════════
# 长度/密度门
# ═══════════════════════════════════════════════════════════
def gate_length(min_len: int, max_len: int = 0) -> Gate:
    """长度门：str 内容长度在 [min_len, max_len]（max_len=0 不限上界）。"""

    def _gate(content, ctx):
        if isinstance(content, dict):
            text = json.dumps(content, ensure_ascii=False)
        else:
            text = str(content or "")
        if len(text) < min_len:
            return False, f"内容过短（{len(text)}/{min_len}）"
        if max_len and len(text) > max_len:
            return False, f"内容过长（{len(text)}/{max_len}）"
        return True, ""

    return _gate


def gate_density(min_chars_per_block: int = 40) -> Gate:
    """密度门：每个 section/块至少有 min_chars 实质内容（防空壳）。

    适用讲义 sections[]（每节 ≥ min_chars_per_block 字）。
    """

    def _gate(content, ctx):
        sections = content.get("sections") if isinstance(content, dict) else None
        if not isinstance(sections, list):
            return True, ""  # 非 sections 结构跳过
        thin = []
        for i, s in enumerate(sections):
            body = " ".join(str(s.get(k, "")) for k in ("body", "content", "explanation", "examples"))
            if len(body.strip()) < min_chars_per_block:
                thin.append(f"节{i}")
        if thin:
            return False, f"薄节: {thin}（<{min_chars_per_block}字）"
        return True, ""

    return _gate


# ═══════════════════════════════════════════════════════════
# PPT 专属门（6×6 原则）
# ═══════════════════════════════════════════════════════════
def gate_ppt_pages(min_pages: int = 6, max_pages: int = 10) -> Gate:
    """PPT 页数门：6-10 页（教学 PPT 硬标准）。"""

    def _gate(content, ctx):
        pages = content.get("pages") if isinstance(content, dict) else None
        if not isinstance(pages, list):
            return False, "缺 pages 列表"
        if not (min_pages <= len(pages) <= max_pages):
            return False, f"页数 {len(pages)} 不在 [{min_pages},{max_pages}]"
        return True, ""

    return _gate


def gate_ppt_density(min_bullets: int = 3) -> Gate:
    """PPT 密度门：每页至少 min_bullets 条要点（防只有标题）。"""

    def _gate(content, ctx):
        pages = content.get("pages") if isinstance(content, dict) else []
        sparse = []
        for i, p in enumerate(pages):
            bullets = p.get("bullets") or p.get("points") or p.get("content") or []
            if isinstance(bullets, str):
                bullets = bullets.split("\n")
            if len(bullets) < min_bullets:
                sparse.append(f"页{i}")
        if sparse:
            return False, f"薄页: {sparse}（<{min_bullets}要点）"
        return True, ""

    return _gate


def gate_ppt_examples(min_examples: int = 1) -> Gate:
    """PPT 例子门：全册至少 min_examples 个实例（教学适用性）。"""

    def _gate(content, ctx):
        pages = content.get("pages") if isinstance(content, dict) else []
        examples = 0
        for p in pages:
            ex = p.get("examples") or p.get("example") or p.get("案例")
            if isinstance(ex, list):
                examples += len(ex)
            elif ex:
                examples += 1
        if examples < min_examples:
            return False, f"实例不足（{examples}/{min_examples}）"
        return True, ""

    return _gate


# ═══════════════════════════════════════════════════════════
# 思维导图专属门
# ═══════════════════════════════════════════════════════════
def gate_mindmap_branches(min_branches: int = 3, max_branches: int = 5) -> Gate:
    """思维导图分支门：3-5 个一级分支。"""

    def _gate(content, ctx):
        branches = content.get("branches") if isinstance(content, dict) else None
        if not isinstance(branches, list):
            return False, "缺 branches 列表"
        if not (min_branches <= len(branches) <= max_branches):
            return False, f"分支数 {len(branches)} 不在 [{min_branches},{max_branches}]"
        return True, ""

    return _gate


def gate_mindmap_depth(min_depth: int = 2) -> Gate:
    """思维导图深度门：分支至少嵌套 min_depth 层（含二级节点）。

    深度 = 嵌套层级（分支本身 1 层，有子节点则 +1），非子节点数量。
    """

    def _branch_depth(b) -> int:
        children = b.get("children") or b.get("nodes") or []
        if not children:
            return 1
        return 1 + max(_branch_depth(c) for c in children)

    def _gate(content, ctx):
        branches = content.get("branches") if isinstance(content, dict) else []
        shallow = []
        for i, b in enumerate(branches):
            if _branch_depth(b) < min_depth:
                shallow.append(f"分支{i}")
        if shallow:
            return False, f"浅分支: {shallow}（深度<{min_depth}）"
        return True, ""

    return _gate


# ═══════════════════════════════════════════════════════════
# 讲义专属门
# ═══════════════════════════════════════════════════════════
def gate_handout_sections(min_sections: int = 3) -> Gate:
    """讲义节数门：≥3 节（课前/课中/课后三维）。"""

    def _gate(content, ctx):
        sections = content.get("sections") if isinstance(content, dict) else None
        if not isinstance(sections, list):
            return False, "缺 sections 列表"
        if len(sections) < min_sections:
            return False, f"节数 {len(sections)} < {min_sections}"
        return True, ""

    return _gate


def gate_handout_blocks(min_blocks: int = 4) -> Gate:
    """讲义四块门：每节含 概念/讲解/例题/小结 四块之一（硬标准）。"""

    _BLOCKS = ("concept", "explanation", "example", "summary", "例题", "小结", "概念", "讲解")

    def _gate(content, ctx):
        sections = content.get("sections") if isinstance(content, dict) else []
        weak = []
        for i, s in enumerate(sections):
            s_str = json.dumps(s, ensure_ascii=False)
            hits = sum(1 for b in _BLOCKS if b in s_str)
            if hits < 1:
                weak.append(f"节{i}")
        if weak:
            return False, f"缺块节: {weak}"
        return True, ""

    return _gate


# ═══════════════════════════════════════════════════════════
# 注册表（按物料类型）
# ═══════════════════════════════════════════════════════════
GATE_REGISTRY: Dict[str, List[Gate]] = {
    "ppt": [gate_ppt_pages(), gate_ppt_density(), gate_ppt_examples()],
    "handout": [gate_handout_sections(), gate_handout_blocks(), gate_density()],
    "mindmap": [gate_mindmap_branches(), gate_mindmap_depth()],
}


def get_gates(material_type: str) -> List[Gate]:
    """按物料类型取门列表（无则空列表，由管线默认门兜底）。"""
    return GATE_REGISTRY.get(material_type, [])


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("gates_lib 门库就绪")
    print("PPT 门 3 个:", len(GATE_REGISTRY["ppt"]))
    print("讲义门 3 个:", len(GATE_REGISTRY["handout"]))
    print("导图门 2 个:", len(GATE_REGISTRY["mindmap"]))
