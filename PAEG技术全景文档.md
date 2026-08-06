# PAEG 教育者智能体 — 技术全景文档

> **版本**：v0.19.12（2026-08-06）
> **适用对象**：项目维护者（你本人）
> **目的**：让你从零到一掌握 PAEG 的每个环节——大模型、智能体架构、后端、前端、网络部署、日常维护与升级。读完本文档，你能独立理解、排查、升级这套系统。
> **项目位置**：`D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\`

---

## 目录

1. [系统总览](#1-系统总览)
2. [大模型知识（LLM 基础）](#2-大模型知识llm-基础)
3. [智能体架构（PAEG 核心）](#3-智能体架构paeg-核心)
4. [后端服务（server.py + API）](#4-后端服务serverpy--api)
5. [前端界面（GUI）](#5-前端界面gui)
6. [网络与公网部署](#6-网络与公网部署)
7. [日常维护与排错](#7-日常维护与排错)
8. [关机/断连后的恢复](#8-关机断连后的恢复)
9. [如何升级与扩展](#9-如何升级与扩展)
10. [附录：文件地图 & 测试](#10-附录文件地图--测试)

---

# 1. 系统总览

## 1.1 这是什么

**PAEG**（Pedagogical Agent with Evolving Growth，自我更新的教育者智能体）是一个**教育 AI 系统**：学生（你或任何访问网页的人）提问，PAEG 用大模型（DeepSeek）生成自然、有教学法的讲解，并记录学习画像、持续自我更新。

## 1.1.1 设计目标（回到初衷 ⭐）

> **一句话**：在"人的温度"的基础上，提供超越普通人的教育专业性——而不是反过来，变成一套刻板模板、一套话术、神志不清地回答所有问题。

PAEG 的设计目标分层：

| 层次 | 目标 | 实现 |
|---|---|---|
| **第一层：像人** | 有温度、真诚、不刻板、不套模板 | 薇依人格（WEIL_CORE）+ presenter 总原则"先做人，再教书" |
| **第二层：专业** | 讲解有结构、有深度、能迁移 | 好讲解质量标准 + 学科黄金法则 + 讲义级结构 + 指令类型判断 |
| **第三层：真实** | 不编造、可核查 | 工具调用（联网搜索/数学验证）+ 拒绝编造协议 |
| **第四层：个体化** | 每个学生被当独立的人 | 用户画像 + BDI + 三层记忆 + 用户资料库 |

**核心判断**：任何功能/提示词都服从一个标准——"这个回答，对眼前这个学生有用吗？他听完会更好吗？"规范是为学生服务的，不是学生为规范服务。

## 1.2 一句话架构

```
浏览器（手机/电脑）
    │  HTTPS
    ▼
Cloudflare 隧道 (trycloudflare.com)      ← 公网入口，转发到本地
    │  HTTP 127.0.0.1:5000
    ▼
Flask server.py (本地 Python 服务)        ← 后端：提供网页 + API
    │
    ├─ GUI (index.html)                   ← 前端：教学对话界面
    ├─ PAEG 智能体核心 (paeg.py)          ← 教学流程编排
    │     ├─ 5 子代理 (subagents.py)      ← 诊断/计划/呈现/评估/调整
    │     ├─ 学科提示词 (prompts.py)      ← 让 LLM 讲"人话"
    │     ├─ 知识库 (knowledge_base.py)   ← 学科/素养/技能节点
    │     ├─ 世界观 (world_view.py)       ← 教学语气切换
    │     └─ 自我更新 (self_update.py)    ← 画像持久化
    └─ 大模型客户端 (llm_api.py)
          │  调用 DeepSeek API
          ▼
    DeepSeek 大模型（云端，真正的"大脑"）
```

**关键点**：你的电脑只做**中转**——接收请求、编排教学流程、转发给 DeepSeek。真正的"思考"在云端完成。所以电脑 CPU/内存负担极小。

## 1.3 数据流（一次完整教学）

```
用户提问 "什么是熵？"
  → GUI 发 POST /api/teach
  → server 创建/查找学习者画像
  → PAEG.teach() 编排：
      ① Diagnostor 诊断（学生水平）→ ② Planner 计划（3 步）
      ③ Presenter 呈现 ×3（每步调 DeepSeek 生成讲解）→ ④ Evaluator 评分
      ⑤ 反思 + 自我更新（更新画像）
  → 返回 JSON（3 段讲解 + 评分 + 画像）
  → GUI 逐步显示气泡对话
```

## 1.4 Agent 指挥 LLM 的工作机制（⭐ 核心设计）

PAEG 之所以比"直接使用 LLM"更强，是因为它在每次对话时，由 **Agent（编排层）综合五路信息指挥 LLM**：

```
用户输入（当前问题）
   │
   ▼
┌─────────────────────────────────────────────┐
│ Agent 编排层（server.py / paeg.py / prompts）│
│                                             │
│  打包五路上下文 → 注入 system/user prompt：  │
│                                             │
│  ① 提示词（顶层设计）                        │
│     · 薇依人格（WEIL_CORE：先做人再教书）    │
│     · 回复三原则（准确性/组织性/功能性）     │
│     · 学科黄金法则 + 讲义级结构              │
│     · 语言铁律（去 AI 味）                   │
│                                             │
│  ② 知识库（Library/ + KnowledgeBase/）      │
│     · 学科事实节点                          │
│     · 用户上传的资料（Library/user_<id>/）  │
│                                             │
│  ③ 工具（tool_registry：5 工具 + skills）   │
│     · web_search / verify_math / fetch_page │
│     · daily_quote / get_time / load_skill__ │
│     · LLM 自主判断何时调用（function calling）│
│                                             │
│  ④ 用户数据                                 │
│     · 画像（自我描述/掌握度）               │
│     · BDI（信念/愿望/意图推断）             │
│     · 三层记忆（短期对话/摘要/长期）        │
│     · 教学记忆（PAEG_PEDAGOGY.md）          │
│                                             │
│  ⑤ 用户输入 + 页面设定（模式/学段/学科）    │
└─────────────────────────────────────────────┘
   │
   ▼
Agent 指挥 LLM 的循环（run_agent_loop）：
   1. 先理解（结合全部上下文）
   2. 需要时调用工具（不编造，标注来源）
   3. 自我检查（针对问题？需验证？够深入？）
   4. 输出高质量内容
   ▲              │
   └── 工具结果回传 LLM，继续完善 ──┘
```

### 回复内容的三原则

| 原则 | 含义 | 落实 |
|---|---|---|
| **准确性** | 回答针对用户的问题，不答非所问；不编造事实 | 指令类型判断（直接请求/概念疑问/做题）+ 工具调用查证 + 打包全部上下文 |
| **组织性** | 输出像优秀讲义：结构清晰、层次分明、内容详实 | 好讲解质量标准 + 学科黄金法则 + 讲义级结构 |
| **功能性** | 用户可复制、可生成文档、可上传资料 | 复制按钮 + 多选生成文档 + 关键词（讲义/要点/例题/笔记）+ 资料上传 |

### 功能真实有效的保障（架构连通性）

所有模块**不是空有文件**，而是真正接入调用链（详见 §10.6 arch_check.py 检测）：

- **工具调用链**：chat → run_agent_loop → tool_registry → (tool_recovery/tool_cache/skills)
- **记忆链**：chat → MemorySystem → 摘要压缩 + 持久化
- **资料链**：用户上传 → Library/user_<id>/ → 注入 system
- **知识链**：Library/ + KnowledgeBase/ → 教学时注入

> 每次改动后运行 `python arch_check.py`，连通率必须保持 100%（§10.6）。

---

# 2. 大模型知识（LLM 基础）

## 2.1 我们用的模型：DeepSeek

- **供应商**：DeepSeek（深度求索），API 地址 `https://api.deepseek.com/v1`
- **协议**：OpenAI 兼容接口（`POST /chat/completions`，Bearer token 认证）
- **模型**：DeepSeek 系列（V3/R1 等，具体取决于你 API 账号的可用模型）
- **计费**：按 token 计费（输入 + 输出），你本地 `~/.config/opencode/auth.json` 里存着 API key

