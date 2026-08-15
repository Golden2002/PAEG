"""
Pytest 版 Individuality v0.23.0 端到端测试

测试 3 个增强：
1. StudentTrait.update_from_dialogue / add_dimension / update_from_facts
2. Individuality.persist() 持久化闭环
3. Individuality 增量建模（第二次 run 看到已有画像）
"""
import sys, os, shutil, json
# v0.69+：reconfigure 移入 __main__——模块级执行会破坏 pytest capsys（收集期副作用）
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')

# 让测试可从 tests/ 目录 import 项目模块
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from subagents import Individuality
from student_trait import StudentTrait, ORTHOGONAL_DEFS, INJECTION_LEVELS
from paeg import LearnerProfile
from user_store import UserStore


class _MockLLM:
    """模拟 LLM 的增量建模行为。"""

    def __init__(self):
        self.call_count = 0
        self.last_system = None
        self.last_user = None

    @property
    def name(self):
        return "mock_llm"

    def chat(self, system, messages=None, max_tokens=512, **kw):
        from subagents import _is_leaky_reply
        self.call_count += 1
        self.last_system = system
        user_content = ""
        if messages:
            user_content = messages[-1].get("content", "")
        self.last_user = user_content
        is_incremental = "已有画像" in system

        # 第一轮：用户说"我代数很弱" → 提取 algebra 薄弱点
        if "我代数很弱" in user_content or "代数很弱" in user_content:
            if is_incremental:
                # 已有画像——只输出真正新增（这里没有）
                return '{"learning_style": "", "knowledge_strengths": [], "knowledge_gaps": [], "emotional_tendency": "", "motivation": "", "interests": []}'
            return '{"learning_style": "visual", "knowledge_strengths": [], "knowledge_gaps": ["algebra"], "emotional_tendency": "anxious", "motivation": "score", "interests": []}'

        # 第二轮：用户说"我喜欢蓝绿色" → 提取兴趣
        if "蓝绿色" in user_content:
            if is_incremental:
                return '{"learning_style": "", "knowledge_strengths": [], "knowledge_gaps": [], "emotional_tendency": "", "motivation": "", "interests": []}'
            return '{"learning_style": "", "knowledge_strengths": [], "knowledge_gaps": [], "emotional_tendency": "", "motivation": "", "interests": ["蓝绿色"]}'
        return "{}"


def _make_user() -> tuple:
    """注册一个临时测试用户。返回 (store, uid, learner)"""
    store = UserStore()
    test_id = "pytest_individuality_test@x.com"
    if test_id in store._data["users"]:
        del store._data["users"][test_id]
        store._save()
    reg = store.register(test_id, "pwd1234", "pytest_test")
    uid = reg["user_id"]
    learner = LearnerProfile(
        id=uid, nickname="测试", grade_level="high_school", age=17,
    )
    return store, uid, learner, test_id


def _cleanup(store, uid, test_id):
    store._data["users"].pop(test_id, None)
    store._save()
    udir = os.path.join(_ROOT, "users_data", uid)
    if os.path.isdir(udir):
        shutil.rmtree(udir)


# ─────────────────────────────────────────────────
# Enhancement 1：StudentTrait 动态更新方法
# ─────────────────────────────────────────────────
class TestStudentTraitDynamicUpdate:
    def test_update_from_dialogue_maps_6_categories(self):
        """update_from_dialogue 把 6 类 LLM 建模结果映射到 16 维。"""
        trait = StudentTrait()
        modeled = {
            "learning_style": "visual",
            "knowledge_strengths": ["geometry", "physics"],
            "knowledge_gaps": ["algebra", "calculus"],
            "emotional_tendency": "anxious",
            "motivation": "score",
            "interests": ["music", "soccer", "music"],  # dedup
        }
        trait.update_from_dialogue(modeled)
        assert trait.cognitive_style == "visual"
        assert "geometry" in trait.mastery
        assert trait.mastery["geometry"]["evidence_pos"]
        assert "algebra" in trait.mastery
        assert trait.mastery["algebra"]["evidence_neg"]
        assert trait.mastery["algebra"]["level"] <= 0.3
        assert trait.emotion == "anxious"
        assert trait.motivation == "score"
        # 第 18 维（interests）—— 去重
        assert trait.interests == ["music", "soccer"]

    def test_update_from_facts_dedup(self):
        trait = StudentTrait()
        trait.update_from_facts(["我喜欢蓝绿色", "我养了一只猫", "我喜欢蓝绿色"])
        assert trait.personal_facts == ["我喜欢蓝绿色", "我养了一只猫"]

    def test_add_dimension_doesnt_break_to_prompt(self):
        """动态扩展第 18/19 维 + to_prompt 自动包含。"""
        trait = StudentTrait()
        trait.add_dimension("sleep_pattern", {"avg": 7}, "睡眠节律")
        trait.add_dimension("device_usage", ["phone", "laptop"], "设备偏好")

        # dataclass 实例上确实有这些字段
        assert trait.sleep_pattern == {"avg": 7}
        assert trait.device_usage == ["phone", "laptop"]

        # ORTHOGONAL_DEFS 已追加
        names = [d["name"] for d in ORTHOGONAL_DEFS]
        assert "sleep_pattern" in names
        assert "device_usage" in names

        # INJECTION_LEVELS 已设默认 L3
        assert INJECTION_LEVELS["sleep_pattern"] == 3
        assert INJECTION_LEVELS["device_usage"] == 3

        # to_prompt(L3) 自动出现动态维
        prompt = trait.to_prompt(levels=[1, 2, 3])
        assert "sleep_pattern（动态扩展维）" in prompt
        assert "device_usage（动态扩展维）" in prompt
        assert "avg=7" in prompt
        assert "phone, laptop" in prompt

        # to_prompt(L1+L2) 默认不包含（动态维 L3）
        prompt_l12 = trait.to_prompt(levels=[1, 2])
        assert "sleep_pattern" not in prompt_l12

    def test_to_dict_from_dict_roundtrip_preserves_dynamic(self):
        trait = StudentTrait()
        trait.add_dimension("x_dim", {"a": 1, "b": 2})
        trait.update_from_facts(["fact1", "fact2"])
        trait.update_from_dialogue({"interests": ["music"], "knowledge_gaps": ["algebra"]})

        d = trait.to_dict()
        trait2 = StudentTrait.from_dict(d)
        # 动态字段已写入 dict
        assert d.get("x_dim") == {"a": 1, "b": 2}
        assert d.get("interests") == ["music"]
        assert "fact1" in d.get("personal_facts", [])
        # from_dict 恢复后属性可访问
        assert trait2.__dict__.get("x_dim") == {"a": 1, "b": 2}
        assert trait2.__dict__.get("interests") == ["music"]
        assert "fact1" in trait2.__dict__.get("personal_facts", [])
        # to_prompt 仍能输出
        prompt = trait2.to_prompt(levels=[1, 2, 3])
        assert "x_dim（动态扩展维）" in prompt


