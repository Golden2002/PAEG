"""
SelfUpdateAgent（第 8 个子代理）的单元测试。
v0.21.4：自我更新子代理——读取过滤后反思 + 外部反馈，驱动 LLM 生成结构化建议。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from subagents import SelfUpdateAgent


class MockModel:
    """模拟 LLM：返回一段带 JSON 建议的文本。"""
    def messages_create(self, **kwargs):
        return {"content": [{"text": (
            "```json\n"
            "[{\"category\": \"prompt_update\", \"target\": \"presenter\", "
            "\"change\": \"增加生活化示例\", \"evidence\": \"用户反馈\", "
            "\"priority\": \"P1\"}]\n"
            "```"
        )}]}


def _make(learner=None):
    return SelfUpdateAgent(), MockModel(), learner


def test_constructor_no_args():
    """构造不需要参数。"""
    a = SelfUpdateAgent()
    assert a is not None
    print("✓ test_constructor_no_args")


def test_run_with_mock_model():
    """Mock 模型：返回结构化建议。"""
    a, model, _ = _make()
    r = a.run(model, "教学示例太抽象")
    assert r["mode"] == "self_update"
    assert isinstance(r["suggestions"], list)
    assert len(r["suggestions"]) >= 1
    assert "feedback_text" in r["sources_used"]
    print("✓ test_run_with_mock_model")


def test_run_with_insights():
    """传入 insights：sources_used 含 insights。"""
    a, model, _ = _make()
    r = a.run(model, "改进教学", insights=[{"content": "学生要更多图示", "subject": "math"}])
    assert "insights" in r["sources_used"]
    print("✓ test_run_with_insights")


def test_run_with_empty_insights():
    """空 insights：不崩溃，sources_used 不含 insights。"""
    a, model, _ = _make()
    r = a.run(model, "改进教学", insights=[])
    assert r["mode"] == "self_update"
    assert "insights" not in r["sources_used"]
    print("✓ test_run_with_empty_insights")


def test_run_without_learner():
    """learner=None 不抛 UnboundLocalError。"""
    a, model, _ = _make(learner=None)
    r = a.run(model, "改进教学", learner=None)
    assert r["mode"] == "self_update"
    print("✓ test_run_without_learner")


def test_suggestion_shape():
    """每条建议必须含 category/target/change/evidence/priority，priority ∈ P0/P1/P2。"""
    a, model, _ = _make()
    r = a.run(model, "教学示例太抽象，多给生活化例子")
    for s in r["suggestions"]:
        assert "category" in s
        assert "target" in s
        assert "change" in s
        assert "evidence" in s
        assert "priority" in s
        assert s["priority"] in ("P0", "P1", "P2")
    print("✓ test_suggestion_shape")


if __name__ == "__main__":
    test_constructor_no_args()
    test_run_with_mock_model()
    test_run_with_insights()
    test_run_with_empty_insights()
    test_run_without_learner()
    test_suggestion_shape()
    print("全部通过")
