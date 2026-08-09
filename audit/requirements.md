# PAEG 架构审计需求表（v0.36 ⭐）

> 审计日期：2026-08-09。基于多维审计（文档契约 vs 实现、死代码扫描、前后端联通检查）。
> 目标：像高楼大厦的砖块瓦块——每个模块整洁、可查、可替换。**每项完成 = 有可验证标准**。

## 需求表

| ID | 类别 | 文档承诺 | 代码现状 | 修复动作 | 验证标准 | 工作量 |
|---|---|---|---|---|---|---|
| P0-01 | 缺失功能 | pptx_mcp_server.py PPT 生成 MCP | 文件不存在 | 实现 MCP server + python-pptx 生成 | 有效请求生成可读 .pptx；无效请求安全失败 | L |
| P0-02 | 缺失功能 | /api/subject-tree 三级联动 | 路由不存在 | 实现 5 学段×学科×subfield 端点 | 返回 5 学段含学科/subfield；前端三级下拉可用 | M |
| P0-03 | 缺失功能 | /api/avatar 头像上传 | 路由不存在 | 实现安全上传（MIME/大小/路径校验） | 合法上传成功；非法/越权失败 | M |
| P0-04 | 缺失功能 | /api/resources 查资料聚合 | 路由不存在 | 实现知识库+Library+web 聚合 | 返回规范化资源；单源失败不拖垮 | L |
| P0-01 ✅ | 已存在 | pptx_mcp_server | v0.25 完整实现+端到端通过 | 无需改 | MCP 24 工具含 pptx | 完成 |
| P0-05 | 未接线 | weekly_insight_update 周度洞察 | 实现但 0 调用 | 接入周期调度器 | evolve_data/insights.json 生成 | S |
| P0-06 | 未接线 | analyze_failures 失败分析 | 实现但 0 调用 | 注册到周期管线 | 失败样例产生分析输出 | S |
| P0-07 | 未接线 | PeriodicSelfUpdater 周期调度 | 实例化未 start | app.run 前 start() | 三个任务可观察；无重复线程 | S |
| P0-08 | 未接线 | ContextBundle 6 端点注入 | 4 函数 0 调用 | 接线到 6 端点 | 注入断言通过 | M |
| P1-01 | 联通缺口 | 8 个 SSE 教学进度事件 | 后端发前端忽略 | 前端消费 diagnosis/plan/step 等 | 思考提示按阶段更新 | M |
| P1-02 | 联通缺口 | 18 个路由前端未调 | 意图不清 | 分类：连接/保留/废弃/删除 | 每个路由有处置记录 | M |
| P1-03 | 联通缺口 | API 表陈旧（25 vs 41） | 文档滞后 | 更新 §4.2 | 文档=代码 | S |
| P2-01 | 结构整洁 | 自我进化 4 文件职责重叠 | 边界不清 | 梳理唯一拥有者 | 职责矩阵；无重复调度 | L |
| P2-02 | 结构整洁 | "9 subagent" 声明夸大 | paeg 持 5 个 | 统一持有或改文档 | 代码=文档 | M |

## 实施波次

- **Wave 1（P0 缺失功能）**：pptx → subject-tree → avatar → resources（解锁前端已有 UI）
- **Wave 2（P0 未接线）**：PeriodicSelfUpdater.start → ContextBundle（激活休眠机制）
- **Wave 3（P1 联通）**：SSE 消费 → 孤儿路由分类
- **Wave 4（P2 整洁）**：自我进化梳理 → subagent 统一 → 文档更新
| P2-03 | 死代码 | 12 个全死 .py 文件 | agent_core/agent_engine/mcp_gateway/expert_guard/observability/memory_system/ai_taste_detector/api_sweep/eval_harness/knowledge_map/llm_enhanced_presenter 等 | 删除（约 2900 行） | 删除后全测试过 | L |
| P2-04 | 装饰性 subagent | Diagnostor/Planner/Evaluator 不在主线 | 仅在 fixture/import | 接入 PAEG 主线或删除（700 行） | 教学仍工作 | L |
| P2-05 | 文档-代码不一致 | module_registry 注释声明 MODULES/register_module | 实际不存在 | 修正注释 | 注释=实际 | S |
| P2-06 | 工具调用不可观测 | 7 工具被调用但前端不渲染 | 只有 web_searched 布尔 | 前端渲染工具列表（tool_calls） | 前端显示调用轨迹 | M |
| P2-07 | 孤儿配置文件 | users.json.bak 等 | dev 残留 | 清理 | 仓库干净 | S |

## 死代码审计补充（2026-08-09 第二轮）

- **SSE 16 种事件未消费**：diagnosis/plan/step/evaluation/adjustment/reflection/self_update/self_evolution/prompt_evolved/user_modeling 等前端全忽略 → P1-01 已列，升级为 P0
- **17 个孤儿路由**：/api/batch、/api/threads/*、/api/solve、/api/self-update/*、/api/skills 等前端未调 → P1-02 细化
- **可清理量**：约 6000-7500 行（后端 5500 + dev 测试 1000+）

## 主项目核实修正（2026-08-09 第三轮）

> 文档审计基于旧副本导致误报。用主项目核实后修正：

| 原审计项 | 主项目核实 | 修正 |
|---|---|---|
| P0-02 /api/subject-tree 缺失 | ✅ 已存在（L628，v0.26，契约匹配） | 完成（无需改） |
| P0-03 /api/avatar 缺失 | ✅ 已存在（L2038，v0.26） | 修复 ok:false bug，完成 |
| P0-07 PeriodicSelfUpdater 未 start | ✅ 已 start（L4205，app.run 前） | 完成（无需改） |

**真实待办**（排除误报后）：
- P0-01 pptx_mcp_server（实现中）
- P0-08 ContextBundle 0 调用（真未接线）
- P0-05 weekly_insight_update 0 调用（真未接线）
- P0-06 analyze_failures 0 调用（真未接线）
- P1/P2：SSE 事件消费、孤儿路由、死代码清理等

**教训**：审计必须以主项目为准（wbo 下 paeg_link/paeg_project 是 junction 指向主项目，paeg_work 是废弃旧版——若审计基于 paeg_work 会大量误报）。


## 已完成状态

（按实施进度更新）
