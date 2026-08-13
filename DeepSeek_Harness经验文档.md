# DeepSeek Harness 架构经验文档（PAEG 参考借鉴）

> 整理日期：2026-08-13
> 来源项目：DeepSeek Harness（github.com/deepseek-ai/deepseek-harness，npm `@deepseek-ai/dsh`）
> 用途：PAEG 独立配置体系（config_hub / hooks / workflows）的设计参考
> 技术文档对应：PAEG技术全景文档 §10.15

---

## 一、项目定位

DeepSeek Harness 是一个 Agent harness 架构（Claude Code / Codex 的替代增强），基于 **Cordis 插件框架**（vendored 在 vendor/），核心哲学：**"Everything is a Plugin"**——所有能力都是可插拔、可逆注册的插件。

安装：`npm install -g @deepseek-ai/dsh`；运行：`dsh --profile web`（网页端，填 API key 即用）。

## 二、核心架构

### 1. Patch Layer（YAML 叠合）—— 配置组合机制

**这是整个设计的根基**（不是 npm patch，是 Cordis 配置叠合）。

组合顺序（应用到空 entry list）：
```
1. profile 列出的每个 bundle（按顺序）
2. profile 自己的 cordis.patch.yml（profile 级覆盖）
3. $DSH_HOME/cordis.patch.yml（用户级覆盖）
4. 命令行 --patch 叠加（按顺序）
```

**核心原则**：*"A patch replaces a row's whole config rather than merging into it"* —— **patch 替换整行配置，不做深度合并**，后层覆盖前层整行。

Bundle 是 npm 包 + `package.json` 声明 `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`——只是把 patch 路径暴露出来。

三个内置 bundle：`dsh-base`（第一层基础）/ `dsh-web-app`（浏览器）/ `dsh-headless`（无服务器一次性）。

### 2. `!!js` JS 表达式 —— 条件配置

`!!js` 是 Cordis Loader 的 YAML 标签，把标量解析成 JS 表达式节点。

**关键规则（postmortem 0002 教训）**：
- `!!js` **只在 plugin config 内求值**（mount 时按 ctx 注入变量）
- **disabled / 其他 entry 元数据不求值**（只是字面对象）——条件组合应该用 **overlay**（叠加 patch），不要把条件塞到 disabled

config 内可用变量：`process.*`（Node 全局）、已声明的 service injections、自定义函数（dshHomePath 等）。

真实示例：
```yaml
- id: sandbox-policy
  name: '@deepseek-ai/dsh-sandbox-policy'
  config:
    mode: !!js process.env.DSH_PERMISSION_MODE ?? 'workspace-write'
    workspaceRoot: !!js process.cwd()
```

### 3. 事件 4 种 Dispatch 模式

| 模式 | 等待 | 顺序 | 返回值 | 用途 |
|---|---|---|---|---|
| `emit` | 否 | 注册顺序 | 无 | 观察（默认）|
| `waterfall` | 否 | 注册顺序 | 有 | 中间件链（listener 必须 next() 让出，否则短路）|
| `parallel` | 是 | 并发 | 无 | 通知 |
| `serial` | 是 | 顺序 | 有 | 串行处理 |

**waterfall 语义**：listener 必须调用 `next()` 让出；不调用 = 主动短路（"我否决"）。

### 4. Capability 三角色（Capability Seam）

每个能力有三个角色：
1. **Service Definition**（接口，如 `ShellExecutor`）—— 占据 `ctx.<key>`
2. **Service Provider**（实现，如 `dsh-bash-local`）
3. **Consumer**（使用方，通常是 model-facing tool）

**能力必须三合一才完整**（"complete, never one role"）。

### 5. Agent 循环

```text
turn/start → agent/pre-step → step/start → agent/request → llm/stream
→ assistant/chunk* → tool/call* → tools/pre-execute → tools/execute
→ tools/post-execute → tool/result* → step/end → agent/turn-stopping → turn/end
```

关键原则：**Session log 是真理之源**（"Model-visible ⟺ logged"）；**Step** = 一次模型请求+工具；**Turn** = 零或多个 step。

## 三、Workflow 系统（PAEG 阶段 3 模板）

### 1. Workflow = plain JS 脚本 + worker thread

