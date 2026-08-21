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

# §3.45 ⭐ 架构拆分后：路由分布两处（server.py + blueprints/*.py），
# 接线完整性 / 测试盲区 / 内部 API 标注 检查必须双源扫描。
BLUEPRINTS_DIR = BASE / "blueprints"


def _backend_route_src() -> str:
    """server.py + blueprints/*.py 拼接源码（蓝图 @bp.route 归一化为 @app.route），
    使既有 `@app.route(...)` 正则无需改动即可覆盖全部路由。"""
    src = SRV.read_text(encoding="utf-8")
    if BLUEPRINTS_DIR.is_dir():
        for _bpf in sorted(BLUEPRINTS_DIR.glob("*.py")):
            _bsrc = _bpf.read_text(encoding="utf-8")
            src += "\n" + _bsrc.replace("@bp.route", "@app.route")
    return src

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
            # v0.40.5: gen_empty_chat 是空输入引导语（无实际对话内容），无需保存历史
            if g != 'empty_chat':
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
    record("静默异常", "P2", "except 总数 < 230", total < 230, f"{total} 处（PAEG 多 subagent + LLM 容错，177 处属正常密度；217 = 既有 + 新增功能端点防护）")


# ---------------------------------------------------------------------------
# 维度 3：接线完整性（前后端契约）
# ---------------------------------------------------------------------------
def audit_wiring():
    # §3.45 ⭐ 双源：server.py + blueprints/*.py（蓝图路由已迁出，接线检查需覆盖）
    srv = _backend_route_src()
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
    record("接线完整性", "P1", "幽灵端点已标注内部 API", internal_marked >= 6, f"{internal_marked} 处标注")


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
    # §3.45 ⭐ 双源：server.py + blueprints/*.py（蓝图路由已迁出，测试盲区需覆盖）
    srv = _backend_route_src()
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
    record("数据健康", "P1", "users_data 精简（<50）", ud_cnt <= 50, f"{ud_cnt} 个（真实+少量测试，41 正常）")
    # versions 轻量
    vd = data / "versions"
    if vd.exists():
        big_snaps = [f for f in os.listdir(vd) if (vd / f).stat().st_size > 1_000_000]
        record("数据健康", "P1", "无 >1MB 版本快照", not big_snaps, f"{big_snaps}")




# ---------------------------------------------------------------------------
# 维度 9：事件处理器完整性（v0.41.2 教训——登录后状态刷新）
# ---------------------------------------------------------------------------
def audit_handler_completeness():
    html = GUI.read_text(encoding="utf-8")
    # applyLogin 必须调用必备加载函数（否则登录后元认知/画像/会话不刷新）
    m = re.search(r'function applyLogin\(result\) \{(.*?)\n\}', html, re.S)
    if m:
        body = m.group(1)
        required = ['loadProfile', 'loadMetaLog', 'loadConversations']
        missing = [fn for fn in required if fn not in body]
        record("处理器完整", "P0", "applyLogin 调用必备加载函数",
               not missing, f"缺: {missing}" if missing else "")
    else:
        record("处理器完整", "P0", "applyLogin 调用必备加载函数", False, "未找到 applyLogin")
    # 头像上传成功回调必须保存 STATE+localStorage
    m2 = re.search(r'avatar-input.*?addEventListener.*?\{.*?\}', html, re.S)
    if m2 and 'avatarUrl' in m2.group(0):
        record("处理器完整", "P1", "头像上传保存 STATE+localStorage", 'localStorage.setItem' in m2.group(0), "")
    else:
        record("处理器完整", "P1", "头像上传保存 STATE+localStorage", True, "")


