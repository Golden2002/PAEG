# PAEG × Manim 接入需求表（v6.1 规划）

> 版本：2026-08-12 | 依据：ManimCE v0.21.0 调研 + Oracle 架构咨询 + LLM→Manim 生态案例
> 定位：Manim 作为视频生成的**上游可视化工具**——LLM 生成数学动画代码 → 渲染 → 与讲稿/配音合并

---

## 一、模块定位与边界

```
用户提问（数学概念）
  → 对话路由：数学/几何类 + 动画收益高 → 触发 Manim
  → LLM 生成 Manim Scene 代码（Python）
  → 独立 worker 沙箱渲染（Docker 隔离）
  → 输出 mp4 → video_service 合并讲稿/配音 → 教学视频
```

**核心原则**：
1. **独立模块**（manim_service.py），**不影响**现有 video_service/对话功能
2. **受控异步渲染**：请求只提交任务，返回 job_id，worker 异步渲染
3. **安全隔离**：LLM 生成代码 → Docker 沙箱执行（防任意代码/资源耗尽）
4. **渐进降级**：Manim 失败 → 回退现有 ffmpeg 静态视频

---

## 二、需求清单

### A. 环境与依赖（P0）
| 项 | 说明 |
|---|---|
| ManimCE v0.21.0 | pip install manim（PyAV 内置 ffmpeg）|
| Docker | manimcommunity/manim:stable 镜像（含 LaTeX/中文字体）|
| 中文字体 | fonts-noto-cjk（Text 中文渲染）|
| LaTeX | MiKTeX（仅公式用，Docker 内）|

### B. 核心模块（P0）
| 模块 | 功能 |
|---|---|
| `manim_service.py` | 任务提交/查询/取消，场景 DSL 校验，产物登记 |
| `manim_worker` | 独立进程/容器，消费任务队列，沙箱渲染 |
| `POST /api/manim/generate` | 输入：题目+类型；输出：job_id + 状态 |
| `GET /api/manim/status/{job_id}` | 查询渲染状态（queued/running/succeeded/failed）|

### C. 安全（P0，Oracle 强调）
| 措施 | 说明 |
|---|---|
| Docker 隔离 | 非 root、只读根、无网络、单任务临时目录 |
| 资源限制 | CPU/内存/进程数/磁盘/时长（cgroup/容器限制）|
| 输出校验 | MIME/大小/时长/编码检查 |
| 输入控制 | 场景 DSL 校验（非法函数/超限参数拒绝）|

### D. LLM 生成（P1）
| 项 | 说明 |
|---|---|
| LLM Prompt 模板 | few-shot Manim 样例（参考 Manim Skills 仓库）|
| Self-Healing | 渲染失败 → 归一化错误 → LLM 修复 → 重试（最多 2 次）|
| 输出限制 | 时长 ≤60s，720p30，单场景 |

### E. 与现有模块连通（用户要求）
| 连通 | 说明 |
|---|---|
| video_service.py | Manim 产物作为 visual_asset 输入，合并讲稿/配音 |
| 知识库 | 数学概念资料注入 LLM（公式/变量域有来源）|
| PPT 生成 | 抽取 Manim 关键帧作为 PPT 配图 |
| 对话路由 | 数学+图形类问题触发 Manim（可解释"将生成约2分钟动画"）|

---

## 三、注意事项（风险与缓解）

| 风险 | 严重度 | 缓解 |
|---|---|---|
| 任意 Python 执行 | 极高 | Docker 沙箱 + DSL 优先（首期仅 5 类模板）|
| CPU/内存/磁盘耗尽 | 极高 | 容器限制 + 超时 + 输出大小限制 |
| 原视频链路阻塞 | 高 | 独立 worker + 异步 + feature flag |
| 数学内容错误 | 高 | 知识库 grounding + 公式校验 |
| 音画不同步 | 高 | 统一时间轴 + 实际音频时长校正 |
| 渲染慢 | 中高 | 异步 + 缓存（内容 hash）+ 预览档 |
| LLM 代码错误率高 | 中高 | Self-Healing（2 次重试覆盖 90%）|

---

## 四、首期 POC（5 类模板验证）

| 模板 | 数学题示例 |
|---|---|
| 函数曲线 | 二次函数 y=x² 图像 |
| 坐标轴/点 | 坐标系+点定位 |
| 导数切线 | 导数的几何意义（切线斜率）|
| 面积/积分 | 圆面积/定积分 |
| 简单变换 | 向量加法/几何变换 |

统一 720p30、短时长、单场景 MP4——先验证教育价值 + 渲染成本 + 用户接受度。

---

## 五、明确不做（首期）
- 任意高级 Manim 代码（仅授权场景开放代码模式）
- 实时交互预览
- GPU/多 worker 优化
- 逐句精确音画同步（先做整段动画作主画面）


---

## 六、调研案例补充（2026-08-12 第二轮调研）

### 6.1 权威参考（LLM→Manim 生态）
| 项目 | 亮点 | PAEG 借鉴 |
|---|---|---|
| TheoremExplainAgent（ACL 2025）| Planner→Coding 两阶段 + 5 次重试（93.8%）| 两阶段架构 + RAG 设计 |
| LLM2Manim（2026-04）| 教学法引导（segmentation/signaling/dual coding）+ HITL | 教育场景必须教师审核 |
| ManimAgent（RITL）| 错误日志最后 10 行反馈 → 90%+ 成功率 | 自纠错循环 |
| manimator（生产级）| BullMQ + Docker + S3 + DeepSeek-V3 | 生产架构 + 性价比 LLM |

### 6.2 四层安全防护（必做）
```
Layer 1: AST 静态校验（拒绝 os/sys/subprocess/eval/open；验证 Scene+construct）
Layer 2: subprocess.run（shell=False + timeout + cwd 隔离）
Layer 3: Docker 沙箱（--memory=2g --cpus=2 --network=none --pids-limit=100）
Layer 4: 全局并发 Semaphore(N-1) + 临时目录清理
```
⚠️ 历史漏洞：ManimCE extract_scene.py 曾用 exec()（HIGH severity）——任何信任代码路径必须沙箱。

### 6.3 错误恢复策略
```
Layer A 预防：RAG 注入 Manim 文档 + few-shot + 低 temperature
Layer B 检测：AST 校验 + qual-manim 静态分析
Layer C 重试：N=3~5 次，反馈错误日志最后 10 行（RITL）
Layer D 降级：简化场景 → 静态图（matplotlib）→ 标记人工审核
```

### 6.4 关键设计决策
1. **HITL**：AI 生成 + 教师审核（subject-matter/teaching/engineering 三关）
2. **DSL 优先**：首期 5 类模板（Oracle 建议），代码模式 P2
3. **DeepSeek-V3** 默认 LLM（性价比最优）
4. **缓存**：partial movie cache 省 50%+ 渲染时间
5. **Build manifest**：模型/prompt/Manim 版本/seed 必录（可复现）
6. **双指标评估**：code 指标 + 视觉质量（相关性弱，必须分开）
