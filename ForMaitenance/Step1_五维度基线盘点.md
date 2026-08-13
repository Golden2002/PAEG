# PAEG 五维度基线盘点（Step1）

> 整理日期：2026-08-14
> 用途：ULW Step1 基线——为 Step2 质量文档和 Step3 自检提供现状依据
> 状态：基线盘点（部分数据来自自我更新审查 + runoob 对照）

---

## 一、代码结构（模块化/多层级/参数化/可扩展/可维护）

### 模块清单（05_实现原型/）
| 层 | 模块 | 职责 |
|---|---|---|
| 入口 | server.py（56 路由）| Flask 入口：app factory 模式 + 蓝图注册（Phase3 规划）|
| 配置 | config.py | 配置层（环境变量/安全基线/LLM 选型/端口）|
| 配置中心 | config_hub.py | 统一配置（MCP/skills/hooks/workflows 四子模块）|
| 工具 | tool_registry.py | 7 内置工具 + 风险分级 + run_agent_loop |
| 工具 | mcp_client.py | MCP 客户端（25 工具，transport 复用）|
| 技能 | skill_registry.py | 多目录扫描（10 skills）|
| 钩子 | hooks_hub.py | waterfall+next/matcher/verdict 合并/timeout |
| 工作流 | workflows_hub.py | teach_minimal/teach_concept DAG |
| 智能体 | paeg.py | 教学主循环（六阶段）|
| 子代理 | subagents.py | 9 subagent + 深度思考矩阵 + 能力清单 |
| 意图 | meta_router.py | 15 意图 LLM 优先 + capability_hint |
| 上下文 | prompt_template.py | 固定块 + 动态槽 |
| 语言 | language_refiner.py | L1/L2/L3 语言规范 + 重复检测 |
| 自进化 | self_evolution.py | 4 路进化（蒸馏/补丁/工具/学科）|
| 记忆 | reflection_store.py / teaching_memory.py | 反思 SQLite + 教学记忆注入 |
| 知识 | knowledge_base.py / library_loader.py | 35 学科 KB + Library 扫描 |
| 检索 | web_search_tool.py | Brave MCP → Bing 降级栈 |
| 学习计划 | services/planner.py | StudyPlan 工作流 + 推荐附录 |

### 层级依赖（高层调低层，参数化）
```
server.py → config_hub → {mcp/skills/hooks/workflows} + tool_registry
         → paeg.py → subagents.py → config_hub.execute_tool
         → meta_router → LLM
```
**参数化模式**：run_agent_loop(model, system, tools=...) 把低层函数作为参数传入 ✅
**可扩展点**：config_hub 插件式 / skills 目录扫描 / hooks 注册 / workflows 声明式 ✅

## 二、功能完善（所有功能可实现）

- **6 模式**：teach/chat/answer/method/knowledge/affection
- **制作功能**：讲义/PPT/授课视频/数学动画/思维导图/深度思考（6 按钮）
- **学习计划**：planner.py（StudyPlan + 推荐资料附录）
- **工具链**：MCP 25 工具（filesystem/memory/pptx）+ 7 内置 + 10 skills
- **56 API 路由**（健康/画像/教学流/聊天/倾诉/知识库/上传/自进化）
- **自我更新**：4 路自进化 + 反思存储
- **评估测试**：132+ pytest / audit_check / smoke_test

## 三、实施质量（每种产出高品质）

- **语言规范层**：language_refiner L1/L2/L3（提示词约束/规则检测/LLM 修正）+ 重复检测
- **防幻觉**：TRUTH_GROUNDING（NEW-9 已注入 presenter/chat/_safe_chat）✅
- **教学深度**：college_physics 拆键 + method_guide + worked_example + 1500 字结构
- **测试**：132+ pytest + 语义压力测试 + LLM-as-judge（部分）
- **错误处理**：语义化日志（限流/超时/网络区分）+ 重试

## 四、智能性（steering + harness 下 LLM 能力释放）

- **意图路由**：meta_router 15 意图 LLM 优先 + 规则兜底 + capability_hint（意图→能力）
- **深度思考**：SUBAGENT_THINKING_LEVELS（A/B/OFF 分级）+ ReasonerModelAPI
- **能力自知**：_build_capability_manifest（能力清单注入 system）
- **工具主动调用**：Presenter 透传 tools（config_hub 42 工具）
- **教学法**：teach 六阶段 + 9 subagent 协作 + 个体化画像注入

## 五、其他维度（待构建）

- 见 Step2 质量文档（代码结构/功能/质量/智能性各自独立文档）
- 九模块底座对照（Step4）

---

## 六、与 runoob 标准对照的缺口（驱动 Step3 自检）

| 缺口 | 对应 runoob | 清单 ID |
|---|---|---|
| 上下文预算管理（System 10%/工具 20%/检索 25%/历史 30%）| 上下文工程 | NEW-2 |
| 历史分层摘要（近 3-5 轮完整，远期结构化）| 上下文工程 | NEW-2 |
| 上下文水印（策略版本/来源/消耗量）| 上下文工程 | NEW-2 |
| XML 标签隔离用户资料（防注入）| 提示词工程 | NEW-9 补充 |
| CoT 结构化（教学加 <thinking> 或显式分步）| 推理规划 | 智能性维度 |
| LLM-as-judge 四类产出评估 | 评估 | NEW-4 |
| 记忆分层模块（episodic/semantic）| 工作原理 | NEW-1 |
