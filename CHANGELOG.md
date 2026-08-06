# PAEG 修改日志（CHANGELOG）

> 独立于《技术全景文档》的版本历史。
> 最新版本在最上方。每次迭代在此追加。

---

## v0.20.3（2026-08-06）

**统一上下文打包器 + 模式自动纠正（关键技术）**

### 1. 上下文打包器（context_bundle.py ⭐）
- **问题**：各端点上下文注入不一致——chat_stream 完整，affection/knowledge/method/answer 缺画像/BDI；teach_stream 主循环漏 user_model 推断
- **ContextBundle**：build_user_model_bundle（infer_user_model + BDI）/ build_learner_context（昵称/学段/自我陈述/掌握度/BDI）/ build_meta_context（模式/学科/学段）/ assemble_messages（多轮历史）
- **修复**：
  - teach_stream 主循环补 user_model/BDI 推断（原漏洞——手动教学循环没走 paeg.teach 注入）
  - teach_stream 创建 LearnerProfile 补 self_description 字段（与 teach 不一致）
  - AffectionSupportor 注入 user_model/BDI（情绪场景最需要 BDI：subject_fear/about_to_give_up）
  - knowledge 端点 system 注入学生画像段

### 2. 模式自动纠正（_mode_auto_correct ⭐）
- **问题**：method/knowledge/affection/answer 端点完全裸奔——用户选错模式后端不纠正
- **修复**：_mode_auto_correct 函数（优先级：情绪 > 知识库 > 方法 > 出题），method/knowledge/affection 端点接入；响应带 actual_mode/requested_mode/was_redirected 字段
- **实测**：
  - 选"学习方法"实际倾诉 → 纠正到 affection（"老师不催你解释什么"）✓
  - 选"倾诉"问知识库 → 纠正到 knowledge ✓
  - 选"知识库"问数学题 → 保留知识库（不误伤）✓

### 3. 其他
- 测试 59/59

---

## v0.20.2（2026-08-06）

**多轮对话连贯性修复（核心 bug）+ GitHub 项目完整性**

### 1. 对话连贯性修复（用户发现的关键 bug）
- **根因**：`_safe_chat`（subagents.py:32）内部硬编码 `messages=[{"role":"user","content":user}]`——所有调用方传的历史被丢弃，LLM 永远只看 system + 当前一句话
- **各模式状态（修复前）**：chat_stream/chat 半回传（历史拼字符串塞 user）；teach_stream/affection/knowledge/method/answer **零回传**
- **修复**：
  - `_safe_chat` 升级支持 messages 列表参数（旧风格兼容）
  - `run_agent_loop` 新增 history 参数（在 user_input 前注入历史）
  - chat_stream：传真 messages 历史（最近 10 条 user/assistant）
  - AffectionSupportor.run 新增 history 参数 + 4 个 affection 入口（teach/teach_stream/chat_stream/api 端点）传 chat_hist
- **实测**：chat_stream 两轮（"我叫小明喜欢篮球"→"我叫什么？"→"你叫小明，你喜欢篮球，这两句我都记住了"）；affection 两轮（"考试考砸难过"→"数学考砸了"→"我听到你说'就是数学考砸了'"）✓

### 2. GitHub 项目完整性
- 补全 Library 目录结构：Language/Philosophy/Simone Weil/user_qa_lib（占位 README，说明资料如何恢复）
- 重要文档已上传（00_Gap/01-04 设计/08_Loop/亮点总览/小红书推文）
- 从 GitHub 可拉出完整项目骨架 + 全部代码/文档

### 3. 其他
- 测试 59/59

---

## v0.20.1（2026-08-06）

**emotion → affection 命名统一（纯命名变化，逻辑不变）**

- server.py：EmotionSupportor→AffectionSupportor、is_emotion_expression→is_affection_expression、emotion_support→affection_support、/api/emotion→/api/affection、step_type/mode/session_id 全部 emotion→affection
- meta_router.py：EMOTION_PATTERNS→AFFECTION_PATTERNS、is_emotion_expression→is_affection_expression
- subagents.py：EmotionSupportor→AffectionSupportor（保留无关的 emotion_signal——那是 Evaluator 的情绪信号字段）
- index.html：/api/emotion→/api/affection
- 验证：4 文件 emotion 全清（零残留）、affection 全面替换、语法 OK、/api/affection 工作（step_type=affection）、旧 /api/emotion 移除、测试 59/59

---

## v0.20（2026-08-06）· 文档亮点完整化

**核对并补全技术文档全部亮点章节**

