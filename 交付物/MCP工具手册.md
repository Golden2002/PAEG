# PAEG MCP 标准化工具手册（v1.1 §3.36）

> 面向：二次开发者 / 其他项目移植者。PAEG 的 14 个标准化 MCP 工具——如何调用、依赖什么、如何移植。
> 参考：DeepSeek Harness"一切皆插件"思想——工具应可独立注册、可配置驱动、可移植复用。

## 一、双层注册架构

每个工具同时暴露两个入口（**标准 MCP 协议**，任何 MCP 客户端可调）：

| 层 | 入口 | 调用方 | 实现 |
|---|---|---|---|
| 内部 | `tool_registry.execute_tool(name, args)` | PAEG 内部 LLM（function calling）| tool_registry._HANDLERS |
| 外部 | `mcp_gateway` (http://localhost:8765/mcp) | 外部 agent（Claude/Codex/OpenCode）| mcp_gateway.build_mcp_server |

**配置驱动**：工具声明集中在 `config/mcp_tools.json`（name/description/risk/module/function/params）——改配置可调整，不改代码。

## 二、14 个工具清单

### A. 语言规范类（§3.28）

| 工具 | 用途 | 风险 | 参数 |
|---|---|---|---|
| `normalize_text` | 语言规范守门（L0+L2）——去 AI 味/修正省略句 | read | text, context, apply_l2 |
| `language_policy_check` | AI 味概率 + 违禁词命中（不调 LLM） | read | text |
| `forbidden_words` | 违禁词维护（list/add/remove） | write | action, word, scope |

**示例**：
```
normalize_text(text="简单来说，这个公式很关键，加油！")
→ "这个公式的推导是关键的。我们来说明一下它的来龙去脉。"
```

### B. 约束引擎类（§3.29）

| 工具 | 用途 | 风险 | 参数 |
|---|---|---|---|
| `constraint_layer_get` | 约束层读取（L0-Lmax 放开组/规则） | read | layer |
| `constraint_layer_set` | 动态切换约束层（教学/考试/自由） | read | layer, session, reason |
| `constraint_compose` | 任意提示词块拼接 | read | parts[], title |
| `constraint_always_active` | 永远激活规则管理 | write | action, rule |
| `constraint_self_evolve` | 约束自演化（洞察写入层组） | write | insight, target_layer, group |
| `constraint_feedback_adjust` | 反馈调强/调弱（信号词映射） | read | feedback, target |
| `constraint_layer_scope` | 框架自省（层范围/来源/扩展指南） | read | — |

**示例**：
```
constraint_layer_set(layer=8)  → 切换到外部扩展层 L8
constraint_feedback_adjust(feedback="太啰嗦") → 检测到『啰嗦』→ 建议放宽节奏组(M)
```

### C. 物料生成类（§3.34/§3.35）

| 工具 | 用途 | 风险 | 参数 |
|---|---|---|---|
| `generate_handout` | 生成结构化讲义（门控流水线） | write | topic, subject, learner_id |
| `generate_script` | 生成讲稿（TTS 朗读稿） | write | topic, subject, learner_id |
| `generate_ppt` | 生成 PPT 大纲（供 pptx 排版） | write | topic, subject, learner_id |
| `generate_mindmap` | 生成知识导图（markdown 缩进） | write | topic, subject, learner_id |

## 三、可移植性评估

| 维度 | 状态 | 说明 |
|---|---|---|
| 标准接口 | ✅ | MCP 协议（JSON Schema） |
| 风险分级 | ✅ | read/write 分级 + exam 模式锁定 |
| 数据化 | ✅ | forbidden_words.json / constraint_layers.json / mcp_tools.json |
| 配置驱动 | ✅ | config/mcp_tools.json 声明式 |
| 依赖解耦 | ⚠️ | 语言/约束类独立；物料类依赖 subagents/llm_adapter（注入式可解耦） |
| 独立文档 | ✅ | 本手册 |

## 四、移植指南（其他项目接入）

### 方式 1：MCP 客户端直连（最简）
```python
from mcp import ClientSession, StdioServerParameters
# 或 HTTP：连接 http://<paeg-host>:8765/mcp
# 然后调用任意工具（如上表）
```

### 方式 2：复用工具实现（需注入依赖）
```python
# 语言规范类：纯函数，可直接 import
from language_refiner import LanguageRefiner
refiner = LanguageRefiner(llm=your_llm)   # 注入你的 LLM
hits = refiner.detect_ai_tells(text)

# 约束类：数据化，无需 PAEG 上下文
from constraint_engine import constraint_layer_get, constraint_layer_set
print(constraint_layer_get(4))

# 物料类：需注入 LLM（run_material_pipeline 接受 llm 参数）
from material_pipeline import run_material_pipeline
result = run_material_pipeline(your_llm, "handout", "导数", "数学")
```

### 方式 3：配置驱动注册（改造你的 tool_registry）
1. 复制 `config/mcp_tools.json`
2. 你的注册器按配置生成 tool_defs（name/description/risk/params）
3. 执行时按 `module.function` 路由到你的实现

## 五、加载机制（v1.1.1 §3.36 ⭐ 配置驱动已落地）

**PAEG 已实现配置驱动加载器 `mcp_tools_loader.py`——改 `config/mcp_tools.json` 即生效，无需改代码。**

### 5.1 架构

```
config/mcp_tools.json（声明：name/description/risk/module/function/params/enabled）
        │
        ▼
mcp_tools_loader.py（校验 → 解析 → 安全动态导入 → 生成 (defs, handlers)）
        │
        ├──► tool_registry.get_tool_defs()      （内置 + 配置工具合并）
        ├──► tool_registry.register_external_tools()（handler 合入 _HANDLERS）
        ├──► _WRITE_TOOLS 自动同步              （risk=write 入黑名单，exam 锁定）
        └──► config_hub.reload_all()            （热重载链尾，失败保留旧配置）
```

### 5.2 生效规则（ratchet 铁律：不破坏现有功能）

| 场景 | 行为 |
|---|---|
| 改 description/params | 工具表立即反映（`get_all_tool_defs()` 变化） |
| 新增工具条目 | 工具表增加该工具（需 module/function 在白名单且可导入） |
| 删除工具条目 | 工具表移除该工具（配置可下架） |
| `enabled: false` | 该工具不注册（保留声明可追溯） |
| 内置工具冲突 | **内置优先**（仅元数据被配置覆盖）；覆盖 handler 需 `override: true` |
| `risk: write` | 自动入 `_WRITE_TOOLS` 黑名单 → exam/read_only 模式锁定 |
| 单条声明损坏 | 跳过该条 + 日志，不影响其他工具 |

### 5.3 安全边界（参照 LangFlow GHSA-2wcq-pvw2-xh7v）

- `module` 必须在白名单前缀：`tool_registry / constraint_engine / material_pipeline / services / lib / utils`
- 拒绝危险模块：`os / sys / subprocess / shutil / importlib / builtins / pickle / yaml / ctypes / socket`
- `function` 必须非下划线开头的合法 Python identifier
- 永不 `exec/eval`——只用 `importlib.import_module` + `getattr` + callable 检查
- 工具名匹配 MCP SEP-986：`^[A-Za-z0-9._-]{1,128}$`

### 5.4 热重载

```python
from config_hub import get_hub
get_hub().reload_all()   # 改 config/mcp_tools.json 后调用即生效（失败保留旧配置）
```

或 HTTP：`POST /api/admin/reload`（config_hub 动态重载入口）。

### 5.5 移植示例（其他项目接入）

```python
# 1. 复制 mcp_tools_loader.py + config/mcp_tools.json
# 2. 调整 _ALLOWED_MODULE_PREFIXES 为你的模块前缀
# 3. 启动时调用 load_config_tools()，把 (defs, handlers) 合并进你的注册表
# 4. 热重载调 reload_config_tools()（原子替换，失败回退旧配置）
```

## 六、最佳实践（对齐 Anthropic/Harness）

1. **description 是 system prompt**：3-4 句，说清何时调用
2. **参数必有 description + 范围**（min/max/enum）
3. **additionalProperties: false**（严格 schema）
4. **工具数量 ≤30**：过多模型选错率飙升
5. **错误返回 is_error 信号**：让模型自主决定重试
6. **写工具必标 risk**：exam 等敏感模式锁定
7. **配置即契约（v1.1.1 §3.36）**：工具声明集中在 mcp_tools.json，改配置不改代码；新增工具先写 example.json 验证再启用
