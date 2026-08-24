# -*- coding: utf-8 -*-
"""Playwright 主测试引擎 —— 可复用测试工程核心。

流程：
  1. 读场景配置（scenarios/test_matrix.yaml）
  2. 教学流：学生状态机动态驱动 → 抓对话 → 复读检测 → Oracle1 评分
  3. 倾诉：12 轮剧本 → 抓对话 → 复读检测 → Oracle2 评分
  4. 物料：触发生成 → 抓取/解析 → Oracle3 评分
  5. 汇总报告（缺陷分级 P0-P3 + 通过判定）

用法：
  python test_engine.py --mode teaching --topic 光合作用
  python test_engine.py --mode confiding
  python test_engine.py --mode material --type ppt
  python test_engine.py --mode all
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from typing import Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 工程根
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "utils"))

from student_simulator import StudentSimulator  # noqa: E402
from repetition_detector import RepetitionDetector  # noqa: E402
from oracles import Oracle1Teaching, Oracle2Confiding, Oracle3Material  # noqa: E402

REPORT_DIR = os.path.join(BASE, "reports")
ARTIFACT_DIR = os.path.join(BASE, "artifacts")
BASE_URL = "http://localhost:5000"


class ChatHarness:
    """Playwright 聊天封装：发送消息 + 抓取回复。"""

    def __init__(self, headless: bool = True):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        self._page = self._browser.new_page(viewport={"width": 1440, "height": 900})
        self._page.goto(BASE_URL, timeout=20000, wait_until="networkidle")
        self._page.wait_for_timeout(2000)
        # 找聊天输入框
        self._ta = None
        for i in range(self._page.locator("textarea").count()):
            if self._page.locator("textarea").nth(i).is_visible():
                self._ta = self._page.locator("textarea").nth(i)
                break
        if not self._ta:
            raise RuntimeError("未找到聊天输入框")

    def switch_mode(self, mode: str):
        """切换到指定模式（如 affection 倾诉）。"""
        btn = self._page.locator(f'button[data-mode="{mode}"]')
        if btn.count() > 0:
            btn.first.click()
            self._page.wait_for_timeout(1500)
            return True
        # 兜底：按文本找
        try:
            self._page.click(f"text={mode}")
            self._page.wait_for_timeout(1500)
            return True
        except Exception:
            return False

    def send(self, message: str, wait_ms: int = 40000) -> str:
        """发送消息并等待回复，返回 AI 回复文本（从 .msg.paeg .msg-bubble 提取）。"""
        self._ta.fill(message)
        self._page.keyboard.press("Enter")
        self._page.wait_for_timeout(wait_ms)
        # 精确提取 AI 消息（避开 UI 菜单文本）
        try:
            bubbles = self._page.locator(".msg.paeg .msg-bubble")
            n = bubbles.count()
            if n > 0:
                return bubbles.nth(n - 1).inner_text()
        except Exception:
            pass
        return self._page.inner_text("body")

    def extract_ai_replies(self) -> list:
        """提取全部 AI 回复（供多轮分析）。"""
        try:
            bubbles = self._page.locator(".msg.paeg .msg-bubble")
            return [bubbles.nth(i).inner_text() for i in range(bubbles.count())]
        except Exception:
            return []

    def screenshot(self, name: str) -> str:
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        path = os.path.join(ARTIFACT_DIR, name)
        self._page.screenshot(path=path, full_page=True)
        return path

    def close(self):
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass


def run_teaching_flow(topic: str, harness: ChatHarness,
                      oracle: Oracle1Teaching, max_rounds: int = 18) -> Dict:
    """教学流测试：学生状态机驱动 15+ 轮，抓取对话。"""
    sim = StudentSimulator(topic, round_limit=max_rounds)
    turns = []
    last_ai = ""
    for _ in range(max_rounds + 5):
        student_input = sim.next_input(last_ai)
        if student_input is None or sim.should_end():
            break
        body = harness.send(student_input, wait_ms=30000)
        # 提取 AI 回复（取 body 尾部作为近似——生产环境用 DOM 选择器）
        last_ai = body[-500:]
        turns.append({"student": student_input, "teacher": last_ai, "state": sim.state})
        if sim.should_end():
            break

    # Oracle1 评分
    result = oracle.score_flow(turns, topic)
    result["rounds"] = len(turns)
    result["turns"] = turns
    result["topic"] = topic
    # 缺陷分级
    result["defects"] = _grade_defects(result)
    return result


def run_confiding(harness: ChatHarness, oracle: Oracle2Confiding,
                  detector: RepetitionDetector, rounds: int = 12) -> Dict:
    """倾诉测试：12 轮剧本 → 复读检测 → Oracle2 评分。"""
    # 12 轮倾诉剧本（渐进式情绪：表面→深层→危机→平复）
    script = [
        "老师，我今天真的很难受，考试又考砸了。",
        "我觉得自己特别失败，别人都考得比我好。",
        "我同桌还说'你也就这样了'，我特别生气，又很难过。",
        "其实我们之前关系挺好的，最近不知道怎么了。",
        "我是不是太敏感了？可能人家只是开玩笑。",
        "但我确实成绩不好，这学期努力了也没用。",
        "我爸妈也总说我，我就更烦。",
        "有时候晚上睡不着，一直想这些事。",
        "我不知道该怎么办，感觉做什么都没用。",
        "你说得好像有点道理，但我还是怕下次考不好。",
        "嗯，我试试你说的把目标定小一点。",
        "谢谢你，我感觉好一点了。",
    ]
    turns = []
    replies = []
    # 切换到倾诉模式
    harness.switch_mode("affection")
    for msg in script[:rounds]:
        body = harness.send(msg, wait_ms=25000)
        reply = body[-400:]
        turns.append({"student": msg, "agent": reply})
        replies.append(reply)

    # 复读检测
    rep = detector.detect(replies)
    # Oracle2 评分
    result = oracle.score_dialog(turns, "考试失利+同伴关系+自我否定",
                                 repetition_rate=rep["repetition_rate"])
    result["repetition"] = rep
    result["rounds"] = len(turns)
    result["turns"] = turns
    result["defects"] = _grade_defects(result)
    return result


def _grade_defects(score_result: Dict) -> List[Dict]:
    """缺陷分级：根据总分 + 一票否决。"""
    defects = []
    total = score_result.get("total") or 0
    if total < 60:
        defects.append({"severity": "P1", "desc": f"总分 {total} < 60，严重不达标",
                        "suggestion": "检查核心链路"})
    elif total < 85:
        defects.append({"severity": "P2", "desc": f"总分 {total} 在 60-84，需改进",
                        "suggestion": "按 rubric 维度逐项改进"})
    # 一票否决信号
    if score_result.get("repetition", {}).get("repetition_risk"):
        defects.append({"severity": "P1", "desc": "复读机风险：对话重复",
                        "suggestion": "检查回复多样性/套话"})
    return defects


def save_report(results: Dict, name: str) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="PAEG 三 Oracle 质量测试引擎")
    parser.add_argument("--mode", choices=["teaching", "confiding", "material", "all"],
                        default="all")
    parser.add_argument("--topic", default="光合作用")
    parser.add_argument("--material-type", default="ppt",
                        choices=["ppt", "handout", "teaching_video", "math_video"])
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    harness = ChatHarness(headless=args.headless)
    results = {"mode": args.mode, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": []}

    try:
        if args.mode in ("teaching", "all"):
            print(f"=== 教学流测试：{args.topic}（15+ 轮） ===")
            o1 = Oracle1Teaching()
            r1 = run_teaching_flow(args.topic, harness, o1)
            print(f"  轮数: {r1['rounds']} | Oracle1 总分: {r1.get('total')}")
            print(f"  缺陷: {[d['severity'] for d in r1['defects']]}")
            results["cases"].append({"type": "teaching", "result": r1})

        if args.mode in ("confiding", "all"):
            print("=== 倾诉测试（12 轮） ===")
            o2 = Oracle2Confiding()
            det = RepetitionDetector()
            r2 = run_confiding(harness, o2, det)
            print(f"  轮数: {r2['rounds']} | Oracle2 总分: {r2.get('total')}")
            print(f"  复读率: {r2.get('repetition', {}).get('repetition_rate')} | "
                  f"风险: {r2.get('repetition', {}).get('repetition_risk')}")
            results["cases"].append({"type": "confiding", "result": r2})

        if args.mode in ("material", "all"):
            print(f"=== 物料测试：{args.material_type} ===")
            o3 = Oracle3Material(args.material_type)
            r3 = _run_material(args, harness, o3)
            print(f"  Oracle3 总分: {r3.get('total')}")
            results["cases"].append({"type": "material", "result": r3})
    finally:
        harness.close()

    path = save_report(results, f"report_{time.strftime('%Y%m%d_%H%M%S')}.json")
    print(f"\n✅ 测试完成，报告: {path}")


def _run_material(args, harness, oracle: Oracle3Material) -> Dict:
    """物料生成测试：用 §3.87 精确魔法关键词触发（生成PPT：主题 等）。

    契约（§3.87 实测确认）：输入"生成PPT：光合作用"/"生成讲义：xxx"等精确关键词
    触发对应物料生成（前端按钮/chip 填前缀+用户补主题后发送）。关键词零正则精确匹配。
    """
    # 物料 → 精确魔法关键词
    keyword_map = {
        "ppt": f"生成PPT：{args.topic}",
        "handout": f"生成讲义：{args.topic}",
        "teaching_video": f"生成教学视频：{args.topic}",
        "math_video": f"生成数学动画：{args.topic}",
    }[args.material_type]
    # §3.97 ⭐ manim 渲染 2-5 分钟，120s 等不到（此前 0/20 分是评测时序问题）
    _wait = 300000 if args.material_type == "math_video" else 120000
    body = harness.send(keyword_map, wait_ms=_wait)
    material_text = body[-2500:]
    # §3.97 ⭐ 判断完成状态（渲染中/失败/成功——避免把中间态当最终质量）
    _status = "unknown"
    if "已生成" in material_text:
        _status = "done"
    elif "渲染" in material_text or "失败" in material_text or "生成中" in material_text:
        _status = "pending_or_failed"
    # §3.99 ⭐ manim 评"代码质量"——读落盘的 scene.py（脚本忠实度/详尽展示）
    _code_text = material_text
    if args.material_type == "math_video":
        try:
            import glob as _glob
            _pipeline = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "05_实现原型", "evolve_data",
                "manim_pipeline", "jobs", "*", "scene.py")
            _newest = None
            for _f in sorted(_glob.glob(_pipeline), key=os.path.getmtime, reverse=True):
                _newest = _f
                break
            if _newest and os.path.getmtime(_newest) > time.time() - 600:
                with open(_newest, encoding="utf-8") as _f:
                    _code_text = _f.read()[:4000]
                _status = "done"
        except Exception:
            pass
    shot = harness.screenshot(f"material_{args.material_type}.png")
    result = oracle.score_material(_code_text, args.topic, f"截图: {shot}")
    result["material_type"] = args.material_type
    result["topic"] = args.topic
    result["screenshot"] = shot
    result["material_text"] = material_text
    result["completion_status"] = _status
    # §3.97 ⭐ 未完成（中间态）不判分——记录待重测
    if _status != "done":
        result["total"] = 0
        result["note"] = "物料未在等待窗口内完成（渲染中/失败），需重测"
    result["defects"] = _grade_defects(result)
    return result


if __name__ == "__main__":
    main()
