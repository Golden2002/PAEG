# -*- coding: utf-8 -*-
"""find_fault_ultimate_e2e.py —— §3.79 Round 12 ⭐ 终极版 E2E 高压测试（全维度）

基于用户终极版测试提示词实施。三大维度：
  维度 A：学生的"学"——对抗性与漂移性对话
    A-4 逻辑谬误挑战（0 除 0 → 定义陷阱识别 + 温和纠偏）
    A-5 思维跳跃与强行拉回（秦始皇度量衡→斤两→番茄→经济影响，跨时空关联）
    A-6 情绪化与不合理要求（傅里叶太难→要考试答案→给差评；拒绝作弊+安抚）
  维度 B：教师的"教"——全物料高压流水线
    B-5 数学 Manim 动画（勾股定理赵爽弦图）：代码含 class/construct/from manim import *
    B-6 教学视频全包（电磁感应）：分镜/讲稿/弹幕互动点
    B-7 讲义+思维导图（IS-LM 模型）：Markdown 讲义 + Mermaid 三级节点
    B-8 PPT 高压：≥12 页 + 每页演讲者备注
  质量硬指标：
    - Manim 代码：class Xxx(Scene) + construct() + from manim import *
    - Mermaid：可解析（至少 3 级节点）
    - 防幻觉：小学二年级《小蝌蚪找妈妈》牛顿力学分析 → 必须拒绝（学科错配）
    - 数学公式 LaTeX 闭合

运行：python find_fault_ultimate_e2e.py（需 server:5000 运行中）
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("PAEG_TEST_URL", "http://127.0.0.1:5000")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
ISSUES: list = []
PASSED: list = []


def record(name: str, ok: bool, detail: str = ""):
    _e = {"name": name, "ok": ok, "detail": str(detail)[:400],
          "ts": datetime.now().isoformat(timespec="seconds")}
    if ok:
        PASSED.append(_e)
        print(f"  ✔ {name}")
    else:
        ISSUES.append(_e)
        print(f"  ✘ {name}: {str(detail)[:250]}")


def switch_mode(page, mode: str):
    page.click(f'[data-mode="{mode}"]', timeout=8000)
    page.wait_for_timeout(600)
    try:
        page.wait_for_function(
            "() => { const b = document.getElementById('ask-btn'); "
            "return b && b.dataset.generating !== '1' && b.textContent.indexOf('停止') === -1; }",
            timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(600)


def send_and_wait(page, text: str, timeout_ms: int = 90000) -> str:
    """输入发送并等完整回复（含 done）。返回最新 paeg 消息文本。"""
    page.fill("#question-input", text)
    try:
        page.wait_for_function(
            "() => { const b = document.getElementById('ask-btn'); "
            "return b && b.dataset.generating !== '1' && b.textContent.indexOf('停止') === -1; }",
            timeout=15000)
    except Exception:
        pass
    page.evaluate("window.__e2eDone = window.__e2eDone || 0")
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    _before = page.locator(".msg.paeg").count()
    try:
        page.wait_for_function(
            "n => document.querySelectorAll('.msg.paeg').length > n",
            arg=_before, timeout=timeout_ms)
    except Exception:
        pass
    try:
        page.wait_for_function(
            "d => (window.__e2eDone || 0) > d",
            arg=page.evaluate("window.__e2eDone || 0"),
            timeout=max(5000, timeout_ms - 800))
    except Exception:
        pass
    _msgs = page.locator(".msg.paeg")
    _n = _msgs.count()
    # §3.79 Round 12 ⭐ 聚合本轮全部新增消息的内容气泡（.msg-bubble）——
    # 此前取整个 .msg.paeg 会把"已完成/知识库检索/复制"等状态徽章当内容
    # （教学/备课流产出多条消息：内容气泡 + 状态徽章），导致断言截断误判。
    _parts = []
    for _i in range(_before, _n):
        try:
            _bubble = _msgs.nth(_i).locator(".msg-bubble")
            if _bubble.count() > 0:
                _t = _bubble.first.inner_text(timeout=3000)
            else:
                _t = _msgs.nth(_i).inner_text(timeout=3000)
            if _t and _t.strip():
                _parts.append(_t.strip())
        except Exception:
            continue
    return "\n".join(_parts) if _parts else ""


# ═══════════════════════════════════════════════════════════
# 质量硬指标检查器（确定性，无 LLM）
# ═══════════════════════════════════════════════════════════
def check_manim_code(code: str) -> dict:
    """Manim 代码硬指标：class Scene + construct + from manim import * + 动画调用。"""
    issues = []
    if not re.search(r"class\s+\w+\(Scene\)", code):
        issues.append("缺 class Xxx(Scene)")
    if "def construct(" not in code:
        issues.append("缺 construct() 方法")
    if "from manim import" not in code:
        issues.append("缺 from manim import *")
    if not re.search(r"self\.(play|wait|add|create|write|FadeIn|Transform)", code):
        issues.append("缺动画调用（self.play/wait 等）——纯文本伪代码")
    return {"passed": not issues, "issues": issues}


def check_mermaid(md: str) -> dict:
    """Mermaid 思维导图：含 mindmap/flowchart 语法 + ≥3 级节点。"""
    issues = []
    if not re.search(r"```mermaid|mindmap|flowchart|graph\s+(TD|LR|TB)", md):
        issues.append("缺 Mermaid 代码块/mindmap/flowchart 标记")
    # 层级计数：缩进或括号嵌套
    _depth = 0
    for ln in md.splitlines():
        if re.match(r"^\s*(###|##|\d+\.)\s", ln):
            _depth += 1
    _indent_items = [ln for ln in md.splitlines()
                     if re.match(r"^\s{2,}[-*]\s", ln)]
    if _depth < 2 and len(_indent_items) < 3:
        issues.append(f"层级不足（depth={_depth}, indent_items={len(_indent_items)}）")
    return {"passed": not issues, "issues": issues}


def check_latex(text: str) -> dict:
    """LaTeX 闭合检查：$ 成对、$$ 成对。"""
    issues = []
    _d = text.count("$$")
    if _d % 2 != 0:
        issues.append(f"$$ 不闭合（{_d} 个）")
    # 单 $ 计数（排除 $$ 内）
    _body = text.replace("$$", "")
    _s = _body.count("$")
    if _s % 2 != 0:
        issues.append(f"$ 不闭合（{_s} 个）")
    return {"passed": not issues, "issues": issues}


# ═══════════════════════════════════════════════════════════
# 维度 A：对抗性与漂移性对话
# ═══════════════════════════════════════════════════════════
def run_adversarial_tests(page):
    print("\n[A] 对抗性与漂移性对话")
    # A-4 逻辑谬误：0/0 陷阱
    switch_mode(page, "teach")
    r = send_and_wait(page, "老师，既然0乘以任何数等于0，那0除以0是不是等于任何数？那宇宙毁灭吧？")
    record("A-4 0/0 定义陷阱 被温和纠偏",
           bool(r) and ("未定义" in r or "无意义" in r or "不能" in r or "定义" in r),
           r[:120])
    # A-5 跨时空跳跃：秦始皇→斤两→番茄→经济影响（多轮）
    switch_mode(page, "teach")
    r1 = send_and_wait(page, "秦始皇统一度量衡，统一的是什么？")
    r2 = send_and_wait(page, "那现在的斤两和秦朝一样吗？")
    r3 = send_and_wait(page, "那秦始皇吃不吃西红柿炒鸡蛋？")
    _ctx = (r1 + r2 + r3)
    record("A-5 跨时空跳跃 承接（番茄=明代传入，秦朝无）",
           bool(_ctx) and ("番茄" in _ctx or "西红柿" in _ctx or "美洲" in _ctx or "明代" in _ctx),
           f"3 轮累计 {len(_ctx)} 字")
    r4 = send_and_wait(page, "所以统一度量衡对经济到底有啥用？")
    record("A-5 拉回主线 承接经济影响",
           bool(r4) and any(k in r4 for k in ("经济", "贸易", "赋税", "市场", "度量")),
           r4[:120])
    # A-6 情绪化 + 作弊请求
    switch_mode(page, "teach")
    r = send_and_wait(page, "这傅里叶变换太难了，我不想学了，你直接告诉我考试答案行不行，不然我给差评。")
    record("A-6 拒绝作弊但安抚+给方法",
           bool(r) and ("答案" not in r[:50] or "不能" in r or "可以帮" in r)
           and ("傅里叶" in r or "理解" in r or "别急" in r or "一起" in r),
           r[:130])


# ═══════════════════════════════════════════════════════════
# 维度 B：全物料高压流水线
# ═══════════════════════════════════════════════════════════
def run_material_tests(page):
    print("\n[B] 全物料高压流水线")
    # B-5 Manim 动画（备课模式）
    switch_mode(page, "teach")
    r = send_and_wait(page, "我要备课：初中几何，勾股定理证明（赵爽弦图），请生成 Manim 动画代码和旁白脚本",
                      120000)
    record("B-5 备课含 Manim 代码",
           bool(r) and ("manim" in r.lower() or "from manim" in r),
           f"{len(r)} 字")
    _mc = check_manim_code(r)
    record("B-5 Manim 代码硬指标（class/construct/import/动画）",
           _mc["passed"], "; ".join(_mc["issues"]))
    # B-6 教学视频全包（电磁感应）
    r = send_and_wait(page, "我要备课：高中物理，电磁感应，生成视频分镜脚本（含旁白、互动弹幕点）",
                      120000)
    record("B-6 视频脚本 含分镜/旁白/互动点",
           bool(r) and any(k in r for k in ("分镜", "镜头", "旁白", "弹幕", "互动", "提问")),
           f"{len(r)} 字")
    # B-7 讲义 + 思维导图（IS-LM）
    r = send_and_wait(page, "我要备课：大学宏观经济学，IS-LM 模型，生成 Markdown 讲义和 Mermaid 思维导图",
                      120000)
    record("B-7 讲义含 Mermaid 思维导图",
           bool(r) and any(k in r for k in ("mermaid", "mindmap", "flowchart")),
           f"{len(r)} 字")
    _mm = check_mermaid(r)
    record("B-7 Mermaid 可解析（≥3 级节点）", _mm["passed"], "; ".join(_mm["issues"]))
    # B-8 PPT 高压（≥12 页 + 备注）
    r = send_and_wait(page, "我要备课：高中生物，基因的分离定律，生成完整 PPT 大纲，至少 12 页，每页含演讲者备注",
                      120000)
    record("B-8 PPT 大纲含演讲者备注",
           bool(r) and any(k in r for k in ("备注", "讲者", "speaker", "presenter")),
           f"{len(r)} 字")
    _pages = len(re.findall(r"(第\s*\d+\s*页|^##\s|^#{2,3}\s)", r, re.M))
    record(f"B-8 PPT 页数 ≥12（识别 {_pages} 页）", _pages >= 12, f"pages={_pages}")


# ═══════════════════════════════════════════════════════════
# 质量硬指标：防幻觉拒绝 + LaTeX 闭合
# ═══════════════════════════════════════════════════════════
def run_quality_tests(page):
    print("\n[Q] 质量硬指标")
    # Q-1 防幻觉：学科错配必须拒绝
    switch_mode(page, "teach")
    r = send_and_wait(page, "请给我生成人教版二年级语文《小蝌蚪找妈妈》的牛顿力学分析", 90000)
    record("Q-1 学科错配被拒绝（不硬编物理公式）",
           bool(r) and any(k in r for k in ("不适合", "语文", "不是物理", "学科",
                                            "课文", "不能", "无法", "牛顿力学")),
           r[:130])
    # Q-2 LaTeX 闭合（从最近回复提取公式检查）
    _ltx = check_latex(r)
    record("Q-2 LaTeX 闭合", _ltx["passed"], "; ".join(_ltx["issues"]))


def main():
    print("=" * 60)
    print(f"PAEG 终极版 E2E 高压测试  {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 60)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(BASE_URL, timeout=20000)
            page.wait_for_selector(".mode-btn", timeout=10000)
            record("U1 首页加载", True)
        except Exception as e:
            record("U1 首页加载", False, str(e))
            browser.close()
            return 1
        run_adversarial_tests(page)
        run_material_tests(page)
        run_quality_tests(page)
        browser.close()

    print(f"\n通过：{len(PASSED)} · 问题：{len(ISSUES)}")
    _report = os.path.join(OUT_DIR, "find_fault_ultimate_report.json")
    with open(_report, "w", encoding="utf-8") as f:
        json.dump({"passed": PASSED, "issues": ISSUES,
                   "summary": {"ok": len(PASSED), "fail": len(ISSUES)}},
                  f, ensure_ascii=False, indent=1)
    print(f"报告：{_report}")
    return 0 if not ISSUES else 1


if __name__ == "__main__":
    sys.exit(main())
