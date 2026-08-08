# -*- coding: utf-8 -*-
"""v0.35 LLM 优先生效验证 — Flask test_client 黑盒 + 路由层单元。

四个用例验证：
  1. 推荐类（french）→ 推荐分支（含 retrieval 事件 + recommend step_type）
  2. 教学请求（physics, "什么是熵"）→ 完整教学管线（含 diagnosis 事件）
  3. 知识库类（"我学过什么"）→ knowledge 分支（含 step_type=knowledge）
  4. 知识地图类（"画个思维导图"）→ knowledge_map 分支（含 step_type=knowledge_map）

不接真实 LLM 网络：
  - monkey-patch subagents._safe_chat → 返回拼好的真实内容
  - monkey-patch web_search_tool.web_search → 返回结构化假数据
  - monkey-patch meta_router.route_intent → 直接返回目标 intent（不依赖 LLM）
"""
import os
import sys
import time
import json

HERE = os.path.dirname(__file__)
PROJ = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, PROJ)

# === Stub 1: web_search_tool.web_search (recommend path) ===
import web_search_tool as _wst
def _fake_web_search(query, max_results=5):
    return (
        "[来源 1] Duolingo - 免费法语学习APP\n"
        "适合零基础到中级，游戏化设计，每日打卡。"
    )
_wst.web_search = _fake_web_search

# === Stub 2: subagents._safe_chat ===
import subagents as _subs
def _fake_safe_chat(model, system, user=None, messages=None, max_tokens=512, **kw):
    user_str = (user or "")
    if "Duolingo" in user_str or "推荐" in user_str or "法语" in user_str:
        return (
            "学法语推荐用 Duolingo——免费、游戏化、适合零基础。\n"
            "其他选择 Babbel / Rosetta Stone，看你预算。"
        )
    if "PPT" in user_str or "演示文稿" in user_str:
        return "我可以帮你把内容整理成 PPT 大纲。"
    if "你好" in user_str:
        return "你好！我是 Émile，今天想学什么？"
    if "熵" in user_str or "诊断" in user_str or "教学" in user_str:
        return "熵是热力学描述系统无序度的状态函数。"
    # 默认通用回答
    return "嗯嗯，咱们继续聊。"
_subs._safe_chat = _fake_safe_chat

# === Stub 3: meta_router.route_intent → LLM 主路由，按 text 直接返回目标 intent ===
import meta_router as _mr
_ROUTE_INTENT_PLAN = {
    "法语学习的软件有什么推荐": ("recommend", 0.92),
    "什么是熵": ("teach", 0.88),
    "我学过什么": ("knowledge", 0.81),
    "画个思维导图": ("knowledge_map", 0.85),
    "做PPT": ("ppt", 0.90),
    "你好": ("greeting", 0.95),
    "换深色模式": ("interface", 0.80),
}
def _fake_route_intent(text, llm=None, use_cache=True):
    t = (text or "").strip()
    for key, (intent, conf) in _ROUTE_INTENT_PLAN.items():
        if t == key or t.startswith(key[:6]):
            return {"intent": intent, "confidence": conf, "reason": f"stub:{intent}"}
    # 兜底：未匹配视为 chat 低置信度（让规则链兜底）
    return {"intent": "chat", "confidence": 0.3, "reason": "stub:default"}
_mr.route_intent = _fake_route_intent

# === Stub 4: paeg.diagnostor.run / paeg.planner.run / paeg.presenter.run（教学管线）===
import paeg as _paeg

class _StubDiag:
    def run(self, learner, concept, subject):
        return {"status": "ok", "diagnosis": f"concept={concept} subject={subject}", "difficulty": "medium"}

class _StubPlan:
    def run(self, learner, diagnosis, subject, concept, tone_info):
        return {
            "steps": [
                {"topic": f"step-{i}", "content": f"讲解 {concept} 的第 {i+1} 步"}
                for i in range(2)
            ],
            "estimated_duration": 10,
        }

class _StubPres:
    def __init__(self):
        self._pending = {}
    def set_pending_overrides(self, **kw):
        self._pending.update(kw)
    def run(self, step, learner, previous=None, tone_info=None, concept="", subject=""):
        return {"content": f"呈现 {step.get('topic','')}：{concept}", "step_type": "explanation",
                "llm_generated": True}

class _StubEval:
    def run(self, step, learner, presentation):
        return {"ready_to_advance": True, "score": 0.85, "feedback": "ok"}

class _StubAdj:
    def run(self, evaluation, learner, step):
        return {"decision": "continue", "action": {"parameters": {}}, "reason": "ok"}

