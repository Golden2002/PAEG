# PAEG 前后端 API 契约 v0.2

> 时间：2026-08-05
> 目的：定义 GUI 前端 ↔ PAEG 后端的接口规范
> 协议：REST + WebSocket
> 数据格式：JSON

---

## 1. 整体架构

```
┌────────────┐         HTTP/WS              ┌──────────────┐
│  GUI 前端 │  ◀──────────────────────▶   │  PAEG 后端   │
│ (HTML/JS) │     /api/teach (POST)        │ (Python)     │
│           │     /api/profile (GET)       │              │
│           │     /api/batch (POST)        │              │
│           │     /api/stream (WebSocket)  │              │
└────────────┘                              └──────────────┘
       │                                            │
       │ 用户视角                                    │
       ▼                                            ▼
   学习者/教师/家长                            5 子代理 + 知识库
```

---

## 2. REST API 端点

### 2.1 教学会话（核心）

**POST /api/teach**

请求：
```json
{
  "learner_id": "hs_001",
  "concept": "什么是熵？",
  "subject": "physics"
}
```

响应：
```json
{
  "session_id": "abc12345",
  "diagnosis": {
    "prerequisites_status": {...},
    "ready_to_teach": true,
    "recommended_depth": "moderate"
  },
  "plan": {
    "steps": [
      {"step_id": 1, "type": "present", "topic": "...", "worldview": "rigorous_cold"},
      {"step_id": 2, "type": "present", "topic": "...", "worldview": "rigorous_cold"},
      {"step_id": 3, "type": "evaluate", "topic": "...", "worldview": "rigorous_cold"}
    ],
    "estimated_total_min": 13
  },
  "presentations": [
    {
      "step_id": 1,
      "content": "...",
      "worldview": "rigorous_cold",
      "tone_ratio": {"1": 0.05, "2": 0.70, "3": 0.10, "4": 0.15}
    }
  ],
  "evaluations": [
    {"step_id": 1, "score": 0.85, "sub_scores": {...}, "ready_to_advance": true}
  ],
  "adjustments": [],
  "summary": {
    "concept": "什么是熵？",
    "subject": "physics",
    "avg_score": 0.81,
    "steps_completed": 3,
    "duration_min": 6,
    "worldview_used": "rigorous_cold"
  }
}
```

### 2.2 流式教学（推荐用于 GUI）

**WebSocket /api/stream**

客户端发送：
```json
{
  "type": "teach.start",
  "learner_id": "hs_001",
  "concept": "什么是熵？",
  "subject": "physics"
}
```

服务端推送（流式）：
```json
{"type": "diagnosis", "data": {...}}
{"type": "plan", "data": {...}}
{"type": "presentation.start", "step_id": 1}
{"type": "presentation.chunk", "text": "..."}
{"type": "presentation.end", "step_id": 1}
{"type": "evaluation", "step_id": 1, "score": 0.85}
{"type": "presentation.start", "step_id": 2}
...
{"type": "summary", "data": {...}}
```

### 2.3 学习者画像

**GET /api/profile/{learner_id}**

响应：
```json
{
  "id": "hs_001",
  "nickname": "小李",
  "grade_level": "high_school",
  "age": 17,
  "cognitive_style": "visual",
  "subjects_mastery": {
    "physics": {"mastery": 0.85, "count": 3, "last_session": "2026-08-05"},
    "math": {"mastery": 0.72, "count": 2, "last_session": "2026-08-05"}
  },
  "world_view_blend": {"1": 0.20, "2": 0.35, "3": 0.35, "4": 0.10},
  "privacy": {"parent_notify_enabled": false}
}
```

### 2.4 元认知日志

**GET /api/meta-log/{learner_id}?limit=10**

响应：
```json
{
  "logs": [
    {
      "timestamp": "2026-08-05T20:50:00",
      "session_id": "abc12345",
      "concept": "什么是熵？",
      "subject": "physics",
      "reflection": "学生小李在'什么是熵？'上的平均掌握度为 0.81",
      "success": true,
      "avg_score": 0.81
    }
  ],
  "total": 7
}
```

### 2.5 批处理

**POST /api/batch**

请求：
```json
{
  "learner_id": "hs_001"  // 可选；省略则全用户
}
```

响应：
```json
{
  "recurring_concepts": [["什么是熵？", 3], ["电车难题", 2]],
  "candidate_strategies": [...],
  "adopted_strategies": [...],
  "total_sessions": 7,
  "rollback_required": [],
  "version_log_size": 7
}
```

### 2.6 知识库浏览

**GET /api/knowledge/{concept_id}**

响应：节点 JSON（subject_node / humanity_node）

### 2.7 教师仪表盘

**GET /api/teacher/class/{class_id}**

响应：
```json
{
  "class_id": "高二(3)班",
  "students": [
    {"learner_id": "hs_001", "nickname": "小李", "overall_mastery": 0.78, "sessions_count": 12},
    ...
  ],
  "intervention_suggestions": [
    {"learner_id": "hs_005", "subject": "math", "suggestion": "立体几何掌握度 0.4，建议加强"}
  ]
}
```

### 2.8 家长简化报告

**GET /api/parent/{learner_id}**

