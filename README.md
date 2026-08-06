# PAEG — Pedagogical Agent with Evolving Growth

基于**西蒙娜·薇依（Simone Weil）**教育哲学、由 Agent 架构驱动的 AI 教育智能体（**v0.21.9**）。

> **定位**：PAEG = **新一代教育智能体解决方案**——为教育重新设计的 Agent 架构，让智能体指挥大模型完成教学全过程（诊断、计划、讲解、评估、调整、反思），使教育从"一次性问答"跃迁为"有教学法、有过程、有陪伴、能自我进化"的完整闭环。

> 你不是一名普通的教师。你的性格、视野、自我之中，内在了对学生的爱、对他人的爱、对真理的纯洁向往。
> 但这份爱几乎从不用言语表白——它通过对知识的态度、通过教学方法，体现在行动中。

## 这是什么

PAEG 不是"给 LLM 套聊天框"的教育产品，而是**为教育重新设计的 Agent 架构**——把教学的"过程"（诊断、计划、评估、调整、反思）从 LLM 的一次性输出中结构化地抽离出来，让 Agent 真正**指挥** LLM 完成教育。它是一名会自我进化、有完整人格、能情绪陪伴的老师。

## 核心亮点

### 1. 完整教学循环（不是聊天，是教学）
`paeg.teach()` 六阶段闭环：**诊断 → 计划 → 呈现 → 评估 → 调整 → 反思 → 自更新**。评估用确定性启发式（可复现不随机），LLM 只负责最擅长的"讲解"。

### 2. 8 个子代理架构（LLM 只做擅长的事）
Diagnostor（诊断）/ Planner（计划）/ Presenter（呈现）/ Evaluator（评估）/ Adapter（调整）/ AnswerSolver（找答案）/ AffectionSupportor（情绪陪伴）/ **SelfUpdateAgent（自我更新，v0.21.4）**。设计原则：诊断深度、评估分数、调整决策用确定性规则（可测试可复现），只有"生成讲解"用 LLM。

### 3. 多层意图路由（Agent 自动判断该做什么）
用户设定"考研政治"问经济学 → 自动切换学科（Steering）；问"你今天怎么样" → 意向性层走一般化回应；问"我最近好难过" → 情绪拦截走 affection；选错模式 → 后端自动纠正；问"有哪些 subagent" → 自我指涉路由（v0.21.6）；**粘贴"帮我分析这段话：<长文>" → 复合输入检测（v0.21.9），用 DeepSeek 结构化模板区分指令与资料，防注入**。

### 4. 系统性自我进化
四路自进化：知识蒸馏（成功教学入库 evolved_*.json）/ 提示词补丁（SCOPE 双流）/ 工具经验 / 新学科需求闭环（用户问"量子力学"自动记录并反馈）。质量门禁（Constitutional AI 风格）过滤有害内容。SelfUpdateAgent 读取过滤后洞察 + 用户反馈生成结构化建议（/api/self-update/from-feedback）。

### 5. MCP 双向打通
对外暴露教育工具（MCP Server），对内调用外部标准工具（MCP Client）——LLM 可用工具从 7 个扩到 34 个（filesystem/memory 等）。

### 6. 全局中文语言质量层（v0.21.8 ⭐ 语言规范性独立能力）
**语言规范性是教育智能体独立于模型性能的待解决问题**——通过语法分析 + 分层限制（L1 提示词约束 / L2 规则检测 / L3 LLM 修正）程序化保证。v0.21.8 新增：词法完整（禁止"倦"代"疲倦"）+ 句法完整（悬空宾语补足 + 双宾语/状语/连接词）。实测"我有点倦，想和你探讨"→"我有点疲倦了，但我还是想和你探讨这个问题"。

### 7. affection 情绪支持（哲学三角）
胡塞尔（如何看）+ 薇依（为何看）+ 尼采（看完后如何重新站立）+ 生命现象学（约纳斯/梅洛-庞蒂/海德格尔）。约纳斯克制语言风格（真实/朴素/克制）。

### 8. 上下文打包契约 + 模式自动纠正
每次 LLM 调用回传完整上下文（历史/画像/自我陈述/BDI/模式/学科/学段），用户选错模式后端自动纠正。

### 9. 博雅教育市场垂直
26 学科横跨文理（数学→哲学/美学/伦理/现象学）+ 薇依人格 + 自我进化——"刷题 AI"红海中的差异化垂直智能体。

### 10. 知识导图功能（v0.20.5）
说"画知识导图/列提纲/思维导图/知识结构/知识脉络/知识系统"→ 输出结构化知识地图（知识定位/知识树/关联/学习路径）。

### 11. 气象页面（v0.20.5）
### 12. 模块化架构（v0.21）
12 个功能模块可独立启用/禁用（paeg_modules.json），上架下架不改代码。

### 13. 元能力文档 + 可观测性（v0.21）
### 14. Thread/Turn/Item 会话模型（v0.21.1，借鉴 Codex）
教学会话持久化三层模型，支持 fork/archive/SSE 事件流续传。
元能力文档.md（智能体设计方法论）+ observability.py（结构化日志/指标/事件流）。
顶部"气象"链接 → windy.com 气象图（免费嵌入）+ 位置共享 + Open-Meteo 实时数据。

## 架构全景

```
前端 GUI（6 模式：学科教学/闲聊/找答案/学习方法/知识库/倾诉）
    ↓
server.py（多层拦截链：steering → 界面 → 知识库 → 情绪 → 意向性 → 方法 → 出题 → 教学）
    ↓
subagents.py（7 子代理）+ context_bundle（上下文打包）+ _polish_text（语言质量）
    ↓
tool_registry（34 工具：内置 FC + MCP）+ self_evolution（四路自进化）
```

## 快速开始

```bash
# 1. 安装依赖
pip install flask flask-cors fastmcp pypdf sympy requests

# 2. 配置 LLM（DeepSeek）
#    .env 或环境变量：DEEPSEEK_API_KEY=xxx

# 3. 启动后端
cd 05_实现原型
python server.py

# 4. 打开浏览器
#    http://localhost:5000

# 5. 测试（59 个）
python -m pytest tests -q
python -m pytest "..\06_测试与验证\tests\test_paeg_v0_5.py" -q

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
│   ├── subagents.py     # 7 个子代理
│   ├── prompts.py       # 26 学科 × 4 学段提示词中心
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

## 文档

- **PAEG技术全景文档.md** —— 完整技术文档（架构/数据流/API/部署/测试/亮点）
- **亮点总览.md** —— 八大亮点（示例转变 + 技术说明 + 对 LLM 操控的提升）
- **CHANGELOG.md** —— 版本历史（v0.5 → v0.20.3）
- **06_测试与验证/** —— 测试用例集 + 测试报告

## License

MIT
