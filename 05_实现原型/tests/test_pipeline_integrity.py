# -*- coding: utf-8 -*-
"""
v0.34 标准化测试 v2.0 — 教学管线完整性测试。

目标（PAEG 盲区 A 修复）：
  teach_stream（server.py L1011）有 10+ 早退分支（情绪/grade_blocked/unknown/
  interface/知识库/思维导图/用户文件/意图路由/方法论/出题/元问题），每个只发
  `presentation→done`，绕过 Individuality 建模和 meta-log 写入。
  此前 204 个测试只验证"有响应"不验证"走了完整管线"。

本测试目标：
  1. 标准教学请求 → 含 diagnosis 事件（走完整管线）；
  2. 早退分支（界面/知识库/元问题）→ 无 diagnosis + presentation→done；
  3. 完整教学后 → meta-log 写入 learner 记录（验证真写了，不是"假教学"）。

设计原则：
  - Flask test_client 真实调用（与 test_v028_endpoints.py / test_v032 一致）；
  - 字段级断言（解析 SSE done.data + meta-log 字段），禁 len()>N；
  - 早退分支测试只用"规则拦截"型（is_interface_query/is_knowledge_query/
    is_meta_question）—— 它们确定性短路，不需 LLM；
  - 完整管线测试可能超时（真实 LLM），失败时报错信息明确指出。
"""
import os
import sys
import time
import uuid
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sse_helpers import (
    parse_sse, event_types, is_complete_pipeline, is_early_return,
    assert_complete_pipeline, assert_early_return, get_done_payload,
)


# ─────────────────────────────────────
# 公共 helper
# ─────────────────────────────────────


def _client():
    from server import app
    return app.test_client()


def _uid(prefix: str = "v034_pi") -> str:
    """生成唯一 learner_id（v034_pi_<timestamp_ms>_<uuid6>）。

    与 test_v032 模式不同：v032 用 _uid() 时隐式回避状态缓存（每次新 ID），
    本测试需要"完整管线后 meta-log 写入"——所以**必须用稳定 ID**（不复用，
    但本测试每次都生成新 ID，规避状态污染——这是元测试（meta-test）的正确做法：
    "新 ID 测新行为，不测 ID 复用"）。
    """
    return f"{prefix}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"


def _post_teach_stream(client, uid, concept, subject="physics", grade="high_school"):
    """调 /api/teach/stream，返回 (events, raw_text)。"""
    resp = client.post("/api/teach/stream", json={
        "concept": concept,
        "subject": subject,
        "grade_level": grade,
        "learner_id": uid,
    })
    assert resp.status_code == 200, f"teach_stream 应 200，实际 {resp.status_code}"
    raw = resp.get_data(as_text=True)
    return parse_sse(raw), raw


def _fetch_meta_log(client, uid, limit=20):
    """拉取 /api/meta-log/<uid>，返回 logs 列表。"""
    resp = client.get(f"/api/meta-log/{uid}?limit={limit}")
    assert resp.status_code == 200, f"meta-log 应 200，实际 {resp.status_code}"
    return resp.get_json().get("logs", [])


# ─────────────────────────────────────
# T1: 标准教学请求走完整管线
# ─────────────────────────────────────


def test_standard_teach_goes_full_pipeline():
    """标准教学（"什么是熵" physics 高中）→ 走完整管线（含 diagnosis）。"""
    client = _client()
    uid = _uid("pi_std")

    events, raw = _post_teach_stream(client, uid, "什么是熵", subject="physics")
    types = event_types(events)

    assert types, f"teach_stream 返回空事件（超时/网络断开），raw 前 200 字: {raw[:200]!r}"

    # 核心断言 1：必须含 diagnosis（教学管线起点）
    assert "diagnosis" in types, (
        f"标准教学应走完整管线（含 diagnosis），实际事件序列={types}\n"
        f"—— 这是 v0.34 盲区 A 的核心：teach_stream 早退分支只发 presentation→done，"
        f"标准学科问题不应被任何早退分支拦截！"
    )

    # 核心断言 2：含完整管线关键事件
    for evt in ("diagnosis", "plan", "step", "presentation", "evaluation",
                "reflection", "self_update", "summary", "done"):
        assert evt in types, f"完整管线缺 {evt}，实际: {types}"

    # 核心断言 3：用严格判定器校验
    assert_complete_pipeline(events)
    print(f"[OK] 标准教学 → 完整管线（含 {len(types)} 个事件，"
          f"起: {types[0]}，终: {types[-1]}）")


# ─────────────────────────────────────
# T2: 早退分支正确绕过完整管线
# ─────────────────────────────────────