## 2.2 关键概念：Token

- **Token** = 模型处理文本的最小单位。中文大约 **1 个汉字 ≈ 1-1.5 token**；英文 1 词 ≈ 1-2 token
- 每次请求 = 输入 token（你的 prompt）+ 输出 token（模型回答）
- PAEG 单次教学约消耗 **2000-5000 token**（3 步讲解 × 每步约 400-600 字）
- 成本估算：DeepSeek 很便宜（约 ¥1-2 / 百万输入 token），一次完整教学约几厘钱

## 2.3 关键概念：Prompt（提示词）

大模型不是"数据库"，是"**根据指令续写文本**"的概率模型。**你怎么说，它怎么答**——这就是提示词工程。

- **System prompt**（系统提示）：设定角色的"人设、规则、语气"。PAEG 的 `prompts.py` 就是干这个的
- **User prompt**（用户消息）：具体任务（"请讲解：什么是熵？"）
- **Temperature**（温度）：0 = 每次回答一样（确定性），1 = 随机发挥。PAEG 用 0.7（教学需要稳定又有点自然）

## 2.4 为什么之前教学"浮夸"，现在"像人话"了？

| 之前的问题 | 现在的解法 |
|---|---|
| system prompt 里塞了 `世界观比例：{1: 0.05, 2: 0.70...}` 数字字典 | **删除数字噪音**，改为可读的教学风格描述 |
| 语气只写"你冷静、严谨"（抽象） | 给**具体行为指导**："用生活中看得见的现象引入" |
| 所有学科用同一个模板 | **每个学科专属 persona + 语言风格 + 教学结构**（prompts.py） |
| 没禁止套话 | **ANTI_FLOWERY 反浮夸约束**：禁止"知识的海洋""点亮智慧"等 |

**核心思想**：与其让模型"猜"你想要什么，不如直接告诉它"像一位具体的物理老师那样，用墨水散开的现象讲熵"。

---

# 3. 智能体架构（PAEG 核心）

## 3.1 主类：paeg.py

`PAEG` 类是心脏，`teach()` 方法编排完整教学流程。学习画像用 `LearnerProfile`（dataclass），会话上下文用 `SessionContext`。

## 3.2 5 个子代理（subagents.py）

| 子代理 | 职责 | 是否用 LLM |
|---|---|---|
| **Diagnostor** 诊断 | 评估学生当前水平、知识缺口 | 是（JSON 输出深度建议）|
| **Planner** 计划 | 设计 3 步教学路径（直观→形式→应用）| 否（规则驱动）|
| **Presenter** 呈现 | 生成教学讲解（核心！）| **是**（调 DeepSeek）|
| **Evaluator** 评估 | 给每次讲解评分（0.4-0.95）| 否（确定性启发式）|
| **Adapter** 调整 | 分数低时换策略 | 否（规则驱动）|

## 3.3 学科提示词中心：prompts.py（v0.8.2 ⭐）

这是教学的核心文件，**集中管理教师人格与所有教学提示词**。三大组成部分：

### 3.3.1 教师画像：薇依（Simone Weil）⭐ 顶层设计灵魂

`WEIL_CORE` 定义了 PAEG 的教师人格——**不是普通教师，而是以法国哲学家西蒙娜·薇依为画像**：

- **爱通过行动体现，不靠言语**：对学生、对他人的爱，通过"对知识的态度"和"教学方法"流露
- **注意力（attention）是教学的最高目的**："你欠学生的不是看法、不是认可、不是赞美，而是注意力——注意力是最稀有、最纯粹的慷慨"
- **爱学生 = 能真心问"你正在经历什么？"**：不把学生当"待灌输的对象"，而是与你一样的人
- **教学是"等待真理"而非"灌输答案"**：思想应当"空的、等待的"，先确认听懂再回应
- **错误是通向真理的入口**：引导看清错误根源，不评判、不羞辱
- **不评分、不催促、不煽情**：热情、同情、鼓励话术都不是注意力的替代品
- **谦逊是注意力的耐心**：不假装全知

### 3.3.2 学科风格：SUBJECT_STYLES（25 个）

```python
SUBJECT_STYLES = {
    "physics": {...}, "math": {...}, "chemistry": {...}, "biology": {...},
    "geography": {...}, "chinese": {...}, "politics": {...}, "history": {...},
    "english": {...}, "french": {...}, "german": {...}, "japanese": {...},
    "philosophy": {...}, "aesthetics": {...}, "literature": {...}, "ethics": {...},
    "phenomenology": {...}, "kaoyan_math": {...}, "kaoyan_politics": {...},
    "writing": {...}, "coding": {...}, "thinking": {...}, "learning": {...},
    "expression": {...}, "default": {...},
}
```
每个学科定义：persona（角色）/ language（怎么讲）/ structure（节奏）/ emphasis（侧重）。

### 3.3.3 学段分层：_GRADE_GUIDE（4 个学段）

```python
_GRADE_GUIDE = {
    "middle_school": "用生活化语言，从具体现象入手，少用术语…",
    "high_school": "在直觉之上建立较严谨表述，给定义/公式/例题…",
    "undergraduate": "直接进入概念本身，给严格定义/推导/批判性讨论…",
    "graduate_exam": "以考点为导向，明确命题意图/解题套路/真题演示…",
}
```
同一学科在不同学段，讲解深度与方式自动切换。

### 3.3.4 一般对话：build_general_chat_*

不限定学科的自由对话，薇依式倾听与陪伴（理解 → 复述确认 → 陪伴 → 不急着给结论）。

- `build_presenter_system(subject, tone, learner, kb_node)` → 学科教学 system prompt
- `build_presenter_user(subject, topic, step_type)` → 学科教学 user prompt
- `build_general_chat_system(learner)` / `build_general_chat_user(text)` → 一般对话 prompt
- **改教学风格 → 改这个文件**，不需要动其他代码

## 3.4 世界观：world_view.py

决定"这个学科该用什么语气讲"：
- physics/math → `rigorous_cold`（严谨）
- literature/phenomenology → `contemplative`（沉思）
- ethics → `warm_caring`（关怀）
- career/skill → `pragmatic`（务实）

## 3.5 知识库：knowledge_base.py

- **80 个节点**：52 学科节点 + 12 素养 + 5 教学法 + 5 案例 + 6 技能
- 覆盖 20 个学科（含用户要求的 15 个学科体系），按学段（初中/高中/本科/考研）分层
- 每个节点：定义/直觉/例子/误区/前置知识/世界观适配
- 作用：给 LLM 提供**事实锚点**（防止编造），但**不决定说话方式**（那是 prompts.py 的事）
- 扩展节点在 `subjects_ext.py`（数据驱动，新增学科只需加数据）

