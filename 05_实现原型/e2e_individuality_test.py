"""
End-to-end self-test for Individuality enhancements (v0.23.0).

Verifies:
- Two-round dialogue: "我代数很弱" → 个体化建模 → 持久化 → 第二轮注入含薄弱点
- Dynamic dimensions (18/19) don't break to_prompt
- All three enhancements work together
"""

import sys, os, json, shutil
sys.stdout.reconfigure(encoding='utf-8')

WORK = r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型'
sys.path.insert(0, WORK)

from subagents import Individuality
from student_trait import StudentTrait, ORTHOGONAL_DEFS, INJECTION_LEVELS
from paeg import LearnerProfile
from user_store import UserStore


class MockLLM:
    """模拟 LLM：根据 system/user 内容返回对应的 JSON 建模结果。

    第一轮：用户说"我代数很弱" → LLM 模拟建模为 knowledge_gaps=[algebra]
    第二轮：用户说"我喜欢蓝绿色" → LLM 模拟建模为 interests=[蓝绿色]（无新增 gap）
    增量模式：若 system 提到"学生已有画像"，则只输出真正新增的项。
    """

    def __init__(self):
        self.call_count = 0
        self.last_system = None
        self.last_user = None

    def chat(self, system, messages=None, max_tokens=512, **kw):
        from subagents import _is_leaky_reply
        # 提取 user content
        user_content = ""
        if messages:
            user_content = messages[-1].get("content", "")
        self.last_system = system
        self.last_user = user_content
        self.call_count += 1

        # 检测增量模式（system 含"已有画像"）
        is_incremental = "学生已有画像" in system or "增量" in system

        # 第一轮：用户说"我代数很弱" → 必有 algebra 薄弱点
        if "我代数很弱" in user_content or "代数很弱" in user_content:
            if is_incremental and "algebra" in user_content:
                # 已建模过 algebra → 输出空增量
                return '{"learning_style": "", "knowledge_strengths": [], "knowledge_gaps": [], "emotional_tendency": "", "motivation": "", "interests": []}'
            return '{"learning_style": "visual", "knowledge_strengths": [], "knowledge_gaps": ["algebra"], "emotional_tendency": "anxious", "motivation": "score", "interests": []}'

        # 第二轮：用户说"我喜欢蓝绿色" → 必有蓝绿色兴趣
        if "蓝绿色" in user_content:
            if is_incremental:
                # 已有 interests——除非本次新增否则不重复
                # 简单模拟：返回空增量
                return '{"learning_style": "", "knowledge_strengths": [], "knowledge_gaps": [], "emotional_tendency": "", "motivation": "", "interests": []}'
            return '{"learning_style": "", "knowledge_strengths": [], "knowledge_gaps": [], "emotional_tendency": "", "motivation": "", "interests": ["蓝绿色"]}'

        # 默认
        return "{}"

    @property
    def name(self):
        return "mock_llm"


# ─────────────────────────────────────────
# 主测试
# ─────────────────────────────────────────
print("=" * 70)
print("【端到端自测】PAEG Individuality v0.23.0 持久化闭环")
print("=" * 70)

# Setup: 注册测试用户
store = UserStore()
test_id = 'e2e_test@x.com'
if test_id in store._data['users']:
    del store._data['users'][test_id]
    store._save()

reg = store.register(test_id, 'pwd1234', 'e2e测试')
uid = reg['user_id']
print(f"\n[Setup] Registered uid={uid}")

learner = LearnerProfile(
    id=uid, nickname='小明', grade_level='high_school', age=17,
    cognitive_style='unknown',
    self_description='我是一名高中生'
)
print(f"[Setup] LearnerProfile: id={learner.id}, nickname={learner.nickname}")

# ───── 第 1 轮对话 ─────
print("\n" + "─" * 70)
print("【第 1 轮】用户说：我代数很弱（首次对话，learner 暂无画像）")
print("─" * 70)

llm = MockLLM()
ind = Individuality()

history_r1 = []
text_r1 = "老师好，我代数很弱，怎么办？"
print(f"[User] {text_r1}")

