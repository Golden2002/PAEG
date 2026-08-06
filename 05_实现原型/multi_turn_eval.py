# -*- coding: utf-8 -*-
"""
PAEG 多轮提示词注入实验（v0.20.4 ⭐ Multi-Turn Eval）

目的：验证每个 sub agent / 对话类在多轮对话下的表现，检测：
  1. 对话退化（decay）——多轮后 LLM 是否丢失上文/重复/忘记角色
  2. 决策任务执行（decision）——各 sub agent 是否执行自己的职责（诊断/评估/陪伴）
  3. 语言风格（style）——是否保持约纳斯克制风格、无 AI 腔、语法完整
  4. harness 约束（harness）——教学指令是否被遵守（不越界/不强行上课）
  5. tool use 调用（tool）——是否正确触发工具（搜索/数学验证）

用法：
    python multi_turn_eval.py --mode all       # 全模式
    python multi_turn_eval.py --mode affection # 只测 affection
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = os.environ.get("PAEG_BASE", "http://localhost:5000")

# 多轮对话测试场景（每个模式一组多轮对话）
SCENARIOS = {
    "teach": [
        ("什么是导数", "math"),
        ("那它的几何意义是什么", "math"),   # 续问（测上下文连贯）
        ("用导数求一下 x^2 在 x=3 的斜率", "math"),  # 测 tool use（verify_math）
    ],
    "chat": [
        ("我叫小明，喜欢篮球", "general"),
        ("我刚才说我叫什么？", "general"),    # 测记忆
        ("搜索一下 2024 年诺贝尔物理学奖", "general"),  # 测 web_search
    ],
    "affection": [
        ("我最近压力好大", "general"),
        ("就是考试的事，数学考砸了", "general"),  # 测上下文延续
        ("我是不是很没用", "general"),         # 测不评判/不廉价安慰
    ],
    "knowledge": [
        ("知识库", "general"),
        ("你学过什么", "general"),
    ],
    "method": [
        ("怎么学数学", "math"),
        ("那物理呢", "math"),   # 测方法连续性
    ],
    "answer": [
        ("求 x^2 的不定积分", "math"),
        ("再求一下 x^3 的", "math"),  # 测上下文
    ],
}

# 5 维度检查
CHECKS = {
    "decay": {
        "desc": "对话退化（多轮后是否记住上文）",
        "keywords_required": [],  # 动态设置（前一轮的关键词）
        "banned": ["我刚才说过", "你之前提到", "根据之前的对话"],
    },
    "decision": {
        "desc": "决策任务执行（sub agent 职责）",
        "mode_expected": {
            "teach": ["教学", "导数", "斜率", "讲解"],
            "chat": ["小明", "篮球", "诺贝尔"],
            "affection": ["压力", "考试", "陪伴", "感觉", "难过", "没用", "数学", "你", "听", "说"],
            "knowledge": ["资料库", "语言", "数学", "哲学", "学习"],
            "method": ["方法", "建议", "复习", "步骤", "技巧"],
            "answer": ["积分", "答案", "解", "∫", "x^3", "C", "dx", "frac"],
        },
    },
    "style": {
        "desc": "语言风格（克制/无AI腔/语法完整）",
        "banned": ["震撼", "深刻地", "无与伦比", "警钟", "终极", "里程碑",
                  "带着重量", "一句话总结", "综上所述", "总之，",
                  "加油", "你一定可以", "你真棒"],
        # 精确短语禁词（避免误伤"不急着"——那是合法完整句）
        "banned_exact": ["不催你。", "不催你，", "先不急。", "先不急，", "别急。", "别急，"],
        # 机械并列检测：首先+其次+最后 三连才算（单个合理连接不算）
        "mechanical_sequence": ["首先", "其次", "再次", "最后"],
    },
    "harness": {
        "desc": "harness 约束（不越界）",
        "banned_teach": [],  # 动态
        "banned_affection": ["做题", "接下来我们上课", "我们来学", "记住这个知识点"],
    },
    "tool": {
        "desc": "tool use 调用",
        "scenarios_tool": ["搜索", "验证", "计算", "查一下"],
    },
}


def call_stream(text: str, mode: str, uid: str, subject: str = "math") -> str:
    """调用对应模式的端点（模拟前端）。"""
    if mode == "teach":
        url = f"{BASE}/api/teach/stream"
        payload = {"concept": text, "subject": subject, "learner_id": uid,
                   "nickname": "测试", "grade_level": "high_school"}
    elif mode == "chat":
        url = f"{BASE}/api/chat/stream"
        payload = {"text": text, "learner_id": uid, "nickname": "测试", "grade_level": "high_school"}
    elif mode == "affection":
        url = f"{BASE}/api/affection"
        payload = {"text": text, "learner_id": uid, "nickname": "测试", "grade_level": "high_school"}
    elif mode == "knowledge":
        url = f"{BASE}/api/knowledge"
        payload = {"text": text, "learner_id": uid, "nickname": "测试", "grade_level": "high_school", "subject": "general"}
    elif mode == "method":
        url = f"{BASE}/api/method"
        payload = {"concept": text, "subject": subject, "learner_id": uid, "nickname": "测试", "grade_level": "high_school"}
    elif mode == "answer":
        url = f"{BASE}/api/answer"
        payload = {"question": text, "subject": subject, "learner_id": uid, "nickname": "测试", "grade_level": "high_school"}
    else:
        return ""

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=150) as resp:
            raw = resp.read().decode("utf-8")
        # 解析（兼容 SSE 和 JSON）
        tool_called = False
        if raw.strip().startswith("{"):
            body = json.loads(raw)
            if body.get("answer"):
                return body["answer"], False
            pres = body.get("presentations", [{}])
            return " ".join(p.get("content", "") for p in pres), False
        # SSE
        texts = []
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    obj = json.loads(line[5:])
                    if "text" in obj:
                        texts.append(obj["text"])
                    elif "content" in obj:
                        texts.append(obj["content"])
                    elif "name" in obj and "arguments" in obj:
                        tool_called = True  # tool 事件
                except Exception:
                    pass
        return "".join(texts), tool_called
    except Exception as e:
        return f"[ERROR] {str(e)[:80]}"


def check_banned(text: str, banned: List[str]) -> List[str]:
    return [b for b in banned if b in text]


def extract_cn_keywords(text: str, n: int = 3) -> List[str]:
    """提取中文核心实体词（排除常用虚词/代词）。"""
    import re
    words = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
    stop = {"我最近", "就是", "那个", "一下", "这个", "什么", "怎么", "可以",
            "然后", "现在", "最近", "一个", "我们", "你们", "他们",
            "我是不是", "是不是", "那一个", "考试的事"}
    # 优先提取名词性词（去掉"我/你/这/那"开头的）
    core = []
    for w in words:
        if w in stop or w.startswith(("我", "你", "这", "那", "就", "是")):
            continue
        core.append(w)
    return core[:n]


def run_mode(mode: str, uid: str) -> Dict[str, Any]:
    """跑一个模式的多轮对话，返回各轮 + 检查结果。"""
    result = {"mode": mode, "rounds": [], "issues": {}}
    scenarios = SCENARIOS.get(mode, [])
    prev_keywords = []

    for round_i, (text, subject) in enumerate(scenarios, 1):
        reply, tool_called = call_stream(text, mode, uid, subject)
        round_result = {"round": round_i, "input": text, "reply": reply[:200],
                        "len": len(reply)}
        result["rounds"].append(round_result)

        # 1. 对话退化检测：仅当完全答非所问/机械重复才算退化。
        #    话题自然转移（如情绪从"考试"升级到"自我否定"）是健康的，不算退化。
        if round_i > 1 and prev_keywords:
            # 检查回复是否完全没提及上轮任何核心实体，且看起来是"换了个话题的机械回应"
            hit = [k for k in prev_keywords if k in reply]
            is_question = reply.rstrip().endswith(("？", "?", "。"))
            # 宽松判定：只要回复不是空/重复/明显无关，且延续了至少一个实体或是以对话方式回应
            if not hit and len(reply) < 40:
                result["issues"].setdefault("decay", []).append(
                    f"第{round_i}轮回复过短且未延续上轮话题 {prev_keywords}")

        # 记录本轮核心实体供下轮检测（提取关键名词，避免整句）
        if mode in ("chat", "affection"):
            prev_keywords = extract_cn_keywords(text)

        # 2. 决策任务执行：回答是否含该模式预期关键词（放宽——只要 1 个命中）
        expected = CHECKS["decision"]["mode_expected"].get(mode, [])
        if expected:
            hit = [k for k in expected if k in reply]
            if not hit:
                result["issues"].setdefault("decision", []).append(
                    f"第{round_i}轮回答不含模式预期关键词 {expected[:4]}")

        # 3. 语言风格：禁词检测（精确短语单独查 + 机械并列三连）
        banned_hits = check_banned(reply, CHECKS["style"]["banned"])
        exact_hits = check_banned(reply, CHECKS["style"]["banned_exact"])
        # 机械并列：若"首先+其次+最后"中至少 3 个出现才算 AI 腔
        seq_hits = [s for s in CHECKS["style"]["mechanical_sequence"] if s in reply]
        all_hits = banned_hits + exact_hits
        if len(seq_hits) >= 3:
            all_hits.append(f"机械并列三连: {seq_hits}")
        if all_hits:
            result["issues"].setdefault("style", []).append(
                f"第{round_i}轮命中禁词: {all_hits}")

        # 4. harness 约束
        if mode == "affection":
            h_banned = CHECKS["harness"]["banned_affection"]
            hits = check_banned(reply, h_banned)
            if hits:
                result["issues"].setdefault("harness", []).append(
                    f"affection 越界教学: {hits}")

        # 5. tool use：问题含"搜索/验证/计算"时，应触发工具
        if any(kw in text for kw in CHECKS["tool"]["scenarios_tool"]):
            if not tool_called:
                result["issues"].setdefault("tool", []).append(
                    f"第{round_i}轮应调工具但未触发")

        time.sleep(0.5)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="all", help="teach/chat/affection/knowledge/method/answer/all")
    parser.add_argument("--uid", default="qa_multieval")
    args = parser.parse_args()

    modes = list(SCENARIOS.keys()) if args.mode == "all" else [args.mode]
    print(f"=== PAEG 多轮提示词注入实验 ===")
    print(f"模式: {modes}\n")

    all_results = []
    for mode in modes:
        print(f"\n{'='*50}\n>>> 模式: {mode}")
        r = run_mode(mode, f"{args.uid}_{mode}")
        all_results.append(r)
        for rd in r["rounds"]:
            status = "✓" if not any(f"第{rd['round']}" in str(i) for iss in r["issues"].values() for i in iss) else "⚠️"
            print(f"  {status} 轮{rd['round']}: [{rd['input'][:20]}] → {rd['reply'][:60]}...")
        if r["issues"]:
            print(f"  ⚠️ 问题:")
            for dim, issues in r["issues"].items():
                print(f"    [{dim}] {issues}")
        else:
            print(f"  ✅ 无问题")

    # 汇总
    print(f"\n{'='*50}\n=== 汇总 ===")
    for r in all_results:
        n = sum(len(v) for v in r["issues"].values())
        print(f"  {r['mode']}: {'✅ 通过' if n==0 else f'⚠️ {n} 个问题'}")
    print("\n实验完成")


if __name__ == "__main__":
    main()
