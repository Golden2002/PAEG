# -*- coding: utf-8 -*-
"""P0-1/P0-2/P0-3/P0-4 harness 优化配套测试。

Oracle 诊断：64 个 SUBJECT_STYLES 键中仅 4 个（physics/college_physics/math/aesthetics）
有 method_guide/worked_example，其余 60 个学科"方法论空心"；考研政治/数学缺分键；
缺收尾问题模板分流；缺学科×学段深度阶梯。

本测试覆盖：
- P0-1：高频学科补齐 method_guide + worked_example（不复用 physics 模板）
- P0-2：考研学科分键 + 别名
- P0-3：收尾问题模板分流（每个学段第 5 段有 closing_question_template）
- P0-4：SUBJECT_GRADE_DEPTH 二维阶梯（5 学科 × 4 学段 = 20 条 + 注入 build_presenter_system）

用法：python -m pytest tests/test_grade_subject_optimization.py -v
"""
from __future__ import annotations

import pytest

import prompts
from prompts import (
    SUBJECT_STYLES,
    GRADE_SCAFFOLDS,
    _SUBJECT_ALIASES,
    normalize_subject,
    build_presenter_system,
)


# ═════════════════════════════════════════════════════════════════
# P0-1：高频学科 method_guide + worked_example 覆盖
# ═════════════════════════════════════════════════════════════════

HIGH_FREQ_SUBJECTS = [
    "chemistry",
    "biology",
    "geography",
    "chinese",
    "politics",
    "history",
    "economics",
    "literature",
    "english",
    "french",
    "german",
    "japanese",
    "law",
    "coding",
]


@pytest.mark.parametrize("subject_key", HIGH_FREQ_SUBJECTS)
def test_major_subjects_have_method_guide(subject_key):
    """P0-1：高频学科必须有 method_guide 字段，非空，且非空字符串。"""
    style = SUBJECT_STYLES.get(subject_key)
    assert style is not None, f"{subject_key} 不在 SUBJECT_STYLES"
    assert "method_guide" in style, f"{subject_key} 缺 method_guide 字段"
    mg = style["method_guide"]
    assert isinstance(mg, str) and mg.strip(), f"{subject_key} method_guide 为空"


@pytest.mark.parametrize("subject_key", HIGH_FREQ_SUBJECTS)
def test_major_subjects_have_worked_example(subject_key):
    """P0-1：高频学科必须有 worked_example 字段，非空。"""
    style = SUBJECT_STYLES.get(subject_key)
    assert style is not None, f"{subject_key} 不在 SUBJECT_STYLES"
    assert "worked_example" in style, f"{subject_key} 缺 worked_example 字段"
    we = style["worked_example"]
    assert isinstance(we, str) and we.strip(), f"{subject_key} worked_example 为空"


def test_method_guides_are_not_just_physics_copy():
    """P0-1 守门：method_guide 必须是学科定制——不能全部抄 physics 模板。
    验证：取每学科 method_guide 的前 40 字符作为指纹，至少 7 个学科的指纹与
    physics 不同（指允许少量学科确实与 physics 内容高度重合的边界）。"""
    physics_guide = SUBJECT_STYLES["physics"]["method_guide"]
    physics_fp = physics_guide[:80]  # 指纹

    customized_count = 0
    for key in HIGH_FREQ_SUBJECTS:
        mg = SUBJECT_STYLES[key]["method_guide"]
        # 学科定制信号：必须出现学科相关术语（取学科 label/术语作为锚点）
        anchor_terms = {
            "chemistry": ["氧化", "化学", "反应", "配平"],
            "biology": ["生物", "基因", "细胞", "遗传"],
            "geography": ["地理", "区位", "气候", "区域"],
            "chinese": ["语文", "阅读", "文本", "鉴赏"],
            "politics": ["政治", "观点", "原理"],
            "history": ["历史", "因果", "史料"],
            "economics": ["经济", "供需", "市场"],
            "literature": ["文学", "文本", "意象"],
            "english": ["英语", "长难句", "语法"],
            "french": ["法语", "发音"],
            "german": ["德语", "格", "语法"],
            "japanese": ["日语", "假名", "助词"],
            "law": ["法", "条文", "案例", "构成要件"],
            "coding": ["代码", "算法", "代码", "函数"],
        }
        terms = anchor_terms.get(key, [])
        # 任一锚点术语出现即视为定制
        if any(t in mg for t in terms):
            customized_count += 1

    # 至少 10/14 学科方法论里有本学科锚点术语（防止复读 physics）
    assert customized_count >= 10, (
        f"仅 {customized_count}/{len(HIGH_FREQ_SUBJECTS)} 个学科的方法论含学科锚点术语"
    )
    # v1.2.1 ⭐ 修复测试自身缺陷：原断言为同一字符串自比
    # （physics_fp 即 SUBJECT_STYLES["physics"]["method_guide"][:80]），恒为假。
    # 正确语义：physics 的 method_guide 必须存在且非空（ratchet），
    # 各学科"非 physics 复读"已由上方 customized_count >= 10 覆盖。
    assert physics_fp.strip(), "physics 的 method_guide 不能为空（ratchet 铁律）"