# v0.23.0：模拟 server.py chat_stream——把本轮用户消息加进 history（与生产一致）
_ind_history_r1 = list(history_r1) + [{"role": "user", "content": text_r1}]
result_r1 = ind.run(model=llm, learner=learner, history=_ind_history_r1, subject="math")
print(f"\n[Individuality.run]")
print(f"  llm_modeled: {result_r1['llm_modeled']}")
print(f"  existing_modeled: {result_r1['existing_modeled']}")
print(f"  native_language: {result_r1['native_language']}")
print(f"  control: {result_r1['control']}")
print(f"  LLM 建模结果 (self._llm_modeled): {ind._llm_modeled}")
print(f"  [DEBUG] learner._individuality_trait = {getattr(learner, '_individuality_trait', None)}")
print(f"  [DEBUG] learner.subjects_mastery 键 = {list(learner.subjects_mastery.keys())}")

# 把本轮加入历史
history_r1.append({'role': 'user', 'content': text_r1})
history_r1.append({'role': 'assistant', 'content': '好的，我们来攻克代数。'})

print(f"\n[learner 状态]")
print(f"  _individuality_trait: {getattr(learner, '_individuality_trait', None)}")
print(f"  subjects_mastery: {learner.subjects_mastery}")
print(f"  interests: {getattr(learner, 'interests', None)}")

# 持久化（注册用户 → 落盘）
ok = ind.persist(learner, uid)
print(f"\n[persist] ok={ok} (True 表示已落盘)")

# 验证落盘
store2 = UserStore()
loaded = store2.load_learner(uid)
print(f"\n[reload from disk]")
print(f"  _individuality_trait: {loaded.get('_individuality_trait') if loaded else None}")
print(f"  subjects_mastery: {loaded.get('subjects_mastery') if loaded else None}")
print(f"  interests: {loaded.get('interests') if loaded else None}")

# 模拟服务器重启 → 重新加载 learner（验证持久化继承）
print(f"\n[模拟服务器重启——新建 LearnerProfile 实例]")
learner2 = LearnerProfile(
    id=uid, nickname=loaded.get('nickname', '小明'),
    grade_level=loaded.get('grade_level', 'high_school'),
    age=loaded.get('age', 17),
    cognitive_style=loaded.get('cognitive_style', 'unknown'),
    self_description=loaded.get('self_description', ''),
)
# 恢复持久化的字段
learner2.subjects_mastery = loaded.get('subjects_mastery', {})
if '_individuality_trait' in loaded:
    learner2.__dict__['_individuality_trait'] = loaded['_individuality_trait']
if '_individuality_trait_obj' in loaded:
    _t_dict = loaded['_individuality_trait_obj']
    if _t_dict:
        learner2.__dict__['_individuality_trait_obj'] = StudentTrait.from_dict(_t_dict)
if loaded.get('interests'):
    learner2.__dict__['interests'] = loaded['interests']

print(f"  恢复后 learner2._individuality_trait: {getattr(learner2, '_individuality_trait', None)}")

# ───── 第 2 轮对话 ─────
print("\n" + "─" * 70)
print("【第 2 轮】再次 run——LLM 看到'已有画像'，只输出新增项")
print("─" * 70)

llm2 = MockLLM()
ind2 = Individuality()

text_r2 = "顺便告诉你，我喜欢蓝绿色"
print(f"[User] {text_r2}")

# v0.23.0：模拟 server.py chat_stream——把本轮用户消息加进 history
history_r2 = list(history_r1)
_ind_history_r2 = history_r2 + [{"role": "user", "content": text_r2}]
result_r2 = ind2.run(model=llm2, learner=learner2, history=_ind_history_r2, subject="math")

print(f"\n[Individuality.run 第 2 次]")
print(f"  llm_modeled: {result_r2['llm_modeled']}")
print(f"  existing_modeled (前次): {result_r2['existing_modeled']}")
print(f"  profile_prompt 是否含'薄弱点: algebra'?")
profile = result_r2['profile_prompt']
contains_algebra = "algebra" in profile
contains_gap_phrase = "代数" in profile or "薄弱点" in profile
print(f"    含 'algebra' 词: {contains_algebra}")
print(f"    含 '代数/薄弱点': {contains_gap_phrase}")
print(f"  LLM prompt 是否看到'学生已有画像'? {('学生已有画像' in llm2.last_system)}")

