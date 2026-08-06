# PAEG v0.1 测试指南

> 版本：v0.1
> 时间：2026-08-06
> 状态：✅ 20 个测试全部通过 + 5 学科 demo 全部跑通

---

## 1. 测试结果（本次实测）

### 1.1 单元测试（14 个全部通过）

| 测试文件 | 用例数 | 结果 |
|---|---|---|
| `tests/test_diagnostor.py` | 2 | ✅ 通过 |
| `tests/test_presenter.py` | 2 | ✅ 通过 |
| `tests/test_worldview.py` | 7 | ✅ 通过 |
| `tests/test_self_update.py` | 3 | ✅ 通过 |

### 1.2 集成测试（6 个全部通过）

| 测试 | 结果 |
|---|---|
| test_e2e_physics（熵） | ✅ |
| test_e2e_math（负负得正） | ✅ |
| test_e2e_literature（特洛伊） | ✅ |
| test_e2e_ethics（电车难题） | ✅ |
| test_e2e_phenomenology（孤独） | ✅ |
| test_all_subjects_with_world_view_blend | ✅ |

### 1.3 5 学科 demo（test_demo.py）

全部跑通完整教学循环：**诊断 → 计划 → 呈现（3 步）→ 评估 → 调整 → 元认知反思 → 自我更新**。

| 学科 | 平均分 | 世界观语气 | 结果 |
|---|---|---|---|
| 物理（什么是熵？） | 0.77 | rigorous_cold | ✅ |
| 数学（为什么负负得正？） | 0.84 | rigorous_cold | ✅ |
| 文学（特洛伊战争） | 0.71 | contemplative | ✅ |
| 道德（电车难题） | 0.81 | warm_caring | ✅ |
| 生命现象学（孤独） | 0.67 | contemplative | ✅ |

自我更新验证：反思历史 5 条、发现策略 4 个、5 学科掌握度 EMA 更新、批处理统计正常。

---

## 2. 如何自己测试（操作步骤）

### 2.1 前提

- 需要 Python 3.9+（本机已装 3.14.2 / 3.9.13）
- **无需任何 API key**（v0.1 用 MockModel 模拟模型，纯本地运行）

### 2.2 运行全部测试

```powershell
cd "D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型\tests"
python test_diagnostor.py
python test_presenter.py
python test_worldview.py
python test_self_update.py
python test_integration.py
```

### 2.3 运行 5 学科 demo

```powershell
cd "D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型"
python test_demo.py
```

### 2.4 运行单个学科

```powershell
cd "D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型"
python -c "from paeg import PAEG, LearnerProfile; from knowledge_base import KnowledgeBase; p=PAEG(MockModel_placeholder(), KnowledgeBase()); print(p.teach(LearnerProfile(id='001', nickname='小李', grade_level='high_school', age=17), '什么是熵？', 'physics')['summary'])"
```

（MockModel 在 `paeg.py` 底部有示例定义。）

---

## 3. 你会看到什么

每次教学会打印完整流程：

```
[1/5] 诊断子代理：评估 小李 的当前水平...
   ✓ 诊断完成：True
[2/5] 计划子代理：设计教学路径...
   ✓ 计划完成：3 步
[3/5] 呈现子代理：第 1/3 步 - present - 直观讲解：什么是熵？
   ✓ 呈现完成：长度 47 字符
   → 评估子代理：检查学生理解...
   ✓ 评估分数：0.78
   → 调整子代理：触发调整...
   ✓ 决策：switch_style - 换类比讲法
[6/6] 元认知反思：本次教学总结...
   ✓ 反思完成
   ✓ 自我更新完成
```

---

## 4. v0.1 验证了什么

| 设计目标 | v0.1 验证 |
|---|---|
| G3 学科教学 | ✅ 5 学科端到端跑通（诊断→计划→呈现→评估→调整） |
| G4 技能教学 | ⚠️ 教学循环通用，技能策略待扩展 |
| G5 人文素养 | ✅ 文学/道德/生命现象学 3 科跑通 |
| G6 个人化 | ✅ 学习者画像 + 4 种世界观语气自动切换 |
| G1 自我懂得 | ⚠️ 元认知反思（每会话）跑通；每步/每周反思 v0.5 补 |
| G2 自我更新 | ✅ 增量更新（反思+策略发现+画像 EMA）+ 批处理统计 |

**v0.1 局限**：模型是模拟的（MockModel）；知识库仅 5 个节点；无交互式界面；无安全中间件。这些在 v0.5 解决。

---

## 5. 下一步（v0.5）

- 接入真实 LLM（DeepSeek / OpenAI / Anthropic / Ollama，抽象接口 + 可配置）
- 交互式教学 CLI（可对话式学习）
- 知识库扩展到 30+ 真实学科节点
- 安全中间件（政治/医疗/法律/儿童保护过滤）
- 自我更新持久化落盘（JSON 存储，可回滚）

---

**v0.1 测试完成。PAEG 最小原型验证通过，可以进入 v0.5 真实 LLM 阶段。**
