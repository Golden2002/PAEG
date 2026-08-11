# PAEG 智能体架构链路图（v0.53 关键节点 · 分层展开）

> 阅读方式：先看 **L0 总览**（一图了解全貌），再按需展开各层细图。
> 每张图 ≤12 节点，聚焦单一主题，避免视觉负担。
> v0.53 更新：检索增强（RRF 融合 + jieba）+ 视频生成（演讲稿驱动）+ PPT 授课讲义 + 经验教训库（memo/022）+ 问答文档体系。
> 全部基于修复后真实代码绘制，连接已逐一验证。

---

## L0 · 架构总览（一图看懂）

> 六层结构 + 三支扩展（检索增强 / 视频生成 / PPT 讲义）。箭头表示数据流向。

```mermaid
flowchart TB
    L1["👤 用户层<br/>学生 · 外部智能体"]
    L2["🌐 应用层<br/>Flask Server · 意图路由 · 学段联动"]
    L3["🧠 主 Agent<br/>Émile · 9 个 subagent · 35 学科"]
    L4["✨ LLM 层<br/>DeepSeek"]
    L5["🔧 工具 + MCP 层<br/>工具链 · 技能 · 3 个 MCP server"]
    L6["📚 本地资源层<br/>知识库 · 画像 · 记忆 · PPT 输出"]
    L7["🔎 检索增强（v0.45）<br/>RRF 融合 + URL 规范化 + jieba 切词"]
    L8["🎬 视频生成（v0.53）<br/>演讲稿驱动 · TTS + 字幕对齐"]
    L9["📊 PPT 讲义（v0.51-53）<br/>授课讲义 · 经验库 memo/022"]

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L3 --> L5
    L5 --> L6
    L6 --> L3
    L6 --> L7
    L7 --> L3
    L6 --> L9
    L9 --> L3
    L3 --> L8
    L8 --> L6
```

> **分层细图导航**：
> - [L1 · 教学闭环](#l1--教学闭环九个-subagent-如何协同)（9 个 subagent 流水线）
> - [L1 · 学段-学科联动](#l1--学段-学科联动v025-新增)（v0.25 新增）
> - [L1 · 个体化（因材施教）](#l1--个体化闭环因材施教)
> - [L1 · 立德树人](#l1--立德树人闭环)
> - [L1 · 工具 / MCP / PPT](#l1--工具--mcp--ppt-生成)
> - [L1 · 自我进化](#l1--自我进化闭环)
> - [L1 · 检索增强（v0.45）](#l1--检索增强v045-新增)
> - [L1 · 视频生成（v0.53）](#l1--视频生成v053-新增)

---

## L1 · 意图路由闭环（v0.41.6 ⭐ 模式短路）

> 聚焦：提示词结构化管线——确定性信号（模式按钮）先行，LLM 判断次之，规则兜底兜尾。

```mermaid
flowchart LR
    B["前端模式按钮<br/>teach/chat/answer/method/knowledge/affection"] -->|"mode 字段随请求发送"| R["route_intent(text, llm, mode)"]
    R -->|"mode 命中 → 短路返回<br/>conf 0.95 不调 LLM"| D["直接路由到对应分支"]
    R -->|"mode 未命中 → LLM 判断<br/>14 意图选项内选一"| L["LLM 语义判断"]
    L -->|"低置信/异常 →"| FB["rule_fallback_intent<br/>规则兜底（interface 优先 meta）"]
    L -->|"teach/answer →"| D
    FB --> D
    D --> P["build_general_chat_system(learner, mode)<br/>注入用户画像 + 模式场景段"]
    P --> O["输出 → language_refiner<br/>语言规范性（AI 味≥0.4 才改写）"]
```

**说明**：判断成本分层——确定性信号（免费）> 规则（廉价）> LLM（昂贵）。用户已选模式时 LLM 不必重复判断；画像+历史+模式场景段一并注入 system prompt（结构化提示词管线）。

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

---

## L1 · 检索增强（v0.45 新增）

> 聚焦：中文检索质量升级——多路检索 + RRF 融合，中英双语变体 + 多轮改写覆盖。

```mermaid
flowchart LR
    Q["问题/多轮对话"] --> V["查询变体生成<br/>中英双语 × 多轮改写（5 主题 × 3 轮 → 16 条）"]
    V --> BM["BM25 检索<br/>jieba 中文切词"]
    V --> NW["网络检索<br/>web_search_multi"]
    BM --> RRF["RRF 融合<br/>倒数排名融合"]
    NW --> RRF
    RRF --> U["URL 规范化<br/>去重 + 归一"]
    U --> R["最终检索结果<br/>注入回答上下文"]
```

**说明**：jieba 解决中文切词（"分离定律"不再被拆碎）；RRF 融合多路结果排序稳定；URL 规范化去重防止重复引用。

---

## L1 · 视频生成（v0.53 新增）

> 聚焦：演讲稿驱动的视频管线——先文后声，音画同步。

```mermaid
flowchart LR
    S["教学主题/检索材料"] --> W["写演讲稿<br/>LLM 生成 narration"]
    W --> T["TTS 合成音频<br/>edge-tts · 时长 audio_duration"]
    W --> C["生成字幕<br/>subtitle_cues 对齐时间轴"]
    T --> A["合并输出视频<br/>音频 + 画面"]
    C --> A
    A --> O["交付<br/>video/*.mp4"]
```

**说明**：**演讲稿驱动**（v0.53）——先定 narration 文本，再生成 TTS 与字幕 cue，`audio_duration` 保证音频长度与视频画面对齐，避免早期"先视频后配音"的错位。经验沉淀在 `memo/022_PPT与视频制作经验教训库.md`。
