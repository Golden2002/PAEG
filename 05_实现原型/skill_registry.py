# -*- coding: utf-8 -*-
"""
PAEG Skills 技能体系（v0.19）

P1-4：对标 Anthropic Agent Skills（SKILL.md 开放标准）的三级渐进加载：
- L1 元数据：会话启动时注入技能目录（name + description）
- L2 指令：模型判断匹配后，加载完整 SKILL.md 正文
- L3 资源：按需读取技能目录下的脚本/参考文件

用法：
    reg = SkillRegistry()                     # 扫描 skills/ 目录
    catalog = reg.catalog_prompt()            # L1 注入 system
    body = reg.activate("math-step-solver")   # L2 加载完整指令
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional


class Skill:
    """单个技能。"""

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.frontmatter: Dict[str, str] = {}
        self.body: str = ""
        self._load()

    def _load(self):
        md_path = os.path.join(self.path, "SKILL.md")
        try:
            with open(md_path, encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            raw = ""
        # 解析 YAML frontmatter（--- 之间）
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            for line in fm.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    self.frontmatter[k.strip()] = v.strip()
            self.body = parts[2].strip()
        else:
            self.body = raw.strip()

    @property
    def description(self) -> str:
        return self.frontmatter.get("description", "")

    def to_tool_def(self) -> dict:
        """把技能暴露为可调用工具（让 LLM 决定是否加载）。"""
        return {
            "type": "function",
            "function": {
                "name": f"load_skill__{self.name}",
                "description": f"加载技能「{self.name}」的完整工作流程。{self.description}",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }

    def activate(self) -> str:
        """L2：返回完整技能正文。"""
        return f"# 技能：{self.name}\n{self.body}"


class SkillRegistry:
    """技能注册表：扫描 skills/ 目录（支持多目录，v0.68+ ⭐ 独立配置体系）。

    目录来源（config/skills.json 的 skills_dirs，缺省 ["skills", "config/skills"]）：
    - 默认 skills/（内置技能）
    - config/skills/（用户私有技能，独立成套配置接口）
    同名技能：先扫的目录优先（内置 > 用户私有，用户可覆盖同名内置）。
    """

    def __init__(self, skills_dirs: Optional[list] = None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.skills_dirs = list(skills_dirs or self._load_dirs(base))
        self.skills: Dict[str, Skill] = {}
        self.reload()

    def _load_dirs(self, base: str) -> list:
        """读 config/skills.json 的 skills_dirs；缺省用内置目录。"""
        _cfg = os.path.join(base, "config", "skills.json")
        try:
            import json as _json
            with open(_cfg, encoding="utf-8") as _f:
                _d = _json.load(_f)
            _dirs = _d.get("skills_dirs") or []
            if isinstance(_dirs, list):
                return [os.path.join(base, d) for d in _dirs]
        except Exception:
            pass
        return [os.path.join(base, "skills")]

    def reload(self):
        """遍历所有目录扫描 SKILL.md（同名先扫优先）。"""
        self.skills.clear()
        for _dir in self.skills_dirs:
            if not os.path.isdir(_dir):
                continue
            for name in os.listdir(_dir):
                sdir = os.path.join(_dir, name)
                if os.path.isdir(sdir) and os.path.isfile(os.path.join(sdir, "SKILL.md")):
                    if name not in self.skills:  # 同名先扫优先（内置 > 用户私有）
                        self.skills[name] = Skill(name, sdir)

    def add_dir(self, path: str):
        """运行时添加扫描目录（独立配置接口：丢目录即加载）。"""
        if path and os.path.isdir(path) and path not in self.skills_dirs:
            self.skills_dirs.append(path)
            self.reload()

    def remove_dir(self, path: str):
        """运行时移除扫描目录。"""
        if path in self.skills_dirs:
            self.skills_dirs.remove(path)
            self.reload()

    def catalog_prompt(self) -> str:
        """返回技能目录（名称+描述），注入 system prompt。"""
        if not self.skills:
            return ""
        lines = ["\n## 可用技能（当问题匹配时调用 load_skill__<名称> 加载完整流程）"]
        for s in self.skills.values():
            desc = s.description[:100]
            lines.append(f"- **{s.name}**: {desc}")
        lines.append("")
        return "\n".join(lines)

    # ─── L2：激活技能 ───
    def activate(self, name: str) -> str:
        s = self.skills.get(name)
        if not s:
            return f"技能不存在: {name}。可用: {', '.join(self.skills.keys())}"
        return s.activate()

    # ─── 工具定义（给 Function Calling 用） ───
    def tool_defs(self) -> List[dict]:
        return [s.to_tool_def() for s in self.skills.values()]

    def match_skill(self, text: str) -> Optional[str]:
        """启发式：判断学生输入匹配哪个技能（用于 Function Calling 不可用时兜底）。"""
        t = text or ""
        # 数学
        if any(k in t for k in ["求", "解", "计算", "证明", "求证", "方程", "导数",
                                "积分", "极限", "数学", "几何", "代数"]):
            if any(k in t for k in ["题", "求", "解", "证明", "计算"]):
                return "math-step-solver"
        # 评改
        if any(k in t for k in ["点评", "批改", "改一改", "评改", "帮我看看这篇文章",
                                "作文", "论述", "写得怎么样"]):
            return "essay-feedback"
        # 计划
        if any(k in t for k in ["学习计划", "备考", "怎么学", "规划", "时间安排",
                                "复习计划", "考", "安排"]):
            return "study-planner"
        # 概念
        if any(k in t for k in ["什么是", "解释", "是什么意思", "讲讲", "介绍一下",
                                "为什么"]):
            return "concept-explainer"
        return None

    def stats(self) -> dict:
        return {"skills": list(self.skills.keys()), "count": len(self.skills),
                "dirs": self.skills_dirs}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    reg = SkillRegistry()
    print("技能:", reg.stats())
    print()
    print("目录 prompt:")
    print(reg.catalog_prompt())
    print()
    print("激活 math-step-solver:")
    print(reg.activate("math-step-solver")[:200])
    print()
    print("匹配测试: '怎么安排考研复习计划' ->", reg.match_skill("怎么安排考研复习计划"))
    print("匹配测试: '求导' ->", reg.match_skill("求导"))
