# PAEG v0.41.7 专项需求表（完善度/稳定性/模块化/结构优化）

> 来源：v0.41.6 发布复盘 + Oracle 架构咨询 + 用户指示（"提升项目的完善程度、稳定性、模块化程度，保证优良的结构"）
> 目标：在 v0.41.6（提示词结构化 + 模式短路 + 模块化落地）基础上，补齐遗留缺口、根治稳定性隐患、深化模块化
> 状态：⏳ 待 Oracle 复盘建议融合

---

## 一、v0.41.6 复盘结论

### 做得好的
1. **模块化落地**：server.py 4556→3977 行（-579 行），infra/（12 单例）+ services/（5 模块），audit 24/24 行为零变化
2. **提示词结构化**：前端 mode → 短路路由 → LLM 判断 → 规则兜底 → 语言规范，端到端验证全对
3. **数据双源一致**：注册即对齐 + audit 常驻三方检查（u106/u8 已修复）

### 遗留缺口（本轮专项）
| # | 缺口 | 现状 | 影响 |
|---|---|---|---|
| 1 | **SESSIONS 缓存重建覆盖画像** | ensure_learner_session 重建时用默认值"学生"，曾覆盖 u106 画像 | 用户画像偶发回退默认值 |
| 2 | **4 个 handler 未迁移** | _handle_recommend/knowledge/method/problem 定义仍在 server.py（L3296/3360/3465/3679） | server.py 仍含大量业务逻辑 |
| 3 | **INTERFACE_GUIDE 缺 4 桶** | voice/ppt/weather/composite 无确定性模板 | 问"麦克风按钮干嘛用"答非所问 |
| 4 | **blueprints/ 未拆分（Phase 3）** | 45 路由仍在 server.py | 路由维护仍集中 |
| 5 | **agents/ 未导出（Phase 4）** | subagent 类在 subagents.py，未做 agents/ 重新导出 | 结构层级不完整 |
| 6 | **早退分支注释/死代码** | keyword_doc 已清一处死代码；其他分支可能仍有 | 维护困惑 |

---

## 二、下一轮专项需求清单（按优先级）

### P0 · 稳定性（本轮核心）
| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 1 | SESSIONS 画像重建根治 | 重建 learner 时从 users.json 加载真实昵称，不落盘默认值 | services/_learner_session.py 默认昵称逻辑 + login 持久画像 | 重启服务后 u106 画像仍为"团聚体" |
| 2 | 并发写保护审查 | 确认 _SAVE_LOCK/写锁覆盖所有持久化路径 | self_update.py + user_store.py 写点审计 | audit_check 新增"写锁覆盖"维度 |

### P1 · 模块化深化
| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 3 | 迁移剩余 4 个 handler | server.py 业务逻辑继续瘦身 | recommend/knowledge/method/problem → services/handlers/ | server.py < 3800 行 |
| 4 | Phase 3 blueprints 低风险拆分 | 先拆小蓝图（ui/health/auth/skills/file_gen/voice） | blueprints/ 包 + 注册 | 45 路由不破坏，audit 24/24 |
| 5 | Phase 4 agents/ 导出 | subagents.py 类在 agents/ 重新导出 | agents/__init__.py | from agents import Presenter 可用 |

### P1 · 完善度
| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 6 | INTERFACE_GUIDE 补 4 桶 | 语音/PPT/气象/复合输入有确定性说明 | self_referential.py | 问"麦克风干嘛用"返回正确说明 |
| 7 | 代码注释/死代码清理 | 消除陈旧注释与不可达代码 | server.py 早退分支 + 死代码扫描 | grep 无"9 个早退分支"等陈旧注释 |

### P2 · 自检增强
| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 8 | audit 新增"模块化健康"维度 | infra/services 引用规则、无循环 import、server.py 行数上限 | audit_check.py | server.py < 4000 行即通过 |
| 9 | audit 新增"接口文档同步"维度 | API 契约文档与路由匹配 | audit_check.py | 45 路由都有文档 |

---

## 三、明确不做（低收益高风险）
| 项 | 原因 |
|---|---|
| teach.py/chat.py 蓝图拆分 | 含 SSE 闭包 + 30+ 依赖，风险极高收益有限（Phase 3 最后做或不做） |
| index.html ES 模块拆分 | 需引入构建工具，破坏单文件部署简单性 |
| JWT 认证 | 单机/局域网使用场景，learner_id 信任制足够（用户量 > 50 再触发） |
| subagents.py 2600 行拆分 | 8 个子代理类已职责清晰，拆文件无实质收益 |

---

*本表由 Sisyphus 于 v0.41.6 发布后整理，待 Oracle 复盘建议融合后定稿。*
