# PAEG 架构优化需求清单（对照 DeepSeek Harness 经验）

> ⚠️ **本文件已于 2026-08-15 并入 `总需求与执行标准.md` 并作废（不再更新）**。
> 全部需求（P0/P1/P2、实施顺序、停手线）已迁移至该唯一需求文档的 §4（A-F 六域编号：P0-1→A1、P0-2→F3、P0-3→A5、P0-4→C1、P0-5→A6、P0-6→D5、P1-1→F6、P1-2→新增 F7、P1-3→C8、P1-4→B2、P1-5→F1、P1-6→F2、P1-7→A5、P1-8→F3、P2 系列→对应域）。
> 后续一切需求状态以 `总需求与执行标准.md` 为准；本文件仅作历史存档。

> 整理日期：2026-08-13
> 来源：Oracle 检视报告（对照 DeepSeek_Harness经验文档.md）
> 状态：待实施（已迁移，见上）

## 一、P0（影响生产，必须做）

| ID | 需求 | 借鉴来源 | 工作量 | 风险 | 收益 |
|---|---|---|---|---|---|
| P0-1 | **workflows_hub 落地**：基于 dsh plain-JS 五原语（agent/parallel/pipeline/phase/log），最小支持"诊断→呈现→评估"教学流水线 | dsh workflow | Medium (1-2d) | 中 | **极高**：教学闭环可声明化、可观测、可重放 |
| P0-2 | **mcp_client session 复用**：每次 call 不再起新 npx 进程 | dsh mcp | Short (1-4h) | 低 | 高：MCP 调用延迟 -80% |
| P0-3 | **hooks_hub emit/waterfall/parallel/serial 四 dispatch** | dsh hook-protocol | Short (1-4h) | 低 | 高：审计/广播事件不再污染钩子链 |
| P0-4 | **工具级 Permission Preset**（4 档：standard/code/minimal/cordis）| dsh preset+permission | Medium (1-2d) | 中 | 高：可"考试模式"锁定工具 |
| P0-5 | **hooks_hub matcher JS 表达式**（!!js）| dsh !!js | Short (1-4h) | 中 | 高：钩子能用任意条件 |
| P0-6 | **config_hub Patch Layer**（base+user+school 三层叠合）| dsh patches | Medium (1-2d) | 低 | 高：多学校/班级配置复用 |

## 二、P1（高价值，应做）

| ID | 需求 | 工作量 | 收益 |
|---|---|---|---|
| P1-1 | Capability 三角色（Definition/Provider/Consumer），web_search 可在 Brave/Bing/Serper 切换 | Medium | 高 |
| P1-2 | Subagent Provider Registry（in-process spawn/fork/codex/claude-code）| Large | 中 |
| P1-3 | Subagent 权限冻结（approval=never）| Short | 高 |
| P1-4 | observability trace id + OTel 导出 | Medium | 高 |
| P1-5 | preset 模式系统（standard/code/minimal/cordis + paeg_teaching）| Medium | 高 |
| P1-6 | skill frontmatter 升级为完整 YAML（PyYAML）| Quick | 中 |
| P1-7 | hooks_hub timeout 真正生效 | Quick | 中 |
| P1-8 | MCP health check + 自动重连 | Short | 中 |

## 三、P2（结构性优化）

| ID | 需求 | 工作量 |
|---|---|---|
| P2-1 | 指标持久化改 append-only + 滚动归档 | Quick |
| P2-2 | hooks event 版本化与 schema 文档 | Short |
| P2-3 | skill 间依赖声明 + 拓扑加载 | Short |
| P2-4 | admin API：远程 reload/toggle hook | Short |
| P2-5 | persona + subject + mode 三维 preset 整合 | Medium |
| P2-6 | tool_cache 接入 config_hub 统一能力 | Quick |
| P2-7 | PaegLogger 级别控制 + 文件 sink | Quick |

## 四、最重要的 3 个优化（高收益 × 低成本 × 教育场景）

1. **P0-1 workflows_hub**：教学六阶段（诊断→计划→呈现→评估→调整→反思）现散落 paeg.py，改成可声明 workflow JSON → 整堂课可序列化/重放/编排
2. **P0-4 Permission Preset**：4 档预设让教师一键切"考试模式 = minimal"（禁 save_document/PPT/破坏性工具）——面对学校/家长最硬卖点
3. **P0-2 mcp_client session 复用**：每次 MCP call 新建 npx 进程（200-500ms），session 复用后单次教学延迟降 3-8 秒，零架构风险

## 五、实施顺序（ULW 循环）

### 立即可做（≤1 天）
1. P0-2 mcp_client session 复用（纯性能，零风险）
2. P1-7 hooks_hub timeout 生效
3. P1-6 skill frontmatter 升级 PyYAML
4. P2-6 tool_cache 接入 config_hub
5. P2-7 PaegLogger 级别控制

### 需设计（1-2 天）
6. P0-1 workflows_hub（MVP：agent+log 两原语 + 教学最小流）
7. P0-3 hooks_hub 4 dispatch
8. P0-4 Permission Preset
9. P1-1 Capability 三角色
10. P1-4 trace id

### 需更多设计（3 天+）
11. P0-6 Patch Layer
12. P1-2 Subagent Provider Registry
13. P1-5 preset 模式系统
14. P0-5 matcher JS 表达式

## 六、停手线信号

- hooks.json 钩子 > 20 且抢同一事件 → 先做 P0-3 4 dispatch
- mcp 工具数 > 50 → 先做 P1-1 Capability 三角色
- subagent 数 > 15 → 先做 P1-2 Provider Registry
- 学校数 > 5 → 先做 P0-6 Patch Layer
