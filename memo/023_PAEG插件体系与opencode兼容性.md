# 023 · PAEG 插件体系与 opencode 兼容性（v0.53）

> 日期：2026-08-11
> 目的：确认 PAEG 能否集成 opencode 式插件（skill + MCP），记录接入方式。

---

## 一、现状确认（架构完全兼容）

PAEG 已采用 **opencode 同款标准 MCP server**（mcp_client.py 明确声明）：

| MCP Server | 类型 | 状态 | 说明 |
|---|---|---|---|
| filesystem | npx 标准 | ✅ 启用 | 文件读写（sandbox 限定）|
| memory | npx 标准 | ✅ 启用 | 知识图谱记忆 |
| pptx | python | ✅ 启用 | PPT 生成（自研）|
| fetch | npx 标准 | ⚠️ 关闭 | 网页抓取 |
| git | npx 标准 | ⚠️ 关闭 | Git 操作 |
| brave-search | npx 标准 | ⚠️ 关闭 | 需 BRAVE_API_KEY，可增强检索 |

**Skills**：SkillRegistry 扫描 skills/ 目录，当前 10 个（concept-explainer/docx/pdf/teach 等）。

## 二、接入 opencode 插件的方法

**MCP**：把 opencode 的 MCP server 声明加入 `mcp_servers.json`（command = npx 标准 server）→
`mcp_client.connect_all()` 自动加载 → LLM 工具调用。

**Skill**：把 opencode 的 skill 目录复制到 `skills/`（每个 skill 一个文件夹 + SKILL.md）→
SkillRegistry 自动注册 → LLM 可通过 tool_registry 调用。

## 三、可增强项（按价值）

1. **brave-search MCP**（需 BRAVE_API_KEY）：高质量搜索引擎，替代 Bing 抓取 → 检索质量跃升
2. **fetch MCP**：网页全文抓取（增强 fetch_page 能力）
3. **git MCP**：版本控制操作
4. **更多 skill**：把 opencode 的成熟 skill（如 playwright 浏览器自动化）接入

## 四、当前检索增强（v0.53 已实现）

- 5 主题 × 3 轮变体（原词+shorten+学科组合）= 15 次请求 → 实测 16 条（≥10 达标）
- 中英双语关键词（LLM 直接给关键词，含英文专业术语）
- jieba 核心词相关性去噪（去"智联招聘"类噪音）

## 五、待办

- [ ] brave-search 接入（用户提供 BRAVE_API_KEY）
- [ ] fetch MCP 启用（增强抓取）
- [ ] 更多 opencode skill 接入评估