- **修复**：文档版本号 v0.19.28 → v0.20（此前 §1.12 已标 v0.20 但头部未更新）
- **§1.9.4 新增**：面向市场的垂直领域优势（市场观察→切入 / C 端 B 端分层 / 差异化壁垒 / 一句话市场定位）
- **§1.6.10 新增**：为什么这套 Agent 架构是革命性的（六维度对比表：教学循环/子代理分工/意图路由/自我进化/工具互通/语言质量 + "从工具到教师的架构跃迁"）
- **§1.11.5 新增**：生命现象学维度 14 条原则（约纳斯/梅洛-庞蒂/海德格尔/Jaspers/Sartre）+ 约纳斯克制语言风格（6 规则/禁词/3 段参考）
- **亮点覆盖核对**：20 项全部 OK（博雅教育/市场优势/语法质量/架构革命性/三大支柱/教学循环/子代理/harness/tool-use/角色提示词/自我更新/MCP 双向/Steering/学科定制化/自我指涉/情绪支持/约纳斯风格/生命现象学/测试方法论）

---

## v0.20（2026-08-06）

**全局中文语言质量层（v0.20 ⭐ 项目亮点）+ 修复 teach_stream 绕过 refiner 漏洞**

### 1. L1 提示词约束（prompts.py 统一中文输出规范）
- 新增"动宾搭配与省略边界"段（注入所有 system prompt）：
  - 主谓必须真搭配（不用"进行/展开/赋能"装饰）
  - 谓宾必须真搭配（禁止"带着重量"——"带"不能随身带重量）
  - 无主语短语禁止单独成句："不催你"→"老师不催你，你慢慢来"；"先不急"→"我们先不着急"；"已经带着重量"→"这句话本身已经有很重的分量"
  - 合法省略边界（3 种可省略 + 讲解/总结/承诺必须显式主语）

### 2. L2 规则检测（language_refiner._check_ellipsis 扩展）
- 新增无主语短语检测："不催你/先不急/先别急/别催/带着重量"等
- 新增动宾搭配不当检测："带着重量/分量/意义/温度""做着思考/努力""进行一个分析"
- 实测：8 个测试样本——"不催你/先不急/带着重量"全捕获，合法句（"老师不催你""我们先不着急""这句话本身已经有很重的分量"）零误报

### 3. L3 LLM 修正（minimal-edit + 风格保留）
- _build_system 加：最小改动/保留已通顺句/不重写风格/教学场景补主语/修正动宾搭配
- 修正 prompt 明确"不改变语气和人格"

### 4. 修复 teach_stream 绕过 refiner 漏洞
- **根因**：teach_stream（前端教学实际接口）手动重写教学循环，跳过 paeg.teach 内的 refiner 钩子——教学输出零语言优化
- **修复**：teach_stream presenter 后补 refiner 调用（LLM 生成才 refine）
- **全局接入**：新增 `_polish_text` 辅助函数（AI 味 or 省略句 or 动宾搭配才触发 LLM 改写），接入 teach emotion 分支 + /api/emotion 端点

### 5. 实测效果（affection 模式）
- 之前："这句话本身，已经带着重量"（动宾不当）→ 现在："这句话很重"（正确）
- "我不急着反驳你""我先不急着问你发生了什么"——完整主谓
- 禁词 0 命中 · 测试 59/59

---

## v0.19.30（2026-08-06）

**affection 支持升级：生命现象学维度 + 约纳斯克制语言风格 + 文件改名 AffectionSAPAO.md**

### 1. 生命现象学维度（参考 Library 约纳斯原著 + 在线权威）
- EMOTION_SUPPORT_CORE.md 扩充"八·五、生命现象学维度"（14 条原则）：
  - **约纳斯 J1-J5**：脆弱性即生命力 / 情绪需被代谢 / 求助即需要性自由 / 引导向未来性 / 有限性即珍贵性
  - **梅洛-庞蒂 M1-M3**：情绪栖居于身体 / 身体图式先于语言 / 新动作打开新世界
  - **海德格尔 H1-H3**：焦虑是"我在乎"的标志 / 有限性赋予本真性 / 拥抱而非沉思有限性
  - **Jaspers B1** 边界情境 · **Sartre S1** 情绪主动转化
- 支持语示例（"承认需要帮助，本身就是你能为自己做的最有尊严的事之一"等）

### 2. 约纳斯克制语言风格（真实/朴素/克制）
- EmotionSupportor system prompt 新增"语言风格（参照汉斯·约纳斯的克制笔法）"段：
  - 6 条规则：名词承重 / 连接词外露 / 谈沉重主动降温 / 概念即时解释 / 第一人称承担具体责任 / 短句重心
  - 禁词清单（震撼/深刻地/无与伦比/警钟/拷问/终极/里程碑/觉醒/蜕变 等）
  - 2 段约纳斯原文风格参考（"一场赌注和风险不断加码的实验""把灾祸的预言放在前面"）
