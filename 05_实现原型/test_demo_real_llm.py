"""
PAEG v0.3 真实 LLM 接入版 Demo

使用 MockLLM（默认）或环境变量配置的真实 LLM：
  export ANTHROPIC_API_KEY=xxx     # 使用 Claude
  export OPENAI_API_KEY=xxx        # 使用 GPT-4o
  export DEEPSEEK_API_KEY=xxx      # 使用 DeepSeek

运行：
    python test_demo_real_llm.py
    python test_demo_real_llm.py --provider anthropic
    python test_demo_real_llm.py --provider deepseek
"""
from __future__ import annotations

import argparse
import os
import sys

from paeg import LearnerProfile, PAEG
from knowledge_base import KnowledgeBase
from llm_adapter import create_llm


def run_demo(paeg: PAEG, learner: LearnerProfile, subject: str, question: str) -> dict:
    """运行一个学科 demo。"""
    print(f"\n{'='*70}")
    print(f"Demo：{subject}")
    print(f"问题：{question}")
    print(f"学生：{learner.nickname} ({learner.grade_level})")
    print(f"{'='*70}")

    result = paeg.teach(learner, question, subject)

    summary = result["summary"]
    print(f"\n--- 总结 ---")
    print(f"  概念：{summary['concept']}")
    print(f"  平均分：{summary['avg_score']:.3f}")
    print(f"  步骤：{summary['steps_completed']}")
    print(f"  时长：{summary['duration_min']} min")
    print(f"  主导世界观：{summary['worldview_used']}")

    # v0.3 新增：显示真实 LLM 输出（首个呈现的前 150 字）
    if result["session"].history:
        first = result["session"].history[0]
        content = str(first.get("content", ""))[:150]
        print(f"  呈现预览：{content}...")

    return result


def main():
    parser = argparse.ArgumentParser(description="PAEG v0.3 真实 LLM Demo")
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "mock", "anthropic", "openai", "deepseek"])
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    print("PAEG v0.3 真实 LLM 接入 Demo")
    print("=" * 70)
    print(f"Provider: {args.provider}")
    if args.model:
        print(f"Model: {args.model}")

    try:
        llm = create_llm(args.provider, model=args.model)
        print(f"✓ LLM 初始化成功: {llm.name}")
    except Exception as e:
        print(f"✗ LLM 初始化失败：{e}")
        if args.provider != "mock":
            print("提示：使用 --provider mock 离线测试，或设置对应 API key 环境变量")
        sys.exit(1)

    # 检查真实 provider 是否可用（v0.5：create_llm 已自动发现 opencode auth.json）
    if args.provider != "mock" and not (llm.available() and llm.name != "mock"):
        print(f"✗ 未找到 {args.provider} 的可用凭据")
        print("  设置环境变量，或在 opencode auth.json 中配置；或使用 --provider mock")
        sys.exit(1)

    # 初始化 PAEG
    kb = KnowledgeBase()
    paeg = PAEG(llm, kb, enable_self_update=True, verbose=True)

    print(f"\n知识库统计：{kb.stats()}")

    # 测试学习者
    high_school_student = LearnerProfile(
        id="hs_001",
        nickname="小李",
        grade_level="high_school",
        age=17,
        cognitive_style="visual",
    )

    kaoyan_student = LearnerProfile(
        id="kg_001",
        nickname="小王",
        grade_level="graduate_exam",
        age=22,
        cognitive_style="reading",
        target_exam="kaoyan_math_i",
        specialty_target="计算机科学",
    )

    # ─── 3 个核心 demo（精简版，避免 token 浪费） ───
    demos = [
        (high_school_student, "physics", "什么是熵？"),
        (high_school_student, "ethics", "电车难题该拉开关吗？"),
        (kaoyan_student, "kaoyan_math", "极限的 ε-δ 定义是什么？"),
    ]

    total_tokens = 0
    for learner, subject, question in demos:
        result = run_demo(paeg, learner, subject, question)
        # 累计 token（如果可获取）
        if hasattr(paeg.model, 'last_response'):
            total_tokens += getattr(paeg.model.last_response, 'input_tokens', 0)
            total_tokens += getattr(paeg.model.last_response, 'output_tokens', 0)

    print(f"\n{'='*70}")
    print(f"v0.3 真实 LLM Demo 完成 ✓")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