# 验证：第二轮注入的 profile_prompt 包含第一轮的薄弱点（证明增量继承）
print(f"\n[profile_prompt 前 600 字]")
print(profile[:600])

# 验证 learner2 状态合并
print(f"\n[learner2 合并后]")
print(f"  _individuality_trait: {getattr(learner2, '_individuality_trait', None)}")
print(f"  subjects_mastery keys: {list(learner2.subjects_mastery.keys())}")
print(f"  algebra evidence_neg: {learner2.subjects_mastery.get('algebra', {}).get('evidence_neg')}")

print(f"\n[结论]")
print(f"  ✅ 第 2 轮注入含第 1 轮的薄弱点（algebra）— 增量继承工作正常"
      if contains_algebra else
      f"  ❌ 第 2 轮未继承第 1 轮的薄弱点")

# ─────────────────────────────────────────
# 动态维度扩展测试
# ─────────────────────────────────────────
print("\n" + "=" * 70)
print("【动态扩展维度测试】add_dimension 不破坏 to_prompt")
print("=" * 70)

# 创建新 StudentTrait + 动态加 2 个维度（第 18/19 维）
trait = StudentTrait()
trait.add_dimension('sleep_pattern', {'avg_hours': 7, 'preferred_time': 'late'},
                    orthogonality='睡眠节律——与学习节奏正交')
trait.add_dimension('device_usage', ['phone', 'laptop'],
                    orthogonality='设备偏好——与协作偏好正交')

print(f"\n[add_dimension 验证]")
print(f"  trait.sleep_pattern: {trait.sleep_pattern}")
print(f"  trait.device_usage: {trait.device_usage}")
print(f"  ORTHOGONAL_DEFS 末尾两条:")
for d in ORTHOGONAL_DEFS[-2:]:
    print(f"    - {d['name']:15s} | {d['type']:18s} | {d['value_space'][:40]}")

# to_prompt 应该包含新维度
prompt_l3 = trait.to_prompt(levels=[1, 2, 3])
print(f"\n[to_prompt(level=L3) 含新维度?")
print(f"  含 'sleep_pattern（动态扩展维）': {'sleep_pattern（动态扩展维）' in prompt_l3}")
print(f"  含 'device_usage（动态扩展维）': {'device_usage（动态扩展维）' in prompt_l3}")
print(f"  含 'avg_hours=7': {'avg_hours=7' in prompt_l3}")
print(f"  含 'phone, laptop': {'phone, laptop' in prompt_l3}")

# 默认 L1+L2 不应包含（动态维默认 L3）
prompt_l12 = trait.to_prompt(levels=[1, 2])
print(f"\n[to_prompt(level=L1+L2) 默认不包含新维度?")
print(f"  含 'sleep_pattern': {'sleep_pattern' in prompt_l12}")

# to_dict/from_dict 往返
d = trait.to_dict()
trait2 = StudentTrait.from_dict(d)
print(f"\n[round-trip]")
print(f"  trait2.sleep_pattern: {trait2.sleep_pattern}")
print(f"  trait2.device_usage: {trait2.device_usage}")
print(f"  to_prompt 仍含新维度: {'sleep_pattern（动态扩展维）' in trait2.to_prompt(levels=[1,2,3])}")

# ─────────────────────────────────────────
# 清理
# ─────────────────────────────────────────
print("\n" + "=" * 70)
print("【清理测试数据】")
print("=" * 70)
store3 = UserStore()
if test_id in store3._data['users']:
    del store3._data['users'][test_id]
    store3._save()
    print(f"  ✓ Removed user {test_id}")
udir = os.path.join(WORK, 'users_data', uid)
if os.path.isdir(udir):
    shutil.rmtree(udir)
    print(f"  ✓ Removed dir {udir}")
print(f"  ✓ Test data cleaned\n")
