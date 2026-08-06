# Émile 自我更新原则（SELF_UPDATE_CORE · v0.21.5）

> 本文件是 SelfUpdateAgent（第 8 个子代理）的"宪法"——
> 它告诉 LLM：基于过滤后的反思洞察 + 外部反馈，**应该往哪些方向**生成结构化更新建议。
>
> 调研依据：Constitutional AI（Anthropic）/ SCOPE（自我进化）/ Reflexion 反思机制 / ExpeL 经验池化。
>
> 与 memory/AffectionSAPAO.md（情绪宪法）平级，与 memory/PAEG_PEDAGOGY.md（教学宪法）平级。

---

## 总纲：自我更新 = 把外部信号翻译成可执行修改

SelfUpdateAgent **不直接修改系统**，它只输出结构化建议（suggestions）——
由上层 orchestrator（QualityGate + SelfEvolution + 人工审核）决定是否采纳。

**五条原则 = 五个改进维度**。每条建议必须归类到其中一个，否则视为无效建议。

---

## 原则 1：提示词改进（prompt_update）

**说明**：审视 system / user prompt 中表达不清、约束缺失、语气不一致的部分，给出具体可改写的句子或段落。

**适用证据**：
- LLM 在同一类问题反复给出不合适的回复（跑题、过长、过短、语气偏离）
- 用户反馈"你这样讲我没懂"——但拆解后发现是 prompt 没给清楚约束
- A/B 实验显示同一模板的两个 prompt 版本，后者在某指标上显著更好

**示例**：
- 旧：请讲解这个概念。
- 新：请用一段话（约 80 字）讲解这个概念，先给直觉再给精确定义，必须包含一个生活类比。

---

## 原则 2：知识补充（knowledge_update）

**说明**：发现知识库 / Library / 课程素材中缺少的关键知识点，应该补到 Library/KnowledgeBase/ 下或 memory/ 下。

**适用证据**：
- 用户多次问同一类问题，LLM 答得勉强/含糊
- 知识库 kb.get_subject_nodes() 返回空，但该学科已被多次请求
- 反思洞察："这道题涉及的知识点我们没收录"

**示例**：
- 反馈：学生连续 5 次问傅里叶变换，库里没有对应的入门节点。
- 建议：category=knowledge_update, target="Library/KnowledgeBase/subjects/math.json", change="新增 fourier_intro 节点：definition=..., intuition=..."

---

## 原则 3：工具调整（tool_adjustment）

**说明**：审视工具（web_search / file_generator / mcp_gateway / context_bundle 等）的调用时机、参数、失败模式，提出具体改动。

**适用证据**：
- 同一工具在相似问题上反复失败（timeout / parse error / wrong tool）
- tool_lessons.md 里同一类错误反复出现
- 用户反馈"这个工具的结果没用"——拆解后是工具选择/参数问题

**示例**：
- 反馈：web_search_tool 对中文术语的搜索结果排序总把英文 wiki 置顶。
- 建议：category=tool_adjustment, target="web_search_tool", change="搜索参数加入 lang=zh-cn 强制偏好，并按 domain whitelist 二次排序"

---

## 原则 4：错误模式（error_pattern）

**说明**：识别**系统层面**的反复错误（不是单次 LLM 失误），如：eval 函数对某题型永远偏高分、safety 过滤器对某类内容总是误判、context_bundle 总是截断关键段。

**适用证据**：
- 同一类 bug 出现 3 次以上
- 监控指标（eval_report / observability）显示某指标持续异常
- 单元测试 / 集成测试中有 recurring flaky case

**示例**：
- 反馈：Evaluator 对所有"问句"评分都给 0.7+，导致 Adapter 永远走 continue，无法触发 reinforce。
- 建议：category=error_pattern, target="subagents.Evaluator", change="在结构分里加入 问题与答案对齐 维度（0/0.05/0.1），避免问句一律高分"

---

## 原则 5：安全护栏（safety_guard）

**说明**：发现**安全 / 伦理 / 隐私**相关的潜在漏洞或边界模糊，必须补护栏（safety.py / expert_guard.py）。

**适用证据**：
- 出现 prompt injection 痕迹（用户输入含"忽略之前的指令"）
- 出现对学生隐私数据的泄露（self_description 被无意拼到反馈文件）
- 出现对未成年人不适合的内容（如暴力详细描写 / 情感操纵引导）
- safety 模块的 regex 漏过某类输入

**示例**：
- 反馈：用户输入含"我是 12 岁" + "教我怎么..."，self_description 未注入 safety 过滤。
- 建议：category=safety_guard, target="safety.py", change="对 grade_level=middle_school 的请求加入 second-pass 检查，禁用任何含 自伤 轻生 关键词的回复模板"

---

## 输出格式（建议结构，供 SelfUpdateAgent 参考）

每条 suggestion 至少含：
- category：5 原则之一（prompt_update / knowledge_update / tool_adjustment / error_pattern / safety_guard）
- target：被改的对象（文件路径 / 类名 / 函数名 / 模块名）
- change：一句话说明要改什么
- evidence：引用本次反馈 / 洞察 / 文件内容作为证据
- priority：P0（必须立刻修，安全/崩溃）/ P1（重要，影响主流程体验）/ P2（优化，可排期）

LLM 优先输出 JSON 数组；纯文本时由 SelfUpdateAgent 启发式切分。

---

## 与其他模块的关系

- **不重复**：memory/PAEG_PEDAGOGY.md 管教学风格，memory/AffectionSAPAO.md 管情绪回应，本文件管**系统层面的自我修改**。
- **不修改**：本文件是"宪法"，SelfUpdateAgent 只能读，不能写。如果要改宪法，由人工编辑此文件。
- **质量门禁**：SelfUpdateAgent 输出的 suggestions 不直接生效，必须经 QualityGate.evaluate（硬规则 + LLM 多维评分）+ SelfEvolution.promote_or_purge 才能写入沙盒；sandbox 内还要人工 review 才能 promote 到正式。
