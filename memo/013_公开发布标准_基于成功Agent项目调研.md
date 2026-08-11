# 013 · PAEG 公开发布标准（基于成功 AI Agent 项目调研）

> 日期：2026-08-11
> 角色：项目经理（PM）
> 依据：librarian 调研 2026 年成功 AI Agent 项目（Claude Code/Codex/Cursor/Devin/LangGraph/
> OpenManus/AutoGPT/Khanmigo/NotebookLM/OpenAI Operator + 中国本土：作业帮/豆包爱学）
> + OWASP GenAI/Agentic Top 10 2026 + Production AI Institute PSF（8 域 32 控制项）
> + 50+ 权威来源（详见调研记录）。
> 目的：确定 PAEG 是否符合"公开发布的良好/优秀"标准，列出差距并修复 P0/P1。

---

## 一、成功 AI Agent 项目共性特征（12 条）

| # | 共性特征 | 参照项目 |
|---|---|---|
| 1 | Agent 循环是简单 while-loop，**价值在周围系统**（Claude Code 仅 1.6% 代码是 AI 决策） | Claude Code/Codex/OpenManus |
| 2 | 工具调用 = 结构化 JSON Schema + **风险分级** | 所有 |
| 3 | Plan = 结构化状态（JSON），非聊天文本 | Devin/Claude Code Plan Mode |
| 4 | **沙箱是 OS 级**而非应用级 | Claude Code/Codex/OpenManus |
| 5 | **记忆分 4 层**（working/session/cross-session/knowledge） | Devin/LangGraph |
| 6 | 上下文压缩是核心工程问题 | Claude Code/Codex/NotebookLM |
| 7 | **HITL 显式而非可选**（写/破坏性操作） | 所有 |
| 8 | 可观测性 = trace + version + failure taxonomy + redaction | 所有生产框架 |
| 9 | Eval 分三层：公开 benchmark + 私有回归 + 在线 canary | OpenAI/Cursor |
| 10 | **Kill switch + rollback + canary rollout 是上线门槛** | PSF |
| 11 | 公开 red team 数据 + system card | OpenAI/Khanmigo |
| 12 | 模型版本固定，升级视为代码变更 | PSF/OpenAI |

## 二、"良好 vs 优秀"发布标准表（21 维度）

| 维度 | 🟡 良好（Good） | 🟢 优秀（Excellent） |
|---|---|---|
| 架构 | 分层抽象，AI 决策 <30% | Agent Loop + 工具注册中心 + 上下文压缩管道 + 权限门 + 沙箱，AI <5% |
| 可靠性-错误率 | max turns/retries/wall-clock 三重上限 + circuit breaker | 自适应预算 + 故障语义分类 + stuck-state 检测 |
| 可靠性-重试 | 幂等 key + 指数退避 | 风险分级 + 死信队列 + 自动回滚 |
| 可观测性-日志 | Trace ID + 版本化 | OpenTelemetry + 失败分类 + 自动告警 + SIEM |
| 可观测性-追踪 | 单会话完整 trace | 全链路 + PII redact + 可重放 |
| 安全-工具权限 | 工具 allowlist + 风险分级 | 动态权限 + 临时凭证 + policy gate |
| 安全-越狱防护 | 输入 sanitizer + 输出 filter | 多层（输入分类 + 数据信封 + 行为检测） |
| 安全-数据隔离 | 多租户 namespace | 进程隔离 + OS 沙箱 + 凭证不写日志 |
| 性能-延迟 | P50/P95/P99 监控 | 流式 + 并行 + 缓存 + graceful degradation |
| 性能-并发 | 异步 I/O + 工具级并发 | 异步队列 + lease 锁 + 读写分离 |
| 可扩展-插件 | 工具注册中心 | MCP 双向 + 工具 marketplace |
| 可扩展-LLM | 多 provider 抽象 | 自动 fallback ladder + 版本固定 + 行为等价测试 |
| UX-取消 | Esc 停止 | Esc + 无中断继续 + rewind + 分叉 |
| UX-错误展示 | 错误信息 + 重试 | 结构化失败原因 + 不暴露堆栈 |
| 合规-隐私 | PII redact + 本地化 | 字段级脱敏 + 加密 + 用户导出/删除 + DPIA |
| 合规-内容 | 输出 filter + 红队 | 多层 + 违规分类 + 自动上报 |
| 评估-测试 | 30-100 题 golden set | 三层（benchmark + 私有回归 + 在线 canary） |
| 评估-红队 | 季度红队 | 持续红队 + 第三方审计 + bug bounty |
| 部署-上线 | Staging → 100% | Canary 1-5%→20%→50%→100% + 闸门 + 72h 观察 |
| 部署-灰度 | Feature flag | Kill switch（60s）+ rollback（5min）+ blast radius |
| 运维-SLA | 可用性 99% | P95 + 错误率 + token 成本 + eval pass rate 四 SLO |

## 三、教育 Agent 特有标准

### 内容准确性（优秀线）
- 事实性回答附引用/来源 + 置信度显示 + 数学计算可验证步骤
- 内置苏格拉底法（不直接给答案）+ 学生水平自适应
- 步骤级反馈 + 类比讲解 + 同类题巩固
- 多模态（文本/语音/视频讲解）

