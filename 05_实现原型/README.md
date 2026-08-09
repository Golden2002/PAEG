# PAEG v0.5 可成熟使用原型

> 版本：v0.5（真实 LLM 接入 + 55 节点知识库 + 交互 CLI + 安全中间件 + 持久化）
> 迭代基线：v0.1（物化测试）→ v0.2/v0.3（历史遗留）→ v0.5（本版）
> 范围：G3（学科教学）+ G4（技能教学）+ G5（人文素养）+ G8（考研适配）+ G9（元认知可观测）

---

## 1. 文件结构

```
05_实现原型/
├── README.md                  (本文件)
├── paeg.py                    (主类：诊断→计划→呈现→评估→调整→反思→自我更新)
├── knowledge_base.py          (55 节点：33 学科 + 12 素养 + 5 策略 + 5 案例)
├── subagents.py               (5 子代理：真实 LLM 接入 + 确定性评估)
├── world_view.py              (13+ 主题 × 4 种世界观的自动切换)
├── self_update.py             (JSON 持久化：reflections/strategies/profiles + 版本回滚)
├── llm_api.py                 (ModelAPI：OpenAI 兼容 / Anthropic / Mock + 自动发现凭据)
├── llm_adapter.py             (旧接口兼容层：create_llm + generate/chat 双接口)
├── safety.py                  (安全中间件：政治/宗教传教/医疗/法律/自伤/作弊等 10 类)
├── cli.py                     (交互式教学 CLI)
├── server.py                  (Flask API：同步/流式教学 + 画像 + 元认知日志)
├── llm_enhanced_presenter.py  (LLM 增强呈现工具)
├── test_demo.py               (5 学科离线 demo)
├── test_demo_real_llm.py      (真实 LLM demo：physics/ethics/kaoyan_math)
├── tests/                     (6 个测试文件，27 个用例)
├── data/                      (持久化：profiles/reflections/strategies + versions 快照)
└── intermediate_v05_demo.txt  (真实 LLM demo 运行记录)
```

---

## 2. 快速开始

### 2.1 交互式教学 CLI（推荐）

```bash
cd 14_教育者Agent项目/05_实现原型/
python cli.py              # 自动模式：优先真实 LLM（自动发现 opencode/环境变量凭据）
python cli.py --mock       # 强制离线 Mock（无网络时）
python cli.py --subject physics --question "什么是熵？"   # 单轮直跑
```

### 2.2 真实 LLM 教学 Demo

```bash
python test_demo_real_llm.py --provider auto   # 3 学科（物理/伦理/考研数学）
python test_demo_real_llm.py --provider mock   # 离线
```

### 2.3 后端 API（GUI 联通）

```bash
python server.py
# http://localhost:5000/                    GUI 首页
# http://localhost:5000/api/health          健康检查
# POST /api/teach                           {"nickname":"小李","concept":"什么是熵？","subject":"physics"}
# GET  /api/profile/<learner_id>            学习者画像
# GET  /api/meta-log/<learner_id>           元认知日志
```

### 2.4 运行测试

```bash
cd tests/
python test_diagnostor.py && python test_presenter.py && python test_worldview.py `
  && python test_self_update.py && python test_integration.py && python test_safety.py
# 27/27 通过
```

---

## 3. 核心设计

### 3.1 教学循环（六步）

`诊断 → 计划 → 呈现(多步) → 评估 → 调整 → 反思+自我更新`

- **诊断**：知识库前置知识 + LLM 深度/缺口分析（LLM 判断失败自动回退规则）
- **呈现**：真实 LLM 基于知识库事实 + 世界观语气生成 100-300 字讲解；离线回退规则模板
- **评估**：确定性启发式（长度 + 结构关键词 + 语气契合 + 知识库依据），无随机
- **调整**：score<0.6 换风格 / <0.7 强化 / 否则继续
- **自我更新**：EMA(α=0.3) 更新学科掌握度 + 策略提炼 + JSON 原子落盘 + 版本快照回滚

### 3.2 世界观（4 种语气自动切换）

| 学科域 | 语气 | 世界观比例(1-4) |
|---|---|---|
| physics/math/logic/cs | rigorous_cold | 5/70/10/15 |
| literature/aesthetics/phenomenology | contemplative | 20/10/60/10 |
| ethics/relationship/character | warm_caring | 50/20/20/10 |
| career/skill/application | pragmatic | 10/20/10/60 |
| default | balanced | 20/35/35/10 |

### 3.3 安全中间件（Layer 0 宪法）

10 类拦截：政治立场 / 宗教传教 / 医疗建议 / 法律建议 / 投资建议 / 自伤 / 暴力仇恨 / 成人内容 / 考试作弊 / 个人信息。命中返回"为什么不能聊 + 可以怎样学"重定向引导。

### 3.4 LLM 自动发现（优先级）

`PAEG_API_KEY` > `DEEPSEEK_API_KEY` > `ANTHROPIC_API_KEY` > `OPENAI_API_KEY` > `opencode auth.json(deepseek)` > Mock 兜底

---

## 4. v0.5 实测证据

| 项目 | 结果 |
|---|---|
| 单元/集成测试 | 27/27 通过 |
| 真实 LLM 教学（physics） | 3 步，avg 0.950，rigorous_cold |
| 真实 LLM 教学（ethics） | 3 步，avg 0.933，warm_caring |
| 真实 LLM 教学（kaoyan_math） | 3 步，avg 0.950 |
| API /api/teach | 真实 LLM 内容 + 画像 EMA 落盘 |
| 安全拦截 | 6/6 典型用例正确 |
| 知识库 | 55 节点（33 学科 + 12 素养 + 5 策略 + 5 案例） |

详见 `intermediate_v05_demo.txt` 与 `06_测试与验证/`。

---

## 5. 已知局限与下一步

- **无云端同步**：数据仅本地 data/ 目录
- **无 LoRA 微调**：v1.0 规划
- **评估为启发式**：未用 LLM 评卷（可设 PAEG_LLM_EVALUATE=1 扩展）
- **无教师/家长模式**：v1.5 规划
- **v0.8**：Layer 0 宪法完整化 + Voyager 不可变库 + 情感感知
- **v1.0**：FastAPI + WebSocket 流式 + 知识图谱可视化