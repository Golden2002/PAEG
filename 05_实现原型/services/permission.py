# -*- coding: utf-8 -*-
"""services/permission.py —— §3.37 #18 ⭐ Permission Presets 双开关服务（v1.1.1）

Harness 模式（packages/interaction/permission-presets，commit 47f9438）：
- 预设 = sandbox（执行域）+ approval（审批策略）命名组合——**一个选择器管两个开关**
- 三个 knob 事件：permission/preset（用户意图，log-only）/ sandbox/mode / approval/policy
- custom 是**衍生状态**（knob 组合偏离所有预设时显示），不可作切换目标
- 切换写 permission/preset 事件 → 可回放（重放状态 = 实时状态）

与 tool_registry.PERMISSION_PRESETS（4 档权限档）兼容：
- standard/exam/read_only/full 预设映射到 (sandbox, approval) 双 knob
- exam 模式锁定写工具逻辑由 tool_registry._WRITE_TOOLS 保持（本服务提供语义层）
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────
# 预设表：预设名 → (sandbox, approval) 双开关
# ─────────────────────────────────────
_PRESETS: Dict[str, dict] = {
    "read_only": {"desc": "只读：仅检索/查询类工具，禁止任何写操作",
                  "sandbox": "read-only", "approval": "never"},
    "standard": {"desc": "标准：教学默认（读 + 联网 + 文档生成）",
                 "sandbox": "workspace-write", "approval": "ask"},
    "exam": {"desc": "考试模式：锁定写工具（禁讲义/PPT/视频/动画生成）",
             "sandbox": "read-only", "approval": "never"},
    "full": {"desc": "全量：所有工具开放",
             "sandbox": "danger-full-access", "approval": "never"},
}

# knob 合法取值（约束 setter 输入）
_VALID_SANDBOX = {"read-only", "workspace-write", "danger-full-access"}
_VALID_APPROVAL = {"ask", "never", "manual_confirm"}


class PermissionService:
    """双开关权限服务：preset 命名组合 + knob 事件记录 + custom 派生 + 可回放。"""

    def __init__(self):
        self._lock = threading.RLock()
        # session → {"events": [ {type, time, data}, ... ]}（append-only 事件日志）
        self._sessions: Dict[str, dict] = {}

    # ─── 内部 ───
    def _events(self, session: str) -> List[dict]:
        return self._sessions.setdefault(str(session), {"events": []})["events"]

    def _append(self, session: str, etype: str, data: dict) -> None:
        self._events(session).append({
            "type": etype, "time": int(time.time() * 1000), "data": data,
        })

    # ─── 查询 ───
    def resolve(self, preset: str) -> Optional[dict]:
        """预设 → (sandbox, approval) 双开关（不存在的预设返回 None）。"""
        p = _PRESETS.get(preset)
        if not p:
            return None
        return {"sandbox": p["sandbox"], "approval": p["approval"]}

    def list_presets(self) -> List[str]:
        return list(_PRESETS.keys())

    # ─── 事件记录（log-only，可回放） ───
    def get_events(self, session: str) -> List[dict]:
        """返回该会话的权限事件日志（append-only）。"""
        with self._lock:
            return [dict(e) for e in self._events(session)]

    # ─── 双开关 setter ───
    def set_sandbox(self, session: str, mode: str) -> bool:
        """设置 sandbox/mode knob（执行域：read-only / workspace-write / danger-full-access）。"""
        if mode not in _VALID_SANDBOX:
            return False
        with self._lock:
            self._append(session, "sandbox/mode", {"mode": mode})
        return True

    def set_approval(self, session: str, policy: str) -> bool:
        """设置 approval/policy knob（审批策略：ask / never / manual_confirm）。"""
        if policy not in _VALID_APPROVAL:
            return False
        with self._lock:
            self._append(session, "approval/policy", {"policy": policy})
        return True

    # ─── 预设应用（一个选择器管两个开关 + 记意图事件） ───
    def apply(self, preset: str, session: str = "_global") -> bool:
        """应用预设：写 permission/preset 意图事件 + 设置两个 knob。

        custom 是衍生状态，不可作目标 → ValueError。
        """
        if preset == "custom":
            raise ValueError("custom 是衍生状态，不能作为切换目标")
        spec = self.resolve(preset)
        if not spec:
            return False
        with self._lock:
            self._append(session, "permission/preset", {"preset": preset})
            self._append(session, "sandbox/mode", {"mode": spec["sandbox"]})
            self._append(session, "approval/policy", {"policy": spec["approval"]})
        return True

    # ─── 状态投影 ───
    def get_effective_knobs(self, session: str) -> dict:
        """折叠事件日志 → 当前 (sandbox, approval) 生效值。"""
        with self._lock:
            events = self._events(session)
        sandbox, approval = "workspace-write", "ask"  # 默认 standard 组合
        for e in events:
            if e["type"] == "sandbox/mode":
                sandbox = e["data"].get("mode", sandbox)
            elif e["type"] == "approval/policy":
                approval = e["data"].get("policy", approval)
        return {"sandbox": sandbox, "approval": approval}

    def current_preset(self, session: str) -> str:
        """当前预设名：knob 组合匹配某预设 → 该预设名；否则 → custom（衍生）。"""
        knobs = self.get_effective_knobs(session)
        for name, p in _PRESETS.items():
            if p["sandbox"] == knobs["sandbox"] and p["approval"] == knobs["approval"]:
                return name
        return "custom"

    def replay(self, session: str, events: List[dict]) -> dict:
        """回放事件日志 → 最终 knobs（与 get_effective_knobs 结果一致）。"""
        sandbox, approval = "workspace-write", "ask"
        for e in events:
            if e["type"] == "sandbox/mode":
                sandbox = e["data"].get("mode", sandbox)
            elif e["type"] == "approval/policy":
                approval = e["data"].get("policy", approval)
        return {"sandbox": sandbox, "approval": approval}

    # ─── 与 tool_registry 同步（exam 模式一致性） ───
    def sync_to_registry(self, session: str = "_global") -> None:
        """把当前生效预设同步到 tool_registry（exam 锁定写工具）。"""
        preset = self.current_preset(session)
        try:
            from tool_registry import set_permission_preset
            set_permission_preset(preset)
        except Exception:
            pass


# ─── 全局单例 ───
_service: Optional[PermissionService] = None
_service_lock = threading.Lock()


def get_permission_service() -> PermissionService:
    global _service
    with _service_lock:
        if _service is None:
            _service = PermissionService()
        return _service


__all__ = ["PermissionService", "get_permission_service"]
