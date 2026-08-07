# PAEG 智能体架构链路图（v0.24 关键节点 · 修复后真实连接）

> 本图基于修复后的真实代码状态绘制，20 项连接已逐一验证（arch 检查通过）。
> 渲染：GitHub 原生支持 Mermaid，任何 Markdown 查看器均可直接显示。

## 一、全链路总览图（技术文档 §1.6 用）

```mermaid
flowchart TB
    subgraph USER["用户层"]
        S["🧑 学生 / 学习者"]
        EXT["🤖 外部智能体<br/>Claude / Codex / OpenCode"]
    end

    subgraph APP["应用层 · Flask Server (server.py)"]
        WEB["Web GUI / API 端点<br/>chat·teach·answer·affection·skills·upload"]
        ROUTER["meta_router.route()<br/>意图集中分发"]
        AGENTENG["AgentEngine<br/>Plan→Act→Observe→Reflect"]
        HEALTH["/api/health<br/>mcp_connected 2/2"]
    end

    subgraph MAIN["主 Agent · Émile Novis (paeg.py)"]
        PAEG["PAEG 主智能体<br/>持有 9 个 subagent"]
        GATE["_affection_gate_check<br/>危机信号先行"]
        IND["Individuality<br/>17 维画像注入"]
    end

    subgraph SUB["Subagent 层（9 个）"]
        DIA["Diagnostor 诊断"]
        PLA["Planner 计划"]
        PRE["Presenter 呈现"]
        EVA["Evaluator 评估<br/>讲解质量+学生状态双分"]
        ADA["Adapter 调整<br/>决策真正执行"]
        ANS["AnswerSolver 直答"]
        AFF["AffectionSupportor<br/>立德树人 · 危机陪伴"]
        SUA["SelfUpdateAgent 自更新"]
        IND2["Individuality 个体化<br/>17 维·增量建模·持久化"]
    end

    subgraph LLM["LLM 层"]
        DS["DeepSeek (llm_adapter)<br/>全部 subagent 调用"]
    end

    subgraph TOOL["工具链层"]
        REG["tool_registry<br/>web_search·verify_math·fetch_page<br/>daily_quote·save_doc·get_time"]
        SK["skill_registry<br/>10 技能（L1 目录注入）"]
        F4["用户文件 4 能力<br/>QA·讲解·原文·重组 (BM25)"]
    end

    subgraph MCP["MCP 层"]
        MC["MCPClientManager<br/>filesystem 14 + memory 9 工具"]
        MG["mcp_gateway :8765<br/>PAEG 能力对外暴露"]
    end

    subgraph RES["本地资源层"]
        KB["knowledge_base 知识库"]
        LIB["Library 薇依原著<br/>weil_corpus.json"]
        MEM["memory/ 记忆<br/>AffectionSAPAO.md"]
        USR["users_data/ 画像<br/>users.json"]
        IMP["improvements.md<br/>自更新建议回流"]
    end

    S -->|"对话/自述/上传"| WEB
    EXT -->|"MCP 协议"| MG
    WEB -->|"路由分发"| ROUTER
    ROUTER -->|"教学意图"| PAEG
    ROUTER -->|"agent 模式"| AGENTENG
    ROUTER -->|"危机/情绪"| AFF
    AGENTENG --> DS
    PAEG -->|"危机检查先行"| GATE
    PAEG --> IND
    IND --> IND2
    GATE -->|"危机通过→教学"| DIA
    DIA --> PLA --> PRE --> EVA --> ADA
    EVA -.->|"学生状态反馈"| ADA
    ADA -.->|"风格/难度决策回流"| PRE
    PAEG --> ANS
    PAEG --> SUA
    PAEG --> AFF
    DIA & PLA & PRE & EVA & ADA & ANS & AFF & SUA & IND2 --> DS
    PAEG -->|"工具调用"| REG
    REG --> SK
    REG --> MC
    PAEG --> F4
    MC -->|"filesystem/memory 标准 server"| MEM
    MG -->|"复用 PAEG 工具"| REG
    DIA & PLA --> KB
    PRE --> LIB
    AFF --> MEM
    IND2 --> USR
    SUA --> IMP
    SUA --> MEM
    REG --> KB
    KB --> LIB
    IMP --> PAEG
    USR -.->|"画像继承"| IND2
    HEALTH --> MC
```

## 二、教学闭环链路（技术文档 §1.6.1 用）

```mermaid
flowchart LR
    S["学生提问"] --> G["_affection_gate_check<br/>危机信号？"]
    G -->|"是→陪伴"| AFF["AffectionSupportor<br/>立德为先"]
    G -->|"否→教学"| I["Individuality<br/>17 维画像注入"]
    I --> D["Diagnostor<br/>诊断就绪度"]
    D --> P["Planner<br/>差异化计划"]
    P --> PR["Presenter<br/>个性化讲解"]
    PR --> E["Evaluator<br/>讲解质量 + 学生状态"]
    E --> A["Adapter<br/>switch_style / reinforce"]
    A -->|"决策回流"| PR
    A -->|"difficulty_delta 累计"| D
    PR -->|"呈现给学生"| S
    A --> EVA2["SelfEvolution<br/>evolve_prompt + on_session_end"]
    EVA2 -->|"改进提示词"| PR
```

## 三、个体化闭环链路（亮点文档用 · 因材施教）

```mermaid
flowchart LR
    H["对话历史"] --> F["extract_user_facts"]
    SD["自我陈述"] --> F
    F --> IM["Individuality.run<br/>LLM 增量建模"]
    OLD["已有画像<br/>users_data"] --> IM
    IM --> T["student_trait 17 维<br/>正交框架"]
    T --> P["persist 持久化"]
    P --> OLD
    IM --> C["inject_control<br/>语言/风格/深度/节奏/情绪"]
    C --> SYS["LLM system prompt"]
    SYS --> OUT["母语回复/因材施教输出"]
```

## 四、立德树人闭环链路（亮点文档用）

```mermaid
flowchart LR
    E["情绪/危机表达"] --> DET["AffectionSupportor<br/>三态检测"]
    DET --> SAFE["safety 检查<br/>自伤信号"]
    SAFE --> WP["薇依世界观<br/>AffectionSAPAO.md"]
    WP --> PRIN["先回应再关怀<br/>拒绝规则·不短路"]
    PRIN --> LLM2["LLM 陪伴输出"]
    LLM2 --> ST["情绪稳定→回归学习"]
```

## 五、工具/MCP/资源链路（技术文档 §1.6.9 用）

```mermaid
flowchart TB
    subgraph AG["Agent 侧"]
        PAEG2["主 Agent / subagent"]
        FC["Function Calling"]
    end
    subgraph TL["工具链"]
        REG2["tool_registry<br/>7 工具"]
        SK2["skill_registry<br/>10 技能 L1 目录"]
    end
    subgraph MP["MCP 层"]
        MC2["MCPClientManager<br/>连外部标准 server"]
        FS["filesystem (14 工具)"]
        MM["memory (9 工具)"]
        MG2["mcp_gateway :8765"]
    end
    subgraph LR2["本地资源"]
        KB2["知识库"]
        LIB2["Library 薇依原著"]
        USR2["users_data 画像"]
    end
    PAEG2 -->|"工具选择"| FC
    FC --> REG2
    FC --> SK2
    REG2 -->|"mcp__ 前缀"| MC2
    MC2 --> FS
    MC2 --> MM
    MG2 -->|"对外暴露"| REG2
    REG2 --> KB2
    SK2 --> KB2
    LIB2 --> KB2
    USR2 --> PAEG2
```