## 3.5.1 教学策略库：pedagogy.py（v0.9 ⭐）

基于教学法理论（EEF 工具包、Bloom 修订版、Vygotsky ZPD、Ericsson 刻意练习）实现"诊断 → 策略选择"：

| 策略 | 适用场景 | 教学步骤 |
|---|---|---|
| **苏格拉底式** | 学生已有基础、目标是高阶思维（分析/评价）| 引问 → 追问 → 收敛 |
| **支架式（ZPD）** | 学生基础差、全新概念 | 示范 → 带做 → 放手 |
| **掌握式** | 技能/理科基础课 | 精讲 → 小测 → 矫正 |
| **费曼式** | 学生"懂但说不出"、复盘阶段 | 讲一遍 → 找漏洞 → 补缺口 |
| **刻意练习** | 程序性技能、易错 | 要点 → 同型练习 → 变式 |
| **综合式** | 默认 | 直观 → 形式 → 应用 |

选择逻辑：诊断的 `recommended_depth` + `identified_gaps` + 学科默认 Bloom 层级 → 决定策略。
每个步骤带 `bloom`（认知层级）和 `strategy_hint`（教学策略提示），注入 Presenter 的 system prompt。

## 3.6 自我更新：self_update.py

- 每次教学后记录反思、更新学习者画像（EMA 指数移动平均掌握度）
- 数据存 `data/` 目录（profiles.json / reflections.json / strategies.json）
- **可回滚**：版本化存储

## 3.7 智能体基础架构：agent_core.py（v0.10 ⭐）

参照 opencode / codex 等通用 agent 的基础设计，为 PAEG 提供三层通用骨架
（教学专用逻辑仍在 paeg.py，这里是可复用的 agent 底座）：

| 组件 | 作用 | 用法 |
|---|---|---|
| **ToolRegistry** | 工具注册与调用（agent 的能力边界）| `reg.register(Tool(name, desc, func))` → `reg.run(name, **kwargs)` |
| **AgentLoop** | 统一的"感知→规划→行动→反思"主循环 | `loop.run(ctx, plan_fn, act_fn, reflect_fn)` |
| **ContextManager** | 上下文组装（系统上下文+用户画像+会话历史）| `cm.build_system(ctx)` / `cm.build_history(ctx)` |
| **AgentContext** | 一次执行的完整上下文（含 user_description）| 由 `new_session(user_id)` 创建 |

设计要点：
- **新能力 = 注册新工具**，不修改主流程
- **新场景 = 用 AgentLoop 跑**，可复用同一骨架
- 教学流程（teach）未来可重构为 AgentLoop 上的一种"策略"

## 3.8 用户自我描述（v0.10 ⭐）

用户可以在网页上写下"我是怎样的人、学习目标、擅长与不擅长"等描述：

- **存储**：`LearnerProfile.self_description` 字段（存在内存 + self_update 持久化）
- **注入**：`prompts.py` 在每次构建 system prompt 时，把描述作为
  `## 这位学生对自己的描述（TA 亲笔写的，请始终尊重并据此教学）` 注入
- **生效范围**：学科教学 + 一般对话都注入
- **API**：
  - `PUT /api/profile/<id>` → `{self_description: "..."}` 保存
  - `GET /api/profile/<id>` → 返回 `self_description`
- **GUI**：左栏"学习者画像"卡片 → "✏️ 告诉老师你是谁" 展开编辑器

**效果**：学生写下"我擅长物理、怕数学"，之后每次对话 PAEG 都会据此调整教学——
用物理类比讲生物、对怕数学的学生放慢节奏多鼓励。

## 3.9 对象意识：用户建模（v0.11 ⭐）

PAEG 能感知不同用户，对不同用户有不同反应。机制分两层：

### 3.9.1 自我描述（显式）
用户主动写的"我是谁/目标/擅长与不擅长"（见 3.8）。

### 3.9.2 对话推断（隐式）——`agent_core.infer_user_model()`
从会话历史 + 自我描述**自动推断**用户特征，无需用户额外操作：

| 推断维度 | 信号 | 教学影响 |
|---|---|---|
| 情绪状态 | "焦虑/紧张/害怕" → anxious；"有意思/明白了" → engaged | 焦虑→放慢节奏、多确认；投入→保持挑战 |
| 困难信号 | "不懂/不会/没听懂" | 给更小的台阶、多检查理解 |
| 能力线索 | 自述"擅长/喜欢" + 对话"我会/明白了" | 直接进入高阶、给挑战 |
| 参与度 | 消息条数 | high/medium/low |

**实现**：`paeg.teach()` 每次调用 `infer_user_model` → 存到 `learner._user_model` →
`prompts.build_presenter_system(user_model=...)` 注入 system prompt。

**效果验证**：同一问题"什么是二次函数"，焦虑型用户得到"先别急着怕…你准备好了我们就往下走"；
自信型用户得到"我们先不从定义开始…今天我们把碗放开"。同一问题，不同对待。

## 3.10 知识库扩展接口（v0.11 ⭐）

为未来加入大量知识库预留了接口和文件夹：

```
Library/
├── KnowledgeBase/          ← 从这里加知识（推荐）
│   ├── subjects/*.json     ← 学科知识节点（与 knowledge_base.py 同构）
│   ├── facts/*.md          ← 事实资料（用文件名当主题标签）
│   └── README.md           ← 扩展指南
├── Language/  Math/  Philosophy/  Simone Weil/   ← 可索引的源文件
```

- **加载器**：`library_loader.KnowledgeLibrary` —— 扫描 Library，把学科节点并入 KnowledgeBase，
  提供 `search_facts()` 检索事实资料
- **API**：`GET /api/knowledge/library` → 返回 Library 统计与源文件列表
- **扩展方法**：加知识 = 往 subjects/ 放 JSON 或 facts/ 放 MD，重启 server 即生效
  （详见 `Library/KnowledgeBase/README.md`）

## 3.11 文件生成与下载（v0.12 ⭐）

让智能体生成可下载的文件（练习题 / 讲解文章）：

- **生成器**：`file_generator.FileGenerator`
  - `generate_quiz(learner, subject, topic, n_questions)` → 练习题（含答案与解析）
  - `generate_article(learner, subject, topic, length)` → 讲解文章
- **API**：
  - `POST /api/generate` → `{type: "quiz|article", subject, topic, ...}` 返回 `{filename, download_url}`
  - `GET /api/download/<filename>` → 下载文件（Markdown 格式）
- **GUI**：对话区下方"生成文件"栏 → 出练习题 / 写讲解文章 + 下载链接
- 文件保存在 `05_实现原型/downloads/` 目录

## 3.12 语言优化 Agent（v0.12 ⭐）

专门去除 AI 痕迹、让语言接近薇依的后处理层：

- **文件**：`language_refiner.py` + `weil_corpus.json`（10 条薇依真实语料）
- **机制**：
  1. `detect_ai_tells(text)`：检测常见 AI 腔（"让我们/综上所述/加油/的海洋中"等 30+ 模式）
  2. `refine(text)`：若检测到 AI 痕迹，用薇依语料作为 few-shot 案例，让 LLM 改写
- **接入**：`PAEG.teach()` 在 Presenter 生成后自动矫正（`presentation["refined"]=True` 标记）
- **效果**："让我们踏上这段奇妙的学习之旅吧！…加油！" → 
  "熵不是一个神秘的东西。它只是一个物理量，一个数字…你不需要相信什么，你只需要观察。"