- **实测**：3 条情绪输入全部禁词 0 命中 + 语言克制化（"这句话本身，已经带着重量"名词承重；"我在这里，不催你"6 字重心句）+ 梅洛-庞蒂身体提问（"压力在胸口还是肩膀"）

### 3. 文件改名
- EMOTION_SUPPORT_CORE.md → **AffectionSAPAO.md**（用户指定命名），subagents.py 引用同步更新

### 4. 其他
- _load_principles 长度限制 3000 → 6000（容纳生命现象学）
- 测试 59/59 通过

---

## v0.19.29（2026-08-06）

**affection 倾诉模式（情绪支持独立对话类型）**

- 新增 `/api/emotion` 端点：显式选择"倾诉"模式时走 EmotionSupportor（不教不答，以注意力陪伴）
- 前端新增第 6 个模式按钮 **"倾诉"**（data-mode="affection"）+ affectionChat 函数 + "倾诉 · 我在听" 标签 + placeholder
- 命名：affection/affectionChat（用户指定），后端 API 路径保持 /api/emotion
- 实测（真实浏览器）：点"倾诉"→ 输入"最近总觉得自己很没用"→ "倾诉 · 我在听"标签 + 悬置判断/注意力陪伴回应 ✓
- 测试 59/59

---

## v0.19.28（2026-08-06）

**测试方法论文档化（含 Playwright 浏览器测试）**

- 技术文档新增 §10.2.1（端到端 API 测试：qa_*.py 脚本 + 关键断言清单）
- 新增 §10.2.2（Playwright 真实浏览器测试：核心流程 8 步 + 关键检查点表 + 历史教训坑位表）
- 新增 §10.2.3（测试金字塔总览：Playwright → API → eval_harness → pytest 59 + 开发节奏）
- 记录 v0.19.24 的"气泡不显示"bug 教训（API 正常但前端渲染失败必须用浏览器测）
- 浏览器实测补充：界面自指涉 + 情绪支持在真实浏览器验证通过

---

## v0.19.27（2026-08-06）

**自我指涉模块 + 情绪与心理支持 subagent（哲学三角）**

### 1. 自我指涉模块（Self-Referential）
- **问题**：用户问"这个界面上不同的按钮是做什么用的"，agent 无法正确回答（META_PATTERNS 不覆盖界面类问题，LLM 自由生成易漏）
- **self_referential.py（新）**：界面指南模板（8 大子主题：模式/输入/账户/侧栏/气泡/动作/生成/试试）+ is_interface_query（界面/按钮/怎么用/功能/模式切换检测）+ handle_interface_query（按关键词分桶返回）
- **server 接入**：teach/teach_stream 的 knowledge 拦截前，step_type=interface
- 实测："这个界面上不同的按钮是做什么用的"→完整界面指南；"模式切换怎么用"→模式段落；"你是谁"→不误触发 ✓

### 2. 情绪与心理支持 subagent（第 7 个子代理）
- **调研**：librarian 双路（薇依 Stanford/IEP 综述 + 尼采/胡塞尔 SEP 综述）+ Library《西蒙娜·薇依文选》+ weil_corpus.json
- **EMOTION_SUPPORT_CORE.md（新）**：情绪支持宪法——哲学三角（胡塞尔怎么看/薇依为何看/尼采看完后如何重新站立）+ 7 大维度（人生观扎根/幸福观爱命运/价值观善恶美学/道德论义务先于权利/美学注意力/科学观生活世界/政治观扎根）+ 三阶段对话流程 + 6 条红线 + 15 条引文
- **EmotionSupportor（subagents.py 第 7 个子代理）**：加载 EMOTION_SUPPORT_CORE 注入 system，三阶段回应（现象学倾听→注意力深入→自我克服）
- **meta_router.is_emotion_expression**：情绪/心理/人生困惑检测（难过/焦虑/孤独/迷茫/意义/失恋等 20+ 模式）
- **server 接入**：teach/teach_stream（出题拦截后、意向性前）+ chat_stream（闲聊模式情绪优先）
- 实测：
  - "我最近好难过"→"我不急着问你为什么……陪着你坐一会儿……像一块沉沉的石头，还是像一层灰蒙蒙的雾"（悬置+注意力+回到体验）✓
  - "我好孤独"→"是身边没有人，还是即使有人，也觉得没有人真正看见你……被一个人认真听见了"（意向性+注意力）✓
- 测试 59/59 通过

---

## v0.19.26（2026-08-06）

**Agent Steering（学科自动识别切换）+ 未收录学科反馈闭环 + 博雅教育定位文档化**

