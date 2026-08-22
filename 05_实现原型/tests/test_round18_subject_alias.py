# -*- coding: utf-8 -*-
"""Round 12 ⭐ 学科子学科映射测试（test_round18_subject_alias.py）。

根因（用户报告）：教学模式问"量子力学"被拒（"未列入学科清单"）——
LLM prompt 把量子力学当 unknown 示例 + 无子学科映射。
守护：
1. 规则兜底：量子力学/热力学/电磁学 → physics；微积分 → math；遗传学 → biology
2. _alias_detect：子学科名 → 父学科（量子纠缠→physics、机器学习→AI 等）
3. lookup_alias：别名表命中
4. detect_subject（无 LLM）：量子力学不判 unknown（规则/映射兜底生效）
5. 真未收录学科（心理学/医学）仍 unknown（不误伤）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subject_detector import (
    _alias_detect, detect_subject, lookup_alias, rule_detect,
)


class TestRuleDetect:
    def test_quantum_mechanics_physics(self):
        assert rule_detect("什么是量子力学") == "physics"

    def test_thermodynamics_physics(self):
        assert rule_detect("玻尔兹曼熵是什么") == "physics"

    def test_calculus_math(self):
        assert rule_detect("微积分基本定理") == "math"

    def test_genetics_biology(self):
        # "遗传学"不在规则关键词，但经 _alias_detect 映射 → biology（双兜底链）
        assert _alias_detect("遗传学基本定律") == "biology"


class TestAliasLookup:
    def test_quantum_aliases(self):
        assert lookup_alias("量子力学") == "physics"
        assert lookup_alias("量子纠缠") == "physics"
        assert lookup_alias("薛定谔") == "physics"

    def test_math_aliases(self):
        assert lookup_alias("线性代数") == "math"
        assert lookup_alias("数论") == "math"

    def test_missing_alias_none(self):
        assert lookup_alias("心理学") is None
        assert lookup_alias("") is None


class TestAliasDetect:
    def test_quantum_entanglement(self):
        assert _alias_detect("量子纠缠是什么原理") == "physics"

    def test_machine_learning(self):
        assert _alias_detect("机器学习中的梯度下降") == "artificial_intelligence"

    def test_data_structure(self):
        assert _alias_detect("数据结构里的红黑树") == "computer_science"

    def test_no_match(self):
        assert _alias_detect("今天心情不错") is None


class TestDetectSubjectNoLLM:
    """无 LLM（llm=None）时走规则+映射兜底，量子力学不判 unknown。"""

    def test_quantum_not_unknown(self):
        r = detect_subject("量子力学是什么", llm=None)
        assert not r["unknown"], f"量子力学不应 unknown: {r}"
        assert r["subject"] == "physics", f"应映射 physics: {r}"

    def test_calculus_math(self):
        r = detect_subject("什么是微积分", llm=None)
        assert r["subject"] == "math"

    def test_real_unknown_still_unknown(self):
        # 心理学/医学无父学科映射 → 保持 unknown（不误伤真未收录）
        r = detect_subject("什么是心理学", llm=None)
        assert not r.get("subject")  # 规则/映射均未命中 → subject None
        # 不强制 unknown（无 LLM 时保持用户设定），但绝不能误判为 physics 等
        assert r["subject"] is None

    def test_greeting_stays_none(self):
        r = detect_subject("你好呀", llm=None)
        assert r["subject"] is None
        assert not r["unknown"]