## 3.13 新方法加强（v0.13 ⭐）

基于 2024-2026 实证研究（Self-Refine/DetectGPT/Binoculars/BDI-ToM/MemoryOS），三项加强：

### 3.13.1 AI 味风格检测器（ai_taste_detector.py）
用 5 个客观信号检测 AI 痕迹（替代纯规则匹配）：
- **句长变异度**：AI 句子均匀（CV<0.35），人类长短交替（CV>0.45）
- **过渡词密度**：furthermore/moreover/总的来说 等（每千字计数）
- **三段式清单**：AI 偏爱"三点/三步"，薇依用二/四/七
- **破折号数量**：AI 连用 em-dash
- **段落对称性**：AI 段落等长

### 3.13.2 Self-Refine 多轮改写（language_refiner.py 升级）
- Init → 检测 AI 味 → Feedback（给出具体信号）→ Refine → 复检
- 最多 2 轮，AI 概率 < 0.4 停止
- **效果**：AI 概率 0.4 → **0.186**（Human）

### 3.13.3 Actor-Critic 自我认知反思（paeg.py `_self_reflect`）
教学完成后自检三方面：
- **薇依对齐**：是否有廉价鼓励/评判性语言（薇依反对）
- **语言质量**：是否有 AI 味（用检测器）
- **教学有效性**：评估分数是否达标
输出改进建议，写入反思日志（可观测）

### 3.13.4 BDI 用户建模（agent_core.py `infer_bdi`）
基于 Theory of Mind（信念-愿望-意图三要素）推断学生心理状态：
- **信念**：自我怀疑/学科畏难/成长型心态/固定心态
- **愿望**：想理解/在意成绩/怕丢脸/有好奇心
- **意图**：在提问/在求助/可能要放弃/在求证
推断结果注入 prompt，并给出教学调整建议（如"ta 想放弃→降低难度"）

## 3.14 语法完整性与用户系统（v0.14 ⭐）

### 3.14.1 语法完整性（language_refiner.py + prompts.py）
教学语言要求**每个句子语法结构完整**（有主谓宾），不写省略句/无主句：
- ❌ "一句话记住：…" → ✅ "我们可以用一句话来记住：…"
- ❌ "先看一个现象" → ✅ "我们先来看一个现象。"
- ❌ "再看它周围是否独一份" → ✅ "我们再来看它周围是否只有它这一条闭合轨道。"

实现：`_check_ellipsis()` 按标点切句检测省略（动词开头命令句/"一句话记住"模式/"关键在"短句），
检测到即触发 Self-Refine 改写补全。

### 3.14.2 Markdown 渲染（GUI）
对话框支持 Markdown：**加粗/斜体/标题/列表/代码/表格/引用/链接**。
用 marked.js（CDN）+ 内置 fallback，消息气泡用 `.md-content` 渲染。

### 3.14.3 用户注册系统（user_store.py + API + GUI）
- **注册**：邮箱或手机号 + 密码（SHA-256 + salt 哈希，不存明文）
- **登录**：验证并加载持久化画像
- **持久化**：`users.json` 保存用户 + 学习者画像（含 self_description、mastery）
- **API**：`POST /api/register`、`POST /api/login`
- **GUI**：顶栏"登录/注册"按钮 + 弹窗；登录后 user_id 固定，**刷新不丢画像**
- **效果**：不同用户有独立画像和反应（个体性持久）

### 3.14.4 下拉菜单小三角（GUI）
学段/学科下拉框加 SVG 三角箭头提示（appearance:none + 背景图）。

## 3.15 自我更新与系统优化（v0.15 ⭐）

### 3.15.1 自我更新（self_evolve.py）
基于 Reflexion + ExpeL + Library Drift 防护 的自我进化闭环：

| 层 | 机制 | 说明 |
|---|---|---|
| **会话级微反思** | `on_session_end()` | 教学后若 EMA 掌握度下降 → LLM 诊断原因 → 写反思日志 |
| **周度洞察提取** | `weekly_insight_update()` | 从近期反思聚类失败模式 → 提取"触发条件→行动"规则 |
| **洞察反馈** | `record_insight_use()` | 每条洞察记录使用效果（UPVOTE/DOWNVOTE）|
| **Drift 防护** | cap=50 + min_evidence + 贡献分 | 防止无治理更新导致退化（检索退化/注入伤害/路由器失效）|

### 3.15.2 教学去重复（核心修复）
根因：Presenter 的 user prompt 只含 topic（都是同一概念）→ 三步重复。
修复：`build_presenter_user` 携带**前文摘要**（前两步内容要点）+ 每步 topic 明确阶段
（"本步讲直觉和现象"/"本步讲机制和定义，在上一步基础上深入"/"本步讲应用/辨析/练习，不重复前两步"）。

### 3.15.3 知识库缓存
`KnowledgeBase.resolve_node(concept, subject)`：缓存检索结果，避免每次教学重复 search。

### 3.15.4 每用户独立文件夹
```
users_data/<user_id>/
├── profile.json      学习者画像（自我描述/掌握度）
├── history.jsonl     对话历史（追加）
├── notes/            用户笔记/生成文件
└── insights.json     该用户的学习洞察
```
登录用户每次教学后自动追加历史（供自我进化/个性化使用）。

## 3.16 名字、词汇策略与 UI 优化（v0.16 ⭐）

### 3.16.1 名字：Émile Novis
PAEG 有了人类名字——**Émile Novis（埃米尔·诺维斯）**。学生可叫 Émile 或"埃米尔老师"。
AI 从不自称"AI/智能体"，被问到时说"我是 Émile Novis，你的老师"。
名字已注入 WEIL_CORE + GUI 顶栏 + 欢迎语。

### 3.16.2 词汇排斥策略
把 AI 味浓的形容词加入词库（`ai_taste_detector.AI_MARKERS` + `language_refiner.AI_TELLS`），输出时排斥：
- **"稳了"类**：稳了/拿捏了/妥了/没跑了/妥妥的/稳稳的/轻松拿下/绝绝子/yyds 等
- **空洞赞美**：深刻/全面/系统/本质/深远/独到
- **策略**：检测器命中 → Self-Refine 改写排除；prompts 明确禁止

### 3.16.3 公式渲染 + HTML 修复
- **MathJax**：支持 `$...$` 和 `\(...\)` 渲染数学公式（配置在 GUI）
- **step-tag 修复**：步骤标签作为 `preHtml` 参数分离，不进入 markdown 渲染（避免被转义成文本）

### 3.16.4 随便说说模式（原"一般对话"）
- 模式名改为**随便说说**
- **本质区别**：chat 模式不调用教学流程（无 5 子代理/无评估），纯粹薇依式倾听陪伴
- **带对话历史**：连续对话（记录最近 20 条，多轮上下文）
- **带用户画像 + BDI**：注入自我描述和信念/愿望/意图推断

### 3.16.5 去除 Emoji
UI 中 19 处 emoji 替换为纯文本（头像用 É 字母，按钮纯文字）。

---

# 4. 后端服务（server.py + API）

## 4.1 是什么

Flask 写的本地 Web 服务，**同时提供网页和 API**。默认监听 `0.0.0.0:5000`。

## 4.2 API 端点一览

