# -*- coding: utf-8 -*-
"""任务1：架构连通性检测——作为关键技术指标。"""
import sys, io, os, json, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

IMPL = r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型'

def read(name):
    try:
        return open(os.path.join(IMPL, name), encoding='utf-8').read()
    except Exception:
        return ""

sv = read('server.py')
tr = read('tool_registry.py')
pr = read('prompts.py')

# 模块连通性检查（每个核心模块 → 被谁调用）
MODULES = {
    # (模块文件, 被调用的关键字, 调用方检查)
    'tool_registry': ['run_agent_loop', 'execute_tool'],
    'tool_recovery': ['with_recovery', 'tool_recovery'],
    'tool_cache': ['cached_call', 'tool_cache'],
    'context_manager': ['ContextManager', 'context_manager'],
    'memory_system': ['MemorySystem', 'memory_system'],
    'expert_guard': ['ExpertGuard', 'expert_guard'],
    'skill_registry': ['SkillRegistry', 'skill_registry'],
    'problem_solver': ['solve_problem', 'problem_solver'],
    'web_search_tool': ['web_search', 'web_search_tool'],
    'meta_router': ['is_meta_question', 'meta_router'],
    'self_improve': ['SelfImprover', 'self_improve'],
    'teaching_memory': ['load_teaching_memory', 'teaching_memory'],
    'mcp_gateway': ['start_mcp_server', 'mcp_gateway'],
    'file_generator': ['FileGenerator', 'file_generator'],
    'quotes': ['quote_of_the_day', 'quotes'],
    'agent_engine': ['run_agent', 'agent_engine'],
}

results = []
print("=== 架构连通性检测 ===\n")
for mod, keywords in MODULES.items():
    # 模块文件存在
    exists = os.path.exists(os.path.join(IMPL, mod + '.py'))
    # 被 server 或 tool_registry 调用（直接或间接）
    called_in_sv = any(k in sv for k in keywords)
    called_in_tr = any(k in tr for k in keywords)
    connected = exists and (called_in_sv or called_in_tr)
    results.append({
        'module': mod, 'exists': exists,
        'called_in_server': called_in_sv, 'called_in_tool_registry': called_in_tr,
        'connected': connected
    })
    print(f"  [{'OK' if connected else 'BROKEN'}] {mod}: 文件={'✓' if exists else '✗'} server={'✓' if called_in_sv else '✗'} tool_registry={'✓' if called_in_tr else '✗'}")

connected_count = sum(1 for r in results if r['connected'])
total = len(results)
print(f"\n连通率: {connected_count}/{total} ({connected_count/total*100:.0f}%)")

# 关键链路（chat/teach 完整调用链）
print("\n=== 关键调用链 ===")
chains = {
    'chat → run_agent_loop → tools': 'run_agent_loop' in sv and 'execute_tool' in tr,
    'teach → paeg.teach → subagents': 'paeg.teach' in sv,
    '记忆压缩 (memory.compress)': 'compress_if_needed' in sv,
    '教学记忆注入 (teaching_memory)': 'load_teaching_memory' in sv,
    '自我改进记录 (self_improve)': 'SelfImprover' in sv,
    '上下文管理 (context_manager)': 'ContextManager' in sv,
    '深度守门 (expert_guard)': 'ExpertGuard' in sv,
    '出题/方法/元问题路由 (meta_router)': 'meta_router' in sv,
}
for name, ok in chains.items():
    print(f"  [{'OK' if ok else 'MISS'}] {name}")

# 输出 JSON 报告
report = {
    'modules': results,
    'connectivity_rate': connected_count/total,
    'key_chains': {k: bool(v) for k, v in chains.items()},
    'timestamp': __import__('datetime').datetime.now().isoformat(),
}
report_path = os.path.join(IMPL, 'arch_report.json')
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print(f"\n报告已存: {report_path}")
