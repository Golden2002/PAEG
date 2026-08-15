# PAEG 差异化定位文档（§3.43 Step 1.6 · 2026-08-15）

> 来源：librarian 联网调研（6 主题 × 18 权威来源）+ Oracle 学段学科咨询
> 核心问题：**用户为何不用通用 AI（ChatGPT/DeepSeek/豆包），而用 PAEG？**

## 三大核心论据

1. **Wharton/PNAS 2025 "AI 悖论"**（Bastani et al., PNAS 2025）：通用 ChatGPT 让学生练习时 +48%，撤掉 AI 后考试 **-17%**（学生把 LLM 当拐杖）；加了"教师护栏"（只能提示不能给答案）则无显著劣势。→ **PAEG"我们比 ChatGPT 更适合学习"的最强证据**。
2. **Khan Academy 6.1% 实证**（2026 官方报告，1500 万条线程 A/B）：仅"提供学习历史+未掌握先决技能"就带来 **+6.1% next-item correctness**。→ **学习历史 + 学科图谱是数据护城河**（9 子代理共享 learner profile 的合法性）。
3. **Durlak SEL 元分析**（2011, 27 万学生, 213 项研究）：SEL 让学业 **+11 百分位**（ES=0.27）；Cipriano 2023 更新（424 项, 53 国, 57.5 万学生）仍显著。→ **情绪支持做进每个学科代理的合法性**。

## 五道护城河（PAEG vs 通用 LLM）

| 护城河 | 通用 LLM | PAEG |
|---|---|---|
| 过程化教学闭环（6 步：诊断→计划→讲解→评估→调整→反思）| ✗ | ✓ 每步有认知科学对应 |
| 学科教学法约束（35 学科 × 4 学段）| ✗ | ✓ method_guide + worked_example + subfield_guide |
| learner profile 数据（认知/情感/行为三维）| ✗ | ✓ users_data/profile.json 落盘 + BDI |
| 间隔重复算法（10-20% 留存间隔公式）| ✗ | ✓（规划中）|
| 儿童安全与合规（危机干预/年龄分层/COPPA/个保法）| 弱 | ✓ 危机协议（12356）+ 未成年人保护 |

## 支持证据（关键研究）

- **ITS 行业基线 g=0.66**（Kulik & Fletcher 2016, 50 项研究）；AI 自适应 g=0.70（2024 元分析, 45 项）
- **ITS 几乎与人类导师等效**：VanLehn 2011, ITS d=0.76 vs 人类导师 d=0.79
- **间隔重复 + 检索练习**：g=0.28（数学）/ g=0.50（检索练习 vs 重读）；最优间隔 = 保持间隔的 10-20%（Cepeda 2006）
- **Karpicke & Roediger 2008（Science）**：反复测试 > 反复学习；学生自评与实际表现无关 → 必须有客观评估
- **FTC 2025-09 调查**：7 家 AI 聊天机器人公司（含 OpenAI/Meta/Google）被查儿童负面影响
- **Character.AI 案（2025-05）**：联邦法官驳回"AI 受第一修正案保护"——聊天机器人非言论自由豁免主体
- **Common Sense Media 8 原则 + Red Lines**：漏检率 ≤5% 红线（自残/性剥削/暴力等）
- **UNESCO**：13 岁以下不应在课堂独立面向未充分测试的 GenAI

## 关键产品决策建议（8 项）

1. 把"Wharton -17%"做成营销标语（通用 AI 让学生考得更差）
2. KPI 必须含 next-item correctness（行业基线，非对话满意度）
3. 学习历史是核心资产（每多一个数据点 = 教学效果 +1pp）
4. 9 子代理共享 learner profile 存储（避免诊断/讲解脱节）
5. 情绪支持做进每个学科代理（挫败识别 + 薇依话术 + 任务拆解）
6. 安全做"冗余设计"（教学法约束 + 内容护栏 + 危机干预 + 合规 + 第三方审计）
7. 送 Common Sense Media 评估并公开结果（安全可信 = 品牌资产）
8. 薇依哲学作为"价值层"（重力→恩典→自由，可执行话术库）

## 引用源（18 个）

Khan Academy Blog 2026 / Duolingo Blog 2023-24 / PNAS 2025 Bastani / Stanford NSSA Wang / Nature 子刊 2025 Kestin / Kulik & Fletcher 2016 / VanLehn 2011 / Karpicke & Roediger 2008 Science / Adesope 2021 / Springer 2025 / Durlak 2011 / Cipriano 2023 / CASEL / Common Sense Media / FTC 2025-09 / Reuters-AP Character.AI / UNESCO 2023-24
