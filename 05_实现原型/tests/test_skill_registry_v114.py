# -*- coding: utf-8 -*-
"""test_skill_registry_v114.py —— §3.38 A1 ⭐ #29 多级 skill 目录测试

Harness 模式（skill-filesystem customSkillDirs，commit 47f9438）：
- 分层：全局（skills/）< 项目（config/skills/）< 用户（~/.paeg/skills/）
- 高优先级层同名覆盖低优先级层（用户可覆盖项目，项目可覆盖全局）
- 用户配置缺失 → 静默回退（不抛错）
- 支持 {env:KEY|默认} 变量替换（复用 config_loader._resolve_vars 模式）

当前（v1.1.3）缺陷：只支持单一 config/skills.json，无 ~/.paeg/skills.json 用户层。
"""
from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """隔离 HOME，避免测试污染真实 ~/.paeg。"""
    monkeypatch.setenv("PAEG_HOME", str(tmp_path / "paeg_home"))
    home = tmp_path / "paeg_home"
    (home / "skills").mkdir(parents=True)
    return home


def _write_skill(dirpath, name, desc):
    """在指定目录写一个 SKILL.md。"""
    sdir = os.path.join(dirpath, name)
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(f"---\ndescription: {desc}\n---\n# {name}\n")


def test_global_skills_load_by_default(tmp_path):
    """全局层（skills/）默认加载。"""
    from skill_registry import SkillRegistry
    reg = SkillRegistry()
    assert len(reg.skills) > 0, "全局 skills/ 目录应有技能"
    assert "math-step-solver" in reg.skills or "concept-explainer" in reg.skills


def test_user_skills_override_project(tmp_path, monkeypatch):
    """用户级 ~/.paeg/skills/<name> 覆盖项目级 config/skills/<name>（同名优先）。"""
    from skill_registry import SkillRegistry
    # 项目级（通过 PAEG_PROJECT_DIR 指向的 config/skills）
    import skill_registry as _sr
    base = os.path.dirname(os.path.abspath(_sr.__file__))
    # 临时项目目录
    proj = tmp_path / "config" / "skills"
    proj.mkdir(parents=True)
    _write_skill(str(proj), "probe_skill", "项目级描述")
    # 用户级（PAEG_HOME 指向的 ~/.paeg/skills）
    home = tmp_path / "home"
    (home / ".paeg" / "skills").mkdir(parents=True)
    _write_skill(str(home / ".paeg" / "skills"), "probe_skill", "用户级描述")
    # 写用户配置声明用户目录（含环境变量替换）
    monkeypatch.setenv("PAEG_HOME", str(home))
    with open(home / ".paeg" / "skills.json", "w", encoding="utf-8") as f:
        json.dump({"skills_dirs": ["{env:PAEG_HOME|}/.paeg/skills"]}, f)
    # 构造时 _load_dirs 读 PAEG_HOME + 项目 config/skills.json（真实 base 的 config/skills.json 含 skills/ config/skills/）
    reg = SkillRegistry()
    # 注入项目目录为中间层（在全局后、用户前）
    # 由于 base 的 config/skills.json 声明的是真实目录，probe_skill 只在临时 proj 中
    # 手动构造分层：全局 → proj → 用户
    reg.skills_dirs = [os.path.join(base, "skills"), str(proj), str(home / ".paeg" / "skills")]
    reg.reload()
    assert reg.skills.get("probe_skill") is not None, "用户级技能应加载"
    assert "用户级" in reg.skills["probe_skill"].description, "用户级应覆盖项目级"


def test_project_skills_override_global(tmp_path, monkeypatch):
    """项目级 config/skills/<name> 覆盖全局 skills/<name>。"""
    from skill_registry import SkillRegistry
    # 用 PAEG_PROJECT_DIR 模拟项目根（_load_dirs 会读 config/skills.json）
    proj_root = tmp_path / "proj"
    (proj_root / "skills").mkdir(parents=True)
    _write_skill(str(proj_root / "skills"), "probe_skill", "全局描述")
    proj_cfg = proj_root / "config" / "skills"
    proj_cfg.mkdir(parents=True)
    _write_skill(str(proj_cfg), "probe_skill", "项目级描述")
    # 配置 skills.json 声明两个目录（全局在前=低优先，项目在后=高优先）
    import json
    (proj_root / "config").mkdir(exist_ok=True)
    with open(proj_root / "config" / "skills.json", "w", encoding="utf-8") as f:
        json.dump({"skills_dirs": ["skills", "config/skills"]}, f)
    monkeypatch.chdir(proj_root)
    # 构造时 _load_dirs 用 module 所在目录为 base，需 monkeypatch base
    import skill_registry as _sr
    base = os.path.dirname(os.path.abspath(_sr.__file__))
    dirs = _sr.SkillRegistry()._load_dirs(base)
    # 用 add_dir 注入项目目录模拟分层（用户层=proj_config 应在项目后）
    reg = SkillRegistry()
    # 直接构造分层：把项目目录加为高优先级（列表后）
    reg.skills_dirs = [str(proj_root / "skills"), str(proj_cfg)]
    reg.reload()
    assert reg.skills.get("probe_skill") is not None
    assert "项目级" in reg.skills["probe_skill"].description, "项目级应覆盖全局"


def test_user_config_missing_fallback(tmp_path, monkeypatch):
    """~/.paeg/skills.json 缺失 → 静默回退（不抛错，仍加载项目/全局）。"""
    from skill_registry import SkillRegistry
    home = tmp_path / "home"
    (home / ".paeg").mkdir(parents=True)
    monkeypatch.setenv("PAEG_HOME", str(home))  # 无 skills.json
    # 不应抛异常
    reg = SkillRegistry()
    assert reg.skills is not None


def test_user_skills_json_env_substitution(tmp_path, monkeypatch):
    """用户配置支持 {env:KEY|默认} 变量替换。"""
    from skill_registry import SkillRegistry
    home = tmp_path / "home"
    (home / ".paeg").mkdir(parents=True)
    monkeypatch.setenv("PAEG_HOME", str(home))
    monkeypatch.setenv("PAEG_SKILLS_DIR", str(tmp_path / "env_skills"))
    (tmp_path / "env_skills").mkdir(parents=True)
    _write_skill(str(tmp_path / "env_skills"), "env_skill", "环境变量技能")
    # 写用户配置引用环境变量
    with open(home / ".paeg" / "skills.json", "w", encoding="utf-8") as f:
        json.dump({"skills_dirs": ["{env:PAEG_SKILLS_DIR|}"], "env_substitution": True}, f)
    reg = SkillRegistry()
    assert "env_skill" in reg.skills, "用户配置的环境变量目录应加载"