| 端点 | 方法 | 作用 | 请求示例 |
|---|---|---|---|
| `/` | GET | 返回 GUI 网页 | — |
| `/api/health` | GET | 健康检查（知识库统计）| — |
| `/api/teach` | POST | **核心**：执行一次教学 | `{subject, concept, learner_id, nickname}` |
| `/api/teach/stream` | POST | 流式教学（SSE 逐字输出）| 同上 |
| `/api/chat` | POST | **一般对话**（v0.8.2，薇依式倾听）| `{text, learner_id, grade_level}` |
| `/api/profile/<id>` | GET | 获取学习者画像 | — |
| `/api/profile/<id>` | PUT | **更新画像**（v0.10，含自我描述）| `{self_description: "..."}` |
| `/api/meta-log/<id>` | GET | 元认知日志 | `?limit=10` |
| `/api/skills` | GET | 列出技能节点（v0.8）| — |
| `/api/knowledge/library` | GET | **Library 扩展信息**（v0.11）| — |
| `/api/generate` | POST | **生成文件**（v0.12）| `{type: quiz\|article, subject, topic}` |
| `/api/download/<f>` | GET | **下载文件**（v0.12）| — |
| `/api/register` | POST | **注册**（v0.14）| `{identifier, password, nickname}` |
| `/api/login` | POST | **登录**（v0.14）| `{identifier, password}` |
| `/api/knowledge/search` | GET | 搜索知识库 | `?q=熵&subject=physics` |
| `/api/batch` | POST | 批处理（每周）| — |
| `/api/quote` | GET | **每日一句**（v0.17，薇依等六位思想家轮换）| — |
| `/api/solve` | POST | **做题模块**（v0.18）：标准答案 | `{problem, subject, grade_level, learner_id}` |
| `/api/save-document` | POST | **保存文档**（v0.18）：回答→MD+HTML | `{title, content, subject}` |
| `/api/conversations/<uid>` | GET | **列出会话**（v0.18）| — |
| `/api/conversations/<uid>` | DELETE | **清空全部会话**（v0.18）| — |
| `/api/conversations/<uid>/<cid>` | GET | **读取某会话**（v0.18）| — |
| `/api/conversations/<uid>/<cid>` | DELETE | **删除某会话**（v0.18）| — |
| `/api/conversations/cleanup` | POST | **定期清理**（v0.18，手动触发）| — |

## 4.3 关键：/api/teach 请求格式

```json
{
  "learner_id": "web_xxx",        // 学习者标识（首次自动创建）
  "nickname": "小林",
  "subject": "physics",            // 学科 key
  "concept": "什么是熵？"           // 要学的内容
}
```

响应包含：`session_id`、`presentations[]`（3 段讲解）、`summary`（评分）、`learner`（更新后的画像）。

---

# 5. 前端界面（GUI）

## 5.1 是什么

`09_GUI前端/index.html` —— 单文件网页（无框架、无依赖，纯 HTML+CSS+JS）。

## 5.2 界面结构

- **顶栏**：品牌 + 连接状态指示灯 + 模式切换（教学/技能/素养）
- **左栏**：学习者画像（掌握度进度条）、学习数据统计、元认知日志
- **右栏**：对话窗口 + 学科选择 + 输入框 + 快捷提问 chips

## 5.3 技术要点

- **CSS 变量**（`:root` 里定义颜色），改主题只需改几个变量
- **Fetch API** 调后端：`fetch('/api/teach', {method:'POST', ...})`
- **同源部署**：GUI 和 API 在同一个 server，`API_BASE = ''` 即相对路径
- **30 秒健康检查**：`setInterval(checkHealth, 30000)`

## 5.4 想改 UI？直接编辑 index.html 的 CSS/HTML 即可，无需动后端。

---

# 6. 网络与公网部署

## 6.1 网络拓扑

```
你的电脑（内网 IP，如 10.163.246.118）
    ├─ PAEG server  :5000（本地服务）
    ├─ cloudflared  （隧道客户端，建立到 Cloudflare 的出站连接）
    │     │  出站 HTTPS（无需开放入站端口！）
    ▼
Cloudflare 边缘网络 → 公网 URL https://xxx.trycloudflare.com
    │
    ▼
任何设备浏览器（手机/平板/异地电脑）都能访问
```

**为什么用隧道**：你的电脑在 NAT 后面（没有公网 IP，或公网 IP 被运营商隔离）。cloudflared 主动"拨号"到 Cloudflare，建立反向通道——**不需要路由器端口映射，不需要公网 IP**。

## 6.2 当前方案（A：临时隧道）

- 启动命令：`D:\devtools\cloudflared.exe tunnel --url http://127.0.0.1:5000`
- 每次启动会生成**随机 URL**（如 `https://girlfriend-object-combines-paragraphs.trycloudflare.com`）
- **缺点**：URL 每次变；进程停止则隧道关闭
- **适合**：临时演示、快速测试

## 6.3 升级方案（B：固定域名，未来可选）

1. 注册域名（如 xxx.top，一年几十块）并托管到 Cloudflare（免费）
2. `cloudflared tunnel login` 授权
3. `cloudflared tunnel create paeg` 建正式隧道
4. `cloudflared tunnel route dns paeg 你的域名` 绑域名
5. 配置 config.yml → 固定 URL，永久不变

---

# 7. 日常维护与排错

## 7.1 查看系统是否在跑

```powershell
# PAEG server
Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
# cloudflared 隧道
Get-Process cloudflared -ErrorAction SilentlyContinue
# 微信桥 wbo（如果还在用）
wbo status
```

## 7.2 常见问题速查

| 现象 | 原因 | 解决 |
|---|---|---|
| 网页打不开 | server 没启动 | 运行 `python server.py` |
| 网页打开但教学报错 | DeepSeek key 失效/欠费 | 检查 `~/.config/opencode/auth.json` |
| 公网 URL 打不开 | cloudflared 进程停了 | 重新运行隧道命令 |
| 修改代码后不生效 | server 没重启 | 杀 5000 端口进程 → 重启 server |
| 端口被占用 | 有残留 server | `taskkill /F /PID <pid>` |
| 测试报 ModuleNotFoundError | 缺 PYTHONPATH | 运行前设 `$env:PYTHONPATH=项目目录` |

## 7.3 日志在哪

- **PAEG server**：无日志文件（Flask 默认输出到控制台）。启动时用 `> server.log 2>&1` 重定向可保存
- **cloudflared**：隧道 URL 打印在启动窗口
- **自我更新数据**：`05_实现原型/data/`（profiles.json 等）

---

# 8. 关机/断连后的恢复

> 核心原理：**所有服务都是本地进程**。电脑关机 = 进程全停 = 公网 URL 失效。开机后重新拉起即可。

## 8.1 最简恢复（一键脚本）

`D:\wbo-workspace\start-paeg-public.ps1` 已备好，**双击运行**（或在 PowerShell 里 `powershell -File D:\wbo-workspace\start-paeg-public.ps1`）：
1. 自动清理残留 server（释放 5000 端口）
2. 启动 PAEG server（后台）
3. 启动 cloudflared 隧道（前台，显示新公网 URL）

**使用方法**：运行后等 5-15 秒，窗口出现 `https://xxx.trycloudflare.com` 就是新的公网地址，复制到任何设备浏览器打开即可。**该窗口必须保持打开**（关闭 = 公网断开）。电脑重启后重新双击本脚本即可恢复。

## 8.2 手动恢复（如果脚本失效）

