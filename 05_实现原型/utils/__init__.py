
# ── v0.50 ⭐ 合并 utils.py 内容（同名冲突修复）──
"""PAEG 通用工具函数层(v0.40 P1-1 server.py Phase1 拆分)。

集中托管 server.py 中"无 server 模块级全局依赖"的纯函数:
  - 路径安全解析(_safe_resolve_user_library_file)
  - 学生画像上下文构造(_build_learner_ctx_str)
  - 匿名用户 ID 生成(_anon_learner_id)
  - 学段/画像同步(_hydrate_learner)

设计原则:
  - 零模块级全局依赖——所有需要的依赖通过参数传入或函数内懒导入
  - 保留原函数名(带下划线前缀)+ 保留原 docstring——纯搬运, 不改名
  - 不引入新行为——调用方传入的请求/数据原样处理
  - 副作用: 仅 _anon_learner_id 在 cookie 读取失败时打 print(保留原行为)

注意: 依赖 server 模块级全局(SKILL_REGISTRY / paeg / USER_STORE 等)的函数
   (_inject_skill_catalog / _polish_text / _is_registered)不搬, 留在 server.py,
   因为 utils.py 设计为可被任意模块导入, 不应反向依赖 server.py 的全局状态。
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional
from pathlib import Path


# ---------------------------------------------------------------------------
# 1) 路径安全解析(v0.26 防目录穿越)
# ---------------------------------------------------------------------------
def _safe_resolve_user_library_file(learner_id: str, filename: str) -> Optional[Path]:
    """解析用户资料文件路径并做安全校验。

    安全策略:
      1. learner_id / filename 必须为非空字符串, 且不含路径分隔符或 ".."
      2. 解析后必须在 LIBRARY_DIR/usr_knowledge/<uid>/ 或 LIBRARY_DIR/user_<uid>/ 实际路径下
      3. 必须为真实文件(非目录、非符号链接逃逸)
      4. 拒绝非当前用户目录(防止 id 字段水平越权)
    """
    if not learner_id or not filename:
        return None
    # 防止 uid 本身含路径分隔符 / 相对路径元素
    if "/" in learner_id or "\\" in learner_id or ".." in learner_id:
        return None
    # 防止 file 字段含路径分隔符 / 相对路径元素
    if "/" in filename or "\\" in filename or ".." in filename:
        return None

    try:
        from lib import library_store
        # 候选根: 规范路径 + 兼容旧路径
        roots = [library_store.resolve_library_root(learner_id)] + library_store.legacy_paths(learner_id)
        for root in roots:
            try:
                candidate = (root / filename).resolve()
                real_root = root.resolve()
                # 必须真实落在某个 user 目录前缀内
                if not (str(candidate).startswith(str(real_root) + os.sep) or candidate == real_root):
                    continue
            except Exception:
                continue
            if candidate.is_file():
                return candidate
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 2) 学生画像上下文段(v0.20.3 供各端点 system 注入)
# ---------------------------------------------------------------------------
def _build_learner_ctx_str(learner) -> str:
    """构造学生画像上下文段(v0.20.3, 供各端点 system 注入)。"""
    try:
        from context_bundle import build_learner_context, inject_user_model
        # 懒推断 user_model(若已有则跳过)
        if not getattr(learner, "_user_model", None):
            inject_user_model(learner, [], getattr(learner, "self_description", ""))
        return build_learner_context(learner)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 3) 匿名用户 ID(v0.26 "一个用户一个 ID")
# ---------------------------------------------------------------------------
def _anon_learner_id(request_data: dict, request_obj=None) -> str:
    """v0.26: 匿名用户"一个用户一个 ID"——优先请求里已有 ID; 否则会话 cookie 绑定稳定 ID。

    关键: 同一用户的所有请求必须映射到同一个 ID, 否则记忆(chat_hist)会混乱。
    """
    # 1. 请求显式带 learner_id → 信任(GUI 已保证 web_/u 前缀)
    lid = request_data.get("learner_id")
    if lid and str(lid).strip():
        return str(lid).strip()
    # 2. 从 cookie 取"会话级匿名 ID"(浏览器每个用户一个 cookie, 跨请求稳定)
    try:
        if request_obj is not None:
            from flask import request as _req
            cid = _req.cookies.get("paeg_anon_id")
            if cid:
                return cid
    except Exception as _e:
        print(f"[PAEG][utils.py] _anon_learner_id 异常忽略: {_e}")
        pass
        pass
    # 3. 无 cookie 上下文 → 生成会话级 ID(本请求内稳定; 有 cookie 时后续请求复用)
    return "web_" + uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------
# 4) 学段/画像同步(v0.32 修复缓存陈旧)
# ---------------------------------------------------------------------------
def _hydrate_learner(learner, data):
    """v0.32 每次请求把请求体的学段/画像字段同步到 SESSIONS 缓存。

    历史 bug: teach_stream 等端点只在首次创建 LearnerProfile 时读 grade_level,
    之后永远用缓存旧值, 导致用户切换学段后后端仍按旧学段教学(linguistics 反复 grade_blocked)。
    这里只更新运行时字段, 不负责持久化(持久化由 profile_update 的 save_learner 负责)。
    """
    if learner is None or not isinstance(data, dict):
        return learner
    grade = data.get("grade_level")
    if grade and getattr(learner, "grade_level", None) != grade:
        try:
            learner.grade_level = grade
        except Exception as _e:
            print(f"[Server] _hydrate_learner grade_level 同步失败: {_e}")
    return learner


# ---------------------------------------------------------------------------
# 公开符号
# ---------------------------------------------------------------------------
__all__ = [
    "_safe_resolve_user_library_file",
    "_build_learner_ctx_str",
    "_anon_learner_id",
    "_hydrate_learner",
]