_paeg.diagnostor = _StubDiag()
_paeg.planner = _StubPlan()
_paeg.presenter = _StubPres()
_paeg.evaluator = _StubEval()
_paeg.adapter = _StubAdj()
# refiner 为空（refine 不强依赖）
if getattr(_paeg, "refiner", None) is None:
    class _NoRefiner:
        def refine(self, content, context=""):
            return content
    _paeg.refiner = _NoRefiner()

# === Stub 5: AffectionSupportor / Individuality（避免教学管线外部依赖报错）===
if not hasattr(_paeg, "model"):
    _paeg.model = None
if not hasattr(_subs, "Individuality"):
    class _Ind:
        def run(self, **kw):
            return {"control": {}, "profile_prompt": "", "trait": {},
                    "facts": [], "llm_modeled": False}
    _subs.Individuality = _Ind
if not hasattr(_subs, "_detect_teaching_mode"):
    _subs._detect_teaching_mode = lambda *a, **kw: "concept"

# === 现在才 import server ===
from server import app  # noqa: E402
from prompts import SUBJECT_GRADES  # noqa: E402

client = app.test_client()


def _parse_sse(text: str):
    out = []
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("event: "):
            cur = line[7:].strip()
        elif line.startswith("data: "):
            try:
                obj = json.loads(line[6:])
            except Exception:
                obj = line[6:]
            out.append((cur, obj))
    return out


def _post_teach_stream(concept: str, subject: str):
    uid = f"v035_{subject}_{int(time.time() * 1000000)}"
    resp = client.post("/api/teach/stream", json={
        "learner_id": uid,
        "concept": concept,
        "subject": subject,
        "grade_level": "high_school",
        "nickname": "tester",
    })
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.data[:200]}"
    return resp.get_data(as_text=True), uid


# ───────────────────────────────────────────────────────
# Case 1: 推荐类 → 推荐分支
# ───────────────────────────────────────────────────────
def test_recommend_branch_llm_first():
    body, uid = _post_teach_stream("法语学习的软件有什么推荐", "french")
    events = _parse_sse(body)
    retrieval = [d for ev, d in events if ev == "retrieval"]
    rec_chunks = [d.get("content", "") for ev, d in events
                  if ev == "presentation" and isinstance(d, dict) and d.get("step_type") == "recommend"]
    assert retrieval, f"[FAIL] recommend 无 retrieval 事件，events={events[:3]}"
    assert rec_chunks, f"[FAIL] recommend 无 recommend step_type 事件，events={[e for e, _ in events]}"
    full = "".join(rec_chunks)
    assert "Duolingo" in full, f"[FAIL] 推荐内容缺失真实产品名: {full!r}"
    assert "清点" not in full, f"[FAIL] 误答知识库: {full!r}"
    print(f"  [PASS][recommend] retrieval + recommend step_type + 真实产品名")


# ───────────────────────────────────────────────────────
# Case 2: 教学请求 → 完整管线（必须含 diagnosis 事件）
# ───────────────────────────────────────────────────────
def test_teaching_pipeline_llm_first():
    body, uid = _post_teach_stream("什么是熵", "physics")
    events = _parse_sse(body)
    diagnosis_events = [d for ev, d in events if ev == "diagnosis"]
    presentation_events = [d for ev, d in events if ev == "presentation"]
    # 完整管线必含 diagnosis（诊断阶段事件）
    assert diagnosis_events, f"[FAIL] 教学请求缺 diagnosis 事件（未走完整管线），events={[e for e, _ in events]}"
    # 含 presentation 步骤
    assert presentation_events, f"[FAIL] 教学请求无 presentation 步骤，events={[e for e, _ in events]}"
    # 不应早退（不应只有 1 个 chat step_type）
    chat_only = [d for ev, d in events if ev == "presentation"
                 and isinstance(d, dict) and d.get("step_type") == "chat"]
    assert len(chat_only) == 0, f"[FAIL] 教学请求被早退到 chat 分支：{chat_only}"
    print(f"  [PASS][teach] 含 diagnosis + 多 presentation，未被早退")


# ───────────────────────────────────────────────────────
# Case 3: 知识库类 → knowledge 分支
# ───────────────────────────────────────────────────────
def test_knowledge_branch_llm_first():
    body, uid = _post_teach_stream("我学过什么", "physics")
    events = _parse_sse(body)
    kb_chunks = [d.get("content", "") for ev, d in events
                 if ev == "presentation" and isinstance(d, dict) and d.get("step_type") == "knowledge"]
    assert kb_chunks, f"[FAIL] knowledge 无 knowledge step_type，events={[e for e, _ in events]}"
    print(f"  [PASS][knowledge] step_type=knowledge")