```powershell
# 1. 启动后端
cd "D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型"
python server.py

# 2. 新开一个窗口，启动隧道
D:\devtools\cloudflared.exe tunnel --url http://127.0.0.1:5000
# 复制输出的 https://xxx.trycloudflare.com
```

## 8.3 数据会丢吗？

**不会**。学习画像、反思记录存在本地 `data/` 目录；代码在硬盘上。关机只影响"在线服务"，不影响数据。

## 8.4 开机后想要全自动？（未来可选）

用 Windows 任务计划程序创建"开机触发"任务，运行 `start-paeg-public.ps1`——开机即自动恢复公网访问。

---

# 9. 如何升级与扩展

## 9.1 调整教学风格（最常见需求）

编辑 `05_实现原型/prompts.py` 中对应学科的字段：

```python
"physics": {
    "persona": "你是一位...",      # 角色定位
    "language": "先用...",          # 说话方式
    "structure": "顺序：...",       # 讲课节奏
    "emphasis": "特别强调...",      # 侧重
}
```
改完重启 server 即生效。

## 9.2 新增学科

1. 在 `prompts.py` 的 `SUBJECT_STYLES` 加一条（如 `"biology": {...}`）
2. 在 `world_view.py` 的 `THEME_TONE_MAP` 加对应语气（可选）
3. 在 `knowledge_base.py` 加知识节点（可选，但推荐——防止编造）
4. 在 `index.html` 的 `<select>` 加选项
5. 重启 server

## 9.3 新增技能节点（G4）

在 `knowledge_base.py` 的 `_load_skills()` 加一条：

```python
s["skill.cooking.egg"] = {
    "id": "...", "category": "cooking", "name": "煎蛋",
    "definition": "...", "steps": [...], "practice": "...", "pitfalls": [...],
}
```

## 9.4 升级到固定域名（方案 B）

见 §6.3。核心是把临时隧道换成命名隧道 + 域名绑定。

## 9.5 增强功能（未来方向）

| 方向 | 说明 |
|---|---|
| 多模态 | 图片/语音（需要 DeepSeek 多模态支持或换模型）|
| 云端同步 | 画像存云端（CRDT）|
| 教师/家长接口 | 管理界面 |
| 会话记忆增强 | 多轮对话上下文 |

---

# 10. 附录：文件地图 & 测试

## 10.1 文件地图

```
14_教育者Agent项目/
├── 01_需求文档/          需求规格（G1-G6 定义）
├── 02_用户决策记录/       关键决策（世界观比例、GUI、考研）
├── 03_架构设计_迭代/      v1-v3 架构演进
├── 04_最终设计/          最终架构定稿
├── 05_实现原型/          ⭐ 核心代码
│   ├── paeg.py           主类（教学编排）
│   ├── agent_core.py     ⭐ 智能体基础架构（Tool/AgentLoop/Context/用户建模，v0.10/0.11）
│   ├── library_loader.py ⭐ 知识库扩展加载器（Library/KnowledgeBase，v0.11）
│   ├── file_generator.py ⭐ 文件生成器（练习题/文章/下载，v0.12）
│   ├── language_refiner.py ⭐ 语言优化 Agent（Self-Refine 多轮，v0.12/0.13）
│   ├── ai_taste_detector.py ⭐ AI 味检测器（5 信号，v0.13）
│   ├── user_store.py      ⭐ 用户注册与画像持久化（v0.14/0.15：独立文件夹）
│   ├── self_evolve.py     ⭐ 自我更新（Reflexion+ExpeL+Drift防护，v0.15）
│   ├── weil_corpus.json   薇依语料（10 条，few-shot 矫正用）
│   ├── subagents.py      5 子代理
│   ├── prompts.py        ⭐ 学科提示词中心（v0.8.1）
│   ├── knowledge_base.py 知识库（61 节点）
│   ├── world_view.py     世界观/语气
│   ├── self_update.py    自我更新
│   ├── llm_api.py        大模型客户端
│   ├── llm_adapter.py    兼容层
│   ├── safety.py         安全中间件
│   ├── cli.py            命令行交互
│   ├── server.py         Flask 后端
│   ├── prompts.py        ⭐ 教师画像（薇依）+ 语言风格 + 学科×学段提示词
│   ├── pedagogy.py       ⭐ 教学策略库（苏格拉底/支架/掌握/费曼，v0.9）
│   ├── subjects_ext.py   15 学科扩展节点
│   ├── tests/            27 个测试
│   └── data/             画像/反思持久化
├── 06_测试与验证/         测试用例 + 验收报告
├── 07_参考与勘误/         API 契约、自检报告
├── 08_Loop记录/          开发循环记录
├── 09_GUI前端/
│   └── index.html        网页前端（含教学动作按钮+意图标签）
└── intermediate/         运行日志/过程记录/自我反思报告
```

## 10.2 测试命令

```powershell
cd "D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型"
$env:PYTHONPATH = $PWD

# 单元 + 集成测试（27 个）
python -m pytest tests -q

# v0.5 验收测试（32 个）
python -m pytest "..\06_测试与验证\tests\test_paeg_v0_5.py" -q

# 离线 demo（不联网，5 学科）
python test_demo.py

# 真实 LLM demo（用 DeepSeek）
python test_demo_real_llm.py --provider auto
```

### 评估 Harness（v0.19 ⭐）

两层测试体系，`eval_harness.py`：

```bash
cd "05_实现原型"

# 快速模式：只测意图识别（寒暄/身份/出题/概念），几秒完成
python eval_harness.py --fast

# 完整模式：调真实 LLM 评估输出质量（意图+公式+深度+tool-use），约 30-60 秒
python eval_harness.py
```

评估维度：
- **意图识别**：寒暄 / 元问题 / 出题请求 / 概念教学是否正确路由
- **公式格式**：数学回答是否使用 `$...$`，有无损坏的 `$`
- **回答深度**：expert_guard 深度评分（长度/套话/理科公式/论述结构）
- **Tool-Use**：工具调用正确性（正常/重试/错误恢复降级）

报告输出到 `eval_report.json`。

## 10.3 版本历史

> 完整修改日志已拆分至独立文档：**[CHANGELOG.md](./CHANGELOG.md)**（v0.1 → v0.19.12 全部记录）。
> 本文档只保留当前版本摘要。

**当前版本 v0.19.12**：回到初衷——"人的基础上更具教育专业性"。新增 presenter 总原则"先做人，再教书"（所有结构/规范指令服务于帮助眼前的学生，不机械套模板），卷首语优化（去重复、更自然、留白收尾）。上一版 v0.19.11 完成答非所问根治 + 用户资料上传模块。

---

## 10.4 从 GitHub 拉取并部署到自己的电脑/服务器

> 目标：任何人都可以从 `https://github.com/Golden2002/PAEG` 拉取项目，在**自己的 PC 或云服务器**上跑起来。
> 全程约 10 分钟（不含安装 Python 的时间）。

### 10.4.1 前置要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | ≥ 3.10（建议 3.12+）| 开发环境用 3.14 验证过 |
| pip | 随 Python | 装依赖用 |
| 网络 | 能访问 api.deepseek.com | 需要真实的 LLM API key（见下） |

### 10.4.2 拉取项目

```bash
# 方式一：git clone（推荐）
git clone https://github.com/Golden2002/PAEG.git
cd PAEG

# 方式二：下载 zip（没有 git 时）
#   打开 https://github.com/Golden2002/PAEG → Code → Download ZIP → 解压
```