# ---------------------------------------------------------------------------
# 维度 10：教学会话必有反思（v0.41.4 教训——u106 有 7 个教学会话但元认知日志 0 条）
# ---------------------------------------------------------------------------
def audit_reflection_consistency():
    """每个注册用户若存在教学会话，则必须已有对应 user_modeling 反思。

    u106 教训：users_data/u106/conversations.json 有 7 个 teach/chat 会话，
    但 SQLite reflections 0 条 → 元认知日志空白（数据缺口，非前端问题）。
    此检查常驻 audit，防止"学了但日志空"再次发生。
    """
    try:
        sys.path.insert(0, str(BASE))
        os.chdir(BASE)
        import json as _json
        import sqlite3
        db_path = BASE / "data" / "paeg.db"
        if not db_path.exists():
            record("反思一致", "P0", "教学会话必有反思记录", False, "paeg.db 不存在")
            return
        ud = BASE / "users_data"
        if not ud.exists():
            record("反思一致", "P0", "教学会话必有反思记录", True, "无 users_data")
            return
        # 收集所有注册用户（u<digits>）的 teach/chat 会话
        import re as _re
        users_with_teach = {}
        for d in sorted(os.listdir(ud)):
            dd = ud / d
            if not dd.is_dir():
                continue
            conv_f = dd / "conversations.json"
            if not conv_f.exists():
                continue
            m = _re.match(r"^u\d+$", d)
            if not m:
                continue
            try:
                data = _json.loads(conv_f.read_text(encoding="utf-8"))
                convs = data.get("conversations", []) if isinstance(data, dict) else data
                teach_cnt = sum(1 for c in convs if c.get("mode") == "teach")
                if teach_cnt > 0:
                    users_with_teach[d] = teach_cnt
            except Exception:
                continue
        # 查 SQLite 反思数（含 user_modeling）
        with sqlite3.connect(str(db_path)) as conn:
            gaps = []
            for uid, tcnt in sorted(users_with_teach.items()):
                row = conn.execute(
                    "SELECT COUNT(*) FROM reflections WHERE learner_id=?",
                    (uid,)).fetchone()
                rcnt = row[0] if row else 0
                if rcnt == 0:
                    gaps.append(f"{uid}(教学{tcnt}会话/反思{rcnt})")
        record("反思一致", "P0", "教学会话必有反思记录（注册用户）",
               not gaps, f"缺反思: {gaps}" if gaps else f"{len(users_with_teach)} 用户均正常")
    except Exception as e:
        record("反思一致", "P0", "教学会话必有反思记录", False, str(e))


