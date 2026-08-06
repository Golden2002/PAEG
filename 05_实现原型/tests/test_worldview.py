"""
世界观自动切换的单元测试。
"""

import sys
sys.path.insert(0, '..')

from world_view import select_tone, THEME_TONE_MAP


def test_physics_tone():
    assert select_tone("physics")["tone"] == "rigorous_cold"
    print("✓ test_physics_tone")


def test_math_tone():
    assert select_tone("math")["tone"] == "rigorous_cold"
    print("✓ test_math_tone")


def test_literature_tone():
    assert select_tone("literature")["tone"] == "contemplative"
    print("✓ test_literature_tone")


def test_ethics_tone():
    assert select_tone("ethics")["tone"] == "warm_caring"
    print("✓ test_ethics_tone")


def test_career_tone():
    assert select_tone("career")["tone"] == "pragmatic"
    print("✓ test_career_tone")


def test_unknown_tone():
    assert select_tone("unknown_topic_xyz")["tone"] == "balanced"
    print("✓ test_unknown_tone")


def test_worldview_ratio_sums_to_one():
    """所有主题的比例和为 1。"""
    for theme, (tone, ratio, _) in THEME_TONE_MAP.items():
        total = sum(ratio.values())
        assert abs(total - 1.0) < 0.01, f"{theme} ratio sums to {total}"
    print("✓ test_worldview_ratio_sums_to_one")


if __name__ == "__main__":
    test_physics_tone()
    test_math_tone()
    test_literature_tone()
    test_ethics_tone()
    test_career_tone()
    test_unknown_tone()
    test_worldview_ratio_sums_to_one()
    print("\n所有测试通过 ✓")
