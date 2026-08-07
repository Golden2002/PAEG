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
import os
import json
import re
from datetime import datetime
from typing import Optional

# 周期参数
INTERVAL_HOURS = 24          # 检查周期
WEEK_SECONDS = 7 * 86400     # 周度阈值


# v0.24：根据 SelfUpdateAgent 建议的 target 字段，把建议分到 improvements.md 的对应改进段。
# 段名与 PeriodicSelfUpdater 写过的现有段呼应（含 subject_requests / SelfImprover 等）。
_TARGET_SECTION_KEYWORDS = (
    # 段名 -> 匹配 target 子串（按顺序匹配，第一个命中者胜）
    ("routing", (
        "meta_router", "meta-router", "router", "route",
        "self_update", "selfupdate", "self-update", "selfevolution",
        "self_evolution.py", "self_update.py", "self_update_agent",
        "from_feedback", "api/self-update", "periodic_self_update",
        "selfupdateagent",
    )),
    ("system_prompt", (
        "prompt", "system", "prompts.py", "build_",
    )),
    ("pedagogy", (
        "pedagogy", "pedagogy.py", "教学法", "教学策略",
    )),
    ("affection", (
        "affection", "AffectionSAPAO", "情绪", "心理", "support",
    )),
    ("subject_patches", (
        "subject_patch", "subject_patches", "学科提示词",
    )),
    ("tool_lessons", (
        "tool_", "tool_lesson", "tool_lessons", "工具",
    )),
    ("knowledge_base", (
        "knowledge", "知识库", "kb", "library",
    )),
    ("safety", (
        "safety", "guard", "安全", "护栏",
    )),
    ("presentation", (
        "presenter", "presentation", "展示",
    )),
    ("diagnosis", (
        "diagnos", "诊断",
    )),
)


