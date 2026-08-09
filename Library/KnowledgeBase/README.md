# PAEG 知识库扩展指南

> 目的：告诉未来的你（或任何维护者）如何向 PAEG 加入更多知识，
> 让模型获得更多现实事实的支撑。

## 目录结构

```
Library/
├── KnowledgeBase/          ← 从这里加知识（推荐）
│   ├── subjects/           ← 学科知识节点（JSON）
│   │   └── *.json          ← 每个文件是一组节点
│   └── facts/              ← 事实性资料（Markdown）
│       └── *.md            ← 每个文件是一个主题的事实资料
├── Language/               ← 词汇/语法（语言学习）
├── Math/                   ← 数学资料
├── Philosophy/             ← 哲学文本
└── Simone Weil/            ← 薇依原文
```

## 如何添加知识

### 方式一：学科知识节点（结构化）

在 `Library/KnowledgeBase/subjects/` 下新建 JSON 文件，格式与 `knowledge_base.py` 的节点一致：

```json
{
  "physics.thermo.entropy": {
    "id": "physics.thermo.entropy",
    "subject": "physics",
    "topic": "thermo",
    "concept": "entropy",
    "level": "high_school",
    "difficulty": 5,
    "definition": "熵是系统混乱程度的度量…",
    "intuition": "墨水在水里散开…",
    "explanation_variants": {
      "intuitive": "…", "formal": "S = k·ln W …"
    },
    "common_misconceptions": ["…"],
    "worldview_fit": {"1": 0.05, "2": 0.7, "3": 0.1, "4": 0.15}
  }
}
```

### 方式二：事实资料（非结构化）

在 `Library/KnowledgeBase/facts/` 下新建 Markdown 文件，**用文件名作为主题标签**：

```markdown
# 光合作用

## 事实
- 光合作用分为光反应和暗反应…
- 光反应在类囊体薄膜上，产生氧气…

## 常见误解
- 以为光合作用只是"吸收二氧化碳放出氧气"…
```

加载后，`library_loader.KnowledgeLibrary().search_facts("光合作用")` 就能检索到。

## 如何让 PAEG 使用新知识

```python
from library_loader import KnowledgeLibrary
from knowledge_base import KnowledgeBase

kl = KnowledgeLibrary()      # 扫描 Library
kb = KnowledgeBase()
added = kl.register(kb)      # 把学科节点并入知识库
print(f'新增 {added} 个节点')

# 检索事实资料（未来可注入 prompt）
facts = kl.search_facts('光合作用')
```

## 建议

1. **先加事实资料（facts/*.md）**——见效最快，直接给 LLM 提供真实依据
2. **学科节点（subjects/*.json）**——适合需要结构化的知识（有前置、有误区）
3. **每个知识点都写"常见误解"**——这是教学最有价值的部分
4. **事实要可验证**——LLM 会基于这些内容教学，错误事实会误导学生
