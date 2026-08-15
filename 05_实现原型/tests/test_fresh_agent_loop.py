# -*- coding: utf-8 -*-
"""test_fresh_agent_loop.py — #23 Fresh-Agent Loop 对照验证测试（Harness 30 项 P2）

覆盖：RALPH 循环已具备 dsh tool-ralph 语义——每轮 fresh child（executor 注入）、
共享进度（history/snapshot）、结构化 handoff（RoundOutput/LoopResult.promise）。
dsh Harness 借鉴（tool-ralph，commit 47f9438）：每轮 fresh child + 共享进度 + 结构化 handoff。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_ralph_loop_contracts_exist():
    """RALPH 循环数据契约齐全（Verdict/ImprovementTask/RoundOutput/LoopResult）。"""
    from ralph.contracts import Verdict, ImprovementTask, RoundOutput, LoopResult, Criterion
    assert Verdict.DONE.value == "DONE"
    assert Verdict.CONTINUE.value == "CONTINUE"
    assert Verdict.ABORT.value == "ABORT"
    assert Verdict.PAUSE.value == "PAUSE"
    # ImprovementTask 有 acceptance_criteria + max_rounds（共享进度语义）
    t = ImprovementTask(id="t1", source="manual", goal="改进X")
    assert t.max_rounds == 10
    assert t.all_criteria_met() is False  # 无标准时 False
    # RoundOutput 有 snapshot（状态快照，可回滚）
    r = RoundOutput(round_idx=1, snapshot={"content": "x"})
    assert r.snapshot["content"] == "x"
    # LoopResult 有 promise（结构化 handoff）
    lr = LoopResult(task_id="t1", verdict=Verdict.DONE, rounds=2)
    assert lr.promise() == "<promise>DONE</promise>"


def test_fresh_child_each_round():
    """每轮 fresh child：executor 每轮被调用，prev 传入但业务可换执行器。"""
    from ralph.contracts import ImprovementTask, RoundOutput, Verdict
    from ralph.loop_controller import LoopController

    calls = []

    def fresh_executor(task, prev):
        """每轮 fresh child——记录调用次数与 prev 传递。"""
        calls.append({"round": len(calls) + 1, "prev_round": getattr(prev, "round_idx", None)})
        return RoundOutput(round_idx=len(calls), summary=f"round-{len(calls)}",
                           scores={"ok": 1.0})

    from ralph.task_registry import get_task_registry
    reg = get_task_registry()
    from ralph.contracts import Criterion
    task = ImprovementTask(id="fresh-test", source="manual", goal="测试",
                           acceptance_criteria=[Criterion("ok", 1.0, 1.0)], max_rounds=3)
    reg.submit(task)

    controller = LoopController(executor=fresh_executor)
    result = controller.run("fresh-test")
    assert result.verdict == Verdict.DONE
    assert len(calls) >= 1  # 至少一轮 fresh child
    assert calls[0]["round"] == 1


def test_shared_progress_history():
    """共享进度：history 累积各轮产出，prev 传给下一轮。"""
    from ralph.contracts import Criterion, ImprovementTask, RoundOutput, Verdict
    from ralph.loop_controller import LoopController
    from ralph.task_registry import get_task_registry

    prev_seen = []

    def executor(task, prev):
        prev_seen.append(getattr(prev, "round_idx", None))
        return RoundOutput(round_idx=len(prev_seen), summary=f"r{len(prev_seen)}",
                           scores={"progress": float(len(prev_seen))})

    reg = get_task_registry()
    # 用 CONTINUE 驱动多轮——标准永远不满足
    task = ImprovementTask(id="prog-test", source="manual", goal="连续改进",
                           acceptance_criteria=[Criterion("progress", 99.0, 0.0)],
                           max_rounds=3)
    reg.submit(task)
    controller = LoopController(executor=executor)
    result = controller.run("prog-test")
    # 3 轮上限触发 ABORT（防呆）
    assert result.verdict == Verdict.ABORT
    assert result.rounds == 3
    # 共享进度：每轮 prev 传的是上一轮（第 1 轮 prev=None，后续 prev=上轮 idx）
    assert prev_seen[0] is None
    assert prev_seen[1] == 1  # 第 2 轮收到第 1 轮的 round_idx
    assert prev_seen[2] == 2  # 第 3 轮收到第 2 轮的 round_idx


def test_structured_handoff():
    """结构化 handoff：RoundOutput 传递 summary/scores/snapshot 给下一轮。"""
    from ralph.contracts import Criterion, ImprovementTask, RoundOutput, Verdict
    from ralph.loop_controller import LoopController
    from ralph.task_registry import get_task_registry

    snapshots = []

    def executor(task, prev):
        if prev is not None:
            snapshots.append(prev.snapshot)
        return RoundOutput(round_idx=len(snapshots) + 1,
                           summary=f"r{len(snapshots)+1}",
                           scores={"n": float(len(snapshots) + 1)},
                           snapshot={"note": f"snap-{len(snapshots)+1}"})

    reg = get_task_registry()
    task = ImprovementTask(id="handoff-test", source="manual", goal="交接",
                           acceptance_criteria=[Criterion("n", 99.0, 0.0)], max_rounds=2)
    reg.submit(task)
    controller = LoopController(executor=executor)
    result = controller.run("handoff-test")
    assert result.verdict == Verdict.ABORT  # 2 轮上限
    # 第 2 轮收到第 1 轮的 snapshot（结构化交接）
    assert len(snapshots) == 1
    assert snapshots[0]["note"] == "snap-1"