### 1. Agent Steering：学科自动识别（核心）
- **问题**：用户设定"考研政治"，问经济学问题，agent 仍用政治 persona 回答（steering 缺陷）
- **subject_detector.py（新）**：LLM 从 26 学科识别问题学科 + 规则关键词兜底 + 10 分钟缓存 + 失败安全（保持用户设定）
- **server.py _steer_subject**：在 `subject = data["subject"]` 后、meta 拦截前——识别学科 ≠ 用户设定 → 覆盖 subject（下游全链路生效）；切换打日志 `[PAEG][steering]`
- **实测**：
  - 考研政治设定问"商品价值由什么决定" → 切换经济学（沙漠金子直觉引入）✓
  - 高中政治设定问"什么是供需曲线" → 切换经济学（早餐店供需讲解）✓
  - 未收录学科"量子力学" → unregistered_subject 反馈 + 记录需求 ✓

### 2. 未收录学科 → 自我更新闭环
- `record_subject_request`（self_evolution.py）：写入 evolve_data/subject_requests.json（去重+计数+concepts）
- 向用户反馈："我已经把这条需求记下来，后续会优先优化升级"
- `periodic_self_update._do_weekly` 第 4 步：读 subject_requests → 按 count 生成新增学科建议 → improvements.md → teaching_memory 自动注入 system
- **修复**：periodic_self_update.py 缺 os/json import（第 4 步 NameError）
- **实测**：量子力学需求 → subject_requests.json → 周度任务 → improvements.md "新增学科建议：量子力学" ✓

### 3. 技术文档
- §1.7 Agent Steering（问题/方案/闭环）
- §1.8 学科/学段定制化技术实现路径（SUBJECT_STYLES/_GRADE_GUIDE/别名/调用链/分层效果）
- §1.9 市场垂直优势：专门的博雅教育（定位/与通用教育AI差异/一句话定位）
- 测试 59/59 通过

---

## v0.19.25（2026-08-06）

**经济学学科 + 学习方法/知识库独立对话类型 + MCP 双向打通 ⭐**

### 1. 经济学学科
- prompts.py 新增 SUBJECT_STYLES["economics"]（persona/language/structure/emphasis）+ 别名（经济学/经济）
- 前端 subject-select 加 option
- 实测：教学"什么是机会成本"→ 一百块钱买书/看电影的直觉引入 ✓

### 2. 学习方法 + 知识库独立对话类型
- 新增 `/api/method` 端点：显式选择"学习方法"模式时，无论输入什么（不必命中 is_method_advice）都走学习方法指导，step_type=method
- 新增 `/api/knowledge` 端点：显式选择"知识库"模式时清点 Library，step_type=knowledge
- 前端加 2 个模式按钮（学习方法/知识库）+ methodChat/knowledgeChat 函数 + mode-tag 样式
- 实测："/api/method 怎么复习经济学"→ 先讲通病再给方法；"/api/knowledge"→ 清点资料库 ✓

### 3. MCP 双向打通（借鉴 oh-my-opencode/opencode ⭐ 核心）
- **现状**：PAEG 只是 MCP Server（对外暴露 7 个工具），内部 LLM/subagent 无法调外部 MCP
- **调研**：oh-my-opencode 的 Skill-Embedded MCP + opencode 的 mcp 配置（npx 启动 @modelcontextprotocol/server-*）
- **新增 mcp_client.py**（fastmcp.Client）：连接外部标准 MCP server（filesystem 14 工具 + memory 9 工具），mcp_servers.json 配置
- **改造 tool_registry**：get_all_tool_defs 合并 MCP 工具（mcp__server__tool 命名）；execute_tool fallback 到 MCP 客户端
- **同步 MCP-only 工具**：solve_problem/save_document 加入 FC 端（内部 LLM 也能用）
- **结果**：服务端 34 个工具（内置 FC 11 + 外部 MCP 23），LLM/subagent 可通过 Function Calling 调文件系统/记忆等标准化工具
- 实测：execute_tool("mcp__filesystem__list_directory") → 返回真实目录列表 ✓
- 测试 59/59 通过

---

## v0.19.24（2026-08-06）

**关键修复：闲聊模式气泡不显示的 JS bug（Playwright 实测定位）**

- **根因**：`generalChat` 里 3 处 `if (!bubbleBody.parentNode) chatWin.appendChild(bubble)` 判断错误——`bubbleBody.parentNode` 永远等于 bubble 自身（即使 bubble 尚未进入聊天窗口），导致**回复气泡永远不被 append 到 DOM**：后端流式响应正常（HTTP 200 + seg + done），但前端无任何输出
- **诊断方法**：Playwright 真实浏览器复现——网络请求 200 且响应体完整，但 DOM 无回复气泡；逐行复刻 SSE 解析逻辑可正常解析 → 定位到 append 条件 bug
- **修复**：3 处改为 `if (!bubble.isConnected)`（`isConnected` 才真正反映元素是否在文档中）
- **实测（公网真实浏览器）**：
  - 闲聊模式"你好" → Émile 正常回复气泡 ✓
  - 闲聊模式"知识库" → 正确清点 Library 资料 ✓
