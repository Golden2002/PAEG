"""stress_turn_eval.py — 语义压力测试（v0.21.7）

用大量相似问题 + 相关问题 + 混沌提问，多轮对话测试 5 个调 LLM 的 subagent，
专门暴露两大难题：**答非所问**（similar/relevance）与 **注意力丧失**
（attention/elaboration）。

## 与 chaos_turn_eval.py 的差异
- chaos_turn_eval：古怪提示词对抗（无意义字符串/反向指令/攻击性注入），检验 LLM 退化
- stress_turn_eval：**语义混淆对抗**（相似但不同的问题/递进延伸/多轮干扰后的回溯），
  检验 agent 架构的"理解/记忆/区分"三能力

## 4 个测试套件
1. **similar**：相似问题混淆——同 uid 连发"看着像但语义不同"的问题，测 agent
   能否区分并各自正确回答（distinguish_score + 侧重点关键词命中）
2. **elaboration**：相关问题上下文延伸——同 uid 连发递进问题，测 agent
   是否记住上文并正确推断终轮答案（continuity_score + 终轮正确性）
3. **attention**：多轮注意力——第 1 轮埋"金句"→ 中间 N 轮干扰 → 终轮追问
   金句内容，测 agent 是否还记得（recall + deep_recall）
4. **relevance**：LLM-as-judge 评分——把 (question, answer) 对发给真实 LLM
   打 0-1 分，按 mode 聚合，定位"答非所问"的具体案例

## 用法
```bash
python stress_turn_eval.py --suite all --uid stress_test_1
python stress_turn_eval.py --suite similar
python stress_turn_eval.py --suite relevance --mode teach
```
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

# 让脚本可独立运行
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = os.environ.get("PAEG_BASE", "http://localhost:5000")
VERSION = "v0.21.7"

# 阈值（低于即 FAIL）
DISTINGUISH_THRESHOLD = 0.50   # 相似问题平均区分度（1 - jaccard）
CONTINUITY_THRESHOLD = 0.70    # 上下文延伸延续率
RECALL_THRESHOLD = 0.60        # 多轮金句回忆率
RELEVANCE_THRESHOLD = 0.70     # LLM-judge 相关性


# ---------------------------------------------------------------------------
# 1. SIMILAR_GROUPS — 相似问题混淆（≥5 组，每组 4-6 个）
# ---------------------------------------------------------------------------
# 格式：(group_name, subject, [(question, [expected_keywords])])
# expected_keywords：每个问题应包含的"侧重点"关键词（≥1 命中即视为该题方向正确）
# 同时若另一个问题的关键词在自己的回答里也被完整命中 → 视为"答非所问"

SIMILAR_GROUPS: List[Tuple[str, str, List[Tuple[str, List[str]]]]] = [
    # 1. 导数组（数学/教学）
    ("derivative", "math", [
        ("什么是导数", ["定义", "极限", "变化率", "dy/dx", "f'(x)", "瞬时"]),
        ("导数的应用", ["应用", "例题", "场景", "最值", "速度", "优化"]),
        ("导数的几何意义", ["几何", "切线", "斜率", "图像", "曲线"]),
        ("导数与积分的关系", ["积分", "原函数", "反运算", "微积分基本定理"]),
        ("用导数求极值的步骤", ["步骤", "令", "f'(x)=0", "二阶", "判别"]),
    ]),

    # 2. 极限组（数学/教学）
    ("limit", "math", [
        ("什么是极限", ["定义", "趋近", "ε", "δ", "无限接近"]),
        ("极限的求法", ["方法", "代入", "约分", "洛必达", "夹逼"]),
        ("极限的几何意义", ["几何", "图像", "趋近", "坐标", "函数"]),
        ("极限存在的条件", ["条件", "存在", "左右极限", "相等"]),
        ("无穷小和极限的关系", ["无穷小", "趋近于零", "比值", "等价"]),
    ]),

    # 3. 矩阵组（数学/教学）
    ("matrix", "math", [
        ("什么是矩阵", ["定义", "数表", "行列", "方阵", "元素"]),
        ("矩阵的乘法", ["乘法", "行×列", "相乘", "维度", "不满足交换律"]),
        ("矩阵的逆", ["逆", "逆矩阵", "A⁻¹", "行列式", "单位矩阵"]),
        ("矩阵的特征值", ["特征值", "λ", "Av=λv", "特征向量"]),
        ("矩阵和行列式的区别", ["区别", "数", "数表", "行列式是数"]),
    ]),

    # 4. 概率组（数学/教学）
    ("probability", "math", [
        ("什么是概率", ["定义", "可能性", "0到1", "事件", "比值"]),
        ("条件概率", ["条件", "P(A|B)", "已知", "前提下"]),
        ("贝叶斯公式", ["贝叶斯", "P(B|A)", "后验", "先验"]),
        ("独立事件的概率", ["独立", "互不影响", "P(AB)=P(A)P(B)"]),
        ("期望和概率的关系", ["期望", "加权平均", "均值", "概率"]),
    ]),

    # 5. 哲学组（哲学/教学）
    ("philosophy", "philosophy", [
        ("什么是存在", ["存在", "being", "此在", "实体"]),
        ("什么是意识", ["意识", "知觉", "主观", "心智"]),
        ("存在和意识的关系", ["关系", "依赖", "先于", "物质"]),
        ("什么是自由意志", ["自由意志", "选择", "决定论", "自主"]),
        ("自由意志和决定论的区别", ["区别", "对立", "必然", "偶然"]),
    ]),

    # 6. 情绪组（情绪/affection）
    ("emotion", "general", [
        ("我最近压力很大", ["压力", "听", "在"]),
        ("是考试的事", ["考试", "听", "在"]),
        ("我是不是很没用", ["没用", "听", "否定", "在"]),
        ("那我该怎么办", ["怎么办", "方法", "步骤", "建议"]),
    ]),
]


# ---------------------------------------------------------------------------
# 2. ELABORATION_GROUPS — 相关问题上下文延伸（≥4 组，每组 4-6 轮）
# ---------------------------------------------------------------------------
# 格式：(group_name, mode, subject, [(question, expected_keywords), ...])
# expected_keywords：每轮回答应包含的关键词（接续上一轮）
# 最后一轮若含 final_keywords → 视为"终轮推断正确"

ELABORATION_GROUPS: List[Tuple[str, str, str, List[Tuple[str, List[str]]]]] = [
    # 1. 三角恒等式证明链（answer/math）
    ("trig_identity", "answer", "math", [
        ("证明 sin²x + cos²x = 1", ["sin", "cos", "恒等", "= 1"]),
        ("那 cos²x + sin²x 呢", ["一样", "对称", "= 1", "相同"]),
        ("如果换成 tan²x + 1 等于什么", ["tan", "= 1", "sec", "sec²"]),
        ("推导一下 tan²x + 1 = sec²x", ["sec²", "sin", "cos", "推导", "= 1"]),
    ]),

    # 2. 情绪递进（affection/general）
    ("emotion_progression", "affection", "general", [
        ("我最近压力大", ["压力", "听", "在"]),
        ("是考试的事", ["考试", "听", "压力"]),
        ("我是不是很没用", ["没用", "否定", "听", "不是"]),
        ("那我该怎么办", ["怎么办", "方法", "具体", "建议", "一点"]),
    ]),

    # 3. 概念递进（teach/math）
    ("derivative_concept", "teach", "math", [
        ("讲讲什么是导数", ["定义", "变化率", "极限"]),
        ("它的几何意义呢", ["切线", "斜率", "几何"]),
        ("物理上导数有什么用", ["速度", "加速度", "位移", "物理"]),
        ("那导数在经济学里呢", ["边际", "成本", "经济学", "应用"]),
    ]),

    # 4. 计算递进（answer/math）
    ("polynomial_integral", "answer", "math", [
        ("求 x² 的不定积分", ["x³/3", "C", "积分"]),
        ("那 x³ 呢", ["x⁴/4", "C", "积分"]),
        ("x 的 100 次方呢", ["x^101", "/101", "C"]),
        ("整理成一般规律 n 次方怎么求", ["n+1", "除以", "x^(n+1)", "规律"]),
    ]),
]


# ---------------------------------------------------------------------------
# 3. ATTENTION_PROBES — 多轮注意力（≥3 组）
# ---------------------------------------------------------------------------
# 格式：(probe_name, mode, subject, setup_question, setup_golden,
#        setup_golden_deeper, distractor_questions, recall_question,
#        recall_expected_keywords, recall_deeper_expected_keywords)
# setup_golden_deeper：可选的"衍生"金句（深一层召回，例如从"蓝绿色"→"#08A89E"）

ATTENTION_PROBES: List[Dict[str, Any]] = [
    {
        "name": "color_preference",
        "mode": "chat",
        "subject": "general",
        "setup_question": "顺便告诉你，我最喜欢的颜色是蓝绿色，对应的十六进制色值是 #08A89E",
        "setup_golden": ["蓝绿色", "08A89E", "#08A89E", "蓝绿"],
        "setup_golden_deeper": ["08A89E", "#08A89E", "蓝绿"],
        "distractor_questions": [
            "你觉得今天天气怎么样",
            "上海明天天气",
            "推荐一首好听的歌",
            "怎么炒西红柿鸡蛋",
            "王者荣耀怎么上分",
            "帮我写一份辞职信",
            "今晚吃什么",
        ],
        "recall_question": "我上次说我喜欢什么颜色",
        "recall_expected_keywords": ["蓝绿色", "蓝绿", "08A89E", "#08A89E", "青绿"],
        "recall_deeper_question": "那个颜色的十六进制色值是什么",
        "recall_deeper_expected_keywords": ["08A89E", "#08A89E"],
    },
    {
        "name": "pet_name",
        "mode": "chat",
        "subject": "general",
        "setup_question": "我养了一只猫，叫奶茶，是一只英短银渐层，今年 3 岁了",
        "setup_golden": ["奶茶", "猫", "英短", "银渐层", "3 岁", "三岁"],
        "setup_golden_deeper": ["银渐层", "英短", "奶茶"],
        "distractor_questions": [
            "上海明天天气",
            "今晚吃什么",
            "杭州房价多少",
            "推荐一只股票",
            "王者荣耀怎么上分",
            "怎么炒西红柿鸡蛋",
        ],
        "recall_question": "我养的猫叫什么名字",
        "recall_expected_keywords": ["奶茶"],
        "recall_deeper_question": "那只猫是什么品种",
        "recall_deeper_expected_keywords": ["英短", "银渐层"],
    },
    {
        "name": "exam_subject",
        "mode": "chat",
        "subject": "general",
        "setup_question": "我下周要参加物理竞赛初赛，考点是力学和电磁学，目标是省一等奖",
        "setup_golden": ["物理", "竞赛", "力学", "电磁学", "省一", "一等奖", "初赛"],
        "setup_golden_deeper": ["力学", "电磁学"],
        "distractor_questions": [
            "王者荣耀怎么上分",
            "推荐一只股票",
            "杭州房价多少",
            "今晚吃什么",
            "上海明天天气",
            "怎么炒西红柿鸡蛋",
            "帮我写一份辞职信",
        ],
        "recall_question": "我下周要参加什么考试",
        "recall_expected_keywords": ["物理", "竞赛"],
        "recall_deeper_question": "考试的目标是什么",
        "recall_deeper_expected_keywords": ["省一", "一等奖", "金奖"],
    },
]


# ---------------------------------------------------------------------------
# 4. RELEVANCE_JUDGE 评分系统提示词（LLM-as-judge）
# ---------------------------------------------------------------------------

RELEVANCE_JUDGE_SYSTEM = """你是 PAEG 教育智能体的相关性评分员。
你的任务：对一对 (问题, 回答) 打 0-1 分，表示回答与问题的相关程度。

