# PAEG 任务总清单与操作规范（固定文档 · 防遗忘）

> 创建日期：2026-08-14
> 性质：**本文件是操作的唯一依据**——所有未完成任务、用户指示、调研要求固定于此，每次操作前先读此文件，完成后更新状态。
> 原则：**不要丧失注意力，不要丢失之前的任务；不要忙着执行，先把任务完整记录；调研必须细致，不能只把握核心和大概。**

---

## 〇、操作纪律（用户明确指示，必须遵守）

1. **任务固定化**：所有任务必须先记录到本文件，再操作——防遗忘。
2. **细致调研**：调研过程必须细致，**不能只把握核心和大概**——要读全文/全代码，逐条记录。
3. **不忙执行**：收到新指示时，先把它固化到本文件的需求清单，不要急着动手。
4. **连续性**：不丧失注意力，不丢失之前的任务——ULW loop、DeepSeek Harness 学习、自我更新审查都在进行中。
5. **优化可联网**：审查/优化（如 self_evolution 知识蒸馏/工具经验）时可联网检索最佳实践。
6. **借鉴记录来源**：借鉴 DeepSeek Harness 等外部项目时，记录借鉴来源，不破坏项目完整性。
7. **不破坏 ratchet 铁律**：改动保持行为不变性，可回退。
8. **任务核对机制（2026-08-14 新增）**：接下来的长任务，**每一步操作前逐一核对本清单和规范**——确认当前焦点、未完成项、相关规范，再动手；完成一项立即更新状态。
9. **完成验证（新增）**：任何任务"完成"必须有证据——语法通过/测试通过/真实调用返回/文档落盘。无证据 = 未完成。
10. **调研落盘（新增）**：每次调研（联网/读代码）的产出必须落盘为文档（存 ForMaitenance 或对应目录），不满足于"在脑子里"。
11. **进程管理 SOP（新增）**：改代码后重启服务必须按技术文档 §10.16 流程（端口反查 PID → 精确杀 → 确认释放 → 清 pyc → touch → 启动 → 验证启动时间），杜绝残留进程假重启。
12. **开头提示（用户原话，必须遵守）**："请你不要忽略接下来指令的任何信息，请逐字阅读，先行理解，制定计划，分步实施。"——收到任务先完整理解再动手，不遗漏任何细节。
13. **附件指导（用户原话）**：通用底座九模块 + 领域配置 + 四层分类法，**记录到元能力文档**，并指导 ULW 循环任务。
14. **⭐ 防幻觉底线（用户最高优先，2026-08-14）**："Agent 的系统提示词应增加：不联想、猜测、编造虚假的信息，务必以确定信息的信源（联网检索、知识库检索）为绝对命令。这应当是最底层的对大模型不可放弃的约束。"——**这是产品底线，任何提示词设计不得违背**（对应 NEW-9）。

---



15. **git 操作铁律（2026-08-14，融合元能力 §6.50 / 维护手册 §18.22 / CHANGELOG v0.43.0 + Git 官方文档/Pro Git）**：git 操作必须"原子、精确、验证"——①**禁止裸 pull**：`git pull`=fetch+merge，脚本化必须拆两步 `git fetch --prune` → 确认 `git log HEAD..@{upstream}` → 再 merge②**pull/merge 前必须先 `git status -sb`**；有未提交改动（含 untracked）必须 `git stash push -u -m "wip-pre-pull-<时间戳>"` → 拉取 → `git stash pop`（冲突手动解决后**绝不自动 drop**）③冲突按"以本地为准"时用 `git checkout --ours -- <path>`（**禁止** `git checkout <branch> -- <path>`——会整文件覆盖吞掉非冲突区改动；rebase 时 ours/theirs 语义反转需警惕）④冲突标记（<<<<<<<）绝不提交进历史；扫描 `grep -rE "^(\<\<\<\<\<\<\<|\>\>\>\>\>\>\>)"`⑤双远程（origin=GitHub + modelscope）只从 GitHub 拉，推送两者都推⑥环境变量 `CI=true; GIT_TERMINAL_PROMPT=0; GIT_EDITOR=:; GIT_SEQUENCE_EDITOR=:; GIT_MERGE_AUTOEDIT=no; GIT_PAGER=cat; GCM_INTERACTIVE=never`（Windows 必须）保证非交互⑦建议配置 `pull.ff only` + `rebase.autoStash true` + `fetch.prune true`。

16. **⭐ 批量重构/正则/AST 清理铁律（2026-08-14，全新——事故记录：CHANGELOG v0.40.6 83 处 NameError + AffectionSupportor 危机块被批量脚本破坏 + 双 pass 正则清理致 subagents.py 语法错误；依据 PEP 8/PEP 760/ast-grep 官方）**：**禁止用正则/sed/PowerShell -replace 批量改写代码结构**——①`except: pass` 是**合法优雅降级模式**（如 `try: import ujson except ImportError: pass`），删除会改变控制流；bare except 会吞 KeyboardInterrupt（Pylint W0702/PEP 760 已承认其脆弱性）②批量改前先提交快照（git commit 或 stash）+ dry-run 预览范围③跨文件批量修改**必须用 AST 工具（ast-grep）**，按 AST 节点（except_clause/try_statement）过滤，禁止按文本匹配 except 关键字④改完立刻 `python -m py_compile` + 跑相关测试⑤小步提交，每步验证，发现破坏用 `git reset --hard HEAD~N` 回滚（前提已提交）。

17. **⭐ git checkout/restore 前必须备份未提交改动 + 禁止 reset --hard（2026-08-14，全新——事故：git checkout 恢复文件时丢失未提交的 TRUTH_GROUNDING/能力清单，已重新注入+提交 a112575 固化；依据 Pro Git 第 2.4 章 "dangerous command" 警告）**：`git checkout -- <file>` / `git checkout <commit> -- <file>` / `git restore` 会**静默丢弃工作区未提交内容**（Pro Git 原话："Any local changes you made to that file are gone"）；`git reset --hard` 是终极大杀器（未提交改动 Git 无法恢复）。恢复前必须：①`git status` 列出未提交文件②未提交改动先 `git stash` 或 cp 备份（<file>.bak）③确认要恢复的确实是"出错的改动"而非"未提交的新工作"④恢复后重新验证语法+功能⑤**禁止在 PAEG 工作区用 `git reset --hard`**，除非已确认所有改动都已 commit/stash。

18. **更新内容及时记录入各个文档（2026-08-14 用户执行标准）**：任何代码/配置/功能改动，**必须同步记录到相应文档**——CHANGELOG（变更历史）、维护手册（故障/修复/SOP）、技术全景文档（架构/机制）、元能力文档（踩坑/经验）、任务清单（状态更新）。禁止只改代码不记文档；文档更新与代码提交同步完成（同一 commit 或紧随其后）。
21. **引号与字符串铁律（2026-08-14 用户要求记录，多次踩坑）**：①Python 字符串中**禁止中文引号（“”）与英文引号（"）混用嵌套**——中文引号是普通字符，会被英文引号定界符打断造成 SyntaxError（如 _build_remediation 的 subtopic 踩坑："学生说：" + _resp + "——…问"这样是不是清楚些？"" 中英文引号配对错乱）②PowerShell here-string（@" "@）内嵌 Python 多行脚本时**避免三引号（'''/"""）**——here-string 与三引号组合易 unterminated（多次踩坑）；改用**临时 .py 文件**执行③f-string 内嵌 dict/json.dumps({...}) 时**花括号冲突**（如 checkpoint yield 踩坑）——先构造 payload 变量再拼接，不用 f-string 内嵌 dict④字符串含引号时优先用单引号包裹或转义，避免嵌套⑤改完立即 `python -m py_compile` 验证（语法错误第一时间暴露）
20. **运行卡住诊断 SOP（2026-08-14 用户要求 T2，记录有时运行卡住的原因）**：agent 运行有时卡住的 5 类根因与处理——①**残留进程**（最常见）：改代码后行为不变/无响应，99% 是旧进程未杀——端口反查 PID→精确杀→确认释放→清 pyc→touch→重启→验证启动时间（技术 §10.16/维护 §18.25）②**LLM 超时/慢响应**：v4-flash 思考型空响应/长响应——检查 thinking/max_tokens 配置；hooks timeout（P1-7）隔离超时钩子不阻断主流程③**SSE 挂起**：客户端断开但生成器未完成——teach_stream try/except + done 事件兜底；前端 AbortController 停止④**工具调用阻塞**：MCP npx 启动慢/失败（fetch/git 404 包）——mcp_client 连接失败跳过不阻塞；web_search 降级栈（Brave→Tavily→Serper→Bing）⑤**网络**（git push/外部 API）：SSL 重置/连接拒绝——本地已提交安全，重试或换网络。**诊断顺序：先怀疑进程→再缓存→最后代码**（改代码后 HTTP 行为不变先查进程）。

19. **subagent 结果及时移入项目文件夹（2026-08-14 用户执行标准）**：**subagent（explore/librarian/writing 等）的输出文件一定落在 wbo-workspace 文件夹**（沙箱/工作区），主 agent 必须**及时将其移动/复制入项目文件夹**（如 ForMaitenance/、audit/、05_实现原型/ 等目标目录），并在任务清单记录移动结果。禁止让 subagent 产物滞留 wbo-workspace 而不归档。

## 一、ULW Loop 大任务（进行中，5 步）

### Step 1：五维度评估基线 ✅
- 代码结构（模块化/多层级/高层函数把低层函数作为参数调用/可扩展/可维护）✅ 已盘点
- 功能完善（所有功能可实现）✅ 56 路由/6 模式/25 MCP/10 skills
- 实施质量（每一种产出都必须高品质）✅ 语言规范层+防幻觉+college_physics
- 智能性（steering + harness 下，大模型能力针对项目场景充分释放，不变傻）✅ 意图路由+深度思考+能力清单+工具透传
- 前端网页没关系
- 其他维度（由我继续构建）
- **产出**：`ForMaitenance/Step1_五维度基线盘点.md`

### Step 1.5：DeepSeek Harness 插件选取
- 遵循"一切皆插件"思想，从 deepseek-harness 仓库选取有用插件配置到 PAEG
- a. 能接入当前项目，不破坏完整性
- b. 记录好借鉴来源

### Step 2：每维度质量文档 → ForMaitenance 文件夹（部分完成）
- 咨询 Oracle + 联网检索，为每个维度制作一份文档（质量标准 + 项目经验 + 实施建议）
- ✅ `质量文档_代码结构.md`（模块化/多层级/参数化/可扩展/可维护 + 红线清单）
- ✅ `质量文档_功能完善.md`（24 行功能盘点 + L0-L3 可达性 + 12 类边界 + 发版 checklist）
- 🔄 `质量文档_实施质量.md` + `质量文档_智能性.md`（重写中）
- ✅ 维护文档移入：ForMaitenance/维护文档/（6 份副本，原位置保留保引用）
- ✅ Step1 基线 + runoob 记录已在 ForMaitenance

### Step 3：基于质量指标自检，修补不足

### Step 4：接口完整性检查
- a. 智能体与外部 MCP、工具链、skills 的接口是否完整
- b. 内部 subagent 和各个模块是否能够调用这些工具链
- c. 是否有明确的、优良的架构：目标/指令 → 规划模块 → 记忆 → 工具调用模块 → 行动执行模块 → 结果评估 → 输出最终结果

### Step 5：runoob 7 篇文档逐字阅读 + 评估改造 ✅ 7/7 已读
需逐字阅读（先记录，后实施）：
1. https://www.runoob.com/ai-agent/agent-architecture.html ✅ 已读（六种架构）
2. https://www.runoob.com/ai-agent/ai-agent-working-principle.html ✅ 已读（三大组成+ReAct）
3. https://www.runoob.com/ai-agent/reasoning-planning.html ✅ 已读（六框架）
4. https://www.runoob.com/ai-agent/ai-agent-intro.html ✅ 已读（Agent 公式+五特征）
5. https://www.runoob.com/ai-agent/prompt-engineering.html ✅ 已读（五段式+防幻觉五策略+XML隔离）
6. https://www.runoob.com/ai-agent/ai-architecture.html ✅ 已读（五层架构）
7. https://www.runoob.com/ai-agent/agent-context-engineering.html ✅ 已读（上下文预算/压缩/水印）

**产出**：`ForMaitenance/runoob七篇学习记录与PAEG对照.md`（逐字要点 + PAEG 对照 + 改造需求表）
**关键发现**：PAEG 缺防幻觉底层约束（NEW-9 最高优先）、上下文预算管理（NEW-2）、LLM-as-judge 评估（NEW-4）

### 最终判定
- 水平达"出众" → 发布最新 release
- 不足 → 修复 P0-P2 所有问题

### 通用底座九模块（用户给定框架，需逐一对照评估）
```
通用底座
├── Interaction：交互
├── Profile：用户模型
├── Diagnosis：差距诊断
├── Plan：计划
├── Action：学习或任务执行
├── Evaluation：效果评估
├── Adaptation：动态调整
├── Knowledge：知识库
└── Output：成果输出
```

### 领域配置（未来扩展方向）
```
├── 乡村教育
├── 企业入职培训
├── 医学生转行
└── 硕博生心理支持
```

### 四层分类法（研究市面产品统一框架）
```
它替谁完成什么工作
现实工作流程有哪些步骤
每一步需要哪些输入、判断和输出
哪些步骤由人、Agent、知识库或外部工具承担
```

---

## 二、DeepSeek Harness 学习任务（进行中）

### 已完成
- ✅ DeepSeek_Harness经验文档.md（九章节：patch层/事件模型/workflow DSL/preset/权限/子agent/hooks/借鉴表/教训）
- ✅ 技术文档 §10.15 参考项目
- ✅ 教材附录 C《参考项目借鉴——DeepSeek Harness 架构经验》
- ✅ workflows_hub MVP + hooks_hub 升级 + config_hub（Patch Layer 思想）