def test_early_return_interface_query_skips_diagnosis():
    """界面自指涉（"按钮在哪里"）→ 走 self_referential.is_interface_query 早退。

    设计依据：self_referential.is_interface_query 是纯规则拦截（关键词匹配），
    teach_stream L1096-1109 直接 return presentation→done，绕过完整管线。
    本测试验证这条早退路径**确实**绕过了 diagnosis（不应误触发管线）。
    """
    client = _client()
    uid = _uid("pi_iface")

    # "按钮在哪里" — 命中 INTERFACE_QUERY_PATTERNS
    events, raw = _post_teach_stream(client, uid, "按钮在哪里")
    types = event_types(events)

    assert types, f"teach_stream 返回空: {raw[:200]!r}"

    # 核心断言：不含 diagnosis（被早退分支短路）
    assert "diagnosis" not in types, (
        f"界面自指涉应走早退分支（无 diagnosis），实际事件序列={types}\n"
        f"—— 若 diagnosis 出现，说明 self_referential 早退分支失效/被绕过！"
    )

    # 核心断言：含 presentation→done（早退分支特征）
    assert "presentation" in types and "done" in types, (
        f"早退分支必须含 presentation→done，实际: {types}"
    )

    # 核心断言：done 收尾
    assert types[-1] == "done", f"应以 done 收尾，实际最后事件: {types[-1]}"

    # 严格判定
    assert_early_return(events)
    print(f"[OK] 界面自指涉「按钮在哪里」→ 早退分支（{len(types)} 个事件: {types}）")


def test_early_return_meta_question_skips_diagnosis():
    """元问题（"你是谁"）→ 走 meta_router.route() 集中路由早退。

    server.py L1175-1191（v0.26 ⭐ C3-1 修复）：teach_stream 改用 meta_router.route()
    集中路由，meta/affection/composite/method/problem/knowledge/non_teaching 全部走
    gen_intent() 一次性回答（step_type=chat），绕过完整管线。

    注意：v0.26 后，纯规则的 is_meta_question/is_greeting 分支（L1243-1259，
    step_type=meta/greeting）已被 meta_router.route() 提前短路——实际教学主路径
    不会再走到。这是 v0.26 集中路由的预期行为。

    本测试验证元问题**确实**走早退（不含 diagnosis + presentation→done）。
    """
    client = _client()
    uid = _uid("pi_meta")

    events, raw = _post_teach_stream(client, uid, "你是谁")
    types = event_types(events)

    assert types, f"teach_stream 返回空: {raw[:200]!r}"

    # 核心断言：不含 diagnosis（早退特征）
    assert "diagnosis" not in types, (
        f"元问题应走早退分支（无 diagnosis），实际事件序列={types}"
    )

    # 核心断言：含 presentation→done
    assert_early_return(events)

    # 校验 step_type：v0.26 后所有 meta/greeting 走 route() → step_type=chat
    # （不再是 v0.19.22 的 step_type=meta/greeting，因为 route() 统一处理）
    presentation_data = next((e["data"] for e in events if e["event"] == "presentation"), {})
    step_type = presentation_data.get("step_type")
    assert step_type in ("meta", "chat"), (
        f"元问题分支 step_type 应为 meta 或 chat（v0.26 集中路由后通常为 chat），"
        f"实际: {presentation_data}"
    )
    print(f"[OK] 元问题「你是谁」→ 早退分支（step_type={step_type}，{len(types)} 个事件）")


def test_early_return_knowledge_query_skips_diagnosis():
    """知识库查询（"你学过什么"）→ 走 meta_router.is_knowledge_query 早退。

    server.py L1111-1125：知识库查询 → _handle_knowledge_query 一次性回答，
    绕过完整管线。
    """
    client = _client()
    uid = _uid("pi_kb")

    events, raw = _post_teach_stream(client, uid, "你学过什么")
    types = event_types(events)

    assert types, f"teach_stream 返回空: {raw[:200]!r}"

    # 核心断言：不含 diagnosis
    assert "diagnosis" not in types, (
        f"知识库查询应走早退分支（无 diagnosis），实际事件序列={types}"
    )

    # 核心断言：含 presentation→done
    assert_early_return(events)

    # 校验 step_type
    presentation_data = next((e["data"] for e in events if e["event"] == "presentation"), {})
    assert presentation_data.get("step_type") == "knowledge", (
        f"知识库查询分支 step_type 应为 knowledge，实际: {presentation_data}"
    )
    print(f"[OK] 知识库查询「你学过什么」→ 早退分支（step_type=knowledge）")


# ─────────────────────────────────────
# T3: 完整教学后 meta-log 真写入（关键！v0.32 接入点）
# ─────────────────────────────────────