- 测试 59/59 通过

---

## v0.19.23（2026-08-06）

**关键修复：/api/teach/stream 补齐拦截链（前端实际接口）**

- **根因**：前端 teach() 调用的是 `/api/teach/stream`（SSE 流式），但 v0.19.22 的知识库/意向性/方法/出题拦截只加在 `/api/teach`（同步版）——前端实际走的接口完全没有这些拦截，导致"知识库/闲聊/一般性问题"全部走了普通教学 harness
- **修复**：teach_stream 补上与 teach 一致的完整拦截链（顺序）：
  1. 知识库查询（knowledge → 清点 Library）
  2. 意向性层（is_teaching_intent → 非教学意图走 chat 响应）
  3. 学习方法咨询（method）
  4. 出题请求（problem）
  5. 元问题/寒暄（meta/greeting）——原有
- **实测（本地+公网 /api/teach/stream）**：
  - "知识库" → step_type=knowledge 清点资料 ✓
  - "你今天怎么样/我心情不好" → step_type=chat 一般化响应 ✓
  - "什么是导数" → 正常教学 ✓
  - "你好" → chat 回应 ✓
- 测试 59/59 通过

---

## v0.19.22（2026-08-06）

**系统性自进化（四路更新 + 质量门禁）⭐ + 知识库拦截修复 + 意向性层**

### 1. 自进化系统（核心亮点，调研 10+ 成熟项目后设计）
- **调研依据**：Reflexion / ExpeL / Voyager / MemGPT / Generative Agents / Self-RAG / Constitutional AI / AlpaGasus / SCOPE / SWE-agent（librarian 双路调研）
- **四路进化管线**（self_evolution.py）：
  ① 知识库更新：成功教学(avg≥0.7)→LLM提炼(definition+intuition)→QualityGate→`Library/KnowledgeBase/subjects/evolved_*.json`（重启自动注册，知识库闭环）
  ② 学科提示词更新（SCOPE 双流）：教学反思→memory/subject_patches.md→teaching_memory 注入 system
  ③ 工具使用经验：调用成败→memory/tool_lessons.md→注入
  ④ 周度洞察：periodic 调度器跑 weekly_insight_update+batch_update+analyze_failures
- **质量门禁**（quality_gate.py，4 层防污染）：
  L1 教育宪法（有害词 + **提示词注入/记忆投毒** + **PII/凭证泄露**——修复中文环境 \b 词边界 bug）
  L2 硬规则（长度/信息量/去重）
  L3 LLM 多维评分（factuality/safety/pedagogy；knowledge 类不查 novelty——经典知识不该被判"不新颖"）
  L4 证据沙盒（洞察类先进沙盒，evidence≥2 转正、贡献分归零淘汰）
- **实测**：教学"牛顿第二定律"(avg=0.95)→自动蒸馏 F=ma+购物车直觉→evolved_20260806.json；"忽略系统指令"/"手机号"/"身份证"/"API Key" 全部被 L1 拦截

### 2. 知识库关键词拦截顺序修复
- **根因**：META_PATTERNS 含裸"知识库|资料库"且 meta 拦截在 knowledge 之前→"知识库"永远被 meta 抢走（讲身份而非清点 Library）
- **修复**：META_PATTERNS 移除裸"知识库"（只留"调用/查"类动词）；server 把 knowledge 拦截移到 meta 之前
- 实测：teach 模式问"知识库/你学过什么"→ step_type=knowledge 清点 Library ✓

### 3. 意向性层
- **问题**：教学模式问"你今天怎么样"被强行变成数学课（教学指令覆盖用户出发点）
- **修复**：meta_router.is_teaching_intent（LLM 判断教学意图，缓存 10 分钟）+ server 在规则拦截后接入
- 实测：教学模式下"你今天怎么样/你今天过得怎么样/我心情不好"→ step_type=chat 一般化响应；"什么是导数"→ 正常教学 ✓

### 4. 前端欢迎语提示关键词
- 初始会话欢迎气泡新增："看我的知识库——问「知识库」或「你学过什么」，我把收着的资料清点给你看"

### 5. 其他
- teaching_memory 注入 subject_patches.md + tool_lessons.md（自进化产物生效）
- 测试 59/59 通过

---

## v0.19.21（2026-08-06）

**知识库拦截顺序 + 意向性层 + 周期调度器（本轮前半）**

