# -*- coding: utf-8 -*-
"""prompt_registry.py —— §3.96 ⭐ 提示词清单（PromptRegistry）骨架（Oracle 方案 PR1）

单一权威清单：data/prompt_registry.json 维护所有提示词块
- type: fixed（固定）/ dynamic（运行时生成）/ user_input（用户原文）
- scenarios: 适用情景（[*] 全情景）
- priority: 装配顺序（越小越前；user_input 强制 99 末尾）
- source: const:/yml:/json:/runtime:/material_prompts: 装载来源
- hot_reload: 热更新标记；contains_user_input: trace 红标记；stage: 子阶段过滤

PR1 只立骨架 + 初始条目，不接入现有路径（build_presenter_system 等签名不变）。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple


# 默认注册表路径（可覆盖）
DEFAULT_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "prompt_registry.json")


class PromptRegistry:
    """提示词清单：按情景装配 system prompt + 可追溯 trace。"""

    def __init__(self, registry_path: str = DEFAULT_REGISTRY_PATH):
        self._path = registry_path
        self._raw: Dict[str, Any] = {}
        self._mtime: float = -1.0
        self.load()

    # ── 装载 / 热更新 ──
    def load(self) -> None:
        """装载注册表（缺失/损坏 → 空，不抛异常）。"""
        try:
            with open(self._path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and "blocks" in d:
                self._raw = d
                self._mtime = os.path.getmtime(self._path)
        except Exception:
            self._raw = {"blocks": [], "scenarios": {}}

    def reload_if_changed(self) -> bool:
        """热更新：文件变更时重新装载。返回是否重载。"""
        try:
            m = os.path.getmtime(self._path)
            if m != self._mtime:
                self.load()
                return True
        except Exception:
            pass
        return False

    # ── 查询 ──
    @property
    def blocks(self) -> List[Dict[str, Any]]:
        return self._raw.get("blocks", [])

    @property
    def scenarios(self) -> Dict[str, Any]:
        return self._raw.get("scenarios", {})

    def get_block(self, block_id: str) -> Optional[Dict[str, Any]]:
        for b in self.blocks:
            if b.get("id") == block_id:
                return b
        return None

    # ── 装配 ──
    def assemble(self, scenario: str, stage: Optional[str] = None,
                 inputs: Optional[Dict[str, Any]] = None,
                 resolvers: Optional[Dict[str, Callable]] = None,
                 ) -> Tuple[str, List[Dict[str, Any]]]:
        """按情景装配 system prompt。

        Args:
            scenario: 情景 id（teaching/material/confide/answer/chat/method/knowledge）
            stage: 子阶段（material 的 outline/slide_paint/render 等；None=跨阶段）
            inputs: 运行时输入（user_text/subject/grade/topic 等，供 runtime: 来源）
            resolvers: 自定义来源解析器（key=来源前缀，val=函数(block, inputs)->str）

        Returns: (system_prompt, trace)。trace 列出拼入块/来源/优先级/长度/user_input 标记。
        """
        inputs = inputs or {}
        candidates = [
            b for b in self.blocks
            if scenario in b.get("scenarios", []) or "*" in b.get("scenarios", [])
        ]
        # 按优先级排序（稳定：同优先级按 id 字典序）
        candidates.sort(key=lambda b: (b.get("priority", 50), b.get("id", "")))

        selected: List[Tuple[int, str, Dict[str, Any]]] = []
        trace: List[Dict[str, Any]] = []
        for b in candidates:
            # stage 过滤（"any"/null = 跨阶段，不过滤）
            b_stage = b.get("stage")
            if b_stage and b_stage != "any" and b_stage != stage:
                continue
            # condition 运行时判断
            cond = b.get("condition")
            if cond and not self._eval_condition(cond, inputs):
                continue
            # 解析来源
            txt = self._resolve(b, inputs, resolvers)
            if txt is None:
                continue
            trace.append({
                "id": b.get("id", "?"),
                "source": b.get("source", ""),
                "priority": b.get("priority", 50),
                "stage": b.get("stage"),
                "len": len(str(txt)),
                "user_input": bool(b.get("contains_user_input")),
            })
            selected.append((b.get("priority", 50), str(txt), b))

        body_parts = [t for _, t, _ in selected]
        # user_input 强制末尾
        if inputs.get("user_text"):
            body_parts.append(f"## 用户原话\n{inputs['user_text']}")
        return "\n\n".join(p for p in body_parts if p), trace

    # ── 内部 ──
    def _eval_condition(self, cond: str, inputs: Dict[str, Any]) -> bool:
        """简单条件求值：支持 == / in / 真值检查；失败默认 True（不阻断）。"""
        try:
            m = re.match(r"^(\w+)\s*(==|!=|in)\s*(.+)$", cond.strip())
            if m:
                var, op, val = m.group(1), m.group(2), m.group(3).strip().strip("'\"")
                actual = inputs.get(var)
                if op == "==":
                    return str(actual) == val
                if op == "!=":
                    return str(actual) != val
                if op == "in":
                    return val in (str(actual) if actual is not None else "")
            # 纯变量真值检查（如 "crisis_signal"）
            return bool(inputs.get(cond.strip()))
        except Exception:
            return True

    def _resolve(self, block: Dict[str, Any], inputs: Dict[str, Any],
                 resolvers: Optional[Dict[str, Callable]] = None) -> Optional[str]:
        """解析 source 指向（const:/yml:/json:/runtime:/material_prompts:）。"""
        src = str(block.get("source", ""))
        kind, _, path = src.partition(":")
        # 自定义 resolver 优先
        if resolvers and kind in resolvers:
            try:
                return str(resolvers[kind](block, inputs) or "")
            except Exception:
                return None
        try:
            if kind == "const":
                # const:模块.常量 或 直接字符串
                if "." in path:
                    mod_name, const_name = path.rsplit(".", 1)
                    import importlib
                    mod = importlib.import_module(mod_name)
                    return str(getattr(mod, const_name, "") or "")
                return path
            if kind == "yml":
                with open(path, encoding="utf-8") as f:
                    return f.read()
            if kind == "json":
                # json:文件路径[.字段路径]
                fp, _, field = path.partition("[")
                with open(fp.strip(), encoding="utf-8") as f:
                    d = json.load(f)
                if field:
                    field = field.rstrip("]")
                    for seg in field.split("."):
                        d = d.get(seg, {})
                return json.dumps(d, ensure_ascii=False, indent=2) if isinstance(d, (dict, list)) else str(d)
            if kind == "runtime":
                key = path.split(".", 1)[-1] if "." in path else path
                return str(inputs.get(key, "") or "")
            if kind == "material_prompts":
                # material_prompts:_MATERIAL_TEMPLATES[ppt].role
                import importlib
                mp = importlib.import_module("material_prompts")
                m = re.match(r"(\w+)\[(\w+)\]\.(\w+)", path)
                if m:
                    _dict_name, _key, _field = m.group(1), m.group(2), m.group(3)
                    d = getattr(mp, _dict_name, {})
                    item = d.get(_key, {})
                    if isinstance(item, dict):
                        return str(item.get(_field, "") or "")
                return ""
            if kind == "text":
                return path  # 字面文本
        except Exception:
            return None
        return None


# 模块级单例（复用，避免重复读文件）
_registry: Optional[PromptRegistry] = None


def get_registry() -> PromptRegistry:
    """获取模块级单例。"""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


def assemble(scenario: str, stage: Optional[str] = None,
             inputs: Optional[Dict[str, Any]] = None,
             resolvers: Optional[Dict[str, Callable]] = None,
             ) -> Tuple[str, List[Dict[str, Any]]]:
    """快捷入口：registry.assemble。"""
    return get_registry().assemble(scenario, stage=stage,
                                   inputs=inputs, resolvers=resolvers)


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    r = get_registry()
    print(f"PromptRegistry 就绪（{len(r.blocks)} 块 / {len(r.scenarios)} 情景）")
    txt, trace = r.assemble("teaching", inputs={"user_text": "什么是导数？"})
    print(f"teaching 装配: {len(txt)} 字符, {len(trace)} 块")
    for t in trace[:6]:
        print(f"  [{t['priority']:>2}] {t['id']}: {t['source']} ({t['len']}字)")
