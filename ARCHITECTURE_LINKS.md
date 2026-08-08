# PAEG 智能体架构链路图（v0.25 关键节点 · 分层展开）

> 阅读方式：先看 **L0 总览**（一图了解全貌），再按需展开各层细图。
> 每张图 ≤10 节点，聚焦单一主题，避免视觉负担。
> v0.25 更新：3 新学科（语言学/大气科学/量子场论）+ 学段-学科联动 + PPT MCP + SelfUpdateAgent 增强。
> 全部基于修复后真实代码绘制，连接已逐一验证。

---

## L0 · 架构总览（一图看懂）

> 六层结构，每层是一个可展开的独立模块。箭头表示数据流向。

```mermaid
flowchart TB
    L1["👤 用户层<br/>学生 · 外部智能体"]
    L2["🌐 应用层<br/>Flask Server · 意图路由 · 学段联动"]
    L3["🧠 主 Agent<br/>Émile · 9 个 subagent · 29 学科"]
    L4["✨ LLM 层<br/>DeepSeek"]
    L5["🔧 工具 + MCP 层<br/>工具链 · 技能 · 3 个 MCP server"]
    L6["📚 本地资源层<br/>知识库 · 画像 · 记忆 · PPT 输出"]

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L3 --> L5
    L5 --> L6
    L6 --> L3
```

> **分层细图导航**：
> - [L1 · 教学闭环](#l1--教学闭环九个-subagent-如何协同)（9 个 subagent 流水线）
> - [L1 · 学段-学科联动](#l1--学段-学科联动v025-新增)（v0.25 新增）
> - [L1 · 个体化（因材施教）](#l1--个体化闭环因材施教)
> - [L1 · 立德树人](#l1--立德树人闭环)
> - [L1 · 工具 / MCP / PPT](#l1--工具--mcp--ppt-生成)
> - [L1 · 自我进化](#l1--自我进化闭环)

---

## L1 · 教学闭环（九个 subagent 如何协同）

> 聚焦：一次教学对话中，9 个 subagent 的分工与协作。

```mermaid
flowchart LR
    Q["学生提问"] --> G["危机检查<br/>_affection_gate_check"]
    G -->|"危机 →"| AFF["AffectionSupportor<br/>立德为先"]
    G -->|"正常 →"| GS["学段检查<br/>grade_blocked?"]
    GS -->|"跨学段 →"| BLK["提示切换学段<br/>不教学"]
    GS -->|"通过 →"| DIA["① Diagnostor<br/>诊断"]
    DIA --> PLA["② Planner<br/>计划"]
    PLA --> PRE["③ Presenter<br/>讲解"]
    PRE --> EVA["④ Evaluator<br/>双维评估"]
    EVA --> ADA["⑤ Adapter<br/>调整"]
    ADA -.->|"换风格/补例子"| PRE
    DIA & PLA & PRE & EVA & ADA --> LLM["DeepSeek"]
    EVA -.->|"低分 →"| SELF["⑥ 自我进化<br/>evolve_prompt"]
    SELF -.-> PRE
```

**说明**：Diagnostor/Planner/Presenter/Evaluator/Adapter 是教学主链；**v0.25 新增学段检查**（跨学段学科拦截）；AnswerSolver 独立处理"直接要答案"；AffectionSupportor 危机先行；SelfUpdateAgent 会话后反思；Individuality 贯穿全程注入画像。

---

## L1 · 学段-学科联动（v0.25 新增）

> 聚焦：学段与学科绑定——高中学段不出现语言学/量子场论等大学学科。

```mermaid
flowchart LR
    G["学段选择<br/>初中/高中/本科/考研"] --> F["get_subjects_for_grade()<br/>SUBJECT_MIN_GRADE"]
    F --> M["学科菜单<br/>初中12·高中22·本科28·考研2"]
    G --> D["detect_subject(text, grade)"]
    D -->|"学科≤学段"| T["正常教学"]
    D -->|"学科>学段"| B["grade_blocked<br/>提示切换学段"]
    D -->|"真未收录"| U["记录需求"]
```

---

## L1 · 个体化闭环（因材施教）

> 聚焦：Individuality 如何把对话/自述变成可用的个性化画像。

```mermaid
flowchart LR
    H["对话历史"] --> F["extract_user_facts"]
    S["自我陈述"] --> F
    F --> IM["Individuality.run<br/>LLM 增量建模"]
    OLD["已有画像"] --> IM
    IM --> T["student_trait<br/>17 维画像"]
    T --> P["persist 持久化"]
    P --> OLD
    IM --> C["inject_control<br/>语言/风格/深度"]
    C --> OUT["个性化输出"]
```

---

## L1 · 立德树人闭环

> 聚焦：AffectionSupportor 的危机处理与陪伴流程。

```mermaid
flowchart LR
    E["情绪/危机表达"] --> D["三态检测"]
    D --> S2["safety 检查"]
    S2 --> W["薇依世界观<br/>AffectionSAPAO.md"]
    W --> P2["先回应再关怀"]
    P2 --> O["陪伴输出"]
    O --> R["情绪稳定 → 回归学习"]
```

---

## L1 · 工具 / MCP / PPT 生成

> 聚焦：LLM 如何调用工具、技能、MCP，以及 v0.25 新增的 PPT 生成链路。

```mermaid
flowchart LR
    A["Agent / subagent"] --> FC["Function Calling"]
    FC --> T["tool_registry<br/>7 工具"]
    FC --> SK["skill_registry<br/>10 技能"]
    T --> MC["MCPClientManager<br/>3 个 server"]
    MC --> FS["filesystem<br/>14 工具"]
    MC --> MM["memory<br/>9 工具"]
    MC --> PX["pptx_mcp_server<br/>生成 PPT"]
    PX --> OUT["downloads/ppt/*.pptx"]
    MG["mcp_gateway :8765"] -->|"对外暴露"| T
    T --> KB["知识库"]
```

---

## L1 · 自我进化闭环（v0.25 增强）

> 聚焦：教学经验如何回流——v0.25 SelfUpdateAgent 扩到 7 分类 + 落地执行器。

```mermaid
flowchart LR
    T["教学/对话"] --> R["反思<br/>SelfUpdateAgent"]
    R --> SUG["self_update_suggestions.jsonl"]
    SUG --> EXE["落地执行器<br/>v0.25"]
    EXE -->|"subject_addition"| NS["学科注册 JSON<br/>自动入库"]
    EXE -->|"library_update"| PL["pending_library.json"]
    SUG --> IMP["improvements.md"]
    IMP --> EV["SelfEvolution<br/>evolve_prompt"]
    EV --> P["提示词/知识库更新"]
    P --> T
```
