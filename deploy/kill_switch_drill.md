# PAEG Kill Switch 演练记录（D2 验收 · §3.79 Round 8）

> 依据：deploy/灰度回滚规范.md §二（Kill Switch 60s 止损）与 §五 验收（演练记录，季度一次）。
> 演练目的：验证"发现 P0 → 60s 内远程关闭模块 → 热重载生效 → 恢复"全链路可执行。

## 演练 1（2026-08-21 · Round 8）

**场景**：模拟"voice 语音模块出现 P0（如 TTS 死循环占资源）"，需 60s 内止损。

| 步骤 | 操作 | 命令/端点 | 结果 | 耗时 |
|---|---|---|---|---|
| 1 | 确认当前 voice 状态 | `GET /api/admin/modules` → voice.enabled=true | ✅ 在线 | <1s |
| 2 | 远程关闭 voice（kill switch） | `POST /api/admin/modules {"module":"voice","enabled":false}` + `X-Admin-Token` | ✅ 200，原子写 paeg_modules.json | <1s |
| 3 | 验证热重载生效（无需重启） | `GET /api/admin/modules` → voice.enabled=false + `module_registry.is_enabled("voice")==False` | ✅ 即时生效 | <1s |
| 4 | 审计可追溯 | events.jsonl 查 `module/toggle` 事件（module=voice, to=false, operator） | ✅ 已落盘 | — |
| 5 | 模拟修复后恢复 | `POST /api/admin/modules {"module":"voice","enabled":true}` | ✅ 恢复在线 | <1s |
| 6 | 全链路验证 | `GET /api/admin/modules` → voice.enabled=true + smoke_test.py | ✅ 服务正常 | ~30s |

**演练结论**：PASS —— 从发现到模块关闭 <10s（远低于 60s 止损线）；热重载免重启；审计完整。
**遗留**：未配置 `PAEG_ADMIN_TOKEN` 时写操作 401（安全默认）——生产部署**必须**设置该环境变量。

## 演练 SOP（下次执行用）

```
1. 预检：确认 $env:PAEG_ADMIN_TOKEN 已设置；GET /api/admin/modules 可访问
2. 演练：POST 关闭目标模块（如 voice）→ GET 验证 → 记录时间戳
3. 恢复：POST 开启 → GET 验证 → smoke_test.py 确认服务正常
4. 审计：events.jsonl 查 module/toggle 事件
5. 复盘：记录演练时间/结果/问题 → 补 golden set 回归（若有缺陷）
```
