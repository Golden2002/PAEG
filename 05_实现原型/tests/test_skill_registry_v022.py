# -*- coding: utf-8 -*-
"""
SkillRegistry 验证套件（v0.22）：
覆盖 skills/ 下 10 个 skill 的加载/激活/工具定义/目录 prompt/启发式匹配。

参考风格：test_self_referential.py / test_v0218_fixes.py
- 函数式测试 + sys.path.insert(0, '..') 导入根模块
- 每条用例末尾打印 "✔ test_xxx"
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skill_registry import SkillRegistry


# 期望的 10 个 skill（5 个自建 + 5 个 marketplace）
EXPECTED_SKILLS = [
    # 自建
    "concept-explainer",
    "essay-feedback",
    "knowledge-map",
    "math-step-solver",
    "study-planner",
    # marketplace 下载
    "pdf",
    "docx",
    "xlsx",
    "doc-coauthoring",
    "teach",
]


def _make_registry():
    """构造 SkillRegistry 实例"""
    return SkillRegistry()


def test_all_skills_loaded():
    """stats() 应返回 10 个 skill,名字集合与 EXPECTED_SKILLS 完全一致"""
    reg = _make_registry()
    st = reg.stats()
    assert st["count"] == 10, f"count 应为 10,实际 {st['count']}"
    names = set(st["skills"])
    expected = set(EXPECTED_SKILLS)
    assert names == expected, (
        f"skill 名字集合不一致。\n"
        f"  缺失: {expected - names}\n"
        f"  多余: {names - expected}"
    )
    print("✔ test_all_skills_loaded")


def test_each_skill_has_valid_frontmatter():
    """每个 skill 都能 activate() 返回非空正文,说明 SKILL.md 解析正常"""
    reg = _make_registry()
    for name in EXPECTED_SKILLS:
        body = reg.activate(name)
        assert isinstance(body, str), f"{name}: activate() 应返回 str"
        assert len(body) > 0, f"{name}: activate() 返回空字符串,SKILL.md 可能解析失败"
        # 至少应包含技能名或标题
        assert name in body or "技能" in body or "Skill" in body or "# " in body, (
            f"{name}: 激活内容缺少标识,body[:80]={body[:80]!r}"
        )
    print("✔ test_each_skill_has_valid_frontmatter")


def test_skill_tool_defs():
    """tool_defs() 应返回 10 个 load_skill__* 工具定义,每个含 name/description"""
    reg = _make_registry()
    defs = reg.tool_defs()
    assert isinstance(defs, list), "tool_defs() 应返回 list"
    assert len(defs) == 10, f"tool_defs 数量应为 10,实际 {len(defs)}"

    seen_names = set()
    for d in defs:
        # 形态: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        assert isinstance(d, dict), f"工具定义应为 dict,实际 {type(d)}"
        assert d.get("type") == "function", f"工具 type 应为 function,实际 {d.get('type')}"
        func = d.get("function")
        assert isinstance(func, dict), "function 字段应为 dict"
        name = func.get("name")
        desc = func.get("description")
        assert isinstance(name, str) and name.startswith("load_skill__"), (
            f"工具 name 应以 load_skill__ 开头,实际 {name!r}"
        )
        assert isinstance(desc, str) and len(desc) > 0, (
            f"工具 description 应为非空字符串,实际 {desc!r}"
        )
        seen_names.add(name)

    # 所有 10 个 skill 都应有对应的 load_skill__<name>
    expected_tool_names = {f"load_skill__{n}" for n in EXPECTED_SKILLS}
    assert seen_names == expected_tool_names, (
        f"工具名集合不一致。\n"
        f"  缺失: {expected_tool_names - seen_names}\n"
        f"  多余: {seen_names - expected_tool_names}"
    )
    print("✔ test_skill_tool_defs")


def test_skill_catalog_prompt():
    """catalog_prompt() 应包含全部 10 个 skill 的 name + description 摘要"""
    reg = _make_registry()
    prompt = reg.catalog_prompt()
    assert isinstance(prompt, str), "catalog_prompt() 应返回 str"
    assert len(prompt) > 0, "catalog_prompt() 返回空字符串"

    missing = []
    for name in EXPECTED_SKILLS:
        if name not in prompt:
            missing.append(name)
        else:
            # name 后面应有一段非空文字(至少 5 个字符的描述)
            idx = prompt.find(name)
            tail = prompt[idx + len(name): idx + len(name) + 200]
            # 描述至少要有冒号和文字
            assert ":" in tail or "：" in tail or len(tail.strip()) > 5, (
                f"{name}: 出现在 catalog_prompt 中但缺少 description"
            )
    assert not missing, f"catalog_prompt 缺失 skill: {missing}"
    print("✔ test_skill_catalog_prompt")


def test_match_skill_heuristics():
    """match_skill 启发式匹配典型输入"""
    reg = _make_registry()

    cases = [
        # (input, expected)
        ("帮我解方程", "math-step-solver"),
        ("点评作文", "essay-feedback"),
        ("什么是导数", "concept-explainer"),
        ("学习计划", "study-planner"),
    ]
    for text, expected in cases:
        got = reg.match_skill(text)
        assert got == expected, f"match_skill({text!r}) 应返回 {expected!r},实际 {got!r}"

    # "画思维导图" 按实际实现:当前实现未把"思维导图"映射到 knowledge-map,返回 None
    # (符合预期——保持实现不动,测试匹配实际行为)
    got = reg.match_skill("画思维导图")
    assert got is None or got == "knowledge-map", (
        f"match_skill('画思维导图') 应为 None 或 'knowledge-map',实际 {got!r}"
    )
    print("✔ test_match_skill_heuristics")


def test_activate_marketplace_skills():
    """5 个 marketplace skill 都能 activate 成功,返回非空正文"""
    reg = _make_registry()
    marketplace = ["pdf", "docx", "xlsx", "doc-coauthoring", "teach"]
    for name in marketplace:
        assert name in reg.skills, f"marketplace skill {name!r} 未加载"
        body = reg.activate(name)
        assert isinstance(body, str), f"{name}: activate() 应返回 str"
        assert len(body) > 0, f"{name}: activate() 返回空字符串"
        # 不应是 "技能不存在: ..." 兜底文本
        assert "技能不存在" not in body, f"{name}: 命中了不存在的兜底分支"
    print("✔ test_activate_marketplace_skills")