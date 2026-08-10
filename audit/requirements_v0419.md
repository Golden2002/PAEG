# PAEG v0.41.9 专项需求表（前端 bug 修复 + 审计增强 + 测试质量）

> 来源：v0.41.8 复盘 + Oracle 策略咨询 + 用户"猛攻下一轮"指示
> 目标：①修 2 个前端 bug（停止键/语音双发送）②固化 v0.41.7-8 反思为常驻检查 ③测试质量可量化评估
> 更新：2026-08-10

---

## 一、v0.41.9 已完成项

### Bug 修复（用户实测反馈）
| Bug | 根因 | 修复 | 验证 |
|---|---|---|---|
| 停止键无反应 | ask-btn click handler 无 data-generating 分支，被 if(!q) 拦截 | 加生成中分支 → abort + 恢复按钮 | 前端代码验证（括号配平 OK） |
| 语音双发送复发 | 三层：_voiceSendOnce 内 addMsg+askBtn.click 双 addMsg / voiceBtn 异步启动重复点创建双 MediaRecorder / 合成 click 碰撞 | ①直调模式函数（不 askBtn.click）②STT 提交锁 _sttSubmitting ③长按直调 _startBackendSTT | 前端代码验证 |

### 审计增强（Oracle 策略 #2/#3）
| 项 | 内容 | 验证 |
|---|---|---|
| pyright P1 归零 | 修 _summary_avg（try 内定义被跨 try 引用）+ _tb（try 内 import 被 except 引用）| pyright 0 可能未绑定 + 0 真未定义 |
| audit 维度 14 模块化健康 | services/handlers 5 件套齐全 + server.py <4000 行 + handler 已迁出 + 无循环依赖 | **发现并修复 routing.py 循环依赖**（from server import → services.handlers 直导）+ 修正则（注释误报） |
| 最终 | **audit 32/32 全绿** | |

### 测试质量评估（Oracle 策略 #4 探针决策）
- **mutmut 不适用**：Windows 无 WSL 支持（官方 issue #397）→ 改用 pytest-cov 覆盖率基线
- **覆盖率基线**：services/ 55%（routing 90%/method 88%/problem 88% 高；steering 30%/keyword_doc 22% 低——LLM 调用密集路径，符合预期）

### 并发写锁审查（Oracle 策略 #5 只读）
| 模块 | 锁 | 结论 |
|---|---|---|
| reflection_store | _DB_LOCK + WAL | ✅ 安全 |
| self_update | 锁引用存在 | ✅ 安全 |
| user_store | 锁引用存在 | ✅ 安全 |
| server.py | 无直接文件写（经 store） | ✅ 安全 |

### 文档
- 技术文档 §10.2.29（本次成功维护可复制方法）
- 元能力 §6.23（智能体使用方法论）
- 启动指南.md（后端/wbo/公网隧道）

---

## 二、待办（用户实测验收）

| # | 需求 | 说明 |
|---|---|---|
| 1 | 停止键用户实测 | 浏览器强制刷新（Ctrl+F5）→ 教学生成中点"■ 停止" → 应停止 |
| 2 | 语音双发送用户实测 | 刷新后语音输入 → 应只有一条消息 |
| 3 | 覆盖率提升 | steering/keyword_doc 低覆盖（LLM 密集），下轮补测试 |

---

## 三、明确不做
- mutmut（Windows 不兼容）→ pytest-cov 替代
- blueprints 拆分（Phase 3，高风险，v0.42+）
- schemathesis 升级（jsonschema 已覆盖）

*本表由 Sisyphus 于 v0.41.9 更新。*
