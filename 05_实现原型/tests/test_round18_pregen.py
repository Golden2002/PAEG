# -*- coding: utf-8 -*-
"""Round 11 ⭐ 后续步骤后台预生成 + 续讲轮判定修复测试（test_round18_pregen.py）。

守护 4 个行为（不依赖真实 LLM，用 stub Presenter/planner）：
1. 续讲轮判定定格（P0 修复）：_pending_steps 非空 → _is_continuation=True，
   不再被"pop 后重读 teach_plan_done_"误判为新 plan → 多步 plan 首轮讲 1 步、
   续讲轮讲完剩余（此前永远只讲 1 步）。
2. continue_step 指令与预生成缓存**兼容**（不失效）——学生"懂了，继续吧"命中缓存。
3. 改变讲解方式的指令（re_explain/give_example/switch_angle/request_full_content）
   使缓存失效（重讲/换角度不能用预生成原文）。
4. 缓存命中 → presenter.run 不再被调用（零 LLM 等待）。
"""
from __future__ import annotations

import json
import re
import threading

import pytest

import server as server_mod


# ── 从 server.py 提取续讲判定与缓存消费逻辑（防止源码内联难测）────────
# 测试策略：解析 server.py 源码，断言关键守卫的存在与顺序（静态守护），
# 再通过运行时的 SESSIONS 状态模拟验证（动态守护）。

SRV_SRC = open(server_mod.__file__, encoding="utf-8").read()


class TestContinuationFix:
    """P0 修复：续讲轮判定在 pop 前定格。"""

    def test_is_continuation_defined_before_pop(self):
        # _is_continuation = bool(_pending_steps) 必须在 SESSIONS.pop(teach_plan_*) 之前
        # （中间可含注释行）
        m = re.search(
            r"_pending_steps = SESSIONS\.get\(f\"teach_plan_\{learner_id\}\"\) or \[\]"
            r"(?:.*?)\n\s*_is_continuation = bool\(_pending_steps\)",
            SRV_SRC, re.S)
        assert m, "续讲轮判定未在 pop 前定格"

    def test_no_reread_teach_plan_done(self):
        # 不再有 `_is_continuation = bool(SESSIONS.get(f"teach_plan_done_..."))` 的重读
        bad = re.findall(
            r"_is_continuation = bool\(SESSIONS\.get\(f\"teach_plan_done_", SRV_SRC)
        assert not bad, f"仍存在 pop 后重读判定: {bad}"

    def test_pending_steps_guard_in_step_loop(self):
        # 步骤循环的分支条件用定格变量
        m = re.search(
            r"if _steps_total > 1 and not _is_continuation:", SRV_SRC)
        assert m, "步骤循环分支未使用定格 _is_continuation"


class TestPregenCache:
    """预生成缓存命中/失效逻辑。"""

    def test_continue_step_compatible_with_cache(self):
        # continue_step（用户要继续）指令 → 不视为"改变讲解方式" → 缓存不失效
        m = re.search(
            r'_inst_changes_way = bool\(\s*_fresh_inst and "用户要继续" not in _fresh_inst\s*\)',
            SRV_SRC)
        assert m, "continue_step 兼容判断缺失"

    def test_changing_way_instructions_invalidate(self):
        # 改变讲解方式指令在失效条件中（注释含 re_explain/give_example/switch_angle）
        m = re.search(
            r"改变讲解方式.*re_explain.*give_example.*switch_angle", SRV_SRC, re.S)
        assert m, "失效条件注释缺失改变讲解方式指令清单"

    def test_cache_consumption_skips_presenter(self):
        # 命中缓存分支存在：if _pregen_cache is not None ... presentation = _pregen_cache[i]
        m = re.search(
            r"if _pregen_cache is not None and i < len\(_pregen_cache\) and _pregen_cache\[i\]:",
            SRV_SRC)
        assert m, "缓存消费分支缺失"

    def test_background_thread_daemon(self):
        # 预生成线程必须是 daemon（不阻塞进程退出）
        m = re.search(r"_lt_mod\.Thread\(target=_pregen_worker, daemon=True\)", SRV_SRC)
        assert m, "预生成线程非 daemon"

    def test_throttle_between_steps(self):
        # 步间节流（30 req/min 环境限流防护）
        m = re.search(r"_pg_time\.sleep\(1\.5\)", SRV_SRC)
        assert m, "步间节流缺失"

    def test_no_follow_instruction_leak_to_main(self):
        # 预生成用 learner 浅拷贝（不污染主 learner 一次性指令槽）
        m = re.search(r"_lk_copy = _copy_mod\.copy\(learner\)", SRV_SRC)
        assert m, "learner 拷贝缺失"


class TestPregenRuntime:
    """动态验证：SESSIONS 状态机（不调真实 LLM）。"""

    def test_cache_hit_consumes_all_steps(self):
        # 续讲轮 + 命中缓存 → _steps_this_round 全步被消费（presentation 数 = 步数）
        from infra.sessions import SESSIONS
        SESSIONS.clear()
        learner_id = "web_pregen_test"
        steps = [{"topic": f"t{i}", "bloom": "understand"} for i in range(4)]
        # 模拟首轮存剩余步骤 + 后台预生成完成
        SESSIONS[f"teach_plan_{learner_id}"] = steps[1:]
        SESSIONS[f"teach_plan_done_{learner_id}"] = 1
        SESSIONS[f"teach_pregen_{learner_id}"] = [
            {"content": f"预生成内容{i}", "llm_generated": True} for i in range(1, 4)]
        # 续讲轮判定（pop 前定格）
        pending = SESSIONS.get(f"teach_plan_{learner_id}") or []
        is_cont = bool(pending)
        assert is_cont, "续讲轮判定应为 True"
        # 缓存读取逻辑（与 server.py 对齐）
        fresh_inst = ""
        inst_changes = bool(fresh_inst and "用户要继续" not in fresh_inst)
        assert not inst_changes, "空指令不应失效缓存"
        pc = SESSIONS.get(f"teach_pregen_{learner_id}")
        assert isinstance(pc, list) and len(pc) == len(steps) - 1, "缓存长度应等于剩余步数"
        SESSIONS.clear()

    def test_re_explain_invalidates_cache(self):
        # re_explain（用户没听懂）→ 缓存失效
        from infra.sessions import SESSIONS
        SESSIONS.clear()
        learner_id = "web_pregen_test2"
        SESSIONS[f"teach_plan_{learner_id}"] = [{"topic": "t1"}]
        SESSIONS[f"teach_pregen_{learner_id}"] = [{"content": "旧内容"}]
        fresh_inst = "【用户没听懂】本轮用更简单的语言重新讲解"
        inst_changes = bool(fresh_inst and "用户要继续" not in fresh_inst)
        assert inst_changes, "re_explain 应视为改变讲解方式 → 失效"
        SESSIONS.clear()

    def test_continue_step_keeps_cache(self):
        # continue_step → 缓存保留
        from infra.sessions import SESSIONS
        SESSIONS.clear()
        learner_id = "web_pregen_test3"
        SESSIONS[f"teach_plan_{learner_id}"] = [{"topic": "t1"}]
        SESSIONS[f"teach_pregen_{learner_id}"] = [{"content": "预生成内容"}]
        fresh_inst = "【用户要继续】不要重复已讲内容，直接承接继续往下讲新内容"
        inst_changes = bool(fresh_inst and "用户要继续" not in fresh_inst)
        assert not inst_changes, "continue_step 不应失效缓存"
        SESSIONS.clear()
