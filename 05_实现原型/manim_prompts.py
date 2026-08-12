# -*- coding: utf-8 -*-
"""Manim 意图提示词库（v0.63 ⭐）

用户需求：确保用户用简单的话（如"画个抛物线""演示向量加法""看看导数"）
就能实现他们真正想要的效果——内置场景提示词，把"简单话"映射为带
教学叙事的精确 Manim 生成指令，而不是通用 prompt 瞎猜。

三层匹配：
1. _INTENT_PROMPTS：关键词 → 完整场景 prompt（LLM 生成专用，含叙事结构）
2. _TEMPLATE_FALLBACK：同关键词 → 模板（LLM 失败时兜底，已渲染验证）
3. 未命中 → 通用 prompt + 通用模板

使用：match_manim_intent(topic) -> {prompt, template_key, hint}
"""
from __future__ import annotations

# 通用教学叙事要求（所有场景 prompt 追加）
_NARRATIVE_TAIL = """
教学叙事要求：
- 用"标题 → 逐步创建 → 观察停留 → 关键结论标注"的结构
- 每个元素 Create 后至少 wait(1.5) 让用户看清
- run_time 2-4s 慢速演示（教学节奏，不是快闪）
- 涉及图形变换时展示"过程"而非一步到位（如切线沿曲线移动、扇形重组）
- 纯几何动画（避免 Text/MathTex 依赖；标题可用 Text 中文需 pango 支持，
  不稳定则改用纯几何 + 英文短标题）
"""

# 场景 → 生成 prompt（中文教学意图 → 精确动画指令）
_INTENT_PROMPTS = {
    "parabola": """生成 Manim 动画：二次函数抛物线的完整教学演示。
1. 绘制坐标轴（Axes），标注刻度
2. 逐步画出抛物线 y=ax²+bx+c（带参数的例子，如 y=x²-2x-1）
3. 用 Dot 标出顶点，DashedLine 画对称轴
4. 让一个点沿曲线缓慢移动（run_time 2s/步），展示不同位置
5. 观察停留后结束""",
    "derivative": """生成 Manim 动画：导数的几何意义——切线斜率的教学演示。
1. 坐标轴 + 一条函数曲线（如 y=x² 或 y=sin(x)）
2. 在曲线某点画切线（蓝色）
3. 让切点沿曲线移动，切线同步旋转（每步 run_time 1.2s + wait 0.8s，共 10+ 步）
4. 展示"割线 → 极限 → 切线"的逼近过程（可选）
5. 结束前保留 3s 观察""",
    "circle_area": """生成 Manim 动画：圆面积公式的推导——扇形切分重组。
1. 画圆 + 半径 r
2. 切成 8 个扇形（Sector，蓝/金交替填色）
3. 扇形交错重组成近似长方形（展示"化圆为方"思想）
4. 标注：底≈半周长 πr，高≈r → 面积 πr²
5. 重组过程慢速演示（每片 FadeIn 2s）""",
    "vector": """生成 Manim 动画：向量加法的教学演示。
1. NumberPlane 坐标网格
2. 画两个向量 v1、v2（不同颜色箭头）
3. 展示平行四边形法则：v1+v2 合成（金色箭头）
4. 先分别 Create（2s），再慢速画出合成向量（3s）
5. 用 DashedLine 展示平行四边形辅助线""",
    "transform": """生成 Manim 动画：几何变换的教学演示。
1. 画一个基础图形（正方形/三角形）
2. 慢速 Transform 到另一个图形（run_time 4s）
3. 再用 Rotate/Scale 展示旋转/缩放（run_time 3s）
4. 每次变换后 wait 2s 观察""",
    "function_graph": """生成 Manim 动画：函数图像的教学演示。
1. Axes 坐标轴
2. 绘制指定函数曲线（如 y=sin(x)、y=e^x、y=1/x）
3. 让一个点沿曲线移动并显示坐标（Dot + 可选轨迹）
4. 慢速绘制（Create run_time 3s），点移动每步 1.5s
5. 结束前 3s 观察""",
    "probability": """生成 Manim 动画：概率/统计的教学演示。
1. 绘制条形图或直方图（BarChart 或 Rectangle 序列）
2. 高亮目标柱（如最大概率处）
3. 可展示大量样本逼近概率的动画（Dot 累积）
4. 每个元素创建慢速（2s），高亮闪烁提示""",
}

# 关键词 → 场景（简单话匹配，中文优先）
_KEYWORDS = {
    "parabola": ["抛物线", "二次函数", "顶点", "quadratic", "parabola", "y=x²", "y=ax"],
    "derivative": ["导数", "切线", "斜率", "瞬时速度", "derivative", "tangent", "slope", "微分"],
    "circle_area": ["圆面积", "圆的面积", "圆形", "扇形", "circle", "πr", "pai r"],
    "vector": ["向量", "矢量", "平行四边形法则", "vector", "箭头"],
    "transform": ["变换", "旋转", "缩放", "平移", "对称", "transform", "rotate", "几何变换"],
    "function_graph": ["函数图像", "图像", "sin", "cos", "指数", "对数", "graph", "曲线"],
    "probability": ["概率", "统计", "直方图", "分布", "probability", "histogram", "正态"],
}


def match_manim_intent(topic: str) -> dict:
    """简单话 → 意图。返回 {prompt, template_key, hint}。

    prompt：场景专用 Manim 生成指令（LLM 用）
    template_key：模板 key（LLM 失败兜底）
    hint：给用户的说明文字（未命中时通用）
    """
    t = (topic or "").lower()
    for scene, kws in _KEYWORDS.items():
        if any(k in t for k in kws):
            return {
                "prompt": _INTENT_PROMPTS[scene] + _NARRATIVE_TAIL,
                "template_key": scene,
                "hint": f"识别到场景「{scene}」，已用专属动画指令生成",
            }
    return {
        "prompt": "生成 Manim 教学动画演示该主题。" + _NARRATIVE_TAIL,
        "template_key": "transform",
        "hint": "未匹配到内置场景，使用通用动画指令",
    }


def template_key_for(topic: str) -> str:
    """简单话 → 模板 key（不调 LLM 时的兜底选择）。"""
    return match_manim_intent(topic)["template_key"]