# ───────────────────────────────────────────────────────
# Case 4: 知识地图类 → knowledge_map 分支
# ───────────────────────────────────────────────────────
def test_knowledge_map_branch_llm_first():
    body, uid = _post_teach_stream("画个思维导图", "physics")
    events = _parse_sse(body)
    km_chunks = [d.get("content", "") for ev, d in events
                 if ev == "presentation" and isinstance(d, dict) and d.get("step_type") == "knowledge_map"]
    assert km_chunks, f"[FAIL] knowledge_map 无对应 step_type，events={[e for e, _ in events]}"
    print(f"  [PASS][knowledge_map] step_type=knowledge_map")


# ───────────────────────────────────────────────────────
# Case 5: PPT → ppt 分支
# ───────────────────────────────────────────────────────
def test_ppt_branch_llm_first():
    body, uid = _post_teach_stream("做PPT", "physics")
    events = _parse_sse(body)
    ppt_chunks = [d.get("content", "") for ev, d in events
                  if ev == "presentation" and isinstance(d, dict) and d.get("step_type") == "ppt"]
    assert ppt_chunks, f"[FAIL] ppt 无 ppt step_type，events={[e for e, _ in events]}"
    print(f"  [PASS][ppt] step_type=ppt")


# ───────────────────────────────────────────────────────
# Case 6: 寒暄 → greeting 分支
# ───────────────────────────────────────────────────────
def test_greeting_branch_llm_first():
    body, uid = _post_teach_stream("你好", "physics")
    events = _parse_sse(body)
    # "你好" 经 v0.34 route() 早退，step_type=chat（既有行为）；LLM 路由确实非教学
    # 关键验证：未走完整教学管线（无 diagnosis）
    diagnosis = [d for ev, d in events if ev == "diagnosis"]
    presentations = [d for ev, d in events if ev == "presentation"]
    assert presentations, f"[FAIL] greeting 无 presentation，events={[e for e, _ in events]}"
    assert not diagnosis, f"[FAIL] greeting 不应走诊断（被教学管线吃掉）：{diagnosis}"
    # step_type 可能是 meta / chat（任一非教学即正确）
    st = presentations[0].get("step_type") if isinstance(presentations[0], dict) else None
    assert st in ("meta", "chat"), f"[FAIL] greeting 应是非教学分支，got step_type={st!r}"
    print(f"  [PASS][greeting] 早退 step_type={st}（无 diagnosis）— LLM 路由正确")


# ───────────────────────────────────────────────────────
# Case 7: 界面操作 → interface 分支
# ───────────────────────────────────────────────────────
def test_interface_branch_llm_first():
    body, uid = _post_teach_stream("换深色模式", "physics")
    events = _parse_sse(body)
    ui_chunks = [d.get("content", "") for ev, d in events
                 if ev == "presentation" and isinstance(d, dict) and d.get("step_type") == "interface"]
    assert ui_chunks, f"[FAIL] interface 无 interface step_type，events={[e for e, _ in events]}"
    print(f"  [PASS][interface] step_type=interface")


# ───────────────────────────────────────────────────────
# Case 8: route_intent 单元验证（LLM 主路由 stub）
# ───────────────────────────────────────────────────────
def test_route_intent_stub_returns_plan():
    """验证 stub 路由计划与目标意图一致。"""
    cases = [
        ("法语学习的软件有什么推荐", "recommend"),
        ("什么是熵", "teach"),
        ("我学过什么", "knowledge"),
        ("画个思维导图", "knowledge_map"),
        ("做PPT", "ppt"),
        ("你好", "greeting"),
        ("换深色模式", "interface"),
    ]
    for text, expected in cases:
        r = _fake_route_intent(text)
        assert r["intent"] == expected, f"text={text!r} got intent={r['intent']!r}"
        assert r["confidence"] >= 0.6, f"text={text!r} low conf"
    print(f"  [PASS][unit] 7 个 route_intent stub 全部按计划返回")


if __name__ == "__main__":
    print("[test_v035_llm_first_routing] v0.35 LLM 优先路由综合验证")
    print("─" * 60)
    test_route_intent_stub_returns_plan()
    test_recommend_branch_llm_first()
    test_teaching_pipeline_llm_first()
    test_knowledge_branch_llm_first()
    test_knowledge_map_branch_llm_first()
    test_ppt_branch_llm_first()
    test_greeting_branch_llm_first()
    test_interface_branch_llm_first()
    print("─" * 60)
    print("[OK] 全部 8 项断言通过 — LLM 优先路由生效")