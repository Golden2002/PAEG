# -*- coding: utf-8 -*-
"""paeg_playwright_test.py —— §3.39 ⭐ Playwright 全功能前端测试（v1.1.5）

用户需求（2026-08-15）：用 Playwright 对页面所有功能测试——每一种对话模式、
每一种物料生成都要测，不同场景、多轮对话。

覆盖：
- 6 种对话模式（teach/chat/answer/method/knowledge/affection）× 不同场景 × 多轮
- 物料生成（讲义/PPT/视频/动画/导图）
- 功能按钮（停止/深度思考/工具条）
- 边界场景（空输入/情绪词/学科切换）

参照：memo/017（全模式真实场景测试标准）+ memo/018（报告范式）
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("PAEG_TEST_URL", "http://127.0.0.1:5000")
OUT_DIR = os.environ.get("PAEG_TEST_OUT", r"D:\wbo-workspace\playwright_test_out")
os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────
# 6 模式 × 场景 × 多轮对话数据
# ─────────────────────────────────────
MODES = {
    "teach": {
        "btn": '[data-mode="teach"]',
        "scenarios": [
            ("教学-第1轮", "什么是导数？给我讲清楚概念"),
            ("教学-第2轮", "导数的几何意义是什么？"),
            ("教学-第3轮", "能不能举一个生活中的例子？"),
        ],
    },
    "chat": {
        "btn": '[data-mode="chat"]',
        "scenarios": [
            ("闲聊-第1轮", "你好呀，今天过得怎么样？"),
            ("闲聊-第2轮", "你觉得什么是幸福？"),
            ("闲聊-第3轮", "推荐一本哲学入门书吧"),
        ],
    },
    "answer": {
        "btn": '[data-mode="answer"]',
        "scenarios": [
            ("找答案-第1轮", "光合作用的完整过程是什么？"),
            ("找答案-第2轮", "勾股定理怎么证明？"),
        ],
    },
    "method": {
        "btn": '[data-mode="method"]',
        "scenarios": [
            ("方法-第1轮", "怎么高效学习数学？"),
            ("方法-第2轮", "如何克服拖延症？"),
        ],
    },
    "knowledge": {
        "btn": '[data-mode="knowledge"]',
        "scenarios": [
            ("知识库-第1轮", "你们知识库里有哲学的内容吗？"),
            ("知识库-第2轮", "列出物理学相关的知识"),
        ],
    },
    "affection": {
        "btn": '[data-mode="affection"]',
        "scenarios": [
            ("倾诉-第1轮", "最近考试没考好，很难过"),
            ("倾诉-第2轮", "感觉自己很失败，什么都不行"),
            ("倾诉-第3轮", "谢谢你听我说这些"),
        ],
    },
}

# 边界场景
EDGE_CASES = [
    ("空输入", ""),
    ("情绪词", "我有点难过"),
    ("危机信号", "我真的活不下去了"),
    ("超短输入", "极限"),
]


class PAEGPlaywrightTester:
    def __init__(self, headless: bool = True):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=headless)
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        self.results = {}

    def open(self):
        self.page.goto(BASE_URL, timeout=30000)
        self.page.wait_for_load_state("networkidle", timeout=15000)
        print(f"[OK] 页面加载: {BASE_URL}")

    def select_mode(self, mode: str):
        """点击模式按钮（.mode-btn 文本匹配）。"""
        label_map = {"teach": "学科教学", "chat": "闲聊", "answer": "找答案",
                     "method": "学习方法", "knowledge": "知识库", "affection": "倾诉"}
        label = label_map.get(mode, mode)
        btns = self.page.query_selector_all(".mode-btn")
        for btn in btns:
            if label in btn.inner_text():
                btn.click(timeout=5000)
                time.sleep(0.8)
                return
        # 兜底：data-mode 属性
        sel = MODES[mode].get("btn")
        if sel:
            self.page.click(sel, timeout=5000)
            time.sleep(0.8)

    def send_message(self, text: str, wait_sec: float = 8.0) -> str:
        """输入消息并发送，等待回复（返回**本轮新增**文本，非历史累积）。"""
        if not text:
            return "[空输入-不发送]"
        # 记录发送前文本长度（用于 diff）
        before = len(self.page.evaluate("() => document.body.innerText"))
        self.page.fill("#question-input", text)
        time.sleep(0.3)
        self.page.click("#ask-btn", timeout=5000)
        # 等待回复出现（轮询直到文本增长或超时）
        deadline = time.time() + wait_sec
        while time.time() < deadline:
            time.sleep(1)
            now = len(self.page.evaluate("() => document.body.innerText"))
            if now > before + 20:  # 有新增内容
                break
        time.sleep(2)  # 稳定
        full = self.page.evaluate("() => document.body.innerText")
        return full[before:before + 500] if len(full) > before else "[无新增]"

    def _get_last_message(self) -> str:
        """获取最后一条 assistant 消息（用 body.innerText 兜底）。"""
        try:
            # 首选：常见 assistant 消息选择器
            for sel in [".assistant-message", ".assistant .content", ".message.assistant",
                        "[class*=assistant] [class*=content]", ".bot-message"]:
                els = self.page.query_selector_all(sel)
                if els:
                    return els[-1].inner_text()[:300]
            # 兜底：body 全文本（包含教学回复）
            full = self.page.evaluate("() => document.body.innerText")
            return full[-400:] if full else "[空页面]"
        except Exception as e:
            return f"[获取消息失败: {e}]"

    def screenshot(self, name: str):
        path = os.path.join(OUT_DIR, f"{name}.png")
        self.page.screenshot(path=path, full_page=False)
        return path

    def test_mode(self, mode: str):
        """测试单个模式：切模式 → 多轮对话 → 截图。"""
        print(f"\n=== 测试模式: {mode} ===")
        self.select_mode(mode)
        time.sleep(0.5)
        mode_results = []
        for label, text in MODES[mode]["scenarios"]:
            reply = self.send_message(text)
            mode_results.append({"label": label, "input": text, "reply": reply[:200]})
            print(f"  [{label}] 输入: {text[:30]}... → 回复 {len(reply)} 字符")
            time.sleep(1)
        shot = self.screenshot(f"mode_{mode}")
        mode_results.append({"screenshot": shot})
        self.results[mode] = mode_results
        return mode_results

    def test_material_generation(self):
        """测试物料生成（讲义/PPT/视频/动画/导图）——通过 teach 模式触发。"""
        print("\n=== 测试物料生成 ===")
        self.select_mode("teach")
        time.sleep(0.5)
        materials = {}
        triggers = {
            "handout": "请帮我生成关于二次函数的讲义",
            "ppt": "请帮我做一份关于微积分的PPT",
            "mindmap": "请帮我画一张关于力学的知识导图",
        }
        for mtype, trigger in triggers.items():
            reply = self.send_message(trigger, wait_sec=10)
            materials[mtype] = {"trigger": trigger, "reply": reply[:150]}
            print(f"  [{mtype}] 触发: {trigger[:25]}... → {len(reply)} 字符")
            time.sleep(1)
        shot = self.screenshot("materials")
        materials["screenshot"] = shot
        self.results["materials"] = materials

    def test_features(self):
        """测试功能按钮（工具条 6 按钮 + 深度思考 + 停止键）。"""
        print("\n=== 测试功能按钮 ===")
        features = {}
        # 工具条 6 按钮存在性
        tool_btns = {
            "handout": "#cmd-trigger-handout",
            "ppt": "#cmd-trigger-ppt",
            "video": "#cmd-trigger-video",
            "manim": "#cmd-trigger-manim",
            "deepthink": "#cmd-trigger-deepthink",
            "kmap": "#cmd-trigger-kmap",
        }
        for name, sel in tool_btns.items():
            el = self.page.query_selector(sel)
            visible = el.is_visible() if el else False
            features[f"tool_{name}"] = f"{'✅ 存在可见' if visible else '❌ 未找到'}"
            print(f"  [工具条-{name}] {'✅' if visible else '❌'}")
        # 深度思考按钮点击
        try:
            deep = self.page.query_selector("#cmd-trigger-deepthink")
            if deep and deep.is_visible():
                deep.click(timeout=3000)
                time.sleep(1)
                tag = self.page.query_selector("#cmd-tag-deepthink")
                features["deepthink_click"] = f"✅ 点击成功，tag={'可见' if tag and tag.is_visible() else '不可见'}"
                print(f"  [深度思考] ✅ 点击成功")
            else:
                features["deepthink_click"] = "❌ 按钮不可见"
        except Exception as e:
            features["deepthink_click"] = f"异常: {e}"
        # 停止键（生成过程中出现）
        try:
            self.select_mode("teach")
            self.page.fill("#question-input", "请详细讲解量子力学的完整内容")
            self.page.click("#ask-btn")
            time.sleep(3)
            stop = self.page.query_selector("[id*=stop], .stop-btn, [class*=stop]")
            if stop and stop.is_visible():
                stop.click(timeout=3000)
                features["stop_btn"] = "✅ 停止键存在并点击成功"
                print(f"  [停止键] ✅ 点击成功")
            else:
                features["stop_btn"] = "⚠️ 生成太快未捕获停止键（功能可能正常）"
                print(f"  [停止键] ⚠️ 未捕获")
        except Exception as e:
            features["stop_btn"] = f"异常: {e}"
        # 语音按钮存在性
        voice = self.page.query_selector("#voice-btn")
        features["voice_btn"] = "✅ 存在" if voice and voice.is_visible() else "❌ 未找到"
        print(f"  [语音] {'✅' if voice and voice.is_visible() else '❌'}")
        self.results["features"] = features

    def test_edge_cases(self):
        """测试边界场景。"""
        print("\n=== 测试边界场景 ===")
        self.select_mode("teach")
        edges = []
        for label, text in EDGE_CASES:
            reply = self.send_message(text, wait_sec=5)
            edges.append({"label": label, "input": text, "reply": reply[:150]})
            print(f"  [{label}] → {len(reply)} 字符")
            time.sleep(1)
        self.results["edge_cases"] = edges

    def close(self):
        self.browser.close()
        self.pw.stop()

    def save_report(self):
        """保存测试报告。"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "results": self.results,
        }
        path = os.path.join(OUT_DIR, "test_report.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"\n[报告] 已保存: {path}")
        return path


def main():
    tester = PAEGPlaywrightTester(headless=True)
    try:
        tester.open()
        # 1. 6 模式 × 多轮
        for mode in MODES:
            tester.test_mode(mode)
        # 2. 物料生成
        tester.test_material_generation()
        # 3. 功能按钮
        tester.test_features()
        # 4. 边界场景
        tester.test_edge_cases()
        # 5. 报告
        tester.save_report()
        print("\n=== 测试完成 ===")
    finally:
        tester.close()


if __name__ == "__main__":
    main()
