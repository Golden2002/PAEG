# runoob AI Agent 七篇文档学习记录 + PAEG 对照评估

> 整理日期：2026-08-14
> 用途：Step5 逐字阅读记录（先记录，后实施改造）
> 来源：https://www.runoob.com/ai-agent/ （7 篇）
> 状态：✅ 7/7 全部逐字读完

---

## 一、逐字阅读要点记录

### 1. Agent 架构（六种主流架构）
- **单 Agent 循环（ReAct）**：感知→推理→行动→观察循环；上下文窗口是主要瓶颈（>15 轮工具调用不适合）
- **规划+执行（Plan & Execute）**：Planner 生成步骤 → Executor 执行；动态重规划更健壮；Claude Plan Mode 体现
- **多 Agent 协作**：Orchestrator + Subagent，独立上下文是核心优势
- **反思/自我修正（Reflection）**：执行→Critic 评估→Reviser 修正；自我反思 vs Critic 模型
- **RAG + Agent**：Agent 主动决定何时检索、检索什么（区别于被动一次性 RAG）
- **工作流 DAG**：低自主性高可预测性；节点内部可是 Agent
- **选型原则**：从最简开始，按需增加复杂度

### 2. AI Agent 工作原理（三大组成）
- **大脑（LLM）**：决策/推理/规划
- **工具（Tools）**：手和脚，扩展能力
- **记忆（Memory）**：短期（对话历史）+ 长期（知识库）
- ReAct 循环：思考→行动→观察→再思考
- Agent 类型：反应式/目标导向/实用型/学习型/多智能体

### 3. 推理与规划（六框架）
- **CoT**：先显式输出中间推理步骤（Let's think step by step）
- **ReAct**：Thought→Action→Observation 闭环；长链易上下文爆炸
- **Plan-and-Execute**：Planner 拆解 + Executor 独立上下文执行
- **ToT/MCTS**：树状多路径探索 + 评估回溯
- **Reflexion**：失败→写反思→存情景记忆→指导下一次（自愈合）
- **工程干预**：子任务模板化（SOP 状态机）/ HITL 人工审批 / RLHF

### 4. AI Agent 简介（Agent 公式）
- **Agent = LLM + Planning + Tool use + Memory**
- 五大特征：自主性/反应性/主动性/社交能力/学习能力
- 挑战：幻觉/边界失控（Scope Creep）/成本/安全隐私
- 最佳实践：渐进式自主/人工监督/持续评估/容错机制

### 5. 提示词工程（重点）
- **五段式架构**：角色与目标/背景知识(XML标签)/行为规则/输出格式/示例
- **XML 标签隔离数据与指令**（防提示词注入）：`<document>` `<user_input>` `<context>` `<example>` 等
- **思维链触发**：`<thinking>` 标签隔离 / 一步一步来 / 先列论据再下结论（顺序关键：先分析后结论）
- **防幻觉五策略**：①允许说"我不知道" ②只使用提供信息 ③先找证据再结论 ④置信度标注 ⑤temperature=0
- **提示词链**：复杂任务拆分子任务，前一步输出作下一步输入，每步独立验证
- **元提示**：用 AI 生成/改进提示词
- **四要素**：角色/指令/背景/限制
- **Token 意识**：System Prompt ≤500 token；重要指令放开头或结尾（Lost in the Middle）

### 6. AI 底层架构（五层）
- 基础层（模型）：LLM/Transformer/Token
- 上下文层（记忆）：Context Window/Prompt/Memory/RAG
- 能力扩展层（工具）：MCP/Tool Calling/API/数据库
- 智能体层（决策）：Agent/Explore/Plan/Act
- 应用层（行动）：Skill/Workflow/Automation
- 运行流程：用户输入→记忆增强→LLM 推理→Agent 规划→工具执行→输出+写记忆

### 7. Agent 上下文工程（重点）
- **上下文预算管理**：System 10% / 工具定义 20% / 检索 25% / 历史 30% / 用户输入 5-10% / 缓冲 5%（200K 窗口示例）
- **系统提示工程化**：分层组织（Markdown 标题）/ 正面表述 / 提供示例 / 优先级明确 / 去除冗余
- **工具描述优化**：精简（移除无关工具省 30-50% token）/ 一句话描述 / 参数约束 / 分组注册
- **历史压缩策略**：滑动窗口/阶梯摘要/分层摘要（近 3-5 轮完整，远期结构化摘要）/关键轮标记
- **检索质量控制**：查询改写/相关性过滤/来源标注/长度裁剪
- **渐进式披露**：按执行阶段逐步注入工具和规则
- **上下文压缩链**：每步只保留精炼中间结果
- **上下文水印**：注入策略版本/来源/消耗量，便于调试
- **评估维度**：任务完成率/上下文效率/工具调用质量/响应一致性

---

## 二、PAEG 对照评估（现状 vs 文档标准）

| 维度 | 文档标准 | PAEG 现状 | 差距 |
|---|---|---|---|
| **Agent 架构** | 六种架构组合 | teach 六阶段=Plan-and-Execute；9 subagent=多 Agent；自进化=Reflexion；workflows=DAG | ✅ 多种组合已具备 |
| **推理规划** | CoT/ReAct/Reflexion | Presenter 有教学法但**无显式 CoT 标签**；自进化=Reflexion（G 区缺口）| ⚠️ 缺 CoT 结构化 |
| **记忆** | 短期+长期分层 | SESSIONS(短期)+画像(长期)；**无独立记忆模块**（NEW-1）| ⚠️ 需强化 |
| **工具** | MCP 标准 | config_hub+MCP 已实现 | ✅ |
| **防幻觉** | 五策略 | **⚠️ 缺失**（NEW-9 最高优先：不联想/不编造/以信源为绝对命令）| ❌ 关键缺口 |
| **上下文工程** | 预算管理/压缩策略/渐进披露 | context_bundle 打包 + prompt_template 动态槽；**缺预算管理/分层摘要/水印**（NEW-2）| ⚠️ 需强化 |
| **提示词结构** | 五段式+XML 隔离 | WEIL_CORE+学科 style+动态槽；**缺 XML 标签隔离用户资料**（防注入缺口）| ⚠️ |
| **评估** | 任务完成率/上下文效率/一致性 | 132 测试 + audit/smoke；**缺 LLM-as-judge 输出质量评估**（NEW-4）| ⚠️ |
| **权限边界** | 渐进式自主/人工监督 | tool risk 三档；**缺 Permission Preset**（NEW-7）| ⚠️ |

---

## 三、改造需求表（由清单驱动）

| 优先级 | 改造项 | 对应清单 ID |
|---|---|---|
| P0 | **防幻觉底层约束注入**（不联想/不编造/信源为绝对命令）| NEW-9（最高优先）|
| P1 | 上下文工程强化（预算/分层摘要/水印）| NEW-2 |
| P1 | 输出质量 LLM-as-judge 评估 | NEW-4 |
| P1 | 记忆模块分层 | NEW-1 |
| P2 | XML 标签隔离用户资料（防注入）| 并入 NEW-9/安全 |
| P2 | CoT 结构化（presenter 教学加 <thinking> 或分步）| 智能性维度 |
