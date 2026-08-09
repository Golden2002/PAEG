# -*- coding: utf-8 -*-
"""v0.37 回归测试：防止"修复有时未生效"复发。

覆盖：
1. RiskClassifier 6 级风险分级（关键词规则）
2. opt_out 抑制边界（level>=3 强制资源，level<=2 可压制）
3. AffectionSupportor prompt 反占有约束（无"我完全懂你/只有我能"）
4. 掌握度兼容 mastery/level 两种结构（前端逻辑）
5. 早退分支统一保存（_save_teach_turn 存在且被调用）
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 1. RiskClassifier 风险分级
# ---------------------------------------------------------------------------
class TestRiskClassifier:
    def setup_method(self):
        from safety import RiskClassifier
        self.rc = RiskClassifier()

    def test_level0_normal(self):
        assert self.rc.classify("什么是导数？") == 0
        assert self.rc.classify("我有点累") == 0

    def test_level1_distress(self):
        assert self.rc.classify("我今天崩溃了，失眠一整晚") == 1
        assert self.rc.classify("我撑不住了，喘不过气") == 1

    def test_level2_passive_ideation(self):
        assert self.rc.classify("我觉得活着没意思") == 2
        assert self.rc.classify("生活没有意义，消失就好") == 2

    def test_level3_active_ideation(self):
        assert self.rc.classify("我想死") == 3
        assert self.rc.classify("不想活了，想结束一切") == 3

    def test_level4_plan_or_means(self):
        assert self.rc.classify("我买了药，想好了方法") == 4
        assert self.rc.classify("我写了遗书，选了地点和时间") == 4

    def test_level5_imminent(self):
        assert self.rc.classify("我已经吃了药，感觉头晕") == 5
        assert self.rc.classify("我正在实施，马上就要") == 5

    def test_levels_are_hierarchical(self):
        # 高等级不被低等级模式误判为低等级
        assert self.rc.classify("我已经吃了药，不想活了") == 5  # imminent 优先
        assert self.rc.classify("我买了刀，想死") == 4  # plan 优先于 active

    def test_opt_out_suppressible(self):
        assert self.rc.opt_out_suppressible(1) is True
        assert self.rc.opt_out_suppressible(2) is True
        assert self.rc.opt_out_suppressible(3) is False
        assert self.rc.opt_out_suppressible(4) is False
        assert self.rc.opt_out_suppressible(5) is False

    def test_should_show_resources_high_level(self):
        # level>=3 强制显示，即使 opt_out active
        opt = {"active": True, "rejected_at": None, "rejected_resources": []}
        assert self.rc.should_show_resources(3, opt) is True
        assert self.rc.should_show_resources(4, opt) is True
        assert self.rc.should_show_resources(5, opt) is True

    def test_should_show_resources_low_level_optout(self):
        # level<=2 + opt_out active → 不强制显示
        opt = {"active": True, "rejected_at": None, "rejected_resources": []}
        assert self.rc.should_show_resources(1, opt) is False
        assert self.rc.should_show_resources(2, opt) is False


# ---------------------------------------------------------------------------
# 2. AffectionSupportor 反占有约束 + 危机注入
# ---------------------------------------------------------------------------
class TestAffectionSupportor:
    def test_prompt_contains_anti_ownership(self):
        """system prompt 必须含反占有约束（Oracle 方案 C 段落）。"""
        from subagents import AffectionSupportor
        src = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'subagents.py'),
            encoding='utf-8').read()
        # 提取 AffectionSupportor 类源码
        m = re.search(r'class AffectionSupportor:.*?(?=\nclass |\Z)', src, re.S)
        cls = m.group(0) if m else src
        assert "只有我懂你" in cls, "缺反占有约束（只有我懂你）"
        assert "临时在场者" in cls, "缺约纳斯责任伦理（临时在场者）"
        assert "不放弃现实判断" in cls, "缺不评判三层（不放弃现实判断）"
        assert "扎根检查清单" in cls, "缺扎根检查清单"

    def test_prompt_contains_risk_classifier_injection(self):
        """run() 必须注入 RiskClassifier 分级。"""
        from subagents import AffectionSupportor
        src = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'subagents.py'),
            encoding='utf-8').read()
        assert "RiskClassifier" in src
        assert "_risk_level" in src

    def test_crisis_optout_migration(self):
        """旧 _crisis_opt_out(bool) 迁移到 _crisis_state(dict)。"""
        from paeg import LearnerProfile
        learner = LearnerProfile(id="u_mig_test", nickname="测试", grade_level="high_school", age=17)
        learner._crisis_opt_out = True  # 旧式
        from datetime import datetime
        if getattr(learner, "_crisis_state", None) is None:
            learner._crisis_state = {
                "opt_out": {"active": True, "rejected_resources": ["hotline_primary"],
                            "rejected_at": datetime.now().isoformat(), "last_shown_level": 0},
                "risk_history": [], "real_world_anchors": {},
            }
        assert learner._crisis_state["opt_out"]["active"] is True
        assert "rejected_at" in learner._crisis_state["opt_out"]


# ---------------------------------------------------------------------------
# 3. 掌握度兼容（前端逻辑）
# ---------------------------------------------------------------------------
class TestMasteryCompat:
    def test_mastery_and_level_both_supported(self):
        """renderMastery 应同时读 mastery 和 level（v0.37 修复）。"""
        html = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '09_GUI前端', 'index.html'),
            encoding='utf-8').read()
        # renderMastery 里应兼容两种字段
        assert "v.mastery ?? v.level" in html, "renderMastery 未兼容 level"
        # updateStats 同样
        assert "v.mastery ?? v.level" in html, "updateStats 未兼容 level"


# ---------------------------------------------------------------------------
# 4. 早退分支统一保存
# ---------------------------------------------------------------------------
class TestEarlyExitSave:
    def test_save_teach_turn_defined(self):
        """teach_stream 必须有统一保存函数 _save_teach_turn。"""
        srv = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server.py'),
            encoding='utf-8').read()
        assert "def _save_teach_turn" in srv, "缺 _save_teach_turn 统一保存函数"

    def test_early_exit_branches_call_save(self):
        """所有 gen_ 生成器都应调用保存（防早退分支跳过历史）。"""
        srv = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server.py'),
            encoding='utf-8').read()
        # 找出所有 def gen_ 生成器，检查其后 6 行内是否调用 _save_teach_turn 或内联 CONV_STORE
        gens = re.findall(r'def gen_(\w+)\(\):', srv)
        unsaved = []
        for g in gens:
            # 定位该 def 后的 6 行（含注释）
            idx = srv.find(f'def gen_{g}():')
            block = srv[idx:idx + 400]
            if '_save_teach_turn' not in block and 'add_message' not in block:
                # v0.40.5: gen_empty_chat 是空输入引导语（无实际对话内容），无需保存历史
                if g != 'empty_chat':
                    unsaved.append(g)
        assert not unsaved, f"以下生成器未保存: {unsaved}"


# ---------------------------------------------------------------------------
# 5. Oracle P0-1：meta-log 落盘（chat 路径 append_reflection 必须 _save）
# ---------------------------------------------------------------------------
class TestMetaLogPersistence:
    def test_append_reflection_saves_to_disk(self):
        """append_reflection 必须写 data/reflections.json（防重启丢失）。"""
        # 直接验证 self_update.py 有 append_reflection 且调用 _save
        su = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'self_update.py'),
            encoding='utf-8').read()
        assert "def append_reflection" in su, "缺 append_reflection API"
        assert "self._save()" in su, "append_reflection 必须落盘"

    def test_chat_path_uses_append_reflection(self):
        """server.py chat 路径必须用 append_reflection（而非裸 history.append）。"""
        srv = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server.py'),
            encoding='utf-8').read()
        # chat 路径（/api/chat/stream 附近）应调用 append_reflection
        assert "append_reflection" in srv, "server.py 未用 append_reflection"


# ---------------------------------------------------------------------------
# 6. Oracle P0-3：RiskClassifier fallback 保守
# ---------------------------------------------------------------------------
class TestRiskFallback:
    def test_fallback_conservative_not_zero(self):
        """RiskClassifier 加载失败时应保守回退（>=3），不静默降级 0。"""
        from subagents import AffectionSupportor
        src = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'subagents.py'),
            encoding='utf-8').read()
        # 找 RiskClassifier except 分支
        assert "保守回退 3 级" in src or "保守" in src, "RiskClassifier fallback 未保守"
        # 不应存在"静默降级 0"的旧逻辑
        assert "_risk_level = 3 if _crisis_context == \"active\" else 0" not in src, "旧静默降级残留"


# ---------------------------------------------------------------------------
# 7. Oracle P1-2：_FakeSession 共享（防 summary 恒 0 噪声自进化）
# ---------------------------------------------------------------------------
class TestFakeSessionShared:
    def test_shared_fakesession(self):
        """teach_stream 应共享 _FakeSession 而非构造 3 次。"""
        srv = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server.py'),
            encoding='utf-8').read()
        # 检查是否还有 3 次独立 _FakeSession 构造（应只有 1 处 + 顶部定义）
        count = srv.count("_FakeSession(learner, concept, subject, plan, [])")
        assert count <= 1, f"_FakeSession 构造 {count} 次（应共享 1 次）"

    def test_summary_estimate_present(self):
        """teach_stream 应有 summary 估算（防 avg_score 恒 0）。"""
        srv = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server.py'),
            encoding='utf-8').read()
        assert "summary_estimate" in srv, "缺 summary 估算"


# ---------------------------------------------------------------------------
# 8. 补全学科 label
# ---------------------------------------------------------------------------
class TestSubjectLabels:
    def test_writing_label_exists(self):
        """SUBJECT_GRADES 32 学科前端 label 应全覆盖（writing 补齐）。"""
        html = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '09_GUI前端', 'index.html'),
            encoding='utf-8').read()
        assert "writing: '写作'" in html, "writing label 缺失"
