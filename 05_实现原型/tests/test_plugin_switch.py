# -*- coding: utf-8 -*-
"""§3.112 插件切换测试：挂载 / 双轨 / fallback / SSE 契约。

现有测试默认走旧路径（PAEG_USE_MATERIAL_PLUGIN=0），本文件显式验证插件路径。
"""
import os
import sys

sys.path.insert(0, r"D:\wbo-workspace\paeg_project\05_实现原型")
# 插件 src（开发模式）
_PLUGIN = r"D:\wbo-workspace\paeg_project\paeg-teaching-materials\src"
if os.path.isdir(_PLUGIN) and _PLUGIN not in sys.path:
    sys.path.insert(0, _PLUGIN)

import pytest


@pytest.fixture(autouse=True)
def _plugin_env():
    """插件路径默认开启；测试结束恢复。"""
    os.environ["PAEG_USE_MATERIAL_PLUGIN"] = "1"
    from services import material_bridge
    material_bridge._USE_PLUGIN_CACHE = None  # 重置灰度缓存
    yield
    os.environ["PAEG_USE_MATERIAL_PLUGIN"] = "0"
    material_bridge._USE_PLUGIN_CACHE = None


# ─────────────────────────────────────
# 1. 桥基础设施
# ─────────────────────────────────────
class TestBridgeInfra:
    def test_bridge_status(self):
        from services.material_bridge import bridge_status
        bs = bridge_status()
        assert "active" in bs
        assert "version" in bs
        assert "use_plugin" in bs

    def test_install_plugin(self):
        from services.material_bridge import install_material_plugin, plugin_active
        ok = install_material_plugin()
        # 插件 src 已加 path → 应成功（若环境无插件则跳过断言）
        if ok:
            assert plugin_active() is True

    def test_execute_typed(self):
        """execute_typed 返回 dict（供双轨消费）。"""
        from services.material_bridge import execute_typed, install_material_plugin, BridgeError
        ok = install_material_plugin()
        if not ok:
            pytest.skip("插件未安装")
        # 注入 mock LLM 避免真实 API
        from paeg_teaching_materials import MaterialRegistry
        def mock_llm(system, user, max_tokens=2000, temperature=0.7):
            return "## 教学目标\n（mock）\n## 课堂导入\n（mock）\n## 新课讲授\n（mock）\n## 巩固练习\n（mock）\n## 课堂小结\n（mock）\n## 课后作业\n（mock）"
        MaterialRegistry.inject(llm=mock_llm)
        r = execute_typed("generate_handout", {"topic": "力学", "subject": "物理"})
        assert r.get("ok") is True

    def test_execute_typed_gray_off(self):
        """灰度关闭 → BridgeError（触发回退）。"""
        os.environ["PAEG_USE_MATERIAL_PLUGIN"] = "0"
        from services import material_bridge
        material_bridge._USE_PLUGIN_CACHE = None
        from services.material_bridge import execute_typed, BridgeError
        with pytest.raises(BridgeError):
            execute_typed("generate_handout", {"topic": "x"})


# ─────────────────────────────────────
# 2. 双轨（_gen_* 插件优先）
# ─────────────────────────────────────
class TestDualTrack:
    def setup_method(self):
        os.environ["PAEG_USE_MATERIAL_PLUGIN"] = "1"
        from services import material_bridge
        material_bridge._USE_PLUGIN_CACHE = None
        from services.material_bridge import install_material_plugin
        install_material_plugin()
        from paeg_teaching_materials import MaterialRegistry
        def mock_llm(system, user, max_tokens=2000, temperature=0.7):
            return "## 教学目标\n（mock）\n## 课堂导入\n（mock）\n## 新课讲授\n（mock）\n## 巩固练习\n（mock）\n## 课堂小结\n（mock）\n## 课后作业\n（mock）"
        MaterialRegistry.inject(llm=mock_llm)

    def test_gen_handout_plugin(self):
        """灰度 1 → _gen_handout 走插件。"""
        import material_router as mr
        r = mr._gen_handout(None, "力学", "物理", "test")
        assert r.get("ok") is True
        assert "教学目标" in str(r.get("content"))

    def test_gen_ppt_plugin(self):
        import material_router as mr
        r = mr._gen_ppt(None, "光合作用", "生物", "test", grade="high_school")
        assert r.get("ok") is True
        assert r.get("step_type") == "ppt"


# ─────────────────────────────────────
# 3. fallback（插件失败 → 旧实现）
# ─────────────────────────────────────
class TestFallback:
    def test_fallback_legacy(self):
        """灰度 0 → _gen_mindmap 走旧实现（knowledge_map）。"""
        os.environ["PAEG_USE_MATERIAL_PLUGIN"] = "0"
        from services import material_bridge
        material_bridge._USE_PLUGIN_CACHE = None
        import material_router as mr
        r = mr._gen_mindmap(None, "细胞", "生物", "test", learner=None)
        # 旧路径：knowledge_map（可能失败但不会抛 BridgeError）
        assert isinstance(r, dict)
        assert "step_type" in r


# ─────────────────────────────────────
# 4. SSE 契约（插件路径事件流）
# ─────────────────────────────────────
class TestSSEContract:
    def test_execute_generator_events(self):
        """插件结果 → SSE presentation + done 事件（字节级契约）。"""
        from services.material_bridge import install_material_plugin, execute_generator
        ok = install_material_plugin()
        if not ok:
            pytest.skip("插件未安装")
        from paeg_teaching_materials import MaterialRegistry
        def mock_llm(system, user, max_tokens=2000, temperature=0.7):
            return "## 教学目标\n（mock）"
        MaterialRegistry.inject(llm=mock_llm)
        events = list(execute_generator("generate_handout", {"topic": "力学", "subject": "物理"}))
        assert len(events) >= 2
        joined = "\n".join(events)
        assert "event: presentation" in joined
        assert "event: done" in joined
