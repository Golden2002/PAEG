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
import re
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
    # v0.16：AI 味形容词（"稳了"类过度自信断言）
    "稳了", "拿捏了", "妥了", "没跑了", "妥妥的", "稳稳的",
    "轻松拿下", "真的绝了", "绝绝子", "yyds", "YYDS", "狠狠拿捏",
    "非常棒", "棒极了", "太给力了",
    # AI 喜欢的高大上形容词
    "深刻", "全面", "系统", "本质", "深远", "独到",
    # v0.17：低劣网络用语（与 ai_taste_detector.AI_MARKERS 同步）
    "格局打开", "当场去世", "主打一个", "不懂的问我", "打通", "开摆", "懂的都懂", "亲们",
    "你并不孤单", "封顶", "纯路人", "高级感", "赚米", "就这就这", "摆烂王", "笑死我了",
    "稳如老狗", "吃瓜", "凡尔赛", "白给", "好家伙", "摸鱼", "拔草", "在许多情况下",
    "赛道", "上头", "最后", "爷青回", "画饼", "完全没问题", "漏斗", "翻车现场",
    "跪了", "牛批", "必入", "出金", "真的超赞", "本命", "击穿", "雪糕刺客",
    "碾压", "已老实", "冤大头", "奥利给", "冲分", "球球了", "退退退", "死磕",
    "狠狠共情", "催更", "草率了", "真的绝", "元宇宙", "陈独秀", "下头", "薅羊毛",
    "收割", "菜鸡", "古希腊掌管", "秒杀", "笑死", "绝活", "带飞", "降维打击",
    "原地去世", "神了", "链接放下面", "背锅侠", "蚌埠住了", "起飞", "爆冷", "扎心了老铁",
    "老实说", "尊嘟假嘟", "心智", "酸了", "嘎嘎", "吊打", "老铁", "长点心",
    "抓手", "钝感力", "满满正能量", "福利", "沉淀", "巨佬", "链路", "格局小了",
    "封神", "精神状态领先", "王者", "氛围感", "欧皇", "划走你就亏了", "完爆", "偷感拉满",
    "大冤种", "活久见", "上点心", "水灵灵地", "至关重要", "配享太庙", "买它", "班味儿",
    "王子请", "秒懂", "网抑云", "前排吃瓜", "上分", "搞起", "牛皮", "兄弟姐妹",
    "没毛病", "含金量还在上升", "偷感", "松弛感", "划水", "戏精", "冲冲冲", "塌房",
    "纯爱战神", "限定", "刺客", "背锅", "爆了", "风口", "恰柠檬", "哇噻",
    "这很难评", "太顶了", "炸了", "应援", "治愈到", "情绪价值", "脱粉", "智商税",
    "蹲一个", "拉满", "神操作", "甩锅侠", "标志着", "搭子", "甩锅", "卷起来",
    "打法", "大佬", "好嘞", "收到收到", "佛系", "不可否认的是", "笑不活了", "爆肝",
    "颜值担当", "假嘟", "平替", "出圈", "公主请", "种草", "断层", "鼠鼠我啊",
    "串联", "闭眼入", "其次", "共创", "我滴妈", "带偏", "手慢无", "偷感很重",
    "拆解", "圈粉", "嘴替", "属实是", "嘎嘎好", "根植于", "更有意思的是", "神仙打架",
    "卷不动", "直接给我冲", "特种兵式", "整活", "内卷", "共建", "抽卡", "解耦",
    "抄作业", "在某种程度上", "不可或缺", "狠狠爱住", "宝子", "肝帝", "首先", "绝了",
    "卷王", "协同", "码住", "本质地", "听我说谢谢你", "走起", "涨知识", "引爆",
    "一整个爱住", "服了你个老六", "欧气", "好滴", "踩雷", "红温", "小孩姐", "给力",
    "精神内耗", "命运的齿轮", "顶流", "稳了稳了", "黑马", "整破防", "绷不住了", "给我哭死",
    "神仙组合", "小趴菜", "跪求", "拉齐", "泰酷辣", "歪楼", "韭菜", "摆烂",
    "仪式感", "依托构思", "就完事了", "交学费", "青铜", "牛啊", "复盘", "拉胯",
    "太卷", "买买买", "躺赢", "反哺", "奠定基础", "很卷", "排位", "电子榨菜",
    "保底", "就这", "天花板", "非酋", "尊嘟", "剁手", "大神", "不长记性",
    "安排上", "吃瓜群众", "多巴胺", "班味", "打脸", "柠檬精", "草台班子", "打榜",
    "菜狗", "吃透", "治愈系", "复利", "出道", "孔乙己", "天秀", "爱豆",
    "那咋了", "小确丧", "路人缘", "哈基米", "破大防", "社死", "双向奔赴", "一整个震惊",
    "包装", "搞抽象", "接盘侠", "针不戳", "爆款", "绝对没问题", "履约", "意义重大",
    "家人们", "大意了", "小确幸", "迷惑行为", "小孩哥", "颗粒度", "墙头", "长记性",
    "家人们冲", "矩阵", "拉通", "骚操作", "你是懂", "狠狠", "氪金", "上车",
    "三连", "嘎嘎香", "哇塞", "稀碎", "梦幻联动", "集美", "对齐", "咸鱼",
    "割韭菜", "啵啵间", "破圈", "破防", "拿捏", "走点心", "联名", "老六",
    "求求了", "操作拉满", "爷青结", "控评", "辣眼睛", "透传", "给我笑死", "不断变化的格局",
    "带节奏", "翻车", "嘎嘎乱杀", "触达", "逆袭", "大受震撼", "接盘", "瞎眼",
    "你人还怪好的", "多巴胺穿搭", "我真的会谢", "整挺好", "啊对对对", "秀儿", "插眼", "倒逼",
    "牛啤", "硬控", "啪啪打脸", "哈哈哈", "显眼包", "躺平", "涨记性", "随缘",
    "盲盒", "啊这", "闭环",
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

        # v0.14：省略句/语法问题也触发改写
        has_ellipsis = len(self._check_ellipsis(text)) > 0

        # 无 AI 味、无省略句、且不算太长 → 直接返回
        if ai_prob < 0.4 and not has_ellipsis and len(text) < 400 \
                and not self.detect_ai_tells(text):
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
        # v0.14：语法完整性检查（省略句/无主句）
        omit_issues = self._check_ellipsis(text)
        if omit_issues:
            feedback_parts.append("存在省略句/无主句，需补全主谓宾：" + "；".join(omit_issues[:3]))
        hits = self.detect_ai_tells(text)
        if hits:
            feedback_parts.append(f"检测到这些套话：{', '.join(hits[:5])}")
        return "；".join(feedback_parts) if feedback_parts else "请保持原意，用更自然、朴素的语言表达。"

    def _check_ellipsis(self, text: str) -> list:
        """检测省略句/无主句（v0.14）。

        常见省略句式：句首直接是动词（"先看""再看""记住""注意"）、
        名词短语单独成句（"一句话记住：""关键在""核心是"）。
        按标点把文本切成"句"，再逐句检查。
        """
        issues = []
        # 动词开头的命令式省略（缺主语）
        verb_openers = ["先看", "再看", "先不谈", "记住", "注意", "想想", "试想",
                        "看一个", "想一下", "先想", "回忆", "算算", "练练"]
        # 按句号/分号/换行切分
        sentences = re.split(r'[。；\n]', text)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            # 去掉 markdown 和编号前缀
            clean = re.sub(r'^[#*\d\.\s\-—]+', '', sent)
            # "一句话记住：" 模式（无主句名词短语）
            if re.match(r'^(一句话)?记住[：:]', clean):
                issues.append(f"'{clean[:24]}…' 应改为'我们可以用一句话来记住：…'")
                continue
            # "关键在/核心是/重点在" 单独成句（缺完整结构）
            if re.match(r'^(关键|核心|重点)(在|是)', clean) and len(clean) < 30:
                issues.append(f"'{clean[:24]}…' 句子不完整，应补全为'这一点很关键：…'")
                continue
            # 动词开头命令句（缺主语）
            for vo in verb_openers:
                if clean.startswith(vo):
                    issues.append(f"'{clean[:24]}…' 是省略主语的命令句，应改为'我们{vo}…'")
                    break
        return issues[:5]

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
- **语法完整（v0.14）**：每一句都是完整句子（有主谓宾），不写省略句、无主句。
  ❌"一句话记住：…"→✅"我们可以用一句话来记住：…"
  ❌"先看一个现象"→✅"我们先来看一个现象。"
  ❌"再看它周围是否独一份"→✅"我们再来看它周围是否只有它这一条闭合轨道。"

## 你的任务
把下面的 AI 生成文本改写为薇依式的语言。要求：
1. 保留原意和事实，只改表达
2. 删掉 AI 痕迹（套话、廉价鼓励、空洞形容词、语气词堆砌）
3. 句子变短，用词变具体
4. **补全省略句**：所有省略主语/谓语的句子改成完整句式
5. **消除重复**：若文本内部有重复说明同一观点的句子，合并或删去冗余
6. 直接输出改写后的文本，不要解释，不要加"改写如下"之类的话"""