# ─────────────────────────────────────────────────
# Enhancement 2 & 3：Individuality 持久化 + 增量建模
# ─────────────────────────────────────────────────
class TestIndividualityPersistence:
    def setup_method(self):
        self.store, self.uid, self.learner, self.test_id = _make_user()

    def teardown_method(self):
        _cleanup(self.store, self.uid, self.test_id)

    def test_run_first_round_models_and_persists(self):
        """第一轮：用户说'我代数很弱' → LLM 建模 → 持久化。"""
        llm = _MockLLM()
        ind = Individuality()
        text = "老师好，我代数很弱"
        history = [{"role": "user", "content": text}]
        result = ind.run(model=llm, learner=self.learner, history=history, subject="math")
        assert result["llm_modeled"] is True
        assert "algebra" in ind._llm_modeled.get("knowledge_gaps", [])
        assert getattr(self.learner, "_individuality_trait", {}).get("knowledge_gaps") == ["algebra"]

        # 持久化
        ok = ind.persist(self.learner, self.uid)
        assert ok is True

        # 重读落盘
        store2 = UserStore()
        loaded = store2.load_learner(self.uid)
        assert loaded is not None
        assert "algebra" in loaded.get("_individuality_trait", {}).get("knowledge_gaps", [])
        assert "algebra" in loaded.get("subjects_mastery", {})
        assert "individuality_LLM" in loaded["subjects_mastery"]["algebra"]["evidence_neg"]

    def test_run_second_round_inherits_via_existing_modeled(self):
        """第二轮：增量建模——profile_prompt 含第一轮的薄弱点。"""
        # 第一轮
        llm1 = _MockLLM()
        ind1 = Individuality()
        text1 = "老师好，我代数很弱"
        ind1.run(
            model=llm1, learner=self.learner,
            history=[{"role": "user", "content": text1}], subject="math",
        )
        ind1.persist(self.learner, self.uid)

        # 模拟重启：从磁盘重建 learner
        store2 = UserStore()
        loaded = store2.load_learner(self.uid)
        learner2 = LearnerProfile(
            id=self.uid,
            nickname=loaded.get("nickname", "测试"),
            grade_level=loaded.get("grade_level", "high_school"),
            age=loaded.get("age", 17),
        )
        # 恢复动态属性
        learner2.subjects_mastery = loaded.get("subjects_mastery", {})
        if loaded.get("_individuality_trait"):
            learner2.__dict__["_individuality_trait"] = loaded["_individuality_trait"]
        if loaded.get("interests"):
            learner2.__dict__["interests"] = loaded["interests"]

        # 第二轮
        llm2 = _MockLLM()
        ind2 = Individuality()
        text2 = "顺便告诉你，我喜欢蓝绿色"
        history2 = [
            {"role": "user", "content": text1},
            {"role": "assistant", "content": "好的，我们来攻克代数。"},
            {"role": "user", "content": text2},
        ]
        result2 = ind2.run(model=llm2, learner=learner2, history=history2, subject="math")

        # 1. existing_modeled 已含第一轮的 algebra
        assert "algebra" in result2["existing_modeled"].get("knowledge_gaps", [])

        # 2. profile_prompt 注入含 algebra（证明增量继承）
        assert "algebra" in result2["profile_prompt"]

        # 3. LLM 看到了"已有画像"提示（增量模式）
        assert "已有画像" in llm2.last_system
