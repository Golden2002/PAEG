# -*- coding: utf-8 -*-
"""
v0.34 标准化测试 v2.0 — SSE 事件捕获与管线完整性检测工具。

来源：PAEG 主项目 server.py teach_stream（app.route("/api/teach/stream")）。

设计原则：
- 解析 Flask test_client 返回的 SSE 响应（text/event-stream）；
- 提供"事件列表 + 完整管线判定 + 早退分支判定"三件套；
- 不依赖 server 模块（纯解析层），可在不 import server 时使用。

SSE 实际事件顺序（server.py L1262-1573 实测）：
  diagnosis → retrieval → plan → step → presentation → evaluation →
  adjustment → reflection → self_update → summary → doc → done
（self_evolution 可能穿插在 self_update 之后）
"""
import json
import re


# 完整教学管线的"主事件"（必须出现，否则视为早退）
# 注：adjustment 是条件事件——仅当 evaluation.ready_to_advance=False 时触发；
#     doc 是条件事件——仅当概念含"讲义/要点/例题/笔记"等关键词时触发；
#     retrieval 是 v0.27 徽章，teach_stream 实际可能省略（try/except 包裹）——
#     因此全部列为"可选"，但 assert_complete_pipeline 的核心仍是"必须含 diagnosis"。
COMPLETE_PIPELINE = [
    "diagnosis",       # 诊断（开始，必现）
    "plan",            # 计划（必现）
    "step",            # 步骤开始（必现，循环内 yield）
    "presentation",    # 讲解（必现，循环内 yield）
    "evaluation",      # 评估（必现，循环内 yield）
    "reflection",      # 反思（必现）
    "self_update",     # 自我更新（必现）
    "summary",         # 总结（必现）
    "done",            # 完成（必现）
]

# 可选事件（管线"加分项"，缺不破坏完整性）
OPTIONAL_PIPELINE_EVENTS = ["retrieval", "adjustment", "doc", "self_evolution"]

# 早退分支共有的事件（早退分支一定只有 presentation→done，且 done 携带特定字段）
EARLY_RETURN_EVENTS = ["presentation", "done"]

# 早退分支 done 事件可能携带的标志位（server.py 实测）
EARLY_RETURN_FLAGS = {
    "affection": "情绪/情感支持（paeg._affection_gate_check 或 meta_router.is_affection_expression）",
    "grade_blocked": "学段不匹配（_steer_subject 返回 grade_blocked）",
    "unregistered_subject": "学科未收录（_steer_subject 返回 unknown）",
    "subject_steered": "学科自动切换（_steer_subject switched）",
    # 界面/知识库/方法论/出题/元问题/复合输入 → done 仅 status=completed
}


def parse_sse(resp_text: str):
    """解析 SSE 响应文本，返回事件列表 [{"event": str, "data": dict}, ...]。

    每条 SSE 消息由 `event:` + `data:` 两行组成：
      event: diagnosis
      data: {"status": "diagnosing"}

    解析失败（非 JSON）的 data 会被包装为 {"raw": "...原文..."}。
    """
    events = []
    cur_event = None
    for line in resp_text.splitlines():
        line = line.strip()
        if line.startswith("event: "):
            cur_event = line[7:].strip()
        elif line.startswith("data: "):
            raw = line[6:]
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {"raw": raw}
            events.append({"event": cur_event or "message", "data": obj})
            cur_event = None
    return events


def event_types(events):
    """提取事件列表的事件名序列（保留顺序）。"""
    return [e["event"] for e in events]


def event_data(events, event_name: str):
    """返回指定事件名对应的 data（首次出现）。多个则返回首个。"""
    for e in events:
        if e["event"] == event_name:
            return e["data"]
    return None


def all_event_data(events, event_name: str):
    """返回指定事件名对应的所有 data 列表（0 个时为 []）。"""
    return [e["data"] for e in events if e["event"] == event_name]


def is_complete_pipeline(events) -> bool:
    """完整教学管线判定：必须含 diagnosis 事件（教学主路径起点）。"""
    return "diagnosis" in event_types(events)


def is_early_return(events) -> bool:
    """早退分支判定：无 diagnosis 且含 presentation→done。

    早退分支的特征：跳过完整管线，直接 presentation→done。
    """
    types = event_types(events)
    return "diagnosis" not in types and "presentation" in types and "done" in types


def get_done_payload(events):
    """返回 done 事件 data（最后一次出现；通常只有一次）。"""
    data = all_event_data(events, "done")
    return data[-1] if data else None