**评分标准**：
- **1.0**：直接、准确、完整地回答了问题（无答非所问）
- **0.7**：回答了核心问题但不够完整/深度不足
- **0.4**：部分相关，但明显答非所问或主题偏题
- **0.0**：完全无关 / 拒答 / 胡说八道

**注意**：
1. 教学类问题答得长不算"答非所问"，重点看是否覆盖核心概念
2. 情绪类问题应包含倾听/陪伴信号（共情/在听），否则 0.4 以下
3. 只看相关性，不看风格/正确性

**输出格式**：只输出一个浮点数（0-1），不要任何解释。例如：0.8
"""


# ---------------------------------------------------------------------------
# 5. HTTP / SSE 工具（同 multi_turn_eval.py 模式）
# ---------------------------------------------------------------------------

def call_stream(text: str, mode: str, uid: str, subject: str = "math") -> str:
    """调用对应模式的端点，返回提取出的文本。失败返回 '[ERROR] xxx'。"""
    if mode == "teach":
        url = f"{BASE}/api/teach/stream"
        payload = {"concept": text, "subject": subject, "learner_id": uid,
                   "nickname": "测试", "grade_level": "high_school"}
    elif mode == "answer":
        url = f"{BASE}/api/answer"
        payload = {"question": text, "subject": subject, "learner_id": uid,
                   "nickname": "测试", "grade_level": "high_school"}
    elif mode == "affection":
        url = f"{BASE}/api/affection"
        payload = {"text": text, "learner_id": uid, "nickname": "测试",
                   "grade_level": "high_school"}
    elif mode == "chat":
        url = f"{BASE}/api/chat/stream"
        payload = {"text": text, "learner_id": uid, "nickname": "测试",
                   "grade_level": "high_school"}
    elif mode == "knowledge":
        url = f"{BASE}/api/knowledge"
        payload = {"text": text, "learner_id": uid, "nickname": "测试",
                   "grade_level": "high_school", "subject": "general"}
    elif mode == "method":
        url = f"{BASE}/api/method"
        payload = {"concept": text, "subject": subject, "learner_id": uid,
                   "nickname": "测试", "grade_level": "high_school"}
    else:
        return f"[ERROR] unknown mode: {mode}"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=150) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return f"[ERROR] URLError: {e.reason}"
    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {str(e)[:80]}"

    # 解析（兼容 JSON 和 SSE）
    if raw.strip().startswith("{"):
        try:
            body = json.loads(raw)
            if body.get("answer"):
                return body["answer"]
            pres = body.get("presentations", [])
            return " ".join(p.get("content", "") for p in pres) or raw[:300]
        except Exception:
            return raw[:300]

    # SSE
    texts: List[str] = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                obj = json.loads(line[5:].strip())
                if isinstance(obj, dict):
                    if "text" in obj:
                        texts.append(str(obj["text"]))
                    elif "content" in obj:
                        texts.append(str(obj["content"]))
            except Exception:
                pass
    return "".join(texts) or raw[:300]


def _safe_chat(llm: Any, system: str, user: str) -> str:
    """调真实 LLM：优先用 llm_adapter 创建的真实 LLM（不走教育 agent 路由）。

    失败返回空串（调用方负责容错）。
    """
    # 路径 1：llm 对象有 chat() 方法（llm_adapter.AdapterLLM）
    if llm is not None and hasattr(llm, "chat"):
        try:
            return llm.chat(system=system, messages=[{"role": "user", "content": user}],
                             max_tokens=200, temperature=0.2)
        except Exception:
            pass
    return ""


def _parse_score(text: str) -> float:
    """从 LLM 输出里抠出第一个浮点数。失败返回 0.5（中性）。"""
    if not text:
        return 0.5
    m = re.search(r"([01]?\.\d+|[01])", text)
    if m:
        try:
            v = float(m.group(1))
            return max(0.0, min(1.0, v))
        except Exception:
            pass
    return 0.5


# ---------------------------------------------------------------------------
# 6. 文本相似度（jieba 不可用 → 字符 bigram + 中文词袋混合）
# ---------------------------------------------------------------------------

# 中文停词（精简）
_CN_STOP = {
    "的", "了", "是", "在", "我", "你", "他", "她", "它", "们",
    "和", "与", "或", "但", "而", "所", "以", "为", "因", "由",
    "这", "那", "这个", "那个", "什么", "怎么", "为什么", "怎样",
    "如何", "可以", "可能", "应该", "就是", "还有", "一个", "一些",
    "也", "都", "就", "才", "已", "正在", "吧", "呢", "啊", "哦",
    "嗯", "嗯嗯", "哈哈", "啊哈", "请问", "请", "我们", "你们",
    "他们", "自己", "现在", "之后", "之前", "然后", "其实", "大概",
    "比较", "非常", "特别", "更", "最", "很", "挺", "蛮",
    "什么", "哪", "里", "怎样", "何", "该",
}


def _tokenize_cn(text: str) -> List[str]:
    """中文分词（无 jieba）：连续中文字符 + 单字 + ASCII token。"""
    if not text:
        return []
    # 先抽 ASCII token
    ascii_tokens = re.findall(r"[A-Za-z0-9+#_]+", text)
    # 中文：按 2-4 字窗口切
    cn_tokens = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
    # 单字（过滤停词）
    single_cn = [c for c in text if "\u4e00" <= c <= "\u9fff" and c not in _CN_STOP]
    return ascii_tokens + cn_tokens + single_cn


def _jaccard(a: str, b: str) -> float:
    """Jaccard 相似度（基于 token 集合）。"""
    ta = set(_tokenize_cn(a))
    tb = set(_tokenize_cn(b))
    if not ta and not tb:
        return 0.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _has_any(text: str, keywords: List[str]) -> int:
    """返回 keywords 中命中的数量。"""
    return sum(1 for k in keywords if k and k in text)


def _extract_cn_keywords(text: str, n: int = 3) -> List[str]:
    """提取中文核心实体词（复用 multi_turn_eval 风格）。"""
    words = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
    stop = {"我最近", "就是", "那个", "一下", "这个", "什么", "怎么", "可以",
            "然后", "现在", "最近", "一个", "我们", "你们", "他们",
            "我是不是", "是不是", "那一个", "考试的事"}
    core: List[str] = []
    for w in words:
        if w in stop or w.startswith(("我", "你", "这", "那", "就", "是")):
            continue
        if w not in core:
            core.append(w)
    return core[:n]


# ---------------------------------------------------------------------------
# 7. run_similar — 相似问题混淆
# ---------------------------------------------------------------------------

def run_similar(uid: str) -> Dict[str, Any]:
    """每组问题同 uid 连续 POST，收集回答，算 distinguish_score + 侧重点关键词。"""
    result = {"groups": {}, "summary": {}}
    all_distinguish: List[float] = []
    all_keyword_hits: List[float] = []
    failures: List[Dict[str, Any]] = []

    for group_name, subject, items in SIMILAR_GROUPS:
        group_uid = f"{uid}_sim_{group_name}"
        answers: List[Dict[str, Any]] = []
        for i, (q, keywords) in enumerate(items):
            # 教学用 teach，情绪用 affection
            mode = "affection" if group_name == "emotion" else "teach"
            reply = call_stream(q, mode, group_uid, subject)
            hit = _has_any(reply, keywords)
            total = len(keywords)
            answers.append({
                "i": i + 1, "question": q, "keywords": keywords,
                "reply": reply[:200].replace("\n", " "),
                "reply_len": len(reply),
                "keyword_hits": hit, "keyword_total": total,
                "keyword_hit_rate": round(hit / total, 3) if total else 0.0,
                "expected_keywords": keywords,
            })

        # 两两算 Jaccard（不含错误回复）
        clean = [a["reply"] for a in answers if not a["reply"].startswith("[ERROR]")]
        pairs: List[float] = []
        for i in range(len(clean)):
            for j in range(i + 1, len(clean)):
                pairs.append(_jaccard(clean[i], clean[j]))
        avg_sim = sum(pairs) / len(pairs) if pairs else 0.0
        distinguish = round(1.0 - avg_sim, 4)
        avg_kw_hit = sum(a["keyword_hit_rate"] for a in answers) / len(answers) if answers else 0.0
        all_distinguish.append(distinguish)
        all_keyword_hits.append(avg_kw_hit)
        group_result = {
            "group": group_name, "subject": subject, "n_questions": len(items),
            "distinguish_score": distinguish,
            "avg_similarity": round(avg_sim, 4),
            "avg_keyword_hit_rate": round(avg_kw_hit, 4),
            "rounds": answers,
            "pass": distinguish >= DISTINGUISH_THRESHOLD,
        }
        # 记录失败案例
        if distinguish < DISTINGUISH_THRESHOLD:
            failures.append({
                "dimension": "similar",
                "group": group_name,
                "distinguish_score": distinguish,
                "threshold": DISTINGUISH_THRESHOLD,
                "reason": f"组内平均相似度 {round(avg_sim,3)} 过高 → 区分度不足",
                "evidence": [(a["question"][:30], a["reply"][:80]) for a in answers[:3]],
            })
        if avg_kw_hit < 0.5:
            failures.append({
                "dimension": "similar_keyword",
                "group": group_name,
                "kw_hit_rate": round(avg_kw_hit, 3),
                "reason": "≥50% 题目未命中其侧重点关键词",
                "evidence": [(a["question"][:30], a["reply"][:80], f"hit={a['keyword_hits']}/{a['keyword_total']}")
                              for a in answers if a["keyword_hits"] == 0][:3],
            })
        result["groups"][group_name] = group_result

    overall_dist = sum(all_distinguish) / len(all_distinguish) if all_distinguish else 0.0
    overall_kw = sum(all_keyword_hits) / len(all_keyword_hits) if all_keyword_hits else 0.0
    result["summary"] = {
        "groups_total": len(SIMILAR_GROUPS),
        "avg_distinguish_score": round(overall_dist, 4),
        "avg_keyword_hit_rate": round(overall_kw, 4),
        "failures": failures,
        "verdict": "PASS" if overall_dist >= DISTINGUISH_THRESHOLD and overall_kw >= 0.5 else "FAIL",
    }
    return result


# ---------------------------------------------------------------------------
# 8. run_elaboration — 相关问题上下文延伸
# ---------------------------------------------------------------------------

def run_elaboration(uid: str) -> Dict[str, Any]:
    """每组递进问题连续 POST：每轮延续性 + 终轮正确性。"""
    result = {"groups": {}, "summary": {}}
    all_continuity: List[float] = []
    all_final_correct: List[bool] = []
    failures: List[Dict[str, Any]] = []

    for group_name, mode, subject, items in ELABORATION_GROUPS:
        group_uid = f"{uid}_ela_{group_name}"
        rounds: List[Dict[str, Any]] = []
        prev_keywords: List[str] = []
        continuity_scores: List[float] = []

        for i, (q, keywords) in enumerate(items):
            reply = call_stream(q, mode, group_uid, subject)
            # 本轮关键词命中
            kw_hit = _has_any(reply, keywords)
            kw_total = len(keywords)
            kw_rate = kw_hit / kw_total if kw_total else 0.0

            # continuity_score：本轮是否含上轮核心实体
            if i > 0 and prev_keywords:
                carry = _has_any(reply, prev_keywords)
                # 至少命中 1 个核心实体 → 1.0；否则看是否回应了新关键词
                if carry >= 1:
                    cont_score = 1.0
                elif kw_rate >= 0.5:
                    cont_score = 0.6  # 回应了但没提上轮实体
                else:
                    cont_score = 0.2  # 脱节
            else:
                cont_score = 1.0  # 首轮无上轮
            continuity_scores.append(cont_score)

            # 提取本轮核心实体供下轮
            extracted = _extract_cn_keywords(reply + " " + q, n=4)
            # 优先用题目里的名词
            extracted_from_q = _extract_cn_keywords(q, n=4)
            merged = extracted_from_q + [k for k in extracted if k not in extracted_from_q]
            prev_keywords = merged[:4]

            rounds.append({
                "i": i + 1, "question": q, "keywords": keywords,
                "reply": reply[:200].replace("\n", " "),
                "reply_len": len(reply),
                "keyword_hits": kw_hit, "keyword_total": kw_total,
                "keyword_hit_rate": round(kw_rate, 3),
                "continuity_score": round(cont_score, 3),
                "is_last": (i == len(items) - 1),
            })

        # 终轮正确性
        last_round = rounds[-1] if rounds else None
        # 最后一轮必须含至少 1 个期望关键词
        if last_round:
            final_correct = last_round["keyword_hits"] >= 1
        else:
            final_correct = False

        all_final_correct.append(final_correct)
        avg_cont = sum(continuity_scores) / len(continuity_scores) if continuity_scores else 0.0
        all_continuity.append(avg_cont)

        result["groups"][group_name] = {
            "group": group_name, "mode": mode, "subject": subject,
            "n_rounds": len(items),
            "avg_continuity": round(avg_cont, 4),
            "final_correct": final_correct,
            "rounds": rounds,
            "pass": avg_cont >= CONTINUITY_THRESHOLD and final_correct,
        }

        if avg_cont < CONTINUITY_THRESHOLD:
            failures.append({
                "dimension": "elaboration_continuity",
                "group": group_name,
                "avg_continuity": round(avg_cont, 3),
                "threshold": CONTINUITY_THRESHOLD,
                "reason": "上下文延续率不足",
                "evidence": [(r["question"][:30], r["reply"][:80], f"cont={r['continuity_score']}")
                              for r in rounds if r["continuity_score"] < 0.7][:3],
            })
        if not final_correct:
            failures.append({
                "dimension": "elaboration_final",
                "group": group_name,
                "reason": "终轮未含期望关键词（推理失败）",
                "evidence": [
                    (rounds[-1]["question"][:30], rounds[-1]["reply"][:120],
                     f"hit={rounds[-1]['keyword_hits']}/{rounds[-1]['keyword_total']}")
                ] if rounds else [],
            })

    overall_cont = sum(all_continuity) / len(all_continuity) if all_continuity else 0.0
    final_correct_rate = sum(all_final_correct) / len(all_final_correct) if all_final_correct else 0.0
    result["summary"] = {
        "groups_total": len(ELABORATION_GROUPS),
        "avg_continuity": round(overall_cont, 4),
        "final_correct_rate": round(final_correct_rate, 4),
        "failures": failures,
        "verdict": "PASS" if overall_cont >= CONTINUITY_THRESHOLD and final_correct_rate >= 0.75 else "FAIL",
    }
    return result


# ---------------------------------------------------------------------------
# 9. run_attention — 多轮注意力（金句埋入 → 干扰 → 追问）
# ---------------------------------------------------------------------------

def run_attention(uid: str) -> Dict[str, Any]:
    """埋金句 → 干扰 → 追问金句 → 追问衍生信息。"""
    result = {"probes": {}, "summary": {}}
    all_recall: List[float] = []
    all_deep_recall: List[float] = []
    failures: List[Dict[str, Any]] = []

    for probe in ATTENTION_PROBES:
        probe_uid = f"{uid}_att_{probe['name']}"
        # 1) 埋金句
        setup_reply = call_stream(probe["setup_question"], probe["mode"], probe_uid,
                                  probe["subject"])
        setup_hit = _has_any(setup_reply, probe["setup_golden"])

        # 2) 干扰轮
        distractor_replies: List[str] = []
        for dq in probe["distractor_questions"]:
            dr = call_stream(dq, probe["mode"], probe_uid, probe["subject"])
            distractor_replies.append(dr[:60])
            time.sleep(0.2)

        # 3) 追问金句
        recall_reply = call_stream(probe["recall_question"], probe["mode"], probe_uid,
                                   probe["subject"])
        recall_hit = _has_any(recall_reply, probe["recall_expected_keywords"])

        # 4) 追问衍生
        deep_reply = call_stream(probe["recall_deeper_question"], probe["mode"],
                                 probe_uid, probe["subject"])
        deep_hit = _has_any(deep_reply, probe["recall_deeper_expected_keywords"])

        recall_rate = recall_hit / max(1, len(probe["recall_expected_keywords"]))
        deep_rate = deep_hit / max(1, len(probe["recall_deeper_expected_keywords"]))
        all_recall.append(recall_rate)
        all_deep_recall.append(deep_rate)

        probe_pass = recall_rate >= RECALL_THRESHOLD
        result["probes"][probe["name"]] = {
            "probe": probe["name"],
            "setup_question": probe["setup_question"],
            "setup_reply": setup_reply[:160].replace("\n", " "),
            "setup_golden_hit": setup_hit,
            "setup_golden_total": len(probe["setup_golden"]),
            "n_distractors": len(probe["distractor_questions"]),
            "recall_question": probe["recall_question"],
            "recall_reply": recall_reply[:200].replace("\n", " "),
            "recall_hits": recall_hit,
            "recall_total": len(probe["recall_expected_keywords"]),
            "recall_rate": round(recall_rate, 4),
            "recall_deeper_question": probe["recall_deeper_question"],
            "recall_deeper_reply": deep_reply[:200].replace("\n", " "),
            "recall_deeper_hits": deep_hit,
            "recall_deeper_total": len(probe["recall_deeper_expected_keywords"]),
            "recall_deeper_rate": round(deep_rate, 4),
            "pass": probe_pass,
        }
        if not probe_pass:
            failures.append({
                "dimension": "attention",
                "probe": probe["name"],
                "recall_rate": round(recall_rate, 3),
                "threshold": RECALL_THRESHOLD,
                "reason": f"经历 {len(probe['distractor_questions'])} 轮干扰后召回率不足",
                "evidence": [
                    ("金句埋设", probe["setup_question"][:60]),
                    ("金句内容", probe["setup_golden"][:3]),
                    ("追问", probe["recall_question"]),
                    ("回答", recall_reply[:160].replace("\n", " ")),
                ],
            })
        if deep_rate < 0.5 and probe_pass:
            failures.append({
                "dimension": "attention_deep",
                "probe": probe["name"],
                "deep_rate": round(deep_rate, 3),
                "reason": "深一层召回失败（衍生信息丢失）",
                "evidence": [
                    ("追问", probe["recall_deeper_question"]),
                    ("回答", deep_reply[:160].replace("\n", " ")),
                ],
            })

    overall_recall = sum(all_recall) / len(all_recall) if all_recall else 0.0
    overall_deep = sum(all_deep_recall) / len(all_deep_recall) if all_deep_recall else 0.0
    result["summary"] = {
        "probes_total": len(ATTENTION_PROBES),
        "avg_recall": round(overall_recall, 4),
        "avg_deep_recall": round(overall_deep, 4),
        "failures": failures,
        "verdict": "PASS" if overall_recall >= RECALL_THRESHOLD else "FAIL",
    }
    return result


# ---------------------------------------------------------------------------
# 10. run_relevance — LLM-as-judge 评分
# ---------------------------------------------------------------------------

# 收集 (mode, question, answer) 样本（≥10 条）
RELEVANCE_SAMPLES: List[Tuple[str, str, str]] = [
    ("teach", "什么是导数", "math"),
    ("teach", "导数的几何意义", "math"),
    ("teach", "讲讲什么是极限", "math"),
    ("answer", "求 x² 的不定积分", "math"),
    ("answer", "证明 sin²x + cos²x = 1", "math"),
    ("answer", "矩阵的特征值是什么", "math"),
    ("affection", "我最近压力很大", "general"),
    ("affection", "我是不是很没用", "general"),
    ("chat", "顺便告诉你，我最喜欢的颜色是蓝绿色", "general"),
    ("chat", "我养了一只猫，叫奶茶", "general"),
    ("knowledge", "什么是存在", "philosophy"),
    ("method", "怎么学数学", "math"),
]


def run_relevance(uid: str, modes: List[str]) -> Dict[str, Any]:
    """收集样本并让真实 LLM 打分（LLM-as-judge）。"""
    result = {"samples": [], "by_mode": {}, "low_cases": [], "summary": {}}
    chosen_modes = set(modes) if modes else {"teach", "answer", "affection", "chat"}
    # 准备样本
    samples: List[Tuple[str, str, str, str]] = []  # (mode, subject, question, answer)
    for mode, q, subject in RELEVANCE_SAMPLES:
        if mode in chosen_modes:
            r_uid = f"{uid}_rel_{mode}_{abs(hash(q)) % 100000}"
            ans = call_stream(q, mode, r_uid, subject)
            samples.append((mode, subject, q, ans))

    # 优先用 import 的真实 LLM（如果有）
    llm: Optional[Any] = None
    try:
        import llm_adapter  # type: ignore
        llm = llm_adapter.create_llm("auto")
    except Exception:
        llm = None

    by_mode_scores: Dict[str, List[float]] = {}
    scored: List[Dict[str, Any]] = []

    for mode, subject, q, ans in samples:
        user_msg = f"问题：{q}\n\n回答：{ans[:600]}"
        judge_text = _safe_chat(llm, RELEVANCE_JUDGE_SYSTEM, user_msg)
        if not judge_text:
            judge_text = "0.5"  # 评分失败兜底
        score = _parse_score(judge_text)
        by_mode_scores.setdefault(mode, []).append(score)
        item = {
            "mode": mode, "subject": subject, "question": q,
            "answer_excerpt": ans[:120].replace("\n", " "),
            "answer_len": len(ans),
            "judge_raw": judge_text[:80],
            "relevance_score": score,
        }
        scored.append(item)
        result["samples"].append(item)
        if score < RELEVANCE_THRESHOLD:
            result["low_cases"].append({
                "mode": mode, "question": q,
                "answer_excerpt": ans[:200].replace("\n", " "),
                "relevance_score": score,
                "judge_raw": judge_text[:100],
            })

    # 聚合
    for mode, scores in by_mode_scores.items():
        result["by_mode"][mode] = {
            "n": len(scores),
            "avg_relevance": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "min_relevance": round(min(scores), 4) if scores else 0.0,
            "max_relevance": round(max(scores), 4) if scores else 0.0,
            "pass": (sum(scores) / len(scores) >= RELEVANCE_THRESHOLD) if scores else False,
        }

    all_scores = [s for scores in by_mode_scores.values() for s in scores]
    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0
    n_pass = sum(1 for s in all_scores if s >= RELEVANCE_THRESHOLD)
    pass_rate = n_pass / len(all_scores) if all_scores else 0.0
    result["summary"] = {
        "samples_total": len(samples),
        "overall_avg_relevance": round(overall, 4),
        "pass_rate": round(pass_rate, 4),
        "by_mode_avg": {m: round(sum(s) / len(s), 3) if s else 0.0
                         for m, s in by_mode_scores.items()},
        "verdict": "PASS" if overall >= RELEVANCE_THRESHOLD else "FAIL",
        "judge_backend": "llm_adapter" if llm is not None else "fallback_0.5",
    }
    return result


# ---------------------------------------------------------------------------
# 11. CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="stress_turn_eval — 语义压力测试 5 个 subagent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python stress_turn_eval.py --suite all --uid stress_test_1
  python stress_turn_eval.py --suite similar
  python stress_turn_eval.py --suite relevance --mode teach
        """,
    )
    parser.add_argument("--suite", default="all",
                        choices=["all", "similar", "elaboration", "attention", "relevance"],
                        help="测哪个套件（默认 all）")
    parser.add_argument("--uid", default=None,
                        help="测试用 uid 前缀（默认 stress_<ts>）")
    parser.add_argument("--report", default="stress_report.json",
                        help="报告 JSON 输出路径")
    parser.add_argument("--mode", default="all",
                        help="relevance 套件限定 mode（teach/answer/affection/chat/all，默认 all）")
    parser.add_argument("--base", default=None,
                        help="PAEG 基础 URL（默认 http://localhost:5000）")
    args = parser.parse_args()

    global BASE
    if args.base:
        BASE = args.base

    uid = args.uid or f"stress_{int(time.time())}"
    print(f"[stress_turn_eval] version={VERSION} suite={args.suite} uid={uid} base={BASE}",
          file=sys.stderr)

    suite_results: Dict[str, Any] = {}
    t0 = time.time()

    suites = ["similar", "elaboration", "attention", "relevance"] if args.suite == "all" else [args.suite]
    for s in suites:
        print(f"[stress_turn_eval] running suite={s} ...", file=sys.stderr)
        ts = time.time()
        try:
            if s == "similar":
                suite_results[s] = run_similar(uid)
            elif s == "elaboration":
                suite_results[s] = run_elaboration(uid)
            elif s == "attention":
                suite_results[s] = run_attention(uid)
            elif s == "relevance":
                modes = ["teach", "answer", "affection", "chat"] if args.mode == "all" else [args.mode]
                suite_results[s] = run_relevance(uid, modes)
        except Exception as e:
            import traceback
            suite_results[s] = {
                "fatal_error": repr(e),
                "traceback": traceback.format_exc(limit=4),
            }
        elapsed = round(time.time() - ts, 2)
        print(f"[stress_turn_eval] suite={s} done in {elapsed}s", file=sys.stderr)

    # 汇总
    verdicts = {}
    by_dimension: Dict[str, float] = {}
    for s, r in suite_results.items():
        if "summary" not in r:
            verdicts[s] = "ERROR"
            continue
        v = r["summary"].get("verdict", "UNKNOWN")
        verdicts[s] = v
        if s == "similar":
            by_dimension["distinguish"] = r["summary"].get("avg_distinguish_score", 0.0)
            by_dimension["similar_keyword_hit"] = r["summary"].get("avg_keyword_hit_rate", 0.0)
        elif s == "elaboration":
            by_dimension["continuity"] = r["summary"].get("avg_continuity", 0.0)
            by_dimension["elaboration_final_correct"] = r["summary"].get("final_correct_rate", 0.0)
        elif s == "attention":
            by_dimension["recall"] = r["summary"].get("avg_recall", 0.0)
            by_dimension["deep_recall"] = r["summary"].get("avg_deep_recall", 0.0)
        elif s == "relevance":
            by_dimension["relevance"] = r["summary"].get("overall_avg_relevance", 0.0)

    # 收集所有 FAIL 案例
    all_failures: List[Dict[str, Any]] = []
    for s in ["similar", "elaboration", "attention"]:
        if s in suite_results and "summary" in suite_results[s]:
            for f in suite_results[s]["summary"].get("failures", []):
                f["suite"] = s
                all_failures.append(f)
    for lc in suite_results.get("relevance", {}).get("low_cases", []):
        all_failures.append({
            "suite": "relevance",
            "dimension": "relevance_low",
            "question": lc["question"],
            "answer_excerpt": lc["answer_excerpt"],
            "relevance_score": lc["relevance_score"],
            "reason": f"LLM-judge 评分 {lc['relevance_score']} 低于阈值 {RELEVANCE_THRESHOLD}",
        })

    n_pass = sum(1 for v in verdicts.values() if v == "PASS")
    summary = {
        "version": VERSION,
        "config": {
            "suite": args.suite,
            "uid": uid,
            "base": BASE,
            "mode": args.mode,
            "thresholds": {
                "distinguish": DISTINGUISH_THRESHOLD,
                "continuity": CONTINUITY_THRESHOLD,
                "recall": RECALL_THRESHOLD,
                "relevance": RELEVANCE_THRESHOLD,
            },
        },
        "elapsed_sec": round(time.time() - t0, 2),
        "verdicts": verdicts,
        "by_dimension": by_dimension,
        "failures": all_failures,
        "n_suites_pass": n_pass,
        "n_suites_total": len(verdicts),
        "overall_verdict": "PASS" if n_pass == len(verdicts) else "FAIL",
    }

    report = {
        "version": VERSION,
        "suite_results": suite_results,
        "summary": summary,
    }

    # 写盘
    out_path = os.path.abspath(args.report)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[stress_turn_eval] report → {out_path}", file=sys.stderr)

    # stdout 输出 summary
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["overall_verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())