def _classify_target_section(target: str) -> str:
    """v0.24：把 SelfUpdateAgent 建议的 target 字段映射到 improvements.md 的改进段。

    例如 target="subagents.AffectionSupportor" → "affection"
                 target="prompts.build_concept_explain_system" → "system_prompt"
                 target="subagents.SelfUpdateAgent.run" → "routing"
                 target="pedagogy.Pedagogy.adapt_to_learner" → "pedagogy"

    默认段：general（落到总览，不进任何专精段）。
    """
    t = (target or "").lower()
    if not t:
        return "general"
    for section, kws in _TARGET_SECTION_KEYWORDS:
        for kw in kws:
            if kw and kw.lower() in t:
                return section
    return "general"


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

        # 4. 新学科需求（v0.19.26）→ 生成待新增学科建议（写入 improvements.md 自动注入）
        try:
            req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'evolve_data', 'subject_requests.json')
            if os.path.isfile(req_path):
                with open(req_path, encoding='utf-8') as f:
                    reqs = json.load(f)
                top = sorted(reqs, key=lambda x: x.get("count", 0), reverse=True)[:10]
                if top:
                    suggestions = [
                        f"- 新增学科建议：{r['subject']}（累计被问 {r['count']} 次，"
                        f"最近：{r.get('last_seen', '')[:10]}）"
                        for r in top
                    ]
                    imp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            'memory', 'improvements.md')
                    with open(imp_path, 'a', encoding='utf-8') as f:
                        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d')} · 新学科需求\n")
                        f.write("\n".join(suggestions) + "\n")
                    results["subject_requests"] = len(top)
                    self._log(f"[PAEG][periodic] 待新增学科: {len(top)} 条已写入 improvements.md")
        except Exception as e:
            self._log(f"[PAEG][periodic] 新学科需求读取失败: {e}")

        # 5. v0.22.2 → v0.24：SelfUpdateAgent 建议回流（self_update_suggestions.jsonl → improvements.md）
        # 增强：
        #   - 按 target 关键词把建议分到对应段（system_prompt / pedagogy / affection / general）
        #   - 按 priority 过滤：P0/P1 写入 improvements.md（P2 仅入日志供人工 review）
        #   - 去重（同一 (category, target, change) 只消费一次）
        #   - 消费过则写入 processed marker 文件，避免下次重复消费
        try:
            _mem = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'memory')
            _su_path = os.path.join(_mem, 'self_update_suggestions.jsonl')
            _imp_path = os.path.join(_mem, 'improvements.md')
            _proc_path = os.path.join(_mem, 'self_update_suggestions.processed.jsonl')
            if os.path.isfile(_su_path):
                _lines = [l for l in open(_su_path, encoding='utf-8').read().splitlines() if l.strip()]
                # 加载已处理 hash（去重）
                _processed = set()
                if os.path.isfile(_proc_path):
                    for _pl in open(_proc_path, encoding='utf-8').read().splitlines():
                        if _pl.strip():
                            try:
                                _processed.add(json.loads(_pl).get("hash", ""))
                            except Exception:
                                continue
                import hashlib as _hl
                _consumed = 0
                _p0p1_lines = []      # 高优先级段（写入 improvements.md）
                _all_summary = []     # 全量摘要段（给运维参考）
                _new_processed = []
                _exec_subjects = []   # v0.25：待落地的"新增学科"建议
                _exec_library = []    # v0.25：待落地的"Library 扩充"建议
                # 按时间段顺序消费（最新在尾部）
                for _l in _lines:
                    try:
                        _d = json.loads(_l)
                    except Exception:
                        continue
                    _ts = _d.get("timestamp", "")
                    _sugs = _d.get("suggestions") or []
                    for _s in _sugs:
                        if not isinstance(_s, dict):
                            continue
                        _cat = str(_s.get("category", "prompt_update"))
                        _tar = str(_s.get("target", ""))
                        _chg = str(_s.get("change", ""))
                        _evi = str(_s.get("evidence", ""))[:160]
                        _pri = str(_s.get("priority", "P2"))
                        if _pri not in ("P0", "P1", "P2"):
                            _pri = "P2"
                        if not _chg:
                            continue
                        _h = _hl.md5(f"{_cat}|{_tar}|{_chg}".encode("utf-8")).hexdigest()[:16]
                        if _h in _processed:
                            continue
                        _processed.add(_h)
                        _new_processed.append({"hash": _h, "ts": _ts,
                                                "category": _cat, "priority": _pri,
                                                "target": _tar[:80]})
                        # 按 target 关键词分到对应改进段
                        _section = _classify_target_section(_tar)
                        _line = (f"- [{_pri}] {_cat} · `{_tar[:60]}`\n"
                                 f"  改：{_chg[:160]}\n"
                                 f"  证：{_evi}\n"
                                 f"  → 段：{_section}\n")
                        _all_summary.append(_line.strip())
                        if _pri in ("P0", "P1"):
                            # 高优 → 写 improvements.md 对应段
                            _p0p1_lines.append((_section, _line))
                            _consumed += 1
                        # v0.25：可执行建议收集（subject_addition / library_update 落地）
                        if _cat == "subject_addition":
                            _exec_subjects.append({
                                "target": _tar, "change": _chg, "evidence": _evi, "priority": _pri})
                        elif _cat == "library_update":
                            _exec_library.append({
                                "target": _tar, "change": _chg, "evidence": _evi, "priority": _pri})
                if _p0p1_lines or _all_summary:
                    with open(_imp_path, 'a', encoding='utf-8') as _f:
                        _today = datetime.now().strftime('%Y-%m-%d')
                        if _p0p1_lines:
                            _f.write(f"\n## {_today} · SelfUpdateAgent 高优先级建议（P0/P1）\n")
                            # 按段聚合
                            _by_section = {}
                            for _sec, _line in _p0p1_lines:
                                _by_section.setdefault(_sec, []).append(_line)
                            for _sec, _lines in _by_section.items():
                                _f.write(f"\n### {_sec}\n")
                                _f.write("".join(_lines))
                        if _all_summary:
                            _f.write(f"\n## {_today} · SelfUpdateAgent 全部建议概览（P0/P1/P2）\n")
                            _f.write("\n".join(_all_summary) + "\n")
                    # 写 processed marker（避免下次重复消费）
                    with open(_proc_path, 'a', encoding='utf-8') as _f:
                        for _p in _new_processed:
                            _f.write(json.dumps(_p, ensure_ascii=False) + "\n")
                    results["su_suggestions"] = _consumed
                    results["su_total_processed"] = len(_new_processed)
                    self._log(f"[PAEG][periodic] SelfUpdateAgent 高优 {_consumed} 条已写入"
                              f" improvements.md（共处理 {len(_new_processed)} 条）")

                # ─── v0.25：可执行建议落地执行器 ⭐ ───
                # 1) subject_addition → 生成学科注册 JSON 到 Library/KnowledgeBase/subjects/
                #    （library_loader 重启自动注册 → 学科真正入库）
                if _exec_subjects:
                    _subj_dir = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        'Library', 'KnowledgeBase', 'subjects')
                    try:
                        os.makedirs(_subj_dir, exist_ok=True)
                    except Exception:
                        _subj_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 'data', 'pending_subjects')
                        os.makedirs(_subj_dir, exist_ok=True)
                    _executed_subs = 0
                    for _es in _exec_subjects[:5]:  # 最多落地 5 条
                        _target = str(_es.get("target", "")).strip() or "new_subject"
                        # target 形如 "linguistics" / "新增学科 linguistics" / "心理学"
                        _name = re.sub(r'[^\w\u4e00-\u9fff]+', '', _target.split()[-1] if _target.split() else _target)[:30]
                        _fname = f"pending_subject_{datetime.now().strftime('%Y%m%d%H%M%S')}_{_hl.md5(_target.encode('utf-8')).hexdigest()[:6]}.json"
                        _node = {
                            "pending_subject": _target,
                            "change": str(_es.get("change", ""))[:500],
                            "evidence": str(_es.get("evidence", ""))[:300],
                            "priority": str(_es.get("priority", "P2")),
                            "timestamp": datetime.now().isoformat(),
                            "note": "SelfUpdateAgent 建议的新学科（需人工确认后转为正式 SUBJECT_STYLES 条目）",
                        }
                        try:
                            with open(os.path.join(_subj_dir, _fname), 'w', encoding='utf-8') as _f:
                                json.dump(_node, _f, ensure_ascii=False, indent=2)
                            _executed_subs += 1
                        except Exception:
                            continue
                    if _executed_subs:
                        results["su_subjects_staged"] = _executed_subs
                        self._log(f"[PAEG][periodic] 新增学科建议 {_executed_subs} 条已写入"
                                  f" {os.path.relpath(_subj_dir)}（待确认入库）")

                # 2) library_update → 记录到 data/pending_library.json（待人工/后续补充）
                if _exec_library:
                    _pend_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             'data', 'pending_library.json')
                    _lib_records = []
                    if os.path.isfile(_pend_lib):
                        try:
                            _lib_records = json.load(open(_pend_lib, encoding='utf-8'))
                        except Exception:
                            _lib_records = []
                    for _el in _exec_library[:5]:
                        _lib_records.append({
                            "target": str(_el.get("target", ""))[:120],
                            "change": str(_el.get("change", ""))[:300],
                            "evidence": str(_el.get("evidence", ""))[:200],
                            "timestamp": datetime.now().isoformat(),
                        })
                    try:
                        os.makedirs(os.path.dirname(_pend_lib), exist_ok=True)
                        with open(_pend_lib, 'w', encoding='utf-8') as _f:
                            json.dump(_lib_records[-50:], _f, ensure_ascii=False, indent=2)
                        results["su_library_staged"] = len(_exec_library)
                        self._log(f"[PAEG][periodic] Library 扩充建议 {len(_exec_library)} 条"
                                  f" 已记录 data/pending_library.json")
                    except Exception:
                        pass
        except Exception as e:
            self._log(f"[PAEG][periodic] 建议回流失败: {e}")

        results["summary"] = (f"洞察+{results['insights']} 批处理:{bool(results['batch'])} "
                              f"改进+{results['improvements']} 学科需求+{results.get('subject_requests', 0)} "
                              f"建议回流+{results.get('su_suggestions', 0)}")
        return results


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    p = PeriodicSelfUpdater(llm=None, paeg=None)
    print("模块自检 OK（未启动线程，仅验证导入）")
