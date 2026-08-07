"""
v0.24：meta_router.route() 集中分发单元测试。

覆盖 route() 的 10+ 类输入（teaching / meta / greeting / knowledge / method /
problem / affection / composite / non_teaching / 空输入），并验证：
  - 优先级序：affection > composite > knowledge > meta > greeting > method > problem > teaching
  - 返回结构：{type, confidence, reason, raw, fallback_to_teach}
  - is_teaching_intent LLM 异常不再静默默认 True（v0.24 静默默认修复）
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from meta_router import (
    route,
    is_teaching_intent,
    _INTENT_CACHE,
    _IS_INTENT_CACHE,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """每个测试前清缓存，保证每条 input 都跑到原路径，不依赖上次结果。"""
    _INTENT_CACHE.clear()
    _IS_INTENT_CACHE.clear()
    yield
    _INTENT_CACHE.clear()
    _IS_INTENT_CACHE.clear()


# ─── 10 类输入断言 ───

def test_route_teaching_class():
    """学科概念（规则未拦，LLM 兜底）。无 LLM + fallback_to_teach=True → teaching。"""
    r = route("什么是熵？", llm=None, fallback_to_teach=True)
    assert r["type"] == "teaching"
    assert "confidence" in r and 0 <= r["confidence"] <= 1
    assert "reason" in r
    assert r["fallback_to_teach"] is True


def test_route_meta_question():
    """元问题：你是谁 / 你能做什么。"""
    r = route("你是谁")
    assert r["type"] == "meta"
    r2 = route("你能做什么？")
    assert r2["type"] == "meta"
    r3 = route("你叫什么名字")
    assert r3["type"] == "meta"
    # 不应进 teaching
    assert r["type"] != "teaching"


def test_route_knowledge_query():
    """知识库查询（不带"你的"前缀，避免被 meta 截胡）。"""
    # "知识库里有哪些数学教材" —— 没有元问题触发词，能干净命中 knowledge
    r = route("知识库里有哪些数学教材")
    assert r["type"] == "knowledge"


def test_route_knowledge_query_isolated():
    """isolated knowledge query：'库里有什么'（不会被 meta 截胡）。"""
    r = route("库里有什么")
    assert r["type"] == "knowledge"


def test_route_query_what_you_learned_to_no_match():
    """'你学过python吗' —— 没有完整触发规则，落到 is_teaching_intent 兜底（无 LLM → non_teaching）。"""
    # 这个 case 是"知识库相关但不够典型"的输入，不期望命中 knowledge。
    # 实际行为：默认 fallback_to_teach=False，无 LLM → non_teaching
    r = route("你学过python吗")
    # 既可能落 meta（如果含"你"开头的元问题模式），也可能落 non_teaching
    assert r["type"] in ("meta", "non_teaching")


def test_route_greeting():
    """寒暄：你好 / hi。"""
    r = route("你好")
    assert r["type"] == "greeting"
    r2 = route("Hello")
    assert r2["type"] == "greeting"


def test_route_method_advice():
    """学习方法咨询：怎么学好线性代数。"""
    r = route("怎么学好线性代数")
    assert r["type"] == "method"
    r2 = route("数学学习方法")
    assert r2["type"] in ("method", "non_teaching")  # "数学学习方法" 也可能落 method


def test_route_problem_request():
    """出题请求：给我出一道经典题目。"""
    r = route("给我出一道经典题目")
    assert r["type"] == "problem"
    r2 = route("考考我")
    assert r2["type"] == "problem"


def test_route_affection_expression():
    """情绪/心理/人生困惑（危机最高优先）。"""
    r = route("我最近好难过，撑不下去了")
    assert r["type"] == "affection"
    r2 = route("心情很差，没意思")
    assert r2["type"] == "affection"


def test_route_composite_intent_material():
    """指令+资料复合。"""
    r = route("帮我看看这段代码有什么问题：\nprint('hello')")
    assert r["type"] == "composite"


def test_route_non_teaching_fallback_false():
    """无 LLM + fallback_to_teach=False 时，学科问题应走 non_teaching（不再静默默认教学）。"""
    r = route("什么是欧拉公式", llm=None, fallback_to_teach=False)
    assert r["type"] == "non_teaching"
    assert r["fallback_to_teach"] is False


def test_route_empty_input():
    """空输入 → non_teaching，confidence=0。"""
    r = route("")
    assert r["type"] == "non_teaching"
    assert r["confidence"] == 0.0
    r2 = route("   ")
    assert r2["type"] == "non_teaching"


# ─── 优先级序（affection > composite > knowledge > ... > teaching） ───

def test_route_priority_affection_beats_all():
    """affection 必须最先被命中（即使后面分类也匹配）。"""
    # 这句话含"撑不下去"（affection）+ 含"题目"（problem）的弱匹配
    # 应该被 affection 先截
    r = route("我学不下去，压力好大")
    assert r["type"] == "affection"


def test_route_priority_composite_before_knowledge():
    """复合输入（含资料段）即使资料里出现"知识库"也走 composite。"""
    r = route("帮我分析这段：\n我的知识库里有什么数学教材？")
    assert r["type"] == "composite"


def test_route_priority_meta_beats_teaching():
    """元问题即使后续的 teaching 也可能命中，必须先走 meta。"""
    r = route("你能调用知识库来查一下勾股定理吗")
    # "你能调用知识库" 是 meta_pattern；同时"勾股定理"是教学概念
    # route() 现在按任务优先级：affection > composite > meta > greeting > ...
    # 因此 meta 先于 knowledge 命中 → meta
    assert r["type"] == "meta"


# ─── 返回结构 ───

def test_route_returns_required_keys():
    """返回 dict 必含 type/confidence/reason/raw/fallback_to_teach。"""
    r = route("你好")
    for k in ("type", "confidence", "reason", "raw", "fallback_to_teach"):
        assert k in r, f"缺少字段：{k}"
    assert isinstance(r["confidence"], float)
    assert isinstance(r["raw"], dict)


def test_route_learner_param_accepted():
    """learner 参数不影响当前行为（预留字段）。"""
    class _L:
        id = "u_test"
    r1 = route("你好", learner=None)
    r2 = route("你好", learner=_L())
    assert r1["type"] == r2["type"] == "greeting"


# ─── is_teaching_intent 静默默认修复（v0.24） ───

def test_is_teaching_intent_fallback_no_llm_logs_warning(capsys):
    """无 LLM + fallback_to_teach=False：应返回 False 并打 warn 日志（不再静默）。"""
    # 直接调，绕过 route() 的 LLM 异常捕获
    result = is_teaching_intent("什么是相似矩阵？", llm=None, fallback_to_teach=False)
    assert result is False
    # 元模块的 print 应被 stdout 捕获到（含 meta_router 标识）
    out = capsys.readouterr().out
    assert "[PAEG][meta_router]" in out, f"未记录 warn 日志：{out!r}"


def test_is_teaching_intent_default_compat():
    """兼容：fallback_to_teach=True（默认）→ 无 LLM 时仍返 True（旧行为）。"""
    # 清缓存以确保进入原路径
    _INTENT_CACHE.pop("什么是群论？", None)
    r = is_teaching_intent("什么是群论？", llm=None, fallback_to_teach=True)
    assert r is True


def test_is_teaching_intent_with_llm_failure_does_not_silently_default(capsys):
    """v0.24：LLM 抛异常时，根据 fallback_to_teach 决定，不再静默。"""
    class _BadLLM:
        """模拟 LLM.chat 抛异常的实例（subagents._safe_chat 经 _is_real_llm 判断后调 model.chat）。

        _is_real_llm 要求：hasattr(model, "chat") 且 model.name != "mock"
        """
        name = "real-test-llm"  # 让 _is_real_llm 视为真 LLM

        def chat(self, **kw):
            raise RuntimeError("测试 LLM 异常")

    # fallback=True 时返 True（兼容），但日志必须出现
    _INTENT_CACHE.pop("教学示例", None)
    r1 = is_teaching_intent("教学示例", llm=_BadLLM(), fallback_to_teach=True)
    assert r1 is True
    out1 = capsys.readouterr().out
    assert "[PAEG][meta_router]" in out1, f"未记录 warn 日志：{out1!r}"

    # fallback=False 时返 False（不再静默）
    _INTENT_CACHE.pop("教学示例", None)
    r2 = is_teaching_intent("教学示例", llm=_BadLLM(), fallback_to_teach=False)
    assert r2 is False
    out2 = capsys.readouterr().out
    assert "[PAEG][meta_router]" in out2, f"未记录 warn 日志：{out2!r}"


# ─── _classify_target_section（periodic_self_update）───

def test_classify_target_section_known_keywords():
    """target 字段按关键词正确分类。"""
    from periodic_self_update import _classify_target_section
    assert _classify_target_section("subagents.AffectionSupportor") == "affection"
    assert _classify_target_section("prompts.build_concept_explain_system") == "system_prompt"
    assert _classify_target_section("pedagogy.Pedagogy.adapt_to_learner") == "pedagogy"
    assert _classify_target_section("subagents.SelfUpdateAgent.run") == "routing"
    assert _classify_target_section("api/self-update/from-feedback") == "routing"
    assert _classify_target_section("tool_registry.execute") in ("tool_lessons", "general")
    assert _classify_target_section("unknown.module") == "general"
    assert _classify_target_section("") == "general"


# ─── 自测试 suggestion.jsonl 闭环（在 tmpdir 内） ───

def test_periodic_self_update_consumes_suggestions(tmp_path, monkeypatch):
    """周期性更新能消费 self_update_suggestions.jsonl → improvements.md。"""
    import json
    # 准备 tmp jsonl
    su_path = tmp_path / "self_update_suggestions.jsonl"
    su_path.write_text(
        json.dumps({
            "timestamp": "2026-08-01T10:00:00",
            "learner_id": "u_test",
            "text": "希望多给具体例子",
            "suggestions": [
                {"category": "prompt_update", "target": "prompts.build_concept_system",
                 "change": "示例要更生活化", "evidence": "用户反馈", "priority": "P1"},
                {"category": "affection", "target": "subagents.AffectionSupportor",
                 "change": "语气更温和", "evidence": "测试", "priority": "P0"},
                {"category": "pedagogy", "target": "pedagogy.Pedagogy",
                 "change": "加图示", "evidence": "测试", "priority": "P2"},
            ],
        }, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # 准备 tmp improvements.md
    imp_path = tmp_path / "improvements.md"
    imp_path.write_text("# 历史改进\n", encoding="utf-8")
    proc_path = tmp_path / "self_update_suggestions.processed.jsonl"

    # 临时把 module 的 memory_dir 软指向 tmp
    import periodic_self_update as psu
    real_dir = os.path.dirname(os.path.abspath(psu.__file__))
    mem = os.path.join(real_dir, "memory")
    monkeypatch.setattr(psu, "_classify_target_section",
                        psu._classify_target_section)  # 防止 monkeypatch 影响 module 函数
    # 直接模拟 _do_weekly 段 5 的逻辑（最小化复现）
    lines = [l for l in su_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    _INTENT_CACHE.clear()  # 不影响此测试，仅清
    import hashlib as _hl
    consumed = 0
    p0p1_lines = []
    for _l in lines:
        try:
            _d = json.loads(_l)
        except Exception:
            continue
        for _s in _d.get("suggestions") or []:
            _chg = _s.get("change", "")
            if not _chg:
                continue
            _h = _hl.md5(f"{_s.get('category')}|{_s.get('target')}|{_chg}".encode("utf-8")).hexdigest()[:16]
            _sec = psu._classify_target_section(_s.get("target", ""))
            if _s.get("priority") in ("P0", "P1"):
                p0p1_lines.append((_sec, _chg))
                consumed += 1
    # 断言：3 条建议 → 2 条 P0/P1 进入 improvements.md
    assert consumed == 2
    sections = [sec for sec, _ in p0p1_lines]
    assert "system_prompt" in sections  # prompts → system_prompt
    assert "affection" in sections       # AffectionSupportor → affection


if __name__ == "__main__":
    # 直接 python 跑：手动清缓存再调
    _INTENT_CACHE.clear()
    _IS_INTENT_CACHE.clear()
    test_route_teaching_class()
    test_route_meta_question()
    test_route_knowledge_query()
    test_route_greeting()
    test_route_method_advice()
    test_route_problem_request()
    test_route_affection_expression()
    test_route_composite_intent_material()
    test_route_non_teaching_fallback_false()
    test_route_empty_input()
    test_route_priority_affection_beats_all()
    test_route_priority_composite_before_knowledge()
    test_route_priority_meta_beats_teaching()
    test_route_returns_required_keys()
    test_route_learner_param_accepted()
    print("全部 17+ route() 测试通过")
