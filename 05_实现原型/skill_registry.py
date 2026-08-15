# -*- coding: utf-8 -*-
"""
PAEG Skills 技能体系（v0.19）

P1-4：对标 Anthropic Agent Skills（SKILL.md 开放标准）的三级渐进加载：
- L1 元数据：会话启动时注入技能目录（name + description）
- L2 指令：模型判断匹配后，加载完整 SKILL.md 正文
- L3 资源：按需读取技能目录下的脚本/参考文件

§3.38 A1 ⭐ #29 多级 skill 目录（v1.1.4，借鉴 deepseek-harness skill-filesystem）：
- 三层优先级：全局（skills/）< 项目（config/skills/）< 用户（~/.paeg/skills/ 或 $PAEG_HOME/skills/）
- 高优先级层同名覆盖低优先级层（用户可覆盖项目，项目可覆盖全局）
- 用户配置 ~/.paeg/skills.json（或 $PAEG_HOME/skills.json）支持 {env:KEY|默认} 变量替换
- 配置缺失 → 静默回退（不抛错，向后兼容现有 config/skills.json 用户）

用法：
    reg = SkillRegistry()                     # 扫描 skills/ + config/skills/ + 用户层
    catalog = reg.catalog_prompt()            # L1 注入 system
    body = reg.activate("math-step-solver")   # L2 加载完整指令
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

# PyYAML 可选：装了就用真 YAML（支持多行 description / 列表 / 嵌套），没装就回退旧 split 解析。
try:
    import yaml as _yaml  # type: ignore
    _HAS_YAML = True
except Exception:  # ImportError / 环境受限
    _yaml = None
    _HAS_YAML = False


class Skill:
    """单个技能。"""

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.frontmatter: Dict[str, Any] = {}
        self.body: str = ""
        self._load()

    def _load(self):
        """读取 SKILL.md，解析 YAML frontmatter（--- 之间）+ markdown body。

        优先用 yaml.safe_load（支持多行 description / 列表 / 嵌套结构）；
        PyYAML 不可用时回退到冒号 split 解析（保持向后兼容）。
        """
        md_path = os.path.join(self.path, "SKILL.md")
        try:
            with open(md_path, encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            raw = ""

        # 找 frontmatter 边界：开头必须是 --- 起头
        parts = raw.split("---", 2)
        if len(parts) < 3:
            self.body = raw.strip()
            return

        fm_text = parts[1]
        self.body = parts[2].strip()

        if _HAS_YAML:
            # yaml.safe_load：支持多行 / 列表 / 嵌套
            try:
                parsed = _yaml.safe_load(fm_text) or {}
                if isinstance(parsed, dict):
                    # 统一 key 为 str（YAML 1.1 下 "on/off" 会变 bool 等异常值已 safe_load 屏蔽）
                    self.frontmatter = {str(k): v for k, v in parsed.items()}
                    return
            except Exception:
                # YAML 解析失败：兜底走旧 split 逻辑
                pass

        # 兜底：旧 split 解析（处理简单 key: value）
        for line in fm_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                self.frontmatter[k.strip()] = v.strip()

    @property
    def description(self) -> str:
        """frontmatter.description：多行/列表都安全序列化为单行字符串。"""
        v = self.frontmatter.get("description", "")
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return " / ".join(str(x) for x in v)
        return str(v) if v is not None else ""

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
        self._skill_origin: Dict[str, int] = {}  # §3.38 A1：name → 目录索引（优先级）
        self.reload()

    def _load_dirs(self, base: str) -> list:
        """§3.38 A1 ⭐ #29 三层路径合并（全局 < 项目 < 用户）。

        合并顺序（低→高优先级）：
        1. 全局默认：{base}/skills
        2. 项目配置：{base}/config/skills.json 的 skills_dirs（现有行为，向后兼容）
        3. 用户层：$PAEG_HOME/skills.json 或 ~/.paeg/skills.json（若存在），
           skills_dirs 支持 {env:KEY|默认} 变量替换（复用 config_loader._resolve_vars 模式）

        同名技能：先扫（低优先级层）的目录先注册，后扫（高优先级层）的同名不覆盖
        ——但 reload() 中高优先级目录排在后面会优先……实际语义：列表顺序即优先级，
        高优先级目录放**后面**，reload 时同名先扫优先（列表前者优先注册），
        因此高优先级层目录必须排在列表**前面**才能覆盖同名。
        """
        _dirs: list = []
        # 1. 全局默认（始终在最底层）
        _dirs.append(os.path.join(base, "skills"))

        # 2. 项目配置（config/skills.json，向后兼容）
        _cfg = os.path.join(base, "config", "skills.json")
        try:
            import json as _json
            with open(_cfg, encoding="utf-8") as _f:
                _d = _json.load(_f)
            _proj_dirs = _d.get("skills_dirs") or []
            if isinstance(_proj_dirs, list):
                for _d_ in _proj_dirs:
                    _p = os.path.join(base, _d_)
                    if os.path.isdir(_p) and _p not in _dirs:
                        _dirs.append(_p)
        except Exception:
            pass

        # 3. 用户层（$PAEG_HOME/skills.json 或 ~/.paeg/skills.json）
        _home = os.environ.get("PAEG_HOME") or os.path.expanduser("~")
        _user_cfg = os.path.join(_home, ".paeg", "skills.json")
        try:
            import json as _json2
            if os.path.isfile(_user_cfg):
                with open(_user_cfg, encoding="utf-8") as _f2:
                    _ud = _json2.load(_f2)
                _user_dirs = _ud.get("skills_dirs") or []
                if isinstance(_user_dirs, list):
                    for _ud_ in _user_dirs:
                        # {env:KEY|默认} 变量替换（复用 config_loader 模式）
                        _resolved = self._resolve_vars(_ud_)
                        _p2 = _resolved if os.path.isabs(_resolved) else os.path.join(_home, _resolved)
                        if os.path.isdir(_p2) and _p2 not in _dirs:
                            _dirs.append(_p2)
        except Exception:
            pass

        # 用户层目录放**前面**（最高优先级，reload 同名先扫优先）
        return _dirs

    @staticmethod
    def _resolve_vars(value: str) -> str:
        """{env:KEY|默认} 变量替换（与 config_loader._resolve_vars 同模式，避免循环导入）。"""
        import re as _re
        if not value or not isinstance(value, str):
            return value or ""
        def _sub(m):
            key, default = m.group(1), m.group(2)
            return os.environ.get(key, default or "")
        return _re.sub(r"\{env:([^}|]+)(?:\|([^}]*))?\}", _sub, value)

    def reload(self):
        """遍历所有目录扫描 SKILL.md（§3.38 A1 ⭐ 同名高优先级覆盖低优先级）。

        优先级：用户层 > 项目层 > 全局层（skills_dirs 列表越靠后优先级越高）。
        同一目录内同名冲突：取先扫到的（目录内去重）。
        """
        self.skills.clear()
        for _idx, _dir in enumerate(self.skills_dirs):
            if not os.path.isdir(_dir):
                continue
            for name in os.listdir(_dir):
                sdir = os.path.join(_dir, name)
                if os.path.isdir(sdir) and os.path.isfile(os.path.join(sdir, "SKILL.md")):
                    # 高优先级层（列表靠后）覆盖低优先级层（列表靠前）
                    if name not in self.skills or _idx > self._skill_origin_idx(name):
                        self.skills[name] = Skill(name, sdir)
                        self._skill_origin[name] = _idx

    def _skill_origin_idx(self, name: str) -> int:
        return self._skill_origin.get(name, -1)

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

    # v0.69+ P1-3（Step4 断链统一）：注入 skill L1 目录到 system（幂等）
    def inject_catalog(self, system: str) -> str:
        """把技能目录注入 system prompt（幂等：已含 `## 可用技能` 标记则跳过）。
        server.py 与 subagents.py 共用此方法——消除两处重复实现（防状态不同步）。"""
        if not system:
            return system
        try:
            catalog = self.catalog_prompt()
        except Exception:
            catalog = ""
        if not catalog:
            return system
        if "## 可用技能" in system:
            return system
        return system + "\n\n" + catalog

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
