# -*- coding: utf-8 -*-
"""Round 19 ⭐ 病句确定性修正测试（v0.71 · 用户反馈："我在这里听着你"是病句）。

覆盖：
- fix_known_gaffes 规则层（4 条正则 + 句末/停顿锚定）
- 合法搭配保护（"听着你说/听着你讲/听着你的话/听着你呼吸"不误伤）
- lang_gate_short / lang_gate_content 链路接入（paeg 不可用时规则仍生效）
"""
import os
import sys

BASE = r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型'
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def test_fix_reported_gaffe():
    """用户反馈原句：'我在这里听着你。'→'我就在这里听你说说。'"""
    from language_refiner import fix_known_gaffes
    assert fix_known_gaffes('我在这里听着你。') == '我就在这里听你说说。'
    print('[PASS] 病句原句修正')


def test_fix_other_subject():
    """其他主语：'老师在这里听着你。'→'老师在这里听你说说。'"""
    from language_refiner import fix_known_gaffes
    assert fix_known_gaffes('老师在这里听着你。') == '老师在这里听你说说。'
    print('[PASS] 其他主语修正')


def test_fix_bare_listening():
    """裸'我听着你'（句末）：'你说吧，我听着你。'→'你说吧，我听你说说。'"""
    from language_refiner import fix_known_gaffes
    assert fix_known_gaffes('你说吧，我听着你。') == '你说吧，我听你说说。'
    print('[PASS] 裸「我听着你」句末修正')


def test_fix_generic_subject():
    """一般主语保留：'他听着你。'→'他听你说说。'"""
    from language_refiner import fix_known_gaffes
    assert fix_known_gaffes('他听着你。') == '他听你说说。'
    print('[PASS] 一般主语保留修正')


def test_fix_comma_pause():
    """停顿位（逗号）也修正：'我在这里听着你，你慢慢说。'"""
    from language_refiner import fix_known_gaffes
    assert fix_known_gaffes('我在这里听着你，你慢慢说。') == '我就在这里听你说说，你慢慢说。'
    print('[PASS] 逗号停顿位修正')


def test_preserve_valid_complements():
    """合法搭配保护：已带补语/后接成分的'听着你'不误伤。"""
    from language_refiner import fix_known_gaffes
    valid = [
        '我在这里听着你说。',
        '听着你讲题，我很有耐心。',
        '我在这里听着你的话，心里踏实。',
        '他安静地听着你呼吸。',
        '我在听着你唱歌，真好听。',
    ]
    for v in valid:
        assert fix_known_gaffes(v) == v, f'合法搭配被误改: {v}'
    print('[PASS] 合法搭配 5 例全部保留')


def test_lang_gate_short_applies():
    """lang_gate_short 链路接入：规则层在 paeg 不可用时仍生效。

    （paeg 可用时 polish/refine 可能对措辞做 LLM 微调——如"听你说说"改
    "听你说明你的想法"——断言只验证不变量：病句消除 + 输出非空。）"""
    from services.lang_gate import lang_gate_short
    out = lang_gate_short('我在这里听着你。')
    assert '听着你' not in out, out
    assert out.strip(), out
    print(f'[PASS] lang_gate_short 接入: {out}')


def test_lang_gate_content_applies():
    """lang_gate_content 链路接入（L0-0 前置 + 最终收口）。"""
    from services.lang_gate import lang_gate_content
    out = lang_gate_content('你说吧，我在这里听着你。', context='test')
    assert '听着你' not in out, out
    assert out.strip(), out
    print(f'[PASS] lang_gate_content 接入: {out}')


def test_empty_input_safe():
    """空输入安全返回。"""
    from language_refiner import fix_known_gaffes
    assert fix_known_gaffes('') == ''
    assert fix_known_gaffes('   ') == '   '
    assert fix_known_gaffes(None) is None
    print('[PASS] 空输入安全')


if __name__ == '__main__':
    tests = [
        test_fix_reported_gaffe, test_fix_other_subject, test_fix_bare_listening,
        test_fix_generic_subject, test_fix_comma_pause, test_preserve_valid_complements,
        test_lang_gate_short_applies, test_lang_gate_content_applies, test_empty_input_safe,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
    print(f'\n=== Round 19 病句修正测试: {passed}/{len(tests)} 通过 ===')
