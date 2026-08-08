# -*- coding: utf-8 -*-
"""v0.35 推荐类问题分支验证 — Flask test_client 黑盒。

不接真实 LLM 网络：
  - monkey-patch web_search_tool.web_search → 返回结构化假数据（含 Duolingo/Babbel/Rosetta Stone）
  - monkey-patch subagents._safe_chat → 返回拼好的真实推荐文本

断言：
  1. teach_stream 响应 SSE 含 `event: retrieval`（前端 badge 触发）
  2. 含 `step_type: recommend` 的 presentation
  3. 回答内容含真实产品名（不含"清点藏书"等答非所问）
"""
import os
import sys
import time
import json

HERE = os.path.dirname(__file__)
PROJ = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, PROJ)

# === Stub 1: web_search_tool.web_search ===
import web_search_tool as _wst
def _fake_web_search(query: str, max_results: int = 5) -> str:
    return (
        "[来源 1] Duolingo - 免费法语学习APP\n"
        "URL: https://www.duolingo.com\n"
        "适合零基础到中级，游戏化设计，每日打卡。\n\n"
        "[来源 2] Babbel - 系统化法语课程\n"
        "URL: https://www.babbel.com\n"
        "侧重口语对话，10-15分钟一节课，备考/旅游实用。\n\n"
        "[来源 3] Rosetta Stone - 沉浸式学习\n"
        "URL: https://www.rosettastone.com\n"
        "全部用法语学法语，沉浸式训练发音与听力。"
    )
_wst.web_search = _fake_web_search

# === Stub 2: subagents._safe_chat ===
import subagents as _subs
def _fake_safe_chat(model, system, user=None, messages=None, max_tokens=512, **kw):
    """模拟 LLM 收到检索资料后拼出真实推荐。"""
    return (
        "学法语常用的几款 APP，按水平给你分一下：\n\n"
        "1. **Duolingo**（零基础友好）—— 免费、游戏化、每日打卡，适合培养语感。\n"
        "2. **Babbel**（想练口语）—— 10-15 分钟一节，侧重日常对话，旅游/通勤很合适。\n"
        "3. **Rosetta Stone**（追求沉浸）—— 全法语教学，训练发音和语感。\n\n"
        "你是零基础还是想考级？我可以更精准地推。"
    )
_subs._safe_chat = _fake_safe_chat

# === 现在才 import server（确保 monkey-patch 已生效）===
from server import app  # noqa: E402

client = app.test_client()


def _parse_sse(text: str):
    """简化版 SSE 解析：返回 events = [(event_name, data_dict), ...]"""
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


def test_teach_stream_recommend_branch():
    """teach_stream：'法语学习的软件有什么推荐' → 走推荐分支，发 retrieval badge + recommend step_type。"""
    uid = f"v035_rec_{int(time.time() * 1000)}"
    resp = client.post("/api/teach/stream", json={
        "learner_id": uid,
        "concept": "法语学习的软件有什么推荐",
        "subject": "french",
        "grade_level": "high_school",
        "nickname": "tester",
    })
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.data[:200]}"
    assert resp.mimetype == "text/event-stream", f"mimetype={resp.mimetype}"

    body = resp.get_data(as_text=True)
    events = _parse_sse(body)

    # 断言 1：存在 retrieval 事件
    retrieval_events = [d for ev, d in events if ev == "retrieval"]
    assert retrieval_events, f"无 retrieval 事件，events={events[:5]}"
    badge = retrieval_events[0].get("done", "")
    print(f"  [PASS] retrieval badge = {badge!r}")

    # 断言 2：存在 step_type=recommend 的 presentation 事件
    rec_chunks = []
    for ev, d in events:
        if ev == "presentation":
            if isinstance(d, dict) and d.get("step_type") == "recommend":
                rec_chunks.append(d.get("content", ""))
    assert rec_chunks, f"无 recommend 类型的 presentation；all events={[e for e, _ in events]}"
    full_answer = "".join(rec_chunks)
    print(f"  [PASS] recommend 回答 (head) = {full_answer[:80]!r}")

    # 断言 3：含真实推荐（来自检索结果），不含答非所问"清点藏书"
    assert "Duolingo" in full_answer or "Babbel" in full_answer or "Rosetta Stone" in full_answer, \
        f"回答缺真实产品名: {full_answer!r}"
    assert "清点" not in full_answer and "藏书" not in full_answer, \
        f"误答知识库风格: {full_answer!r}"
    print("  [PASS] 回答含真实产品名，未答非所问")

    # 断言 4：存在 done 事件收尾
    done_events = [d for ev, d in events if ev == "done"]
    assert done_events, "无 done 事件"
    print(f"  [PASS] done 事件 = {done_events[0]!r}")


if __name__ == "__main__":
    print("[test_v035_recommend_branch] 验证推荐类问题早退分支")
    print("─" * 60)
    test_teach_stream_recommend_branch()
    print("─" * 60)
    print("[OK] 全部断言通过")
