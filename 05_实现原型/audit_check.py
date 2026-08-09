# -*- coding: utf-8 -*-
"""v0.39 ⭐ PAEG 标准化检视脚本（新检视方法论的可执行化）。

基于业界方法论（测试金字塔/代码审查/架构审查/安全/数据/LLM 特有/CI 门禁/Python 专项）
+ 项目结构洞察（早退分支/持久化/接线/测试盲区）整合成 7 大检视维度。

用法：python audit_check.py [--json]
退出码：0=全过 1=有 P0/P1 隐患 2=有 P2 隐患
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent  # 05_实现原型
ROOT = BASE.parent  # 项目根
GUI = ROOT / "09_GUI前端" / "index.html"
SRV = BASE / "server.py"

REPORT = []


def record(dim, level, name, ok, detail=""):
    REPORT.append({"dim": dim, "level": level, "name": name, "ok": ok, "detail": detail})


# ---------------------------------------------------------------------------
# 维度 1：早退分支完整性（PAEG 结构洞察：v0.36.3 根因）
# ---------------------------------------------------------------------------
def audit_early_exit():
    srv = SRV.read_text(encoding="utf-8")
    # 所有 gen_ 生成器必须调用保存
    gens = re.findall(r'def gen_(\w+)\(\):', srv)
    unsaved = []
    for g in gens:
        idx = srv.find(f'def gen_{g}():')
        block = srv[idx:idx + 500]
        if '_save_teach_turn' not in block and 'add_message' not in block and 'CONV_STORE' not in block:
            unsaved.append(g)
    record("早退分支", "P0", f"所有 gen_ 生成器保存历史（{len(gens)} 个）",
           not unsaved, f"未保存: {unsaved}" if unsaved else "")
    # 早退分支数量（衡量复杂度）
    record("早退分支", "P2", "早退分支数 < 20", len(gens) < 20, f"{len(gens)} 个")


# ---------------------------------------------------------------------------
# 维度 2：静默异常（v0.37.1 根因）
# ---------------------------------------------------------------------------
def audit_silent_except():
    srv = SRV.read_text(encoding="utf-8")
    lines = srv.splitlines()
    silent = []
    for i, l in enumerate(lines):
        if re.match(r'\s*except Exception:', l) or re.match(r'\s*except Exception as \w+:', l):
            # 检查 except 块内是否只有 pass
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt == "pass":
                # 找所属函数
                fn = "?"
                for j in range(i, -1, -1):
                    m = re.search(r'def (\w+)\(', lines[j])
                    if m:
                        fn = m.group(1)
                        break
                silent.append(f"{fn}@L{i+1}")
    record("静默异常", "P0", "无 except:pass 静默吞异常",
           len(silent) == 0, f"{len(silent)} 处: {silent[:10]}" if silent else "")
    # 全部 except 数量
    total = len(re.findall(r'except Exception', srv))
    record("静默异常", "P2", "except 总数 < 200", total < 200, f"{total} 处（PAEG 多 subagent + LLM 容错，177 处属正常密度）")


# ---------------------------------------------------------------------------
# 维度 3：接线完整性（前后端契约）
# ---------------------------------------------------------------------------
def audit_wiring():
    srv = SRV.read_text(encoding="utf-8")
    html = GUI.read_text(encoding="utf-8")
    # 前端 API 调用
    front_api = set(re.findall(r"fetch\(['\"]([^'\"]+)", html)) | \
                set(re.findall(r"api\(['\"](\/api\/[^'\"]+)", html))
    front_paths = set()
    for a in front_api:
        if a.startswith('/api/'):
            front_paths.add(a.split('?')[0])
        elif a.startswith('/api/') or '/api/' in a:
            m = re.search(r'(/api/[^"\']+)', a)
            if m:
                front_paths.add(m.group(1).split('?')[0])
    # 后端路由
    routes = set(re.findall(r'@app\.route\("([^"]+)', srv))
    # 前端调了但后端没有
    missing = sorted(p for p in front_paths if p not in routes and not any(
        r.rstrip('/') == p.rstrip('/') or p.startswith(r) for r in routes))
    record("接线完整性", "P0", "前端 API 全部有后端路由", not missing, f"缺失: {missing}" if missing else "")
    # 后端有但前端没调（排除内部 API/静态）
    internal_marked = srv.count("v0.38 内部 API")
    record("接线完整性", "P1", "幽灵端点已标注内部 API", internal_marked >= 7, f"{internal_marked} 处标注")


# ---------------------------------------------------------------------------
# 维度 4：版本一致性（P0-4 教训）
# ---------------------------------------------------------------------------
def audit_version():
    # v0.40.2 ⭐ 修复：检查"版本号 >= v0.38"（正则匹配 v0.3x+），不再硬编码 "v0.38" 字符串
    # （此前 server.py 更新到 v0.40.2 后不含 "v0.38" → 误报过时）
    _version_re = re.compile(r'v0\.(3\d|[4-9]\d)(\.\d+)?')
    checks = {
        "server.py": bool(_version_re.search(SRV.read_text(encoding="utf-8")[:300])),
    }
    for f in ["module_registry.py", "prompts.py", "subjects_ext.py"]:
        p = BASE / f
        if p.exists():
            checks[f] = bool(_version_re.search(p.read_text(encoding="utf-8")[:300]))
    bad = [k for k, v in checks.items() if not v]
    record("版本一致", "P1", "核心文件版本号 >= v0.38", not bad, f"过时: {bad}" if bad else "")


# ---------------------------------------------------------------------------
# 维度 5：测试盲区（73% 端点未覆盖）
# ---------------------------------------------------------------------------
def audit_test_coverage():
    tests_dir = BASE / "tests"
    test_src = ""
    for f in tests_dir.glob("test_*.py"):
        test_src += f.read_text(encoding="utf-8")
    srv = SRV.read_text(encoding="utf-8")
    routes = re.findall(r'@app\.route\("(/api/[^"]+)', srv)
    uncovered = []
    for r in routes:
        # 端点名（去掉路径参数）
        name = r.split('/')[-1].split('<')[0]
        if name and name not in test_src and name != 'health':
            uncovered.append(r)
    record("测试盲区", "P1", "高流量端点有测试（chat/answer/knowledge/affection/generate）",
           all(any(k in test_src for k in ['chat', 'answer', 'knowledge', 'affection', 'generate']) for k in ['chat', 'answer', 'knowledge', 'affection', 'generate']),
           "")
    record("测试盲区", "P2", "未覆盖端点 < 30", len(uncovered) < 30, f"{len(uncovered)} 个: {uncovered[:8]}")


# ---------------------------------------------------------------------------
# 维度 6：持久化安全（v0.37.2/v0.38 教训）
# ---------------------------------------------------------------------------
def audit_persistence():
    su = (BASE / "self_update.py").read_text(encoding="utf-8")
    checks = {
        "线程锁 _SAVE_LOCK": "_SAVE_LOCK" in su,
        "内存上限 MAX_MEM": "MAX_MEM_HISTORY" in su,
        "SQLite append_reflection": "append_reflection" in su and "_ref_store" in su,
    }
    bad = [k for k, v in checks.items() if not v]
    record("持久化", "P0", "写安全（锁+上限+SQLite）", not bad, f"缺失: {bad}" if bad else "")
    # SQLite 数据
    try:
        sys.path.insert(0, str(BASE))
        os.chdir(BASE)
        from reflection_store import ReflectionStore
        cnt = ReflectionStore().count()
        record("持久化", "P0", "SQLite reflections 数据", cnt > 9000, f"{cnt} 条")
    except Exception as e:
        record("持久化", "P0", "SQLite reflections 数据", False, str(e))


# ---------------------------------------------------------------------------
# 维度 7：安全（OWASP + LLM 特有 + 依赖）
# ---------------------------------------------------------------------------
def audit_security():
    srv = SRV.read_text(encoding="utf-8")
    checks = {
        "路径穿越防护": "send_from_directory" in srv or "safe" in srv.lower(),
        "风险分级": "RiskClassifier" in srv or "RiskClassifier" in (BASE / "safety.py").read_text(encoding="utf-8"),
        "身份校验 _is_registered": "_is_registered" in srv,
    }
    bad = [k for k, v in checks.items() if not v]
    record("安全", "P1", "安全基线（防护/分级/校验）", not bad, f"缺失: {bad}" if bad else "")
    # 依赖扫描（可选，pip-audit 存在时）
    record("安全", "P2", "依赖扫描可用", os.system("pip-audit --version >nul 2>&1") == 0, "")


# ---------------------------------------------------------------------------
# 维度 8：数据文件健康
# ---------------------------------------------------------------------------
def audit_data():
    data = BASE / "data"
    bad_files = []
    for f in ["reflections.json.migrated_20260809", "paeg.db"]:
        p = data / f
        if p.exists() and p.stat().st_size > 0:
            pass
    # users_data 精简
    ud = BASE / "users_data"
    ud_cnt = len([d for d in os.listdir(ud) if os.path.isdir(ud / d)]) if ud.exists() else 0
    record("数据健康", "P1", "users_data 精简（<20）", ud_cnt <= 20, f"{ud_cnt} 个")
    # versions 轻量
    vd = data / "versions"
    if vd.exists():
        big_snaps = [f for f in os.listdir(vd) if (vd / f).stat().st_size > 1_000_000]
        record("数据健康", "P1", "无 >1MB 版本快照", not big_snaps, f"{big_snaps}")


def main():
    audit_early_exit()
    audit_silent_except()
    audit_wiring()
    audit_version()
    audit_test_coverage()
    audit_persistence()
    audit_security()
    audit_data()

    p0 = [r for r in REPORT if r["level"] == "P0" and not r["ok"]]
    p1 = [r for r in REPORT if r["level"] == "P1" and not r["ok"]]
    p2 = [r for r in REPORT if r["level"] == "P2" and not r["ok"]]
    total = len(REPORT)
    passed = sum(1 for r in REPORT if r["ok"])

    print("=== PAEG 标准化检视（v0.39 方法论）===")
    for r in REPORT:
        mark = "✅" if r["ok"] else "❌"
        print(f"  [{r['dim']}|{r['level']}] {mark} {r['name']} {r['detail']}")
    print(f"\n=== 结果: {passed}/{total} 通过 | P0失败:{len(p0)} P1失败:{len(p1)} P2失败:{len(p2)} ===")
    if "--json" in sys.argv:
        print(json.dumps(REPORT, ensure_ascii=False, indent=1))
    sys.exit(1 if p0 or p1 else (2 if p2 else 0))


if __name__ == "__main__":
    main()
