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

## 五、当前技术状态快照（2026-08-14）

- **版本**：v0.68+（server.py version=0.68.0）
- **config_hub**：统一配置中心（MCP/skills/hooks/workflows 四子模块 + get_all_tool_defs/execute_tool）
- **hooks_hub**：waterfall+next/matcher/verdict 合并/timeout/legacy_adapter
- **workflows_hub**：teach_minimal + teach_concept（DAG 拓扑执行）
- **meta_router**：15 意图 LLM 优先 + capability_hint（意图→能力）
- **subagents**：9 subagent + SUBAGENT_THINKING_LEVELS + _build_capability_manifest（能力清单注入）
- **学习计划**：planner.py（StudyPlan）+ 推荐资料附录（确定性渲染）
- **自我更新**：self_evolution.py（4 路进化：distill_knowledge/evolve_prompt/learn_tool_lesson/record_subject_request）+ reflection_store + SelfUpdateAgent
- **记忆**：SESSIONS（短期）+ LearnerProfile/画像（长期）+ 三层记忆（未独立模块化）
- **动态提示词**：prompt_template.py（STATIC_TEMPLATES 固定 + DYNAMIC_SLOTS 动态槽）；subject_patches.md 反思补丁（待接入动态槽/拼接 tool）
- **已知问题**：学习计划 HTTP 附录偶发 False（polish 随机性，已用"提取附录+polish正文+拼回"根治，待回归确认）

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
- **补全**：真正实施 compaction（上下文压缩）+ user-approval（用户确认）+ llm-retry（LLM 重试）+ timeout-policy 评估
- **参考**：Harness 本地克隆 D:\wbo-workspace\deepseek-harness-research\dsh\packages\（compaction/user-approval/llm-retry/timeout-policy 已定位）
- **优先级**：P0（用户明确要求补全引入）

