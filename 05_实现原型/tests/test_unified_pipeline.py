# -*- coding: utf-8 -*-
"""§3.89 统一物料流水线框架测试：v2.0 gates/fix + teaching_scene + scope_refine。"""
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from material_pipeline import MaterialPipeline
from teaching_scene import TeachingScene
from manim_extensions import scope_refine, tts_mux


class FakeLLM:
    name = "test"

    def chat(self, system=None, user=None, messages=None, max_tokens=512, **kw):
        if "修复" in str(system or ""):
            return '{"ok": true, "fixed": true}'
        return "测试内容"


def _stages():
    def plan(llm, topic, subject, learner_id, **kw):
        return {"topic": topic, "subject": subject}

    def draft(llm, spec, topic, subject, learner_id, **kw):
        return f"讲义内容：{topic}"

    def implement(content, **kw):
        return {"ok": True, "content": content}

    return {"plan": plan, "draft": draft, "implement": implement}


def test_pipeline_v20_custom_gate_pass():
    """S1：自定义 gate 通过 → stages 标记 ok。"""
    def gate_ok(content, ctx):
        return True, ""

    p = MaterialPipeline("handout", _stages(), ["topic"],
                         gates=[gate_ok])
    r = p.run(FakeLLM(), "导数")
    assert r["stages"].get("gate0") == "ok"


def test_pipeline_v20_custom_gate_fail_no_fix():
    """S2：gate 失败且无 fix_strategy → 中止。"""
    def gate_fail(content, ctx):
        return False, "内容过短"

    p = MaterialPipeline("handout", _stages(), ["topic"],
                         gates=[gate_fail])
    r = p.run(FakeLLM(), "导数")
    assert r["stages"].get("gate0") == "fail"
    assert not r.get("ok")


def test_pipeline_v20_gate_fail_with_fix():
    """S3：gate 失败 + fix_strategy → 修复后继续。"""
    def gate_fail(content, ctx):
        return False, "内容过短"

    def fixer(stage_name, content, ctx, errors):
        return content + "（已修复）"

    p = MaterialPipeline("handout", _stages(), ["topic"],
                         gates=[gate_fail], fix_strategy=fixer)
    r = p.run(FakeLLM(), "导数")
    assert r["stages"].get("gate0_fixed") == "ok"


def test_pipeline_v20_no_gates_backward_compat():
    """S4：不传 gates → 退化 v1.1 行为（不报错）。"""
    p = MaterialPipeline("handout", _stages(), ["topic"])
    r = p.run(FakeLLM(), "导数")
    assert r["stages"].get("plan") == "ok"
    assert r["stages"].get("draft") == "ok"


def test_teaching_scene_grid():
    """S5：网格定位正确（6×6 覆盖画布）。"""
    s = TeachingScene()
    p1 = s._grid_pos(1, 1)
    p6 = s._grid_pos(6, 6)
    assert p1[0] < p6[0] and p1[1] < p6[1]  # 左上 < 右下
    assert -6 <= p1[0] <= 6 and -3.5 <= p1[1] <= 3.5


def test_teaching_scene_grid_bounds():
    """S6：网格边界钳制（越界输入收敛到合法范围）。"""
    s = TeachingScene()
    p = s._grid_pos(99, -99)
    assert -6 <= p[0] <= 6 and -3.5 <= p[1] <= 3.5


def test_scope_refine_level1_no_llm():
    """S7：L1 无 LLM → 保持原样。"""
    script = {"scenes": [{"id": "s1"}]}
    r = scope_refine(script, ["err"], None, level=1)
    assert isinstance(r, dict)
    assert r == script


def test_scope_refine_level3_no_llm():
    """S8：L3 无 LLM → None（触发整体重生）。"""
    script = {"scenes": [{"id": "s1"}]}
    r = scope_refine(script, ["err"], None, level=3)
    assert r is None


def test_tts_mux_no_video():
    """S9：无视频文件 → None（不崩溃）。"""
    assert tts_mux("/nonexistent/video.mp4", "旁白") is None


def test_video_pipeline_registered():
    """S10：video 管线已注册（§3.89 Step2）。"""
    from material_pipeline import create_pipeline
    p = create_pipeline("video")
    assert p is not None
    assert p.material_type == "video"
    assert len(p.gates) == 3  # 镜数/时长/旁白


def test_video_gate_scenes():
    """S11：视频门——镜数不足 3 拒绝。"""
    from material_pipeline import video_pipeline
    p = video_pipeline()
    ok, reason = p.gates[0]([{"id": "s1"}], {})
    assert not ok and "镜数不足" in reason
    ok2, _ = p.gates[0]([{"id": f"s{i}"} for i in range(4)], {})
    assert ok2


def test_video_gate_duration():
    """S12：视频门——时长越界（<8s 或 >15s）拒绝。"""
    from material_pipeline import video_pipeline
    p = video_pipeline()
    scenes = [{"id": "s1", "duration_sec": 5},
              {"id": "s2", "duration_sec": 12},
              {"id": "s3", "duration_sec": 12}]
    ok, reason = p.gates[1](scenes, {})
    assert not ok and "时长" in reason
    good = [{"id": f"s{i}", "duration_sec": 12} for i in range(3)]
    ok2, _ = p.gates[1](good, {})
    assert ok2


def test_video_gate_narration():
    """S13：视频门——静音镜（无旁白）拒绝。"""
    from material_pipeline import video_pipeline
    p = video_pipeline()
    scenes = [{"id": "s1", "duration_sec": 12, "narration": "有"},
              {"id": "s2", "duration_sec": 12, "narration": ""}]
    ok, reason = p.gates[2](scenes, {})
    assert not ok and "静音" in reason


