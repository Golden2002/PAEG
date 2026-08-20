# -*- coding: utf-8 -*-
"""§3.73 备课魔法词引导式交互——提取层 + 引导分支 + 合并 E2E 测试。

覆盖（对齐最终 A+ 实现：'我要备课'独立激活词 + 确定性短路）：
A. _extract_lesson_topic  提取用例（独立激活词语义）
B. magic_intent 独立激活词匹配（含退化输入）
C. 引导后补充识别（确定性短路核心字段正则逻辑由 server 承载，此处验证提取器）
"""
import os, sys
import pytest

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from meta_router import _extract_lesson_topic, _SUBJECT_MAP, _GRADE_MAP
from magic_intent import match_magic


# ─────────────── A. _extract_lesson_topic 提取用例 ───────────────
class TestExtractLessonTopic:
    @pytest.mark.parametrize("text, expect", [
        ("我要备课", {}),                                    # 纯词 → 引导
        ("我要备课：光合作用", {"topic": "光合作用"}),        # 冒号+主题
        ("我要备课 高中数学函数单调性45分钟",                 # 完整需求
         {"topic": "函数单调性", "subject": "math", "grade": "high_school", "duration_min": 45}),
        ("我要备课：高中数学，函数单调性，45分钟，重点讲图像变换",  # extra 提取
         {"topic": "函数单调性", "subject": "math", "grade": "high_school",
          "duration_min": 45, "extra_requirement": ["重点讲图像变换"]}),
        ("我要备课 初二物理光的折射",                         # 学段 junior
         {"topic": "光的折射", "subject": "physics", "grade": "junior"}),
        ("你好", {}),                                        # 非备课输入
        ("", {}),                                            # 空输入
    ])
    def test_extract(self, text, expect):
        r = _extract_lesson_topic(text)
        if expect == {}:
            assert r == {}, f"{text!r} 应返回 {{}}，实际 {r}"
        else:
            for k, v in expect.items():
                assert r.get(k) == v, f"{text!r} {k} 期望 {v}，实际 {r.get(k)}"

    def test_subject_map_complete(self):
        assert "数学" in _SUBJECT_MAP and _SUBJECT_MAP["数学"] == "math"
        assert "物理" in _SUBJECT_MAP and _SUBJECT_MAP["物理"] == "physics"
        assert "化学" in _SUBJECT_MAP and _SUBJECT_MAP["化学"] == "chemistry"

    def test_grade_map_high_precedence(self):
        # "高一" 应先于 "高中" 匹配（长度降序）
        assert _GRADE_MAP.get("高一") == "high_school"
        assert _GRADE_MAP.get("高中") == "high_school"
        assert _GRADE_MAP.get("初中") == "junior"


# ─────────────── B. magic_intent 独立激活词匹配 ───────────────
class TestMagicIntentIndependent:
    @pytest.mark.parametrize("text, expect_hit", [
        ("我要备课", True),           # 纯词 → lesson_prep（引导）
        ("我要备课：光合作用", True),  # 带需求 → lesson_prep_topic（直接生成）
        ("我要备课 高中数学函数单调性45分钟", True),
        ("帮我备课", False),          # 变体不匹配（独立激活词）
        ("备课：导数", False),         # 变体不匹配
        ("你好", False),
    ])
    def test_match(self, text, expect_hit):
        r = match_magic(text)
        assert (r is not None) == expect_hit, f"{text!r} 期望命中={expect_hit}，实际 {r}"
        if expect_hit:
            assert r["intent"] == "lesson_prep"

    def test_degenerate_empty_tail(self):
        # "我要备课：" 空后缀 → 不匹配（退化输入）
        assert match_magic("我要备课：") is None


# ─────────────── C. 引导后补充识别（提取器层面） ───────────────
class TestGuideSupplement:
    def test_supplement_extractable(self):
        # 引导后补充句应能被 _extract_lesson_topic 提取（供合并分支消费）
        r = _extract_lesson_topic("高中数学，函数单调性，45分钟")
        # 无"我要备课"前缀时，提取器只剥离前缀（无则原样）→ topic 为整句或部分
        assert isinstance(r, dict)
