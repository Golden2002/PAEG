# PAEG v0.41 架构优化需求表（2026-08-09）

> 来源：Oracle 架构优化方案 + 成熟项目调研（Flask 官方/llama-index/langchain/pytest 官方/Kraken/EAS Station）
> 目标：解决自我评估发现的不足（巨型单文件/安全/测试隔离/STT 前端未接）

## 一、问题清单（自我评估 → 调研确认）

| # | 问题 | 成熟项目做法 | 本轮优先级 |
|---|---|---|---|
| 1 | server.py 4500 行巨型单文件 | Flask blueprint + application factory + 分层（routes/services/infra） | P1（Phase1 抽 config/utils） |
| 2 | subagents.py 2600 行 | 按"变化原因"拆模块（registry/orchestrator/prompts/tools） | P2（延后） |
| 3 | index.html 3900 行单文件 | ES modules 渐进拆分（不引构建工具） | P2（延后，STT 顺手拆 voice） |
| 4 | 无认证（learner_id 信任） | JWT + httpOnly cookie（多用户上线前必做） | P2（延后，触发条件：用户量>5） |
| 5 | 无依赖/secret 扫描 | pip-audit + gitleaks pre-commit | **P0（本轮）** |
| 6 | SECRET_KEY 可能硬编码 | 环境变量 + .env + dotenv | **P0（本轮）** |
| 7 | 3 个测试状态污染 | tmp_path + monkeypatch + function-scope fixture | **P0（本轮）** |
| 8 | STT 前端未接后端 | MediaRecorder → POST /api/voice/stt（Web Speech 作 fallback） | **P0（本轮，用户痛点）** |

## 二、本轮实施（P0 × 4 + P1 Phase1）

### P0-1 测试隔离（0.5 天）
- 根因：test_individuality/test_routing 共享 users.json/users_data 文件
- 修复：conftest.py 加 tmp_path + monkeypatch fixture，隔离 data 目录
- 验收：245/248 → 248/248（含单独跑+连跑）

### P0-2 安全基线（1 小时）
- SECRET_KEY/JWT_SECRET 从环境变量读取（无默认值）
- pip-audit 扫描依赖（装 pip-audit 跑一次，记录结果）
- 验收：无高危依赖；密钥不在代码

### P0-3 STT 前端接后端（4 小时）
- 前端：MediaRecorder 录音 → POST /api/voice/stt → 回填输入框（不直接发送，用户复核）
- Web Speech API 保留作 fallback（iOS Safari）
- 与长按/麦克风/气泡交互兼容
- 验收：Chrome 录音→识别→输入框显示文本；失败降级提示

### P1-1 server.py Phase1 拆分（1 天）
- 抽 config.py（配置+常量+路径）
- 抽 utils.py（纯函数工具）
- 抽 extensions.py（裸扩展模式，消除循环导入）
- Expand-Migrate-Contract 三阶段，不动业务逻辑
- 验收：4500→3800 行；245 测试全过

## 三、延后项（触发条件明确）

| 项 | 触发条件 |
|---|---|
| subagents 模块化 | 新增第 4 个 subagent 时 |
| JWT 认证 | 用户量 >5 或对外公网暴露 |
| 前端全拆分 | index.html >5000 行 |
| application factory | 需要多环境配置/独立测试配置时 |

## 四、验证方法论（阶段4）

1. audit_check.py 15 项全绿
2. pytest 248/248
3. smoke_test 12/12
4. STT 手动测 5 次（中英混/安静/嘈杂）
5. 综合测试（6 模式/学段/学科/混沌/多轮）
