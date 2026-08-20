# PAEG 找茬式 E2E 结论（2026-08-20 · §3.79 Round 7）

## 方法
Playwright（headless Chromium）模拟真实用户：6 模式对话 + 找茬输入（空/乱码/超长/注入/混合/连点/模式切换）+ 并发压力 + 前端控制台错误捕获。
产出：`find_fault_e2e.py`（可重复运行）、`find_fault_report.json/.md`（逐用例）、`focused_affection.py`（定位辅助）。

## 发现的问题（真实 Bug，已修复 3 项）

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | `/api/teach/stream` 直接 **HTTP 500**（教学/倾诉/找答案全挂） | 生成器函数内 `data = request.get_json()` 在流式迭代时执行——**请求上下文已弹出**（"Working outside of request context"） | `teach_stream` 改为外层普通函数读 data + `stream_with_context(_teach_stream_gen(data))`（Flask 官方流式方案，上下文全程保持） |
| 2 | 早退分支（affection/lesson_prep/unknown 等 18 处）`return Response(gen_x(), ...)` 在生成器内是 **StopIteration——Response 被丢弃，客户端收空流** | 生成器函数内 return 不发送响应（结构性缺陷） | 18 处统一改为 `yield from gen_x()` + `return`（早退语义保持，SSE 头由外层统一设置） |
| 3 | **主教学循环 `generate()` 从未真正输出**——函数尾 `return Response(generate(), ...)` 同样被丢弃 | 同上结构性缺陷（generate 定义的 1500 行主循环是死代码） | 末尾改 `yield from generate()`——教学主路径恢复（retrieval→diagnosis→plan→presentation 全事件流） |

**验证**：修复后 `/api/teach/stream` 恢复完整事件流（HTTP 200 + text/event-stream + retrieval/diagnosis/plan/step）；倾诉 3s、注入 1.9s、找答案 36.8s 均正常回复；并发 health×20 + teach×6 无 5xx；server 相关 pytest 75/75 全绿。

## 其他发现（记录，下轮处理）

| # | 发现 | 性质 | 建议 |
|---|---|---|---|
| 4 | **前端对错误静默**：429/500 时聊天窗口无任何反馈（用户看到"没反应"） | 真实 UX 缺陷 | 前端捕获非 200/error 事件 → 显示"服务繁忙，请稍后再试"（下轮 UI） |
| 5 | **LLM 延迟高**：找答案 36.8s、教学追问 >60s | 性能（真实 LLM + 网络） | D1 SLO 监控 + 超时/降级策略（下轮） |
| 6 | E2E 同 IP 累积触发 429 限流（30 次/分钟 LLM） | 环境 + 限流设计（合理） | 测试脚本加节流/等待窗口 |

## 结论
**找茬有效**：找到了会让教学/倾诉/找答案在真实场景完全失效的 3 个结构性 Bug 并已修复——这是"模拟真实用户使用"的典型价值。产品层剩余问题（错误反馈 UX、LLM 延迟）已记录进 `总需求与执行标准 §3.7/§4.7` 下轮计划。