### 10.4.3 安装依赖

```bash
cd "05_实现原型"

# 核心依赖（Flask 后端）
pip install flask flask-cors requests sympy fastmcp

# 可选：MCP 网关（让外部智能体连接 PAEG 工具）
pip install fastmcp

# 可选：联网搜索升级（不装也能用 Bing 免 key 兜底）
pip install requests
```

### 10.4.4 配置 LLM（DeepSeek）

PAEG 会自动按以下顺序查找模型凭据：

1. **环境变量**（推荐）：
   ```bash
   # Windows PowerShell
   $env:DEEPSEEK_API_KEY = "sk-你的key"
   # Linux/macOS
   export DEEPSEEK_API_KEY="sk-你的key"
   ```
2. **opencode auth.json**（`~/.config/opencode/auth.json` 里的 deepseek key）
3. 都找不到 → 启动**离线模拟模式**（MockLLM，可跑通流程但回答是占位的）

> 没有 DeepSeek key？去 https://platform.deepseek.com 注册，充值几块钱就够测试。

### 10.4.5 启动服务

```bash
cd "05_实现原型"
# Windows
set PYTHONPATH=%CD%
python server.py

# Linux/macOS
PYTHONPATH=$PWD python server.py
```

启动成功后看到：
```
[PAEG Server] 启动在 http://localhost:5000
[PAEG Server] GUI 在 http://localhost:5000/
[PAEG Server] 健康检查 http://localhost:5000/api/health
[PAEG Server] MCP 网关已启动: http://localhost:8765/mcp
```

浏览器打开 **http://localhost:5000** 即可使用。

### 10.4.6 验证

```bash
# 健康检查（应返回 200）
curl http://localhost:5000/api/health

# 跑测试（59 个，2 秒）
cd "05_实现原型"
python -m pytest tests "..\06_测试与验证\tests\test_paeg_v0_5.py" -q

# 跑评估 harness（7 个案例，调真实 LLM 约 30 秒）
python eval_harness.py --fast    # 快速：只测意图识别
python eval_harness.py           # 完整：调 LLM 评估输出质量
```

### 10.4.7 部署到云服务器（公网访问）

**方式 A：Cloudflare 临时隧道（免费，适合演示）**

在项目目录跑（需先启动 server.py）：
```bash
cloudflared tunnel --url http://localhost:5000
```
会输出一个 `https://xxx.trycloudflare.com` 地址，任何人可访问。

**方式 B：nginx + 系统服务（长期稳定）**

```bash
# 1. 用 systemd 管理 server.py（Linux）
sudo tee /etc/systemd/system/paeg.service <<'EOF'
[Unit]
Description=PAEG Education Agent
After=network.target

[Service]
WorkingDirectory=/opt/PAEG/05_实现原型
Environment=PYTHONPATH=/opt/PAEG/05_实现原型
Environment=DEEPSEEK_API_KEY=sk-xxx
ExecStart=/usr/bin/python3 server.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable paeg && sudo systemctl start paeg

# 2. nginx 反代（可选：加 HTTPS/域名）
#    server { listen 80; location / { proxy_pass http://127.0.0.1:5000; } }
```

**安全提示**：公网部署建议：
- 用户注册/登录已内置（`/api/register`），可防止匿名滥用
- 若不需要公网，保持 localhost 即可

---

## 10.5 可扩充与更新的资源清单

> 维护升级 PAEG 时，以下是**最容易扩充/更新**的资源点。每个都独立成文件，改动不影响其他模块。

### 10.5.1 每日一句语料库（quotes.py）

| 位置 | 说明 |
|---|---|
| `05_实现原型/quotes.py` | 47 句语录，`DAILY_QUOTES` 列表 |

**如何扩充**：
- 直接往 `DAILY_QUOTES` 列表追加 `{"text": "...", "author": "...", "source": "..."}`
- 每句格式：`text`（句子）、`author`（作者）、`source`（出处，可空）
- 已收录：西蒙娜·薇依、汉斯·约纳斯、胡塞尔、维特根斯坦、斯宾诺莎、怀特海
- **可加**：更多思想家、中国古典（孔子/庄子）、教育格言、学科名言
- 按日期自动轮换（`day_index % len(DAILY_QUOTES)`），加多少句都行

### 10.5.2 用户模型 / 画像（user_store.py + agent_core.py）

| 位置 | 说明 |
|---|---|
| `05_实现原型/user_store.py` | 用户注册、画像持久化、对话历史 |
| `05_实现原型/agent_core.py` | `infer_user_model`（对象意识）、`infer_bdi`（信念/愿望/意图）|
| `05_实现原型/memory_system.py` | 三层记忆（短期/中期/长期+摘要）|

**可扩充**：
- **画像字段**：在 `LearnerProfile`（paeg.py）加字段（如学习风格、目标院校、薄弱科目），保存逻辑自动兼容
- **BDI 模型**：`agent_core.py` 的 `infer_bdi` 里可加更多心理维度（如动机类型、挫败感阈值）
- **对话摘要**：`memory_system.py` 的摘要压缩策略（保留条数、摘要长度可调）

### 10.5.3 学科与教学法（prompts.py + pedagogy.py + subjects_ext.py）

| 位置 | 说明 |
|---|---|
| `05_实现原型/prompts.py` | 学科风格（SUBJECT_STYLES）+ 学段分层（_GRADE_GUIDE）|
| `05_实现原型/pedagogy.py` | 教学策略库 |
| `05_实现原型/subjects_ext.py` | 扩展学科 |

**可扩充**：
- **新学科**：在 `SUBJECT_STYLES` 加 dict（label/persona/language/structure/emphasis）
- **新学段**：在 `_GRADE_GUIDE` 加 dict（如"专升本""国际课程"）
- **教学策略**：`pedagogy.py` 加新策略函数，`PEDAGOGY_MAP` 注册即可

### 10.5.4 语言词库（ai_taste_detector.py + language_refiner.py）

| 位置 | 说明 |
|---|---|
| `05_实现原型/ai_taste_detector.py` | `AI_MARKERS`（483 条 AI 味/网络用语）|
| `05_实现原型/language_refiner.py` | `AI_TELLS`（406 条，本地预检）|

**可扩充**：
- 往 `AI_MARKERS` / `AI_TELLS` 追加词条（新网络用语、新 AI 腔）
- 建议每季度更新一次（追踪《咬文嚼字》年度网络用语）

### 10.5.5 技能库（skills/ 目录）

| 位置 | 说明 |
|---|---|
| `05_实现原型/skills/<技能名>/SKILL.md` | 4 个技能（math-solver/essay-feedback/study-planner/concept-explainer）|

**如何新增技能**：
1. 建目录 `skills/你的技能名/SKILL.md`
2. 写 frontmatter：`name` + `description`（描述触发条件）
3. 正文写工作流程和输出规范
4. 重启服务，`SkillRegistry` 自动扫描加载

### 10.5.6 知识库（Library/KnowledgeBase + knowledge_base.py）

| 位置 | 说明 |
|---|---|
| `Library/KnowledgeBase/` | 知识库扩展文件（README.md 有指南）|
| `05_实现原型/knowledge_base.py` | 55+ 知识节点 |

**可扩充**：
- 往 `Library/KnowledgeBase/` 加主题文件（含"直觉/定义/形式定义/核心问题"字段）
- `library_loader.py` 自动注册新节点