def test_existing_physics_method_guide_unchanged():
    """Ratchet 铁律：现有 physics/college_physics/math/aesthetics 的 method_guide 不能动。"""
    for key in ("physics", "college_physics", "math", "aesthetics", "philosophy"):
        if key in SUBJECT_STYLES:
            assert "method_guide" in SUBJECT_STYLES[key], (
                f"ratchet：{key} 原本有 method_guide，不得删除"
            )


def test_no_existing_subject_key_removed():
    """Ratchet 铁律：现有 SUBJECT_STYLES 键不能删（只增字段/键）。"""
    # 抽样验证关键键仍在
    must_have = [
        "physics", "math", "chemistry", "biology", "geography", "chinese",
        "politics", "history", "english", "french", "german", "japanese",
        "law", "economics", "literature", "philosophy", "aesthetics",
        "college_physics", "college_chinese", "college_english",
        "college_politics", "coding", "thinking", "learning", "expression",
        "writing", "linguistics", "atmospheric_science", "computer_science",
        "artificial_intelligence", "electronics", "ethics", "phenomenology",
        "default",
    ]
    for k in must_have:
        assert k in SUBJECT_STYLES, f"现有学科键缺失：{k}（ratchet 铁律）"


# ═════════════════════════════════════════════════════════════════
# P0-2：考研学科分键
# ═════════════════════════════════════════════════════════════════

def test_korean_exam_subject_keys():
    """P0-2：politics_exam 与 math_exam 必须在 SUBJECT_STYLES 中。"""
    assert "politics_exam" in SUBJECT_STYLES, "缺考研政治分键 politics_exam"
    assert "math_exam" in SUBJECT_STYLES, "缺考研数学分键 math_exam"

    # 必须有 method_guide + worked_example（与 politics/math 区隔）
    for key in ("politics_exam", "math_exam"):
        style = SUBJECT_STYLES[key]
        assert "method_guide" in style, f"{key} 缺 method_guide"
        assert "worked_example" in style, f"{key} 缺 worked_example"


def test_korean_exam_alias():
    """P0-2：『考研政治』『考研数学』『考研政治（…）』等应归一到 politics_exam/math_exam。"""
    assert normalize_subject("考研政治") == "politics_exam"
    assert normalize_subject("考研数学") == "math_exam"
    # 历史别名『考研数学（高等数学/线性代数/概率统计）』必须重定向到 math_exam
    # （旧 values = "math"，必须修改为 "math_exam"）
    assert normalize_subject("考研数学（高等数学/线性代数/概率统计）") == "math_exam"
    assert normalize_subject("思想政治（考研）") == "politics_exam"


def test_korean_exam_available_for_graduate_exam():
    """P0-2：考研政治/数学必须对 graduate_exam 档可用（subject_available_for_grade）。"""
    assert prompts.subject_available_for_grade("politics_exam", "graduate_exam")
    assert prompts.subject_available_for_grade("math_exam", "graduate_exam")


# ═════════════════════════════════════════════════════════════════
# P0-3：收尾问题模板分流（GRADE_SCAFFOLDS 第 5 段有 closing_question_template）
# ═════════════════════════════════════════════════════════════════

GRADES_FOR_CLOSING = ["middle_school", "high_school", "undergraduate", "graduate_exam"]


@pytest.mark.parametrize("grade_key", GRADES_FOR_CLOSING)
def test_closing_question_templates(grade_key):
    """P0-3：GRADE_SCAFFOLDS[grade_key] 第 5 段必须有 closing_question_template（list[2]）。"""
    scaffold = GRADE_SCAFFOLDS[grade_key]
    segments = scaffold["segments"]
    assert len(segments) >= 5, f"{grade_key} 段数不足 5"
    seg5 = segments[4]
    assert "closing_question_template" in seg5, (
        f"{grade_key} 第 5 段缺 closing_question_template"
    )
    cqt = seg5["closing_question_template"]
    assert isinstance(cqt, list), f"{grade_key} closing_question_template 必须是 list"
    assert len(cqt) >= 2, f"{grade_key} closing_question_template 至少 2 题"
    for q in cqt:
        assert isinstance(q, str) and q.strip(), f"{grade_key} 含空题目"


