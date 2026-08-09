"""PAEG 运行时依赖的懒加载单例。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


_llm: Any = None
_kb: Any = None
_paeg: Any = None
_user_store: Any = None
_user_store_initialized = False
_conv_store: Any = None
_conv_store_initialized = False
_evolver: Any = None
_evolver_initialized = False
_file_generator: Any = None
_file_generator_initialized = False
_skill_registry: Any = None
_skill_registry_initialized = False
_mcp_client: Any = None
_mcp_client_initialized = False
_mcp_health_stats: Dict[str, Any] = {}
_agent_engine: Any = None
_agent_engine_initialized = False
_library: Any = None
_library_initialized = False
_periodic_updater: Any = None


def get_llm() -> Any:
    global _llm
    if _llm is None:
        from config import LLM_MODEL, LLM_PROVIDER
        from llm_adapter import create_llm

        _llm = create_llm(LLM_PROVIDER, model=LLM_MODEL)
        print(f"[PAEG Server] LLM: {LLM_PROVIDER}/{LLM_MODEL or 'default'} -> {_llm.name}")
    return _llm


def get_kb() -> Any:
    global _kb
    if _kb is None:
        from knowledge_base import KnowledgeBase

        _kb = KnowledgeBase()
    return _kb


def get_library() -> Any:
    global _library, _library_initialized
    if not _library_initialized:
        _library_initialized = True
        try:
            from library_loader import KnowledgeLibrary

            _library = KnowledgeLibrary()
            added = _library.register(get_kb())
            if added:
                print(f"[PAEG Server] Library 知识库扩展: 新增 {added} 个节点")
            print(f"[PAEG Server] Library 可索引源文件: {len(_library.raw_files)} 个")
        except Exception as exc:
            _library = None
            print(f"[PAEG Server] Library 加载跳过: {exc}")
    return _library


def get_paeg() -> Any:
    global _paeg
    if _paeg is None:
        from paeg import PAEG

        get_library()
        _paeg = PAEG(get_llm(), get_kb(), enable_self_update=True, verbose=False)
    return _paeg


def get_user_store() -> Any:
    global _user_store, _user_store_initialized
    if not _user_store_initialized:
        _user_store_initialized = True
        try:
            from user_store import UserStore

            _user_store = UserStore()
            print(f"[PAEG Server] 用户系统就绪: {_user_store.stats()['users']} 个已注册用户")
        except Exception as exc:
            _user_store = None
            print(f"[PAEG Server] 用户系统初始化失败: {exc}")
    return _user_store


def get_conv_store() -> Any:
    global _conv_store, _conv_store_initialized
    if not _conv_store_initialized:
        _conv_store_initialized = True
        try:
            from user_store import ConversationStore

            _conv_store = ConversationStore()
            try:
                removed = _conv_store.cleanup()
                if removed:
                    print(f"[PAEG Server] 对话清理: 已删除 {removed} 个超期会话")
            except Exception as exc:
                print(f"[PAEG Server] 对话清理失败: {exc}")
            print(f"[PAEG Server] 对话历史存储就绪（保留 {_conv_store.retention_days} 天）")
        except Exception as exc:
            _conv_store = None
            print(f"[PAEG Server] 对话历史初始化失败: {exc}")
    return _conv_store


def get_evolver() -> Any:
    global _evolver, _evolver_initialized
    if not _evolver_initialized:
        _evolver_initialized = True
        try:
            from self_evolution import SelfEvolution

            _evolver = SelfEvolution(llm=get_llm(), verbose=True)
            print("[PAEG Server] 自进化模块就绪（知识库/提示词/工具经验，质量门禁过滤）")
        except Exception as exc:
            _evolver = None
            print(f"[PAEG Server] 自进化模块初始化失败（不影响主服务）: {exc}")
    return _evolver


def get_file_generator() -> Any:
    global _file_generator, _file_generator_initialized
    if not _file_generator_initialized:
        _file_generator_initialized = True
        try:
            from file_generator import FileGenerator

            _file_generator = FileGenerator(get_llm())
        except Exception as exc:
            _file_generator = None
            print(f"[PAEG Server] 文件生成器初始化失败: {exc}")
    return _file_generator


def get_skill_registry() -> Any:
    global _skill_registry, _skill_registry_initialized
    if not _skill_registry_initialized:
        _skill_registry_initialized = True
        try:
            from skill_registry import SkillRegistry

            _skill_registry = SkillRegistry()
            stats = _skill_registry.stats()
            print(f"[PAEG Server] SkillRegistry 就绪：{stats['count']} 个技能 (L1 目录将注入 system prompt)")
        except Exception as exc:
            _skill_registry = None
            print(f"[PAEG Server] SkillRegistry 初始化失败（不影响主服务）: {exc}")
    return _skill_registry


def get_mcp_client() -> Tuple[Any, Dict[str, Any]]:
    global _mcp_client, _mcp_client_initialized, _mcp_health_stats
    if not _mcp_client_initialized:
        _mcp_client_initialized = True
        _mcp_health_stats = {"configured": 0, "connected": 0, "tools": 0, "last_error": ""}
        try:
            from mcp_client import get_mcp_client as create_mcp_client

            _mcp_client = create_mcp_client()
            try:
                connected = _mcp_client.connect_all()
                _mcp_health_stats["connected"] = connected
                _mcp_health_stats["configured"] = sum(
                    1 for config in _mcp_client.config.values() if config.get("enabled", True)
                )
                _mcp_health_stats["tools"] = len(_mcp_client._tools)
                _mcp_health_stats["last_error"] = _mcp_client._last_error
                print(
                    f"[PAEG Server] MCP 连接：成功 {connected}/{_mcp_health_stats['configured']} 个 server, "
                    f"暴露 {_mcp_health_stats['tools']} 个工具"
                )
                if connected == 0 and _mcp_health_stats["last_error"]:
                    print(f"[PAEG Server] MCP 提示：{_mcp_health_stats['last_error'][:200]}（容错继续）")
            except Exception as exc:
                _mcp_health_stats["last_error"] = f"connect_all 异常: {str(exc)[:120]}"
                print(f"[PAEG Server] MCP connect_all 异常（容错继续）: {exc}")
        except Exception as exc:
            _mcp_client = None
            _mcp_health_stats["last_error"] = f"导入失败: {str(exc)[:120]}"
            print(f"[PAEG Server] MCP 客户端初始化失败（不影响主服务）: {exc}")
    return _mcp_client, _mcp_health_stats


def get_agent_engine() -> Any:
    global _agent_engine, _agent_engine_initialized
    if not _agent_engine_initialized:
        _agent_engine_initialized = True
        try:
            from agent_engine import AgentEngine

            _agent_engine = AgentEngine(llm=get_llm(), max_iterations=3, replan_limit=2)
            print("[PAEG Server] AgentEngine 就绪（Plan→Act→Observe→Reflect 循环 max_iter=3）")
        except Exception as exc:
            _agent_engine = None
            print(f"[PAEG Server] AgentEngine 初始化失败（不影响主服务）: {exc}")
    return _agent_engine


def get_periodic_updater() -> Any:
    global _periodic_updater
    if _periodic_updater is None:
        from periodic_self_update import PeriodicSelfUpdater

        _periodic_updater = PeriodicSelfUpdater(llm=get_llm(), paeg=get_paeg(), verbose=True)
    return _periodic_updater
