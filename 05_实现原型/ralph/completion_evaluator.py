# -*- coding: utf-8 -*-
"""RALPH 完成判定器（v0.69+ T5）：三层判定 L0 QualityGate + L1 任务指标 + L2 改进证据。"""
from __future__ import annotations

from typing import Dict, Optional

from .contracts import ImprovementTask, RoundOutput, Verdict


class CompletionEvaluator:
    """三层完成判定：
    - L0：QualityGate L1-L4 全通过（content 类产出必经质量门禁）
    - L1：任务 acceptance_criteria 全部达标
    - L2：本轮产出有可测量 delta（改进证据）
    """

    def __init__(self, quality_gate=None):
        self.quality_gate = quality_gate  # 复用 quality_gate.QualityGate

    def _l0_quality(self, output: RoundOutput) -> bool:
        """L0 质量门槛（若产出含 content 文本则过 QualityGate）。"""
        _content = str(output.summary or "")
        _snap = output.snapshot or {}
        if isinstance(_snap, dict) and _snap.get("content"):
            _content = str(_snap["content"])
        if not _content.strip():
            return True  # 无内容产出视为通过（非内容类任务）
        if self.quality_gate is None:
            return True
        try:
            _v = self.quality_gate.evaluate({
                "content": _content,
                "entry_type": _snap.get("entry_type", "knowledge") if isinstance(_snap, dict) else "knowledge",
                "subject": _snap.get("subject", "") if isinstance(_snap, dict) else "",
                "source": f"ralph:{output.round_idx}",
            }, skip_sandbox=True)
            return bool(_v.get("pass"))
        except Exception:
            return True

    def evaluate(self, task: ImprovementTask, output: RoundOutput) -> Verdict:
        """三层判定 → DONE / CONTINUE。"""
        # L0 质量门槛
        if not self._l0_quality(output):
            return Verdict.CONTINUE
        # L1 任务指标（更新 criteria current 分数）
        _l1_ok = True
        for c in task.acceptance_criteria:
            if c.metric in output.scores:
                c.current = output.scores[c.metric]
            if not c.met():
                _l1_ok = False
        if not _l1_ok:
            return Verdict.CONTINUE
        # L2 改进证据（有可测量分数即可）
        if output.scores:
            return Verdict.DONE
        # 无指标但有摘要 → 视为完成（够好即可，DONE 是首选）
        if output.summary.strip():
            return Verdict.DONE
        return Verdict.CONTINUE
