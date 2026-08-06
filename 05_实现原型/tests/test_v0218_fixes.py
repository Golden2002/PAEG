"""
stress_turn_eval 修复的防回归测试（v0.21.8）。

覆盖三个架构修复：
1. extract_user_facts：多轮注意力（关键事实提取）
2. answer 端点 chat_hist 写入逻辑（context_bundle 层验证）
3. 哲学 concept_analysis 学科特有注入（仅 philosophy 生效）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_extract_user_facts_color():
    """多轮注意力：从历史提取颜色事实。"""
    from context_bundle import extract_user_facts
    hist = [
        {'role': 'user', 'content': '顺便告诉你，我最喜欢的颜色是蓝绿色，对应的十六进制色值是 #08A89E'},
        {'role': 'assistant', 'content': '蓝绿色确实很有意味'},
        {'role': 'user', 'content': '什么是导数？'},
    ]
    facts = extract_user_facts(hist)
    assert any('蓝绿色' in f for f in facts), "应提取颜色事实"
    assert any('#08A89E' in f for f in facts), "应提取色值"
    print("✓ test_extract_user_facts_color")


def test_extract_user_facts_ignores_questions():
    """多轮注意力：问题句不应被当作事实。"""
    from context_bundle import extract_user_facts
    hist = [
        {'role': 'user', 'content': '什么是导数？'},
        {'role': 'user', 'content': '我养了一只猫叫奶茶'},
    ]
    facts = extract_user_facts(hist)
    assert any('猫' in f for f in facts), "应提取猫事实"
    assert not any('什么是导数' in f for f in facts), "问题句不应被提取"
    print("✓ test_extract_user_facts_ignores_questions")


def test_philosophy_concept_analysis_injected():
    """哲学概念分析注入：philosophy 的 system 含概念对子。"""
    from prompts import build_presenter_system
    s = build_presenter_system('philosophy', 'contemplative')
    assert '概念分析方法' in s
    assert '概念对子' in s
    assert 'Dasein' in s
    assert 'attention' in s
    print("✓ test_philosophy_concept_analysis_injected")


def test_math_not_injected_concept_analysis():
    """学科特有：math 不应注入概念分析（无 concept_analysis 字段）。"""
    from prompts import build_presenter_system
    s = build_presenter_system('math', 'rigorous_cold')
    assert '概念分析方法' not in s, "math 不应有概念分析段"
    assert '回到原文' not in s
    print("✓ test_math_not_injected_concept_analysis")


def test_philosophy_style_has_concept_analysis_field():
    """学科特有机制：只有 philosophy 定义 concept_analysis 字段。"""
    from prompts import get_style
    for subj in ['philosophy', 'math', 'physics', 'aesthetics', 'literature']:
        st = get_style(subj)
        if subj == 'philosophy':
            assert st.get('concept_analysis'), "philosophy 应有 concept_analysis"
        else:
            assert not st.get('concept_analysis'), f"{subj} 不应有 concept_analysis"
    print("✓ test_philosophy_style_has_concept_analysis_field")


def test_lang_refiner_ellipsis_word():
    """语言规则：省略词形检测（倦→疲倦）。"""
    from language_refiner import LanguageRefiner
    r = LanguageRefiner(None)
    issues = r._check_ellipsis('我觉得倦了。')
    assert any('倦' in i for i in issues), "应检出省略词形"
    print("✓ test_lang_refiner_ellipsis_word")


def test_lang_refiner_dangling_object():
    """语言规则：悬空宾语检测（与你探讨→补宾语）。"""
    from language_refiner import LanguageRefiner
    r = LanguageRefiner(None)
    issues = r._check_ellipsis('我想与你探讨。')
    assert any('悬空' in i for i in issues), "应检出悬空宾语"
    # 完整句不误伤
    ok = r._check_ellipsis('我想与你探讨这个问题。')
    assert not any('悬空' in i for i in ok), "完整句不应误伤"
    print("✓ test_lang_refiner_dangling_object")


if __name__ == "__main__":
    test_extract_user_facts_color()
    test_extract_user_facts_ignores_questions()
    test_philosophy_concept_analysis_injected()
    test_math_not_injected_concept_analysis()
    test_philosophy_style_has_concept_analysis_field()
    test_lang_refiner_ellipsis_word()
    test_lang_refiner_dangling_object()
    print("全部通过")
