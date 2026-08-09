"""
PAEG v0.5 交互式教学 CLI。

功能：
  - 学习者设置（昵称/年级）
  - 学科目录浏览 + 自由提问
  - 安全中间件（safety.py）拦截敏感输入
  - 真实 LLM 教学（自动发现凭据）；离线时回退 Mock
  - 教学循环后支持苏格拉底式追问

用法：
  python cli.py                     # 自动模式（优先真实 LLM）
  python cli.py --mock              # 强制离线
  python cli.py --subject physics --question "什么是熵？"   # 单轮直跑
  python cli.py --persist data      # 画像持久化到 data/profiles.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from knowledge_base import KnowledgeBase
from paeg import LearnerProfile, PAEG
from safety import SafetyChecker
from llm_adapter import create_llm
from self_update import SelfUpdater  # noqa: F401  （确保持久化模块可导入）

# 中文标识符宽度对齐显示
import shutil

BANNER = """
=====================================================================
  PAEG - Pedagogical Agent with Evolving Growth  (v0.5)
  自我更新的教育者智能体
  学科知识 | 审美 · 道德 · 思辨 · 生命现象学素养
=====================================================================
"""


def _println(text: str):
    print(text)


def load_profile(path: Path, learner_id: str) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get(learner_id, {})
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_profile(path: Path, learner_id: str, profile: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    data[learner_id] = profile
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run_teaching(paeg: PAEG, learner: LearnerProfile, question: str, subject: str) -> dict:
    """执行一次教学，返回 result。"""
    result = paeg.teach(learner, question, subject)
    summary = result["summary"]
    _println("\n" + "-" * 60)
    _println(f"教学完成：{summary['concept']}")
    _println(f"  平均分：{summary['avg_score']:.3f} | 步骤：{summary['steps_completed']} | "
             f"主导世界观：{result.get('worldview_used', '?')}")
    if result.get("tone_ratio"):
        _println(f"  世界观比例：{result['tone_ratio']}")
    return result


def socratic_follow_up(paeg: PAEG, learner: LearnerProfile, subject: str, checker: SafetyChecker):
    """苏格拉底式追问循环。"""
    _println("\n[追问模式] 输入问题继续追问（q 退出，m 换学科）：")
    while True:
        try:
            q = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            _println("\n再见！")
            return
        if q.lower() in ("q", "quit", "exit"):
            _println("再见！")
            return
        if q.lower() in ("m", "menu"):
            return
        if not q:
            continue
        guard = checker.guard_question(q, learner)
        if guard:
            _println(f"  [安全拦截] {guard['reason']}")
            _println(f"  {guard['suggestion']}")
            continue
        result = paeg.teach(learner, q, subject)
        _println(f"  平均分：{result['summary']['avg_score']:.3f}")


def interactive_loop(paeg: PAEG, learner: LearnerProfile, kb: KnowledgeBase,
                     checker: SafetyChecker, persist_dir: str = ""):
    catalog = kb.subject_catalog()
    subjects = sorted(catalog.keys())
    _println("可选学科：")
    for i, s in enumerate(subjects, 1):
        nodes = catalog[s]
        _println(f"  {i:2d}. {s:<16s}（{len(nodes)} 节点）")

    current_subject = None
    while True:
        try:
            choice = input("\n[主菜单] 输入学科编号/名称，或 q 退出：").strip()
        except (EOFError, KeyboardInterrupt):
            _println("\n再见！")
            return
        if choice.lower() in ("q", "quit", "exit"):
            _println("再见！")
            return

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(subjects):
                current_subject = subjects[idx]
            else:
                _println("无效编号。")
                continue
        elif choice in catalog:
            current_subject = choice
        else:
            _println("未找到该学科，请重试。")
            continue

        _println(f"\n=== 学科：{current_subject} ===")
        while True:
            try:
                q = input(f"[{current_subject}] 提问（q 返回学科列表）：").strip()
            except (EOFError, KeyboardInterrupt):
                _println("\n再见！")
                return
            if q.lower() in ("q", "quit", "exit"):
                break
            if not q:
                continue
            guard = checker.guard_question(q, learner)
            if guard:
                _println(f"  [安全拦截] {guard['reason']}")
                _println(f"  {guard['suggestion']}")
                continue
            run_teaching(paeg, learner, q, current_subject)
            socratic_follow_up(paeg, learner, current_subject, checker)
            # 追问结束后保存画像
            if persist_dir:
                save_profile(Path(persist_dir) / "profiles.json", learner.id, {
                    "nickname": learner.nickname,
                    "grade_level": learner.grade_level,
                    "age": learner.age,
                    "cognitive_style": learner.cognitive_style,
                    "subjects_mastery": learner.subjects_mastery,
                    "world_view_blend": learner.world_view_blend,
                    "target_exam": learner.target_exam,
                    "specialty_target": learner.specialty_target,
                    "updated_at": datetime.now().isoformat(),
                })


def main():
    parser = argparse.ArgumentParser(description="PAEG v0.5 交互式教学 CLI")
    parser.add_argument("--mock", action="store_true", help="强制离线 Mock 模式")
    parser.add_argument("--provider", default="auto", help="llm provider: auto/mock/deepseek/openai/anthropic")
    parser.add_argument("--subject", default=None, help="单轮模式：学科")
    parser.add_argument("--question", default=None, help="单轮模式：问题")
    parser.add_argument("--grade", default="high_school", help="年级: high_school/undergraduate/graduate_exam")
    parser.add_argument("--nickname", default="学生", help="昵称")
    parser.add_argument("--persist", default="", help="画像持久化目录（如 data）")
    parser.add_argument("--no-self-update", action="store_true", help="禁用自我更新")
    args = parser.parse_args()

    _println(BANNER)

    # LLM
    if args.mock:
        llm = create_llm("mock")
    else:
        llm = create_llm(args.provider)
    mode = "真实 LLM" if (llm.available() and llm.name != "mock") else "离线 Mock"
    _println(f"[模型] {llm.name}（{mode}）")

    kb = KnowledgeBase()
    checker = SafetyChecker()
    paeg = PAEG(llm, kb, enable_self_update=not args.no_self_update)

    learner = LearnerProfile(
        id="cli_001",
        nickname=args.nickname,
        grade_level=args.grade,
        age=17 if args.grade == "high_school" else 20,
    )

    # 画像加载
    if args.persist:
        saved = load_profile(Path(args.persist) / "profiles.json", learner.id)
        if saved:
            learner.subjects_mastery = saved.get("subjects_mastery", {})
            learner.world_view_blend = saved.get("world_view_blend", learner.world_view_blend)
            _println(f"[画像] 已加载历史画像：{len(learner.subjects_mastery)} 个学科掌握度")

    # 单轮模式
    if args.subject and args.question:
        guard = checker.guard_question(args.question, learner)
        if guard:
            _println(f"[安全拦截] {guard['reason']}")
            _println(guard["suggestion"])
            sys.exit(1)
        run_teaching(paeg, learner, args.question, args.subject)
        if args.persist:
            save_profile(Path(args.persist) / "profiles.json", learner.id, {
                "nickname": learner.nickname,
                "grade_level": learner.grade_level,
                "age": learner.age,
                "cognitive_style": learner.cognitive_style,
                "subjects_mastery": learner.subjects_mastery,
                "world_view_blend": learner.world_view_blend,
                "updated_at": datetime.now().isoformat(),
            })
        sys.exit(0)

    # 交互模式
    _println(f"[学习者] {learner.nickname}（{learner.grade_level}，{learner.age} 岁）")
    interactive_loop(paeg, learner, kb, checker, args.persist)


if __name__ == "__main__":
    main()