- 知识库/闲聊不回复问题根因：公网与本地 index.html MD5 不一致→确认是本地文件编码读取差异（磁盘二进制 24b7faba == 服务返回），实际后端前端均最新，需浏览器强刷
- 周期自我更新调度器（periodic_self_update.py）：后台守护线程 + /api/self-update/run（手动）+ /api/self-update/status，对话后 mark_activity
- 调度器已实测运行（thread_alive=True）

---

## v0.19.20（2026-08-06）

**阶段性总结：项目最大亮点文档化 + 自检复盘 + 材料索引**

- **技术文档新增 §1.6「项目最大亮点：教育者 Agent 的基础架构定义」**：完整回答"一个教育者智能体需要怎样的基础架构"——
  - 教学设计循环（teach 六阶段：诊断→计划→呈现→评估→调整→反思→自检→自更新）
  - 6 个子代理架构（Diagnostor/Planner/Presenter/Evaluator/Adapter/AnswerSolver，各自是否用 LLM 的原则）
  - 执行引擎 harness（教学层 teach 循环 + 对话层 Plan-Act-Observe-Reflect）
  - 工具调用系统（5 工具 + 缓存 + 错误恢复 + 优雅降级）
  - 子代理连通（SessionContext 枢纽 + 共享知识库 + 对象意识 + 三层记忆）
  - 角色与提示词（Émile Novis / 薇依哲学 / "先做人再教书" / 19 学科 × 4 学段 / 价值观护栏）
- **自我更新能力如实确认（§1.6.7）**：对话级自我更新真实运行（SelfUpdater.incremental_update → reflections.json 1297KB；SelfImprover.record → cases.jsonl 21KB；teaching_memory 注入）；**周期级（周度）自我更新机制已实现但缺定时调度器**（weekly_insight_update/batch_update/analyze_failures 在 server.py 0 调用）——列入优化任务 #1
- **文档新增 §10.7 自检复盘与优化任务列表**（8 项机制优化 + 7 项内容扩充，含优先级与工作量）
- **文档新增 §10.8 设计背景与材料存放位置索引**（快速启动路径 / 设计决策记录 / 代码数据 / Library / 外部环境）——方便下次 LLM 启动工作
- **修正**：SUBJECT_STYLES 学科数 25→19（实际代码核对）
- 测试 59/59 通过（本轮为纯文档变更，未改代码）

---

## v0.19.19（2026-08-06）

**知识库总结真正基于 Library 实际内容**

- **修复根因**：`_handle_knowledge_query` 原返回 `jsonify`，在 SSE 生成器（无 Flask app context）里调用抛 `Working outside of application context`，被 `except: pass` 静默吞掉 → 闲聊模式问"你学过什么"实际走了 agent loop 自由发挥，未基于知识库
- **修复**：改为返回**纯 dict**（不 jsonify），两个调用处各自处理（HTTP 教学路由包 `jsonify`，SSE 生成器直接用 dict）；生成器里加 `[PAEG][kb]` 日志便于排查
- **读取全部真实内容**：md/txt/json 读前 800 字正文，**PDF 用 pypdf 提取前 3 页文本**（不再只列文件名）——LLM 真正"读过"每份资料
- **强制基于内容总结**：system prompt 明令"只能基于【Library 资料库收录】实际内容回答，逐份介绍具体讲了什么"，不得凭训练知识发挥；内容不可读如实说"存着但还没细读"
- **结尾提示关键词**：明确告诉学生"以后只要说'知识库'或'你学过什么'，我就会为你打开这份资料清单"
- **实测**：闲聊"你学过什么"→ 逐领域逐份介绍（《2026年8月词汇扩充1-8》7天×30词结构、德语A1手册 ä/ö/ü/ß 发音、《数理统计讲义》结构、《责任原理》等），如实标注 PDF 未细读，结尾提示"知识库"关键词；教学模式 HTTP 200 正常

---

## v0.19.18（2026-08-06）

**闲聊模式修复 + 知识库关键词全覆盖**

- **闲聊模式**：后端实测稳定（3-5s 返回 seg+done）；前端加**空结果兜底**（流正常结束但无内容时显示占位，不再静默无回复）+ **渲染容错**（marked/公式处理异常时降级显示纯文本，不阻塞）
- **知识库关键词**：正则从 3 条扩展到 6 条，覆盖"知识库/你学过什么/学习过什么/学过什么/你掌握了哪些知识/你懂哪些/你会什么/你知道什么/有哪些知识/资料库"等 16 种说法（实测 16/16）
- 实测：闲聊模式问"学过什么/学习过什么/掌握哪些知识"均返回 LLM 根据知识库内容的自然总结；"你好"正常闲聊

