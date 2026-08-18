"""blueprints 包 — PAEG HTTP 蓝图（§3.45 架构导向拆分）。

职责边界：
- 只做 HTTP 层（路由 + 请求解析 + 响应序列化）
- 业务逻辑下沉 services/，基础设施走 infra/（runtime 懒加载单例）
- 依赖方向：server.py → blueprints → services/infra（单向；蓝图禁止反向依赖入口模块，否则循环导入）

拆分纪律（audit 常驻检查支撑）：
- 行为字节级不变（Expand-Migrate-Contract，每步可回滚）
- `server.SESSIONS is infra.sessions.SESSIONS`（同引用）
- 迁移时 `__file__` 相关路径需上溯 parent.parent（blueprints/ 比 server.py 深一层）
"""