def assert_complete_pipeline(events):
    """断言事件序列是完整教学管线。

    规则：
    1. 必须含 COMPLETE_PIPELINE 中全部事件；
    2. 第一个事件必须是 diagnosis（教学管线起点）；
    3. 最后一个事件必须是 done（收尾）。

    注意：retrieval/adjustment/doc/self_evolution 是穿插或可选事件——
    retrieval 通常在 diagnosis 后；adjustment 仅在评估不达标时触发；
    doc 仅在概念含"讲义/要点/例题/笔记"等关键词时触发；self_evolution 偶尔出现。
    """
    types = event_types(events)
    assert types, "事件列表为空（teach_stream 返回空？超时？网络断开？）"

    # 核心 1：必须含 diagnosis
    assert "diagnosis" in types, (
        f"完整管线必须含 diagnosis（教学起点），实际事件序列={types}"
    )

    # 核心 2：完整管线主事件全在
    missing = [e for e in COMPLETE_PIPELINE if e not in types]
    assert not missing, (
        f"完整管线缺事件: {missing}（实际: {types}）"
    )

    # 核心 3：第一个事件必须是 diagnosis
    assert types[0] == "diagnosis", (
        f"完整管线应从 diagnosis 开始，实际首个事件: {types[0]}（前 5 个: {types[:5]}）"
    )

    # 核心 4：最后一个事件必须是 done
    assert types[-1] == "done", (
        f"完整管线应以 done 收尾，实际最后事件: {types[-1]}"
    )


def assert_early_return(events, expected_mode: str = None):
    """断言事件序列是早退分支。

    规则：
    1. 无 diagnosis 事件；
    2. 必须含 presentation 与 done（早退分支至少一次 presentation）；
    3. 最后一个事件必须是 done；
    4. 若 expected_mode 提供，则 done.data 必须含对应标志位（如 grade_blocked / affection）。

    注意：early_return 不一定不含 plan——某些早退分支（如 grade_blocked）可能含 plan
    但绕过教学循环。核心判定是"无 diagnosis + 含 presentation→done"。
    """
    types = event_types(events)
    assert types, "事件列表为空"

    # 核心 1：无 diagnosis
    assert "diagnosis" not in types, (
        f"早退分支不应含 diagnosis（应走完整管线），实际事件序列={types}"
    )

    # 核心 2：必须含 presentation 与 done
    assert "presentation" in types, (
        f"早退分支必须含 presentation，实际: {types}"
    )
    assert "done" in types, (
        f"早退分支必须含 done（收尾），实际: {types}"
    )

    # 核心 3：done 必须收尾
    assert types[-1] == "done", (
        f"早退分支应以 done 收尾，实际最后事件: {types[-1]}"
    )

    # 核心 4：可选标志位校验
    if expected_mode:
        done = get_done_payload(events) or {}
        assert expected_mode in done, (
            f"早退分支 mode={expected_mode} 应在 done.data 中，实际 done={done}"
        )


def find_event(events, event_name: str, occurrence: int = 0):
    """按出现顺序查找指定事件。

    occurrence=0 → 第 1 次出现；occurrence=1 → 第 2 次。
    返回 (event, data) 元组；找不到返回 (None, None)。
    """
    matches = [e for e in events if e["event"] == event_name]
    if occurrence < len(matches):
        e = matches[occurrence]
        return e["event"], e["data"]
    return None, None


# 简单自测（运行 `python tests/sse_helpers.py` 可验证解析层）
if __name__ == "__main__":
    # 完整管线样例（按 server.py teach_stream 实际事件顺序构造）
    complete_sample = (
        "event: diagnosis\ndata: {\"status\": \"diagnosing\"}\n\n"
        "event: retrieval\ndata: {\"done\": \"知识库检索\"}\n\n"
        "event: plan\ndata: {\"status\": \"planning\"}\n\n"
        "event: step\ndata: {\"step_id\": 1, \"status\": \"presenting\"}\n\n"
        "event: presentation\ndata: {\"step_id\": 1, \"content\": \"讲解\"}\n\n"
        "event: evaluation\ndata: {\"ready_to_advance\": true}\n\n"
        "event: reflection\ndata: {\"reflection\": \"好\"}\n\n"
        "event: self_update\ndata: {\"history_size\": 5}\n\n"
        "event: summary\ndata: {\"avg_score\": 0.8}\n\n"
        "event: done\ndata: {\"status\": \"completed\"}\n\n"
    )
    ev = parse_sse(complete_sample)
    expected = ["diagnosis", "retrieval", "plan", "step", "presentation",
                "evaluation", "reflection", "self_update", "summary", "done"]
    assert event_types(ev) == expected, f"事件序列错: {event_types(ev)} vs {expected}"
    assert is_complete_pipeline(ev) is True
    assert is_early_return(ev) is False
    assert_complete_pipeline(ev)
    print(f"[OK] parse_sse + assert_complete_pipeline 通过：{event_types(ev)}")

    # 早退分支样例
    early_sample = (
        "event: presentation\ndata: {\"step_id\": 1, \"content\": \"你好\"}\n\n"
        "event: done\ndata: {\"status\": \"completed\", \"grade_blocked\": true}\n\n"
    )
    ev2 = parse_sse(early_sample)
    assert event_types(ev2) == ["presentation", "done"]
    assert is_complete_pipeline(ev2) is False
    assert is_early_return(ev2) is True
    assert_early_return(ev2, expected_mode="grade_blocked")
    print(f"[OK] parse_sse + assert_early_return 通过：{event_types(ev2)}")

    # 边界：空响应（超时/网络断开）
    ev3 = parse_sse("")
    assert ev3 == []
    assert is_complete_pipeline(ev3) is False
    assert is_early_return(ev3) is False
    print("[OK] parse_sse 空响应返回空列表")

    print("[OK] sse_helpers 自测全通过")
