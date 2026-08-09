"""
/api/self-update/from-feedback 端点的集成测试。
v0.21.4：从反馈/反思生成自我更新建议。
"""

import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture(scope="module")
def app():
    """导入 server 模块（Flask app）。"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import server
    return server


def _post(app, payload, timeout=90):
    import urllib.request
    req = urllib.request.Request(
        'http://localhost:5000/api/self-update/from-feedback',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, None


def test_empty_body_returns_400(app):
    """空 body → 400。"""
    import urllib.request
    req = urllib.request.Request(
        'http://localhost:5000/api/self-update/from-feedback',
        data=b'{}',
        headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=10)
        assert False, "应返回 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
    print("✓ test_empty_body_returns_400")


def test_missing_text_returns_400(app):
    """缺 text 字段 → 400。"""
    st, body = _post(app, {"learner_id": "u8"})
    assert st == 400
    assert body["ok"] is False
    print("✓ test_missing_text_returns_400")


def test_valid_text_returns_200_with_suggestions(app):
    """有效 text → 200 + suggestions。"""
    st, body = _post(app, {
        "text": "测试反馈：希望多给具体例子",
        "learner_id": "u8",
        "include_insights": False,
        "include_feedback_files": False,
    })
    assert st == 200
    assert body["ok"] is True
    result = body["result"]
    assert result["mode"] == "self_update"
    assert isinstance(result["suggestions"], list)
    assert "summary" in result
    print("✓ test_valid_text_returns_200_with_suggestions")


def test_with_insights_returns_merged_suggestions(app):
    """读取 insights.json 后返回合并建议。"""
    st, body = _post(app, {
        "text": "请基于当前反思给出改进建议",
        "learner_id": "u8",
        "include_insights": True,
        "include_feedback_files": False,
    })
    assert st == 200
    assert body["ok"] is True
    print("✓ test_with_insights_returns_merged_suggestions")


if __name__ == "__main__":
    import urllib.request
    import urllib.error
    test_empty_body_returns_400(None)
    test_missing_text_returns_400(None)
    test_valid_text_returns_200_with_suggestions(None)
    test_with_insights_returns_merged_suggestions(None)
    print("全部通过")