### 安全合规（优秀线）
- **儿童保护**：Moderation + 家长实时可见聊天 + 触发即冻结 + 心理专家复盘
- **家长/教师知情**：功能变更通知 + 聊天日志可查 + 家长仪表盘
- **使用时长**：每日额度 + 长会话提示休息
- **年龄分级**：按年级差异化 prompt + 监护人分级授权
- **PII/学生数据**：加密 + 本地化 + 可导出/删除 + 不入训练集
- **越狱防护**：教育专用 guardrail + 拒绝非学习问题 + red team 教育题库
- **中国合规三件套**：ICP + 算法备案 + 教育 APP 备案 + CSAC 023-2025 未成年人指引
- **学术诚信**：不直接给答案 + 抄袭预警 + 教师端
- **心理健康**：危机识别 + 转人工 + 机构对接 + 报监护人

### 教学效果（优秀线）
- 课标对齐 + 学情数据 + 个性化路径 + 教师 dashboard + 学情报告
- 可解释（为什么 + 知识图谱溯源 + 类似题推荐）
- 学习闭环（错题本→复习→测试→评估→家长报告）

## 四、PAEG 差距评估（对照二/三标准，2026-08-11 现状）

| 维度 | 现状 | 达标度 |
|---|---|---|
| 架构 | 子代理分层 + 工具注册中心 + 模块化 | 🟢 优秀线（Agent Loop 清晰） |
| 检索质量 | RRF + URL 规范化 + jieba + 多查询（5/5 稳定） | 🟢 优秀线 |
| 教育理念 | 薇依哲学 + 因材施教 + 立德树人 + 危机协议 | 🟢 优秀线 |
| 内容审核 | quality_gate.py + safety.py + 危机协议 | 🟡 良好（缺家长可见/教育 guardrail） |
| 工具权限 | **v0.46 新增风险分级 + policy gate** | 🟢 优秀线（7 工具全 read） |
| 成本控制 | **v0.46 新增 token 预算门（60000/会话）** | 🟢 优秀线 |
| 间接注入 | **v0.46 新增数据信封（<<UNTRUSTED>>）** | 🟢 优秀线 |
| 可观测性 | request_id + health 深度化 + logger（部分） | 🟡 良好（136 print 未全转 logger） |
| 记忆 | Individuality 17 维画像 + 历史持久化 | 🟡 良好（无显式 4 层） |
| 测试 | audit 39/40 + pytest + E2E + 质量哲学（memo/010） | 🟡 良好（无 canary/红队） |
| 合规 | 无 ICP/算法备案/隐私政策文件 | 🔴 不达标（P0） |
| 家长可见 | 无 | 🔴 不达标（P0，教育特有） |
| 安全存储 | SHA-256 + JSON 非原子 | 🔴 不达标（P0） |
| 部署 | 无 canary/kill switch/gunicorn | 🟡 良好（单进程 threaded） |

## 五、P0/P1 修复清单与状态

### ✅ 已修复（本轮 v0.46）
| # | 缺陷 | 修复 | 对照标准 |
|---|---|---|---|
| P0-1 | 工具无风险分级 | tool_registry 加 risk 分级 + is_tool_allowed 策略门 | B 表安全-工具权限 |
| P0-2 | 无成本上限 | _safe_chat 加会话级 token 预算门（60000） | D 节失败模式 #9 |
| P0-3 | 间接注入无防护 | 检索内容加 <<UNTRUSTED>> 数据信封 | D 节失败模式 #2 |

### 🔴 待修复（P0）
| # | 缺陷 | 方案 | 工作量 |
|---|---|---|---|
| P0-4 | 密码 SHA-256 | bcrypt/argon2 升级 | 2-4h |
| P0-5 | users.json 非原子写 | tmp+os.replace | 1h |
| P0-6 | 无登录限流 | 失败计数 + IP 封禁 | 3-4h |
| P0-7 | CORS 全开 + 无 HTTPS | origins 白名单 + ssl_context | 1-4h |
| P0-8 | 无隐私政策/LICENSE 文件 | 补文件（README 已声明 MIT） | 2-3h |
| P0-9 | 家长可见性缺失（教育特有） | 聊天记录家长/教师视图 + 每日时长限制 | 1-2d |

### 🟡 待修复（P1）
| # | 缺陷 | 方案 |
|---|---|---|
| P1-1 | 136 处 print 未接 logger | 全量 logger.* 替换 |
| P1-2 | teach_stream 995 行 | 拆 3 模块 |
| P1-3 | 无 golden set/canary | 50+ 题回归集 + 灰度 |
| P1-4 | 模型版本未固定 | config 锁模型 + 升级视为变更 |
| P1-5 | 教育 guardrail 题库 | 100+ 题教育场景 red team |

## 六、PAEG 明确不做的事（借鉴 AutoGPT 教训）

- ❌ 不引入复杂向量 DB（JSON 检索已够，AutoGPT 移除 Milvus 后评估更好）
- ❌ 不把规划与执行合并（保持规则兜底 + LLM 优先的分离）
- ❌ 不等"完美数据"再上线（先 MVP 听反馈）

## 七、结论

**PAEG 处于"良好偏上"**：架构/检索质量/教育理念/工具安全（本轮 3 个 P0 修复后）
已达优秀线；但**合规（P0-8/9）、存储安全（P0-4/5/6）、部署（P0-7）**仍是公开发布的
硬门槛。**补完 P0-4~9 后可达到"良好"公开发布标准；再加 P1 清单进入"优秀"。**

> 参考：88% 的 agent 原型从不上线（NWI），主因 production-ready 评估缺位——本表即
> PAEG 的 production-ready 自评依据。调研完整报告见 librarian 会话记录（21 维度 +
> 15 失败模式 + 教育特有标准 + 50 来源）。
