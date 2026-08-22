# AGENTS.md — PAEG 开发者/进化代理工作准则（§3.85 Codex Harness 借鉴 P1）

> Codex init-deep 借鉴：根/域/模块三级 AGENTS.md——让自我进化（SelfEvolution/QA 代理）
> 与人类开发者共享同一份机构记忆，避免"洞见散落、决策不可审计"。
> 深度 ≤3 层；原则优先于细节；每个文件回答"在这里工作必须知道什么"。

## Golden Principles（最高优先级，冲突时以此裁决）

1. **correctness > safety > brevity > performance**（Codex 原则）：教学正确性第一；
   安全（隐私/防幻觉/权限）次之；简洁与性能最后——禁止为性能牺牲正确性或安全。
2. **LLM 先判断、规则兜底**（元能力 L918）：语义判断交给 LLM，规则只做确定性兜底；
   规则不得覆盖 LLM 判断。
3. **证据驱动完成**：改动必须可验证（测试/真实调用/文档），无证据 = 未完成。
4. **文档融贯**：技术说明文档新增内容融入结构（§7.11 五主线），不简单附随末尾；
   需求文档每轮先读再动手。
5. **数据安全**：users.json 等持久化数据损坏/被清空时先备份留证（.corrupt_<ts>）
   再兜底；恢复后必须重启服务器（内存与磁盘同步，防覆盖恢复数据）。

## 目录结构速览

```
14_教育者Agent项目/
├── 05_实现原型/          # 核心代码（server.py/subagents.py/services/infra/blueprints/tests）
├── 09_GUI前端/           # 前端（index.html 单页）
├── Library/              # 知识库（common/张宇扬课件 + KnowledgeBase + 学科）
├── deploy/               # 运维（canary.ps1/kill_switch_drill.md/灰度回滚规范）
├── 06_测试与验证/        # E2E（playwright find_fault*/grade_quality_probe）
├── 10_封闭测试/          # 用户封闭测试
├── PAEG_任务总清单与操作规范.md   # 每轮任务状态（NEW-xx 固化）
├── 总需求与执行标准.md    # 需求与执行标准（§3.79/§3.81-3.85 轮次需求）
├── PAEG技术说明.md        # 技术说明（§7.11 五主线融贯 + 附录 C 追溯）
├── PAEG技术全景文档.md    # 技术全景（§10.xx 轮次记录）
└── 维护手册.md            # 运维手册（§18.xx 教训/要点，双 BOM UTF-8）
```

## 领域指引（域级 AGENTS.md 摘要）

### 教学核心（05_实现原型/）
- **教学管线**：teach_stream（SSE）→ 诊断→计划→呈现→评估→调整→反思；
  学段特征/深度守门（grade_quality_gate）+ 输出质量注入（GRADE_OUTPUT_QUALITY）
- **意图路由**：meta_router LLM 优先 + 规则兜底；学科识别 subject_detector
  LLM 先判断（子学科映射 SUBJECT_ALIASES 仅兜底）
- **物料生产**：LessonPrep 8 步 + quality_report（material_judge 5 维评审 +
  结构检查器）+ exec_engine 受控子进程执行
- **自我进化**：self_evolution 4 路 + QualityGate（promote=采纳事件）+ adoption_tracker
- **Rollout**：services/rollout.py 教学事件流持久化（审计/恢复）

### 运维（deploy/）
- 灰度：canary.ps1（C1 5%→C4 100%）+ 闸门（错误率≤0.5%/P95≤120s）
- kill switch：paeg_modules.json 热重载 + admin token + rate-limit
- 排障：改代码后确认端口进程启动时间晚于文件修改时间（残留进程教训）

## 工作纪律（每轮必读）

1. **先读需求文档**（总需求与执行标准.md 的 🚨 优先区 + §3.xx 轮次需求）再动手
2. **任务清单固化**：动手前在 PAEG_任务总清单 新增/更新 NEW-xx 行
3. **调研→策略→标准→实施→测试**：设计先于编码，标准先于实现
4. **验证闭环**：测试全绿 + 真实调用 + 文档落盘 + git 提交双远程
5. **双远程同步**：GitHub（origin）+ ModelScope（modelscope）main/master 一致
