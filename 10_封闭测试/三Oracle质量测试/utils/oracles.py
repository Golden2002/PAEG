# -*- coding: utf-8 -*-
"""三 Oracle 评分器 —— LLM-as-judge 基类 + 教学流/倾诉/物料评分器。

设计（Oracle 方案）：
- 可插拔：每 Oracle 一个类，prompt 内嵌 rubric 锚点（1/3/5 分描述）
- LLM-as-judge：对产出物按维度评分 0-100，附证据引用
- 确定性叠加：复读检测（相似度）+ 一票否决（规则）作为 LLM 评分的补充
- 话题特异锚点：每个场景可配置自己的锚点（YAML 驱动）
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

API_URL = "https://api.deepseek.com/v1/chat/completions"
# 安全：密钥从环境变量读取（禁止硬编码；泄露的旧 key 已提示轮换）
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("PAEG_DEEPSEEK_API_KEY", "")


class LLMJudge:
    """LLM-as-judge 基类：按 rubric 评分 + 证据引用。"""

    def __init__(self, name: str, rubric: Dict[str, Any]):
        self.name = name
        self.rubric = rubric  # {dimension: {"weight": 0.25, "anchor_1": "...", "anchor_5": "..."}}

    def score(self, content: str, extra_context: str = "") -> Dict[str, Any]:
        """对产出物评分（0-100），返回维度分 + 总分 + 证据。"""
        try:
            import requests
            dims = self.rubric.get("dimensions", {})
            dim_desc = "\n".join(
                f"- {k}（权重{v.get('weight', 0.2)}）：1分={v.get('anchor_1', '')}；5分={v.get('anchor_5', '')}"
                for k, v in dims.items()
            )
            prompt = (
                f"你是教育质量评审专家。请按以下 rubric 对{self.name}评分。\n\n"
                f"【评分维度】\n{dim_desc}\n\n"
                f"【待评内容】\n{content[:3000]}\n\n"
                f"【附加上下文】\n{extra_context[:500]}\n\n"
                "请以 json 格式输出评分结果。输出结构："
                '{"scores": {"维度1": 85, "维度2": 70}, '
                '"total": 78, '
                '"evidence": {"维度1": "引用内容中的证据"}, '
                '"defects": [{"severity": "P0|P1|P2|P3", "desc": "缺陷描述", "suggestion": "建议"}]}'
            )
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是教育质量评审专家。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "max_tokens": 2000,
            }
            r = requests.post(API_URL, json=payload,
                              headers={"Authorization": f"Bearer {API_KEY}"}, timeout=90)
            r.raise_for_status()
            resp = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", resp, re.S)
            if not m:
                return {"error": "LLM 返回非 JSON", "total": 0}
            parsed = json.loads(m.group(0))
            # 加权总分（代码计算，不依赖 LLM 返回的 total——LLM 可能省略）
            total = 0.0
            wsum = 0.0
            for dim, w in dims.items():
                sc = parsed.get("scores", {}).get(dim)
                if isinstance(sc, (int, float)):
                    # LLM 常按 0-5 打分（rubric 锚点 1-5），映射到 0-100
                    sc100 = sc * 20 if sc <= 5 else sc
                    total += sc100 * w.get("weight", 0.2)
                    wsum += w.get("weight", 0.2)
            if wsum > 0:
                parsed["total"] = round(total / wsum, 1)
            else:
                parsed["total"] = 0.0
            parsed["judge"] = self.name
            return parsed
        except Exception as e:
            return {"error": str(e), "total": 0, "judge": self.name}


# ── Oracle 1：教学流评分 ──
ORACLE1_RUBRIC = {
    "dimensions": {
        "教学准确性": {"weight": 0.25,
                      "anchor_1": "有知识错误或表述模糊",
                      "anchor_5": "知识准确，术语规范，无科学性错误"},
        "耐心与情绪支持": {"weight": 0.20,
                         "anchor_1": "出现不耐烦、重复话术、否定学生",
                         "anchor_5": "持续耐心，换角度解释，鼓励学生"},
        "回应针对性": {"weight": 0.20,
                     "anchor_1": "回答笼统，未针对学生问题",
                     "anchor_5": "精准回应学生具体困惑"},
        "拐题处理": {"weight": 0.15,
                    "anchor_1": "粗暴打断或完全跑偏",
                    "anchor_5": "回应联想后自然拉回主线"},
        "节奏与深入": {"weight": 0.20,
                      "anchor_1": "该深入时重复基础，或该慢时讲太快",
                      "anchor_5": "根据学生反应调节节奏，及时深入或放缓"},
    },
}


class Oracle1Teaching(LLMJudge):
    """教学流质量评分（四类学生行为覆盖 + 耐心 + 准确性）。"""

    def __init__(self):
        super().__init__("教学流质量", ORACLE1_RUBRIC)

    def score_flow(self, turns: List[Dict[str, str]], topic: str) -> Dict[str, Any]:
        """对整个教学流评分（多轮对话）。"""
        dialog = "\n".join(
            f"学生: {t.get('student', '')}\n教师: {t.get('teacher', '')}"
            for t in turns
        )
        return self.score(dialog, f"话题：{topic}")


# ── Oracle 2：倾诉对话评分 ──
ORACLE2_RUBRIC = {
    "dimensions": {
        "共情准确性": {"weight": 0.20,
                      "anchor_1": "机械回复，无视情绪，或过度煽情",
                      "anchor_5": "准确识别情绪，共情自然"},
        "回应具体性": {"weight": 0.20,
                      "anchor_1": "泛泛而谈，套话多",
                      "anchor_5": "针对具体事件回应，不空洞"},
        "推进深度": {"weight": 0.25,
                    "anchor_1": "停留在表面，反复问同样问题",
                    "anchor_5": "逐步深入，帮助梳理，有方向"},
        "反重复多样性": {"weight": 0.20,
                        "anchor_1": "同一话术重复，多轮无新信息",
                        "anchor_5": "每轮有新角度或推进，语言多样"},
        "安全边界": {"weight": 0.15,
                    "anchor_1": "说教、评判、过度承诺、越界",
                    "anchor_5": "尊重、不评判，边界清晰"},
    },
}


class Oracle2Confiding(LLMJudge):
    """倾诉对话质量评分（不复读 + 共情 + 安全边界）。"""

    def __init__(self):
        super().__init__("倾诉对话质量", ORACLE2_RUBRIC)

    def score_dialog(self, turns: List[Dict[str, str]], theme: str,
                     repetition_rate: float = 0.0) -> Dict[str, Any]:
        """对倾诉长对话评分（含复读率惩罚）。"""
        dialog = "\n".join(
            f"学生: {t.get('student', '')}\n智能体: {t.get('agent', '')}"
            for t in turns
        )
        result = self.score(dialog, f"倾诉主题：{theme}")
        # 复读率惩罚：复读率 > 5% 扣分
        if repetition_rate > 0.05 and result.get("total"):
            penalty = min(20, int((repetition_rate - 0.05) * 200))
            result["total"] = max(0, result["total"] - penalty)
            result["repetition_rate"] = round(repetition_rate, 3)
            result["repetition_penalty"] = penalty
        return result


# ── Oracle 3：物料质量评分 ──
ORACLE3_RUBRIC = {
    "dimensions": {
        "内容准确性": {"weight": 0.25,
                      "anchor_1": "有知识错误或误导",
                      "anchor_5": "知识准确，术语规范，无科学性错误"},
        "内容详实度": {"weight": 0.25,
                      "anchor_1": "仅标题+提纲，缺解释和例子",
                      "anchor_5": "有实质解释、例子、数据，信息密度合适"},
        "视觉/结构质量": {"weight": 0.20,
                         "anchor_1": "排版混乱/结构缺失",
                         "anchor_5": "排版美观/结构完整，适用于课堂"},
        "教学适用性": {"weight": 0.30,
                      "anchor_1": "不适合课堂直接使用",
                      "anchor_5": "教师可直接使用，含导入/例题/练习/小结"},
    },
}


# §3.99 ⭐ manim 数学动画专属 rubric：评"生成代码质量"（非渲染视频——渲染是引擎问题）
ORACLE3_MANIM_RUBRIC = {
    "dimensions": {
        "详尽展示": {
            "weight": 0.25,
            "anchor_1": "代码仅少量元素，未覆盖脚本分镜（单场景/少步骤）",
            "anchor_5": "多场景/多步骤完整覆盖脚本，每步有明确视觉呈现（几何直觉/公式/变换过程）",
        },
        "脚本忠实度": {
            "weight": 0.25,
            "anchor_1": "代码与脚本 scenes 脱节，概念/视觉目标未实现",
            "anchor_5": "代码忠实实现 script.json 的每个 scene（concept/visual_goal/narration 对应）",
        },
        "视频代码结构": {
            "weight": 0.20,
            "anchor_1": "结构混乱（无 construct/类组织差/教学节奏缺失）",
            "anchor_5": "Scene 子类 + construct 清晰，wait/pause 教学节奏，动画分组有序",
        },
        "数学表达": {
            "weight": 0.15,
            "anchor_1": "数学公式缺失或错误（无 MathTex/公式符号错误）",
            "anchor_5": "MathTex 公式正确呈现，逐步展开/编号/对齐（LaTeX 符号保留）",
        },
        "可运行性": {
            "weight": 0.15,
            "anchor_1": "代码 AST 校验失败/无法运行",
            "anchor_5": "代码通过 AST 校验，import 合法，可被 manim 引擎渲染",
        },
    },
}


class Oracle3Material(LLMJudge):
    """备课物料质量评分（PPT/教学视频/数学视频/讲义通用 rubric）。"""

    def __init__(self, material_type: str):
        # §3.99 ⭐ manim 用代码质量 rubric（评生成代码，非渲染视频）
        _rubric = ORACLE3_MANIM_RUBRIC if material_type in ("math_video", "数学动画", "manim") else ORACLE3_RUBRIC
        super().__init__(f"物料质量-{material_type}", _rubric)
        self.material_type = material_type

    def score_material(self, material_text: str, topic: str,
                       visual_meta: str = "") -> Dict[str, Any]:
        """对物料内容评分（文本提取 + 视觉元数据）。"""
        ctx = f"话题：{topic}；物料类型：{self.material_type}；视觉元数据：{visual_meta}"
        return self.score(material_text, ctx)


if __name__ == "__main__":
    # 冒烟测试：三个评分器可实例化
    o1 = Oracle1Teaching()
    o2 = Oracle2Confiding()
    o3 = Oracle3Material("PPT")
    print("三 Oracle 评分器实例化 OK")
    print("Oracle1 维度:", list(o1.rubric["dimensions"].keys()))
    print("Oracle2 维度:", list(o2.rubric["dimensions"].keys()))
    print("Oracle3 维度:", list(o3.rubric["dimensions"].keys()))