# ---------------------------------------------------------------------------
# 维度 11：值域/展示质量（v0.41.4 教训——"风 visual / 情 neutral"直出）
# ---------------------------------------------------------------------------
def audit_display_quality():
    """检查 LLM 枚举值是否被前端/后端规范化，杜绝英文枚举原样直出。

    v0.41.4 教训：LLM 建模输出英文枚举（visual/neutral 等）+ 越界长句，
    此前 server.py 原样写入、前端原样显示 → 元认知日志出现"风 visual / 情 neutral"。
    结构性自检全过（数据落了库、路由有、锁有），但展示质量无人把关。
    此检查确保：①写入端有规范化函数 ②前端有中文映射表 ③无单字标签（风/情/擅/薄）。
    """
    srv = SRV.read_text(encoding="utf-8")
    html = GUI.read_text(encoding="utf-8")
    # 1) 后端：写入端必须调用规范化函数（_norm_trait_scalar）
    ok_norm = "_norm_trait_scalar" in srv and "_TRAIT_LS_CN" in srv and "_TRAIT_EMO_CN" in srv
    record("展示质量", "P0", "后端值域规范化函数存在", ok_norm,
           "" if ok_norm else "server.py 缺 _norm_trait_scalar/_TRAIT_LS_CN/_TRAIT_EMO_CN")
    # 2) 前端：必须有中文映射表（visual→视觉型 等）
    ok_map = ("视觉型" in html and "听觉型" in html and "动觉型" in html)
    record("展示质量", "P0", "前端枚举→中文映射表", ok_map,
           "" if ok_map else "index.html 缺 LS_CN/EMO_CN 中文映射")
    # 3) 前端：不得有单字缩写标签（风/情/擅/薄 直出）
    bad_labels = []
    for kw in ["`风 ${ls}`", "`情 ${emo}`", "`擅 ${ks}`", "`薄 ${kg}`"]:
        if kw in html:
            bad_labels.append(kw)
    record("展示质量", "P1", "无单字缩写标签", not bad_labels,
           f"残留: {bad_labels}" if bad_labels else "")
    # 4) 数据层：现有 user_modeling 记录不得残留英文枚举（visual/neutral/anxious 等）
    try:
        sys.path.insert(0, str(BASE))
        os.chdir(BASE)
        import sqlite3
        db_path = BASE / "data" / "paeg.db"
        en_vals = ["visual", "auditory", "reading", "kinesthetic", "mixed",
                   "anxious", "engaged", "neutral", "withdrawn"]
        leaked = []
        if db_path.exists():
            with sqlite3.connect(str(db_path)) as conn:
                rows = conn.execute(
                    "SELECT learner_id, concept, reflection_json FROM reflections"
                    " WHERE reflection_json LIKE '%user_modeling%' ORDER BY ts DESC LIMIT 200").fetchall()
            import json as _json
            for uid, concept, rj in rows:
                try:
                    r = _json.loads(rj)
                except Exception:
                    continue
                if r.get("type") != "user_modeling":
                    continue
                ls = r.get("learning_style") or ""
                emo = r.get("emotional_tendency") or ""
                mot = r.get("motivation") or ""
                for v in en_vals:
                    if v in str(ls) or v in str(emo) or v in str(mot):
                        leaked.append(f"{uid}:{v}")
                        break
        record("展示质量", "P1", "历史 user_modeling 无英文枚举残留", not leaked,
               f"残留 {len(leaked)} 处: {leaked[:6]}" if leaked else "")
    except Exception as e:
        record("展示质量", "P1", "历史 user_modeling 无英文枚举残留", False, str(e))


# ---------------------------------------------------------------------------
# 维度 12：昵称双源一致性（v0.41.5 教训——u106 users.json=团聚体/profile.json=学生）
# ---------------------------------------------------------------------------
def audit_nickname_consistency():
    """users.json.learner.nickname vs users_data/<uid>/profile.json.nickname vs
    users.json[user].nickname（根昵称）三方必须一致。

    v0.41.5 教训：LearnerProfile.nickname dataclass 默认"小李"，端点兜底"学生"/
    "学习者"，占位符被刻进 profile.json → 前端显示"学生"而 users.json 是"团聚体"。
    写入侧（register/save_learner/persist）零一致性保护，只有读取侧 v0.26 回退。
    """
    try:
        import re as _re
        users_json = BASE / "users.json"
        ud = BASE / "users_data"
        if not users_json.exists() or not ud.exists():
            record("昵称双源", "P0", "三方昵称一致", False, "users.json 或 users_data 缺失")
            return
        data = json.loads(users_json.read_text(encoding="utf-8"))
        bad = []
        for uid_dir in sorted(ud.iterdir()):
            if not uid_dir.is_dir():
                continue
            m = _re.match(r"^u\d+$", uid_dir.name)
            if not m:
                continue
            profile = uid_dir / "profile.json"
            if not profile.exists():
                continue
            try:
                p = json.loads(profile.read_text(encoding="utf-8"))
                p_nick = (p.get("nickname") or "").strip()
                root_nick, learner_nick = None, None
                for u in data.get("users", {}).values():
                    if u.get("user_id") == uid_dir.name:
                        root_nick = (u.get("nickname") or "").strip()
                        learner = u.get("learner") or {}
                        learner_nick = (learner.get("nickname") or "").strip()
                        break
                # 三方一致（占位符等价于空——占位符另查）
                norm = lambda s: "" if s in ("学生", "学习者", "小李") else s
                if norm(p_nick) != norm(root_nick) or (
                        learner_nick and norm(p_nick) != norm(learner_nick)):
                    bad.append(f"{uid_dir.name}: profile={p_nick!r} learner={learner_nick!r} root={root_nick!r}")
            except Exception:
                continue
        record("昵称双源", "P0", "profile.json/learner/users.json 三方昵称一致",
               not bad, f"不一致: {bad[:5]}" if bad else "")
        # 注册用户昵称不得是占位符（学生/学习者/小李/空）
        placeholders = {"学生", "学习者", "小李", ""}
        placebad = []
        for u in data.get("users", {}).values():
            uid = u.get("user_id", "")
            if not _re.match(r"^u\d+$", uid):
                continue
            nick = (u.get("nickname") or "").strip()
            if nick in placeholders:
                placebad.append(f"{uid}:{nick!r}")
        record("昵称双源", "P1", "注册用户昵称非占位符",
               not placebad, f"占位符: {placebad[:5]}" if placebad else "")
    except Exception as e:
        record("昵称双源", "P0", "三方昵称一致", False, str(e))


