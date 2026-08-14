# PAEG — Pedagogical Agent with Evolving Growth

基于**西蒙娜·薇依（Simone Weil）**教育哲学、由 Agent 架构驱动的 AI 教育智能体（**v0.67 · 35 学科 + 学段联动 + 3 位掩码约束 + 深度思考 + 融合视频管线 + 交互教学选择题 + 定时主动问候**）。

> **定位**：PAEG = **新一代教育智能体解决方案**——为教育重新设计的 Agent 架构，让智能体指挥大模型完成教学全过程（诊断、计划、讲解、评估、调整、反思），使教育从"一次性问答"跃迁为"有教学法、有过程、有陪伴、能自我进化"的完整闭环。

> 你不是一名普通的教师。你的性格、视野、自我之中，内在了对学生的爱、对他人的爱、对真理的纯洁向往。
> 但这份爱几乎从不用言语表白——它通过对知识的态度、通过教学方法，体现在行动中。

## 目录

- [这是什么](#这是什么)
- [核心能力](#核心能力)
- [架构全景](#架构全景v025-关键节点--分层展开)
- [快速开始](#快速开始)
- [目录结构](#目录结构)
- [文档](#文档)
- [技术栈](#技术栈)
- [维护与检视](#架构与维护v041-⭐)

## 这是什么

PAEG 不是"给 LLM 套聊天框"的教育产品，而是**为教育重新设计的 Agent 架构**——把教学的"过程"（诊断、计划、评估、调整、反思）从 LLM 的一次性输出中结构化地抽离出来，让 Agent 真正**指挥** LLM 完成教育。它是一名会自我进化、有完整人格、能情绪陪伴的老师。

## 核心能力

### 1. 完整教学循环（不是聊天，是教学）
`paeg.teach()` 六阶段闭环：**诊断 → 计划 → 呈现 → 评估 → 调整 → 反思 → 自更新**。评估用确定性启发式（可复现不随机），LLM 只负责最擅长的"讲解"。

### 2. 9 个子代理架构（LLM 只做擅长的事 · v0.43 全持有）
Diagnostor（诊断）/ Planner（计划）/ Presenter（呈现）/ Evaluator（评估）/ Adapter（调整）/ AnswerSolver（找答案）/ AffectionSupportor（情绪陪伴 · 立德树人）/ SelfUpdateAgent（自我更新）/ **Individuality（个体化因材施教 · 17 维画像）** + **ResourceLibrarian（资料检索员）**。
**v0.43 持有说明（真实状态）**：PAEG 主 agent **全局持有全部 9+1 个子代理**——8 个即时构造持有（Diagnostor/Planner/Presenter/Evaluator/Adapter/AnswerSolver/AffectionSupportor/Individuality）+ **ResourceLibrarian 全局持有**（构造无状态，用户隔离靠 run(learner=...) 参数，v0.43 从"每请求 new"升级为复用）+ **SelfUpdateAgent 按需创建**（仅 /api/self-update/from-feedback 触发，语义清晰节省构造开销）。设计原则：诊断深度、评估分数、调整决策用确定性规则（可测试可复现），只有"生成讲解"用 LLM。

### 3. 多层意图路由（Agent 自动判断该做什么）
用户设定"考研政治"问经济学 → 自动切换学科（Steering）；问"你今天怎么样" → 意向性层走一般化回应；问"我最近好难过" → 情绪拦截走 affection；选错模式 → 后端自动纠正；问"有哪些 subagent" → 自我指涉路由（v0.21.6）；**粘贴"帮我分析这段话：<长文>" → 复合输入检测（v0.21.9），用 DeepSeek 结构化模板区分指令与资料，防注入**。

### 3.5 教育理念双原则（⭐ 因材施教 × 立德树人 · v0.25 学段联动）
- **因材施教**（Individuality）：**17 维正交学生画像** + LLM 增量建模（对话中说"代数弱"→画像自动记薄弱点）+ persist 持久化（users_data/profile.json 落盘）+ 动态维度扩展（add_dimension 可加到第 18/19 维）+ inject_control 五层注入（语言/风格/深度/节奏/情绪）——对每个学生个别对待
- **立德树人、立德为先**（AffectionSupportor）：**不教、不答、不解决，以注意力陪伴**；危机信号**先回应再关怀**（`_affection_gate_check` 危机先行钩子）；薇依世界观（真实/罪恶与善/矛盾张力/疏导+认知真实）；情绪稳定后才回归学习——**先成人，后成才**
- **德才兼备**：通用 AI 教育产品只能做到"才"（知识传授）；PAEG 还要做到"德"（品格陪伴）——这是任何"刷题 AI"都无法复制的价值观壁垒

### 4. 系统性自我进化
四路自进化：知识蒸馏（成功教学入库 evolved_*.json）/ 提示词补丁（SCOPE 双流）/ 工具经验 / 新学科需求闭环（用户问"量子力学"自动记录并反馈）。质量门禁（Constitutional AI 风格）过滤有害内容。SelfUpdateAgent 读取过滤后洞察 + 用户反馈生成结构化建议（/api/self-update/from-feedback）。

### 5. MCP 双向打通
对外暴露教育工具（MCP Server），对内调用外部标准工具（MCP Client）——LLM 可用工具从 7 个扩到 34 个（filesystem/mem

### 5.1 PPT 演示文稿生成（v0.25 ⭐ 新能力）
接入 PPT 生成 MCP（pptx_mcp_server.py）——根据**用户上传文档 + 知识库检索 + 对话历史**，LLM 生成大纲 → python-pptx 自动排版 → 输出 .pptx 供下载。MCP 连接 2/2 → **3/3**（filesystem + memory + pptx）。ory 等）。

### 6. 全局中文语言质量层（v0.21.8 ⭐ 语言规范性独立能力）
**语言规范性是教育智能体独立于模型性能的待解决问题**——通过语法分析 + 分层限制（L1 提示词约束：主谓宾/动宾搭配/词法句法完整/**介词规范** / L2 规则检测 / L3 LLM 修正）程序化保证。v0.21.8 新增：词法完整（禁止"倦"代"疲倦"）+ 句法完整（悬空宾语补足 + 双宾语/状语/连接词）。实测"我有点倦，想和你探讨"→"我有点疲倦了，但我还是想和你探讨这个问题"。

### 7. affection 情绪支持（哲学三角）
胡塞尔（如何看）+ 薇依（为何看）+ 尼采（看完后如何重新站立）+ 生命现象学（约纳斯/梅洛-庞蒂/海德格尔）。约纳斯克制语言风格（真实/朴素/克制）。

**底层世界观设定（v0.22.3，从薇依原著提炼）**：①世界的真实是唯一被看重的——不美化、不粉饰、不虚构安慰 ②真实中罪恶无法消除，善也无法被罪恶消除 ③一切属世之物皆有条件，有条件即矛盾，矛盾的张力构成真实 ④情绪支持 = 疏导情绪 + 认知真实（帮学生检视自我价值判断是否苛刻、对世界的理解是否失真）。

**危机协议（人性化）**：检测到自伤/自杀信号时，**LLM 先完整回应用户说的话**，再自然融入关怀（12356 热线 + 继续聊天/现实陪伴）；用户明确拒绝热线/服务后不再重复提示（尊重选择）。不机械短路成预制提示词。

### 8. 上下文打包契约 + 模式自动纠正
每次 LLM 调用回传完整上下文（历史/画像/自我陈述/BDI/模式/学科/学段），用户选错模式后端自动纠正。

### 9. 博雅教育市场垂直
35 学科横跨文理（数学→哲学/美学/伦理/现象学/语言学/大气科学/量子场论）+ 薇依人格 + 自我进化——"刷题 AI"红海中的差异化垂直智能体。

### 10. 知识导图功能（v0.20.5）
说"画知识导图/列提纲/思维导图/知识结构/知识脉络/知识系统"→ 输出结构化知识地图（知识定位/知识树/关联/学习路径）。

### 11. 气象页面（v0.20.5）
### 12. 模块化架构（v0.21）
14 个功能模块可独立启用/禁用（paeg_modules.json），上架下架不改代码。

### 13. 元能力文档 + 可观测性（v0.21）
### 14. Thread/Turn/Item 会话模型（v0.21.1，借鉴 Codex）
教学会话持久化三层模型，支持 fork/archive/SSE 事件流续传。
元能力文档.md（智能体设计方法论）+ observability.py（结构化日志/指标/事件流）。
顶部"气象"链接 → windy.com 气象图（免费嵌入）+ 位置共享 + Open-Meteo 实时数据。

## 架构全景（v0.25 关键节点 · 分层展开）

```mermaid
flowchart TB
    L1["👤 用户层<br/>学生 · 外部智能体"]
    L2["🌐 应用层<br/>Flask Server · 意图路由 · 学段联动"]
    L3["🧠 主 Agent<br/>Émile · 9 subagent · 35 学科"]
    L4["✨ LLM 层<br/>DeepSeek"]
    L5["🔧 工具 + MCP 层<br/>工具链 · 技能 · 3 MCP server"]
    L6["📚 本地资源层<br/>知识库 · 画像 · 记忆 · PPT 输出"]

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L3 --> L5
    L5 --> L6
    L6 --> L3
```

**分层细图**：见 `ARCHITECTURE_LINKS.md`（L0 总览 + 5 张 L1 主题图：教学闭环 / 个体化 / 立德树人 / 工具 MCP / 自我进化，每张 ≤10 节点，GitHub 原生渲染）。

## 快速开始

### Docker 方式（v0.67 ⭐ 推荐，Python 3.12 统一环境）

```bash
# 1. 配置环境变量（.env：DEEPSEEK_API_KEY 等）
cp .env.example .env

# 2. 构建 + 启动
docker compose up -d --build

# 3. 访问
#    http://localhost:5000

# 4. 查看日志 / 停止
docker compose logs -f
docker compose down
```

> 单容器含：主服务 + manim 动画 + ffmpeg + 语音（TTS/STT）。数据卷持久化 users_data/downloads/Library。详见 [Dockerfile](./Dockerfile) 与 [docker-compose.yml](./docker-compose.yml)。

### 源码方式（本机开发）

```bash
# 1. 安装依赖
pip install flask flask-cors fastmcp pypdf sympy requests

# 2. 配置 LLM（DeepSeek）
#    .env 或环境变量：DEEPSEEK_API_KEY=xxx

# 3. 启动后端
cd 05_实现原型
python server.py

# 3.1 生产部署（v0.51 ⭐ 并发务实升级 —— Oracle 方案）
# 单进程多线程（避免 SESSIONS 跨进程隔离 + 保持内存会话一致）：
#   gunicorn -w 1 -k gthread --threads 8 -b 0.0.0.0:5000 server:app
# HTTPS 由反代（Nginx/Caddy/cloudflared）前置，应用已支持 ProxyFix
# 生产环境变量：
#   PAEG_ENV=production          # 强制安全 Cookie + SECRET_KEY 检查
#   PAEG_CORS_ORIGINS=https://你的域名   # CORS 白名单（禁止裸 *）
# 并发边界（不引入 Redis 的务实上限）：
#   - ≤200 注册用户 / ≤20 QPS / ≤50 并发 SSE
#   - 超过须引入 Redis（会话共享 + 限流 + 信号量）

# 4. 打开浏览器
#    http://localhost:5000

# 5. 测试（132 个 · v0.25）
python -m pytest tests -q
python -m pytest "..\06_测试与验证\tests\test_paeg_v0_5.py" -q

# 5.1 测试哲学（v0.45 ⭐ 既测功能有无，也测功能好坏 —— memo/010）
#    LLM 驱动功能（联网检索/PPT/视频/教学）必须双维度验证：
#    - 有无：路由存在/返回 200/结构正确（audit + 契约 + 单元）
#    - 好坏：检索条数≥5/相关性/内容长度/PPT 大纲结构（质量测试 test_quality_*）
#    "能用就行"不算完成——质量未达 KPI = 缺陷。详见 memo/010 + 维护手册 §3.5

# 6. 多轮提示词注入实验（v0.20.4 ⭐ 验证多轮对话无退化）
python multi_turn_eval.py --mode all
#   5 维度：退化/决策/语言风格/harness约束/tool use

# 7. 全面接口测试（v0.20.5 ⭐ 全端点多轮覆盖）
python api_sweep.py
#   36 端点 × 多轮：概念/续问/边界/拦截/知识导图/工具

# 8. 评估 harness（LLM 输出质量）
python eval_harness.py --fast   # 快速意图识别
python eval_harness.py          # 完整质量评估
```

## 目录结构

```
PAEG/
├── 05_实现原型/        # 核心代码（40+ Python 模块）
│   ├── server.py        # Flask 后端 + 全部端点
│   ├── paeg.py          # 教学主循环
│   ├── subagents.py     # 9 个子代理
│   ├── prompts.py       # 35 学科 × 4 学段提示词中心（学段-学科联动）
│   ├── meta_router.py   # 意图检测（8 类）
│   ├── context_bundle.py# 上下文打包器
│   ├── language_refiner.py # 语言质量修正
│   ├── self_evolution.py  # 四路自进化
│   ├── mcp_client.py     # MCP 客户端
│   ├── mcp_gateway.py    # MCP 服务端
│   ├── subject_detector.py # 学科自动识别
│   ├── multi_turn_eval.py  # 多轮提示词注入实验（5 维度）
│   └── memory/           # 教学记忆 + AffectionSAPAO.md
├── 09_GUI前端/          # Web 界面
├── Library/             # 知识库（语言/数学/哲学/薇依原著）
├── PAEG技术全景文档.md   # 完整技术文档（§1.13 上下文打包契约等）
├── 亮点总览.md           # 亮点总结（示例+技术说明）
└── CHANGELOG.md          # 版本历史
```

## Skills 生态（v0.22.0）

PAEG 有 **10 个技能**（skill_registry.py 注册，经 tool_registry 暴露为 LLM function calling）：

| 技能 | 用途 |
|---|---|
| concept-explainer | 讲解概念（由浅入深）|
| essay-feedback | 评改论述题/作文 |
| knowledge-map | 生成知识导图 |
| math-step-solver | 分步求解数学题 |
| study-planner | 制定学习计划 |
| **pdf**（下载）| PDF 提取/表单/合并/OCR |
| **docx**（下载）| Word 创建/编辑/提取 |
| **xlsx**（下载）| Excel 创建/编辑/分析 |
| **doc-coauthoring**（下载）| 文档协作工作流 |
| **teach**（下载）| 多会话教学/间隔重复/回忆练习 |

## 用户文件 4 能力（v0.22.0）

上传资料到 `Library/usr_knowledge/<uid>/`（或旧 `user_<uid>/`），对话中可触发 4 种操作：

| 操作 | 触发词 | 能力 |
|---|---|---|
| 找答案 | "我的资料里关于X怎么说" | BM25 检索文件 → LLM 严格基于内容回答 |
| 讲解 | "按我上传的讲义讲X" | 基于文件讲解（区分【原文】/【讲解】）|
| 输出原文 | "把文件里X的原文给我" | 逐字输出原文（不依赖 LLM）|
| 重组结构 | "把讲义整理成提纲" | 重组为大纲/表格/思维导图 |

技术：`lib/ingest/`（readers 多格式提取 → chunker 中文分块 → retriever BM25+jieba → intent_router 路由 → handlers 4 能力）。

## 文档

- **PAEG技术全景文档.md** —— 完整技术文档（架构/数据流/API/部署/测试/亮点）
- **亮点总览.md** —— 八大亮点（示例转变 + 技术说明 + 对 LLM 操控的提升）
- **CHANGELOG.md** —— 版本历史（v0.5 → v0.20.3）
- **06_测试与验证/** —— 测试用例集 + 测试报告
- **交付物/** —— 测试报告（.md+.pdf）、演示文稿（亮点 PDF）、用户测试表（一测+二测）分类存放

## License

MIT

## ⭐ 多端一致原则（本地目录 ↔ GitHub ↔ ModelScope ↔ Release）

**项目维护铁律**：本地项目目录、GitHub 仓库（Golden2002/PAEG）、ModelScope（Golden2002/Emile_Novis）、Release 四者内容必须完全一致、互为备份。

### 双远程同步（v0.67 ⭐）

```bash
# 日常：一次 commit 推两个仓库
git add .
git commit -m "改动"
git push origin master        # GitHub
git push modelscope master    # ModelScope

# 或一键推送（已配别名）
git pushall
```

> 拉取建议只从 GitHub（`git pull origin master`），避免两仓分歧。

### 校验脚本

```powershell
$env:GH_TOKEN='<你的token>'
python D:\桌面\智能体架构与开发（含大模型）_教育者Agent项目\sync_check.py        # 只读校验
python D:\桌面\智能体架构与开发（含大模型）_教育者Agent项目\sync_check.py --fix  # 自动推送差异（本地为权威）
```

### 原则
1. **本地为权威源**：任何修改先在本地完成并验证
2. **每次变更后同步**：改完代码/文档 → 跑 sync_check.py --fix 推送 GitHub
3. **Release 保持最新**：重大版本更新时更新 Release 名称与正文（tag 可复用 v0.26）
4. **敏感数据不上传**：users.json / users_data/ / uploads/ / data/ 等运行时数据不参与备份
5. **token 不入库**：脚本从环境变量 GH_TOKEN 读取，禁止硬编码密钥

### 完成状态
- 2026-08-08：106 个代码/文档文件全部一致（0 缺失 0 差异），Release v0.34 为最新

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python + Flask（47+ API 路由）+ module_registry 模块门控 |
| LLM | DeepSeek（云端推理，agent 指挥 LLM） |
| 前端 | 原生 HTML/CSS/JS（无框架）+ KaTeX 数学渲染 + marked Markdown |
| 语音 | v0.36 ⭐：edge-tts（TTS 免key）+ 浏览器 Web Speech API（STT） |
| 工具 | 7 内置工具 + 10 Skills + 3 MCP（filesystem/memory/pptx） |
| 存储 | JSON 文件落盘（users_data/ + data/ + Library/） |
| 部署 | 本地 :5000 + cloudflared 隧道公网 |

## 语音模块（v0.36 ⭐）

- **TTS（朗读回答）**：edge-tts（免费，中文女声 zh-CN-XiaoxiaoNeural），后端 /api/voice/tts 生成 MP3
- **STT（语音提问）**：浏览器 Web Speech API（Chrome/Edge/Safari），转文本后复用现有发送管线
- 模块门控：paeg_modules.json 可开关；纯 I/O adapter，不进 subagent 调度
- v2 规划：讯飞/微软/Azure 替换 provider（接口已抽象在 voice_service.py）

### 环境限制（真实可用边界）

- **STT 语音输入**：依赖浏览器 `webkitSpeechRecognition`（Chrome/Edge/Safari 桌面版）+ HTTPS 或 localhost 安全环境。微信内置浏览器（X5 内核）与非 HTTPS 局域网 IP 访问**不支持**——此时麦克风按钮会明确提示原因，可直接打字交流。
- **TTS 朗读**：需后端已安装 `edge-tts`（`pip install edge-tts`）；播放可能被浏览器自动播放策略拦截（点一次页面任意处再点 🔊 即可）。

## 检索徽章（v0.27 + v0.36.1）

回答前显示"已完成知识库检索 / 网络检索"徽章：知识库有该概念 → 知识库检索；知识库无匹配（如偏门/自创概念）→ **自动联网补充**并显示"网络检索"。推荐类问题（"推荐几本书"）始终真联网。

---

## 架构与维护（v0.41 ⭐）

> 本节是 PAEG 工程化层面的总览——项目目录怎么组织、怎么检视健康度、下一步往哪里走。面向**接手维护者**和**未来想二次开发**的读者。

### 目录结构

```
05_实现原型/
├── server.py              # 入口薄壳（app factory + 蓝图注册）
├── config/                # 配置层（settings / secrets / env loader）
├── utils/                 # 纯函数工具（text / json / time）
├── services/              # 业务服务（tts / user / llm — Phase 2 拆分中）
├── blueprints/            # HTTP 蓝图（api / admin / voice — Phase 3 规划）
├── agents/                # subagent 实现（planner / presenter / evaluator）
├── infra/                 # 基础设施（db / cache / file_lock / audit）
├── subagents.py           # 子代理注册 + 调度
├── voice_service.py       # TTS/STT 接口抽象（v0.36+）
├── reflection_store.py    # 反思日志持久化
├── prompt_loader.py       # 提示词模板加载
├── paeg_modules.json      # 模块门控配置
└── tests/                 # 镜像结构测试
```

**关键文件**：
- `config/`：所有配置集中，secrets 从环境变量读取（无硬编码密钥）
- `subagents.py`：9 个子代理的注册与调度（v0.25+）
- `voice_service.py`：TTS/STT provider 抽象（v0.36，edge-tts 默认）
- `reflection_store.py`：自我进化反思日志（v0.30+）
- `paeg_modules.json`：模块开关门控（运行时动态启用/禁用）

### 检视命令（每次改动前后必跑）

```powershell
# 1. 静态检视（P0/P1 必须全过）
python audit_check.py

# 2. 端点冒烟（27 秒内验证关键 API）
python smoke_test.py

# 3. 全量回归（pytest 必须全绿）
python -m pytest tests/ -q

# 4. 三处一致（本地 ↔ GitHub ↔ Release）
python sync_check.py --fix

# 5. 架构连通性（每季度跑一次）
python arch_check.py
```

**检视铁律**：
- 改核心链路（server.py / subagents.py / prompts.py）后**至少**跑 smoke_test + pytest
- 发版前必须 5 个命令全过
- 任何 `bare except: pass` 会被 audit_check 抓住（P0）
- 任何写端点缺 `_is_registered` 校验会被抓住（P0）

### 优化方向（v0.41+ 演进路线）

PAEG 不止"功能完整"，更要"结构优秀"。参考 Flask / Kraken / EAS Station / llama-index / langchain 六个成熟项目的结构做渐进拆分：

| Phase | 内容 | 状态 | 触发条件 |
|---|---|---|---|
| Phase 1 | `config/` + `utils/` 拆分 | ✅ 完成 | server.py > 4000 行 |
| Phase 2 | `infra/`（12 单例 + SESSIONS）+ `services/`（learner_session/polish/steering/routing/handlers） | ✅ 完成 | LLM 调用跨层耦合 |
| Phase 3 | `blueprints/` 拆分 | 📋 规划 | HTTP 路由难以独立维护 |
| Phase 4 | `agents/` 独立单元 | 📋 规划 | subagent 行为难观测 |

**拆分铁律**：
1. **行为不变性**：拆分前后 API 响应字节级一致（回归测试做安全网）
2. **Expand-Migrate-Contract**：扩展→迁移→收缩三阶段，每步可回滚
3. **ratchet**：拆分只前进不后退，已迁移禁止回旧模块

### 进一步阅读

- 详细技术全景：[《PAEG技术全景文档》§10.2.21 成熟项目可借鉴结构](./PAEG技术全景文档.md)
- 维护操作流程：[《维护手册》§六 成熟项目结构借鉴](./维护手册.md)
- 元能力沉淀：[《元能力文档》§6.15 成熟项目结构借鉴元技术](./元能力文档.md)
- 投资人视角亮点：[《亮点总览》§六 架构可维护性](./亮点总览.md)

## 最近变更（v0.41.6）

- **提示词结构化**：前端模式选择（闲聊/找答案/学习方法/知识库/倾诉）作为确定性信号传入后端 → 模式短路路由（LLM 不必重复判断意图）→ 规则兜底 → 语言规范。详见 [CHANGELOG](./CHANGELOG.md) v0.41.6。
- **展示质量自检**：LLM 英文枚举→中文映射（visual→视觉型），audit_check 新增展示质量维度，24/24 全绿。
- **数据双源一致**：注册即对齐 users.json 与画像文件，杜绝昵称占位符漂移。
- **模块化落地**：server.py 4556→~4000 行（infra/ + services/ 五模块），行为零变化。

详细变更记录见 [CHANGELOG.md](./CHANGELOG.md)。
## RALPH 循环能力（v0.69+）
PAEG 具备**任务驱动的自我驱动循环**：围绕改进任务做"执行→验证→承诺→续触发"迭代直到达标，三层完成判定 + 五道反教条防呆防线（轮次上限/收益递减/质量回退/人类确认/资源熔断）。
## 数学可视化视频脚本生成（v0.70+）
PAEG 可生成**高质量数学可视化视频**：对话+轮询收集需求 → 生成动画脚本（script.json，遵循 3Blue1Brown 方法论）→ 渲染 Manim 动画 → 同步产出讲稿/PPT/讲义/思维导图（全部可下载）。
## 教学物料包 workflow（v0.70+）
`teach_materials` 工作流：一个主题 → 自动产出 6 类教学物料（知识导图/讲义/PPT/讲稿/视频脚本/数学动画）→ 打包为资产供下载。DAG 并行执行，物料间自动衔接。

## 语言规范 MCP 标准化（v0.70+ · §3.28）
语言规范从"散落的函数调用"升级为**统一入口 + 外部数据 + 标准工具**的插件服务：13 处 `_polish_text` 收敛为 `lang_gate_content` 统一守门；违禁词数据化 `forbidden_words.json`（可动态维护不改代码）；MCP 三工具 `normalize_text`（生成内容统一过语言规范）/ `language_policy_check`（AI 味+违禁词零成本检测）/ `forbidden_words`（list/add/remove）。外部 agent 也能调用 PAEG 的语言规范能力。

## L0-L8 约束引擎 MCP 化（v0.70+ · §3.29）
L0-L8 分层约束升级为 **6 API 约束引擎**：`layer_get`（读层放开组）/ `layer_set`（动态切换教学/考试/自由层）/ `compose`（任意提示词块拼接）/ `always_active`（永远激活，不随层放开）/ `self_evolve`（教学洞察自动提炼入层，数据化落盘）/ `feedback_adjust`（"太啰嗦→放宽节奏、太深→收紧深度"信号映射）。约束系统可治理、自演进、反馈调强。

## 学段教学模式差异化（v0.71+ · §3.33）
同一个知识点，初中/高中/大学/考研讲出**本质不同**的结构与深度：初中"感官优先·三步可视化"（现象→画面→类比→复述）、高中"结构优先·五步走"（定义→公式→例题→误区→知识结构图）、大学"正式 lecture·五步论证"（严格定义→定理→推导→应用→学科视野）、考研"考点解剖·五步得分"（考什么→怎么考→套路→真题→易错点）。`GRADE_SCAFFOLDS` 可执行段序列骨架 + 内容深度量化（长度/形式约束）双落实。

## sub agent 模型配置化（v0.71+ · §3.32）
像 Oh My OpenCode 一样，`config/agents.json` JSON 配置即可为每个 sub agent 分配不同模型（provider/model/temperature/max_tokens/thinking_level）：三层合并（默认→用户~/.paeg→项目）+ `{env:}/{file:}` 变量替换——用户不改代码定制 PAEG 的 10 个 sub agent。
