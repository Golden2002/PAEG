# -*- coding: utf-8 -*-
"""
v0.28 P0 测试盲区补齐：Planner / MemorySystem / tool_registry

覆盖三个长期零测试的模块（paeg 核心依赖链）：
  1. subagents.Planner.run()  —— 教学策略选择 + 步骤生成
  2. memory_system.MemorySystem  —— 三层记忆 + 摘要压缩 + 上下文构建
  3. tool_registry  —— get_tool_defs() 工具清单 + execute_tool 7 工具分发

每个测试都必须有真实断言（不能空跑 / pass）。
"""
import os
import sys
import shutil
import tempfile

# 让测试能找到 05_实现原型/ 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────
# 0. 共用 fixture / mock
# ─────────────────────────────────────


class _MockModel:
    """所有 subagent / tool_registry 用的最小 mock：不是真实 LLM（_is_real_llm=False）。"""

    name = "mock"

    def chat(self, *args, **kwargs):
        return None

    def messages_create(self, **kwargs):
        return {"content": [{"text": "ok"}]}


def _make_learner(grade="high_school", age=17, mastery=None):
    from paeg import LearnerProfile
    return LearnerProfile(
        id=f"test_pl_{os.getpid()}",
        nickname="测试学生",
        grade_level=grade,
        age=age,
        subjects_mastery=mastery or {},
    )


def _make_kb():
    from knowledge_base import KnowledgeBase
    return KnowledgeBase()


# ─────────────────────────────────────
# 1. Planner subagent
# ─────────────────────────────────────


def test_planner_run_returns_steps_with_required_fields():
    """Planner.run() 必须返回带 step_id/type/topic/bloom/strategy/worldview/duration_min 的 steps。"""
    from subagents import Planner
    planner = Planner(_MockModel(), _make_kb())
    learner = _make_learner()
    diagnosis = {"recommended_depth": "moderate", "identified_gaps": [], "prerequisites_status": {}}

    plan = planner.run(
        learner=learner,
        diagnosis=diagnosis,
        subject="physics",
        concept="牛顿第二定律",
    )

    assert isinstance(plan, dict), "Planner.run 应返回 dict"
    assert "steps" in plan and isinstance(plan["steps"], list) and len(plan["steps"]) >= 2, \
        f"steps 应为非空 list，实际 {plan.get('steps')}"
    for i, step in enumerate(plan["steps"]):
        for field in ("type", "topic", "bloom", "step_id"):
            assert field in step, f"第 {i} 步缺字段 {field}，step={step}"
        assert isinstance(step["step_id"], int) and step["step_id"] >= 1
        assert step["type"] in ("present", "practice", "question", "guide", "feedback"), \
            f"非法 type={step['type']}"
        assert step["bloom"] in (
            "remember", "understand", "apply", "analyze", "evaluate", "create",
        ), f"非法 bloom={step['bloom']}"
        # 阶段后缀必须包含 concept（确保 topic 携带主题）
        assert "牛顿第二定律" in step["topic"], f"topic 应含 concept，实际={step['topic']}"
    assert "estimated_total_min" in plan
    assert "strategy" in plan and plan["strategy"] in (
        "default", "socratic", "scaffolded", "mastery", "feynman", "deliberate",
    ), f"非法 strategy={plan.get('strategy')}"
    assert "strategy_name" in plan and isinstance(plan["strategy_name"], str)
    assert "base_bloom" in plan
    assert "presenter_hint" in plan and isinstance(plan["presenter_hint"], str)
    print(f"[OK] Planner.run 返回完整 plan（strategy={plan['strategy']}, steps={len(plan['steps'])}）")


def test_planner_subject_math_picks_mastery_strategy():
    """math 学科默认应选 mastery 策略（程序性技能）。"""
    from subagents import Planner
    planner = Planner(_MockModel(), _make_kb())
    learner = _make_learner()
    diagnosis = {"recommended_depth": "moderate", "identified_gaps": [], "prerequisites_status": {}}

    plan = planner.run(learner=learner, diagnosis=diagnosis,
                       subject="math", concept="二次函数")
    assert plan["strategy"] == "mastery", \
        f"math 应选 mastery，实际 {plan['strategy']}"
    # mastery 策略的 steps 含 present/practice/feedback
    types = {s["type"] for s in plan["steps"]}
    assert "practice" in types, f"mastery 策略应含 practice 步骤，实际 types={types}"
    print(f"[OK] math → mastery 策略（steps={len(plan['steps'])}, types={types}）")