### Step 1.5：从 harness 选取插件配置到 PAEG（细化 · 待完成）

> 用户原话："遵循'一切皆插件'的思想，利用好这个开源仓库，从中选取有用的插件配置到我们自己的项目中。a. 能接入当前项目，不破坏项目完整性 b. 记录好借鉴来源"

**候选插件清单（按 PAEG 价值排序，借鉴来源=deepseek-harness 对应文件）**：

| 插件 | 借鉴来源 | PAEG 落地点 | 优先级 |
|---|---|---|---|
| **Guard：repeat-tool-reminder** | packages/guard/repeat-tool-reminder（同工具连续 N 次调用注入提醒）| hooks_hub 加"重复工具调用提醒"钩子 | P1 |
| **Guard：timeout-policy** | packages/guard/timeout-policy（对声明 timeoutMs 工具协作超时）| hooks_hub timeout 已实现，可增强 | P1 |
| **tool-presentation（code mode）** | apps/cli/config/agent-presets/code（工具暴露为 TS SDK，run_code 一次多步）| workflows_hub 加"程序化步骤"（多步合并一次执行）| P2 |
| **Preset 模式系统** | apps/cli/config/agent-presets/（standard/code/minimal/cordis）| config_hub 加"教学模式预设"（如 minimal_teaching=只读工具）| P1 |
| **Permission Presets** | packages/bundle/base/cordis.patch.yml（read-only/workspace-write/full）| tool_registry 加"权限档位"（考试模式锁定写工具）| P1 |
| **Subagent Provider Registry** | packages/subagent/（spawn/fork/codex/claude-code）| subagents.py 加"子代理 provider"抽象 | P2 |
| **Hook Bridge 兼容** | packages/hooks/hooks-claude-code（CC/Codex hooks.json 翻译）| hooks_hub 支持外部 hooks.json 格式 | P2 |
| **isolate realm** | cordis-primer（preset 隔离作用域）| config_hub 会话级配置隔离 | P2 |

**实施要求**：
- a. 每个插件接入必须**不破坏现有功能**（ratchet 铁律：改前测、改后回归）
- b. 每个借鉴必须**记录来源**（文件路径 + commit SHA `47f943859bef60e4160492346772ded9b24f765a`）
- c. 优先做 P1 三项（Guard 两件 + Permission Presets）——高价值低成本

### 待完成汇总
- ❌ Step 1.5 插件选取（按上表，先 P1 三项）
- ❌ 每个借鉴的来源记录（文件 + commit）

### Step 2：Harness 架构深调研 → 16+ 优化需求（2026-08-14 用户新指令 · 待实施）

> 用户原话："联网检索 Deepseek 的新的 Harness 库，调研其 Harness 架构，这个项目非常值得学习，依据其项目至少产生16项针对我们项目的优化需求，首先记录入需求文档"

**调研结论（官方 docs/architecture.md 全文 + 仓库结构 + commit 12,293 条 / 81.5k stars）**：

DeepSeek Harness（dsh）核心架构 = **一切皆插件**（Everything is a Plugin），基于 **Cordis** 框架（插件贡献服务/类型化事件/可逆副作用到共享 context）：
- **无特权核心**：模型适配器、工具注册表、会话日志、agent 循环本身都是插件，全部可从配置替换——注册即副作用，插件卸载时自动解注册（unwind）
- **Profile/Bundle 分层**：profile = 命名组合（bundles 堆叠顺序 + 用户 cordis.patch.yml + home 级 patch + --patch 覆盖层）；bundle = Cordis 配置行分发格式；`dsh --dump-config` 打印完整可打补丁树，**每一行都可被 patch 覆盖**
- **事件系统三分域**：session 事件（持久事实，追加式日志）/ agent 事件（`agent/*` 携带 live Agent：pre-step/request/turn-stopping 等）/ 能力事件（`fs/*` `tools/*` `telemetry/*` 接缝）；瀑布事件需 next() 委托
- **Turn/Step 流**：step = 一次模型请求+工具调用；turn = 0+ steps，输入收件箱驱动；`agent/turn-stopping` 串行无 next
- **会话日志 = 模型上下文唯一真相源**：模型可见 = 已记录（运行时不变量断言！）；fork/resume/transcripts/telemetry 全部从日志派生
- **能力接缝（Seam）**：Service Definition + Service Provider + Consumer 三角色；一个 provider 换全产品（filesystem/subprocess 共享执行世界，远程沙箱一次迁移 Bash/PTY/LSP）
- **扩展点映射表**：官方给出"新行为挂哪里"完整对照表（添加 provider/工具/上下文/UI 节点/持久状态/会话标题/goals/fork 等）

**依据 Harness 产生的 PAEG 优化需求（≥16 项，借鉴来源=deepseek-harness 对应文件）**：

