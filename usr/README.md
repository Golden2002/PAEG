# usr/ — 用户数据视图（v0.21.4）

本目录是**用户个人数据**（身份/对话历史/自我陈述）的逻辑视图别名。

- 实际存储：`05_实现原型/users_data/<user_id>/`（profile.json + history.jsonl + notes/ + self_description.json）
- 逻辑别名：`user_store.user_data_paths(uid)` 返回统一路径
- 上传资料：`Library/usr_knowledge/<user_id>/`（用户私有知识库，回答时自动参考）
- 反馈文件：`users_data/<user_id>/feedback/`（线下用户测试反馈，SelfUpdateAgent 读取）

| 用户 | 身份/画像 | 对话历史 | 自我陈述 | 上传资料 | 反馈 |
|---|---|---|---|---|---|
| u1 小陈 | users_data/u1/profile.json | users_data/u1/history.jsonl | 同上 | Library/usr_knowledge/u1/ | users_data/u1/feedback/ |
| u8 | users_data/u8/profile.json | users_data/u8/history.jsonl | 同上 | Library/usr_knowledge/u8/ | users_data/u8/feedback/ |

> 迁移说明：v0.14 起用户数据在 `05_实现原型/users_data/`；`usr/` 是面向开发者的统一视图入口。
> 任何代码请用 `user_store.user_data_paths(uid)` 取路径，不要硬编码。