### 10.5.7 评估用例（eval_harness.py）

| 位置 | 说明 |
|---|---|
| `05_实现原型/eval_harness.py` | `default_cases()` 里的案例列表 |

**可扩充**：
- `ev.add_case("问题", subject=..., expect_type=..., expect_keywords=[...])`
- 加更多学科/题型/边界案例，形成回归测试集

### 10.5.8 对话历史存储（ConversationStore）

| 位置 | 说明 |
|---|---|
| `05_实现原型/user_store.py` | `ConversationStore` 类 |

**可调参数**：
- `retention_days=30`（会话保留天数）
- `max_conversations=50`（每用户会话数上限）
- `users_data/<user_id>/` 下按用户隔离存储

### 10.5.9 工具链（tool_registry + tool_recovery + tool_cache + web_search_tool）

| 位置 | 说明 |
|---|---|
| `05_实现原型/tool_registry.py` | 5 个 Function Calling 工具（web_search/verify_math/fetch_page/daily_quote/get_time）+ agent loop |
| `05_实现原型/tool_recovery.py` | 错误分类（瞬时/永久/限流/配额）+ 指数退避重试 + 失败降级 |
| `05_实现原型/tool_cache.py` | 工具结果缓存（canonical key + 按工具 TTL）|
| `05_实现原型/web_search_tool.py` | 搜索后端（Bing 免 key 默认 + Tavily/Serper 可选）|

**可扩充**：
- **新工具**：在 `tool_registry.py` 加 `_make_tool(...)` 定义 + `_HANDLERS` 注册 + `TOOL_TTL`（tool_cache）加 TTL
- **搜索后端**：配 `TAVILY_API_KEY` / `SERPER_API_KEY` 环境变量自动升级搜索质量
- **工具缓存 TTL**：`tool_cache.py` 的 `TOOL_TTL` 表按需调整（如 web_search 时效性高可缩短）

### 10.5.10 上下文管理（context_manager.py）

| 位置 | 说明 |
|---|---|
| `05_实现原型/context_manager.py` | 多轮对话上下文管理（滑动窗口 window_k + token 预算 System15%/History60%/Response25%）|

**可调参数**（`ContextConfig`）：
- `window_k=12`：保留最近多少轮对话
- `max_context_tokens=32000`：总预算（适配不同模型窗口）
- `summarize_trigger=0.80`：history 使用率阈值触发摘要

### 10.5.11 记忆与自我改进（memory_system + self_improve + expert_guard）

| 位置 | 说明 |
|---|---|
| `05_实现原型/memory_system.py` | 三层记忆（短时/长期/摘要压缩）|
| `05_实现原型/self_improve.py` | 自我改进（反思 + 失败案例库 + 改进建议）|
| `05_实现原型/expert_guard.py` | 专业深度守门员（深度评分/套话检测/理科公式检查）|

**可扩充**：
- **记忆摘要**：`memory_system.py` 的 `compress_if_needed` 摘要策略（保留条数、摘要长度）
- **改进建议**：`memory/improvements.md` 由 `self_improve.py` 自动生成，也可手工编辑
- **深度标准**：`expert_guard.py` 的评分阈值（`_SHALLOW_PATTERNS` / `_FLUFF_PATTERNS`）

### 10.5.12 做题模块（problem_solver.py）

| 位置 | 说明 |
|---|---|
| `05_实现原型/problem_solver.py` | 题型识别（论述/计算/证明）+ 三套标准答案模板 + SymPy 验证 |

**可扩充**：
- **题型模板**：`_CALC_PROMPT` / `_PROOF_PROMPT` / `_ESSAY_PROMPT` 按学科细化
- **关键词**：`_CALC_KEYWORDS` / `_PROOF_KEYWORDS` / `_ESSAY_KEYWORDS` 扩展识别

### 10.5.13 对话交互增强（打包 + 复制/文档）

| 位置 | 说明 |
|---|---|
| `05_实现原型/prompts.py` | `build_general_chat_user`（页面设定打包 + 先理解再输出）|
| `09_GUI前端/index.html` | 复制按钮 + 多选生成文档（msg-copy/msg-select/select-bar）|

**可扩充**：
- **打包内容**：在 server.py 的 chat 路由 `ctx_parts` 加更多页面设定（如当前题目、模式）
- **文档模板**：前端 `genSelectedDoc` 的组装格式可定制

---

## 10.6 架构连通性指标（v0.19.7 ⭐ 关键技术指标）

> **目的**：确保 PAEG 的所有模块不是"空有独立文件"，而是真正被调用链连接、在实际对话中发挥作用。
> 每次重大改动后运行以下检测，连通率必须保持 **100%**。

### 10.6.1 检测命令

```bash
cd "05_实现原型"
python arch_check.py          # 输出连通性报告 + arch_report.json
```

### 10.6.2 连通性定义

每个模块的判定标准：**文件存在 + 被 server.py 或 tool_registry.py 调用**（直接或间接）。

| 模块 | 调用方式 | 状态 |
|---|---|---|
| tool_registry | server 直接调用（run_agent_loop）| ✅ |
| tool_recovery | 经 tool_registry 间接调用（with_recovery 装饰器）| ✅ |
| tool_cache | 经 tool_registry 间接调用（cached_call）| ✅ |
| context_manager | server 直接调用（ContextManager）| ✅ |
| memory_system | server 直接调用（MemorySystem + compress）| ✅ |
| expert_guard | server 直接调用（ExpertGuard 深度守门）| ✅ |
| skill_registry | 经 tool_registry 间接调用（SkillRegistry）| ✅ |
| problem_solver | server 直接调用（/api/solve）| ✅ |
| web_search_tool | server + tool_registry 调用 | ✅ |
| meta_router | server 直接调用（意图路由）| ✅ |
| self_improve | server 直接调用（对话后记录）| ✅ |
| teaching_memory | server 直接调用（system 注入）| ✅ |
| mcp_gateway | server 启动时挂载 | ✅ |
| file_generator | server 直接调用（文档生成）| ✅ |
| quotes | server + tool_registry 调用 | ✅ |
| agent_engine | server + tool_registry 调用 | ✅ |

### 10.6.3 关键调用链（必须全部存在）

```
① chat 链路:  /api/chat/stream → run_agent_loop → tool_registry → tools
② teach 链路: /api/teach → paeg.teach → subagents(5子代理)
③ 记忆压缩:   chat → MemorySystem.compress_if_needed → memory_summary.json
④ 教学记忆:   chat/teach → load_teaching_memory → memory/PAEG_PEDAGOGY.md
⑤ 自我改进:   chat 对话后 → SelfImprover.record → memory/cases.jsonl
⑥ 上下文管理: chat → ContextManager.build → token预算+滑动窗口
⑦ 深度守门:   chat 回答后 → ExpertGuard.refine → 改进
⑧ 意图路由:   teach → meta_router(is_problem_request/is_method_advice/is_meta_question)
```

### 10.6.4 失败处理

- **连通率 < 100%**：说明有模块没被调用（可能新加模块未接入）→ 立即排查
- **关键链路缺失**：对话功能会静默失效 → 用 `arch_check.py` 的报告定位
- 检测输出保存在 `05_实现原型/arch_report.json`，可纳入 CI

---

*本文档由 Sisyphus 编写，基于当前系统实际状态。修改代码前请先备份；重大改动后运行 §10.2 测试确认无回归。*
