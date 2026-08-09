"""
PAEG 真实 LLM 增强的 Presenter（v0.3）

使用真实 LLM 重新生成讲解内容（当知识库没有直接匹配时）。
v0.3 流程：
  1. 先用知识库节点拼接（fallback）
  2. 如果有真实 LLM，用 LLM 基于节点信息 + tone system prompt 重新生成
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def llm_enhanced_present(model: Any, topic: str, node: Optional[Dict[str, Any]],
                          tone_info: Dict[str, Any], learner: Any) -> str:
    """使用 LLM 重新生成讲解内容。"""

    if not model or not hasattr(model, "generate"):
        # 无 LLM：返回空字符串（让 fallback 处理）
        return ""

    # 构造 prompt
    system_suffix = tone_info.get("system_suffix", "")
    tone_ratio = tone_info.get("ratio", {})

    system = (
        f"你是 PAEG 教育者智能体。{system_suffix}\n"
        f"当前主题主导世界观比例：{tone_ratio}\n"
        f"你的讲解必须基于以下事实，不能编造。"
    )

    if node:
        if "intuition" in node:
            user = (
                f"请用你自己的话重新讲解以下概念：\n\n"
                f"主题：{topic}\n"
                f"直觉理解：{node['intuition']}\n"
                f"严格定义：{node.get('formal_definition') or node.get('definition', '')}\n"
                f"学生认知风格：{learner.cognitive_style}\n"
                f"学生年级：{learner.grade_level}\n\n"
                f"要求：\n"
                f"1. 长度 100-300 字\n"
                f"2. 必须基于上述事实，不能编造\n"
                f"3. 体现你（{tone_info.get('tone')}）的语气\n"
                f"4. 适合该学生认知风格"
            )
        elif "core_question" in node:
            perspectives = "\n".join(
                f"- {k}: {v}" for k, v in node.get("tradition_perspectives", {}).items()
            )
            user = (
                f"请重新阐述以下问题：\n\n"
                f"问题：{node['core_question']}\n"
                f"已有视角：\n{perspectives}\n\n"
                f"要求：\n"
                f"1. 长度 100-300 字\n"
                f"2. 用你自己的话\n"
                f"3. 体现 {tone_info.get('tone')} 语气\n"
                f"4. 适合 {learner.grade_level} 学生"
            )
        else:
            user = f"请讲解：{topic}（{node.get('definition', '')}）"

    else:
        user = f"请简要介绍：{topic}"

    try:
        messages = [{"role": "user", "content": user}]
        resp = model.generate(messages, system=system, max_tokens=512)
        return resp.text if hasattr(resp, "text") else str(resp)
    except Exception as e:
        return f"[LLM 生成失败：{e}]"


# ─────────────────────────────────────
# 测试示例
# ─────────────────────────────────────


if __name__ == "__main__":
    from llm_adapter import create_llm
    from world_view import select_tone

    # 测试 mock
    llm = create_llm("mock")
    tone_info = select_tone("physics")
    fake_node = {
        "intuition": "想象一杯热水放凉：分子从有序运动变得混乱。",
        "formal_definition": "S = k·lnΩ",
        "definition": "熵是系统无序程度的度量。",
    }

    class FakeLearner:
        cognitive_style = "visual"
        grade_level = "high_school"

    content = llm_enhanced_present(llm, "熵", fake_node, tone_info, FakeLearner())
    print(f"LLM 增强呈现（mock）：\n{content}\n")

    # 检测真实 LLM
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("\n检测到 ANTHROPIC_API_KEY，使用真实 Claude...")
        real_llm = create_llm("anthropic")
        real_content = llm_enhanced_present(real_llm, "熵", fake_node, tone_info, FakeLearner())
        print(f"LLM 增强呈现（anthropic）：\n{real_content}")