| # | 优化需求 | 借鉴来源 | PAEG 落地点 | 优先级 |
|---|---|---|---|---|
| H-1 | **⭐ 会话日志事件化**：把 SESSIONS 内存 dict 升级为追加式 SessionEvent 日志 + deriveMessages 投影（模型可见=已记录不变量断言）| packages/core/session | infra/session 或 server SESSIONS 改造 | P1 |
| H-2 | **Profile 预设组合**：教学/考试/陪聊/外部 agent 四场景 profile（bundles 堆叠 + patch 覆盖），运行时 `--dump-config` 式导出 | packages/boot/app-boot profiles | config_hub 加 profile 层 | P1 |
| H-3 | **扩展点映射文档**：官方"新行为挂哪里"对照表 → PAEG 技术文档新增同款映射（加工具/加 LLM 适配器/加钩子/注入上下文/持久状态）| docs/architecture.md Where new behavior goes | PAEG技术说明.md | P1 |
| H-4 | **agent 生命周期事件**：hooks_hub 补 agent/pre-step、agent/request、agent/turn-stopping 事件（拦截/改写请求、停轮）| packages/core/agent + core/agent-loop | hooks_hub | P1 |
| H-5 | **能力接缝化**：TTS/文件系统/工具执行三处 provider 抽象统一为 Seam（Definition/Provider/Consumer）| docs/architecture.md capability seams | voice_service/fs 封装 | P2 |
| H-6 | **agent.inject() 运行时上下文注入**：运行中向下一请求注入上下文（教学中途补画像/提示）| core/agent inject | context_bundle 加 inject API | P2 |
| H-7 | **子代理 provider 注册表**：subagents 9 个硬编码 → provider 接口（spawn/fork/委托外部 agent turn）| packages/subagent | subagents.py | P2 |
| H-8 | **工具作用域隔离**：每 agent 可挂独立工具集（agent.ctx 隔离 realm），会话级能力组合 | cordis scope + isolate realm | tool_registry 加作用域 | P2 |
| H-9 | **LLM 适配器接缝**：llm_adapter 升级为 ctx.llm 式 provider 注册表（模型/流式/工具 schema 组装）| packages/llm/llm | llm_adapter.py | P2 |
| H-10 | **jobs 后台任务系统**：教学长任务（生成讲义/PPT/视频）注册后台 job + job_* 收集/停止 | core/jobs | config_hub 加 jobs | P2 |
| H-11 | **UI 节点化**：前端功能（知识导图/气象/PPT）注册为 ConversationNode 式节点（keyed renderer）| core/agent Web Client Chat Node | 09_GUI前端 | P3 |
| H-12 | **SessionEventMap 类型化**：会话事件类型化扩展点（新增模型可见输入必须先加事件）| core/session SessionEventMap | infra/session | P3 |
| H-13 | **配置树导出 API**：`/api/admin/dump-config` 打印全部可 patch 配置行（对齐 dsh --dump-config）| app-boot dump-config | config_hub + server 端点 | P2 |
| H-14 | **hooks 瀑布补全**：hooks_hub 对齐 waterfall 语义（llm/stream、tools/* 三事件 next 委托链）| docs/architecture.md turn flow | hooks_hub | P1 |
| H-15 | **fork/resume 日志派生**：Thread fork/archive 改为从事件日志派生（保留原始 assistant/chunk 保真）| core/session fork/resume | thread 模型 | P3 |
| H-16 | **Guard 插件化**：repeat-tool-reminder/timeout-policy 从单钩子升级为 guard 包（可组合可卸载）| packages/guard | hooks_hub/guard | P1 |
| H-17 | **bundle 分发格式**：PAEG 技能/工具打包为 bundle（patch 文件 + 代码行，可整体上架下架）| packages/bundle | config_hub bundles | P3 |
| H-18 | **可逆副作用注册**：工具/钩子注册支持 unwind（卸载即解注册，防热加载泄漏）| cordis effects | config_hub reload | P2 |

**实施要求**：
- a. 每项接入**不破坏现有功能**（ratchet 铁律：改前测、改后回归）
- b. 每项记录来源（deepseek-harness 文件路径 + commit SHA `47f943859bef60e4160492346772ded9b24f765a`）
- c. 优先 P1 六项：H-1 会话日志事件化 / H-2 Profile 预设 / H-3 扩展点文档 / H-4 agent 生命周期事件 / H-14 hooks 瀑布 / H-16 Guard 插件化

### Step 2 补充：Librarian 30 项细化调研（2026-08-14 · 与 H-1~H-18 同源）

> 说明：librarian 深度调研（15 章节 / 30 项需求 / 9 P0 + 14 P1 + 7 P2 / 4 阶段 6-10 周路线）。下表为**权威细化版**，H-1~H-18 为速查精简版，对应关系标注于#列。

**关键架构五要点**：
1. **"patch 是 YAML 行级覆盖，不是 Python 继承"**——同一文件同时管 bash/pwsh（`disabled: !!js process.platform === 'win32'`）
2. **4 预设 = 工具子集差异**：standard（全工具）/ code-PTC（+Code Mode TS 程序）/ minimal（仅 2 工具）/ cordis（+tool-cordis 自修改运行时）——可直接迁移到 PAEG"标准/答疑/编程/薇依人格"
3. **Capability Seam 三角色**（Definition/Provider/Consumer）——dsh 换一行即换 Codex/Claude Code 子代理；PAEG 9 subagent 应同模式重构
4. **`!!js` 条件标签**：patch 文件支持 JS 表达式（平台/env 分支）
5. **Permission Preset = sandbox + approval 命名组合**——一个选择器管两个开关；`custom` 是衍生状态不可作目标；切换写 `permission/preset` log-only 事件可回放

**30 项优化需求（权威版）**：

| # | 优化需求 | 借鉴来源（dsh） | PAEG 落地点 | 优先级 |
|---|---|---|---|---|
| 1 | **Subagent Patch 系统**：9 subagent YAML 装扮（persona/prompt/工具/调度全配置可换）| agent.cordis.yml `- id:` 整体替换 | subagents.py → subagent_loader | **P0** |
| 2 | **Profile Bundle 机制**：`python paeg.py --profile education/minimal/research` | dsh.profile.bundles + --patch | config_hub profile 层 | **P0** |
| 3 | **Persona 外置**：薇依 persona 拆 `paeg_personas/{id}.yml` | preset.yml name/description | prompts.py 长字符串外置 | **P0** |
| 4 | **!!js 条件启停**：配置支持 JS 表达式 | `disabled: !!js expr` | config_hub SafeLoader | P1 |
| 5 | **用户家目录 overlay**：`~/.paeg/cordis.patch.yml` 不改代码改默认模型/学科 | $DSH_HOME/cordis.patch.yml | config_hub 加载链 | P1 |
| 6 | **OS 平台双轨**：TTS/STT/PPT 模板按平台分支 | bash+pwsh 双轨 | config_hub 条件挂载 | P2 |
| 7 | **教学预设 4 内置+N 自定义**：standard/minimal/code-mode/weil-classical | 4 预设目录 | paeg/presets/ | **P0** |
| 8 | **PresetService**：mount/list/resolve/recompose/copy/remove | ctx.agentPresets | paeg/preset/service.py | **P0** |
| 9 | **Per-Agent Scope**：每 subagent 独立工具/提示词作用域（shadowing）| dsh-scope agent.ctx | AgentScope 类 | P1 |
| 10 | **Preset 文件结构标准化**：agent.patch.yml + preset.yml + prompts/ + assets/ | preset 目录规范 | paeg/presets/* | P1 |
| 11 | **9 Subagent 三角色重构**：Service Definition/Provider/Consumer（RuleDiagnostor vs LLMDiagnostor 等）| ctx.shell 三角色 | subagents.py | **P0** |
| 12 | **LLM Provider Seam**：切换模型不改业务代码（deepseek/openai_compat）| ctx.llm 多 provider | llm_adapter.py | **P0** |
| 13 | **Shell/Subprocess Seam**：本地/docker/沙箱执行可换 | ctx.shell + ctx.subprocess | tool 执行层 | **P0** |
| 14 | **Tool Registry 能力协商**：元数据级先注入 name/desc，按需完整加载 | defer_loading + listChanged | skill_registry.py | P1 |
| 15 | **Session Event Log**："Model-visible ⟺ logged" 铁律 + deriveMessages 投影 + SessionEventMap 类型化 | core/session | infra/session | P1 |
| 16 | **Hooks 瀑布链**：waterfall 事件（next() 委托，短路可观测）| Waterfall listeners MUST call next() | hooks_hub | P2 |
| 17 | **Subprocess 抽象**：MCP 客户端/ffmpeg/PDF/PPT 统一 spawn 服务 | ctx.subprocess | subprocess service | P2 |
| 18 | **权限预设系统**：student-safe/tutor-write/researcher-full 三档 | permission-presets | tool_registry PERMISSION_PRESETS 升级 | P1 |
| 19 | **Permission 事件入 Session Log**：切换可回放 | permission/preset log-only | session log | P1 |
| 20 | **Custom 衍生状态**：临时切换显示"自定义"不可保存 | current() 返回 custom | permission service | P2 |
| 21 | **Subagent Registry Provider 可插拔**：in-process/external-script/llm-call | ctx.subagents 6 providers | subagents.py registry | **P0** |
| 22 | **Subagent Report/Continuable 协议**：子代理回报 + 父发消息 | subagent-control/report | subagent 控制 | P1 |
| 23 | **Fresh-Agent Loop**（tool-ralph）：每轮 fresh child + 共享进度 + 结构化 handoff | tool-ralph | 对应 PAEG RALPH 循环（已有，对照增强）| P2 |
| 24 | **Web UI 模式化**：shell/wire/slots 拆分，ui-*.js 插件化 | ui-* 插件 ~30 个 | 09_GUI前端 | P1 |
| 25 | **Preset 即 UI 风格**：预设决定挂哪些 ui-* 模块 | web-app patch | 前端按 preset 挂载 | P1 |
| 26 | **客户端 HMR 热刷新**：dev 模式前端自动刷新 | client-hmr | 09_GUI前端 | P2 |
| 27 | **Self-Update via Patch**：AI 读/写自己 patch 文件（cordis preset 自修改）| tool-cordis | 对应 PAEG self_evolution + tool-cordis 化 | P1 |
| 28 | **Constitutional AI 补丁化**：反思/门禁/重复检测走 patch 配置 | plan-mode + repeat-tool-reminder | quality_gate 配置化 | P2 |
| 29 | **用户级 + Profile 级 + 全局级 Skill 目录** | skill-filesystem customSkillDirs | skill_registry 多目录 | P1 |
| 30 | **Cordis 式 Service Registry**："一切皆 ctx"（llm/sessions/agents/tools/subagents...）| ctx.<key> Service | runtime/registry.py Context | P1 |

**H 表 ↔ #表 对应关系**：H-1↔#15 · H-2↔#2/#7 · H-3↔文档类(新增扩展点映射) · H-4↔#16 · H-5↔#11/#13 · H-6↔#15(context_inject) · H-7↔#21 · H-8↔#9 · H-9↔#12 · H-10↔dsh tool-jobs(独立项) · H-11↔#24/#25 · H-12↔#15/#19 · H-13↔dsh --dump-config(独立项) · H-14↔#16 · H-15↔#15(fork/resume) · H-16↔#28 · H-17↔#2(bundle) · H-18↔#30(effects unwind)

**实施路线（4 阶段，6-10 周）**：
- Phase 1 运行时底座（1-2 周）：#30 Context Registry / #12 LLM Seam / #13 Shell Seam / #15 Session Event Log
- Phase 2 装扮系统（2-3 周）：#1 subagent patch / #2 profile / #3 persona / #7-10 教学预设 / #4-6 条件+overlay
- Phase 3 能力接缝+权限+UI（2-3 周）：#11 三角色 / #14 Tool Registry / #18-20 权限 / #21-23 subagent / #24-26 UI
- Phase 4 元能力+自我改造（1-2 周）：#27 Self-Update via Patch / #28 Constitutional Patch / #29 多级 skill

**证据链接（permalinks）**：架构 [docs/architecture.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md) · Cordis 原语 [cordis-primer.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cordis-primer.md) · 4 预设目录 [agent-presets/](https://github.com/deepseek-ai/deepseek-harness/tree/master/apps/cli/config/agent-presets) · base bundle（~80 插件清单）[base/cordis.patch.yml](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/bundle/base/cordis.patch.yml) · 权限预设 [permission-presets/README.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/interaction/permission-presets/README.md) · 子代理 seam [subagent/README.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/subagent/README.md) · Capability Seams 全图 [capability-seams.md](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/capability-seams.md)

**建议**：本项需求（#1-30）为**长期架构升级蓝图**（6-10 周），建议先实施高价值低成本的 P1 子集：#18 权限预设升级 / #5 home overlay / #9 per-agent scope / #14 tool 元数据按需加载 / #16 hooks 瀑布补全——与当前 §3.28/§3.29 语言规范 MCP + 约束系统工作衔接。

### Step 3：技术说明图表渲染问题（2026-08-14 用户新反馈 · 待技术说明任务处理）

> 用户原话："技术说明的图9，图中元素和背景同为黑色（如，sse输出），因而视觉效果欠佳，请优化" / "增加：技术文档的图15也有同样的问题：深色文字和深色背景在渲染后无法辨认，不可见"

**问题**：Mermaid 图（图 9、图 15）渲染后出现**深色文字 + 深色背景**——元素与背景同为深色（如图 9 的 sse 输出节点、图 15 的对应节点），导致文字无法辨认/不可见。视觉对比度不足。

**修复要求**（并入"技术说明最终任务"，最后做）：
- a. 定位图 9、图 15 的 Mermaid 源码：找出深色文字节点（深色主题色文字/描边）落在深色背景（主题暗色填充）的节点
- b. 修复方式（二选一或组合）：① 给节点显式指定浅色文字/浅色填充（如 `style X fill:#1a1a2e,color:#eaeaea`）② 统一 Mermaid 主题为浅色（theme: base / themeVariables 高对比度）
- c. 全文档巡检：不只图 9/15，扫描全部 Mermaid 图是否存在同类深色文字+深色背景问题，一并修复
- d. 重新渲染 PDF 前完成（该任务属于 §3.30 技术说明最终更新的一部分）

---

## 三、自我更新能力审查与优化（用户新关注 · 重点）

用户关心 PAEG 的大亮点——自我更新能力。需审查：

### 3.1 动态性边界
- agent 能更新到什么程度？哪些可动态，哪些固定？

### 3.2 知识蒸馏（distill_knowledge）—— 需细致审查 + 可联网优化
- 如何实现？教学成功后知识如何入库（evolved_*.json）？
- 质量门禁（Constitutional AI）如何过滤？
- 优化方向：联网检索"知识蒸馏 Agent 最佳实践"

### 3.3 工具经验（learn_tool_lesson）—— 需细致审查 + 可联网优化
- 如何实现？工具调用失败/成功的经验如何沉淀（_compose_lesson/_append_tool_lesson）？
- 优化方向：联网检索"工具使用经验沉淀模式"

### 3.4 Library 更新能力
- 用户上传文档 → 保存在用户个人文件夹 ✅？
- 能否转移到公共目录或相关学科目录？❌ 需检查/实现
- 知识库（KnowledgeBase）如何从用户上传中学习？

### 3.5 教学反思 → 动态系统提示词（用户的核心设想）
- 是否真正进入教学反思？✅（self_evolution.evolve_prompt）
- 能否用 LLM 总结生成**新的动态更新的系统提示词**？✅（_extract_prompt_patch → subject_patches.md）
- **agent 能否自动调取一个 tool 来拼接系统提示词？** ❓ 需检查
- 动态反思的**被隔离的提示词**，每次发送时与**固定系统提示词合并发送**？❓ 需检查（prompt_template.py render_dynamic_slots 机制）
- 用户设想：一个"动态提示词拼接 tool"，把动态反思段 + 固定段合并

### 3.6 自我更新完整链路检查
- self_evolution.py（311 行，4 路：knowledge/prompt/tool/subject）
- reflection_store.py（反思日志持久化）
- SelfUpdateAgent（subagent）
- prompt_template.py（固定块 + 动态槽：STATIC_TEMPLATES + DYNAMIC_SLOTS）

### 3.7 自我更新每一维度优化（2026-08-14 用户明确：每一维度都要优化，且可拓展新维度）

| 维度 | 现状 | 优化方向 | 状态 |
|---|---|---|---|
| 知识蒸馏 distill_knowledge | 教学成功→LLM提炼→门禁→evolved_*.json | 提炼 prompt 优化/门禁增强/去重/闭环使用 | 🔄 审查中（联网）|
| 工具经验 learn_tool_lesson | 工具成败→LLM总结→lesson 落盘 | 经验格式/闭环注入/去重/规模控制 | 🔄 审查中（联网）|
| 提示词补丁 evolve_prompt | 反思→补丁→subject_patches.md | 动态提示词拼接 tool（用户核心设想）| ✅ §3.8 已实现 |
| 学科需求 record_subject_request | 用户问新学科→记录→反馈 | 学科自动创建/知识初始化 | ✅ 核实（periodic subject_requests）|
| 反思闭环（拓展）| reflection_store→SelfUpdateAgent | 反思→优化→验证→再反思（完整闭环）| ✅ 核实（建议回流+反思机制）|
| 记忆分层（拓展）| SESSIONS 短期 + profile 长期 | 独立记忆模块（episodic/semantic/procedural）| ✅ 核实（MemorySystem 三层）|
| 知识老化（拓展）| evolved 无限增长 | 知识时效/淘汰/权重衰减 | ✅ v0.69+ 老化归档已实现 |
| 用户反馈学习（拓展）| 点赞/👎未接入 | 反馈→画像/教学策略调整 | ✅ v0.69+ /api/feedback 已实现（前端 UI 后续）|

### 3.8 动态提示词拼接 tool（用户核心设想 · ✅ 已实现 v0.69+）
- 设想：agent 自动调一个 tool，该 tool 拼接系统提示词——动态反思的被隔离提示词，每次发送时与固定系统提示词合并
- 现状：prompt_template.py 有 STATIC_TEMPLATES（固定）+ DYNAMIC_SLOTS（动态槽）机制
- 缺口：subject_patches（反思补丁）是否作为动态槽注入？是否有专门的"拼接 tool"暴露给 LLM？
- 目标：新增 `compose_dynamic_prompt` tool（config_hub 注册），LLM 可调用，把反思补丁 + 固定段合并

- **实施记录（v0.69+）**：tool_registry 新增内置 compose_dynamic_prompt——LLM 可主动调用，返回 self_evolution 的动态反思补丁（subject_patches 学科补丁/tool_lessons 工具经验/teacher_notes 教师笔记/方法论，经 teaching_memory.load_teaching_memory 聚合），供 LLM 与固定 system 合并。验证：工具集 45 个含该工具，执行返回动态补丁。

### 3.9 AffectionSupportor 引入 WEIL_CORE（2026-08-14 用户新需求 · ✅ 已完成）
- **需求**：倾诉模式（AffectionSupportor）的 system prompt 目前**没有引入 WEIL_CORE**（薇依人格）——用户明确"affection supporter 也应该引入 weil_core"
- **现状（修复前）**：subagents.py 中 AffectionSupportor 有独立的人格（Émile Novis + 手写薇依世界观 5 条 + 约纳斯克制笔法），**不含 WEIL_CORE 完整常量**；且 **TRUTH_GROUNDING 防幻觉底线也未覆盖倾诉模式**
- **实施（v0.68+，commit d840eb7）**：三处注入——①`from prompts import WEIL_CORE, TRUTH_GROUNDING`（run 方法局部导入）②身份声明后注入完整 WEIL_CORE（身份三层/薇依底色/核心信念，2461 字符）③system 收尾注入 TRUTH_GROUNDING（防幻觉底线 3206 字符）
- **验证**：语法 OK + 静态注入确认 + 真实端到端 /api/affection 调用（回复正常，薇依人格风格，无伪共情动词）
- **注意**：WEIL_CORE 与现有手写"底层世界观"互补不冲突（场景定位 vs 人格内核）；倾诉"不教不答不解决"约束不受影响

---

## 四、需求清单（完整记录：已完成 / 进行中 / 新增）

### 3.10 哲学学科专项教学能力：文献论证结构 + 概念分析方法论（2026-08-14 用户新需求 · ✅ 已完成 v0.68+）
- **需求**：为高中/大学本科/考研哲学教学增加能力——将哲学文献阅读方法完善为**系统提示词片段**纳入
- **目标学段**：高中 / 大学本科 / 考研
- **实现方式**：完善系统提示词纳入（哲学学科专用提示词片段，作为 subject 专项能力注入）
- **用户提供的文献阅读要求（需完整纳入）**：
  1. **论证结构分析**：划分章节论证结构——要说明的问题/目的、从何出发、如何得到结论；以哪些段落-所属哪一部分论证过程-本阶段的论证方式组织回答；**避免表格**，用分段文字；所有概念、论证**必须来自原文**，**禁止比喻/隐喻/引用/类比**方式输出答案
  2. **概念分析（哲学阅读基础）**：整理本章重要概念——全面透彻把握作者使用的所有关键概念；准确理解作者对概念的阐释；注意**概念与概念的区分、概念之间的关系、概念对子**；使用**技术方法做概念分析**
  3. **目的**：深度思考，使学习者能准确把握概念、完整观看论证过程、理解作者问题意识
- **调研项**：哲学学科目前在教学 subagent（Presenter）下的专项实现现状——学科方法论映射/专门提示词/学段差异（高中/本科/考研）如何实现？college_physics 有拆键，哲学是否有类似机制？
- **优先级**：P0（用户明确要求，先入清单再执行）

- **实施记录（v0.68+）**：①SUBJECT_STYLES[philosophy] 新增 method_guide（文献论证结构分析 A 六步 + 概念分析 B 六步，含反教条可偏离句式）+ worked_example（柏拉图洞穴寓言完整论证解构）②SUBJECT_GRADES 解锁 graduate_exam 考研档 ③SUBFIELD_TREE 新增 philosophy 三学段二级学科（高中 2/本科 6/考研 4）。验证：py_compile OK + build_presenter_system(philosophy) 真实注入（论证结构段/洞穴寓言/概念分析均 True）

### 3.11 教学能力结构化：教育知识与能力体系纳入教学 subagent（2026-08-14 用户新需求 · ✅ 核心已实现 v0.69+）
- **需求**：教学模式更专业——联网检索教育知识与能力（教师资格证考试体系），将**教学能力结构化**，纳入教学 subagent（Presenter）
- **关键探索**：**系统提示词 vs skill 两种方式哪种更合适**（需评估：注入时机/上下文成本/可维护性/可复用性/学习者适配）
- **目标**：教师专业能力结构化进入教学流程（教学设计/教学实施/教学评价/学科教学法/学情分析/教育心理学应用等）
- **调研项**：①教育知识与能力体系结构（教资科目二：教育学原理/心理学基础/教学法/德育/班级管理/教学评价等模块；以及教师专业标准/TPACK/ADDIE 教学设计模型）②项目内现有教学能力组织（skill 目录/essay-feedback/方法论文档/提示词字段 method_guide/worked_example）③提示词 vs skill 的优劣对比（上下文预算/LLM 注意力/维护性）
- **⭐ 反教条设计约束（2026-08-14 用户重点强调）**：**不能把教学能力当作教条，对 LLM 施加不合理约束，导致教学模式输出刻板内容**——因材施教和变化本身就是教学能力的要求。教学能力结构化必须遵循：①能力是判断准则/可选工具箱而非必须执行的步骤序列②任何教学流程/步骤注入时须附何时可偏离的弹性说明（学情/学科/情境决定）③结构化服务于诊断（用什么方法教这个学生）而非输出格式化（机械套模板）④LLM 保留最终教学判断权——结构是脚手架，不是牢笼
- **设计咨询**：已咨询 Oracle（2026-08-14）评估结构化但非教条的实现路径
- **调研结论（2026-08-14，三份并行：Oracle 设计 + skill 机制探索 + 联网教育体系检索）**：
  1. **体系来源**：教资科目二 8 模块（教育基础/课程/教学/学习心理/发展心理/心理辅导/德育/班级管理）+ 教师专业标准 6 能力（教学设计/实施/评价/班级管理/人际/自我发展）+ 国际模型（ADDIE/加涅九事件/布卢姆/TPACK）+ Berliner 五阶段（分层介入强度而非身份标签）
  2. **承载方式结论（Oracle 推荐）**：**skill 化为主 + 诊断阶段轻量注入为辅**——三层组织：L1 能力地图（~200 字短句，plan 阶段注入）/ L2 判断准则（按需 skill 调用）/ L3 案例锚点（skill 正文）。理由：skill 调用是 LLM 主动行为（参考而非服从）；system prompt 注入有权威效应易被当执行清单；实施阶段不重复注入避免膨胀
  3. **反教条落地**：判断准则用何时做/何时可偏离格式；写作禁忌（禁必须/务必开头、禁编号流程 1-2-3-4、禁先...再...然后...）；因材施教用双层（静态学段 learner_default + 动态 learner_profile）；adapt_directives 用具体动作（本轮减少类比）而非灵活处理
  4. **项目 skill 机制现状**：三级渐进（L1 目录注入 catalog_prompt / L2 activate 全文 / L3 子资源）；config/skills 空目录为私有预留；现有 10 skill 全被动加载；SUBJECT_STYLES 有死字段（error_correction 等 6 字段定义未渲染——**新增字段须确认渲染逻辑**）
  5. **四层能力架构建议**：L1 专业约束（目的/师德/安全）/ L2 专业能力（学情/目标/设计/实施/评价/沟通/反思）/ L3 教学流程（ADDIE+加涅+布卢姆）/ L4 学科与情境适配（TPACK+学科教学法+学情差异）
- **优先级**：P0（用户明确要求，先入清单再执行）

### A. 已完成需求（历史全部，v0.5 → v0.68）

| ID | 需求 | 状态 |
|---|---|---|
| DONE-1 | 9 子代理架构（Diagnostor/Planner/Presenter/Evaluator/Adapter/AnswerSolver/AffectionSupportor/SelfUpdateAgent/Individuality）| ✅ |
| DONE-2 | 六阶段教学闭环（诊断→计划→呈现→评估→调整→反思→自更新）| ✅ |
| DONE-3 | 17 维画像 + BDI + 三层记忆 + 问卷 | ✅ |
| DONE-4 | meta_router 意图路由（v0.26 LLM 优先 → v0.35 15 意图）| ✅ |
| DONE-5 | 语言规范层（language_refiner L1/L2/L3）| ✅ |
| DONE-6 | 四路自我进化（知识/提示词/工具/学科）| ✅ |
| DONE-7 | MCP 双向打通（filesystem/memory/pptx）| ✅ |
| DONE-8 | 深度思考接入（SUBAGENT_THINKING_LEVELS + ReasonerModelAPI）| ✅ |
| DONE-9 | 视频融合管线（讲义→讲稿→PPT→manim→视频）| ✅ |
| DONE-10 | 学习计划工作流（planner.py + 推荐资料附录）| ✅ |
| DONE-11 | config_hub 统一配置中心 + hooks_hub + workflows_hub | ✅ |
| DONE-12 | 能力清单注入 + 意图→能力 hint + Presenter 工具透传 | ✅ |
| DONE-13 | v4-flash 思考空响应修复（thinking:disabled + max_tokens 4000）| ✅ |
| DONE-14 | DeepSeek Harness 学习（经验文档/技术§10.15/教材附录C/需求清单）| ✅ |
| DONE-15 | 学习体验修复（习题册正文/1500字/college_physics/method_guide/worked_example/deep_think）| ✅ |
| DONE-16 | 倾诉语言修复（分量替换/随机开头/词汇多样/重复检测）| ✅ |
| DONE-17 | 画像缓存 bug 修复（_learner_session 重新水合）| ✅ |
| DONE-18 | 学习计划附录修复（去 emoji + refiner 保留结构 + polish 后拼回）| ✅ |
| DONE-19 | 进程管理 SOP（技术§10.16 + 元能力§6.56）| ✅ |

### D. 历史 bug report 档案（2026-08-14 用户要求重点记录，4 份完整报告）


> 用户报告 → 根因 → 修复 → 验证，全部可追溯。对应 DONE-12/15/16/17。

**Bug-Report-1：画像暂无学习记录（DONE-17）**
- 用户报告：web 端学习者画像显示暂无学习记录，但实际已有教学记录
- 根因：_learner_session 缓存未重新水合——服务器重启后画像读旧缓存，新会话记录不写回
- 修复：画像读取时用最新 session 数据重新水合缓存
- 验证：画像正确显示学习记录

**Bug-Report-2：教学效果不满意 / 学习体验差（DONE-15）**
- 用户报告：教学效果不满意，学习体验差
- 根因：多因素叠加——习题册正文未接通（read_user_corpus 缺失）；输出 300 字过短；max_tokens 不足；college_physics 未拆键；缺 method_guide/worked_example；teach 未走 deep_think
- 修复：接通习题册正文 read_user_corpus + 300→1500 字 + max_tokens 2000 + college_physics 拆键 + method_guide/worked_example + teach deep_think
- 验证：教学输出显著改善

**Bug-Report-3：倾诉语言生硬（DONE-16）**
- 用户报告：倾诉（AffectionSupportor）语言生硬
- 根因：很重歧义（分量/担子被 LLM 理解偏差）+ 回复模板化（开头单一、词汇重复）
- 修复：分量/担子替换 + 随机开头 + 词汇多样 + _check_word_repetition 查重
- 验证：倾诉回复自然多样

**Bug-Report-4：Agent 不够智能 / 不知道自己有哪些能力（DONE-12）**
- 用户报告：agent 不够智能——用户不点按钮/不说关键词时，agent 不会主动按指令完成工作（如做视频/动画/PPT）；agent 自己不知道自身能力清单
- 根因：系统提示词未注入能力清单；意图→能力映射缺失；Presenter 工具未透传
- 修复：_build_capability_manifest 能力清单注入 + INTENT_TO_CAPABILITY_HINT 意图→能力映射 + Presenter tools 透传
- 验证：agent 能主动识别意图并调用对应能力/工具


### B. 进行中需求（ULW 主任务）

| ID | 需求 | 状态 |
|---|---|---|
| ULW-1 | Step 1 五维度基线盘点 | ✅ |
| ULW-2 | Step 1.5 harness 插件选取（记来源）| ✅ Permission Preset + repeat-tool-reminder |
| ULW-3 | Step 2 ForMaitenance 文件夹 + 各维度质量文档 + 移入维护文档 | ✅ |
| ULW-4 | Step 3 自检修补 | ✅ G1-G8 全闭环 |
| ULW-5 | Step 4 接口完整性检查 | ✅ 12 断链 P0/P1/P2 全修复 |
| ULW-6 | Step 5 runoob 7 篇逐字阅读 + 评估改造 | ✅ 7/7 已读 + 对照落盘 |
| ULW-7 | 九模块底座对照评估 | ✅ §3.12 已固化+核实 |
| ULW-8 | 发布 release 或修复 P0-P2 | ✅ v0.69.0 Release 已发布 |

### C. 自我更新优化需求（用户重点关注）

| ID | 需求 | 状态 |
|---|---|---|
| SEL-1 | 知识蒸馏审查+优化（**审查完成：Explore G1-G11 + Librarian 最佳实践**，待实施）| 🔄 |
| SEL-2 | 工具经验审查+优化（同上）| 🔄 |
| SEL-3 | 提示词补丁优化 + 动态提示词拼接 tool | ✅ §3.8 compose_dynamic_prompt 已实现 |
| SEL-4 | 学科需求自动创建/知识初始化 | ✅ 核实（periodic subject_requests 已实现）|
| SEL-5 | 反思闭环（反思→优化→验证→再反思）| ✅ 核实（_safe_chat 反思 + 建议回流）|
| SEL-6 | 记忆分层 | ✅ 核实已实现（MemorySystem 短期/中期/长期 + 摘要压缩；episodic 等语义分类为可选增强）|
| SEL-7 | 知识老化/淘汰 | ✅ 已实现（v0.69+ evolved 日文件 >90 天归档 Archive/，保留历史不删）|
| SEL-8 | 用户反馈学习（点赞/👎→画像/策略）| ✅ 完整实现（v0.69+ /api/feedback + 前端消息气泡 👍/👎 按钮 → feedback_log.jsonl，端到端可用）|
| SEL-9 | Library 更新：用户上传 → 公共/学科目录转移 | ✅ 核实（/api/upload purpose=library）|
| SEL-10 | 自我更新完整链路验证 | ✅ **真实端到端验证通过**（v0.69+ 真实 LLM：教学会话→distill 蒸馏→evolved_20260814 写入→G3 热加载→KB 检索命中；牛顿第一定律节点定义准确）|

**自我更新审查发现（2026-08-14 Explore 逐行审查，11 个闭环缺口）**：

| 缺口 | 描述 | 优先级 |
|---|---|---|
| G1 | distill_knowledge 仅同步 /api/teach 触发 | **✅ 已修复**（v0.68+ 2026-08-14 用户方案：自我更新与流式无关——teach_stream done 后从完整对话历史抓取 → SimpleNamespace 构造 session → EVOLVER.distill_knowledge；SSE 端到端验证通过，avg>=0.7 门槛静默拒绝属正常）|
| G2 | skip_sandbox 绕过 L4 实证 | **✅ 已修复**（v0.68+ 澄清：L3 LLM factuality 事实评分始终执行；skip_sandbox 仅跳过 L4 证据累积；双信号=教学评分+L3 事实评分；注释纠正误导）|
| G3 | evolved_*.json 写入后无热加载，KB 重启才可见 | **最高 → ✅ 已修复**（reload_library）|
| G4 | 工具经验 success 判定过粗 | **✅ 已修复**（v0.69+ 失败信号词集：错误/失败/无法/不存在/未找到/异常/error/failed/not found/unable/超时/timeout，判定逻辑验证通过）|
| G5 | 教学路径（Presenter/teach_stream）不注入 tool_lessons/subject_patches | 高 → ✅ 已修复（Presenter 注入教学记忆）|
| G6 | _compose_lesson 无 LLM 提炼 | **✅ 已修复**（v0.68+ LLM 提炼工具经验：适用场景/要点/误区/替代方案，模板兜底；无 LLM 或提炼失败回退模板）|
| G7 | 蒸馏节点无去重/版本化 | **✅ 核实已满足**（_append_evolved_node 用 dict——同 id 自然覆盖去重；知识蒸馏覆盖=版本更新，合理）|
| G8 | tool_lessons.md 无限增长 + 老经验沉没 | **✅ 已修复**（v0.69+ 超 40KB 截断保留最近 30 条，防无限增长+防老经验沉没）|
| G9 | SelfUpdateAgent 建议无自动派发 | **✅ 核实已实现**（periodic_self_update 建议回流：self_update_suggestions.jsonl → improvements.md）|
| G10 | reflection_store(SQLite) 与 self_evolution(md/json) 隔离 | **✅ 核实为设计**（SQLite=反思日志 vs md/json=演化数据，隔离是刻意的）|
| G11 | suggestions.jsonl 堆积不消费 | **✅ 核实已实现**（v0.24 建议回流 + processed.jsonl 去重标记）|

**知识蒸馏最佳实践（Librarian 联网检索，Voyager/Reflexion/MemGPT/A-MEM/ExpeL/ReasoningBank/Constitutional AI）**：
- L0：提炼 prompt 加 JSON Schema + CoT（+30% 质量）
- L0：metadata 字段（subject/grade/type/tags/importance）→ 检索召回 +50%
- L1：三阶段门禁（硬规则→Constitutional→动态评分，ExpeL importance count）
- L1：**失败案例也提炼**（pitfall/anti_pattern，ReasoningBank 反直觉：失败是高质量知识源）
- L2：embedding 去重 + supersession（soft_delete 不硬删，Hindsight）
- L2：KnowledgeRetriever 多路召回 + 注入教学 prompt（Voyager top-5）
- L3：使用闭环追踪（use_count→importance 衰减，防"蒸馏了没人用"）

**工具经验最佳实践**（Librarian 检索中，部分完成）：参考 ExpeL trajectory + Toolformer/TALM——经验应结构化（tool/scenario/lesson）+ 失败模式 LLM 抽象 + 注入工具选择逻辑

### D. 新增任务（2026-08-14 用户要求至少 5 条，基于项目了解）

| ID | 需求 | 理由 |
|---|---|---|
| NEW-1 | **记忆系统强化**：独立 memory 模块（短期对话/长期画像/语义知识分层），参考 MemGPT 分层 | runoob 文档强调"记忆是三大组成之一"，当前记忆散落 SESSIONS/profile |
| NEW-2 | **上下文工程优化** | ✅ 基本满足（context_bundle.py 6 函数统一入口，server 3 处+subagents 6 处引用；全量统一为后续）|
| NEW-3 | **工具链闭环验证** | ✅ 已完成（v0.69+ 工具集 45 端到端回归：agent 模式 9 阶段/teach/chat 全通过，MCP/skills/workflows 可见可调）|
| NEW-4 | **输出质量评估体系** | ✅ 核心已实现（quality_gate L3 LLM 多维评分：factuality/safety/pedagogy 阈值；对话/知识蒸馏评估已接，PPT/视频评估为后续）|
| NEW-5 | **错误处理审计** | ✅ 已实现（audit_check.py 27.9KB 全项目检查 + hooks_hub timeout 语义日志 + G4 判定信号词）|
| NEW-6 | **知识库可扩展性** | ✅ 基础已实现（subjects_ext.py 48 扩展节点 + evolved_*.json 动态注入 + G3 热加载；新学科动态创建为后续）|
| NEW-7 | **安全工程补强**：工具级 Permission Preset（考试模式锁定写工具）| Oracle 检视 P0-4，教育场景硬卖点 |
| NEW-8 | **教材同步**：将自我更新/记忆/上下文工程的新实现写入《用智能体开发智能体》| 教材是活文档 |
| **NEW-9** | **⭐ 防幻觉底层约束（用户最高优先）✅ 已完成**：TRUTH_GROUNDING 常量（10 条底线：不编造/信源为绝对命令/先证据后结论/允许说不知道）+ 注入 build_presenter_system + build_general_chat_system + _safe_chat 兜底（幂等）| 对应 runoob 防幻觉五策略；用户"最底层不可放弃" |

---

## 五、当前技术状态快照（2026-08-14 · v0.70）

- **版本**：v0.70（server.py version 待 bump；§3.28/3.29 已实施）
- **语言规范 MCP（§3.28 ✅）**：lang_gate_content 统一入口（13 处收敛）+ forbidden_words.json 数据化（内嵌 577 项去重 555 + 外部 18）+ 三工具（normalize_text/language_policy_check/forbidden_words）
- **约束引擎（§3.29 ✅）**：constraint_engine.py 6 API（layer_get/set/compose/always_active/self_evolve/feedback_adjust）+ 数据化（constraint_layers.json/always_active.json/constraint_feedback_log.jsonl）
- **工具集**：54 个（内置 19 + MCP + skills + workflows，无重复）
- **config_hub**：统一配置中心（MCP/skills/hooks/workflows 四子模块 + get_all_tool_defs/execute_tool）
- **hooks_hub**：waterfall+next/matcher/verdict 合并/timeout/legacy_adapter
- **workflows_hub**：teach_minimal + teach_concept（DAG 拓扑执行）
- **meta_router**：15 意图 LLM 优先 + capability_hint（意图→能力）
- **subagents**：9 subagent + SUBAGENT_THINKING_LEVELS + _build_capability_manifest（能力清单注入）
- **学习计划**：planner.py（StudyPlan）+ 推荐资料附录（确定性渲染）
- **自我更新**：self_evolution.py（4 路进化）+ reflection_store + SelfUpdateAgent + RALPH 循环
- **记忆**：SESSIONS（短期）+ LearnerProfile/画像（长期）+ 三层记忆
- **动态提示词**：prompt_template.py（STATIC_TEMPLATES 固定 + DYNAMIC_SLOTS 动态槽）+ compose_dynamic_prompt tool
- **DeepSeek Harness 借鉴（§二 Step 2 ✅）**：30 项优化需求已记录（P0/P1/P2 + 4 阶段路线），H-1~H-18 速查表
- **测试**：42 工具相关测试全过（skill 11 断言/MCP 实际 API 已更新）

---

## 六、操作流程（每次操作前必读）

1. **任务核对**（规范 §8）：操作前先读本文件，确认当前焦点任务（B/C/D 区）与相关规范，再动手
2. 按优先级执行：D 新增任务 → C 自我更新 → B ULW → 按 NEW 清单从上到下
3. 每完成一项，更新本文件状态（✅/🔄/⏳）——**不批量，实时更新**
4. 所有调研**细致**（读全文/全代码，逐条记录），不满足于大概
5. 借鉴外部项目**记录来源**（§二 DeepSeek Harness 学习）
6. **完成验证**（规范 §9）：语法通过 + 测试通过 + 真实调用返回 + 文档落盘，无证据 = 未完成
7. **调研落盘**（规范 §10）：调研产出存 ForMaitenance 或对应目录
8. **进程管理**（规范 §11）：改代码后按技术 §10.16 重启流程
9. 重大改动后：回归验证（学习计划/核心功能）→ 更新技术状态快照（§五）
6. 重大改动后：语法验证 → 重启（按 §10.16 进程 SOP）→ 回归
- **实施记录（v0.69+）**：①新建 skills/teaching-capability/SKILL.md——教学专业能力判断库（能力地图 6 领域/学情诊断何时做/目标-活动-评价一致性/节奏调控/三层评价/教育心理学边界/因材施教/TPACK 检查/防刻板元规则），反教条句式（判断工具不是执行清单允许偏离因材施教不作免责声明）②注册验证：11 技能，L2 激活 1991 字符，目录可见 ③承载方式按 Oracle 推荐：skill 化为主（按需加载防僵化）；L1 能力地图轻量注入 build_presenter_system 列为后续增强

### 3.12 Step4 九模块底座评估结果：诊断→计划闭环 + 画像驱动（2026-08-14 Oracle 评估 · 待实施）
- **九模块成熟度（Oracle 对照评估）**：Interaction 中 / Profile 中 / **Diagnosis 弱** / Plan 中 / Action 强 / Evaluation 中 / Adaptation 中 / Knowledge 强 / Output 强
- **诊断→计划闭环：✅ 已实现（修正 Oracle 误判）**——paeg.teach 已串联 Diagnostor.run → planner.run(diagnosis=session.diagnosis) → choose_strategy(learner, diagnosis, subject) 差异化步骤；Oracle 评估基于简化输入，实际闭环已通
- **画像驱动：✅ 已补（v0.69+）**——choose_strategy 此前接收 learner 但未用画像维度；已增加画像分支（学段 graduate_exam→socratic / 初高中技能→mastery / 目标考试→socratic / 认知风格具体偏好→scaffolded），诊断/学科规则优先、画像兜底 default 场景
- **次痛点：17 维画像 + BDI 仅声明未被下游消费**——Planner/Presenter 不读画像（个性化是文案而非机制）
  - 改动：Planner 入参增 LearnerProfile（按先验/动机分支）；Presenter 读 learning_style；画像陈旧触发轻量诊断
- **其他薄弱点核实（v0.69+ 全部完成）**：**交互式教学**（提问-等待-追问循环——唯一真实架构级缺口，后续改造 Presenter 循环）；**效果评估 ✅ 已覆盖**（Evaluator learner_state 0.4 权重 + _student_signal 理解度/困惑/参与信号——Oracle 误判）；**知识依赖图 ✅ 已存在**（33 处 prerequisites+leads_to，Diagnostor 已用）；**实时自适应 ✅ 基础已有**（能力清单看不懂→换例子重讲）
- **优先级**：诊断闭环 > 画像驱动（影响所有学习者 vs 老用户更显著）

### 3.13 Step4 接口完整性检查：12 处断链（2026-08-14 explore 全链路核对 · P0 待修）
- **最严重**：config_hub.execute_tool() 与 hooks.run_hook() **全项目无调用方**——v0.68 独立配置体系未真正接入运行时，仍走 tool_registry 旧路径
- **P0-1**：config_hub.execute_tool 零调用方 → **✅ 已修复**（v0.68+ run_agent_loop else 分支改调 get_hub().execute_tool，含回退；repeat_guard/workflows 路由解锁并验证）
- **P0-3**：workflows 最后一公里断裂 → **✅ 已修复**（v0.68+ get_tool_defs 合并 _extended_tool_defs：内置7+skills10+MCP25+workflows2=44 无重复；修复递归守卫+list()dict 解析+内置去重）
- **P0-2**：hooks 7 事件全无触发点 → **✅ 已修复**（v0.68+ 内置 log_hook + config/hooks.json 5 个 log hook + teach_stream 入口触发 session.start/message.before_user、done 后 message.after_assistant；日志验证 learner=hook_final 触发；reload 响应验证 loaded:true）
- **P0-3**：workflows 最后一公里断裂（meta_router.INTENT_TO_CAPABILITY_HINT.auto_tools 无消费者，LLM 看不见 run_workflow__*）→ 修复：teach 端点消费 capability_hint
- **P0-4**：config_hub.reload_all 无调用 → **✅ 已修复**（v0.68+ /api/admin/reload 端点，返回 hooks 加载状态）
- **P1-1~6 全部 ✅ 清零（v0.69+）**：hooks.json 5 hook / mcp 副本删除 / skill 注入统一 inject_catalog / 工具集 44 覆盖 / 工具提示动态生成 / answer skill 注入
- **P2-1~2**：transport 复用仅同 async 块（P2-1 待优化）/ tool_registry 与 config_hub 双路径行为不一致（✅ P2-2 已统一：mcp__ 优先走 config_hub 触发 hooks，回退直连）
- **优先级**：P0-1 → P0-2 → P0-3 → P0-4（修复后跑 smoke_test + 端到端）

### 3.14 v0.69.0 Release（2026-08-14 ✅ 已发布）
- **tag**：v0.69.0（GitHub origin 推送成功：master + tag）
- **内容**：自我更新闭环（G1/G2/G3/G5/G6）+ 配置体系运行时接入（Step4 P0-1~4）+ 哲学专项 + 防幻觉 + AffectionSupportor WEIL_CORE + 执行纪律 15-19 + bug report 档案 + CHANGELOG v0.69
- **ModelScope 结论（2026-08-14 最终）**：远程 3 个平台端 Dockerfile 提交（10c8494/c44811e/e49107c）——force push 被平台 pre-receive hook 拒绝（保护机制）；ModelScope 保持现状，**GitHub 为权威完整源**（v0.69.0 tag + 全部提交）；如需同步 ModelScope 需用户联系平台解除 hook 或手动 merge
- **后续**：P1×5（mcp_servers 双份/skill 注入重复/teach+answer 工具集/手工工具列表/answer 无 skill）+ P2×2 + §3.12 诊断闭环与画像驱动

### 3.15 用户新批次任务（2026-08-14 ULW 四连 · 待执行）
- **T1 Dockerfile 对比覆盖**：✅ 已确认（v0.69+ 本地 Dockerfile/docker-compose/.dockerignore 哈希与远程最新 10c8494 完全一致——本地即最新含 Pango/GLib 修复；远程 3 提交是平台端历史演进，最终版已同步本地，无需覆盖）
- **T2 运行卡住原因→执行标准**：✅ 已完成（纪律 20：5 类根因——残留进程/LLM 超时/SSE 挂起/工具阻塞/网络 + 诊断顺序先进程→再缓存→最后代码）
- **T3 DeepSeek Harness 模块引入（完整调研 · 2026-08-14 完成调研，待实施）**：调研 DeepSeek Harness github 库，把**在 agent 中引入同样的模块**加入需求文件。完整 packages 清单见下方 §3.16。
- **T5 RALPH 循环能力 · ✅ 核心已实现（v0.69+）**：①记录入需求文件+元能力 §5.3 ✅②Oracle 设计已落地——新增 ralph/ 子系统（loop_controller/task_registry/completion_evaluator/termination_guard/contracts），端到端验证 DONE（2 轮达标+快照+日志）③已记录：技术/维护/CHANGELOG/README/亮点总览。P1/P2 后续：Web UI/优先级队列/人类确认点 UI/周度适配器。
- **T5 RALPH 循环能力（2026-08-14 用户新增）**：**RALPH 循环本身是重要能力**——①记录 RALPH 循环（自我指涉开发循环：持续推进直到完成，每轮输出 DONE promise，系统自动续触发）到需求文件 + 元能力文档②**咨询 Oracle 补全 PAEG 的 RALPH 循环能力**（如何让 PAEG agent 具备自我驱动持续工作直到完成的循环能力——融入自我更新/任务执行）③完成后记录：技术文档、维护文档、README、**亮点文档**
- **T4 执行存量需求 · ✅ 核对完成（v0.69+）**：P1-1~6 全清零 ✅ / P2-2 双路径统一 ✅ / P2-1 transport 复用（性能优化，与 §3.16 P2 观望合并）/ §3.12 五项核实+实现 ✅（交互式教学完整循环为架构级后续）/ §3.16 P0 四项：ralph ✅（ralph/ 子系统）+ **spill ✅ 已实现**（v0.69+ config_hub 溢出截断 12000 字符，验证通过）+ **user-approval ✅ 核实由现有机制覆盖**（Permission Preset 4 档 + hooks tool.before 拦截，hooks.json 可配确认）+ **compaction ✅ 核实已覆盖**（memory_system 摘要压缩 compress_if_needed）——§3.16 P0 全部完成

---

### 3.16 T3 深度调研产出：DeepSeek Harness 完整模块清单与 PAEG 引入候选（2026-08-14）

> 来源：本地克隆 `D:\wbo-workspace\deepseek-harness-research\dsh\`（已校验）+ GitHub `deepseek-ai/deepseek-harness` 公开 README/packages 索引
> 调研方法：遍历 `packages/` 下 41 个顶层分组 / 167 个子包，按 README 提取语义；对照 PAEG 现有 80+ Python 模块做映射

#### 一、Harness 完整顶层分组（41 组）

| # | 分组 | 子包数 | 角色 |
|---|---|---|---|
| 1 | `core/` | 8 | 产品 API 脊柱：session / system-prompt / tools / agent / agent-loop / scope / agent-default-model / agent-tool-presentation |
| 2 | `llm/` | 5 | LLM 能力族：seam + DeepSeek/pi-ai adapter + token-meter + retry |
| 3 | `shell/` | 9 | Bash 能力族：executor seam + local/pwsh provider + 4 个工具 |
| 4 | `fs/` | 7 | 文件系统能力族：seam + local + observation-policy + sandbox + 3 工具 |
| 5 | `subprocess/` | 2 | 子进程能力族（local process-tree provider）|
| 6 | `terminal/` | 3 | 持久 PTY 能力族（owner-scoped session）|
| 7 | `code-runtime/` | 2 | 代码执行能力族（worker-thread runtime）|
| 8 | `sandbox/` | 4 | **进程隔离沙箱**（bwrap/Landlock/Seatbelt/Windows-ACL）|
| 9 | `lsp/` | 3 | LSP 能力族（go-to-def / find-ref / hover 语义）|
| 10 | `mcp/` | 1 | MCP client bridge（外接 stdio/HTTP MCP server）|
| 11 | `skill/` | 4 | 技能注册表 + filesystem provider + tool |
| 12 | `compaction/` | 4 | **上下文压缩**能力族（token-meter + LLM summarizer）|
| 13 | `spill/` | 3 | **工具输出溢出防护**（spill store + policy）|
| 14 | `web/` | 5 | Web 能力族：search/fetch seam + Exa/Perplexity/DeepSeek/Http provider |
| 15 | `context/` | 4 | 模型可见上下文：AGENTS.md 加载 / 时间 / tmux / session-reference |
| 16 | `subagent/` | 11 | **子代理能力族**：registry + spawn/fork/ACP/Codex/Claude/dsh-sdk provider + 3 工具 |
| 17 | `workflow/` | 4 | **工作流编排**（worker-thread 引擎 + workflow/ralph 工具）|
| 18 | `jobs/` | 3 | 后台 job 运行时（owner-scoped long-running task）|
| 19 | `goal/` | 4 | **同 session 目标持久化**（goal domain + round driver）|
| 20 | `schedule/` | 1 | **会话级定时提醒**（schedule_create/list/delete）|
| 21 | `todo/` | 1 | 模型可见 `todo_write` 工具 |
| 22 | `plan/` | 1 | **Plan 协作模式**（`/plan`/`exit_plan_mode`）|
| 23 | `preset/` | 2 | Preset 系统（agent-presets / persona shadowing）|
| 24 | `guard/` | 2 | **循环卫生守卫**（repeat-tool-reminder / timeout-policy）|
| 25 | `bundle/` | 3 | 可安装 profile bundle（base / web-app / headless）|
| 26 | `extensions/` | 4 | Agent 自修改工具（runtime 检视/mount/unmount plugin）|
| 27 | `hooks/` | 3 | **Hook 桥**：claude-code / codex / shared protocol |
| 28 | `session/` | 13 | 会话持久化层（JSONL/SQLite）+ 投影 + 标题 + 统计 + 遥测 OTel |
| 29 | `session-query/` | 4 | **会话检索**（SQLite FTS + lineage + 关系图）|
| 30 | `settings/` | 2 | 用户设置 seam（file provider）|
| 31 | `credentials/` | 2 | 凭据引用 seam（env/.env provider）|
| 32 | `storage/` | 4 | 非会话存储 hub（json/sqlite + storage-domain）|
| 33 | `identity/` | 1 | 匿名 user id（UUID v4 持久化）|
| 34 | `interaction/` | 5 | **人机协作平面**：approval / ask-user / commands / permission-presets / user-questions |
| 35 | `attachment/` | 2 | 持久附件（图像字节验证 + content-addressed 存储）|
| 36 | `runtime-diagnostics/` | 1 | 运行时不变量（invariants companion）|
| 37 | `feedback/` | 2 | 反馈记录（`/feedback` + 消息级 message-feedback sidecar）|
| 38 | `acp/` | 1 | Agent Client Protocol（自动化 JSON-RPC stdio）|
| 39 | `host/` | 8 | Web-GUI 后端：API gateway + webserver + static + directory-picker + plugin-inventory |
| 40 | `client/` | 42 | Web-GUI 前端（shell/runtime/modules + 35 个 ui-* 子包）|
| 41 | `util/` | 8 | 零依赖工具（atomic-write / brand / home-paths / timeout / output-retention 等）|

#### 二、PAEG 已引入清单对照（基线 · v0.69+）

| PAEG 模块 | 对应 Harness | 状态 |
|---|---|---|
| `config_hub.py` | `core/agent-default-model` + `preset/agent-presets` 的 patch 层思想 | ✅ 已实现（Patch Layer / 4 档权限）|
| `hooks_hub.py` | `hooks/hook-protocol` | ✅ 已实现（waterfall + matcher + verdict 合并）|
| `workflows_hub.py` | `workflow/workflow` | ✅ 已实现 MVP（plain JS 脚本 DSL）|
| `subagents.py`（9 subagent）| `subagent/subagent-spawn-in-process` | ✅ 已实现（单进程 spawn 派生子代理）|
| `expert_guard.py` | `guard/repeat-tool-reminder`（启发式部分）| ✅ 已实现（v0.69+ 重复工具提醒）|
| `tool_registry.py` | `core/tools`（部分）+ `interaction/permission-presets`（4 档）| ✅ 已实现（4 档风险分级）|
| `mcp_client.py` / `mcp_gateway.py` | `mcp/mcp-client` | ✅ 已实现 |
| `skill_registry.py`（10 skill）| `skill/skill`（provider 抽象思想）| ✅ 已实现 |
| `llm_api.py` / `llm_adapter.py` | `llm/llm-deepseek` | ✅ 已实现（DeepSeek 适配）|
| `context_bundle.py` / `context_manager.py` | `core/system-prompt` + `core/scope` 思想 | ✅ 已实现（上下文打包契约）|
| `safety.py` | `runtime-diagnostics/invariants` 思想（部分）| ✅ 已实现（粗粒度）|
| `session_model.py` | `core/session`（部分：thread/turn/item 三层）| ✅ 已实现 |
| `observability.py` | `session/session-telemetry`（轻量版）| ✅ 已实现 |

#### 三、未引入候选模块清单（按价值排序 · 11 项）

> 评估维度：**①PAEG 痛点匹配度 ②实施复杂度（低/中/高）③教育领域独特价值**

##### 🔴 P0 高价值（首批必做 · 4 项）

| # | Harness 包名 | 功能说明 | PAEG 对应物 | 引入价值 | 建议方式 |
|---|---|---|---|---|---|
| 1 | **`compaction/compaction-basic`** + **`compaction/compaction-tool-result-pruner`** | 上下文压缩：当 token 接近模型上限（默认 0.8 阈值）自动调用 LLM 总结旧历史 + 裁剪超大工具结果；保留原始事件在日志（replay-safe） | **无**（PAEG 长 session 易爆 LLM 上下文；只能靠对话长度限制 + 简单截断） | **极高**——教育场景多轮 35 学科 × 学段联动极易超限；防止"后面忘了前面"的工程级解决方案 | **新增模块** `services/compaction.py`：用 token-meter 测压 → 触发总结 → shadowed region + checkpoint；写回 `core/session` 日志 |
| 2 | **`spill/spill-policy`** + **`spill/spill-local`** | **提示词溢出防护**：当工具结果 > `maxInlineBytes`（默认 8192），自动落盘 + 用 head/tail 预览替换为 `Omitted N bytes. Full stored at: <locator>` | **无**（`context_bundle.py` 只能控制总长度，无法按工具结果单独裁剪） | **高**——MCP/联网/PDF 提取常返回大文档；当前只能让 LLM "假装看到"或暴力截断，丢内容 | **新增模块** `services/spill.py`：监听 `tools/post-execute`（类比 hooks_hub），超阈值则 spill 到 `users_data/<uid>/spill/` + 返回 locator |
| 3 | **`interaction/user-approval`** + **`interaction/tool-ask-user`** + **`interaction/user-questions`** | **三件套**：① `ask_user_question` 工具：让 LLM 主动向学生澄清歧义（如"你想问的是函数极限还是数列极限？"）② approval seam：高风险工具需学生确认③ user-questions service：UI 适配契约 | **无**（当前只能被动等学生输入；LLM 无法主动追问） | **极高**——**教育学必备**：诊断阶段（Diagnostor）需要追问学生；高风险操作（修改 Library/分享对话）需要确认 | **新增模块** `interaction/` 三文件：`user_questions.py`（service）+ `ask_user_tool.py`（注册到 tool_registry）+ `approval.py`（高风险工具如 file_gen/pptx 接入）；扩展前端：多选按钮 UI |
| 4 | **`workflow/tool-ralph`** | **RALPH 循环工具**：固定策略的工作流——给一个不可变目标，每轮启动**全新子 session**（不继承父对话），用结构化 handoff（status/summary/evidence/nextSteps/blocker）跨循环传状态；maxRounds 防护 | **无**（当前 subagent 继承父对话 + 自由递归，无"持续推进直到完成"的固定循环） | **极高**——**T5 任务直接命中**；自我更新（§3.5-3.9）+ 复杂任务（论文辅导/解题全流程）天然适合 RALPH | **新增模块** `workflows/ralph.py`：在 workflows_hub 加 `ralph(objective, maxRounds)` 工具；每次启动 fresh subagent + handoff 结构；maxRounds 默认 64 |

##### 🟡 P1 中价值（中期迭代 · 4 项）

| # | Harness 包名 | 功能说明 | PAEG 对应物 | 引入价值 | 建议方式 |
|---|---|---|---|---|---|
| 5 | **`guard/timeout-policy`** | 工具调用协作超时：声明 `timeoutMs` 的工具到时返回 `TOOL_TIMEOUT` 错误（不杀进程，仅通知） | 部分（`hooks_hub` 有 timeout 字段但未对接工具声明）| **中**——防止 LLM 陷入无限循环；MCP/联网工具易卡死 | **扩展现有** `hooks_hub.py`：在 `tools/execute` 包一层 timeout 监听；tool_registry 给每个工具声明 `timeoutMs` |
| 6 | **`llm/llm-retry`** | **模型请求重试**：normal mode（EMPTY_RESPONSE/RATE_LIMIT/SERVER/TIMEOUT/TRANSPORT 各重试 2 次，500ms-10s 指数退避 + 10% 抖动）+ always mode（无上限重试到成功） | **无**（PAEG 失败即返回，依赖前端重试）| **高**——教育 LLM 调用频次高；429/服务端抖动常见；学生体验"刚才没答上来"是糟糕的 | **新增模块** `services/llm_retry.py`：监听 `agent/request-error` 瀑布；分类错误码 → 退避 → 重试；可关闭（default on） |
| 7 | **`session/session-persistence-sqlite`** + **`session-query/session-query-sqlite`** | **SQLite 持久化 + FTS5 检索**：会话日志落 SQLite（单文件 0600 权限），session-query 提供全文检索 + lineage + 事件关系 | **JSON 文件**（`users_data/<uid>/sessions/*.json`，无检索能力）| **中**——多用户扩展（v0.38+）后 JSON 不可持续；历史检索是"教过什么"的关键 | **新增模块** `infra/session_db.py`：用 SQLite + FTS5 替换 JSON；提供 `search_sessions(uid, query, date_range)` API |
| 8 | **`feedback/message-feedback`** | **消息级反馈 sidecar**：对每条 final assistant message 单独点赞/点踩 + 备注；带 version 乐观锁 + header identity fence | **无**（PAEG 只有 session 级反馈）| **中**——精确定位"哪条回答有问题"；为 self-evolution（§3.2-3.4）提供更细粒度数据 | **新增模块** `feedback/message_feedback.py`：每条 message 一行；前端加 👍👎 按钮；纳入 self_evolution 数据源 |

##### 🟢 P2 低价值 / 实验性（3 项）

| # | Harness 包名 | 功能说明 | PAEG 对应物 | 引入价值 | 建议方式 |
|---|---|---|---|---|---|
| 9 | **`sandbox/sandbox`** + **`sandbox/sandbox-policy`** + **`sandbox/sandbox-local`** | **进程隔离沙箱**：3 档（read-only / workspace-write / danger-full-access）；local backend 在 Linux 用 bwrap / macOS 用 sandbox-exec / Windows 用 ACL restricted-token | **无**（学生可写路径无隔离；工具调用直接落盘）| **低**——教育场景"考试模式"锁定可写路径有意义，但当前 PAEG 多用读工具（找答案/讲解）| **暂搁置**：等 P0/P1 完成 + 出现"考试场景"需求再实施；可借 `windows-acl` 实现 Windows-only 简化版 |
| 10 | **`plan/plan-mode`** | **Plan 协作模式**：激活后让 LLM 只设计不执行；`exit_plan_mode` 让学生审阅 plan 才能执行 | **无**（学生无法"先看方案再执行"）| **低-中**——主要价值在多步教学场景（"先教我思路，再教我细节"）| **暂搁置**：v0.41+ Phase 3 后再议；可作 interaction/user-questions 的特例（带 `plan-review` intent）|
| 11 | **`code-runtime/code-runtime`** + **`code-runtime/code-runtime-worker-thread`** | **代码执行能力**（TypeScript/Python worker-thread）：LLM 写代码一次多步（run_code），绑定工具为 async functions | **无**（PAEG 无代码执行；manim_service.py 仅执行预生成代码）| **低**——教育 agent 主要解释概念不写代码；但"数学步解 + 可执行验证"有潜力 | **暂搁置**：等数学学科 subagent（math-step-solver skill）需求出现再评估；可借 `e2b`（远程沙箱）而非本地 worker |

#### 四、PAEG 整体建议与 T3 → T4 衔接

1. **首要执行（T4 立即）**：P0 四项——compaction + spill + user-approval/ask-user + ralph loop。理由：直接命中已知痛点（长 session 爆炸 / 工具结果太大 / 学生主动澄清缺失 / T5 RALPH 闭环）
2. **次要执行（v0.70-0.80 路线）**：P1 四项——timeout-policy（增量）+ llm-retry（高频价值）+ session-persistence-sqlite（多用户扩展）+ message-feedback（精细化）
3. **战略观望**：P2 三项——sandbox/plan-mode/code-runtime，待需求自然出现再引入，避免过早工程化
4. **借鉴来源记录（必须）**：每个 P0 实施时附 commit SHA（本地克隆当前 SHA 可用 `git rev-parse HEAD` 在 `D:\wbo-workspace\deepseek-harness-research\dsh\` 取得）
5. **不破坏原则**：ratchet 铁律——任何模块接入必须 smoke_test.py + pytest 全绿；现有 hooks_hub/workflows_hub 不删不退

#### 五、Harness 顶层分组中"PAEG 暂不需要"的明确清单（18 组 · 仅备查）

- `core/` 全部 8 个子包：理念已融入 config_hub/hooks_hub/session_model，**不重写** Python 实现（Node.js+TypeScript 不直接迁）
- `shell/` 9 子包：PAEG 无 shell executor 需求（学生不直接跑 bash）
- `fs/` 7 子包：PAEG 文件操作走 tool_registry（LLM 调用）+ 用户上传走 9_GUI前端
- `lsp/` 3 子包：教育 agent 不做代码导航
- `bundle/` 3 子包：仅 TS 打包概念，Python 端用 paeg_modules.json 已实现
- `extensions/` 4 子包：agent 自修改当前 PAEG 不开放（教学安全边界）
- `settings/` 2 子包：已被 config_hub 覆盖
- `credentials/` 2 子包：API key 单 env 即可
- `storage/` 4 子包：JSON 落盘够用，session 级 SQLite 是 P1 范围
- `identity/` 1 子包：用户 uid 已在 users.json/user_store.py
- `attachment/` 2 子包：图像/附件当前走 9_GUI前端 上传
- `runtime-diagnostics/` 1 子包：safety.py 粗粒度已覆盖
- `host/` 8 子包：Flask 后端结构不迁移
- `client/` 42 子包：9_GUI前端 已独立演化
- `util/` 8 子包：Python 端 utils/ 目录已存在
- `acp/` 1 子包：自动化协议当前不开放
- `e2b/` 3 子包：远程沙箱仅 code-runtime 配套
- `sdk/` 3 子包：仅 SDK 概念
### 3.17 用户新批次任务（2026-08-14 U 系列三连 · 待执行）
- **U1 交付物提交 GitHub**：交付物/路演PPT/（艾弥儿项目说明书 PDF + PPTX）提交到 GitHub 库（.gitignore 移除交付物/行）
- **U2 ModelScope 只 pull 差异文件**：严格确认——**只 pull 本地完全没有的文件**；本地已有的文件以本地为准（远程 3 提交仅 Dockerfile/.dockerignore/docker-compose，本地均已确认=最新 → 预计无文件可 pull）
- **U3 交互式教学循环改造**：咨询 Oracle 设计提问-等待-追问循环（不破坏 teach_stream 流式），实施后记录文档

### 3.18 用户新批次任务（2026-08-14 W 系列 · 记录后执行）
- **W1 测试工程记录入维护文档**：把测试工程（38 测试文件/11 回归类/测试基础设施修复：conftest sys.path/reconfigure 移 __main__/baselines skip/manim skipif）记录到维护手册（18.30 测试工程）
- **W2 RALPH+提示词模板记录入元能力**：RALPH 循环已记 §5.3 ✅；**智能体基本提示词模板**（先查找后插入——explore 已查）→ 插入元能力文档
- **W3 ModelScope 解决提交问题（以本地为准）**：远程 3 个平台 Dockerfile 提交 + 本地领先——force push 被 hook 拒（tag）；**想办法解决**：尝试 merge 远程 3 提交（内容与本地一致无冲突）→ 本地含远程 → push fast-forward；tag 被 hook 保护则跳过/手动
- **U3 交互式教学循环**（已入 §3.17）：Oracle 设计已收集 → 实施 P0（checkpoint 事件/resume 端点/前端问答）
- **U2 ModelScope pull 差异**（已入 §3.17）：远程 3 提交仅 Docker/文件（本地均=最新）→ 无文件可 pull（并入 W3 解决提交问题）
- **执行纪律**：执行时依据需求文档自查（任务核对机制第 8 条），每完成一项实时更新状态

### 3.19 项目技术说明撰写（2026-08-14 用户新需求 · 待执行）
- **Z1 简明项目技术说明 · ✅ 已完成（v0.69+）**：Oracle 设计结构 → PAEG技术说明.md（项目根 + 交付物/技术说明/PAEG技术说明_v0.69.md）——①能力全景 F1-F7 每功能含技术路线+实现方法 ②六层架构（L1 入口→L6 基础设施 + L0 横切质量层）③关键流程（教学生命周期/自我进化 G1-G11/RALPH/热加载/防幻觉）④扩展指南+术语表+文件索引；已微信发送用户，含：
  1. **项目能够实现的功能**——写细致（不能粗放），每个功能写明：技术路线 + 实现方法
  2. **整个 Agent 架构**——分层级展示：从最粗略的顶层，逐步具体到每一个更小的部分（架构分层）
- **执行方式**：先咨询 Oracle（设计技术说明的结构/粒度/架构分层方式）→ 撰写文档 → 记录
- **优先级**：P0（用户明确要求，先咨询 Oracle 再写）

### 3.20 深入版教学互动（2026-08-14 用户新需求 · 待实施）
- **需求**：§3.12 深入版教学互动——真正"挂起等待学生回答→评估回答→智能调整续讲"的循环（非可忽略提示）
- **执行**：联网调研（已完成 bg_2515721a）+ 咨询 Oracle（bg_4f82f061 运行中）+ 本地调研（bg_e9fb1fab 运行中）→ 找合适方法实施
- **现状基础**：checkpoint 事件（每步后，可答可忽略不挂起）+ _pending_steps 续讲机制 + Evaluator._student_signal 信号 + 前端问答面板
- **优先级**：P0（用户明确要求认真完成）

### 3.21 技术说明 PDF 渲染（2026-08-14 用户新需求 · 进行中）
- **需求**：把 PAEG技术说明.md 渲染成**好看**的 PDF（微 agent 设计样式）→ 发微信一份 + 交付物一份
- **执行**：visual-engineering agent 设计模板（bg_2c22c8f8 ✅ 已完成）→ weasyprint 渲染（weasyprint 可用）
- **优先级**：P0（用户明确要求，已收到设计模板）

### 3.22 Harness 引入补全（2026-08-14 用户指出"调研和引入没完成" · 待实施）
- **现状**：调研 ✅（§3.16：41 分组/167 子包/P0 四项），引入仅 ralph ✅ + spill ✅；user-approval/compaction 只核实未真正实施，P1（timeout-policy/llm-retry）未动
- **补全 · ✅ 核心已实现（v0.69+）**：llm-retry ✅（_safe_chat 重试循环 3 次+退避，验证通过）+ compaction ✅（compaction.py 压缩守卫 + chat_history 槽接入，30→13 验证）+ user-approval ✅ 基础已具备（Permission Preset + hooks tool.before 拦截；完整确认 UI 为后续）+ timeout-policy ✅（hooks_hub P1-7 已有）
- **参考**：Harness 本地克隆 D:\wbo-workspace\deepseek-harness-research\dsh\packages\（compaction/user-approval/llm-retry/timeout-policy 已定位）
- **优先级**：P0（用户明确要求补全引入）

### 3.23 技术说明文档优化批次（2026-08-14 用户 ULW · ✅ 全部完成）
- **D1 封面占满** ✅ visual agent 专业设计（右侧圆环锚点右上角避让/能力亮点卡/元信息四栏/副标语填充）——v0.70 PDF
- **D2 Roadmap 更新** ✅ 当前情况 + 更多未来规划（8 项详细规划表）
- **D3 Oracle 文档评估** ✅（6.5/10 → 应用改进：5 名词速查/怎么读表/术语表 11→35 条）
- **D4 架构多尺度图** ✅ 4 张 Mermaid（全景/系统/教学流/组件）
- **D5 引号纪律** ✅（纪律 21 + 元能力 §5.5）
- **模板资产化** ✅ 交付物/文档模板/（style.css+template.html+render_pdf.py+README，可循环复用+升级）
- **D1 封面占满修复**：PDF 封面仅左上角（未占满）——.cover-inner flex 占满布局 + 内容增强
- **D2 Roadmap 更新**：记录当前情况 + 更多未来规划（详细规划清单）
- **D3 Oracle 文档评估**：咨询 Oracle 评估文档是否用户友好（便于了解技术原理和架构）
- **D4 架构多尺度图**：用多个图展示从最大尺度（全景）到精细尺度（模块级）的架构（Mermaid/ASCII 多图）
- **D5 引号纪律**（已 ✅）：纪律 21 + 元能力 §5.5

### 3.24 技术说明扩展指南扩充 + Mermaid 修复（2026-08-14 用户 ULW · 待执行）
- **M1 Mermaid 未渲染排查**：咨询 Oracle（bg_2620a571 运行中）→ mermaid.js 已本地化（3.3MB 下载，防 CDN 被墙）→ 应用可靠方案
- **M2 扩展指南扩充**：①知识库扩展 ②学段扩展 ③学科专用提示词扩展（Python 脚本控制和提取）④**调研本项目找更多可扩展内容**（explore 启动）——如 config/skills/workflows/hooks/MCP 扩展、插件机制等

### 3.25 架构图集扩充（2026-08-14 用户 ULW · 待执行）
- **A1 架构图集更多图**：咨询 Oracle（设计扩充方向）+ 调研项目本体与技术文档（找更多可画图的机制/模块）→ 新增更多尺度/机制图
- **现状**：图集已有 9 张（全景/系统/教学流/组件/自我进化/RALPH/意图路由/配置体系/checkpoint 时序）——需更多



### 3.26 Manim 生成流程升级：提示词 → 脚本（2026-08-14 用户新需求 · 待执行）
- **现状**：Manim 动画用提示词 + 用户简单指令生成（manim_service：提示词模板→代码生成→渲染）
- **改进**：每次生成视频前，**根据与用户的对话和轮询**（已有的选择题/填空题轮询功能）获取足够信息后 → **先生成脚本** → 用脚本制作动画
- **脚本定位**：对用户可不显现（内部脚本）——但**脚本和讲稿、PPT、讲义、思维导图一同作为资产**，均提供**可下载选项**（用户澄清）
- **资产清单（一条线连通，全部可下载）**：Manim 脚本（脚本化流程产物）+ 讲稿（script_service）+ PPT（pptx 管线）+ 讲义（keyword_doc）+ 思维导图（knowledge_map）
- **涉及模块**：manim_service（动画）、script_service（讲稿）、production_pipeline（大纲）、轮询功能（选择题/填空题）、knowledge_map（思维导图）、资产下载
- **设计**：咨询 Oracle 设计对话+轮询→脚本→动画+资产联动流程 → 实施
- **数学可视化脚本创作方法调研（2026-08-14 完成 · 决定方法）**：Manim 官方（3B1B 8 原则：直觉先于形式化/单一聚焦/空间承载含义/慢而稳/停顿/文字最小化/回看锚点）+ manim_skill 社区库（scenes.md 模板/12 失败模式/ManimCE 颜色语义与节奏规范）+ Oracle 设计（**script.json 单一真相源**：对话轮询→脚本生成→校验修补→5 资产联动[Manim视频/讲稿/PPT/讲义/思维导图全部可下载]）
- **实施（P0 起）**：visual_script_generator（系统提示词+script.json）+ visual_script_validator（7 铁律）+ manim_renderer（模板渲染）+ 资产联动（script_service/pptx/keyword_doc/knowledge_map）+ 轮询 question bank
- **优先级**：P0（用户明确要求，先记录后执行）### 3.27 workflow 增强教学物料制作（2026-08-14 用户 ULW · 待执行）
- **需求**：既然已有 workflow（声明式 DAG，teach_minimal/teach_concept），是否可利用 workflow 增强教学物料制作——思维导图/讲义/PPT 讲稿/视频脚本/数学视频/讲解视频，用 workflow 进一步提升效果
- **执行**：咨询 Oracle（workflow 教学物料制作设计）+ 调研项目（workflows_hub/现有 workflow/物料生成模块）+ 检索联网经验（workflow 编排最佳实践）→ 设计 workflow 增强方案 → 实施
- **同步**：完成后同步更新各文档（CHANGELOG/README/技术/元能力/亮点）
- **优先级**：P0（用户明确要求，先记录后执行）

### 3.28 语言规范模块 MCP 标准化（2026-08-14 用户 ULW · ✅ 已完成 v0.70）
- **需求**：查看语言规范模块（polish/refiner/LANGUAGE_STYLE/违禁词模块）是否有**标准化接口接入所有输出端**；联网检索 + Oracle
- **本质**：语言规范模块 = LLM 系统提示词（明晰分点列出的语法规则，约束 LLM 输出质量）+ 动态维护的违禁词模块
- **开发方式**：按 **MCP 标准接口**开发（工具化/标准化）
- **执行**：先写入底层逻辑+标准化+改进措施到需求文档 → 按需求实施
- **优先级**：P0
- **实施记录（v0.70，4 阶段全完成）**：
  - Phase 1-2：13 处 `_polish_text` 收敛为 `lang_gate_content` 统一入口（server/file_generator/problem_solver 等 9 文件）+ 补 /api/solve 与知识导图漏洞
  - Phase 3：违禁词数据化——`data/forbidden_words.json`（extra_forbidden/pseudo_empathy_verbs/ai_tells_extra）+ language_refiner 启动合并加载（内嵌 AI_TELLS 577 项去重后 555 + 外部 18 项，dict.fromkeys 去重，文件缺失容错）
  - Phase 4：MCP 三工具（tool_registry + mcp_gateway 双层注册）——`normalize_text`（L0+L2 统一守门）/ `language_policy_check`（AI 味概率 + 违禁词命中，不调 LLM）/ `forbidden_words`（list/add/remove 落盘，幂等）；修复 _BUILTIN_NAMES 去重漏洞（config_hub 回灌导致 4 工具重复 → 54 工具无重复）
  - Phase 5（并入）：PPT 生成路径确认已接 lang_gate（server.py 1487 `teach:ppt` + file_generator 176）

### 3.29 L0-L8 分层动态 LLM 约束系统 MCP 升级（2026-08-14 用户 ULW · ✅ 已完成 v0.70）
- **需求**：L0-L8 分层动态 LLM 约束系统升级——联网搜索 + Oracle；与"标准化格式提取提示词、动态拼接提示词"合并开发；按 MCP 标准接口
- **目标**：实现 agent 动态性/自创生性/反馈控制能力
- **资产**：固定提示词 + 可动态调整的提示词模板；功能=动态解放/添加约束、任意提示词组合拼接、指引约束大模型、可设永远保持激活的提示词
- **执行**：先写入需求文档 → 联网调研 + Oracle → 升级方案写入需求文档 → 按需求实施
- **优先级**：P0
- **现有基础（已核实）**：prompts.py CONSTRAINT_LAYERS（8 层 × 6 组开关矩阵：M节奏/R修辞/T温度/D教学法深度/S学科教学法/P哲学框架）+ L0_RESERVED_RULES（11 条保底）+ `_build_constraint_layers(constraint_flags, layer, crisis_signal)`（L0→L7 线性谱，crisis 强制 L1）+ `_flags_to_layer`（3 位掩码兼容）
- **Oracle 升级方案（已收）**：MCP 化 `paeg_constraint_engine`，6 API：
  | API | 功能 | 对应资产 |
  |---|---|---|
  | constraint_layer_get(layer) | 读某层放开组/规则 | CONSTRAINT_LAYERS + _GROUP_RULES |
  | constraint_layer_set(session, layer) | 动态切换约束层（教学/考试/自由） | _build_constraint_layers |
  | constraint_compose(parts[]) | 任意提示词块组合拼接 | prompt_template STATIC_TEMPLATES + DYNAMIC_SLOTS |
  | constraint_always_active(names[]) | 永远保持激活的提示词（不随层放开） | L0_RESERVED_RULES 扩展 |
  | constraint_self_evolve(insight) | 约束系统自我演化（LLM 提炼新规则入层） | self_evolution 联动 |
  | constraint_feedback_adjust(feedback, target) | 反馈调强/调弱约束 | 用户反馈 → 画像/约束 |
- **实施要点**：①复用 prompts.py 现有层结构不重写 ②MCP tool 注册（tool_registry + mcp_gateway 双面）③数据化（约束规则可外置 JSON，如 constraint_layers.json）④与 §3.28 lang_gate 衔接（语言约束是 L1 的具体化）
- **实施记录（v0.70，commit 0602792）**：
  - 新建 `constraint_engine.py`：6 API 全实现——layer_get（层放开组+规则结构化输出）/ layer_set（复用 _build_constraint_layers 拼装）/ compose（任意块拼接）/ always_active（list/add/remove 落盘 always_active.json，内嵌 L0 11 条 + 外部）/ self_evolve（洞察写入指定层组，落盘 constraint_layers.json）/ feedback_adjust（信号词映射：啰嗦→loosen_m、太直接/冷漠→tighten_t、太机械→loosen_s、太浅→loosen_d、太深/听不懂→tighten_d；落盘 constraint_feedback_log.jsonl）
  - 双层注册：tool_registry 6 工具（constraint_always_active/self_evolve 标 write 风险入 exam 黑名单）+ mcp_gateway 6 工具（异步 list_tools 真实调用验证通过）
  - 数据化：`data/constraint_layers.json`（外部层覆盖）+ `data/always_active.json`（永远激活）+ `data/constraint_feedback_log.jsonl`（反馈日志）
  - 验证：6 API 全测通过（L7 层 6 组展开/layer_set 返回 L1 段/self_evolve 去重/feedback 多信号/风险分级/exam 锁定）+ MCP 网关真实调用 + 54 工具无重复 + 42 测试全过

### 3.30 技术说明动态更新 + PDF（2026-08-14 用户 ULW · 待执行）
- **需求**：技术说明手册动态更新——①F3 学习辅助工具加 数学视频/教学视频/PPT/讲义 功能记录 ②最近更新按特性更新入手册（注意插入位置衔接）
- **执行**：先列入需求文档 → Oracle 咨询 → 完成；markdown 和 pdf 都保存项目文件夹；渲染完成后微信发 PDF
- **优先级**：P0

### 3.31 DeepSeek Harness 继续调研（2026-08-14 用户 ULW · 待执行）
- **需求**：继续调研 DeepSeek Harness github 库（新发布内容）→ 为需求文档更新需求

### 3.32 sub agent 模型配置化 + 面向用户配置化定制服务（2026-08-14 用户新指令 · ✅ 已完成 v0.71）
- **背景**：用户观察到 Oh My OpenCode 支持 JSON 配置为每个 sub agent 分配不同模型；询问 PAEG 是否支持（现状：不支持——所有 LLM subagent 共用同一个 model_api，paeg.py 统一传入）
- **需求**：①设计 config/agents.json——每 subagent 可配置 model/provider/temperature/prompt/工具开关 ②探索项目其他方面可配置化（面向用户的可定制服务，如教学风格/学科/人格）③咨询 Oracle + 联网检索 opencode/codex/DeepSeek Harness 最新实践 ④按需求文档实施 ⑤上传示例配置 + push GitHub
- **执行**：先记录入需求文档 → 并行调研（librarian 联网 + explore 项目现状）→ Oracle 方案 → 实施 → 示例 + 上传
- **优先级**：P0
- **现状核查（2026-08-14 已完成）**：
  - paeg.py 构造时统一创建 model_api → 传 Diagnostor/Planner/Presenter/Evaluator/Adapter/ResourceLibrarian/LanguageRefiner/SelfEvolver（8 个 LLM subagent）
  - subagent 类构造器接受 `model` 参数（`_safe_chat`/`_safe_reason_chat` 函数级传入）——**改造基础已具备，成本低**
  - llm_adapter.create_llm 已支持 provider 选择（auto/reasoner/flash 等）
  - 无 per-subagent 模型 JSON 配置；无面向用户的 subagent 定制配置
- **实施记录（v0.71，commit 20dc3ce）**：
  - 新建 `config_loader.py`：三层合并（DEFAULTS 内置 → ~/.paeg/agents.json 用户全局 → config/agents.json 项目级）+ `{env:KEY|默认}`/`{file:path}` 变量替换 + `create_llm_for(name)` per-subagent LLM 工厂 + `get_agent_config` + disabled 回退
  - 新建 `config/agents.json`：10 subagent 可配（provider/model/temperature/max_tokens/thinking_level/enabled），含使用示例注释
  - `paeg.py` __init__ 增加 `agents_config`/`use_agents_config` 参数：各 LLM subagent 按配置创建独立 LLM（presenter 用 A 模型、answer_solver 用 B 等），配置缺失/失败回退原 model_api
  - 验证：7 项 config_loader 测试（默认完整/三层合并/变量替换/global 默认/disabled 回退）+ 3 项 paeg 注入测试（默认启用/关闭回退/自定义 mock）全过
  - 借鉴来源：opencode 多层 merge + DeepSeek Harness 稀疏 patch + Claude Code 文件引用——librarian 四项目对比报告（opencode.json/Codex toml/Harness preset.yml/Claude Code frontmatter）已存档

### 3.33 学段教学模式差异化（2026-08-14 用户 ULW 新增 · ✅ 已完成 v0.71）
- **背景**：用户指出初中/高中/大学（考研）的授课风格应当差距非常大——大学考研要像正式 presentation/lecture；高中重知识结构/解题/实例/适时复习；初中重 visualization/直观/生活化例子。要求学段上明确区分。
- **需求**：①学段教学模式明确差异化（不只是深度档位，而是授课风格本质不同）②咨询 Oracle 调研项目现状 ③寻找解决方案实施
- **执行**：先记录入需求文档 → Oracle 咨询 → 调研项目（SUBJECT_STYLES/SUBJECT_GRADES/学段联动现状）→ 方案 → 实施
- **优先级**：P0
- **用户原话**："初中、高中、大学和考研阶段对于教学模式来说，它的授课风格依然应当差距非常大。大学的考研水平……你讲课要像一场正式的presentation，要像一场正式的lecture一样，然后去完成对一个知识的讲授。而高中呢，可能更加需要注重知识结构啊，解题呀，然后应用一些实例，以及总是在适当的时候引入复习的环节，而初中可能更加强调visualization，能强调一些直观和更多生活化的例子。"
- **现状待调研**：SUBJECT_GRADES（4 学段档位）+ SUBJECT_STYLES 的 grade 联动 + Presenter 教学模式三档（easy/normal/deep）+ build_presenter_system 的 grade_level 参数——现有学段差异是否只是"深度"区别而非"风格"区别？
- **实施记录（v0.71，commit ed98c3a + 276d6d1）**：
  - **Phase 1（ed98c3a）**：新增 `GRADE_TEACHING_MODES`（prompts.py）——4 学段 × 6 维教学法结构（structure/explanation/examples/interaction/review/output + system 提示词段）：初中"感官优先·三步可视化"（现象→画面→类比→命名→复述）/ 高中"结构优先·五步走"（定义→公式→例题→误区→知识结构图）/ 大学"正式 lecture·五步论证"（严格定义→定理→推导→应用→学科视野，绝不把大学课当高中补习讲）/ 考研"考点解剖·五步得分"（考什么→怎么考→套路→真题→易错点）；`get_grade_mode()` 未知学段回退高中；build_presenter_system 注入 grade_mode_line（grade_line 后、constraint 前）
  - **Phase 2 升级（276d6d1，Oracle 二次咨询）**：用户要求"风格差异不仅体现在内容，也体现在结构上"——新增 `GRADE_SCAFFOLDS`（可执行段序列模板：段名/目的/内容指令/长度约束/形式约束）+ `get_grade_scaffold()` + `render_scaffold_to_system()`（渲染为【NEXT】逐段强制清单）→ build_presenter_system 注入 scaffold_line。结构差异（骨架段名互斥）+ 内容深度量化（初中每段≤5行禁公式/高中必有LaTeX+###标题/大学5-20行LaTeX推导+学科史/考研真题编号+⚡⚠️📌⏱标签）双落实
- **验证**：6 项学段测试（4×6维完整/风格互斥/回退/三学段注入/顺序/兼容）+ 6 项骨架测试（段数/字段/段名互斥/渲染/注入/顺序）全过；测试断言修复（self_update_agent 懒加载）
- **注意**：学段模式与 Presenter easy/normal/deep 三档、L0-L7 约束层正交——四层叠加不覆盖

### 3.34 Manim 动画模块优化（2026-08-15 用户新指令 · 待实施）
- **背景**：用户提供"智绘科普"（首届'小有可为 AI 向善'挑战赛'点亮乡村课堂'一等奖）技术拆解资料，要求参考其思路优化 PAEG 的 Manim 动画模块。核心参考：**Agent 分阶段协作 + 门控 + 自检** 的"AI 流水线"范式（Qwen3.5-397B-A17B 作为思考内核 + Manim 作为执行工具）
- **需求（用户三点）**：
  1. **参考"智绘科普"优化 Manim 动画模块**（先计入需求清单）
  2. **确保 Manim 生成动画既独立，又是教学视频的上游环节**——即：动画生成独立可用；同时是教学视频的前置（讲稿、讲义、数学视频脚本的下游环节——动画消费这些上游产物）
  3. **其中的很多思路也适合应用到其他物料的制作**——多 Agent 协作/门控/自我修复范式平移到 PPT/讲义/讲稿/知识导图等其他物料生成
- **智绘科普关键思路（借鉴，不换大模型）**：
  - **结构化 JSON 脚本（build_spec）**：beats 分镜头最小单元（3-6 个，每 beat 一个教学点），可校验/可复用/可回放——所有下游环节共用同一份 spec
  - **三道质量门**：结构门（必填字段）/ 数量门（beats 3-6）/ 可执行门（视觉目标 Manim 可实现）
  - **三段式**：Phase1 规划 → Phase2A 草稿（写代码不渲染）→ Phase2B 实现（渲染+审计）——中间产物可检查可修改，出错只重跑该阶段
  - **时序门控**：每 beat 动画时长 ≥ 目标 80%，总时长 ≥ 60%——不达标回炉
  - **三道硬门控**：Manim 渲染门（跑通出片）/ 几何审计门（元素重叠/越界检测）/ 视觉审查门（抽帧视觉大模型评估美观清晰）
  - **失败返工回路**：渲染失败→自动提取错误日志→生成修复提示词→重渲染（"抛物线"任务 5 次失败 5 次自愈，自动修复 import 路径/箭头绘制/虚线参数）
  - **角色分层禁令**：规划 Agent 严禁写代码、审查 Agent 严禁改文件——防模型越界
- **PAEG 现状（§3.26 已有基础）**：visual_script_generator.py（3B1B 原则 script.json）+ visual_script_validator.py（7 铁律校验修补）+ manim_service（渲染）——已具备"脚本→校验→渲染"雏形
- **优化方向（待细化）**：①补齐"多 Agent 分阶段"（规划/草稿/实现/审查分离）②补几何审计门（重叠/越界检测）③补失败自动修复回路（错误日志→修复提示词）④动画作为教学视频上游（讲稿/讲义/脚本作为动画输入，动画输出回灌物料包）⑤范式平移到其他物料
- **执行**：先记录入需求文档 → 调研现状（visual_script_generator/validator/manim_service）→ 方案（可咨询 Oracle）→ 实施
- **优先级**：P1