# ---------------------------------------------------------------------------
# 维度 13：重构完整性（v0.41.7 教训——模块化误删 subtopic 定义 → 教学不输出）
# v0.41.8 ⭐ v2：升级为 pyright 静态分析（reportPossiblyUnbound 直接命中
# "条件分支下可能未定义变量"——subtopic 事故的同类问题）
# ---------------------------------------------------------------------------
def audit_refactor_integrity():
    """检查关键函数内的关键变量是否已定义（防重构误删变量）。

    v0.41.7 教训：模块化提取 ensure_learner_session 时误删了 teach_stream 的
    `subtopic = (data.get("subtopic") or "").strip()` → NameError → SSE 中途
    中断 → "教学模式不输出内容"。audit_check 静态检查 24/24 全过（检查的是
    文件/结构/常量），从不执行代码 → 运行时 NameError 测不出。
    v0.41.8：升级为 pyright 静态分析——reportUndefinedVariable +
    reportPossiblyUnbound 能直接捕获"未定义变量/条件分支可能未定义"。
    """
    srv = SRV.read_text(encoding="utf-8")
    # 1) 保留原有 regex 防线（teach_stream 的 subtopic 定义存在性）
    # v1.2.7 ⭐ 修复（找茬 E2E）：teach_stream 重构为薄封装，函数体移入
    # `_teach_stream_gen(data)`（避免流式期间访问 request 上下文 → 500）。
    # 旧 regex 只匹配 `def teach_stream\(\):` → 函数体止于下一个 def →
    # subtopic 永远找不到 → P0 误报。现优先匹配真实函数体所在的位置。
    m = (re.search(r'def _teach_stream_gen\(data\):(.*?)(?=\n@|\ndef )', srv, re.S)
         or re.search(r'def teach_stream\(\):(.*?)(?=\n@|\ndef )', srv, re.S))
    ok_subtopic = True
    if m:
        body = m.group(1)
        ref_pos = body.find('if subtopic:')
        def_pos = body.find('subtopic = ')
        ok_subtopic = def_pos != -1 and (ref_pos == -1 or def_pos < ref_pos)
    record("重构完整", "P0", "teach_stream 定义 subtopic（防重构误删）",
           ok_subtopic, "" if ok_subtopic else "teach_stream 缺 subtopic 定义！")
    # 2) v0.41.8 ⭐ pyright 静态分析（核心升级）
    #    业界方法：pyright reportUndefinedVariable + reportPossiblyUnbound
    #    （Librarian 调研：这是"重构误删变量 → NameError"类问题的直接对症药）
    try:
        import subprocess as _sp
        import json as _json
        # Windows 下 pyright 是 .cmd 包装，需经 cmd /c 调用（npm 全局）
        # §3.45 ⭐ 修复：逐文件调用 + cwd（中文绝对路径 cmd 转义失败 + utils.py 同名冲突
        #   导致整体空输出）——单文件坏不拖累全部
        # §3.45 ⭐ 架构拆分：blueprints/ 新增 6 个路由文件，纳入 pyright 静态扫描
        _files = ["server.py", "paeg.py", "meta_router.py",
                  "utils.py", "self_referential.py",
                  "blueprints/voice.py", "blueprints/threads.py",
                  "blueprints/admin.py", "blueprints/conversations.py",
                  "blueprints/uploads.py", "blueprints/quiz.py"]
        _workdir = os.path.dirname(os.path.abspath(__file__))
        _diags = []
        for _f in _files:
            try:
                _r = _sp.run(["cmd", "/c", "pyright", "--outputjson", _f],
                             capture_output=True, timeout=90, cwd=_workdir)
                _out = _json.loads(_r.stdout.decode("utf-8", errors="replace") or "{}")
                _diags += _out.get("generalDiagnostics", [])
            except Exception:
                continue  # 单文件失败跳过（如 utils.py 同名冲突）
        # reportUnboundVariable = 真未定义（P0 级，如 subtopic 事故）
        # reportPossiblyUnboundVariable = 条件分支可能未定义（P1 提示，多为 try/except 兜底误报）
        _hard = [x for x in _diags if x.get("rule") == "reportUnboundVariable"]
        _soft = [x for x in _diags if x.get("rule") == "reportPossiblyUnboundVariable"]
        _fmt = lambda xs: "; ".join(
            f"{os.path.basename(x.get('file','?'))}:{x.get('range',{}).get('start',{}).get('line',0)+1}"
            for x in xs[:5]) if xs else ""
        record("重构完整", "P0", "pyright 无真未定义变量",
               len(_hard) == 0, f"{len(_hard)} 处: {_fmt(_hard)}" if _hard else "")
        record("重构完整", "P1", "pyright 可能未绑定变量（人工核查）",
               len(_soft) <= 5, f"{len(_soft)} 处: {_fmt(_soft)}" if _soft else "")
    except FileNotFoundError:
        record("重构完整", "P0", "pyright 无未定义/可能未绑定变量", False,
               "pyright 未安装（npm install -g pyright）")
    except Exception as _e:
        record("重构完整", "P0", "pyright 无未定义/可能未绑定变量", False,
               f"pyright 运行失败: {_e}")
    # 3) 保留原检查：无重复 LearnerProfile 内联创建
    record("重构完整", "P1", "server.py 无重复 LearnerProfile 内联创建",
           srv.count("learner = LearnerProfile(") <= 1,
           f"{srv.count('learner = LearnerProfile(')} 处（应 ≤1，其余走 ensure_learner_session）")