```ts
interface WorkflowStartRequest {
  script: string        // 普通 JS 脚本体（顶层 await 可用，以 return 结束）
  meta: WorkflowMeta    // 身份（plain JSON，不是脚本片段）
  args?: unknown        // 输入数据
  parent: Agent         // 必需：每个 agent() 归属到它
  maxTotalAgents?: number
  signal?: AbortSignal
}
```

### 2. 脚本 DSL（5 个全局）

```javascript
const globals = {
  agent: (prompt, opts) => ...,      // 启动 subagent
  parallel: (thunks) => ...,         // 并发执行
  pipeline: (items, ...stages) => ...,  // 流水线
  phase: (title) => ...,             // 进度分组
  log: (message) => ...,             // observer 日志
  args,                              // 输入数据
};
```

**不需要新语言**——顶层 await + async + 对象解构即可编排。

### 3. 关键约束

- `meta` 和 `args` 是 **plain JSON data**，脚本文本**不会**被求值得到它们（防注入）
- `parent` 必需——child agent 自动归属（cwd/lineage/depth 继承）
- Fatal 错误（`SCRIPT_PARSE`/`META_INVALID`）抛 `WorkflowError.fatal`，被 parallel/pipeline 重抛（不降级）

### 4. Workflow 事件（observe-only）

`workflow/start`、`phase`、`log`、`agent-start`、`agent-end`、`end`——监听器不能拿 cancel/dispose 权限。

### 5. Ralph（固定策略 workflow）

每轮**全新子 session**（不继承父/前 child 对话），共享 workspace + 有界 Ralph handoff（结构化交接报告）携带跨循环状态。

```ts
interface RalphHandoff { status, summary, evidence, nextSteps, blockerText }
```

`maxRounds` 是配置项（如 64），无动态条件触发。

## 四、Preset 模式系统

### 1. Preset 结构

每个 preset 是目录，含两个文件：
- `preset.yml`：元数据（name/description/order）
- `agent.cordis.yml`：Cordis 配置（选哪些 plugin rows + 什么 config）

### 2. 4 个预设

| Preset | 核心差异 | 场景 |
|---|---|---|
| **standard** | 全功能：shell+FS+jobs+skills+goal+plan+subagent+workflow+Ralph+todo+ask+web | 默认编程助手 |
| **code (PTC)** | standard + `tool-presentation: {mode: code}`（工具暴露为 TS SDK，run_code 一次多步）| 多步编排 |
| **minimal** | 仅持久 bash + str_replace_editor 两工具 | 极简终端 |
| **cordis** | standard + 自修改工具（运行时 mount/unmount plugin）| 创建新 preset |

### 3. Preset 隔离

- Preset 只影响**该 session**（mount 在 agent 的 scope context 下）
- 其他活跃 session 不受影响；一个进程可跑多个不同 preset
- 新 service 行必须放 `isolate: { svc: true }` realm（否则冲突）
- 自定义路径：`${DSH_HOME}/.agent-presets/<id>/`

## 五、权限/安全模型

### 1. 三层防护

```yaml
# Layer 1: Sandbox（文件/进程边界）
- id: sandbox
  name: '@deepseek-ai/dsh-sandbox-local'
- id: sandbox-policy
  config:
    mode: !!js process.env.DSH_PERMISSION_MODE ?? 'workspace-write'

# Layer 2: Approval（用户审批）
- id: approval
  name: '@deepseek-ai/dsh-user-approval'

# Layer 3: Permission presets（预置组合）
- id: permission
  name: '@deepseek-ai/dsh-permission-presets'
  config:
    presets:
      read-only: { sandbox: read-only, approval: ask }
      workspace-write: { sandbox: workspace-write, approval: ask }
```

### 2. 运行时限制

运行时只能改 sandbox 和 approval，**不能 mount/unmount 文件系统**（composition-time 特性）。

### 3. 子 agent 权限冻结

```typescript
// captureDelegatedPolicyOverrides(parent)
// 子 agent 继承父的 sandbox
// approval policy 强制改为 'never'（防止 ask 被忽略）
// 任何 sandbox 升级请求被拒绝
```

### 4. Guard 插件

- `repeat-tool-reminder`：连续相同工具调用 N 次注入 escalation 提醒（WeakMap<Agent, Chain> 按 agent 隔离）
- `timeout-policy`：对声明 timeoutMs 的工具设置协作超时

## 六、Subagent 系统

### 1. Provider Registry（多 provider 共存）