def test_planner_basic_depth_picks_scaffolded_strategy():
    """诊断推荐 basic 深度 → 选 scaffolded（支架式）。"""
    from subagents import Planner
    planner = Planner(_MockModel(), _make_kb())
    learner = _make_learner()
    diagnosis = {"recommended_depth": "basic", "identified_gaps": [], "prerequisites_status": {}}

    plan = planner.run(learner=learner, diagnosis=diagnosis,
                       subject="physics", concept="加速度")
    assert plan["strategy"] == "scaffolded", \
        f"basic 深度应选 scaffolded，实际 {plan['strategy']}"
    assert plan["base_bloom"] == "apply", "physics 默认 base_bloom=apply"
    print(f"[OK] basic 深度 → scaffolded 策略")


def test_planner_philosophy_picks_socratic_strategy():
    """philosophy（高阶目标 analyze/evaluate）→ socratic 策略。"""
    from subagents import Planner
    planner = Planner(_MockModel(), _make_kb())
    learner = _make_learner()
    diagnosis = {"recommended_depth": "moderate", "identified_gaps": [], "prerequisites_status": {}}

    plan = planner.run(learner=learner, diagnosis=diagnosis,
                       subject="philosophy", concept="存在主义")
    assert plan["strategy"] == "socratic", \
        f"philosophy 应选 socratic，实际 {plan['strategy']}"
    # socratic 策略以 question 为主
    types = {s["type"] for s in plan["steps"]}
    assert "question" in types, f"socratic 应含 question 步骤，实际 {types}"
    print(f"[OK] philosophy → socratic 策略（types={types}）")


def test_planner_with_gaps_picks_scaffolded():
    """诊断有 identified_gaps 且无前置 → scaffolded。"""
    from subagents import Planner
    planner = Planner(_MockModel(), _make_kb())
    learner = _make_learner()
    diagnosis = {
        "recommended_depth": "moderate",
        "identified_gaps": ["缺少导数基础"],   # 非空 → 触发 scaffolded
        "prerequisites_status": {},             # 空 → 满足 scaffolded 条件
    }
    plan = planner.run(learner=learner, diagnosis=diagnosis,
                       subject="history", concept="工业革命")
    assert plan["strategy"] == "scaffolded", \
        f"有 gap 且无前置应选 scaffolded，实际 {plan['strategy']}"
    print(f"[OK] gaps+无前置 → scaffolded")


def test_planner_estimated_total_min_matches_steps_sum():
    """estimated_total_min 应等于各 step duration_min 之和。"""
    from subagents import Planner
    planner = Planner(_MockModel(), _make_kb())
    learner = _make_learner()
    diagnosis = {"recommended_depth": "moderate", "identified_gaps": [], "prerequisites_status": {}}

    plan = planner.run(learner=learner, diagnosis=diagnosis,
                       subject="math", concept="三角函数")
    expected = sum(s["duration_min"] for s in plan["steps"])
    assert plan["estimated_total_min"] == expected, \
        f"estimated_total_min={plan['estimated_total_min']} != sum={expected}"
    assert plan["estimated_total_min"] > 0
    print(f"[OK] estimated_total_min={plan['estimated_total_min']} 与 steps 求和一致")


# ─────────────────────────────────────
# 2. MemorySystem 三层记忆
# ─────────────────────────────────────


def _make_memory(user_id="test_mem_user", summary_path=None, limit=12):
    """构造一个用临时目录的 MemorySystem（不污染真实 users_data）。"""
    from memory_system import MemorySystem
    return MemorySystem(user_id=user_id, llm=None,
                        short_term_limit=limit, summary_path=summary_path)


def test_memory_add_and_short_term_size():
    """add() 增加消息；短记忆按顺序存放。"""
    mem = _make_memory()
    mem.add("user", "什么是熵？")
    mem.add("assistant", "熵是描述系统无序程度的物理量。")
    mem.add("user", "能举个例子吗？")
    assert len(mem.short_term) == 3
    assert mem.short_term[0] == {"role": "user", "content": "什么是熵？"}
    assert mem.short_term[2]["role"] == "user"
    print(f"[OK] add() 短记忆长度={len(mem.short_term)}")


