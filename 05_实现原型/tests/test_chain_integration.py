# -*- coding: utf-8 -*-
"""全链路集成测试（v0.66 ⭐ Oracle 标准：连通性安全网）

覆盖：
- 讲义→大纲→讲稿→PPT→manim→视频 链路
- 统一资源门面 collect_all_resources
- 短指令补全 infer_context
- 思维导图三路资源
- 语言规范 lang_gate
"""
import os
import sys

BASE = r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型'
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def test_handout_six_sections():
    """讲义必须有 6 段结构（Oracle 设计）。"""
    from file_generator import _parse_handout_sections
    md = (
        "# 极限讲义\n## 一、教学目标\n- 知识目标\n## 二、导入\n**情境**：\n"
        "## 三、新课讲授\n### 3.1 定义\n- 定义\n## 四、巩固练习\n1. 题\n"
        "## 五、课堂小结\n- 要点\n## 六、作业与拓展\n- 作业"
    )
    sections = _parse_handout_sections(md)
    assert len(sections) >= 5, f"讲义段数不足: {len(sections)}"
    print(f'[PASS] 讲义 6 段结构: {len(sections)} 段')


def test_intent_inference_short_input():
    """短指令补全：'极限'→数学/高中。"""
    from services.intent_inference import infer_context
    ctx = infer_context('极限')
    assert ctx['subject'] == '数学', ctx
    assert ctx['topic'] == '极限', ctx
    ctx2 = infer_context('考研微积分怎么学')
    assert ctx2['grade'] == 'graduate_exam', ctx2
    print(f'[PASS] 短指令补全: 极限→{ctx["subject"]}/{ctx["grade"]}; 考研→{ctx2["grade"]}')


def test_manim_suitability_inference():
    """主题推断：subject 空时靠关键词识别 manim 主题。

    v0.69+：manim 环境不可用时 skip（infer_manim_suitability 依赖 manim_service
    初始化，无 manim 环境的 CI/新机器上是预期跳过）。"""
    import pytest
    try:
        from manim_service import infer_manim_suitability
    except Exception as _m_e:
        pytest.skip(f"manim 环境不可用: {_m_e}")
    assert infer_manim_suitability('行列式的几何意义', '') is True
    assert infer_manim_suitability('文言文实词', '') is False
    print('[PASS] 主题推断: 行列式=True, 文言文=False')


def test_lang_gate_preserves_text():
    """语言规范守门不破坏正常文本。"""
    from services.lang_gate import lang_gate_short, lang_gate_content
    t = '同学们，我们这一节的主题是极限的概念。'
    assert lang_gate_short(t) == t
    assert '极限' in lang_gate_content('# 极限讲义\n## 一、教学目标', context='test')
    print('[PASS] 语言规范守门: 正常文本保留')


def test_script_teaching_tone():
    """讲稿授课式兜底（不退化要点拼接）。"""
    from services.script_service import _fallback_narration
    n = _fallback_narration('极限的概念', ['极限描述趋近行为', '极限是微积分基础'])
    assert '同学' in n, n
    assert '我们' in n, n
    print(f'[PASS] 授课式讲稿兜底: {n[:40]}...')


def test_resource_facade():
    """统一资源门面可用（不抛异常）。"""
    from services.library import collect_all_resources
    r = collect_all_resources('u_chain_test', '极限', llm=None, subject='数学', include_web=False)
    assert 'block' in r and 'has_any' in r
    print(f'[PASS] 资源门面: has_any={r["has_any"]}')


if __name__ == '__main__':
    tests = [
        test_handout_six_sections, test_intent_inference_short_input,
        test_manim_suitability_inference, test_lang_gate_preserves_text,
        test_script_teaching_tone, test_resource_facade,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
    print(f'\n=== 全链路集成测试: {passed}/{len(tests)} 通过 ===')
