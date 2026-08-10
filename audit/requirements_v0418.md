# PAEG v0.41.8 专项需求表（Subagent 治理 + 自检增强）

> 来源：v0.41.7 复盘 + Oracle 反思 + Librarian 业界调研（突变测试/契约测试/属性测试/SSE 测试/静态分析进阶/测试金字塔）
> 目标：①解决 subagent 30 分钟超时无返回 ②补齐三大自检盲区（pyright/属性测试/契约测试）
> 更新：2026-08-10

---

## 一、v0.41.7 复盘要点（延续）

- ✅ 3 bug 修复（subtopic NameError / 语音双发送 / 提示文案）+ 质检方法论反思
- ✅ smoke_test 教学完整流断言 + audit_check 维度 13
- ⏳ 待做：4 handler 迁移 / INTERFACE_GUIDE 4 桶 / blueprints 拆分

---

## 二、Subagent 治理（用户核心关切："经常崩溃，要监控进度"）

### 根因（Oracle 分析）
**最大真相：执行完成但没 ack**——模型（MiniMax-M3）长任务自检循环不输出完成信号 + 后台转换机制吞回调 + 任务粒度过大。
**核心转向：从"等回调"改为"轮询产物 + 服务健康 + 告警"三段式，不依赖 LLM 完成信号。**

### ✅ 已落地：维护手册 §4.9 Subagent 委派监控规范
- 委派前：任务原子化（≤2 步/任务）+ 显式 finish_signal（`###TASK_COMPLETE###`）+ 影子快照
- 运行中：5 分钟心跳探针 + 中间产物日志 + 15 分钟静默告警 + 进程级兜底（服务健康/git diff）
- 超时后：30 分钟强杀 + 三态盘点（已完成/部分/失败）+ 已完成利用（服务健康+测试过=成功）+ 失败重委派去重
- **铁律：超时 ≠ 失败，先看产物再看信号**

---

## 三、自检增强（业界调研落地）

### ✅ 已落地 1：pyright 静态分析集成（audit_check 维度 13 v2）
- **背景**：Librarian 调研发现 pyright 的 `reportUndefinedVariable`/`reportPossiblyUnbound` 是"重构误删变量 → NameError"的直接对症药
- **落地**：audit_check 调 pyright（`cmd /c pyright --outputjson`）→ P0 真未定义 / P1 可能未绑定
- **成果**：检出 1 处真未定义（server.py:3053 fgen 全局+局部赋值混合）+ 10 处 P1 需核查（多为 try/except 兜底保守误报）
- **价值**：重构后"误删变量"在 commit 阶段就能阻断（此前要等运行时 NameError）

### ✅ 已落地 2：属性测试（tests/test_properties.py）
- **背景**：Oracle 推荐的 quick win——"任何合法教学输入，teach_stream 必含 done"
- **落地**：3 个性质测试（完整结束 / 无错误痕迹 / subtopic 传递）
- **成果**：3/3 通过（305s 真实教学流验证）——v0.41.7 事故场景现在有自动防线

### 📋 待做 3：契约测试（schemathesis + openapi.yaml）
- 把 01_API契约.md 的 5 个核心端点转 openapi.yaml → schemathesis 自动生成测试
- 价值：捕获"重构导致响应字段漂移"（当前 test_contracts.py 是手写断言）

### 📋 待做 4：SSE 增强（首事件时延 + 断连测试）
- test_first_event_arrives_under_2s + test_client_disconnect_mid_stream

### 📋 待做 5：突变测试（mutmut，核心模块）
- 需先补覆盖率基线，目标 mutation score ≥ 70%（中期）

### ❌ 不做
- Pact（单体架构不适配）/ 金丝雀发布（单机部署收益低）/ 并发模糊测试（并发量低）

---

## 四、测试金字塔健康度（Librarian 评估）

| 层级 | PAEG 现状 | 业界期望 | 缺口 |
|---|---|---|---|
| 静态检视 | audit 13 维度（含 pyright v2） | — | ✅ 已补 pyright |
| 单元/契约（Small） | ~35 pytest | 70% | ✅ 健康 |
| 服务（Medium） | ~5 端点测试 | 20% | ✅ 健康 |
| 端到端（Large） | smoke + user_journey | 10% | ✅ 教学完整流已补 |
| 属性测试 | 新增 test_properties.py | 可选 | ✅ 已补 3 项 |

---

## 五、下一轮待做（按优先级）

| # | 需求 | 目标 | 改动点 | 验收 |
|---|---|---|---|---|
| 1 | 迁移剩余 4 个 handler | server.py 继续瘦身 | recommend/knowledge/method/problem → services/handlers/ | server.py < 3800 行 |
| 2 | INTERFACE_GUIDE 补 4 桶 | 语音/PPT/气象/复合输入有说明 | self_referential.py | 问"麦克风干嘛用"答对 |
| 3 | schemathesis 契约测试 | API 响应字段漂移自动捕获 | openapi.yaml + test_openapi_contract.py | 契约测试过 |
| 4 | SSE 增强（首事件/断连） | 流式体验 + 鲁棒性 | 2 个新测试 | pytest 过 |
| 5 | pyright P1 10 处核查 | 消除"可能未绑定"隐患 | server.py try/except 兜底加固 | pyright P1 ≤ 5 |
| 6 | mutmut 突变测试 | 测试质量元评估 | 覆盖率基线 + 核心模块 mutmut | score ≥ 70% |

---

*本表由 Sisyphus 于 v0.41.8 更新（Oracle + Librarian 双调研融合）。*