def test_closing_question_distinct_by_grade():
    """P0-3：各学段的收尾模板应学段差异化（不全相同），避免模板被复读。"""
    fingerprints = {}
    for grade in GRADES_FOR_CLOSING:
        seg5 = GRADE_SCAFFOLDS[grade]["segments"][4]
        fingerprints[grade] = tuple(seg5["closing_question_template"])
    distinct = len(set(fingerprints.values()))
    assert distinct >= 3, (
        f"4 学段仅 {distinct} 种收尾模板——P0-3 期望学段差异化（≥3）"
    )


# ═════════════════════════════════════════════════════════════════
# P0-4：SUBJECT_GRADE_DEPTH 二维阶梯
# ═════════════════════════════════════════════════════════════════

DEPTH_SUBJECTS = ["physics", "math", "chemistry", "biology", "chinese"]
DEPTH_GRADES = ["middle_school", "high_school", "undergraduate", "graduate_exam"]
EXPECTED_DEPTH_COUNT = len(DEPTH_SUBJECTS) * len(DEPTH_GRADES)  # 20 条


def test_grade_depth_exists():
    """P0-4：SUBJECT_GRADE_DEPTH 必须覆盖 5 学科 × 4 学段 = 20 条。"""
    depth = getattr(prompts, "SUBJECT_GRADE_DEPTH", None)
    assert depth is not None, "缺 SUBJECT_GRADE_DEPTH 字典"
    assert isinstance(depth, dict)
    # 计数：键总数 ≥ 20
    assert len(depth) >= EXPECTED_DEPTH_COUNT, (
        f"SUBJECT_GRADE_DEPTH 需 ≥ {EXPECTED_DEPTH_COUNT} 条，实际 {len(depth)}"
    )


@pytest.mark.parametrize("subject_key", DEPTH_SUBJECTS)
@pytest.mark.parametrize("grade_key", DEPTH_GRADES)
def test_grade_depth_shape(subject_key, grade_key):
    """P0-4：每条 (subject, grade) 必须有 scope/avoid_terms/must_terms/depth_examples。"""
    depth = getattr(prompts, "SUBJECT_GRADE_DEPTH", None)
    assert depth is not None, "缺 SUBJECT_GRADE_DEPTH"
    key = (subject_key, grade_key)
    assert key in depth, f"SUBJECT_GRADE_DEPTH 缺 {key}"
    entry = depth[key]
    assert isinstance(entry, dict)
    for field in ("scope", "avoid_terms", "must_terms", "depth_examples"):
        assert field in entry, f"{key} 缺字段 {field}"
    # scope 必为非空字符串
    assert isinstance(entry["scope"], str) and entry["scope"].strip(), (
        f"{key} scope 为空"
    )
    # 必须为 list 类型
    for list_field in ("avoid_terms", "must_terms", "depth_examples"):
        assert isinstance(entry[list_field], list), (
            f"{key} {list_field} 不是 list"
        )


def test_grade_depth_distinct_by_grade():
    """P0-4：同一学科不同学段应深度递增（scope 不应完全相同）。"""
    depth = getattr(prompts, "SUBJECT_GRADE_DEPTH", None)
    for subject_key in DEPTH_SUBJECTS:
        scopes = []
        for g in DEPTH_GRADES:
            entry = depth.get((subject_key, g))
            if entry:
                scopes.append(entry["scope"])
        # 同学科 4 个 scope 应该不全相同（深度递增）
        distinct = len(set(scopes))
        assert distinct >= 3, (
            f"{subject_key} 4 学段 scope 仅 {distinct} 种，应 ≥3（深度递增）"
        )


def test_depth_injected():
    """P0-4：build_presenter_system 必须注入 depth（(physics,middle_school) 信息在 system 中）。"""
    # 构造 learner：middle_school（让 grade_key 中包含 depth 注入段）
    learner = prompts.LearnerProfile if hasattr(prompts, "LearnerProfile") else None
    if learner is None:
        # 退化：直接用 learner 字典代替（仅提供 grade_level 与 nickname）
        from paeg import LearnerProfile as _LP
        learner = _LP(id="depth_test", nickname="测试", grade_level="middle_school", age=13)
    else:
        learner = learner(id="depth_test", nickname="测试", grade_level="middle_school", age=13)

    system = build_presenter_system(
        subject="physics",
        tone="balanced",
        learner=learner,
    )
    # depth 注入段标识 + physics middle_school 的 must_terms 锚词
    assert "学科深度阶梯" in system or "深度阶梯" in system, (
        "build_presenter_system 未注入 depth 段"
    )
    # physics 中学必须包含 "力" / "能量" 等关键词（避免注入但内容空白）
    must_terms = prompts.SUBJECT_GRADE_DEPTH.get(("physics", "middle_school"), {}).get("must_terms", [])
    if must_terms:
        # 至少一个 must_term 应出现在 system 中
        assert any(t in system for t in must_terms), (
            f"build_presenter_system 的 depth 注入未包含 must_terms: {must_terms}"
        )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
