# PAEG 智能体架构链路图（v0.24 关键节点 · 分层展开）

> 阅读方式：先看 **L0 总览**（一图了解全貌），再按需展开各层细图。
> 每张图 ≤10 节点，聚焦单一主题，避免视觉负担。
> 全部基于修复后真实代码绘制，20 项连接已逐一验证。

---

## L0 · 架构总览（一图看懂）

> 六层结构，每层是一个可展开的独立模块。箭头表示数据流向。

```mermaid
flowchart TB
    L1["👤 用户层<br/>学生 · 外部智能体"]
    L2["🌐 应用层<br/>Flask Server · 意图路由"]
    L3["🧠 主 Agent<br/>Émile · 9 个 subagent"]
    L4["✨ LLM 层<br/>DeepSeek"]
    L5["🔧 工具 + MCP 层<br/>工具链 · 技能 · 外部 server"]
    L6["📚 本地资源层<br/>知识库 · 画像 · 记忆"]

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L3 --> L5
    L5 --> L6
    L6 --> L3
```

> **分层细图导航**：
> - [L1 · 教学闭环](#l1--教学闭环九个-subagent-如何协同)（9 个 subagent 流水线）
> - [L1 · 个体化（因材施教）](#l1--个体化闭环因材施教)
> - [L1 · 立德树人](#l1--立德树人闭环)
> - [L1 · 工具 / MCP](#l1--工具与-mcp-层)
> - [L1 · 自我进化](#l1--自我进化闭环)

---

## L1 · 教学闭环（九个 subagent 如何协同）

> 聚焦：一次教学对话中，9 个 subagent 的分工与协作。

```mermaid
flowchart LR
    Q["学生提问"] --> G["危机检查<br/>_affection_gate_check"]
    G -->|"危机 →"| AFF["AffectionSupportor<br/>立德为先"]
    G -->|"正常 →"| DIA["① Diagnostor<br/>诊断"]
    DIA --> PLA["② Planner<br/>计划"]
    PLA --> PRE["③ Presenter<br/>讲解"]
    PRE --> EVA["④ Evaluator<br/>双维评估"]
    EVA --> ADA["⑤ Adapter<br/>调整"]
    ADA -.->|"换风格/补例子"| PRE
    DIA & PLA & PRE & EVA & ADA --> LLM["DeepSeek"]
    EVA -.->|"低分 →"| SELF["⑥ 自我进化<br/>evolve_prompt"]
    SELF -.-> PRE
```

**说明**：Diagnostor/Planner/Presenter/Evaluator/Adapter 是教学主链；AnswerSolver 独立处理"直接要答案"；AffectionSupportor 危机先行；SelfUpdateAgent 会话后反思；Individuality 贯穿全程注入画像。

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

## L1 · 工具与 MCP 层

> 聚焦：LLM 如何调用工具、技能，以及 MCP 双向连通。

```mermaid
flowchart LR
    A["Agent / subagent"] --> FC["Function Calling"]
    FC --> T["tool_registry<br/>7 工具"]
    FC --> SK["skill_registry<br/>10 技能"]
    T --> MC["MCPClientManager"]
    MC --> FS["filesystem<br/>14 工具"]
    MC --> MM["memory<br/>9 工具"]
    MG["mcp_gateway :8765"] -->|"对外暴露"| T
    T --> KB["知识库"]
```

---

## L1 · 自我进化闭环

> 聚焦：教学经验如何回流，让系统越用越懂怎么教。

```mermaid
flowchart LR
    T["教学/对话"] --> R["反思<br/>SelfUpdateAgent"]
    R --> SUG["self_update_suggestions.jsonl"]
    SUG --> IMP["improvements.md<br/>分段归类"]
    IMP --> EV["SelfEvolution<br/>evolve_prompt"]
    EV --> P["提示词/知识库更新"]
    P --> T
```