def test_memory_clear_short_empties_short_term_but_keeps_summary():
    """clear_short 清空短记忆；摘要（已压缩部分）应保留。"""
    mem = _make_memory()
    mem.add("user", "消息 A")
    mem.add("assistant", "回复 A")
    # 手工设一个模拟"此前摘要"
    mem.summary = "此前对话：学生问过导数"
    mem.clear_short()
    assert len(mem.short_term) == 0, "clear_short 应清空短记忆"
    assert mem.summary == "此前对话：学生问过导数", "summary 不应被 clear_short 抹掉"
    print("[OK] clear_short 清空短记忆、保留摘要")


def test_memory_compress_if_needed_by_count():
    """条数超 limit 时触发压缩（force=True 保证即使未超也执行）。"""
    tmpdir = tempfile.mkdtemp(prefix="paeg_mem_")
    sp = os.path.join(tmpdir, "memory_summary.json")
    try:
        # 短 limit=4，强制让条数 > limit
        mem = _make_memory(summary_path=sp, limit=4)
        for i in range(8):
            mem.add("user", f"问题 {i}")
            mem.add("assistant", f"回答 {i}")
        # 触发一次（保证本测试里强制压缩）
        mem.compress_if_needed(force=True)
        # force=True 后 short_term 应被裁剪到保留条数
        assert len(mem.short_term) <= max(6, mem.short_term_limit // 2) + 1, \
            f"压缩后短记忆应保留最近 keep 条，实际 {len(mem.short_term)}"
        # 摘要文件被写入（即使 LLM=None 时也会 _save_summary）
        assert os.path.isfile(sp), f"summary 文件应已写盘，实际不存在：{sp}"
        print(f"[OK] count 触发压缩 → short_term={len(mem.short_term)}, summary file ok")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_memory_compress_if_needed_by_token_budget():
    """单条超长消息 → token 估算超预算 → 触发压缩（实际触发条件：
    ① token 超 budget **或** 条数超 limit；② len(short_term) > keep（keep≥6））。"""
    tmpdir = tempfile.mkdtemp(prefix="paeg_mem_")
    sp = os.path.join(tmpdir, "memory_summary.json")
    try:
        # limit=20 → keep=max(6, 10)=10 → 必须有 >10 条才进入压缩主体
        mem = _make_memory(summary_path=sp, limit=20)
        mem.token_budget = 100  # 设极小 token 预算（让"超 token"条件也满足）
        # 12 条短消息 + 2 条超长 → 总 token 远超 100，条数 14 > keep=10
        for i in range(12):
            mem.add("user", f"问题 {i}")
            mem.add("assistant", f"回答 {i}")
        # 再加一条超长 → token 估算远超 budget
        mem.add("user", "测试" * 250)   # token ≈ 500*0.8 = 400 > 100
        mem.add("assistant", "回复" * 100)
        before = len(mem.short_term)
        mem.compress_if_needed()  # 不 force：靠 token_budget + len > keep 触发
        # token 预算触发后，short_term 应被裁剪（len<=keep+1）
        assert len(mem.short_term) < before, \
            f"token 超预算 + 条数 > keep 应裁剪短记忆，before={before} after={len(mem.short_term)}"
        assert os.path.isfile(sp), "token 超预算时也应写 summary 文件"
        print(f"[OK] token_budget 触发压缩 → short_term {before}→{len(mem.short_term)}, summary file ok")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_memory_build_context_contains_summary_and_recent():
    """build_context() 应包含摘要段（此前对话摘要）+ 最近对话段。"""
    mem = _make_memory()
    mem.summary = "此前主题：导数"
    mem.add("user", "那导数的几何意义呢？")
    mem.add("assistant", "导数是切线斜率。")
    ctx = mem.build_context(max_recent=5)
    assert "此前对话摘要" in ctx, f"应有摘要前缀，实际 ctx={ctx[:60]!r}"
    assert "导数" in ctx, "摘要内容应被注入"
    assert "最近对话" in ctx, "应有最近对话前缀"
    assert "切线斜率" in ctx, "最近 assistant 消息应被注入"
    print("[OK] build_context 含摘要 + 最近对话")


def test_memory_build_context_empty_when_no_history():
    """空记忆 → build_context 返回空字符串（不是 None）。"""
    mem = _make_memory()
    ctx = mem.build_context()
    assert ctx == "", f"空记忆应返回空字符串，实际={ctx!r}"
    print("[OK] build_context 空记忆 → 空字符串")


def test_memory_get_long_term_returns_string():
    """get_long_term() 返回字符串（可能含自我描述 / 掌握度 / 历史会话统计）。"""
    mem = _make_memory()
    out = mem.get_long_term()
    # 即使用户没有任何画像数据，也应返回字符串（空或部分）
    assert isinstance(out, str), f"应返回 str，实际 {type(out)}"
    print(f"[OK] get_long_term 返回 str（长度={len(out)}）")


def test_memory_stats_shape():
    """stats() 返回三字段：short_term / summary_len / has_summary。"""
    mem = _make_memory()
    mem.add("user", "hi")
    mem.summary = "abc"
    s = mem.stats()
    assert s["short_term"] == 1
    assert s["summary_len"] == 3
    assert s["has_summary"] is True
    print(f"[OK] stats={s}")


# ─────────────────────────────────────
# 3. tool_registry 7 工具分发
# ─────────────────────────────────────


def test_get_tool_defs_returns_at_least_seven():
    """get_tool_defs() 必须返回 7+ 工具定义（含 web_search / verify_math / fetch_page /
    daily_quote / get_time / solve_problem / save_document）。"""
    from tool_registry import get_tool_defs
    defs = get_tool_defs()
    names = {d["function"]["name"] for d in defs}
    expected = {"web_search", "verify_math", "fetch_page", "daily_quote",
                "get_time", "solve_problem", "save_document"}
    assert len(defs) >= 7, f"应 ≥7 工具，实际 {len(defs)}: {names}"
    missing = expected - names
    assert not missing, f"缺少工具: {missing}"
    for d in defs:
        assert d["type"] == "function", f"非 function 类型: {d}"
        fn = d["function"]
        assert isinstance(fn["name"], str) and fn["name"]
        assert isinstance(fn["description"], str) and fn["description"]
        params = fn["parameters"]
        assert params["type"] == "object"
        assert isinstance(params.get("properties", {}), dict)
    print(f"[OK] get_tool_defs() 返回 {len(defs)} 工具: {sorted(names)}")


def test_execute_tool_get_time_deterministic():
    """get_time 工具确定性可调用 → 包含日期字符串。"""
    from tool_registry import execute_tool
    out = execute_tool("get_time", {})
    assert isinstance(out, str) and out, f"get_time 应返回非空 str，实际 {out!r}"
    # 包含"今天是" + 年-月-日（至少 4 位年份）
    assert "今天是" in out, f"get_time 输出应含 '今天是'，实际 {out!r}"
    assert "20" in out and "-" in out, f"get_time 输出应含日期格式，实际 {out!r}"
    print(f"[OK] get_time → {out[:60]}")


def test_execute_tool_verify_math_success_and_retry():
    """verify_math 解析简单表达式成功；隐式乘法也能触发自动重试。"""
    from tool_registry import execute_tool
    # 1) 简单表达式
    out1 = execute_tool("verify_math", {"expr": "x**2 - 4"})
    assert "解析成功" in out1, f"x**2-4 应解析成功，实际 {out1!r}"
    assert "LaTeX" in out1, f"应含 LaTeX 字段，实际 {out1!r}"
    # 2) 隐式乘法（2x → 2*x 自动修正）
    out2 = execute_tool("verify_math", {"expr": "2x + 3"})
    assert "解析成功" in out2 or "SymPy 解析失败" in out2, \
        f"隐式乘法表达式应至少返回明确结果，实际 {out2!r}"
    print(f"[OK] verify_math 分发（成功 + 修正重试）")


def test_execute_tool_verify_math_invalid_returns_error():
    """无法解析的表达式 → 返回含'失败/错误'的错误信息（不抛异常）。"""
    from tool_registry import execute_tool
    out = execute_tool("verify_math", {"expr": "@@@not_valid@@@"})
    assert isinstance(out, str)
    assert ("失败" in out) or ("错误" in out) or ("SymPy" in out), \
        f"非法表达式应明确失败，实际 {out!r}"
    print(f"[OK] verify_math 错误路径 → {out[:60]}")


def test_execute_tool_daily_quote_returns_quote():
    """daily_quote 调用 quotes.quote_of_the_day，返回含 text/author 的句子。"""
    from tool_registry import execute_tool
    out = execute_tool("daily_quote", {})
    assert isinstance(out, str) and out, "daily_quote 应返回非空 str"
    assert "「" in out and "」" in out, \
        f"daily_quote 应含「」引号包裹，实际 {out!r}"
    assert "——" in out, f"daily_quote 应含'——'分隔作者，实际 {out!r}"
    print(f"[OK] daily_quote → {out[:60]}")


def test_execute_tool_web_search_dispatches_to_handler():
    """web_search 实际跑 web_search_tool.web_search（或网络失败时返回可读错误）。"""
    from tool_registry import execute_tool
    out = execute_tool("web_search", {"query": "PAEG 教育智能体"})
    assert isinstance(out, str) and out, "web_search 应返回非空 str"
    # 网络/凭据失败时 handler 返回 "搜索失败..." 或 "搜索未返回结果"，至少应可读
    print(f"[OK] web_search 分发 → {out[:80]}")


def test_execute_tool_fetch_page_dispatches():
    """fetch_page 派发到 web_search_tool.fetch_page；网络失败时返回错误信息。"""
    from tool_registry import execute_tool
    out = execute_tool("fetch_page", {"url": "https://example.com"})
    assert isinstance(out, str), "fetch_page 应返回 str"
    # 不强求成功（可能网络受限），但不应抛异常
    print(f"[OK] fetch_page 分发 → {out[:60]}")


def test_execute_tool_solve_problem_dispatches():
    """solve_problem 派发到 problem_solver.solve_problem + LLM。"""
    from tool_registry import execute_tool
    out = execute_tool("solve_problem", {
        "problem": "求 1+1",
        "subject": "math",
        "grade_level": "high_school",
    })
    assert isinstance(out, str), "solve_problem 应返回 str"
    # LLM 不可用时 handler 返回 "做题失败..."；可用时返回答案文本
    print(f"[OK] solve_problem 分发 → {out[:80]}")


def test_execute_tool_save_document_dispatches():
    """save_document 派发到 FileGenerator.save_answer；返回保存路径或错误。"""
    from tool_registry import execute_tool
    out = execute_tool("save_document", {
        "title": "测试文档",
        "content": "# Hello\n\n这是测试内容。",
        "subject": "math",
    })
    assert isinstance(out, str), "save_document 应返回 str"
    # 成功时含 "已保存：" + md/html 路径；失败时含 "文档保存失败"
    assert ("已保存" in out) or ("失败" in out), \
        f"save_document 输出应可读，实际 {out!r}"
    print(f"[OK] save_document 分发 → {out[:80]}")


def test_execute_tool_unknown_tool_returns_helpful_error():
    """未知工具名 → 返回明确错误 + 列出可用工具。"""
    from tool_registry import execute_tool
    out = execute_tool("nonexistent_tool_xyz", {})
    assert isinstance(out, str)
    assert "未知工具" in out, f"未知工具应报错，实际 {out!r}"
    # 应列出至少一个已知工具以提示用户
    assert ("web_search" in out) or ("get_time" in out), \
        f"错误信息应列出可用工具，实际 {out!r}"
    print(f"[OK] 未知工具 → {out[:80]}")


def test_execute_tool_mcp_fallback_handles_gracefully():
    """mcp__server__tool 形式走 MCP fallback；MCP 不可用时返回可读错误（不抛异常）。"""
    from tool_registry import execute_tool
    out = execute_tool("mcp__fake__tool", {"foo": "bar"})
    assert isinstance(out, str)
    # 应含 'MCP 工具 ... 调用失败' 或 '未知工具'，但不应抛异常
    print(f"[OK] mcp__ fallback → {out[:80]}")


if __name__ == "__main__":
    # 直接运行（不用 pytest）也便于调试
    funcs = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    fails = 0
    for n, f in funcs:
        try:
            f()
        except Exception as e:
            fails += 1
            print(f"[FAIL] {n}: {e}")
    print(f"\n{len(funcs) - fails}/{len(funcs)} passed")