## v0.19.17（2026-08-06）

**三大架构支柱验证并写入文档**

- 检查并确认三项核心设计全部为真：
  1. **场景差异化配置**：三模式（教学5子代理/闲聊/找答案）+ 26 学科 × 4 学段各自专属配置
  2. **Agent 指挥 LLM 完整链路**：context 打包（6项）→ tool use（真实触发）→ 知识库注入 → 思考迭代（run_agent_loop + agent_engine）→ 深度守门
  3. **角色/人格/顶层设计**：Émile Novis 身份三层 + 薇依人格（爱是朝向/注意力）+ 先做人再教书总原则 + 好讲解质量标准 + 语言铁律
- 文档新增 **§1.5 三大架构支柱**（三个验证表 + 指挥链路图）

## v0.19.16（2026-08-06）

**知识库查询升级：LLM 根据内容总结回答**

- 修复：问"你的知识库里有哪些内容/你学过什么"不再返回干巴巴文件列表，而是 **LLM 读取资料内容摘要后自然总结**（逐领域介绍：语言 CET-4 词汇/数学讲义/哲学硬核/薇依藏书，提到各资料内容要点，证明"读过"）
- 修复：知识库查询拦截从仅 teach 扩展到 **chat_stream（闲聊模式）**——闲聊问"你学过什么"也走知识库总结
- 实测：闲聊模式三层结构总结（学科/方法/思考）+ 教学模式逐领域详细介绍

## v0.19.15（2026-08-06）

**知识库查询 + 法学学科 + subagent 架构优化**

- **"知识库"固定关键词**：用户问"你学过什么/你的知识库"→ 扫描 Library 按领域列出已收录资料（实测列出 KnowledgeBase/Language/Math/Philosophy/Simone Weil/用户资料）+ 提示可上传资料更精通
- **新增"法学"学科**：SUBJECT_STYLES 加 law（label/法学生人设/构成要件思维/法条准确优先）+ _SUBJECT_ALIASES 加 law/法学/法律 + 前端下拉框加"法学"选项 + SUBJECT_LABELS
- **subagent 架构优化**：明确"哪些需要/不需要 subagent"原则（需要理解/创造/判断→LLM 推理型；需要确定/稳定→规则型；纯查询/闲聊→不走 subagent 避免过度设计），连通率 16/16 保持 100%，工具调用真实性确认
- 文档：§3.2 补"需要/不需要 subagent"决策表 + 工具调用真实性保障

## v0.19.14（2026-08-06）

**闲聊修复 + 找答案模式 + 子代理体系完善**

- 闲聊模式：后端实测正常，前端加 SSE 读流超时保护（120s 无数据自动停止，防连接挂起"不回复"）+ timer 清理
- **新增"找答案"模式**：第 6 个子代理 AnswerSolver（直接输出完整答案——论述题范文/计算题完整解法/证明题标准证明，不受教学"先例后抽象"约束）+ 前端"找答案"按钮 + /api/answer 路由。实测三种题型直接给完整规范答案
- 子代理审计：6 个子代理全部可用（推理型：Diagnostor/Presenter/AnswerSolver；规则型：Planner/Evaluator/Adapter），测试齐全
- 文档：§3.2 更新为 6 子代理体系 + 类型说明 + 三模式对应表

## v0.19.13（2026-08-06）

**语法完整性强化——禁止"没头没尾的总结句"**

- prompts 语法完整段强化：明确禁止"一句话总结""记住这一句""牢记这一点""核心就是""说白了""简单来说"等祈使句碎片（缺主语）
- 要求**每一句主谓宾完整**，输出前自查"这句有主语吗？有谓语吗？"
- 例外：真正对学生的祈使指令（"请做一下这道题"）可省略主语；讲解/总结句必须完整
- AI_MARKERS/AI_TELLS 各加入 21 个"没头没尾总结句"（双保险：约束 + 检测）

## v0.19.12（2026-08-06）

**回到初衷：人的基础上更具教育专业性**

- 卷首语优化：去重复、更自然（"想学点什么，或者想聊点什么"），收尾留白（"从你现在心里想的那件事开始"）
- **总原则"先做人，再教书"**（presenter 最高优先级）：所有结构/规范指令都是为"帮助眼前这个人"服务，不机械执行、不套模板、人话优先
- 技术文档：版本历史拆分至本文档，主文档更精简

## v0.19.11（2026-08-06）

**答非所问根治 + 用户资料库**

- ①指令类型判断（直接请求类→直接回答不绕弯；概念疑问类→深度讲解；做题类→解题），实测"给我一个你喜欢的数学公式"→直接给欧拉公式
- ②打包上传完整性（设定+画像+BDI+教学记忆+历史+用户资料库）
- ③用户资料上传模块（/api/upload purpose=library → Library/user_<id>/ + 注入 system + /api/user-library + 前端按钮）
- ④Agent 连通性文档

