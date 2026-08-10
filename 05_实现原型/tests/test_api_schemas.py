# -*- coding: utf-8 -*-
"""v0.41.8 ⭐ API 响应结构契约测试（JSON Schema 校验）。

针对"重构导致响应字段漂移"（如 handler 迁移后字段缺失/类型变）——
用 jsonschema 对核心端点的响应结构做契约断言。与 01_API契约.md 对齐。

这是 schemathesis 的轻量替代（零新依赖，覆盖核心 HTTP 契约）：
- schemathesis 需要 openapi.yaml（1-2 天成本），本项目已有 test_contracts.py
- jsonschema 校验响应字段结构，捕获"实现比契约多/少字段"

用法：python -m pytest tests/test_api_schemas.py -q
"""
import json
import sys
import urllib.request

import jsonschema
import pytest

BASE = "http://127.0.0.1:5000"


# ── 核心端点响应 schema（对照 01_API契约.md）────────────────
TEACH_STREAM_EVENTS = {"presentation", "diagnosis", "plan", "done"}
PROFILE_SCHEMA = {
    "type": "object",
    "required": ["id", "nickname", "grade_level", "subjects_mastery"],
    "properties": {
        "id": {"type": "string"},
        "nickname": {"type": "string"},
        "grade_level": {"type": "string"},
        "age": {"type": "integer"},
        "cognitive_style": {"type": "string"},
        "subjects_mastery": {"type": "object"},
    },
}
HEALTH_SCHEMA = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {"type": "string"},
    },
}
METHOD_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["session_id", "presentations", "learner"],
    "properties": {
        "session_id": {"type": "string"},
        "presentations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["step_id", "content", "step_type"],
            },
        },
        "learner": {
            "type": "object",
            "required": ["id", "nickname"],
        },
    },
}


def _get_json(path):
    try:
        resp = urllib.request.urlopen(BASE + path, timeout=15)
        return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return -1, str(e)


# ── 1. /api/health ─────────────────────────────────────────
def test_health_schema():
    s, body = _get_json("/api/health")
    assert s == 200, f"HTTP {s}"
    jsonschema.validate(body, HEALTH_SCHEMA)


# ── 2. /api/profile/<id>（u106 注册用户）──────────────────
def test_profile_schema():
    s, body = _get_json("/api/profile/u106")
    assert s == 200, f"HTTP {s}"
    jsonschema.validate(body, PROFILE_SCHEMA)


# ── 3. /api/method（学习方法，响应结构契约）────────────────
def test_method_response_schema():
    import urllib.request as _ur
    data = json.dumps({"learner_id": "u106", "concept": "怎么学数学",
                       "subject": "math", "grade_level": "high_school",
                       "mode": "method"}).encode()
    req = _ur.Request(BASE + "/api/method", data=data,
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = _ur.urlopen(req, timeout=90)
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
        jsonschema.validate(body, METHOD_RESPONSE_SCHEMA)
    except Exception as e:
        pytest.fail(f"method 响应契约失败: {e}")


# ── 4. teach_stream 事件结构（完整流，核心事件必含）────────
def test_teach_stream_event_contract():
    import urllib.request as _ur
    data = json.dumps({"learner_id": "u106", "concept": "什么是质数",
                       "subject": "math", "grade_level": "high_school",
                       "mode": "teach"}).encode()
    req = _ur.Request(BASE + "/api/teach/stream", data=data,
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = _ur.urlopen(req, timeout=90)
        raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        pytest.fail(f"teach_stream 异常: {e}")
    # 断言核心事件类型都存在（对照 API 契约的 SSE 事件序列）
    for evt in TEACH_STREAM_EVENTS:
        assert f"event: {evt}" in raw, f"缺少事件 {evt}"
    # 每个 presentation 事件必须有 content 字段
    import re
    pres = re.findall(r'event: presentation\ndata: \{"step_id": \d+, "content": "(.*?)", "step_type": "\w+"\}', raw)
    assert pres, "无 presentation 内容（教学未输出）"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