响应：
```json
{
  "summary": "小李这周学了 5 个新概念，3 个掌握好",
  "emotional_state": "稳定，无明显异常",
  "recommendations": ["建议家长鼓励他多看科普书"]
}
```

---

## 3. 数据 Schema

### 3.1 LearnerProfile

```typescript
interface LearnerProfile {
  id: string;
  nickname: string;
  grade_level: 'high_school' | 'undergraduate' | 'graduate_exam' | 'adult';
  age: number;
  cognitive_style: 'visual' | 'auditory' | 'reading' | 'kinesthetic';
  target_exam?: string;        // 考研目标
  specialty_target?: string;    // 考研目标院校/专业
  subjects_mastery: Record<string, {
    mastery: number;           // 0-1
    count: number;
    last_session?: string;     // ISO timestamp
  }>;
  world_view_blend: Record<string, number>;  // {"1":0.20,"2":0.35,...}
  privacy: {
    parent_notify_enabled: boolean;
    data_retention: 'indefinite' | '30days' | '1year';
  };
}
```

### 3.2 SubjectNode

```typescript
interface SubjectNode {
  id: string;
  subject: string;
  topic: string;
  concept: string;
  level: 'middle_school' | 'high_school' | 'undergraduate' | 'graduate_exam';
  difficulty: number;          // 1-10
  bloom_level: 'remember' | 'understand' | 'apply' | 'analyze' | 'evaluate' | 'create';
  prerequisites: string[];
  leads_to: string[];
  definition: string;
  intuition?: string;
  formal_definition?: string;
  examples: string[];
  common_misconceptions: string[];
  teaching_strategies: string[];
  worldview_fit: Record<string, number>;  // {"1":0.05,"2":0.70,...}
  exam_module?: string;        // 考研模块
  exam_tips?: string;
  references: string[];
}
```

### 3.3 HumanityNode

```typescript
interface HumanityNode {
  id: string;
  dimension: 'aesthetics' | 'morality' | 'critical_thinking' | 'life_phenomenology';
  core_question: string;
  tradition_perspectives: Record<string, string>;  // {"kant": "...", "confucian": "..."}
  teaching_modes: string[];
  worldview_fit: Record<string, number>;
  difficulty: number;
  bloom_level: string;
  age_range: [number, number];
}
```

### 3.4 TeachingPlan

```typescript
interface TeachingPlan {
  steps: Array<{
    step_id: number;
    type: 'present' | 'practice' | 'evaluate' | 'reflect';
    topic: string;
    duration_min: number;
    worldview: 'rigorous_cold' | 'contemplative' | 'warm_caring' | 'pragmatic' | 'balanced';
    tools_to_use: string[];
    expected_outcome: string;
  }>;
  estimated_total_min: number;
  tone: string;
}
```

### 3.5 Evaluation

```typescript
interface Evaluation {
  score: number;               // 0-1
  sub_scores: {
    accuracy: number;
    completeness: number;
    depth: number;
  };
  misconceptions_detected: string[];
  gaps_remaining: string[];
  ready_to_advance: boolean;
  emotion_signal: 'engaged' | 'confused' | 'frustrated' | 'bored' | 'received';
}
```

---

## 4. 前端组件 → API 端点映射

| GUI 组件 | 调用 API | 用途 |
|---|---|---|
| 主对话面板 | POST /api/teach 或 WS /api/stream | 教学对话 |
| 学习者画像面板 | GET /api/profile/{id} | 画像可视化 |
| 评估条 | 嵌入在 teach 响应中 | 显示每步评估 |
| 元认知日志查看器 | GET /api/meta-log/{id} | 透明化更新历史 |
| 知识图谱浏览器 | GET /api/knowledge/{id} + /api/knowledge/search | 浏览知识库 |
| 世界观切换指示器 | 嵌入在 teach 响应中 | 显示主导世界观 |
| 教师仪表盘 | GET /api/teacher/class/{id} | 班级统计 |
| 家长简化报告 | GET /api/parent/{id} | 简化进度 |
| 批处理触发器 | POST /api/batch | 周批处理 |

---

## 5. 错误码

| HTTP | 含义 |
|---|---|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 权限不足（如家长看其他学生） |
| 404 | 学习者/会话/节点不存在 |
| 429 | 速率限制 |
| 500 | 服务器错误 |
| 503 | 服务暂时不可用（如 LLM API 失败） |

---

## 6. v0.2 简化版说明

当前 v0.2 GUI 为**纯前端原型**（`09_GUI前端/index.html`），用 JS 模拟后端 API。**与真实后端的接入路径**：

1. 实现 Python 后端（Flask/FastAPI）
2. 把 `09_GUI前端/index.html` 中的 `simulateTeach()` 替换为 `fetch('/api/teach', ...)`
3. 流式推送部分用 WebSocket（推荐）或 SSE
4. 知识图谱可视化：用 Cytoscape.js 替换当前的简化列表（按调研推荐）

---

## 7. 未来扩展 API

- `POST /api/self-update/rollback/{version}` - 回滚到指定版本
- `GET /api/health` - 健康检查
- `POST /api/safety-check` - 安全审查（政治/医疗/法律）
- `GET /api/constitution` - 获取 PAEG 的"宪法"（价值观）

---

**API 契约 v0.2 已定义。前端原型可独立运行；后端实现后可立即联通。**
