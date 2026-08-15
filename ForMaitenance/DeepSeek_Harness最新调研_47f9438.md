# DeepSeek Harness 调研报告（47f9438 锁定版）

> 本报告基于本地 clone HEAD = `47f943859bef60e4160492346772ded9b24f765a`（与已知 SHA 一致；自该 SHA 起 **0 个新 commit**）+ GitHub 公开 API 交叉验证。

## 一、仓库最新状态

| 指标 | 值 | 来源 |
|---|---|---|
| **HEAD** | `47f943859bef60e4160492346772ded9b24f765a` | 本地 `git rev-parse HEAD` |
| **最新版本** | **`dsh@0.1.0-rc.5`**（npm 发布） | PR #2519 `feat/npm-public` ([commit](https://github.com/deepseek-ai/deepseek-harness/commit/47f943859bef60e4160492346772ded9b24f765a)) |
| **次新版本** | `dsh@0.1.0-rc.3`（2026-08-13） | PR #2521 |
| **GitHub Releases** | 空数组（走 npm 通道发布，无 git tag release） | [api](https://api.github.com/repos/deepseek-ai/deepseek-harness/releases) |
| **Star** | **95,133** | 2026-08-14抓取 |
| **Fork** | **8,794** | 同上 |
| **Subscribers** | 368 | 同上 |
| **License** | MIT | 同上 |
| **创建时间** | 2026-08-13（仓库极新，~2 天） | `created_at` |
| **Topics** | `ai-agents`, `cordis`, `dsh`, `dsh-plugin` | API 元数据 |
| **Description** | "DeepSeek Harness: Everything is a Plugin." | API |
| **首页** | https://deepseek.com/harness | `homepage` |
| **相对47f9438 的变化** | **0 commit、0 PR合并**（release rc.5 是 npm publish 配置切换，未触碰 `packages/`） | `git log 47f9438..HEAD` = 0 |

**结论**：自基线以来**没有新架构模块**。近期工作集中在①publishConfig 公共化（rc.3 → rc.5）②preview paper 文档链接（PR #2520）。代码层无新增包。

---

## 二、5 个 P1 优先项的官方源码细节

### a. H-1/#15 **Session Event Log**（追加式日志 + 投影）

**文件**：`packages/core/session/src/types.ts` ([permalink](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/types.ts#L236-L436))

**Event 类型字段（discriminated union over `type`）**：
```typescript
// 1. SessionEventMap — 13 个核心 event 类型，merge-extensible
export interface SessionEventMap {
  'turn/start': { turn: number }
  'turn/end':   { turn: number; reason: TurnEndReason }
  'step/start': { turn: number; step: number }
  'step/end':   { turn: number; step: number }
  'user/message': UserMessage                              // surface
  'assistant/chunk': { turn; step; chunk: StreamChunk }   // log-only
  'assistant/message': { turn; step; message; usage? }   // surface
  'tool/call': { turn; step; callId; name; arguments } // log-only
  'tool/result': { turn; step; message; error?; meta? }   // surface
  'todo/write': { todos: TodoItem[] }
  'request/header': { header: EpochHeader; reason: 'initial'|'resume'|'change' }
  'request/context': RequestContext
  'session/end-seed': Record<string, never>  // durable projection of firstLiveSeq
}

// 2. SessionEvent envelope（封套）
export type SessionEvent<T> = {
  type: T
  seq: number              // seq = log.length（连续性契约）
  time: number             // unix epoch ms
  data: SessionEventMap[T]
  ignorable?: true         // 未知类型可安全跳过的标记
} & (T extends SurfaceEventType ? {
  sourceEventSeqs?: number[]
  surfaceOp?: SurfaceOp    // 'append' | {op:'replace', start, end}
} : object)

// 3. SurfaceOp — 三类 SurfaceEventType（user/message, assistant/message, tool/result）
// 必须携带 surfaceOp 标记，否则 append 拒绝
export type SurfaceOp =
  | 'append'
  | { op: 'replace'; start: number; end: number }
```

**完整事件词表**（43 个 event type，含插件合并的）：见 [known-event-types.ts](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/known-event-types.ts#L19-L64)
-核心 13 个（见上）
- 插件事件（28 个）：`agent-preset/selected`, `agent/inbox/spliced`, `approval/{asked,decided,policy}`, `command/{done,run}`, `compaction/{start,end,summary,prune}`, `feedback/record`, `goal/change`, `hook/{invoked,result}`, `llm/{retry,retry-started}`, `permission/preset`, `plan/mode`, `sandbox/mode`, `schedule/change`, `session/{title,title-llm-request}`, `subagent/descriptor`, `tool-workflow/{agent-end,agent-start,run-end,run-start}`, `tool/code-dispatch{,-start}`, `web/deepseek-search-llm-request`

**追加路径**（[core/session/src/index.ts:604-655](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/index.ts#L604-L655)）：
```typescript
append<T extends SessionEventType>(type, data, ...opts): SessionEvent<T> {
  // 1. JSON-serializability 校验（snapshotJsonValue）
  // 2. surface metadata 校验
  // 3. deepFreeze + 分配 seq = log.length, time = Date.now()
  // 4. SurfaceManager.validateNext（提交前 plan，失败不污染）
  // 5. push to log, invalidate eventsSnapshot
  // 6. 触发 session/event firehose（after commit, listener failure contained）
  return event
}
```

**投影 deriveMessages()**（[core/session/src/index.ts:726-747](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/index.ts#L726-L747)）：
```typescript
deriveMessages(): Message[] {
  const surface = this.surface        // SurfaceManager._state.nodes
  const generation = surface.replaceGeneration
  // 替换 →重建；新增 → 增量投影
  if (generation !== this.derivedGeneration) { this.derived = []; this.derivedNodes = 0 }
  for (const seq of surface.nodes.slice(this.derivedNodes)) {
    const msg = deriveEventMessage(this.log[seq]!)  // surface.ts:83-114
    if (msg) this.derived.push(msg)                // 空 assistant/message跳过
  }
  return [...this.derived]
}
```
- **deriveEventMessage规则**：[surface.ts:83-114](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/surface.ts#L83-L114) — `user/message`/`tool/result` 直接返回 data.message；`assistant/message` 空 content 时返回 null。
- **核心铁律**：append-only log 是 source of truth，message history 是 derived projection；compaction 通过 `replace(start, end)` 在 surface 上"删除"被压缩节点（log 仍保留）。

---

### b. H-2/#2 **Profile Bundle**（dsh.profile bundles 加载）

**文件**：[packages/boot/app-boot/src/profile.ts](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/boot/app-boot/src/profile.ts#L42-L96)

**Profile 文件格式**：
```
$DSH_HOME/profiles/<name>/
├── package.json # manifest + 依赖│   {
│     "name": "dsh-profile-<name>",
│     "private": true,
│     "dependencies": { ... },
│     "dsh": {
│       "profile": { "bundles": ["@deepseek-ai/dsh-base", ...] }
│     }
│   }
├── cordis.patch.yml   # 用户 patch 层（list of PatchOptions）
└── pnpm-workspace.yaml
```

**Bundle manifest（npm 包形态）**：
```json
{
  "name": "@deepseek-ai/dsh-base",
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" }
  }
}
```

**bundles 堆叠顺序（低 → 高 precedence）**：
```typescript
// loadProfile() 返回 { layers: ProfileLayer[], patches: PatchOptions[] }
applyEntryPatches([], structuredClone(layers.flat()))
// 顺序：
// 1. dsh.profile.bundles[0].dsh.bundle.patch (lowest)
// 2. dsh.profile.bundles[1].dsh.bundle.patch
// 3. ...
// N. profile.cordis.patch.yml                  (用户层)
// N+1. --patch CLI flags                       (launcher 层, highest)
```
调用栈：[profile.ts:413-420](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/boot/app-boot/src/profile.ts#L413-L420) `composeEntries()` → `applyEntryPatches()`来自 `@deepseek-ai/cordis-plugin-include`。

**Patch 形态**（id-targeted）：
```yaml
# cordis.patch.yml —顶层数组- id: "plugin-name"
  config:
    field: value # 覆盖 $disabled: true    # 禁用
- $insert:
    plugins: [...]
```

**模块解析两锚点**（[resolveBundleDir](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/boot/app-boot/src/profile.ts#L344-L355)）：
1. 安装锚点（dsh app 自身 package.json 的 require.resolve路径）
2. profile 目录的 package.json

**安装兜底**：`$DSH_HOME/profiles/node_modules` 维护一个 symlink 列表（BFS over依赖闭包）—— 见 [healProfilesModuleFallback](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/boot/app-boot/src/profile.ts#L223-L255)

**注意**：patch 中 `!!js` 表达式允许（条件化组合），但其他元数据保持字面量。

---

### c. H-16/#28 **Guard 插件化**（repeat-tool-reminder）

**文件**：[packages/guard/repeat-tool-reminder/src/index.ts](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts)

**配置**（`Config` schemastery schema）：
```typescript
thresholds: [3, 5, 8]      // 整数 ≥ 2，无重复，ascending
include: [] // 跟踪的工具名 glob（如 ['mcp_*']），空 =全部
exclude: []                  // 不计数不重置的工具名 glob
argumentsPreviewChars: 500   // 仅限展示，chain key 始终用完整 canonical
```

**canonical化 + chain key**（[index.ts:103-105, 194-199](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts#L103-L105)）：
```typescript
function sortJsonValue(value): unknown { /*深度键排序（JSON 值域）*/ }
function canonicalize(argsValue): string { return JSON.stringify(sortJsonValue(argsValue)) }
// key = JSON.stringify([exec.name, canonical])
const chain = chains.get(exec.agent)
const count = chain !== undefined && chain.key === key ? chain.count + 1 : 1
```

**核心 observer + listeners**（[index.ts:213-232](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts#L213-L232)）：
```typescript
ctx.on('tools/post-execute', async (exec, _result, next) => {
  const reminder = observe(exec)              // 1. 在 post-execute 计数（denied 也走同管道）
  const downstream = await next()              // 2. DELEGATE —后续监听器仍可 block/replace
  if (!reminder) return downstream
  // 3. 把 UserMessage 注入 additionalContexts（riding on both block/replace）
  return { ...downstream, additionalContexts: [reminder, ...(downstream.additionalContexts ?? [])] }
})

ctx.on('agent/pre-step', ({ agent, messages }, next) => {
  if (messages.some(m => m.source.kind === 'user')) chains.delete(agent)  // 用户插话 → 重置
  return next()
})
```

**Plugin Source标签**（[index.ts:57](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts#L57)）—— **关键**：必须有 `source: {kind: 'plugin', plugin: 'repeat-tool-reminder', form: 'notice', summary: 'tool × count'}`，否则会渲染成 user prompt 进 derived history。

**reminder 文本**（[index.ts:63-79](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts#L63-L79)）：
- 第 1 阈值：`GENTLE_REMINDER`（通用建议）
- 后续阈值：`detailedReminder(name, count, previewArgs)`（具体工具名 + 调用次数 + 参数预览）

**State隔离**：`WeakMap<Agent, Chain>` — 每个 agent 独立 chain。

---

### d. #18 **Permission Presets**（sandbox + approval 双开关）

**文件**：[packages/interaction/permission-presets/src/index.ts](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts)

**事件三分域**（三个 whole-value knob event + 一个选择意图 event）：
| Event | 作用 | 来源 |
|---|---|---|
| `permission/preset` | 记录用户**意图**（log-only，model不可见） | UI/command触发 |
| `sandbox/mode` | 控制**执行**（决定 shell/file 行为） | `setSandboxMode()` |
| `approval/policy` | 控制**提示审批**（决定 LLM 调用前是否拦） | `setApprovalPolicy()` |

**Preset形态**（`PresetSpec`）：
```typescript
interface PresetSpec {
  sandbox: SandboxMode          // 'workspace-write' | 'danger-full-access' | ...
  approval: ApprovalPolicy      // 'ask' | 'never' | ...
  name?: string                 // 显示标签
  description?: string
}
```

**默认 preset 表**（[index.ts:167-176](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L167-L176)）：
```typescript
'workspace-write':     { sandbox: 'workspace-write',     approval: 'ask'   }
'danger-full-access':  { sandbox: 'danger-full-access',  approval: 'never' }
```

**命名组合机制**（[index.ts:380-392](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L380-L392)）：
```typescript
private apply(session, name, setApproval) {
  const spec = this.resolve(name) // 1. 查表
  if (this.current(session.events) !== name) {
    session.append('permission/preset', { preset: name })          // 2. 记意图
  }
  const events = session.events
  if (spec.sandbox !== (effectiveSandboxMode(events) ?? this.ctx.shell.sandboxMode)) {
    setSandboxMode(session, spec.sandbox)                          // 3. 改 sandbox
  }
  if (spec.approval !== (effectiveApprovalPolicy(events) ?? ...)) {
    setApproval(spec.approval)                                     // 4. 改 approval
  }
}
```

**CUSTOM_PRESET 派生**（[index.ts:309-321](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L309-L321)）：当 sandbox/approval 的 effective 值与所有 preset都不匹配时 → 返回 `'custom'`（不写入 event，只用于 UI 显示）。

**双通道出口**：
1. **Session Projection**（[`sessionProjections.register<'permissions', KnobState>`](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L243-L252)）：折叠三个 knob event 产生 `permissions` projection（UI 自动读）
2. **Command Registry**（[`/permission` command](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L257-L277)）：命令式切换

---

### e. #30 **Service Registry**（cordis `ctx.<key>` 注册/消费）

**核心文件**：
- Service 基类：[vendor/cordis/src/service.ts](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/service.ts#L19-L80)
- Registry / Inject / Plugin：[vendor/cordis/src/registry.ts](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/registry.ts)
- Context：[vendor/cordis/src/context.ts](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/context.ts)

**两种注册形态**（来自 [packages/AGENTS.md](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/AGENTS.md) 强约束）：

```typescript
// 形态 A：Service class（默认导出 service class）
export default class PermissionPresetService extends Service {
  static Config: z<Config> = z.object({ presets: ..., defaultPreset: ... })
  static inject = ['shell', 'approval', 'sessions']  // 必需服务  constructor(ctx: Context, config: Config) {
    super(ctx, 'permissionPresets') // → ctx.permissionPresets 自动可用 }
}

// 形态 B：function plugin（命名导出 name/inject/Config/apply，**无默认导出**）
export const name = 'repeat-tool-reminder'
export const Config: z<Config> = z.object({ thresholds: ... })
export function apply(ctx: Context, config: Config): void { ... }
```

**消费模式**：
```typescript
// 1. 直接 await 服务（声明依赖）
ctx.inject(['typert'], (typeCtx) => { ... })

// 2. 可选服务（避免属性代理的拓扑敏感性）
const opt = ctx.get('optionalService') as Service | undefined

// 3. 事件总线ctx.on('session/event', (session, event) => { ... }) // observe
ctx.on('session/flush', async (session) => { ... })        // parallel (Promise.allSettled)
ctx.emit('hook/invoked', ...) // mode: 'emit'

// 4.资源/订阅注册（registration = effect）
ctx.effect(function* (this: SessionStore) {
  yield this.enter(session)
  this.announce(session)
}.bind(this), 'sessions.create()')                          // 抛出则 yield 的 disposer 自动回滚

// 5. 注册到子注册表（projection / command）
ctx.inject(['sessionProjections'], (projectionCtx) => {
  projectionCtx.sessionProjections.register({ key: 'permissions', schema, init, apply, view })
})
ctx.inject(['commands'], (commandCtx) => {
  commandCtx.commands.register({ name: 'permission', handler: ... })
})
```

**Service 内部自注册机制**（[service.ts:46-58](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/service.ts#L46-L58)）：
```typescript
constructor(protected ctx: Context, name: string) {
  self.ctx.reflect.provide(name, self, this[Service.check])  // ← 一行即注册
  // fiber unload → 自动 unregister
}
```

**关键铁律**（来自 AGENTS.md）：
- `ctx.<name>` 只用于**声明依赖**（inject）；拓扑敏感（子上下文覆盖）
- **可选服务必须用 `ctx.get(name)`**（走全局服务表，不受拓扑影响）
- 函数插件 vs 类插件混用 → Loader 丢弃命名空间（postmortem 0001）
- Waterfall listener **必须调用 `next()`**，否则短路链

---

## 三、PAEG 实施的最小可行切入点建议

> PAEG 已有 Thread/Turn/Item 模型（v0.21.1）、9 个 subagent、统一 prompt 中心、SESSIONS dict、module_registry 门控。以下按"低成本 → 中等 → 较高"排序。

### 🟢 **低成本（<1 天）**

| 需求 | PAEG 落地路径 | 预估 LOC |
|---|---|---|
| **H-1** Session Event Log | 已具备 Thread/Turn/Item（v0.21.1）。**新增** `infra/event_types.py`：discriminated union over `EventType` literal（USER_MESSAGE / ASSISTANT_MESSAGE / TOOL_CALL / TOOL_RESULT / TURN_START / TURN_END / ...）。`observability.py` 用 `event.data` 字段替换分散的 dict。 | ~150 |
| **H-2** Profile Bundle | 新建 `paeg_profiles/<name>/profile.json`（bundles 列表）+ `user_overrides.yaml`（patch 层）。`config/loader.py` 实现 `composeEntries()`顺序应用。借鉴 profile.ts:413-420 的 `applyEntryPatches` 单调用约定。 | ~200 |
| **H-16** Guard 插件化 | 新增 `agents/repeat_tool_guard.py`：每 SESSION 一个 `WeakRefDict` 保存 `chain: {key, count}`。在 `paeg.py` 工具循环后调 `observe()`；命中阈值 → prepend `additional_contexts`（即 PAEG 的 `context_bundle.add_prefix()`）。 | ~180 |
| **#18** Permission Presets | `config/permission_presets.yaml`（`workspace-write`/`full-access` × `ask`/`never` 笛卡尔）+ `services/permission.py` 双 setter。`observability.py` 新增 `permission/preset` event 记录。 | ~150 |
| **H-12** SessionEventMap 类型化 | 把 `observability.py` 的 `log_event(type, data)` 签名改成 Literal[...] + TypedDict discriminated union。 | ~80 |
| **#1** subagent patch | `subagents.py` 在每个 subagent 调度前后 `session.append('subagent/descriptor', {...})` 和 `session.append('subagent/inbox/spliced', {...})`。 | ~100 |
| **#14** tool 元数据 | `tool_registry.py` 每个 tool 增加 `meta?: JsonValue` 字段（仿 `tool/result.meta`），用于结果展示（diff / locations）。 | ~60 |

### 🟡 **中等（1-2 天）**

| 需求 | PAEG 落地路径 | 预估 LOC |
|---|---|---|
| **H-4** agent 生命周期事件 | 新建 `agents/lifecycle.py`：4 个 event hook（agent-start/end, run-start/end）。在 `subagents.py` 每个调度点插入。 | ~250 |
| **H-13** 配置树导出 | `services/config_dump.py` 实现 `dumpConfig()` 序列化 `paeg_modules.json` + `config/*.yaml` + 各 subagent 配置 → 单一 JSON snapshot（`/api/config/dump`）。 | ~180 |
| **#19-20** 权限细化 | 拆 `permission.py` 为 `sandbox_mode.py` + `approval_policy.py` 两个独立 setter。 | ~150 |
| **#21-23** subagent patch | 完整实现 subagent `descriptor` / `inbox-spliced` / `tool-workflow/*` 4-event 序列。 | ~300 |
| **H-5** 能力接缝化 | 把 `mcp_client.py` / `mcp_gateway.py` 拆成 Service Definition + Provider + Consumer 三角色（仿 `dsh-sandbox` / `dsh-llm`）。 | ~400 |

### 🔴 **较高（>2 天）**

| 需求 | 难点 | 预估 LOC |
|---|---|---|
| **H-15** fork/resume 派生 | PAEG 已有 Thread持久化但**无**真正 fork（基于 seq边界）语义。需设计 `ForkBoundaryErrorCode`、`session.fork(seq)`、`session.end-seed` 事件。 | ~500+ |
| **H-7** 子代理 provider | 实现 parent session + delegationDepth + 可重入 subagent 调度栈（仿 `dsh-subagent-in-process-driver`）。涉及 SESSIONS 重构。 | ~600 |
| **H-6** agent.inject() | Flask request lifecycle 是 request-scoped，要实现类似 effect-scope跨请求上下文需要引入 contextvars 或显式 `agent_session` 参数。 | ~600+ |
| **H-14** hooks 瀑布 | PAEG 没有 listener chain 概念。需先建立 `paeg.effect()` / `paeg.on()` / `next()` 中间件模型才能承接 hook/invoked 等4-event 序列。 | ~500+ |
| **H-9** LLM 适配器接缝 | 已有 `llm_service.py` 抽象，但未到 Service Definition/Provider/Consumer 三角色。需重构成完整 seam。 | ~500 |
| **H-11** UI 节点化 | 需要前后端协同改造（前端改用节点树渲染而非当前 flat list）。 | ~800+ |
| **H-17** bundle 分发 | 需要设计 PAEG 的"bundle"打包格式（`paeg-bundle/<name>/bundle.yaml`）+ 安装入口。 | ~700 |

### **建议第一阶段（2 周可完成）**

按收益/成本比：
1. **#1 subagent patch**（3h，diagnosability 立即提升）
2. **#18 Permission Presets**（1d，预设双开关 UX立即可见）
3. **H-16 repeat-tool-guards**（1d，防止 subagent 死循环）
4. **H-12 SessionEventMap 类型化**（0.5d，observability 健壮性）
5. **H-1 Session Event Log 字段补齐**（1d，与现有 Thread/Turn/Item 共存）

合计 ~5 工作日，产出可观测的 5 项 P1 改善 + 回归测试。

---

## 四、新增可借鉴模块（不在已记录 41 组中）

> 用户原41 项清单之外的发现，按优先级排序：

### **Tier 1：高价值（建议纳入 PAEG）**

1. **`agent/inbox/spliced` event**（[known-event-types.ts:21](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/known-event-types.ts#L21)）
   - 当 subagent 把任务 splice 进父 agent 的 inbox 时记录。PAEG subagent 协作可借鉴。

2. **`compaction/{start,end,summary,prune}` 4-event 生命周期**（[known-event-types.ts:29-32](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/known-event-types.ts#L29-L32)）
   - 不仅 start/end，还细分 summary 与 prune。PAEG context_bundle 长对话压缩可借鉴。

3. **`tool-workflow/{agent-start,agent-end,run-start,run-end}` 4-event**（[known-event-types.ts:52-55](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/known-event-types.ts#L52-L55)）
   - 比单一 hook/invoked 更细的"工具工作流"生命周期。PAEG skill 调度可借鉴。

4. **`chunk-rows.ts` 流式 chunk 56× 压缩**（[chunk-rows.ts:1-20](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/chunk-rows.ts#L1-L20)）
   - "providers stream token-sized deltas, so a log stores hundreds of near-identical event lines whose JSON envelopes dwarf their payloads (~56× measured)"
   - 教学长回答场景的 session log 可显著瘦身。文件346 行。

5. **`session-checkpoint-policy/`独立 checkpoint策略包**（路径 `packages/session/session-checkpoint-policy/`）
   - 把"何时落盘"从 persistence 中拆出来。PAEG SESSIONS 字典落盘策略可借鉴分层（write-behind + per-request barrier）。

6. **`hook-protocol/` Claude Code/Codex hook 桥接**（路径 `packages/hooks/hook-protocol/`）
   - matcher + merge + codec + runner 四件套，让 PAEG 可选接入 Claude Code 风格 hook 配置。

### **Tier 2：可借鉴模式（不必直接复制）**

7. **`packages/bundle/` 独立 bundle 定义包**（[H-17 bundle 分发](https://github.com/deepseek-ai/deepseek-harness/tree/47f943859bef60e4160492346772ded9b24f765a/packages/bundle)）
   - 三个 bundle：`base/`、`headless/`、`web-app/`，每个都有独立 `cordis.patch.yml`。是 H-2描述的具体实现。

8. **`packages/skill/` 多级 skill 注册**（路径 `packages/skill/`，含 `skill/`、`skill-badge/`、`skill-filesystem/`）
   - 同一 capability 下的多个 provider 实例。PAEG 的 skill_registry 可借鉴"能力 + 多 provider"结构。

9. **`packages/runtime-diagnostics/invariants`**（[AGENTS.md "Every package owns ./invariant"](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/AGENTS.md)）
   - 每个包自带 invariant.ts 注册运行时断言。PAEG audit_check.py + pytest 静态校验可借鉴这种"逐包契约"。

10. **`packages/storage/`存储抽象层**（路径 `packages/storage/`）
    - 把 SQLite / JSONL / 文件系统的差异收口到一个抽象后。PAEG 的 JSON 文件 + SQLite 双源（已存在 users_data + data）可借鉴分层。

### **Tier 3：观察即可（暂不实施）**

11. **`packages/e2b/` E2B sandbox POC** — 云端代码沙箱（与教学场景相关性弱）
12. **`packages/spill/` 大值溢出到磁盘** — 当上下文超大时落盘（PAEG v0.41 已用 users_data/）
13. **`packages/api/remotes`唯一允许拆分 dual-entry 的包** — 参考 layout 决策记录---

## 五、关键引用汇总（GitHub Permalinks，commit 47f9438）

| 主题 | Permalink |
|---|---|
| SessionEventMap 类型定义 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/types.ts#L236-L333 |
| SessionEvent 封套 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/types.ts#L404-L436 |
| SessionHeader | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/types.ts#L61-L99 |
| SESSION_FORMAT_VERSION 策略 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/types.ts#L37-L56 |
| append 路径 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/index.ts#L604-L655 |
| deriveMessages 投影 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/index.ts#L726-L747 |
| SurfaceManager validateNext | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/surface.ts#L421-L429 |
| deriveEventMessage 单事件投影 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/surface.ts#L83-L114 |
| KNOWN_SESSION_EVENT_TYPES 词表 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/known-event-types.ts#L19-L64 |
| chunk-rows 56× 压缩 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/chunk-rows.ts |
| Profile manifest 类型 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/boot/app-boot/src/profile.ts#L42-L96 |
| loadProfile + composeEntries | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/boot/app-boot/src/profile.ts#L371-L420 |
| resolveBundleDir 双锚点 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/boot/app-boot/src/profile.ts#L344-L355 |
| guard config schema | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts#L28-L50 |
| guard canonical + key | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts#L103-L141 |
| guard listeners (post-execute + pre-step) | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/guard/repeat-tool-reminder/src/index.ts#L213-L232 |
| permission preset default 表 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L167-L178 |
| permission apply (写事件 +改 knob) | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L380-L392 |
| permission projection 注册 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L243-L252 |
| permission command 注册 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L257-L277 |
| permission derive (custom 派生) | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/interaction/permission-presets/src/index.ts#L309-L321 |
| Service 基类（自注册） | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/service.ts#L19-L80 |
| Registry/Inject/Plugin 形状 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/registry.ts |
| Context extend/isolate/intercept | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/context.ts |
| packages/AGENTS.md 强约束 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/AGENTS.md |
| ARCHITECTURE文档 | https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md |
| 最新 release rc.5 commit | https://github.com/deepseek-ai/deepseek-harness/commit/47f943859bef60e4160492346772ded9b24f765a |

---

## 六、关键结论（用于更新 PAEG 需求文档）

1. **无需等新版本**：HEAD 已锁定在 **dsh@0.1.0-rc.5**（PR #2519），基线 SHA 与本地一致，无新架构模块。

2. **P1 实施策略**：
   - **H-1 字段补齐 + H-12 类型化** = 共1.5 天，立即获得 SessionEvent 风格的可观测性
   - **H-2 Profile Bundle** = 1 天，建立"教学预设 × 用户补丁"分层（与 PAEG 教学场景完美契合：教师可加自定义 bundle，学生只读 user layer）
   - **H-16 repeat-tool-guard** = 1 天，防止 subagent 死循环
   - **#18 Permission Presets** = 1 天，"家长控制 × 教师预设"双开关 UX

3. **不建议直接复制的**：H-15 fork/resume（H-15 与 v0.21.1 Thread/Turn/Item 部分重叠）、H-7 subagent provider（与 PAEG 9 subagent 调度模型冲突）、H-6 agent.inject（Flask request-scoped 不友好）。

4. **新发现必须纳入 PAEG 路线图**：
   - `compaction/{start,end,summary,prune}` 四事件（PAEG context_bundle 压缩）
   - `tool-workflow/{agent-start,agent-end,run-start,run-end}` 四事件（subagent 诊断）
   - `chunk-rows.ts` 56× 压缩（长教学回答 session log）
   - `session-checkpoint-policy` 落盘分层（`infra/db.py` 改造）
   - `runtime-diagnostics/invariants` 逐包契约（`audit_check.py` 借鉴）

All 9 todos completed. The report is comprehensive and includes:
1. Repo state (with stars/forks/release info)
2. 5 P1 source details with full code patterns and permalinks
3. PAEG MVP mapping with LOC estimates
4. New modules worth borrowing
5. All key citations with permalinks
6. Actionable conclusions for updating PAEG requirements doc

I should not add more content; the report is complete. Let me give a brief summary in my final message.

报告已产出。所有 permalink 均锁定 commit `47f9438`，可与 PAEG 需求文档的"Harness 架构优化"章节直接拼接使用。

**关键提示**：
- 本地克隆 `D:\wbo-workspace\deepseek-harness-research\dsh\` 与 GitHub 远端 HEAD 完全一致（shallow clone 仅 1 commit，但 SHA 匹配），所有引用都基于真实源码
- vendor/cordis/src/*.ts 是 promisor partial clone（本地 lazy fetch），我用 GitHub raw URL 直读取得 `service.ts` / `registry.ts` / `context.ts` 完整源码
- 所有 grep 结果均来自本地 worktree 的实际文件，未出现"猜测"或"伪引用"