# -*- coding: utf-8 -*-
"""subject_inducers.py —— §3.107 ⭐ 学科×物料专属诱导提示词层

在 L1 启发式提示词（通用沉思）之下，按学科特点 + 物料特点增强诱导：
- 学科诱导（L2a）：数学重几何直觉/物理重实验类比/经济重机制权衡/语文重叙事语境...
- 物料诱导（L2b）：视频重分镜节奏/PPT 重 6×6/讲义重四块/Manim 重变换可视化

与 SUBJECT_STYLES（36 学科 persona/structure）协同——本模块补"诱导引导"，
SUBJECT_STYLES 提供"讲解风格"，material_prompts 提供"物料模板"。
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════
# 学科专属诱导（L2a）——按学科认知特点引导 LLM 的展示侧重
# ═══════════════════════════════════════════════════════════
SUBJECT_INDUCERS = {
    "math": "【数学诱导】重几何直觉与变换可视化：先让学习者'看见'图形/变换过程，再形式化；"
            "用动态例子（切线逼近/面积累积）建立直觉；关键公式必须给'为什么'而不只给'是什么'。",
    "physics": "【物理诱导】重现象→实验类比→原理：先呈现物理现象（生活场景），用实验/类比解释机制，"
               "再给公式含义；强调'这个定律在现实中的表现'。",
    "economics": "【经济诱导】重机制与权衡：先生活情境（如货币/价格），讲清背后的激励机制与权衡取舍，"
                 "不绝对化；用真实案例（政策/市场）支撑抽象概念。",
    "chinese": "【语文诱导】重文本细读与语境：先疏通文意，再分析手法/表达，落到情感主旨；"
               "兼顾应试要点与素养培养。",
    "chemistry": "【化学诱导】重现象→微观解释→方程：先呈现反应现象，用微观粒子模型解释，再给方程式；"
                 "强调生活应用与安全常识。",
    "biology": "【生物诱导】重生命现象→结构基础→机制：先具体生命现象，讲清结构-功能关系，"
               "联系人体/生态；'结构决定功能'贯穿。",
    "history": "【历史诱导】重叙事与因果链：先时代背景/事件经过，分析原因-结果-影响，"
               "用具体人物/事件让历史鲜活；培养历史思维（多视角/史料实证）。",
    "philosophy": "【哲学诱导】重概念辨析与论证：先厘清核心概念（是什么/不是什么），"
                  "展示论证结构（前提-推理-结论），用思想实验激发思辨。",
    "default": "【通用诱导】先建立直觉（例子/类比）→ 再形式化（定义/公式）→ 应用与边界；"
               "关键概念首次出现即定义，不跳步。",
}


# ═══════════════════════════════════════════════════════════
# 物料专属诱导（L2b）——按物料特点引导生成侧重
# ═══════════════════════════════════════════════════════════
MATERIAL_INDUCERS = {
    "manim": "【Manim 诱导】动画是'论证'不是演示：每段动画承载一个推理步骤；"
             "几何直觉先于公式；关键变换用 TransformMatchingTex 逐步推导；"
             "hook 提问开头 + recap 总结结尾；字幕管理生命周期（同位置先 FadeOut 再 FadeIn）。",
    "video": "【视频诱导】分镜节奏是灵魂：8-15s 每镜 + 旁白对应画面；"
             "引入（钩子）→ 主体（3-5 镜渐进）→ take-away 结尾；每镜画面与旁白严格对应。",
    "ppt": "【PPT 诱导】6×6 原则：单页 ≤6 条要点 + 有视觉焦点（图/表/公式）；"
           "封面→目录→3-5 页正文→小结→思考题；每页只讲一个主题，有例子支撑。",
    "handout": "【讲义诱导】四块结构：每节含【核心概念】【典型例题】【易错点】【小结】；"
               "例题给完整解题步骤；抽象概念配生活类比；内容准确可自学。",
    "mindmap": "【导图诱导】层级清晰：中心主题 + 3-5 一级分支 + 每分支 2-4 二级节点；"
               "每分支总结一句（summary）；逻辑关系准确。",
    "script": "【讲稿诱导】口语化 + 节奏：按教学顺序组织（引入→概念→例子→小结）；"
              "语句口语化可朗读；每段讲透一个点，衔接自然。",
}


def get_subject_inducer(subject: str) -> str:
    """按学科取诱导提示词（无匹配用 default）。"""
    return SUBJECT_INDUCERS.get(subject, SUBJECT_INDUCERS["default"])


def get_material_inducer(material_type: str) -> str:
    """按物料取诱导提示词（无匹配返回空）。"""
    return MATERIAL_INDUCERS.get(material_type, "")


def build_inducer_prompt(subject: str, material_type: str = "") -> str:
    """组合学科 + 物料诱导（L2a + L2b），拼在 L1 沉思引导后。"""
    parts = [get_subject_inducer(subject)]
    _m = get_material_inducer(material_type)
    if _m:
        parts.append(_m)
    return "\n".join(parts)


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("学科×物料诱导层就绪（§3.107）")
    print("学科诱导:", len(SUBJECT_INDUCERS), "种 | 物料诱导:", len(MATERIAL_INDUCERS), "种")
    print(build_inducer_prompt("math", "manim")[:80])
