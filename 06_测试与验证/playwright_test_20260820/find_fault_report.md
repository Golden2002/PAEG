# PAEG 找茬式 E2E 报告（2026-08-20T23:51:30）

- 通过：9 · 问题：6

## 问题清单

- **A2 教学-追问**：Page.wait_for_function: Timeout 60000ms exceeded.
- **A3 倾诉-危机信号**：Page.wait_for_function: Timeout 90000ms exceeded.
- **A4 找答案**：Page.wait_for_function: Timeout 90000ms exceeded.
- **B2 乱码输入**：Page.wait_for_function: Timeout 45000ms exceeded.
- **B4 注入尝试**：Page.wait_for_function: Timeout 60000ms exceeded.
- **B5 情绪+学习混合**：Page.wait_for_function: Timeout 90000ms exceeded.

## 通过清单

- A1 首页加载+模式按钮可见
- A2 教学-概念 有回复
- B1 空输入 不崩溃
- B3 超长输入 有回复
- B6 快速连续发送 页面存活
- D1 模式快速切换 稳定
- B7 非法 learner_id 不 500
- C1 并发 health×20 无 5xx
- C2 并发 teach/stream×6 无 5xx
