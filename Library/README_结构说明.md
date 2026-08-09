# PAEG Library 结构（v0.26 ⭐ 学科化）

> 为每个学科建立独立子文件夹，与对应学科的教学/解题 subagent 联通。

## 目录结构
```
Library/
├── common/               # 公共资源（所有 subagent 联通）
├── users/                # 用户上传资料（按用户作用域隔离）
│   └── <learner_id>/     # 每个用户自己的资料
├── math/                 # 数学学科资源
├── physics/              # 物理学科资源
├── ...                   # 每个学科一个子文件夹
├── KnowledgeBase/        # 结构化知识节点（subjects/evolved_*.json）
└── Simone Weil/          # 薇依原著（公共哲学资源）
```

## 联通规则
- **学科子文件夹** ↔ 对应学科教学/解题 subagent（按 subject 路由）
- **common/** ↔ 所有 subagent（通用教学法/参考资料）
- **users/<learner_id>/** ↔ 仅该用户可访问（作用域隔离）
