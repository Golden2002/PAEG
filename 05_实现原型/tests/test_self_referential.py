"""
self_referential 自我指涉模块的单元测试。
v0.21.6：subagent / 学科学段切换含义的自我指涉路由（防误路由知识库清点）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from self_referential import is_interface_query, handle_interface_query
from meta_router import is_knowledge_query


def test_subagent_question_self_referential():
    """"有哪些subagent"应路由自我指涉（不是知识库清点）。"""
    for q in ['你都有哪些subagent', '你有哪些子代理', '你的subagent有哪些', '你有几个agent']:
        assert is_interface_query(q) is True, f"应命中自我指涉: {q}"
    print("✓ test_subagent_question_self_referential")


def test_subject_grade_switch_self_referential():
    """"切换学科学段意味着什么"应路由自我指涉。"""
    for q in ['切换学科和学段对你意味着什么', '切换学科对你意味着什么', '学段切换什么意思']:
        assert is_interface_query(q) is True, f"应命中自我指涉: {q}"
    print("✓ test_subject_grade_switch_self_referential")


def test_knowledge_questions_not_hijacked():
    """真知识库问题不受影响（仍走 knowledge）。"""
    for q in ['你学过什么', '你的知识库里有什么', '知识库里有什么']:
        assert is_knowledge_query(q) is True, f"应命中知识库: {q}"
    print("✓ test_knowledge_questions_not_hijacked")


def test_normal_teaching_not_hijacked():
    """正常教学问题不被自我指涉误伤。"""
    for q in ['什么是导数', '讲讲勾股定理', '什么是熵']:
        assert is_interface_query(q) is False, f"不应命中自我指涉: {q}"
        assert is_knowledge_query(q) is False, f"不应命中知识库: {q}"
    print("✓ test_normal_teaching_not_hijacked")


def test_handle_self_arch_content():
    """自我架构回答包含 subagent 分工和学科学段说明。"""
    r = handle_interface_query('你都有哪些subagent')
    assert 'Diagnostor' in r
    assert 'SelfUpdateAgent' in r
    assert '分工' in r
    r2 = handle_interface_query('切换学科和学段对你意味着什么')
    assert '切换学科' in r2
    assert '切换学段' in r2
    print("✓ test_handle_self_arch_content")


def test_interface_questions_still_work():
    """既有界面问题不受影响。"""
    for q in ['这个界面上不同的按钮是做什么用的', '怎么使用这个网站', '学科下拉里都有什么']:
        assert is_interface_query(q) is True, f"应命中界面: {q}"
    print("✓ test_interface_questions_still_work")


if __name__ == "__main__":
    test_subagent_question_self_referential()
    test_subject_grade_switch_self_referential()
    test_knowledge_questions_not_hijacked()
    test_normal_teaching_not_hijacked()
    test_handle_self_arch_content()
    test_interface_questions_still_work()
    print("全部通过")