| 包 | 类型 |
|---|---|
| subagent-spawn-in-process | 同进程 spawn（fresh agent）|
| subagent-fork-in-process | 同进程 fork（继承父历史）|
| subagent-acp | 进程外 ACP |
| subagent-codex | 真正 Codex app-server |
| subagent-claude-code | 真正 Claude Code via Agent SDK |
| subagent-dsh-sdk | 进程外 deepseek-harness 子进程 |

### 2. Codex 子 agent 流程

```text
1. 启动官方 codex app-server --stdio 子进程（父 session cwd）
2. JSON-RPC: initialize → thread/start { cwd, ephemeral: true }
3. 接收 agentMessage → 等 turn/completed → 取 final_answer
```

**one-shot**：子 agent 看不到父对话；无 resume/continuation（进程死了就死了）。

### 3. 默认禁用外部子 agent

standard preset 默认 `disabled: true` 暴露 Codex/Claude 子 agent 工具行——**通过复制 preset 启用**，不修改共享文件。

## 七、Hooks 系统（PAEG 阶段 2 模板）

### 1. Hooks 是"桥"不是一等公民

Hooks 把 Claude Code / Codex 外部 `hooks.json` 翻译成 harness 自己的 typed interception points。**"任何 bespoke 的应做原生 plugin"**。

### 2. Hook Point 映射

| Claude Code hook | Harness 拦截点 | 语义 |
|---|---|---|
| SessionStart | agent/session-start（emit）| additionalContext → inject（不能 block）|
| UserPromptSubmit | agent/pre-step（waterfall）| deny → reject；additionalContext → next() 后追加 |
| PreToolUse | tools/pre-execute（waterfall）| deny/ask |
| PostToolUse | tools/post-execute（waterfall）| deny → block with feedback |
| Stop | agent/turn-stopping（serial）| blocking → steer() 强制继续 |

### 3. 关键协议

- **Matcher**：`*`/字面量/正则；invalid regex 返回 false（不抛）；配置阶段 matcherDiagnostic 拒绝
- **Most-restrictive merge**：deny > ask > allow；continue:false sticky；additionalContext 累积
- **runHook 永不抛**：执行器拒绝 → 退化为 exitCode undefined（非阻塞错误）
- **超时**：默认 600_000ms（10 分钟），per-hook timeout 覆盖
- **cwd**：用 session 的 cwd（不是 server 启动目录）
- **detached run**：emit 点无 await → 必须跟踪 run chain；dispose 时 drain（先 abort 再等落定）

## 八、可借鉴到 PAEG 的经验总结

| 借鉴点 | deepseek-harness 设计 | PAEG 落地 |
|---|---|---|
| **Patch Layer** | YAML 叠合，后层覆盖整行 | config_hub 配置叠合（P0）|
| **!!js 条件** | 只在 config 求值，不在 disabled | config_hub 规则引擎（P0）|
| **waterfall+next()** | listener 调 next() 让出 | hooks_hub（✅ 已实现）|
| **matcher** | */字面量/正则，invalid→false | hooks_hub match 字段（✅ 已实现）|
| **most-restrictive** | deny>ask>allow，sticky | hooks_hub verdict 合并（✅ 已实现）|
| **Workflow DSL** | plain JS（agent/parallel/pipeline/phase/log）| workflows_hub（阶段 3）|
| **4-Preset** | standard/code/minimal/cordis | config_hub 教学预设（P1）|
| **权限三层** | Sandbox/Approval/Permission | 复用 tool_registry risk 分级（P1）|
| **子 agent 冻结** | approval=never | workflows 子 agent（P1）|
| **Provider Registry** | spawn/fork/外部 agent | workflows subagent（P1）|
| **Capability 三角色** | Definition/Provider/Consumer | config_hub taxonomy（P1）|

## 九、关键教训（避免踩坑）

1. **JS 表达式只在 config 求值**——不要在 disabled/元数据里用（postmortem 0002）
2. **Patch 替换整行而非合并**——避免配置漂移
3. **Hook runHook 永不抛**——执行器拒绝退化为非阻塞错误
4. **Workflow Meta 是 plain JSON**——脚本不求值它（防注入）
5. **子 agent 权限冻结**——approval 强制 never，sandbox 升级拒绝
6. **Preset 用 isolate realm**——不污染其他 session
7. **waterfall listener 必须 next()**——不调用 = 短路（"我否决"）
8. **Model-visible ⟺ logged**——所有模型可见内容必须能从日志重建
