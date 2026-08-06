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


def test_intent_with_material_detects_composite():
    """"指令+资料"复合输入应被识别（走资源分析而非教学）。"""
    from meta_router import is_intent_with_material
    composite = [
        '帮我分析这段话：\n从前有座山，山里有座庙……（超过六十字符的长文本示例用于测试）',
        '这段代码有什么问题：\ndef add(a,b):\n    return a+b\n\ndef add(x,y):\n    print(x+y)',
        '请翻译下面这段：\nHello world, this is a test.',
    ]
    normal = ['什么是导数？', '帮我讲讲勾股定理', '你好']
    for t in composite:
        assert is_intent_with_material(t) is True, f"应识别复合输入: {t[:30]}"
    for t in normal:
        assert is_intent_with_material(t) is False, f"不应误判: {t}"
    print("✓ test_intent_with_material_detects_composite")


def test_split_intent_material():
    """"指令+资料"切分：指令与资料分离。"""
    from meta_router import split_intent_and_material
    instr, mat = split_intent_and_material('帮我分析这段话：\n这是要分析的资料')
    assert '分析' in instr
    assert '资料' in mat
    print("✓ test_split_intent_material")


def test_intent_guide_in_system_prompt():
    """指令vs资源指引注入所有系统提示。"""
    from prompts import build_general_chat_system, build_presenter_system
    s1 = build_general_chat_system(None)
    assert '指令' in s1 and '资源' in s1 and '形态 B' in s1
    s2 = build_presenter_system('math', 'rigorous_cold')
    assert '指令' in s2 and '资料' in s2
    print("✓ test_intent_guide_in_system_prompt")


def test_identity_questions_self_referential():
    """"你是谁/有哪些功能"应触发自我指涉（身份确定性回复，非闲聊）。"""
    from self_referential import is_interface_query, handle_interface_query
    for q in ['你是谁', '你有哪些功能', '你能做什么', '你叫什么名字', '你有什么功能']:
        assert is_interface_query(q) is True, f"应命中自我指涉: {q}"
    r = handle_interface_query('你是谁')
    assert 'Émile Novis' in r
    assert '我能帮你做的事' in r or '能帮你' in r
    print("✓ test_identity_questions_self_referential")


def test_identity_not_hijack_normal():
    """"你是谁"改造不误伤正常问题。"""
    from self_referential import is_interface_query
    for q in ['什么是导数', '你好', '帮我讲讲勾股定理']:
        assert is_interface_query(q) is False, f"不应命中自我指涉: {q}"
    print("✓ test_identity_not_hijack_normal")