def test_manim_pipeline_registered():
    """S14：manim 管线已注册（§3.89 Step3）。"""
    from material_pipeline import create_pipeline
    p = create_pipeline("manim")
    assert p is not None
    assert p.material_type == "manim"
    assert len(p.gates) == 1  # run_all_gates 门
    assert p.fix_strategy is not None  # scope_refine 三级


def test_six_pipelines_registered():
    """S15：6 类物料管线全部注册。"""
    import material_pipeline as mp
    expected = {"handout", "script", "ppt", "mindmap", "video", "manim"}
    assert expected == set(mp._PIPELINES.keys())


# ═══════════════════════════════════════════════════════════
# Step5：gates_lib 门库
# ═══════════════════════════════════════════════════════════
def test_gate_ppt_pages():
    """S16：PPT 页数门——6-10 页硬标准。"""
    from gates_lib import gate_ppt_pages
    ok, _ = gate_ppt_pages()({"pages": [{} for _ in range(6)]}, {})
    assert ok
    ok2, reason = gate_ppt_pages()({"pages": [{} for _ in range(3)]}, {})
    assert not ok2 and "页数" in reason


def test_gate_ppt_density():
    """S17：PPT 密度门——薄页（<3 要点）拒绝。"""
    from gates_lib import gate_ppt_density
    good = {"pages": [{"bullets": ["a", "b", "c"]} for _ in range(2)]}
    assert gate_ppt_density()(good, {})[0]
    bad = {"pages": [{"bullets": ["a"]}]}
    ok, reason = gate_ppt_density()(bad, {})
    assert not ok and "薄页" in reason


def test_gate_ppt_examples():
    """S18：PPT 例子门——无实例拒绝。"""
    from gates_lib import gate_ppt_examples
    ok, _ = gate_ppt_examples()({"pages": [{"examples": ["例1"]}]}, {})
    assert ok
    ok2, reason = gate_ppt_examples()({"pages": [{"bullets": ["a"]}]}, {})
    assert not ok2 and "实例不足" in reason


def test_gate_handout_sections():
    """S19：讲义节数门——≥3 节（课前/课中/课后）。"""
    from gates_lib import gate_handout_sections
    assert gate_handout_sections()({"sections": [{}, {}, {}]}, {})[0]
    ok, reason = gate_handout_sections()({"sections": [{}, {}]}, {})
    assert not ok and "节数" in reason


def test_gate_handout_blocks():
    """S20：讲义四块门——每节含概念/讲解/例题/小结之一。"""
    from gates_lib import gate_handout_blocks
    good = {"sections": [{"concept": "x", "explanation": "y"}]}
    assert gate_handout_blocks()(good, {})[0]
    bad = {"sections": [{"title": "只有标题"}]}
    ok, reason = gate_handout_blocks()(bad, {})
    assert not ok and "缺块" in reason


def test_gate_mindmap_branches():
    """S21：思维导图分支门——3-5 分支。"""
    from gates_lib import gate_mindmap_branches
    assert gate_mindmap_branches()({"branches": [{}, {}, {}]}, {})[0]
    ok, reason = gate_mindmap_branches()({"branches": [{}, {}]}, {})
    assert not ok and "分支数" in reason


def test_gate_mindmap_depth():
    """S22：思维导图深度门——分支需二级节点。"""
    from gates_lib import gate_mindmap_depth
    good = {"branches": [{"children": [{"name": "a"}]}]}
    assert gate_mindmap_depth()(good, {})[0]
    bad = {"branches": [{"name": "无子节点"}]}
    ok, reason = gate_mindmap_depth()(bad, {})
    assert not ok and "浅分支" in reason


def test_gates_registry():
    """S23：门库注册表按物料类型就位。"""
    from gates_lib import GATE_REGISTRY, get_gates
    assert len(GATE_REGISTRY["ppt"]) == 3
    assert len(GATE_REGISTRY["handout"]) == 3
    assert len(GATE_REGISTRY["mindmap"]) == 2
    assert get_gates("manim") == []


# ═══════════════════════════════════════════════════════════
# Step5：fixers_lib 修复策略
# ═══════════════════════════════════════════════════════════
def test_fixer_retry_no_llm():
    """S24：retry 无 LLM → 保持原样。"""
    from fixers_lib import make_retry_fixer
    r = make_retry_fixer()("draft", "内容", {}, ["错误"])
    assert r == "内容"


def test_fixer_escalate_level_upgrade():
    """S25：escalate 跨轮升级（ctx 记录 level L1→L2）。"""
    from fixers_lib import make_escalate_fixer
    fixer = make_escalate_fixer()
    ctx = {}
    script = {"scenes": [{"id": "s1"}]}
    r1 = fixer("draft", script, ctx, ["err"])
    assert isinstance(r1, dict)          # L1 保持原样
    assert ctx.get("_fix_level_draft") == 2  # 已升级
    r2 = fixer("draft", script, ctx, ["err"])
    assert ctx.get("_fix_level_draft") == 3  # 再升级到 L3


def test_fixer_escalate_empty_scene():
    """S26：escalate 空剧本 → None（触发重生）。"""
    from fixers_lib import make_escalate_fixer
    r = make_escalate_fixer()("draft", {"scenes": []}, {}, ["err"])
    assert r is None


def test_fixer_regenerate_no_stages():
    """S27：regenerate 无 stages → 退化 retry 保持原样。"""
    from fixers_lib import make_regenerate_fixer
    r = make_regenerate_fixer()("draft", "内容", {}, ["err"])
    assert r == "内容"


def test_fixer_registry():
    """S28：修复策略注册表 3 策略。"""
    from fixers_lib import FIXER_REGISTRY, get_fixer
    assert set(FIXER_REGISTRY.keys()) == {"retry", "escalate", "regenerate"}
    assert get_fixer("retry") is not None
    assert get_fixer("nope") is None