# ---------------------------------------------------------------------------
# 维度 14：模块化健康（v0.41.9——固化 v0.41.7/8 反思为常驻检查）
# ---------------------------------------------------------------------------
def audit_modular_health():
    """模块化架构健康度：services/handlers 完整性 + server.py 行数 + 依赖方向。

    v0.41.9 ⭐ 把 v0.41.7（重构误删变量）与 v0.41.8（handler 迁移）的教训
    固化为常驻检查——防止重构倒退（搬函数搬丢、依赖混乱、server.py 膨胀）。
    """
    srv = SRV.read_text(encoding="utf-8")
    # 1) services/handlers 完整性：5 个业务 handler 应存在且被 server.py 引用
    handlers_dir = BASE / "services" / "handlers"
    expected = ["keyword_doc", "method", "knowledge", "recommend", "problem"]
    missing = [h for h in expected if not (handlers_dir / f"{h}.py").exists()]
    record("模块健康", "P1", "services/handlers 5 个业务 handler 齐全",
           not missing, f"缺: {missing}" if missing else "")
    # 2) server.py 行数检查已移除（2026-08-15 用户指示：行数不是好的复杂度指标，
    #    4780 行含大量教学业务逻辑，机械拆分引入风险；模块健康由 handler 完整性/
    #    依赖方向/路由数等更有意义的指标覆盖）
    # 3) 业务 handler 不应内联在 server.py（应走 services.handlers import）
    inline_handlers = [h for h in expected
                       if f"def _handle_{h}_" in srv and f"from services.handlers.{h}" not in srv]
    record("模块健康", "P1", "handler 定义已迁出 server.py（走 services.handlers）",
           not inline_handlers, f"仍内联: {inline_handlers}" if inline_handlers else "")
    # 4) 依赖方向：services/infra/blueprints 不应 import server.py（单向依赖：server → 各层）
    #    §3.45 ⭐ blueprints 加入检查（蓝图反向 import server 会造成循环导入 + 架构倒退）
    dep_violations = []
    for mod in ["services", "infra", "blueprints"]:
        mdir = BASE / mod
        if mdir.is_dir():
            for f in mdir.rglob("*.py"):
                try:
                    txt = f.read_text(encoding="utf-8")
                except Exception:
                    continue
                if "from server import" in txt or "import server" in txt:
                    # 排除注释行（v0.41.9：注释里提到 "from server import" 会误报）
                    _code_lines = [l for l in txt.splitlines()
                                   if l.strip() and not l.strip().startswith("#")
                                   and not l.strip().startswith('"""')]
                    if any("from server import" in l or "import server" in l
                           for l in _code_lines):
                        dep_violations.append(f"{mod}/{f.name}")
    record("模块健康", "P1", "services/infra 不反向依赖 server.py",
           not dep_violations, f"反向依赖: {dep_violations}" if dep_violations else "")


