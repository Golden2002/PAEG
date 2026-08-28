# -*- coding: utf-8 -*-
"""material_harness.py —— §3.95 ⭐ 物料生产 AgentEngine harness 接入

用户要求："物料生产根据 agent 的 harness 逐步调用 LLM 先生成中间的文件，
中间的良好的文件又指导下一环节的物料的制作。"

复用 agent_engine.AgentEngine（Plan→Act→Observe→Reflect）驱动物料生成：
- Plan：规划物料（生成 spec/大纲——中间文件 1）
- Act：执行生成（产出物料内容——中间文件 2）
- Observe：门控检查（结构/质量门）
- Reflect：反思修正（门控失败则重试，中间文件指导修正）

与 MaterialPipeline v2.0 关系：harness 是"调度层"，pipeline 是"执行层"——
harness 用 AgentEngine 循环驱动 pipeline 的 plan/draft/implement 阶段。
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional


class MaterialHarness:
    """物料生产 harness：AgentEngine 循环驱动物料生成，中间产物落盘可下载。"""

    def __init__(self, llm, max_iterations: int = 3, replan_limit: int = 2):
        self.llm = llm
        self.max_iterations = max_iterations
        self.replan_limit = replan_limit
        self.trace: List[Dict[str, Any]] = []
        self.artifacts: Dict[str, Any] = {}   # 中间产物（可下载）

    # ── Plan：规划物料（中间文件 1：spec/大纲）──
    def _plan(self, material_type: str, topic: str, subject: str,
              grade: str, user_requirements: str) -> Dict[str, Any]:
        """规划阶段：生成物料 spec（大纲/结构规划）。

        用户要求（§3.95）作为提示词拼接进规划 prompt。
        """
        try:
            from subagents import _safe_chat
            _sys = (
                f"你是{self._type_cn(material_type)}规划师。为教学主题规划物料结构。\n"
                f"【用户要求】{user_requirements or '无'}\n"
                f"【学科】{subject}【学段】{grade}\n"
                "输出 JSON：{\"plan\": 结构规划, \"sections\": [...]}"
            )
            _usr = f"主题：{topic}\n请规划物料结构。"
            _raw = _safe_chat(self.llm, _sys, _usr, max_tokens=1500) or "{}"
            _m = __import__("re").search(r"\{.*\}", _raw, __import__("re").S)
            if _m:
                return json.loads(_m.group(0))
        except Exception:
            pass
        return {"plan": f"{topic}物料规划", "sections": []}

    # ── Act：执行生成（中间文件 2：物料内容）──
    def _act(self, material_type: str, topic: str, subject: str,
             spec: Dict[str, Any], generator: Callable) -> Dict[str, Any]:
        """执行阶段：调用物料生成器产出内容。"""
        try:
            return generator(self.llm, topic, subject, spec=spec) or {}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Observe：门控检查 ──
    def _observe(self, material_type: str, content: Any) -> List[str]:
        """观察阶段：结构/质量门检查，返回问题列表（空=通过）。

        §3.28 ⭐ 语言规范接线：除结构门外，追加语言门（AI 味/违禁词/省略句）——
        语言规范是内容输出的质量控制模块，harness 生产的文本物料必须过语言门。
        """
        issues = []
        try:
            from gates_lib import get_gates
            for gate in get_gates(material_type):
                ok, reason = gate(content, {})
                if not ok:
                    issues.append(reason)
        except Exception:
            pass
        # §3.28 ⭐ 语言门：AI 味/违禁词检测（复用 material_pipeline.language_gate）
        if isinstance(content, str) and content.strip():
            try:
                from material_pipeline import language_gate
                _lang_issues = language_gate(content[:3000], context=f"harness:{material_type}")
                issues.extend(_lang_issues)
            except Exception:
                pass
        # 基本非空门
        if not content:
            issues.append("内容为空")
        return issues

    # ── Reflect：反思修正 ──
    def _reflect(self, material_type: str, topic: str, content: Any,
                 issues: List[str]) -> Any:
        """反思阶段：根据门控问题修正内容（LLM 重写）。"""
        try:
            from subagents import _safe_chat
            _sys = (f"你是{self._type_cn(material_type)}修复器。根据问题修正物料，"
                    "保持结构，只修违反项。")
            _usr = f"问题：{issues}\n物料：{str(content)[:1500]}\n请修复。"
            _raw = _safe_chat(self.llm, _sys, _usr, max_tokens=2000)
            if _raw:
                return _raw
        except Exception:
            pass
        return content

    # ── 主流程：Plan→Act→Observe→Reflect 循环 ──
    def run(self, material_type: str, topic: str, subject: str,
            grade: str = "high_school", user_requirements: str = "",
            generator: Optional[Callable] = None,
            spec_generator: Optional[Callable] = None) -> Dict[str, Any]:
        """执行物料生产 harness 循环。

        Args:
            material_type: ppt/handout/video/manim/mindmap/script
            generator: 物料生成器（默认用 material_router._gen_xxx）
            spec_generator: 规划器（默认用 _plan）

        Returns: {ok, content, artifacts, trace, iterations}
        """
        # 默认生成器：material_router 的 ROUTER
        if generator is None:
            try:
                from material_router import ROUTER
                _route = ROUTER.get(material_type)
                if _route:
                    def _gen(llm, topic, subject, spec=None, **_kw):
                        return _route.generator(llm, topic, subject, "anon",
                                                user_requirements=user_requirements)
                    generator = _gen
            except Exception:
                generator = None

        result = {"ok": False, "content": None, "artifacts": {},
                  "trace": [], "iterations": 0}
        self.trace = []
        self.artifacts = {}

        # Plan（中间文件 1）
        t0 = time.time()
        if spec_generator:
            spec = spec_generator(material_type, topic, subject, grade, user_requirements)
        else:
            spec = self._plan(material_type, topic, subject, grade, user_requirements)
        self.artifacts["plan"] = spec
        self.trace.append({"phase": "plan", "spec": spec, "ts": time.time() - t0})

        # Act→Observe→Reflect 循环
        content = None
        replans = 0
        for i in range(self.max_iterations):
            # Act
            act_result = self._act(material_type, topic, subject, spec, generator)
            content = act_result.get("content") if isinstance(act_result, dict) else act_result
            if not content:
                content = str(act_result)
            self.artifacts["content"] = content
            self.trace.append({"phase": "act", "iter": i, "len": len(str(content))})

            # Observe
            issues = self._observe(material_type, content)
            self.trace.append({"phase": "observe", "iter": i, "issues": issues})
            if not issues:
                result["ok"] = True
                break

            # Reflect（修正）
            if replans < self.replan_limit:
                content = self._reflect(material_type, topic, content, issues)
                self.artifacts["content"] = content
                replans += 1
                self.trace.append({"phase": "reflect", "iter": i, "issues": issues})
            else:
                break

        result["content"] = content
        result["artifacts"] = self.artifacts
        result["trace"] = self.trace
        result["iterations"] = i + 1
        # §3.28 ⭐ 语言规范收口：最终文本物料过 lang_gate（Reflect 修正后仍收口）
        if isinstance(content, str) and content.strip():
            try:
                from material_pipeline import language_refine
                result["content"] = language_refine(content, context=f"harness:{material_type}")
            except Exception:
                pass
        return result

    # ── 工具 ──
    def _type_cn(self, material_type: str) -> str:
        return {"ppt": "PPT", "handout": "讲义", "video": "教学视频",
                "manim": "数学动画", "mindmap": "思维导图",
                "script": "讲稿"}.get(material_type, material_type)


# 模块级单例
_harness: Optional[MaterialHarness] = None


def get_harness(llm=None) -> MaterialHarness:
    """获取物料 harness（懒加载）。"""
    global _harness
    if _harness is None or (llm is not None and _harness.llm is None):
        _harness = MaterialHarness(llm)
    return _harness


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    h = MaterialHarness(None)
    r = h.run("handout", "光合作用", "生物", user_requirements="重点讲光反应")
    print(f"harness 冒烟: ok={r['ok']} iter={r['iterations']} trace={len(r['trace'])}")
    print("artifacts keys:", list(r['artifacts'].keys()))
