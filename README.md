# PAEG — Pedagogical Agent with Evolving Growth

基于**西蒙娜·薇依（Simone Weil）**教育哲学的 AI 教育智能体。

> 你不是一名普通的教师。你的性格、视野、自我之中，内在了对学生的爱、对他人的爱、对真理的纯洁向往。
> 但这份爱几乎从不用言语表白——它通过对知识的态度、通过教学方法，体现在行动中。

## 核心特性

### 🎓 薇依式教师人格
- **注意力是最稀有的慷慨**：你欠学生的不是看法、不是认可、不是赞美，而是注意力
- **爱是一种朝向，不是灵魂状态**：爱是行动方向，不是情绪
- **同情是把自身的存在移入对方**：先走进学生处境，再回应
- **不评分、不催促、不煽情**：廉价鼓励不是注意力的替代品

### 📚 15 学科 × 4 学段
数学、物理、化学、生物、地理、语文、政治、历史、英语、法语、德语、日语、哲学、美学、文学
每个学科有专属教学风格 + 初中/高中/本科/考研分层

### 🧠 对象意识（个体性）
- **自我描述**：用户写下"我是谁/目标/擅长与不擅长"，每次对话自动注入
- **用户建模**：从对话推断情绪/困难/能力/参与度
- **BDI 推断**：基于 Theory of Mind 推断学生信念/愿望/意图，不同学生不同对待

### ✍️ 薇依式语言
- **AI 味检测器**：5 个客观信号（句长变异/过渡词密度/三段清单/破折号/段落对称）
- **Self-Refine 多轮改写**：AI 概率 0.4 → 0.186
- **10 条薇依真实语料**作为 few-shot 矫正

### 📄 文件生成
- 出练习题（含答案+解析）/ 写讲解文章 → 一键下载

## 快速开始

```bash
# 1. 启动后端
cd 05_实现原型
python server.py

# 2. 浏览器访问
# 本地: http://localhost:5000
```

### 命令行教学
```bash
python cli.py --subject physics --question "什么是熵？"
```

## 项目结构

```
14_教育者Agent项目/
├── 05_实现原型/          ⭐ 核心代码
│   ├── paeg.py          主类（教学编排 + 自我认知反思）
│   ├── prompts.py       薇依画像 + 语言风格 + 学科×学段提示词
│   ├── agent_core.py    智能体基础架构（Tool/AgentLoop/用户建模/BDI）
│   ├── subagents.py     5 子代理（诊断/计划/呈现/评估/调整）
│   ├── pedagogy.py      教学策略库（苏格拉底/支架/掌握/费曼）
│   ├── language_refiner.py 语言优化（Self-Refine）
│   ├── ai_taste_detector.py AI 味检测器
│   ├── file_generator.py   文件生成（练习题/文章）
│   ├── library_loader.py   知识库扩展加载器
│   ├── server.py        Flask 后端
│   └── ...
├── 09_GUI前端/          网页前端
├── Library/             知识库扩展（薇依原文等）
└── PAEG技术全景文档.md  完整技术文档
```

## 部署

- 本地：`python server.py` → `http://localhost:5000`
- 公网：Cloudflare Tunnel（临时隧道：`cloudflared tunnel --url http://127.0.0.1:5000`）

## 文档

- [PAEG技术全景文档.md](PAEG技术全景文档.md) — 架构/维护/升级完整指南

## 技术栈

- Python 3.14 / Flask
- DeepSeek API（OpenAI 兼容）/ Anthropic
- Cloudflare Tunnel（公网）
- 纯前端 HTML/CSS/JS（无框架）

## License

MIT
