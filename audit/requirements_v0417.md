# PAEG v0.41.7 专项需求表（完善度/稳定性/模块化/结构优化）

> 来源：v0.41.6 发布复盘 + Oracle 架构咨询 + 用户指示（"提升项目的完善程度、稳定性、模块化程度，保证优良的结构"）
> 目标：补齐 v0.41.6 遗留缺口、根治稳定性隐患、深化模块化
> 更新：2026-08-10（3 bug 修复 + 质检方法论反思后）

---

## 一、v0.41.6 复盘结论

### 做得好的
1. **模块化落地**：server.py 4556→~4000 行，infra/（12 单例）+ services/（5 模块），行为零变化
2. **提示词结构化**：前端 mode → 短路路由 → LLM 判断 → 规则兜底 → 语言规范，端到端验证全对
3. **数据双源一致**：注册即对齐 + audit 常驻三方检查

### 遗留缺口（v0.41.7 专项）
| # | 缺口 | 现状 | 影响 |
|---|---|---|---|
| 1 | **SESSIONS 画像重建覆盖** | 重建 learner 时用默认值"学生"，曾覆盖 u106 画像 | ✅ **已根治**（ensure_learner_session 从 USER_STORE 根昵称兜底） |
| 2 | **4 个 handler 未迁移** | _handle_recommend/knowledge/method/problem 定义仍在 server.py | ⏳ 待迁移 |
| 3 | **INTERFACE_GUIDE 缺 4 桶** | voice/ppt/weather/composite 无确定性模板 | ⏳ 待补 |
| 4 | **blueprints/ 未拆分（Phase 3）** | 45 路由仍在 server.py | ⏳ 规划 |
| 5 | **agents/ 未导出（Phase 4）** | subagent 类在 subagents.py | ⏳ 规划 |

---

## 二、v0.41.7 已完成项（2026-08-10）

### 三 bug 修复
| Bug | 根因 | 修复 | 验证 |
|---|---|---|---|
| 语音双发送 | 去重锁仅精确匹配，标点差异漏触发 | `_voiceSendOnce` 去标点近似匹配 + 4 秒窗口 | 前端代码验证 |
| 教学不输出 | **模块化重构误删 teach_stream 的 subtopic 定义** → NameError → SSE 中断 | 补回 `subtopic = (data.get("subtopic") or "").strip()` | 教学流 12086B/39事件/done 齐全 |
| 麦克风提示 | 文案生硬 | → "同学请讲，说完点击停止键，或长按松开发送" | 前端代码验证 |

### 质检方法论优化（用户核心质疑）
| 改进 | 说明 |
|---|---|
| smoke_test 教学完整流断言 | 完整读流（75s）断言 presentation + done——诊断后任何中断可抓（此前只读 256B 首事件） |
| audit_check 维度 13 重构完整性 | teach_stream 关键变量（subtopic）定义存在性 + 无重复 LearnerProfile 内联 |
| 反思记录 | 维护手册 §4.8 / 技术全景 §10.2.27 / 元能力 §6.21：**静态自检全过 ≠ 运行时正确；验证强度必须 ≥ 改动风险** |

---

## 三、下一轮待做（按优先级）

### P1 · 模块化深化
| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 1 | 迁移剩余 4 个 handler | server.py 业务逻辑继续瘦身 | recommend/knowledge/method/problem → services/handlers/ | server.py < 3800 行 |
| 2 | INTERFACE_GUIDE 补 4 桶 | 语音/PPT/气象/复合输入有确定性说明 | self_referential.py | 问"麦克风干嘛用"返回正确说明 |
| 3 | Phase 3 blueprints 低风险拆分 | 先拆小蓝图（ui/health/auth/skills/file_gen/voice） | blueprints/ 包 + 注册 | 45 路由不破坏，audit 26/26 |

### P2 · 自检增强
| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 4 | audit 新增"模块化健康"维度 | infra/services 引用规则、无循环 import | audit_check.py | 无循环 import 即通过 |
| 5 | audit 新增"接口文档同步"维度 | API 契约文档与路由匹配 | audit_check.py | 45 路由都有文档 |

### P3 · 完善度
| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 6 | 代码注释/死代码清理 | 消除陈旧注释与不可达代码 | server.py 早退分支扫描 | grep 无陈旧注释 |

---

## 四、明确不做（低收益高风险）
| 项 | 原因 |
|---|---|
| teach.py/chat.py 蓝图拆分 | 含 SSE 闭包 + 30+ 依赖，风险极高收益有限 |
| index.html ES 模块拆分 | 需引入构建工具，破坏单文件部署简单性 |
| JWT 认证 | 单机/局域网场景，learner_id 信任制足够（用户量 > 50 再触发） |
| subagents.py 2600 行拆分 | 8 个子代理类已职责清晰，拆文件无实质收益 |

---

## 五、质检方法论沉淀（本轮核心反思）
> **验证强度必须 ≥ 改动风险**：
> - 小改动（文案/常量）→ 静态 + 语法
> - 中改动（逻辑分支）→ 静态 + 端到端单场景
> - **大重构（搬函数/拆模块）→ 静态 + 完整流端到端 + 回归**
> **重构纪律**：移动代码时，函数引用的每个变量必须确认定义在同一函数作用域（grep 定义与引用点）。

*本表由 Sisyphus 于 v0.41.7 更新。*