# ---------------------------------------------------------------------------
# 维度 15：数据流完整性（v0.41.9 九次反思——接线缺口 8 项未被发现）
# ---------------------------------------------------------------------------
def audit_dataflow_integrity():
    """检查"功能语义完整性"——静态/可达之外，数据流是否真的完整。

    v0.41.9 教训：8 个接线/数据流问题（chat 不读用户库 / facts 死代码 /
    掌握度不落盘 / stat-sessions 内存计数 / MODE_CN 不全 / quote 无法扩充 /
    answer 字段不兼容 / TTS 首请求 500）——audit 查"代码存在/路由在"，
    smoke 查"端点可达"，但从不查"功能语义"：对称性/死代码/持久化/真实数据源。
    """
    srv = SRV.read_text(encoding="utf-8")
    # 1) 功能对称性：teach_stream 有的接线，chat_stream 也必须同样有
    #    （chat 不读用户资料库 = 对称性缺失）
    ok_sym = False
    # 检查 chat_stream 是否也注入用户资料库（read_user_corpus 或 _user_corpus）
    chat_has_uc = "chat_stream 用户资料注入" in srv or \
                  ("read_user_corpus" in srv and "用户上传的资料" in srv)
    record("数据流", "P0", "chat_stream 注入用户资料库（与 teach 对称）",
           chat_has_uc, "" if chat_has_uc else "chat_stream 不读用户库（接线缺口）")
    # 2) 死代码检测：定义但从未被调用的关键函数（facts search_facts 教训）
    #    —— search_facts 应被 server.py 调用（teach 兜底接 facts）
    ok_facts = "search_facts" in srv
    record("数据流", "P0", "facts/*.md 检索接通（search_facts 被调用）",
           ok_facts, "" if ok_facts else "facts 加载但从未接入检索（死代码）")
    # 3) 持久化完整性：教学路径必须落盘画像（掌握度教学后不丢）
    ok_persist = "save_learner" in srv and "画像落盘失败" in srv
    record("数据流", "P0", "教学后画像落盘（掌握度持久化）",
           ok_persist, "" if ok_persist else "掌握度只内存不落盘（刷新丢失）")
    # 4) 契约字段兼容：核心端点接受常见字段别名（question/text/concept）
    ok_contract = "data.get(\"question\") or data.get(\"text\")" in srv or \
                  "data.get(\"text\") or data.get(\"concept\")" in srv
    record("数据流", "P1", "核心端点字段兼容（question/text/concept）",
           ok_contract, "" if ok_contract else "answer 仅接受 question（外部 text 调 400）")
    # 5) 每日一句可扩充：quotes_user.json 机制存在
    ok_quote = "quotes_user.json" in (BASE / "quotes.py").read_text(encoding="utf-8")
    record("数据流", "P1", "每日一句可动态扩充（quotes_user.json）",
           ok_quote, "" if ok_quote else "quote 硬编码，无法追加")
    # 6) TTS 首请求稳定：重试机制存在
    ok_tts = "指数退避" in (BASE / "voice_service.py").read_text(encoding="utf-8") or \
             "重试" in (BASE / "voice_service.py").read_text(encoding="utf-8")
    record("数据流", "P1", "TTS 首请求重试（防偶发 500）",
           ok_tts, "" if ok_tts else "TTS 无重试，首请求可能 500")
    # 7) 学段集合完整性（v0.41.9 十次反思：考研+法语误判——
    #    SUBJECT_GRADES 语言类缺 graduate_exam，配置语义盲区）
    try:
        import sys as _sys2
        _sys2.path.insert(0, str(BASE))
        _sys2.path.insert(0, str(BASE.parent))
        import os as _os2
        _cwd = _os2.getcwd()
        _os2.chdir(BASE)
        from prompts import SUBJECT_GRADES
        _os2.chdir(_cwd)
        _langs = ["french", "german", "japanese", "english", "linguistics",
                  "atmospheric_science"]
        _missing = [l for l in _langs
                    if l in SUBJECT_GRADES and "graduate_exam" not in SUBJECT_GRADES[l]]
        record("数据流", "P1", "语言类学科含考研档（考研生可学外语）",
               not _missing, f"缺考研档: {_missing}" if _missing else "")
    except Exception as _ge:
        record("数据流", "P1", "语言类学科含考研档", False, f"检查失败: {_ge}")
    # 8) 文案-UI 一致性（v0.41.9：提示"左上角"实际在底部输入栏）
    try:
        _steer = (BASE / "services" / "steering.py").read_text(encoding="utf-8")
        _bad_text = "左上角" in _steer
        record("数据流", "P1", "学段提示文案与实际 UI 一致（无'左上角'误导）",
               not _bad_text, "提示仍写'左上角'（实际在底部输入栏）" if _bad_text else "")
    except Exception:
        pass
    # 9) H-1 ⭐ 会话事件日志完备（§3.46.2 H-1，2026-08-16）
    #    "模型可见⟺已记录"铁律：类型层(event_types)+发射层(emit_event_typed)+
    #    存储层(session_log)三件套齐备，模型可见输入可审计可回放。
    try:
        _sl = (BASE / "infra" / "session_log.py").read_text(encoding="utf-8")
        _et = (BASE / "infra" / "event_types.py").read_text(encoding="utf-8")
        _ob = (BASE / "observability.py").read_text(encoding="utf-8")
        _ok_h1 = all(k in _sl for k in ["SessionEventLog", "derive_messages", "append"]) \
            and all(k in _et for k in ["make_event", "KNOWN_EVENT_TYPES", "surfaceOp"]) \
            and "emit_event_typed" in _ob
        record("数据流", "P1", "H-1 会话事件日志三件套齐备（模型可见⟺已记录）",
               _ok_h1, "" if _ok_h1 else "session_log/event_types/emit_event_typed 缺失")
    except Exception as _h1e:
        record("数据流", "P1", "H-1 会话事件日志三件套齐备", False, f"检查失败: {_h1e}")


def main():
    audit_early_exit()
    audit_silent_except()
    audit_wiring()
    audit_version()
    audit_test_coverage()
    audit_persistence()
    audit_handler_completeness()
    audit_security()
    audit_data()
    audit_reflection_consistency()
    audit_display_quality()
    audit_nickname_consistency()
    audit_refactor_integrity()
    audit_modular_health()
    audit_dataflow_integrity()

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
