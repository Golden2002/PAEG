# -*- coding: utf-8 -*-
"""
PAEG 周期自我更新调度器（v0.19.21 ⭐）

补上 v0.19.20 自检发现的缺口：weekly_insight_update / batch_update /
analyze_failures 机制早已实现，但从未被定时触发。

本模块用一个后台守护线程实现：
- 启动时立即跑一次（把积压的反思/案例消化掉）
- 之后按 INTERVAL_HOURS（默认 24h）周期检查，满一周（或距上次周度更新 >= 7 天）执行周度任务
- 每次对话后由 server 调 mark_activity() 更新活跃时间戳

周度任务（满 7 天执行）：
1. SelfEvolver.weekly_insight_update() —— 从近期反思提取教学洞察（ExpeL 风格，含 Library Drift 防护）
2. SelfUpdater.batch_update()         —— 每周批处理：识别反复模式 + 清理过期快照
3. SelfImprover.analyze_failures()    —— 分析失败案例，生成改进建议写入 memory/improvements.md

改进建议闭环：teaching_memory.load_teaching_memory() 已会读取 improvements.md
并注入 system prompt（v0.19.7 已接线）——所以调度器跑起来后，改进建议会自动生效。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

# 周期参数
INTERVAL_HOURS = 24          # 检查周期
WEEK_SECONDS = 7 * 86400     # 周度阈值


class PeriodicSelfUpdater:
    def __init__(self, llm=None, paeg=None, interval_hours: int = INTERVAL_HOURS,
                 verbose: bool = True):
        self.llm = llm
        self.paeg = paeg          # PAEG 主类实例（提供 self_updater / evolver）
        self.interval = interval_hours * 3600
        self.verbose = verbose
        self.last_weekly = time.time()   # 上次周度更新（启动即视为"刚跑过"，避免启动立刻执行）
        self.last_activity = time.time()  # 最近一次对话活动
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._log(f"[PAEG][periodic] 初始化完成（检查间隔 {interval_hours}h，周度阈值 7 天）")

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    # ─── 外部接口 ───
    def mark_activity(self):
        """每次对话后调用：记录活跃时间（用于判断是否需要补跑）。"""
        self.last_activity = time.time()

    def start(self):
        """启动后台守护线程。"""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="periodic-self-update")
        self._thread.start()
        self._log("[PAEG][periodic] 调度线程已启动")

    def stop(self):
        self._stop.set()

    def run_now(self) -> dict:
        """立即执行一次周度任务（供 /api/self-update/run 手动触发）。"""
        return self._do_weekly()

    # ─── 内部 ───
    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                now = time.time()
                # 条件：距上次周度 >= 7 天，且系统有活跃使用（避免空转）
                if now - self.last_weekly >= WEEK_SECONDS and now - self.last_activity < WEEK_SECONDS:
                    result = self._do_weekly()
                    self.last_weekly = now
                    self._log(f"[PAEG][periodic] 周度自我更新完成: {result.get('summary', '')}")
            except Exception as e:
                self._log(f"[PAEG][periodic] 调度循环异常: {e}")

    def _do_weekly(self) -> dict:
        """执行全部周度自我更新任务。"""
        results = {
            "ts": datetime.now().isoformat(),
            "insights": 0, "batch": None, "improvements": 0,
        }
        # 1. 周度洞察提取（SelfEvolver，ExpeL 风格）
        try:
            if self.paeg is not None and getattr(self.paeg, 'evolver', None) is not None:
                new_insights = self.paeg.evolver.weekly_insight_update()
                results["insights"] = len(new_insights)
                self._log(f"[PAEG][periodic] 周度洞察: 新增 {len(new_insights)} 条")
        except Exception as e:
            self._log(f"[PAEG][periodic] 洞察提取失败: {e}")

        # 2. 批处理（SelfUpdater.batch_update：识别反复模式 + 清理过期快照）
        try:
            if self.paeg is not None and getattr(self.paeg, 'self_updater', None) is not None:
                results["batch"] = self.paeg.self_updater.batch_update()
                self._log(f"[PAEG][periodic] 批处理: {results['batch']}")
        except Exception as e:
            self._log(f"[PAEG][periodic] 批处理失败: {e}")

        # 3. 失败案例分析 → 改进建议（SelfImprover.analyze_failures → improvements.md）
        try:
            if self.llm is not None:
                from self_improve import SelfImprover
                improver = SelfImprover(llm=self.llm)
                suggestions = improver.analyze_failures()
                results["improvements"] = len(suggestions)
                if suggestions:
                    self._log(f"[PAEG][periodic] 改进建议 {len(suggestions)} 条已写入 memory/improvements.md")
        except Exception as e:
            self._log(f"[PAEG][periodic] 失败分析失败: {e}")

        results["summary"] = (f"洞察+{results['insights']} 批处理:{bool(results['batch'])} "
                              f"改进+{results['improvements']}")
        return results


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    p = PeriodicSelfUpdater(llm=None, paeg=None)
    print("模块自检 OK（未启动线程，仅验证导入）")