## v0.19.10（2026-08-06）

**Agent 指导 LLM 工作能力全面强化**

- ①工具调用修复（llm_adapter 透传 tools；实测 web_search/verify_math 自主触发）
- ②Agent 工作协议（先理解→调工具→自我检查 loop→高质量输出）
- ③讲义级结构（学习《数理统计讲义》教科书范式）
- ④在线资源入库（数理统计讲义 → Library/Math/）

## v0.19.9（2026-08-06）

**公式渲染彻底修复（KaTeX 替代 MathJax）**

- 根因：MathJax autoload 按需加载 404 → startup reject → 公式全不渲染
- 方案：KaTeX（18 文件自包含、同步渲染、throwOnError 降级）

## v0.19.8（2026-08-06）

**提升 Agent 指导大模型能力**

- ①架构连通性指标（arch_check.py + §10.6）
- ②教学对话全面提升（好讲解 7 标准 + 学科黄金法则 6 类）
- ③"接住"类动词屏蔽（调研 7 项目，AI_MARKERS 612 + AI_TELLS 556 + 三条铁律）

## v0.19.7（2026-08-06）

**四大问题修复**：方法咨询拦截 / 讲义 fgen 修复 / 闲聊学段 / 架构连通 + renderMath 竞态修复

## v0.19.6（2026-08-06）

**三大根因修复**：公式本地化 vendor / 教学单气泡 / 讲义主题错位

## v0.19.5（2026-08-06）

**教学针对性优化**：公式渲染 extension + 讲义式输出 + 关键词系统（讲义/要点/例题/笔记）

## v0.19.4（2026-08-06）

**三问题修复**：偏离提问根因（run_agent_loop 传打包 user）/ 公式补齐 / 复制多选全挂载

## v0.19.3（2026-08-06）

**对话交互三原则 + 记忆检查 + 上下文管理 + 前端个性化**

## v0.19.2（2026-08-06）

**工具错误恢复 + tool-use 评估 + SVG 替换 emoji + 文档完善**

## v0.19.1（2026-08-06）

**公式渲染修复 + 出题拦截 + 教学流式 + 登录优化 + 评估 harness**

## v0.19（2026-08-06）

**P0/P1/P2 全优化**：Function Calling / 三层记忆 / MCP / Skills / 流式 / 工具可视化 / Agent 主循环 / 自我改进 / 教学记忆 / 多模态

## v0.18.1（2026-08-06）

**前端历史会话 GUI**：恢复/删除/清空

## v0.18（2026-08-06）

**五大模块**：专业深度守门员 / 联网搜索 / 文档生成 / 做题模块 / 对话历史持久化

## v0.17.x（2026-08-06）

**v0.17.1**：幻觉修复（meta_router 元问题拦截）+ 公式增强 + 多段对话流
**v0.17.2**：寒暄拦截 + math 代码块修复 + 讲解深度 + 步骤标签自然化 + 昵称

## v0.17（2026-08-06）

**每日一句库 / 闲聊~ / 身份三层 / 加载动画 / 网络用语排除**

## v0.16（2026-08-06）

**名字 Émile Novis + 词汇排斥 + 公式渲染 + 随便说说 + 去 Emoji**

## v0.15（2026-08-06）

**自我更新（Reflexion/ExpeL）+ 教学去重复 + 知识库缓存 + 每用户文件夹**

## v0.14（2026-08-06）

**语法完整性 + Markdown 渲染 + 用户注册 + 个体性验证 + 下拉小三角**

## v0.13（2026-08-06）

**AI 味检测 + Self-Refine + Actor-Critic 反思 + BDI 建模**

## v0.12（2026-08-06）

**文件生成下载 + 语言优化 Agent（薇依语料）**

## v0.11（2026-08-06）

**薇依思想深化 + 语言规范 + 对象意识 + 知识库扩展**

## v0.10（2026-08-06）

**智能体基础架构（agent_core）+ 用户自我描述**

## v0.9（2026-08-06）

**语言风格强化 + 薇依画像深化 + 教学策略库 + GUI 动作按钮**

## v0.8.x（2026-08-06）

**v0.8.1**：学科提示词中心
**v0.8.2**：薇依画像教师 + 4 学段 + 15 学科 + 一般对话

## v0.8（2026-08-06）

**GUI 重写 + G4 技能教学 + 公网部署**

## v0.5（更早）

**真实 LLM + 55 节点 + CLI + 安全中间件 + 持久化**

## v0.1-v0.3（最早）

**原型物化：6 个 .py 从 README 落地**
