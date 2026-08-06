"""
PAEG 语言优化 Agent（v0.12）

任务3：去除 AI 痕迹，让语言像真人、接近薇依。
方法：
1. 用薇依真实语料作为 few-shot 案例（weil_corpus.json）
2. 对模型输出进行"语言矫正"——识别并改写 AI 味浓的句子
3. 可作后处理管道：LLM 生成 → 语言优化 Agent 润色 → 输出

核心概念（来自薇依原文）：
- "爱是一种朝向"：语言要朝向真实，不朝向讨好
- 反对"自发、真诚、无偿"等空洞词：评价要具体
- 语言要"能承重"：每句有重量，不漂浮

用法：
    from language_refiner import LanguageRefiner
    refiner = LanguageRefiner(llm)
    refined = refiner.refine(text)   # 矫正文本
"""

from __future__ import annotations

import json
import os
from typing import Optional

from subagents import _safe_chat


# AI 痕迹检测：常见 AI 腔模式（用于本地预检）
AI_TELLS = [
    "总的来说", "综上所述", "值得注意的是", "不难发现", "众所周知",
    "让我们", "让我们一起", "在这个充满", "的海洋中", "点亮", "赋能",
    "拥抱", "精彩纷呈", "无限可能", "开启一段", "踏上", "之旅",
    "首先，", "其次，", "最后，", "总而言之",
    "好的呢", "对的呀", "没错没错", "拉一拉", "推一推",
    "嗯嗯", "啊哈", "啦~",
    "作为AI", "作为一个模型", "我理解你的感受", "我明白你的困惑",
    "这真是个", "真棒", "太棒了", "加油", "你一定可以",
]


class LanguageRefiner:
    """语言优化 Agent：用薇依语料矫正文本，去除 AI 痕迹。"""

    def __init__(self, llm, corpus_path: Optional[str] = None):
        self.llm = llm
        self.corpus = self._load_corpus(corpus_path)

    def _load_corpus(self, corpus_path: Optional[str] = None):
        """加载薇依语料。"""
        path = corpus_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'weil_corpus.json')
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def detect_ai_tells(self, text: str) -> list:
        """检测文本中的 AI 痕迹。返回命中的模式列表。"""
        hits = []
        for tell in AI_TELLS:
            if tell in text:
                hits.append(tell)
        return hits

    def refine(self, text: str, context: str = "", max_rounds: int = 2) -> str:
        """用薇依语料矫正文本（v0.13：Self-Refine 多轮）。

        流程（基于 Self-Refine 论文 NeurIPS 2023 + AI 味检测）：
        1. 检测 AI 味信号（句长变异/过渡词/三段清单/破折号）
        2. 若有 AI 味 → LLM 改写
        3. 复检信号，未达标且有轮次 → 再改写（最多 max_rounds 轮）
        """
        if not text or not text.strip():
            return text

        # 检测 AI 味信号
        try:
            from ai_taste_detector import detect_ai_taste
            signals = detect_ai_taste(text)
            ai_prob = signals.ai_likelihood
        except Exception:
            ai_prob = 1.0 if self.detect_ai_tells(text) else 0.2

        # 无 AI 味且不算太长 → 直接返回
        if ai_prob < 0.4 and len(text) < 400 and not self.detect_ai_tells(text):
            return text

        system = self._build_system()
        current = text
        for round_i in range(max_rounds):
            # 生成反馈（指出具体 AI 味）
            feedback = self._get_feedback(current, context)
            # 改写
            refined = _safe_chat(self.llm, system,
                                 self._build_user(current, context, feedback),
                                 max_tokens=800)
            if not refined or not refined.strip():
                break
            current = refined.strip()
            # 复检
            try:
                signals = detect_ai_taste(current)
                if signals.ai_likelihood < 0.4:
                    break
            except Exception:
                break

        return current

    def _get_feedback(self, text: str, context: str = "") -> str:
        """生成 AI 味反馈（用检测器信号）。"""
        feedback_parts = []
        try:
            from ai_taste_detector import detect_ai_taste
            s = detect_ai_taste(text)
            if s.burstiness_cv < 0.35:
                feedback_parts.append("句子长度太均匀，需要长短交替（短句制造节奏）")
            if s.marker_density > 1.5:
                feedback_parts.append("过渡词/套话过多，需要删除")
            if s.three_list_count > 0:
                feedback_parts.append("避免'三点/三步'式列举（薇依用二、四、七）")
            if s.em_dash_count > 3:
                feedback_parts.append("破折号过多，每段最多一个")
            if not feedback_parts and s.ai_likelihood >= 0.35:
                feedback_parts.append("整体偏'AI腔'，请用更朴素、具体的语言重写")
        except Exception:
            pass
        hits = self.detect_ai_tells(text)
        if hits:
            feedback_parts.append(f"检测到这些套话：{', '.join(hits[:5])}")
        return "；".join(feedback_parts) if feedback_parts else "请保持原意，用更自然、朴素的语言表达。"

    def _build_user(self, text: str, context: str = "", feedback: str = "") -> str:
        fb = f"\n【改写方向】{feedback}" if feedback else ""
        return f"""请改写下面的文本为薇依式的语言：{fb}
{('（上下文：' + context + '）\n') if context else ''}
【待改写文本】
{text[:1500]}"""

    def _build_system(self) -> str:
        """构建语言优化的 system prompt（含薇依语料 few-shot）。"""
        corpus_examples = "\n\n".join(
            f"【薇依原句 {i+1}】\n{c[:300]}" for i, c in enumerate(self.corpus[:6])
        )
        return f"""你是一位语言校正者，任务是让 AI 生成的文字像一位真实的人写的——像西蒙娜·薇依那样朴素、准确、有力量。

## 薇依的语言是怎样的（参考她的原句）
{corpus_examples}

## 薇依语言的核心特征
- 朴素：说具体的话，不用空泛的大词。"墨水在水里散开"胜过"生命的奥秘"。
- 准确：用词精确，不模糊。描述动作用自然的动词（观察/比较/拆开），不硬造"拉一拉"类怪动词短语。
- 有力量：每句话立得住——要么是事实，要么是观点，要么是问题。
- 温柔：不哄不捧，认真对待。不用"你真棒""加油"这类廉价鼓励。
- 不煽情：不用"让我们踏上""知识的海洋""点亮智慧"等套话；不堆语气词（嗯/啊/呢/吧/呀）。
- 循循善诱：像一位耐心老师，先让学生自己走一步。

## 你的任务
把下面的 AI 生成文本改写为薇依式的语言。要求：
1. 保留原意和事实，只改表达
2. 删掉 AI 痕迹（套话、廉价鼓励、空洞形容词、语气词堆砌）
3. 句子变短，用词变具体
4. 直接输出改写后的文本，不要解释，不要加"改写如下"之类的话"""
