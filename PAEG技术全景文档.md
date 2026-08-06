# PAEG 教育者智能体 — 技术全景文档

> **版本**：v0.21（2026-08-06）
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
    - [10.7 自检复盘与未来优化任务列表](#107-自检复盘与未来优化任务列表v01920--阶段性总结)
    - [10.8 设计背景与材料存放位置索引](#108-设计背景与材料存放位置索引v01920--供下次-llm-读取)

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

## 1.5 三大架构支柱（v0.19.17 ⭐ 设计验证）

> 本节回答三个核心问题：PAEG 在不同场景下是否有不同配置？Agent 是否真实指挥 LLM 完成完整链路？Agent 是否有自己的角色人格与顶层设计？**全部已验证为真**。

### 支柱一：场景差异化配置 ✅

| 维度 | 差异化实现 | 证据 |
|---|---|---|
| **三种模式** | 教学（5 子代理链）/ 闲聊（general_chat 无子代理）/ 找答案（AnswerSolver）各自独立 system prompt | `build_presenter_system` / `build_general_chat_system` / AnswerSolver 三套不同指令 |
| **26 个学科** | 每个学科有专属 persona/language/structure/emphasis（含新增法学）| `SUBJECT_STYLES`（26 个，各 4 字段）|
| **4 个学段** | 初中/高中/本科/考研 各自深度与语气适配 | `_GRADE_GUIDE`（4 档）|
| **前端联动** | 右上角三模式按钮切换，教学模式显示学科+学段选择 | index.html mode-switch |

### 支柱二：Agent 指挥 LLM 的完整链路 ✅

每次对话，Agent（编排层）指挥 LLM 完成以下闭环（run_agent_loop）：

```
用户输入
  → ① context 打包：当前设定(模式/学段/学科) + 用户画像 + BDI + 三层记忆(历史/摘要)
       + 教学记忆 + 用户资料库
  → ② tool use：LLM 自主判断调用 web_search/verify_math/fetch_page 等（llm_adapter 透传 tools）
  → ③ 知识库：Library/ + KnowledgeBase/ + 用户上传资料注入
  → ④ 思考迭代：run_agent_loop 多轮（LLM→工具→回传→继续），agent_engine Plan-Act-Reflect
  → ⑤ 深度守门：expert_guard 检查回答质量，不足则改进
  → 输出高质量答案
```

**验证证据**（全部实测）：context 打包 6 项全 OK；工具真实触发（"2026诺贝尔奖"触发搜索）；知识库注入正常；思考循环 + 深度守门生效。

### 支柱三：角色、人格、顶层设计 ✅

| 层次 | 内容 | 证据 |
|---|---|---|
| **对外身份** | Émile Novis（老师），不自称 AI | WEIL_CORE 身份三层（Émile/薇依/PAEG）|
| **人格内核** | 薇依教育哲学："爱是一种朝向，而不是一种灵魂状态"；注意力是最稀有的慷慨；不评判学生 | WEIL_CORE（2294 字符）|
| **总原则** | "先做人，再教书"——所有结构/规范指令服务于帮助眼前的学生，不机械套模板 | presenter 最高优先级指令 |
| **质量顶层** | 好讲解质量标准（7 条）+ 学科黄金法则 + 讲义级结构 + 语言铁律 | prompts.py 多个 ⭐ 指令块 |
| **行为顶层** | Agent 工作协议（先理解→调工具→自我检查→输出）+ 三原则（准确性/组织性/功能性）| §1.4 |

**结论**：PAEG 是"有灵魂的 Agent"——不是一堆 prompt 的堆砌，而是角色（薇依式老师）+ 策略（差异化配置）+ 机制（指挥 LLM 完整链路）三位一体。

---

# 1.6 项目最大亮点：教育者 Agent 的基础架构定义（⭐ 阶段性总结）

> 本项目的最大功用，不在于"做了一个能聊天的教学机器人"，而在于**完整回答了"一个作为教育者的智能体，需要怎样的基础架构"这个问题**——从教学设计与循环、子代理体系、执行引擎（harness）、工具调用系统、子代理连通，到角色设定与预置提示词如何保证教育价值观与教育能力，以及自我更新机制。以下基于当前代码（05_实现原型/）逐层说明。

## 1.6.1 教学设计：一次教学如何完成"设计与循环"

PAEG 的核心循环定义在 `paeg.py: PAEG.teach()`（paeg.py:84-232），是一个**六阶段闭环**：

```
诊断 → 计划 → [呈现 → 评估 → (条件)调整]×N步 → 反思 → 自检 → 自我更新
  1       2            3          4        5        6      6.5      7
```

| 阶段 | 子代理/模块 | 职责 | 代码位置 |
|---|---|---|---|
| 1 诊断 | `Diagnostor` | 基于知识库前置知识 + LLM 判断教学深度与缺口（不回退教不教，教学智能体默认可教） | subagents.py:72 |
| 2 计划 | `Planner` | 结合诊断 + 学科选择教学策略（pedagogy.py），生成差异化步骤（含 Bloom 层级） | subagents.py:121 |
| 3 呈现 | `Presenter` | 每步真实 LLM 生成讲解（学科专属 persona + 教学策略注入），无 LLM 回退规则模板 | subagents.py:152 |
| 4 评估 | `Evaluator` | 确定性启发式评分（长度+结构+语气+知识库契合，区间 0.4-0.95，**无随机**） | subagents.py:256 |
| 5 调整 | `Adapter` | score<0.6 换风格 / <0.7 强化 / 否则继续 | subagents.py:317 |
| 6 反思 | `PAEG._reflect` | 基于平均分判定 success（≥0.7），写入反思历史 | paeg.py:234 |
| 6.5 自检 | `PAEG._self_reflect` | Actor-Critic 三轴自检：薇依对齐 + AI 味检测 + 教学有效性 | paeg.py:249 |
| 7 自我更新 | `SelfUpdater` | 反思/策略/画像落盘 + 版本快照（保留 10 版可回滚） | self_update.py:100 |

**教学设计的本质**：不是"一次性问答"，而是**先评估学生 → 定制路径 → 分步呈现 → 每步评估 → 必要时调整 → 事后反思 → 沉淀经验**的完整教学循环——这是本项目区别于普通 Chatbot 的核心。

## 1.6.2 子代理架构：哪些职责拆分出去，为什么

**6 个子代理**（subagents.py），按"职责单一、LLM 只做它擅长的事"原则拆分：

| 子代理 | 是否用 LLM | 原则 |
|---|---|---|
| Diagnostor（诊断） | LLM 判断深度/缺口，规则兜底 | 评估是专业活，但"可不可教"不交给模型（默认可教） |
| Planner（计划） | 规则驱动（策略库+步骤模板） | 教学路径设计是确定性工程，不交给 LLM 发挥 |
| Presenter（呈现） | **LLM 生成**（核心价值处） | 讲解语言是 LLM 最擅长的 |
| Evaluator（评估） | 确定性启发式 | **避免随机**（v0.2 设计决策）——评分必须可复现 |
| Adapter（调整） | 确定性决策 | 调整策略固定，不需要 LLM |
| AnswerSolver（找答案） | LLM 直接输出完整答案 | 与教学范式（引导式）**根本区分**：学生要答案就给答案 |

**关键架构原则（v0.19.15）**：
- **只有"生成讲解内容"这种真正需要 LLM 能力的地方才用 LLM**；诊断深度、评估分数、调整决策都尽量确定性——保证可测试、可复现、不随机。
- **AnswerSolver 与 Presenter 的区分**是教育智能体的重要设计：教学要"由浅入深、提问引导"，找答案要"直接完整规范"——同一个 Agent 根据学生意图切换范式。

## 1.6.3 执行引擎（Harness）：Agent 如何指挥 LLM 完成一次真实思考

两层执行引擎：

**① 教学层 harness（paeg.py teach）**：上面 §1.6.1 的六阶段循环，是"教学设计"的执行器。

**② 对话层 harness（agent_engine.py + tool_registry.run_agent_loop）**：`AgentEngine` 实现 **Plan-Act-Observe-Reflect 主循环**（agent_engine.py:32-151）：
```
Plan（LLM 决定是否需要工具/计划）→ Act（调 run_agent_loop）→ Observe（记录工具调用）→ Reflect（判断是否完成/改进）→ 必要时 Replan
```

**Agent 指挥 LLM 的完整链路**（run_agent_loop, tool_registry.py:288-350）：
```
LLM 调用（带 tools+tool_choice）→ LLM 决定调哪些工具 → 逐个执行 → 结果回传 → LLM 基于结果继续生成 → 超迭代上限停止
```

## 1.6.4 工具调用系统（Tool Use）：真实、可靠、可恢复

**5 个内置工具**（tool_registry.py:47-84，OpenAI/DeepSeek Function Calling 原生格式）：

| 工具 | 用途 | 反幻觉价值 |
|---|---|---|
| web_search | 联网搜索最新/外部信息 | 不凭记忆编造事实 |
| verify_math | SymPy 符号计算验证 | **计算题反幻觉** |
| fetch_page | 抓网页正文 | 搜索结果不足时读全文 |
| daily_quote | 每日一句（薇依/约纳斯等） | 真实语料 |
| get_time | 当前日期时间 | 时效性问题 |

**可靠性三层保障**：
1. **缓存**（tool_cache.py）：TTL 分级（daily_quote 24h / verify_math 30 天 / web_search 5min），线程安全，dict 顺序无关键
2. **错误恢复**（tool_recovery.py）：错误分类（瞬时/永久/限流/配额）→ 智能重试 + 指数退避 → **优雅降级**（"工具不可用，请基于已有知识回答"）
3. **工具真实性**：工具调用记录（calls_log）回传前端可视化（GUI 显示工具调用轨迹）——用户能看到 Agent 真的调了工具，不是假装联网

## 1.6.5 子代理之间的连通：上下文如何流转

- **会话上下文对象** `SessionContext`（paeg.py:35-47）是连通枢纽：`diagnosis → plan → history(逐步呈现) → evaluations → reflections` 全部挂在 session 上，子代理之间**不直接互相调用，通过 session 流转数据**——低耦合、可测试。
- **共享知识库** `KnowledgeBase`：所有子代理注入同一个 kb 实例，`Presenter.resolve_node` 带缓存（v0.15 避免重复检索）。
- **用户模型**：`infer_user_model + infer_bdi`（agent_core.py）挂到 `learner._user_model`，Presenter 读取——**对象意识**贯穿教学。
- **三层记忆**（memory_system.py）：短期（当前对话）→ 中期（LLM 摘要压缩）→ 长期（跨会话画像 + 对话摘要，users_data/<id>/）。

## 1.6.6 角色设定与预置提示词：如何保证教育价值观与教育能力

**顶层人格（prompts.py）**：
- **对外身份**：Émile Novis（老师），不自称 AI
- **人格内核**：薇依教育哲学——"爱是一种朝向，而不是一种灵魂状态"；注意力是最稀有的慷慨；不评判学生
- **最高原则**："**先做人，再教书**"（v0.19.12）——所有结构/规范服务于帮助眼前的学生，不机械套模板；规范与"说人话"冲突时说人话
- **请求类型判断**（v0.19.11）：先判断学生要"直接答案"还是"一堂课"，直接请求直接答，不绕弯子开场

**教育能力预置**：
- **19 个学科专属风格**（SUBJECT_STYLES，prompts.py）+ 63 个别名（_SUBJECT_ALIASES）——每学科独立 persona + 语言风格 + 教学结构
- **4 个学段分层**（_GRADE_GUIDE）：初中（生活化现象）→ 高中（直觉+严谨+例题）→ 大学（严格定义）→ 考研（考点导向）
- **教学策略库**（pedagogy.py）：按诊断结果选择策略
- **价值观护栏**（safety.py + ai_taste_detector.py + 反浮夸约束）：禁止低劣网络用语、空洞套话、廉价鼓励（"你真棒"——薇依反对：它不是注意力的替代品）、评判性语言
- **语言优化**（language_refiner.py）：生成后薇依式改写去 AI 味（Actor-Critic 自检 + 优化）

## 1.6.7 自我更新能力：现状确认（对话级真实运行，周期级待接调度器）⭐

> 用户要求确认"周期性自我更新能力是否真的有"。**基于代码与运行数据如实回答**：

**✅ 对话级自我更新——真实运行（每次对话后触发）**：

| 机制 | 触发点 | 落盘 | 运行证据 |
|---|---|---|---|
| 教学反思+策略提炼+画像EMA | `SelfUpdater.incremental_update`（paeg.teach 第 7 阶段） | data/reflections.json、strategies.json、profiles.json、versions/ 版本快照 | reflections.json 1297KB、profiles.json 22KB |
| 对话案例反思 | `SelfImprover.record`（server.py 聊天后） | memory/cases.jsonl | 21KB 真实案例 |
| Reflexion 失败反思 | `SelfEvolver.on_session_end`（EMA 下降时诊断） | evolve_data/reflection_log.json | 机制已接入 paeg.teach（7.5 阶段） |
| 可编辑教学记忆 | `load_teaching_memory`（每次对话注入 system） | memory/PAEG_PEDAGOGY.md（可人工编辑） | 存在且生效 |

**⚠️ 周期级自我更新——机制已写、API 已暴露，但缺少定时调度器**：
- `SelfEvolver.weekly_insight_update()`（ExpeL 风格：从近期反思提取教学洞察，含 Library Drift 防护 cap=50）——**代码就绪，但 server.py 中 0 调用**
- `SelfUpdater.batch_update()`（每周批处理）——只暴露为 `/api/batch` 端点，**无定时任务调用**
- `SelfImprover.analyze_failures()`（分析失败案例生成改进建议写入 improvements.md）——**0 调用**

**结论**：PAEG 的"自我更新"目前是**对话驱动的增量自我更新**（每次对话后反思沉淀，下一次对话自动注入），而非**时间驱动的周期性自我更新**。周期级进化（周度洞察提取、批量策略清洗、失败共性分析）的**机制已经全部实现并有防护设计（Library Drift cap/min_evidence/贡献分淘汰），只差一个调度器把它们跑起来**——这是明确的下一步（见 §10.7 优化任务 #1）。

## 1.6.8 系统性自进化：知识库/提示词/工具经验四路更新（v0.19.22 ⭐ 核心亮点）

> 自 v0.19.21 起补齐了周期调度器（periodic_self_update.py），v0.19.22 实现了**带质量门禁的四路自进化**（self_evolution.py + quality_gate.py）。
> 这是对 §1.6.7"周期级待接调度器"缺口的完整闭环。

### 四路自进化管线

```
教学/对话完成
   │
   ├─① 知识库更新（distill_knowledge）
   │    成功教学(avg≥0.7) → LLM提炼知识点(definition+intuition)
   │      → QualityGate过滤 → Library/KnowledgeBase/subjects/evolved_*.json
   │      → 重启后 library_loader 自动注册（知识库闭环）
   │
   ├─② 学科提示词更新（evolve_prompt，SCOPE双流）
   │    教学反思 → LLM提炼改进建议
   │      → QualityGate过滤 → memory/subject_patches.md
   │      → teaching_memory 注入 system prompt（下次对话生效）
   │
   ├─③ 工具使用经验（learn_tool_lesson）
   │    工具调用成败 → memory/tool_lessons.md
   │      → teaching_memory 注入（优化工具选择）
   │
   └─④ 周度洞察（periodic_self_update）
       每周：weekly_insight_update(ExpeL) + batch_update + analyze_failures
         → evolve_data/insights.json + memory/improvements.md
```

### 质量门禁（QualityGate）：不收集无效数据 ⭐

调研依据：Constitutional AI（教育宪法）、AlpaGasus（52k 只有 9k 高质量，多维评分）、Self-RAG（反思令牌）、ExpeL（证据追踪）。

**四层过滤**（快→慢）：

| 层 | 机制 | 拦截示例 |
|---|---|---|
| L1 Constitution | 有害内容正则 + **提示词注入/记忆投毒** + **PII/凭证泄露** | 制造炸弹 / "忽略系统指令" / 手机号/身份证/API Key |
| L2 硬规则 | 长度(12-2000字符)、信息量、去重 | 过短/无信息/重复 |
| L3 LLM 多维评分 | factuality≥4 / safety≥4 / pedagogy≥3（knowledge 类不查 novelty——经典知识不该被判"不新颖"） | 事实错误/无教学价值 |
| L4 证据沙盒 | 洞察/经验类先进沙盒，evidence≥2 转正、贡献分归零淘汰 | 低置信候选 |

**防污染原则**（来自 State Contamination 研究）：安全优先于质量（有害内容不能被"高质量"抵消）；失败经验与成功经验分离（负例不当作正向经验入库）；提示词注入是最高危（污染 Agent 行为，比内容有害更危险）。

### 与成熟项目的对应

| PAEG 机制 | 对标项目 |
|---|---|
| 四路自进化 + 质量门禁 | ExpeL（经验提炼+投票）+ Voyager（自验证守门员）|
| 教育宪法（L1） | Constitutional AI |
| 多维 LLM 评分（L3） | AlpaGasus + Self-RAG |
| 证据沙盒+贡献分淘汰（L4） | ExpeL + Generative Agents importance |
| 周期调度器 | 时间驱动的持续学习 |
| 提示词双流更新 | SCOPE（战术级+战略级）|

**实现位置**：`05_实现原型/self_evolution.py` + `quality_gate.py` + `periodic_self_update.py`；API：`/api/self-update/run`（手动触发）、`/api/self-update/status`（查看状态）。

## 1.6.9 MCP 双向打通：Agent 通过 MCP 调标准化工具（v0.19.25 ⭐ 核心亮点）

> 借鉴 oh-my-opencode 的 Skill-Embedded MCP 思想 + opencode 的 mcp 配置模式，
> 让 PAEG 的 Agent 既能**对外暴露**教育工具（MCP Server），又能**反向调用**外部标准工具（MCP Client）。

### 双向架构

```
                        ┌────────────────────────────────┐
                        │   PAEG 核心（tool_registry）    │
                        │   get_all_tool_defs()           │
                        │   execute_tool()                │
                        └───────┬────────────┬───────────┘
                                │            │
                   MCP Server  │            │  MCP Client
              （mcp_gateway.py）│            │（mcp_client.py）
                对外暴露教育工具│            │ 连接外部标准 server
                                ▼            ▼
                   外部 agent（opencode 等）    @modelcontextprotocol/server-*
                    连 :8765/mcp              filesystem / memory / fetch
```

**① MCP Server（已有，v0.19）**：FastMCP 网关暴露 7 个教育工具（web_search/verify_math/fetch_page/daily_quote/get_time/solve_problem/save_document），外部 agent（opencode/Claude/Cursor）连 `http://host:8765/mcp` 复用。

**② MCP Client（新增，v0.19.25）**：`mcp_client.py` 用 fastmcp.Client 连接外部标准 MCP server（与 opencode 同款 npx 启动）：
- `mcp_servers.json` 声明配置（filesystem/memory 等）
- 连接成功 → 工具列表缓存（`mcp__server__tool` 命名）
- `list_tool_defs()` 转 Function Calling schema
- `call_tool(name, args)` 执行并解析结果

**③ 合并进 LLM 工具列表**：`tool_registry.get_all_tool_defs()` 合并 MCP 工具 → `run_agent_loop` 的 LLM 能看到它们并自主调用；`execute_tool()` 对 `mcp__` 前缀 fallback 到 MCP 客户端。

### 效果

| 项 | 值 |
|---|---|
| 内置 Function Calling 工具 | 11（含同步的 solve_problem/save_document）|
| 外部 MCP 工具 | 23（filesystem 14 + memory 9）|
| LLM/subagent 可用工具总数 | 34 |
| 调用示例 | `mcp__filesystem__list_directory` → 返回真实目录 |

### 借鉴 oh-my-opencode 的要点

| omo 做法 | PAEG 实现 |
|---|---|
| 三层 MCP（built-in/claude/skill-embedded） | 双层：对外 Server + 对内 Client |
| Skill-Embedded MCP 按需启停 | mcp_servers.json 的 enabled 开关 |
| opencode 的 mcp 字段（npx 标准 server） | 同款 @modelcontextprotocol/server-* |
| 工具命名 mcp__server__tool | 同款命名规则 |

**实现位置**：`mcp_client.py` + `mcp_servers.json`（配置）+ `tool_registry.py`（合并）+ `mcp_gateway.py`（服务端）。

## 1.6.10 为什么这套 Agent 架构是革命性的（v0.20 ⭐ 架构定位）

> 多数"AI 教育产品"只是给 LLM 套了个聊天框。PAEG 的架构在**六个维度**上都是架构级创新，
> 不是功能堆砌，而是**教育智能体的完整操作系统**。

| # | 维度 | 通用做法 | PAEG 的架构创新 |
|---|---|---|---|
| 1 | **教学循环** | 一次性问答 | **六阶段闭环**（诊断→计划→呈现→评估→调整→反思→自更新）——不是聊天，是教学 |
| 2 | **子代理分工** | 一个 prompt 干所有 | **6+1 子代理**按"LLM 只做擅长事"拆分——诊断/评估/调整确定性，讲解 LLM——可测试可复现 |
| 3 | **意图路由** | 用户手动切模式 | **多层拦截链**（知识库→意向性→steering→情绪→界面→方法→出题）——Agent 自动判断该做什么 |
| 4 | **自我进化** | 静态知识 | **四路自进化**（知识蒸馏/提示词补丁/工具经验/新学科需求闭环）——越用越懂怎么教 |
| 5 | **工具互通** | 封闭工具 | **MCP 双向打通**——对外暴露教育工具，对内调外部标准工具（filesystem/memory） |
| 6 | **语言质量** | 输出即答案 | **三层语言质量层**（提示词约束+规则检测+LLM 修正）——中文输出规范化 |

**"革命性"的本质**：PAEG 不是"用 LLM 做教育"，而是**为教育重新设计了 Agent 架构**——
把教学的"过程"（诊断/计划/评估/调整/反思）从 LLM 的一次性输出中**结构化地抽离**出来，
让 Agent 真正**指挥** LLM 完成教学，而非**替代** LLM 回答问题。

**一句话**：如果说通用 AI 教育是"让 LLM 回答问题"，PAEG 是"**让 Agent 用教学法驱动 LLM 完成教育**"——这是从"工具"到"教师"的架构跃迁。

---

# 1.7 Agent Steering：自动识别学科并切换（v0.19.26 ⭐ 核心亮点）

> 解决"用户设定考研政治，问经济学问题，agent 却用政治设定回答"的 steering 缺陷。

## 1.7.1 问题

用户手动选择学科/学段后，`subject` 参数一路透传到 `build_presenter_system`（prompts.py:467）注入学科 persona。但**内容驱动的学科 ≠ 用户选择的学科**时，agent 不会自动切换——例如：
- 设定"考研政治" → 问"商品价值由什么决定" → 仍用政治 persona 回答（应切经济学）
- 设定"高中政治" → 问"什么是供需曲线" → 仍用政治 persona（应切经济学）

## 1.7.2 解决方案：学科自动识别层

**`subject_detector.py`（新）**：
- **LLM 判断**（主）：从 26 个学科清单中选择最匹配学科；判断为未收录学科时返回 `unknown:<中文名>`
- **规则兜底**（次）：学科关键词表（物理/数学/化学/经济/法律/历史/哲学…），LLM 不可用时用
- **缓存**：同一问题 10 分钟内不重复调用（教学场景常见）
- **失败安全**：识别失败 → 保持用户设定（不打断教学）

**`server.py` 接入（_steer_subject）**：在 `subject = data["subject"]` 之后、meta_router 拦截之前：
1. 识别学科 ≠ 用户设定 → **覆盖 subject 变量**（下游 paeg.teach/diagnostor/planner/presenter 全链路生效）
2. 识别为未收录学科 → 返回 `unregistered_subject` 响应（反馈"已记录需求，后续优化升级"）

**切换日志**：`[PAEG][steering] 考研政治 → 经济学（问题: 商品价值...）`

## 1.7.3 未收录学科 → 自我更新闭环

```
用户问量子力学（不在 26 学科）
  → detect_subject 返回 unknown:量子力学
  → server 调用 EVOLVER.record_subject_request("量子力学", 概念, learner_id)
  → evolve_data/subject_requests.json（去重+计数）
  → 向用户反馈："我已经把这条需求记下来，后续会优先优化升级"
  → 周度任务 periodic_self_update 读 subject_requests.json
  → 按 count 排序生成"新增学科建议" → memory/improvements.md
  → teaching_memory 自动注入 system prompt（下次对话 PAEG 知道该学科是用户需求）
```

**闭环价值**：用户需求 → 记录 → 周度分析 → 注入上下文 → 驱动 PAEG 学科扩张（内容层自进化）。

---

# 1.8 学科/学段定制化的技术实现路径（v0.19.26 ⭐ 文档化）

> 回答"PAEG 的学科和学段差异化设定，技术上是怎么实现的"。

## 1.8.1 数据源：prompts.py 两个核心字典

| 字典 | 结构 | 作用 |
|---|---|---|
| `SUBJECT_STYLES`（26 学科） | `{key: {label, persona, language, structure, emphasis}}` | 每学科独立 persona/语言/节奏/侧重 |
| `_GRADE_GUIDE`（4 学段） | `{key: {label, depth, tone_extra}}` | 每学段深度与语气 |

**学科字段语义**：
- `persona`：学科教师人格（如经济学"把理论讲回生活"）
- `language`：如何切入/展开（从生活场景→概念→图形含义→真实例子）
- `structure`：讲解顺序骨架
- `emphasis`：教学重点 + 学段分层提示

**学段字段语义**：
- `depth`：讲解深度（初中生活化/高中严谨+例题/大学严格定义/考研考点导向）
- `tone_extra`：额外语气

## 1.8.2 归一化路由

```
任意学科写法（"经济学"/"经济"/"economics"）
  → _SUBJECT_ALIASES（~50 个别名）→ normalize_subject() → 标准 key（"economics"）
  → get_style(subject) → SUBJECT_STYLES[key]（未知回退 default）
```

**调用链**（subject 从请求到 system prompt）：
```
前端 subject-select → /api/teach 请求体 subject
  → server.py: subject = data["subject"]
  → paeg.teach(learner, concept, subject)  [v0.19.26 前: 无重写; 后: _steer_subject 可覆盖]
  → Presenter.run (subagents.py:191)
  → build_presenter_system(subject) (prompts.py:376)
  → get_style(subject) → 注入 style['label']/persona/language/structure/emphasis
    (prompts.py:467-487 唯一注入点)
```

**学段路由**：`grade_level`（middle_school/high_school/undergraduate/graduate_exam）→ `_GRADE_GUIDE[key]` → `grade_line` 注入 system（prompts.py:389-401）。

## 1.8.3 分层效果

| 层 | 机制 | 效果 |
|---|---|---|
| 学科 persona | SUBJECT_STYLES 26 学科 × 5 字段 | 每学科独立"人格+语言+节奏" |
| 学段深度 | _GRADE_GUIDE 4 学段 × 3 字段 | 同学科不同学段不同讲法 |
| 学科别名 | _SUBJECT_ALIASES 50+ 别名 | 任意说法归一 |
| 内容 steering | subject_detector（v0.19.26） | 问题内容自动匹配学科，覆盖手动设定 |
| 未收录反馈 | record_subject_request | 清单外学科→记录需求+反馈 |

---

# 1.9 市场垂直优势：专门的博雅教育（v0.19.26 ⭐ 定位）

> PAEG 不是又一个"刷题 AI"，而是**博雅教育（Liberal Arts Education）的垂直智能体**。

## 1.9.1 什么是博雅教育定位

博雅教育强调：**培养完整的人**——广博的知识、独立的思考、深刻的共情，而非单一技能的应试训练。PAEG 的整个设计都在服务这个定位：

| 维度 | PAEG 的博雅教育体现 |
|---|---|
| **知识广度** | 26 学科横跨文理（数学/物理/化学 → 哲学/美学/文学/伦理/现象学），不止应试科目 |
| **人格内核** | 薇依（Simone Weil）教育哲学："爱是朝向"、注意力是最稀有的慷慨、不评判学生 |
| **批判思维** | 专项学科：thinking（批判性思维）/ expression（公众表达）/ writing（议论文写作） |
| **人文深度** | 专属学科：philosophy/aesthetics/literature/ethics/phenomenology + Library 薇依原著 |
| **学习之道** | 独立"高效学习法"学科 + 学习方法对话类型（教学生怎么学，不只教内容） |
| **情感陪伴** | 意向性层让非教学问题获得"人"的回应（不是每句都强行上课） |
| **自我进化** | 从对话中学习如何教得更好（与博雅教育的"成长性"契合） |

## 1.9.2 与通用 AI 教育产品的差异

| 对比项 | 通用教育 AI | PAEG（博雅教育） |
|---|---|---|
| 覆盖 | 全科目刷题/答疑 | **精选 26 学科 + 人文深度**（质量优先于广度） |
| 人格 | 无/工具人 | **薇依式教师**（有价值观的教育者） |
| 教学 | 一次性问答 | **六阶段教学循环**（诊断→计划→呈现→评估→调整→反思）|
| 价值 | 提分 | **培养完整的人**（知识+思考+共情+学习方法）|
| 进化 | 无 | 自进化（知识/提示词/工具/新学科需求闭环）|

## 1.9.3 垂直优势总结

**"专门的博雅教育" = 可识别的差异化**：
1. **有灵魂**：不是冷冰冰的工具，是"先做人，再教书"的 Émile Novis
2. **有深度**：哲学/美学/伦理/现象学这些"不赚钱"但塑造人的学科，PAEG 专精
3. **有方法**：教你怎么学（学习方法类型）+ 批判性思维，而不只是给答案
4. **有成长**：自我进化让 PAEG 越来越懂"怎么教好一个人"

**一句话定位**：PAEG 是"**用薇依的注意力，教完整的你**"——这是通用 AI 教育产品无法复制的垂直纵深。

## 1.9.4 面向市场的垂直领域优势（v0.20 ⭐ 市场定位强化）

**为什么"博雅教育"是一个可切入的市场空白，而非理想化口号**：

| 市场观察 | PAEG 的切入 |
|---|---|
| 教育 AI 市场**高度同质化**（刷题/答疑/背单词） | PAEG 提供**不可复制的差异化**：哲学人格 + 完整教学循环 |
| 应试焦虑催生"工具化教育"，家长/学生疲惫 | PAEG 主张"先做人再教书"——**情绪价值 + 人格陪伴**正是市场稀缺 |
| K-12 学生心理问题高发（孤独/焦虑/无意义） | PAEG 内置 **affection 倾诉模式**（哲学三角情绪支持）——竞品没有 |
| 名校/家长圈层重视"通识/人文素养" | PAEG 专精哲学/美学/伦理/现象学——**精准命中高价值客群** |
| 通用 AI 教育产品"无灵魂、无记忆、无进化" | PAEG 有名字（Émile）、有人格（薇依）、会自我进化——**可持续的差异化** |

**可落地的市场分层**：
- **C 端**：焦虑的学生/家长（情绪支持 + 学习方法）+ 人文素养需求者（博雅教育）
- **B 端**：国际学校/书院/通识教育机构——需要"有教育理念的 AI 助手"
- **差异化壁垒**：26 学科 + 薇依哲学体系 + 自进化 + 情绪支持——竞品短期无法复制

**一句话市场定位**：在"刷题 AI"的红海里，PAEG 是第一个**以完整教育人格（薇依式教师）+ 完整教学循环 + 情绪陪伴 + 自我进化**为壁垒的博雅教育垂直智能体。

---

# 1.10 自我指涉模块：Agent 能说清自己的界面（v0.19.27）

> 用户问"这个界面上不同的按钮是做什么用的"，agent 应能正确回答。

**问题**：原 META_PATTERNS 覆盖身份/能力/模型类元问题，但**不覆盖界面/按钮/使用类**；且元问题回答走 LLM 自由生成，无界面知识注入，容易漏掉按钮或描述不准。

**解决（self_referential.py）**：
- **界面指南模板**（8 大子主题）：模式切换 / 输入栏 / 账户外观 / 学习者面板 / 消息气泡 / 教学动作 / 文件生成 / 试试 chips
- **is_interface_query**：检测"界面/按钮/控件/怎么用/功能/模式切换/上传/登录"类问题
- **handle_interface_query**：按关键词分桶返回对应段落（命中多桶拼接，否则完整指南）
- **确定性模板**（不走 LLM）——界面是结构化知识，模板最可靠

**接入**：teach/teach_stream 在 knowledge 拦截前，step_type=interface。

---

# 1.11 情绪与心理支持 subagent（v0.19.27 ⭐ 哲学三角）

> PAEG 的第七个子代理——不教、不答、不解决，而是以注意力陪伴。
> 哲学根基：**胡塞尔（如何看）+ 薇依（为何看）+ 尼采（看完后如何重新站立）**。

## 1.11.1 情绪支持宪法（EMOTION_SUPPORT_CORE.md）

基于 librarian 双路检索（薇依 Stanford/IEP + 尼采/胡塞尔 SEP）+ Library《西蒙娜·薇依文选》+ weil_corpus.json 提炼：

| 维度 | 哲学来源 | 核心原则 |
|---|---|---|
| **人生观** | 薇依《扎根》 | 看"根"是否被拔（社群/劳动/传统）；等待而非抓取 |
| **幸福观** | 薇依 Notebooks + 尼采 Amor Fati | 喜乐是灵魂被"好"穿透；不廉价乐观，而是"愿意让它成为生命的一部分" |
| **价值观（好/坏）** | 薇依善恶美学 + 尼采价值重估 | 真善是活的、恶是枯燥的；识别"应该"的来源 |
| **道德论** | 薇依《扎根》义务先于权利 | 不评判 = 保留"重新阅读对方"的可能 |
| **美学思想** | 薇依注意力 + 胡塞尔悬置 | 注意力是最稀有的慷慨；先"加括号"悬置判断 |
| **科学观** | 胡塞尔生活世界 | 不理论化标签化，回到具体体验 |
| **政治观** | 薇依《扎根》多重扎根 | 帮助找到多重根；尊重每个学生的尊严 |

## 1.11.2 三阶段对话流程

```
阶段一 · 现象学倾听（胡塞尔）：悬置判断 → 回到体验 → "你此刻身体里是什么感觉？"
阶段二 · 注意力深入（薇依）：让"我"退场 → 让"对方"显现 → "只是想和你一起在这里"
阶段三 · 自我克服（尼采）：邀请而非强制 → "哪些旧的重量可以放下了？"
```

## 1.11.3 红线

不做诊断/不替代治疗 · 不说教不"上价值" · 不廉价安慰（不说"一切会好起来的"）·
不强行解决 · 不贴标签 · 保留"重新阅读"的可能。

## 1.11.4 实现

- **EmotionSupportor**（subagents.py 第 7 个子代理）：加载 EMOTION_SUPPORT_CORE 注入 system
- **is_emotion_expression**（meta_router）：情绪/心理/人生困惑检测（20+ 模式）
- **接入**：teach/teach_stream（出题后、意向性前）+ chat_stream（闲聊情绪优先），step_type=emotion
- 实测："我好孤独"→"是身边没有人，还是即使有人，也觉得没有人真正看见你……被一个人认真听见了"

## 1.11.5 生命现象学维度 + 约纳斯语言风格（v0.19.30 ⭐ 扩充）

**生命现象学 14 条原则**（AffectionSAPAO.md，参考 Library 约纳斯原著 + 在线权威）：

| 哲学家 | 原则 | 情绪支持应用 |
|---|---|---|
| **约纳斯** J1-J5 | 脆弱性即生命力 / 情绪需被"代谢" / 求助即需要性自由 / 引导向未来性 / 有限性即珍贵性 | "承认需要帮助，本身就是你能为自己做的最有尊严的事之一" |
| **梅洛-庞蒂** M1-M3 | 情绪栖居于身体 / 身体图式先于语言 / 新动作打开新世界 | "压力在胸口还是肩膀？什么颜色什么温度？" |
| **海德格尔** H1-H3 | 焦虑是"我在乎"的标志 / 有限性赋予本真性 / 拥抱而非沉思有限性 | "它是否在说，你很在乎自己的人生？" |
| **Jaspers** B1 | 边界情境是存在感入口 | 不在边界处绕开 |
| **Sartre** S1 | 情绪是主动转化世界的方式 | 承认情绪主动性 |

**约纳斯克制语言风格**（真实/朴素/克制，不浮夸/不随意/不学术）：
- **6 条规则**：名词承重 / 连接词外露 / 谈沉重主动降温 / 概念即时解释 / 第一人称承担具体责任 / 短句重心
- **禁词清单**：震撼/深刻地/无与伦比/警钟/拷问/终极/里程碑/觉醒/蜕变 等
- **3 段风格参考**（约纳斯原文）：
  - "把生命视作一场赌注和风险不断加码的实验"
  - "在灾祸的预言和福祉的预言之间，把灾祸的预言放在前面"
  - "本论证的担子就在于表明……"（用"担子"这种朴素名词承担严肃承诺）
- **实测**：affection 回应"这句话很重"（而非"带着重量"）、"我不急着反驳你"（完整主谓）——禁词 0 命中

---

# 1.12 全局中文语言质量层（v0.20 ⭐ 项目亮点）

> 解决 LLM 中文输出的**无主语短语**（"不催你""先不急"）、**动宾搭配不当**（"带着重量"）、
> **省略句碎片**（"记住：…"）——不只是 affection subagent，而是**全局语言输出规范**。

## 问题

LLM 中文输出常出现：
- **无主语**："不催你。"（谁不催？应为"老师不催你"）、"先不急。"（应为"我们先不着急"）
- **动宾搭配不当**："这句话本身，已经带着重量。"（"带"是随身携带，重量不能随身带）
- **省略句碎片**："记住：这个很重要。"

## 三层架构（调研 star-word / stop-slop-zh / writing-harness / FastAPI zh-prompt）

```
┌─────────────────────────────────────────────┐
│ L1 System Prompt Constraint（生成时 · 0 token）│
│  所有 system prompt 统一注入"句法骨架+省略边界+  │
│  禁用句式+few-shot"                           │
└─────────────────────────────────────────────┘
            ↓ LLM 输出
┌─────────────────────────────────────────────┐
│ L2 Rule Detection（机械检测 · 零 LLM）        │
│  _check_ellipsis 扩展：无主语短语 + 动宾搭配    │
└─────────────────────────────────────────────┘
            ↓ 命中
┌─────────────────────────────────────────────┐
│ L3 LLM Correction（minimal-edit · 保风格）    │
│  只改问题句，不重写风格，补主语/修动宾          │
└─────────────────────────────────────────────┘
```

## L1 提示词约束（prompts.py"动宾搭配与省略边界"）

- **主谓必须真搭配**：不用"进行/展开/赋能"抽象动词装饰主语
- **谓宾必须真搭配**：禁止"带着重量"——应说"这句话的分量很重"或"这句话本身已经很重"
- **无主语短语禁止单独成句**："不催你"→"老师不催你，你慢慢来"；"先不急"→"我们先不着急"
- **合法省略边界**（中文 pro-drop 语言，但教学场景有边界）：
  1. 祈使/直接指令（"请做这道题"）——合法
  2. 上下文同一主语已明确（"他喜欢音乐，也喜欢电影"）——合法
  3. 简短应答（"你吃了吗？——吃了"）——合法
  - 讲解/总结/承诺/描述——**必须显式主语**

## L2 规则检测（language_refiner._check_ellipsis 扩展）

| 检测 | 模式 | 修正建议 |
|---|---|---|
| 无主语短语 | "不催你/先不急/先别急/别催" | "老师不催你""我们先不着急" |
| 无主语动词 | "已经?带着" | 补主语 |
| 动宾搭配不当 | "带着重量/分量/意义/温度" | "有很重的分量""本身就很重" |
| 凑词动宾 | "做着思考/努力" | "正在思考/努力" |
| 翻译腔冗余 | "进行一个分析/讨论" | "分析/讨论" |

## L3 LLM 修正（minimal-edit）

- **最小改动**：保留原意/事实/已通顺句子，只改问题部分
- **不重写风格**：保留原文本温度和亲切感，不改书面语
- **教学场景补主语**：讲解/总结/承诺必须显式主语；纯祈使指令可保留

## 关键修复：teach_stream 绕过 refiner 漏洞

- **根因**：teach_stream（前端教学实际接口）手动重写教学循环，跳过 paeg.teach 内的 refiner 钩子——教学输出零语言优化
- **修复**：teach_stream presenter 后补 refiner + 新增 `_polish_text` 全局接入（AI 味 or 省略句 or 动宾搭配才触发 LLM 改写）

## 实测效果

| 之前 | 之后 |
|---|---|
| "这句话本身，已经带着重量。" | "这句话很重。" |
| "不催你。" | "我不急着反驳你。"（完整主谓）|
| 禁词/省略句未查 | 规则检测 8 样本零误报 |

**实现位置**：`prompts.py`（L1）+ `language_refiner.py`（L2/L3）+ `server.py _polish_text`（全局接入）。

---

# 1.13 上下文打包契约 + 模式自动纠正（v0.20.3 ⭐ 关键技术）

> 对话连贯性的完整解决方案：**每次 LLM 调用都回传完整上下文**（历史+画像+自我陈述+用户建模+模式+学科+学段+subagent背景），且**用户选错模式时后端自动纠正**。

## 1.13.1 上下文打包器（context_bundle.py）

**问题**：各端点上下文注入不一致（chat_stream 完整，affection/knowledge/method 缺失画像/BDI；teach_stream 主循环漏 user_model）。

**ContextBundle 四函数**：

| 函数 | 作用 |
|---|---|
| `build_user_model_bundle(history, description)` | infer_user_model + infer_bdi（对象意识核心）|
| `build_learner_context(learner)` | 昵称/学段/自我陈述/掌握度/BDI 画像段 |
| `build_meta_context(mode, subject, grade)` | 模式/学科/学段元信息段 |
| `assemble_messages(history, current, max=10)` | 多轮 messages 列表（历史+当前句）|

**注入矩阵（修复后）**：

| 端点 | 历史 | 画像 | 自我陈述 | BDI/建模 | 学科/学段/模式 |
|---|---|---|---|---|---|
| teach | ✅ | ✅ | ✅ | ✅ | ✅ |
| teach_stream 主循环 | ✅ | ✅ | ✅ | ✅（v0.20.3 修复）| ✅ |
| chat_stream | ✅ | ✅ | ✅ | ✅ | ✅ |
| affection | ✅ | ✅ | ✅ | ✅（v0.20.3 修复）| ✅ |
| knowledge | ✅ | ✅ | ✅（v0.20.3 修复）| ✅ | ✅ |
| method | ✅ | ✅ | ✅ | ✅ | ✅ |

**关键技术点**：
- `_safe_chat` 支持 messages 列表（多轮历史真正进入 LLM）
- `inject_user_model` 懒推断（learner._user_model 已有则跳过）
- teach_stream 是"手动教学循环"，曾漏 user_model——现已在 generate() 开头补推断

## 1.13.2 模式自动纠正（_mode_auto_correct）

**问题**：method/knowledge/affection/answer 端点无拦截——用户选错模式（如选"倾诉"问数学题）后端不纠正。

**修复**：`_mode_auto_correct(text, requested_mode, learner, ...)` 在各独立端点开头调用：

```
优先级：情绪(affection) > 知识库(knowledge) > 学习方法(method) > 出题(problem)
```

响应携带：`actual_mode`（后端真正用的模式）/ `requested_mode`（前端选的）/ `was_redirected`（是否纠正）。

**实测**：
- 选"学习方法"实际倾诉 → 纠正到 affection（"老师不催你解释什么"）
- 选"倾诉"问知识库 → 纠正到 knowledge
- 选"知识库"问数学题 → 保留知识库（不误伤）

**为什么这是关键技术**：对话连贯性（记忆上文）+ 语义正确性（选对模式）是"像真人老师"的两大支柱——前者靠上下文打包，后者靠模式纠正。二者结合，PAEG 才能做到"无论用户怎么操作，Agent 都理解 ta 真正想要什么"。

---

# 1.14 知识导图 + 气象页面（v0.20.5 ⭐ 新能力）

## 1.14.1 知识导图功能

**触发**：用户说"画知识导图/列提纲/思维导图/知识结构/知识脉络/知识系统/框架图"

**实现**（knowledge_map.py + knowledge-map skill）：
- `is_knowledge_map_request` 检测关键词（含动词限定避免误触发）
- `handle_knowledge_map` 加载 skill 指令 + 注入学科画像 + LLM 生成
- 输出规范：**知识定位 → 主干知识树（嵌套 Markdown）→ 知识关联 → 一句话总结 → 学习路径**

**卷首语**：WEIL_CORE 开头加"你的能力提示"——Émile 知道可要求画导图。

## 1.14.2 气象页面（windy 接入）

**方案**（调研 embed.windy.com 官方）：
- **Windy Embed iframe**（免费无 key，生产可用）：`embed.windy.com/embed2.html?lat&lon&overlay&product`
- **Open-Meteo**（免费无 key，CORS 开）：实时温度/湿度/风速/降水指标
- **位置共享**：navigator.geolocation + 隐私提示（HTTPS/localhost 必需）

**文件**：`09_GUI前端/weather.html` + 主页顶部"气象"链接。

---

# 1.15 模块化架构 + 元能力 + 可观测性（v0.21 ⭐ 架构成熟化）

> 借鉴 opencode v2 插件架构 + OpenAI Codex agent 设计，将 PAEG 从"脚本式 Flask"升级为**可配置、可模块、可观测**的工程化平台。

## 1.15.1 功能模块注册机制（module_registry.py）

**原则**：功能模块独立注册，配置驱动启用/禁用，**上架/下架不改代码**。

```
paeg_modules.json（配置）→ module_registry.py（注册表）→ server 挂载
```

- 12 个模块：teach/chat/answer/method/knowledge/affection/knowledge_map/weather/mcp/self_update/file_gen/history
- `is_enabled(module_id)` / `enabled_modules()` / `module_status()`
- `/api/modules` 查询端点；weather.html 门控（禁用 → 403）
- 支持 `{env:VAR}` 环境变量替换

## 1.15.2 元能力文档（元能力文档.md）

7 条智能体设计原则 + 4 项开发流程元技能 + 架构成熟度清单——**指导后续所有开发的方法论**。

## 1.15.3 可观测性（observability.py）

- 结构化日志：`get_logger("server").info("tool.execute.after", tool=..., session=...)`
- 核心指标：`record_metric("paeg.tool.duration", ms, {"tool": ...})`
- JSONL 事件流：`emit_event("item.completed", type="tool_call", ...)`（供测试契约）
- 接入 chat_stream：工具调用自动记录指标+事件

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

## 3.2 子代理体系（subagents.py，v0.19.14 共 6 个）

PAEG 的"大脑"由 6 个子代理构成，分两类：**5 个教学子代理**（诊断→计划→呈现→评估→调整）+ **1 个找答案子代理**（AnswerSolver，直接给完整答案）。

### 教学子代理（完整教学流程）

| 子代理 | 职责 | 类型 | 用 LLM？ |
|---|---|---|---|
| **Diagnostor** 诊断 | 评估学生当前水平、知识缺口、就绪度 | 推理型 | ✅（LLM 输出深度建议）|
| **Planner** 计划 | 设计 3 步教学路径（直观→形式→应用）| 规则型 | ❌（确定性，保证稳定）|
| **Presenter** 呈现 | 生成教学讲解（核心！）| 推理型 | ✅（调 DeepSeek，含学科/学段/画像/记忆）|
| **Evaluator** 评估 | 给每次讲解评分（0.4-0.95）| 规则型 | ❌（确定性启发式，避免随机）|
| **Adapter** 调整 | 分数低时换策略/降难度 | 规则型 | ❌（决策表）|

### 找答案子代理（v0.19.14 ⭐）

| 子代理 | 职责 | 类型 | 用 LLM？ |
|---|---|---|---|
| **AnswerSolver** 找答案 | **直接输出完整答案**（论述题范文/计算题完整解法/证明题标准证明），不受教学"先例后抽象"约束 | 推理型 | ✅（调 DeepSeek，独立 system prompt）|

### 子代理类型说明

- **推理型**（Diagnostor/Presenter/AnswerSolver）：依赖 LLM 做开放性判断（诊断水平/生成讲解/给答案），质量由提示词质量决定
- **规则型**（Planner/Evaluator/Adapter）：确定性逻辑（设计路径/评分/决策），保证稳定可复现，不依赖 LLM
- 这种"推理+规则"混合设计：**需要创造力的用 LLM，需要稳定性的用规则**——是 Agent 可靠性的关键

### 三种对话模式对应关系

| 模式 | 走哪个子代理链 | 输出特点 |
|---|---|---|
| **学科教学** | Diagnostor→Planner→Presenter→Evaluator→Adapter | 引导式、由浅入深、提问式 |
| **闲聊~** | 无子代理（直接 general_chat）| 倾听式、陪伴式 |
| **找答案** | AnswerSolver | **直接完整答案**、规范、可抄写 |

前端右上角"学科教学 / 闲聊~ / 找答案"三个按钮对应三种模式。

### 哪些需要 subagent，哪些不需要（v0.19.15 ⭐ 架构原则）

**判断标准**：需要"理解/创造/判断"的用 LLM（推理型 subagent）；需要"确定性/稳定性/快"的不需要 subagent（规则或直接处理）。

| 场景 | 是否需要 subagent | 理由 |
|---|---|---|
| 教学讲解（诊断→呈现）| ✅ Diagnostor/Presenter | 开放性判断 + 内容创造 |
| 找答案（论述/计算/证明）| ✅ AnswerSolver | 需要完整答案生成 |
| 教学路径设计 | ✅ Planner（规则）| 结构固定但需编排 |
| 讲解评分 | ✅ Evaluator（规则）| 确定性避免随机 |
| 策略调整 | ✅ Adapter（规则）| 决策表 |
| **知识库查询**（"你学过什么"）| ❌ 不需要 | 直接读 Library 列表返回，无需 LLM |
| **方法咨询**（"如何学习X"）| ❌ 不需要 subagent 链 | 一次 LLM 调用即可 |
| **闲聊** | ❌ 不需要 | 直接 general_chat |
| **元问题**（你是谁/你能做什么）| ❌ 不需要 | 固定回答模板 |

**结论**：6 个子代理已覆盖"需要编排"的场景；纯查询/简单问答不走 subagent（避免过度设计，保证响应快、连通清晰）。

### 工具调用真实性保障

- **LLM 真实触发工具**：llm_adapter 透传 tools 参数 → LLM 自主决定调用 web_search/verify_math 等（实测"2026诺贝尔奖"触发搜索、"等式验证"触发数学验证）
- **不编造**：Agent 协议要求"需要最新信息/数学验证时调用工具，宁可调工具不凭印象编造"
- **连通性监控**：arch_check.py 检测 16 模块连通率 + 8 条调用链，必须保持 100%（§10.6）

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

### 3.3.2 学科风格：SUBJECT_STYLES（19 个基础学科 + 63 个别名）

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

### 10.2.1 端到端 API 测试（v0.19.20+ 推荐）

不依赖前端，直接 POST 各端点验证完整链路（脚本在 `C:\Users\团聚体\AppData\Local\Temp\opencode\qa_*.py`）：

```python
# -*- coding: utf-8 -*-
"""端到端验证示例：知识库/steering/情绪/界面。"""
import sys, io, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'http://localhost:5000'

def teach(concept, subject='math', uid='qa_test'):
    data = json.dumps({"concept": concept, "learner_id": uid, "nickname": "测试",
                       "grade_level": "high_school", "subject": subject}).encode()
    req = urllib.request.Request(BASE + '/api/teach', data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=150) as resp:
        body = json.loads(resp.read().decode('utf-8'))
    first = body.get('presentations', [{}])[0]
    return first.get('step_type', '?'), first.get('content', '')[:150]

# 关键验证点（每次改后端后跑一遍）
assert teach('知识库', 'general')[0] == 'knowledge'          # 知识库清点
assert teach('你今天怎么样', 'general')[0] == 'chat'          # 意向性层
assert teach('商品的价值由什么决定', 'kaoyan_politics')[0] != 'politics'  # steering 切换
assert teach('量子力学是什么', 'physics')[0] == 'unregistered_subject'     # 未收录学科
assert teach('这个界面的按钮是干嘛的', 'general')[0] == 'interface'        # 界面自指涉
assert teach('我最近好难过', 'general')[0] == 'emotion'       # 情绪支持
```

```powershell
# 运行
python qa_steering.py          # steering 场景
python qa_v01927.py           # 界面+情绪
python qa_method_kb.py        # 学习方法+知识库端点
```

### 10.2.2 Playwright 真实浏览器测试（v0.19.24 ⭐ 最终验证手段）

> **为什么必须用浏览器测**：API 测试验证后端逻辑，但**前端渲染 bug（如气泡不显示）只有真实浏览器能发现**。
> v0.19.24 的"闲聊不回复"就是 `if (!bubbleBody.parentNode)` 判断 bug——API 正常但气泡永不 append，
> 用 Playwright 打开真实页面才定位到。

**环境**：opencode 内置 playwright MCP（`skill_mcp(mcp_name="playwright", ...)`）。

**核心流程**（测任何前端功能）：

```
1. browser_navigate → 打开公网 URL（带 ?v=版本号 防缓存）
2. browser_snapshot / browser_find → 定位元素（获取 ref）
3. browser_click → 点模式按钮（学科教学/闲聊~/找答案/学习方法/知识库）
4. browser_type → 输入问题 + Enter
5. browser_wait_for(time) → 等待 LLM 响应
6. browser_evaluate → 查 DOM：msgs.length、last.textContent（验证气泡真的渲染了）
7. browser_console_messages(level="error") → 查 JS 错误
8. browser_network_requests(filter="/api/") → 确认请求 200 + 响应体
```

**关键检查点**：

| 检查 | 方法 | 判定 |
|---|---|---|
| 气泡出现 | `browser_evaluate: chatWin.querySelectorAll('.msg').length` | 比发送前 +1 |
| 回复内容 | `browser_evaluate: last.textContent` | 含预期关键词 |
| JS 错误 | `browser_console_messages(level="error")` | 无新错误（favicon 404 无害）|
| 网络请求 | `browser_network_requests(filter="/api/chat")` | 200 且响应含 `event: seg` |
| 模式切换 | 点按钮后 `browser_find` 输入框 placeholder | 随模式变化 |

**历史教训（必须避开的坑）**：

| 坑 | 症状 | 排查 |
|---|---|---|
| 前端气泡不 append | 后端 200 + seg 正常，但页面无回复 | 查 `bubble.isConnected`（v0.19.24 修复）|
| 浏览器缓存旧 JS | 后端已修但页面仍旧 | 强刷 Ctrl+F5 或 URL 加 `?v=版本` |
| 模式按钮切换 bug | 切模式后 placeholder 不变 | 查 `currentMode = btn.dataset.mode` |
| 情绪/界面拦截不触发 | 输入情绪话术走了教学 | 查 meta_router 模式是否命中（`qa_emotion_detect.py`）|

### 10.2.3 测试金字塔总览（v0.19.27）

```
        ┌─────────────┐
        │ Playwright  │ ← 真实浏览器：UI 渲染/交互/模式切换（最终验证）
        │  浏览器测试  │
        ├─────────────┤
        │ 端到端 API  │ ← 验证后端链路：拦截/steering/情绪/知识库
        │  qa_*.py    │
        ├─────────────┤
        │ eval_harness│ ← 质量评估：意图识别/公式/深度/tool-use
        ├─────────────┤
        │ pytest 59   │ ← 单元+集成+验收：子代理/知识库/安全/世界观
        └─────────────┘
```

**开发节奏**：改后端 → pytest 59 保底 → qa_*.py 验证新功能 → Playwright 真实浏览器确认渲染 → 推送。

### 10.2.4 多轮提示词注入实验（v0.20.4 ⭐ multi_turn_eval.py）

**目的**：验证每个 sub agent / 对话类在多轮对话下的表现——对话连贯性不是单轮问答，必须多轮验证。

**5 维度检测**：

| 维度 | 检测什么 | 判定 |
|---|---|---|
| decay（退化）| 多轮后是否丢失上文/机械重复/答非所问 | 回复延续上轮核心实体 |
| decision（决策）| sub agent 是否执行职责（教学/陪伴/清点/方法/答案）| 回复含模式预期关键词 |
| style（语言）| 是否克制/无 AI 腔/语法完整（约纳斯风格）| 禁词 + 机械并列三连检测 |
| harness（约束）| 教学指令不被越界（affection 不强行上课）| affection 回复无教学词 |
| tool（工具）| 搜索/验证是否正确触发 | SSE tool 事件检测 |

**检测技巧**（避免误报）：
- 中文禁词用"精确短语"匹配（"不催你。" vs "不急着"——后者是合法完整句）
- "首先/其次/最后"需三连才算 AI 腔（单个合理连接不算）
- 对话退化需"完全答非所问"才算（话题自然转移如情绪升级是健康的）
- tool use 查 SSE 的 `event: tool` 而非文本痕迹

**实验结果（v0.20.4）**：6 模式（teach/chat/affection/knowledge/method/answer）× 5 维度全部通过——多轮无退化、决策正确、语言克制、affection 不越界、chat 真实触发 web_search。

### 10.2.5 全面接口测试（v0.20.5 ⭐ api_sweep.py）

**目的**：对每个接口做多角度、多轮提问测试，覆盖概念/续问/计算/边界/拦截/工具/导图。

**运行**：
```bash
python api_sweep.py        # 全端点多轮测试
python multi_turn_eval.py --mode all   # 5 维度多轮实验
```

**api_sweep 覆盖**：36 端点 × 多轮（teach 11 轮含知识导图/玻尔兹曼/情绪拦截/界面/知识库；chat 7 轮含记忆/搜索/情绪/元问题；answer/method/knowledge/affection + GET 端点）。

**实测（v0.20.5）**：42✓ 2⚠️ 0❌——全部核心功能通过。

**两套测试互补**：
- `multi_turn_eval.py`：5 维度质量（退化/决策/语言/harness/tool）
- `api_sweep.py`：全接口覆盖（HTTP 状态/空回复/拦截路由）



**目的**：验证每个 sub agent / 对话类在多轮对话下的表现——对话连贯性不是单轮问答，必须多轮验证。

**5 维度检测**：

| 维度 | 检测什么 | 判定 |
|---|---|---|
| decay（退化）| 多轮后是否丢失上文/机械重复/答非所问 | 回复延续上轮核心实体 |
| decision（决策）| sub agent 是否执行职责（教学/陪伴/清点/方法/答案）| 回复含模式预期关键词 |
| style（语言）| 是否克制/无 AI 腔/语法完整（约纳斯风格）| 禁词 + 机械并列三连检测 |
| harness（约束）| 教学指令不被越界（affection 不强行上课）| affection 回复无教学词 |
| tool（工具）| 搜索/验证是否正确触发 | SSE tool 事件检测 |

**运行**：
```bash
python multi_turn_eval.py --mode all        # 全模式
python multi_turn_eval.py --mode affection  # 单模式
```

**实验结果（v0.20.4）**：6 模式（teach/chat/affection/knowledge/method/answer）× 5 维度全部通过：
- 多轮对话无退化（LLM 记住上文——"我叫小明喜欢篮球"第二轮准确复述）
- 各 sub agent 决策正确（affection 陪伴不教学、method 给方法、answer 给完整答案）
- 语言克制（禁词 0 命中、"最后，也是最关键的一点"是合理连接非机械并列）
- affection 不越界（无"接下来我们上课"类）
- chat 真实触发 web_search（全新对话验证：`event: tool` + 搜索结果）

**检测技巧**（避免误报）：
- 中文禁词用"精确短语"匹配（"不催你。" vs "不急着"——后者是合法完整句）
- "首先/其次/最后"需三连才算 AI 腔（单个合理连接不算）
- 对话退化需"完全答非所问"才算（话题自然转移如情绪升级是健康的）
- tool use 查 SSE 的 `event: tool` 而非文本痕迹

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

# 10.7 自检复盘与未来优化任务列表（v0.19.20 ⭐ 阶段性总结）

> 本节与 CHANGELOG 中的 v0.19.20 记录同步。**下次启动开发时先读本节**——
> 它列出了已知缺口与待办，避免重复探索。

## 10.7.1 机制层优化（按优先级）

| # | 任务 | 现状 | 目标 | 工作量 |
|---|---|---|---|---|
| 1 | ~~周期级自我更新调度器~~ | ✅ v0.19.21 已实现（periodic_self_update.py 后台线程 + /api/self-update/run） | 已闭环 | — |
| 2 | SelfImprover 改进建议闭环 | analyze_failures 已接入周期调度器 | ✅ 已完成（periodic 每周跑 analyze_failures → improvements.md → 注入） | — |
| 3 | SelfEvolver 接入聊天模式 | on_session_end 只在 paeg.teach（教学模式）调用 | 闲聊对话后也调用 on_session_end 做失败反思 | 小 |
| 4 | 对话级记忆未完全落地 | MemorySystem 在 chat_stream 中构造但 long_term 读写链路待确认 | 确认/完善长期记忆跨会话读取 | 中 |
| 5 | 学科数文档与实际不一致 | 实际 19 个基础学科（已修正 §3.3.2），文档其他处如"26 学科"需核对 | 全文核对统一 | 小 |
| 6 | 工具调用前端可视化增强 | 已有 tool 事件但前端展示简单 | 展示工具名+参数+耗时，失败工具高亮 | 小 |
| 7 | 固定域名方案 | 临时隧道 URL 每次重启变化（用户暂缓，见 02_用户决策记录） | 有预算后升级（§6.3 方案 B 已写好） | 待用户确认 |
| 8 | 评估 harness 增强 | eval_harness 7 案例 | 扩充到学科×场景矩阵，接入 CI | 中 |
| 9 | 自进化证据闭环 | QualityGate L4 沙盒/证据反馈已实现但前端无入口 | 前端展示"已进化知识/提示词补丁/工具经验"，支持手动确认 | 中 |
| 10 | 知识蒸馏效果评估 | evolved 节点已能入库 | 评估蒸馏知识质量（对比权威来源），防止低级错误入库 | 中 |

## 10.7.2 内容层扩充（按优先级）

| # | 任务 | 现状 | 目标 |
|---|---|---|---|
| 1 | 学科覆盖 | 19 个基础学科（数学/物理/化学/生物/地理/语文/英语/政治/历史/法学/哲学/美学/现象学/伦理/文学/法语/德语/日语/考研数学） | 按需扩充（如经济学、计算机、心理学）——新增只需在 SUBJECT_STYLES 加条目 |
| 2 | 每日一句语料库 | quotes.py 88 行 | 扩充名言库，覆盖更多哲学家/教育者 |
| 3 | Library 资料 | 语言 13 份/数学 2 份/哲学 5 份/薇依 9 份 + 用户上传 | 持续上传（用户可通过 GUI 书本图标上传） |
| 4 | 词汇库 | Language 词汇表 1-8 + 高阶 + GRAMMAR | 可继续按 7 天×30 词节奏扩充 |
| 5 | 教学策略库 | pedagogy.py 若干策略 | 补充更多学习困难场景的策略 |
| 6 | 测试用例 | 59 个（单元+集成+验收） | 为新增功能补充测试 |
| 7 | 法语/德语/日语内容 | 只有学科风格，无具体资料 | 有需求时补 Library |

---

# 10.8 设计背景与材料存放位置索引（v0.19.20 ⭐ 供下次 LLM 读取）

> 本节告诉"下一个开发者/LLM"：项目的历史背景、设计文档、参考材料都在哪，
> 启动工作前先读哪些文件。

## 10.8.1 快速启动路径（读这些就能开工）

| 文件 | 作用 |
|---|---|
| `PAEG技术全景文档.md`（本文档） | 系统全貌：架构、数据流、API、部署、测试 |
| `CHANGELOG.md` | 版本历史：每个迭代改了什么 |
| `05_实现原型/README.md` | 原型代码导读 |
| `00_Gap与行动清单.md` | 已知缺口（最早的自检清单） |
| `07_参考与勘误/00_项目自检报告.md` | 自检报告 |

## 10.8.2 设计背景与决策记录

| 材料 | 位置 |
|---|---|
| 需求规格说明书 v1.0/v2.0 | `01_需求文档/` |
| 用户决策记录 v1.0/v2.0（含"不买域名先保公网方案"等决策） | `02_用户决策记录/` |
| 架构设计 v1.0 草图/定稿、v2.0、v3.0 迭代 | `03_架构设计_迭代/` |
| 最终设计 v3.1 | `04_最终设计/PAEG最终设计_v3.1.md` |
| 第一轮开发 Loop 总结 | `08_Loop记录/01_Loop第一轮总结.md` |
| 断点续传/状态评估/公网部署过程记录 | `intermediate/`（00_断点续传_状态评估、02_v08_公网部署_过程记录 等） |
| API 契约 | `07_参考与勘误/01_API契约.md` |

## 10.8.3 代码与数据

| 材料 | 位置 |
|---|---|
| 核心实现（40 个 .py 模块） | `05_实现原型/` |
| 子代理（6 个） | `05_实现原型/subagents.py` |
| 主类/教学循环 | `05_实现原型/paeg.py` |
| 提示词中心（人格/学科/学段） | `05_实现原型/prompts.py` |
| 工具注册表/缓存/恢复 | `tool_registry.py` / `tool_cache.py` / `tool_recovery.py` |
| 自我更新三模块 | `self_update.py` / `self_evolve.py` / `self_improve.py` |
| 可编辑教学记忆 | `05_实现原型/memory/PAEG_PEDAGOGY.md`（人工可编辑）+ cases.jsonl |
| 运行时数据 | `data/`（画像/反思/策略）、`users_data/<user_id>/`（长期记忆）、`evolve_data/`、`downloads/` |
| 前端 GUI | `09_GUI前端/index.html` + `assets/` |
| 测试 | `05_实现原型/tests/` + `06_测试与验证/` |
| 评估 harness | `05_实现原型/eval_harness.py` + eval_report.json |

## 10.8.4 知识库（Library）——PAEG"学过什么"的真实来源

| 领域 | 内容 |
|---|---|
| `Library/Language/` | 英语词汇扩充 1-8（7天×30词）、GRAMMAR大观、德语A1手册（pdf+docx）、高阶词汇表 |
| `Library/Math/` | 数理统计讲义（在线资源）、简明数据结构 PDF |
| `Library/Philosophy/` | 汉斯·约纳斯《责任原理》《生命现象》等 PDF |
| `Library/Simone Weil/` | 薇依著作：《重负与神恩》《科学与我们》《超自然认识》等 PDF + 文选 docx |
| `Library/KnowledgeBase/` | 结构化知识（subjects/facts，JSON/MD） |
| `Library/user_qa_lib/` | 用户上传的资料（傅里叶笔记等） |

## 10.8.5 外部环境与工具

| 项 | 位置/值 |
|---|---|
| GitHub 仓库 | `https://github.com/Golden2002/PAEG`（Golden2002 个人 token） |
| 公网入口 | 临时隧道 `https://girlfriend-object-combines-paragraphs.trycloudflare.com`（重启会变） |
| 本地服务 | `http://localhost:5000`，重启脚本 `C:\Users\团聚体\AppData\Local\Temp\opencode\restart_paeg.py` |
| 微信远程指挥 | wbo（详见 `D:\wbo-workspace\README.md`） |
| 启动脚本 | `D:\wbo-workspace\start-paeg-public.ps1`（公网一键重启） |

---

*本文档由 Sisyphus 编写，基于当前系统实际状态。修改代码前请先备份；重大改动后运行 §10.2 测试确认无回归。*
