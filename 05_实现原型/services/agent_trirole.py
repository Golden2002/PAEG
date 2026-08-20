# -*- coding: utf-8 -*-
"""services/agent_trirole.py —— #11 9 Subagent 三角色契约（Harness 30 项 P0，§3.46.2，2026-08-16）

dsh Harness 借鉴（ctx.shell 三角色：Service Definition + Provider + Consumer，commit 47f9438）：
RuleDiagnostor vs LLMDiagnostor——同一 ServiceDefinition 可挂多个 Provider，Consumer 不感知实现。

设计（低风险增量，ratchet 铁律）：
- ServiceDefinition：服务契约（name/desc/input_schema/output_schema）——"做什么"
- ServiceProvider：服务实现（绑定定义，execute 契约）——"怎么做"
- Consumer：调用方（只依赖 ServiceProvider 抽象契约）——"谁来用"
- DEFAULT_SERVICE_DEFINITIONS：9 个内置 subagent 的服务契约（与 #1 装扮层/#21 Registry 对齐）
- register_definition()：自定义服务可注册（dsh 一切皆插件）

与既有机制衔接：
- #1 services/subagent_loader.py：9 subagent 装扮层（persona/prompt 配置）
- #21 infra/subagent_registry.py：provider 注册表（in-process/external-script/llm-call）
- 本模块：服务契约层（Definition/Provider/Consumer 三角色的类型基础）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class ServiceDefinition:
    """服务契约：定义"做什么"（与实现解耦）。

    dsh ctx.shell 三角色之 Definition——描述服务名/职责/输入输出 schema，
    不绑定任何实现。多个 Provider 可实现同一 Definition（Rule vs LLM 语义）。
    """
    name: str
    desc: str = ""
    input_schema: Dict[str, str] = field(default_factory=dict)
    output_schema: Dict[str, str] = field(default_factory=dict)


class ServiceProvider:
    """服务实现基类：绑定 ServiceDefinition，提供 execute 契约。

    dsh ctx.shell 三角色之 Provider——实现 Definition 声明的行为。
    子类实现 execute(**inputs) -> dict（output_schema 声明的结果）。
    """

    def __init__(self, definition: ServiceDefinition):
        self.definition = definition

    def execute(self, **inputs: Any) -> Dict[str, Any]:
        """执行服务（子类实现）。返回 output_schema 声明的结果 dict。"""
        raise NotImplementedError(f"{self.__class__.__name__}.execute 必须实现")


# ─────────────────────────────────────
# 9 个内置 subagent 服务契约（与 #1 装扮层对齐）
# ─────────────────────────────────────
DEFAULT_SERVICE_DEFINITIONS: Dict[str, ServiceDefinition] = {
    "diagnostor": ServiceDefinition(
        name="diagnostor", desc="学情诊断：知识缺口/认知风格/前置知识",
        input_schema={"question": "str", "subject": "str", "learner": "object"},
        output_schema={"diagnosis": "dict"},
    ),
    "planner": ServiceDefinition(
        name="planner", desc="学习计划：目标→步骤→资源",
        input_schema={"diagnosis": "dict", "subject": "str", "learner": "object"},
        output_schema={"plan": "dict"},
    ),
    "presenter": ServiceDefinition(
        name="presenter", desc="核心讲解：因材施教注入",
        input_schema={"concept": "str", "subject": "str", "learner": "object"},
        output_schema={"presentation": "dict"},
    ),
    "evaluator": ServiceDefinition(
        name="evaluator", desc="掌握度评估（确定性启发式）",
        input_schema={"session": "object"},
        output_schema={"evaluation": "dict"},
    ),
    "adapter": ServiceDefinition(
        name="adapter", desc="教学策略调整（画像驱动）",
        input_schema={"evaluation": "dict", "learner": "object"},
        output_schema={"adaptation": "dict"},
    ),
    "answer_solver": ServiceDefinition(
        name="answer_solver", desc="找答案/解题",
        input_schema={"question": "str", "subject": "str"},
        output_schema={"answer": "dict"},
    ),
    "affection_supportor": ServiceDefinition(
        name="affection_supportor", desc="情绪陪伴：不教不答不解决（薇依注意力）",
        input_schema={"text": "str", "learner": "object"},
        output_schema={"reply": "str"},
    ),
    "self_update_agent": ServiceDefinition(
        name="self_update_agent", desc="自我更新：反思→建议（质量门禁）",
        input_schema={"text": "str", "insights": "list"},
        output_schema={"suggestions": "list"},
    ),
    "individuality": ServiceDefinition(
        name="individuality", desc="个体化：17 维画像建模（因材施教）",
        input_schema={"text": "str", "learner": "object"},
        output_schema={"profile_prompt": "str"},
    ),
    # §3.79 Round 3 ⭐ 补全：v0.43/v0.69 新增 subagent 的服务契约
    # （此前契约只有 9 个，manifest 校验接入后 resource_librarian/lesson_prep 缺契约会报缺失）
    "resource_librarian": ServiceDefinition(
        name="resource_librarian", desc="资料检索员：知识库+Library+用户资料+联网聚合检索",
        input_schema={"query": "str", "scope": "str", "learner": "object"},
        output_schema={"chunks": "list", "has_any": "bool"},
    ),
    "lesson_prep": ServiceDefinition(
        name="lesson_prep", desc="备课生成器：教案+讲义+讲稿+PPT大纲+视频脚本+思维导图",
        input_schema={"topic": "str", "subject": "str", "grade": "str"},
        output_schema={"lesson_plan": "dict", "quality_report": "dict"},
    ),
}


# ─────────────────────────────────────
# API
# ─────────────────────────────────────
def get_definition(name: Optional[str] = None) -> Optional[ServiceDefinition]:
    """获取服务契约；未知 → None（容错）。"""
    if not name:
        return None
    return DEFAULT_SERVICE_DEFINITIONS.get(name)


def register_definition(definition: ServiceDefinition) -> None:
    """注册自定义服务契约（dsh 一切皆插件：服务可插拔）。"""
    DEFAULT_SERVICE_DEFINITIONS[definition.name] = definition


def make_provider(definition_name: str, impl_factory: Callable[[ServiceDefinition], ServiceProvider]) -> ServiceProvider:
    """按契约名构造 Provider（工厂注入实现）。"""
    sd = get_definition(definition_name)
    if sd is None:
        raise ValueError(f"未知服务契约: {definition_name}")
    return impl_factory(sd)


__all__ = [
    "ServiceDefinition", "ServiceProvider",
    "DEFAULT_SERVICE_DEFINITIONS",
    "get_definition", "register_definition", "make_provider",
]