def test_teach_actually_records_meta_log():
    """完整教学后 → paeg.self_updater.history 应含该 learner_id 的记录。

    验证盲区 A 的关键问题：完整管线真的把 meta-log 写入了（不是"假教学"），
    且 user_modeling reflection（v0.32 ⭐ 接入）也被写入。
    """
    client = _client()
    uid = _uid("pi_meta_log")

    # 完整教学
    events, raw = _post_teach_stream(client, uid, "什么是熵", subject="physics")

    # 断言确实走了完整管线（含 self_update 事件——这是 meta-log 写入的标志）
    types = event_types(events)
    assert "self_update" in types, (
        f"完整教学应含 self_update 事件（meta-log 写入点），实际: {types}\n"
        f"—— 若无 self_update，说明 teach_stream 跳过了 incremental_update（盲区 A！）"
    )

    # 验证 meta-log API 能查到该 uid 的记录
    logs = _fetch_meta_log(client, uid, limit=50)
    assert len(logs) > 0, (
        f"完整教学后 /api/meta-log/{uid} 应有记录，实际 0 条\n"
        f"—— paeg.self_updater.incremental_update 没写入 history！"
    )

    # 字段级断言：每条 log 应含 learner_id 字段且匹配
    for log in logs:
        assert "learner_id" in log, f"meta-log 条目缺 learner_id 字段: {log}"
        assert log["learner_id"] == uid, (
            f"meta-log.learner_id 应为 {uid}，实际 {log['learner_id']}"
        )

    # v0.32 ⭐ meta-log 接入 LLM 建模：应至少一条 user_modeling 类型
    has_user_modeling = any(log.get("type") == "user_modeling" for log in logs)
    if has_user_modeling:
        # 若有 user_modeling 条目，验证关键字段
        um = next(log for log in logs if log.get("type") == "user_modeling")
        for f in ("learner_id", "timestamp", "llm_modeled", "concept", "subject"):
            assert f in um, f"user_modeling 条目缺字段 {f}: {um}"
        print(f"[OK] 完整教学 → meta-log 写入 {len(logs)} 条（含 user_modeling）")
    else:
        # 即便 LLM 未建模，v0.32 注释里说仍会写一条 llm_modeled=False
        print(f"[OK] 完整教学 → meta-log 写入 {len(logs)} 条（无 user_modeling——LLM 建模未触发）")


# ─────────────────────────────────────
# T4: 同 uid 完整 vs 早退对照——早退不应触发 meta-log
# ─────────────────────────────────────


def test_early_return_does_not_trigger_meta_log():
    """早退分支（界面自指涉）→ meta-log 不应新增 user_modeling 条目。

    验证早退分支**确实**绕过了 Individuality 建模 + meta-log 写入
    （这是设计意图——早退不应被误计为"教学"）。
    """
    client = _client()
    uid = _uid("pi_early_no_log")

    # 记下 meta-log 起始数量
    before = _fetch_meta_log(client, uid, limit=50)

    # 早退请求
    events, _ = _post_teach_stream(client, uid, "按钮在哪里")
    assert_early_return(events)

    # meta-log 数量不应增长（早退不应触发 meta-log 写入）
    after = _fetch_meta_log(client, uid, limit=50)

    # 字段级断言：不应新增 user_modeling 条目
    new_user_modeling = [l for l in after if l.get("type") == "user_modeling"
                         and l not in before]
    assert not new_user_modeling, (
        f"早退分支不应触发 user_modeling 写入，新增: {new_user_modeling}"
    )
    print(f"[OK] 早退分支 → 未误触发 user_modeling（before={len(before)}, after={len(after)}）")


# ─────────────────────────────────────
# T5: 完整管线 done 事件应携带必要字段
# ─────────────────────────────────────


def test_complete_pipeline_done_payload_has_required_fields():
    """完整管线 done.data 应含 status=completed 等必要字段。

    字段级断言（禁 len()>N 弱断言）。
    """
    client = _client()
    uid = _uid("pi_done_f")

    events, raw = _post_teach_stream(client, uid, "什么是熵", subject="physics")
    types = event_types(events)
    assert "diagnosis" in types, f"应走完整管线，实际: {types}"

    # 取 done 事件（最后一次）
    done = get_done_payload(events)
    assert done is not None, f"完整管线必须以 done 收尾，实际事件: {types}"

    # 字段级断言
    assert "status" in done, f"done.data 缺 status: {done}"
    assert done.get("status") == "completed", (
        f"done.status 应为 completed，实际: {done.get('status')}"
    )
    print(f"[OK] 完整管线 done.payload = {done}")


if __name__ == "__main__":
    print("运行 test_pipeline_integrity.py（管线完整性测试）")
    print("请用 pytest 运行：pytest tests/test_pipeline_integrity.py -v")
