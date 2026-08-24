# -*- coding: utf-8 -*-
"""v6.1 ⭐ Manim 数学动画服务（独立模块）
LLM 生成 Manim 代码 → 隔离渲染 → 数学动画视频
- 独立于 video_service.py（不互相依赖）
- 渲染用隔离 venv（manim_env/venv，Python 3.12）
- AST 校验防恶意代码 + subprocess 超时
"""
import os, re, ast, subprocess, tempfile, uuid, sys, io

# §3.97 ⭐ LaTeX 可用性检测：manim MathTex/Tex 依赖 latex.exe，缺失时降级
_MIKTEX_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manim_env", "miktex",
                          "texmfs", "install", "miktex", "bin", "x64")


def _latex_available() -> bool:
    """检测 LaTeX 可用性：系统 PATH 或 MiKTeX 安装路径。"""
    try:
        import shutil as _sh
        if _sh.which("latex") is not None or _sh.which("latex.exe") is not None:
            return True
        # MiKTeX 便携安装
        if os.path.isfile(os.path.join(_MIKTEX_BIN, "latex.exe")):
            return True
    except Exception:
        pass
    return False


_LATEX_OK = _latex_available()

# v0.69+：stdout 包装移入 __main__——模块级替换会破坏 pytest capsys（import 时副作用）
if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from manim_speed import _SPEED_STANDARD_TEXT  # v0.64 ⭐ 速度规范固定化

# 隔离环境路径（可移植：相对项目根）
_BASE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_BASE)
_MANIM_ENV = os.path.join(_PROJ, 'manim_env', 'venv', 'Scripts')
_MANIM_PY = os.path.join(_MANIM_ENV, 'python.exe')
_MANIM_CLI = os.path.join(_MANIM_ENV, 'manim.exe')
_MEDIA_DIR = os.path.join(_PROJ, 'downloads', 'manim')

# v0.67 ⭐ Docker 兼容：容器内统一 Python 3.12（pip manim），无 manim_env/venv
# 检测 Windows venv 不存在 → 用系统 manim 命令（Linux 容器：shutil.which('manim')）
if not os.path.exists(_MANIM_CLI):
    import shutil as _shutil
    _SYS_MANIM = _shutil.which('manim')
    if _SYS_MANIM:
        _MANIM_CLI = _SYS_MANIM
        _MANIM_PY = _SYS_MANIM

# 安全校验：禁用的 import / 调用
_BLOCKED_IMPORTS = {'os', 'sys', 'subprocess', 'socket', 'shutil', 'ctypes',
                    'multiprocessing', 'signal', 'importlib', 'pathlib', 'requests'}
_BLOCKED_CALLS = {'eval', 'exec', '__import__', 'compile', 'globals', 'locals',
                  'open', 'getattr', 'setattr', 'delattr'}

# v1.0 ⭐ 学科门控：仅"可视化类"学科插入 manim 动画。
# 数学/物理/几何等有图形语义；语文/历史/英语等纯文本学科不插（走纯讲解视频）。
_MANIM_SUBJECTS = {
    'math', 'mathematics', '物理', 'physics', '数学',
    '几何', 'geometry', '代数', 'algebra', '化学', 'chemistry',
    '函数', '微积分', 'calculus', '统计', 'statistics', '概率', 'probability',
    '线性代数', 'linear_algebra', '解析几何', 'graph', '图论',
}


def is_manim_subject(subject: str) -> bool:
    """主题类型分派：该学科是否适合插入 manim 演示动画。

    用户需求（v1.0）：除数学讲解视频外，其他讲解视频不需要往视频中插入
    manim 渲染动画——融合管线按学科类型决定是否渲染/插入 manim 片段。
    """
    if not subject:
        return False
    s = str(subject).strip().lower()
    if s in {x.lower() for x in _MANIM_SUBJECTS}:
        return True
    # 包含匹配：如 "高中数学" → math
    return any(k.lower() in s for k in _MANIM_SUBJECTS)


# v0.66 ⭐ 主题内容推断：不依赖用户显式选学科，从主题关键词判断是否适合 manim
# 可视化主题关键词（数学/物理/几何图形语义）
_MANIM_TOPIC_KEYWORDS = (
    # 数学核心概念
    '行列式', '矩阵', '特征值', '特征向量', '导数', '积分', '极限', '微积分',
    '函数', '抛物线', '正弦', '余弦', '三角函数', '向量', '几何', '面积',
    '方程', '线性代数', '概率', '统计', '分布', '曲线', '图像', '图形',
    '斜率', '切线', '圆周率', '圆', '三角形', '多边形', '对称',
    # 物理可视化
    '力', '速度', '加速度', '运动', '波形', '电场', '磁场', '光学', '振动',
    '机械波', '电磁', '轨迹', '场', '能量', '动能', '势能',
    # 化学
    '分子结构', '晶体', '化学键', '反应速率', '轨道',
    # 英文
    'determinant', 'matrix', 'eigenvalue', 'eigenvector', 'derivative',
    'integral', 'limit', 'function', 'sine', 'cosine', 'vector', 'geometry',
    'area', 'probability', 'statistics', 'graph', 'curve', 'slope', 'tangent',
    'circle', 'triangle', 'polygon', 'velocity', 'acceleration', 'wave',
)


def infer_manim_suitability(topic: str, subject: str = "") -> bool:
    """v0.66 ⭐ 判断主题是否适合 manim 动画（显式学科 + 主题内容推断取并集）。

    修复：用户不选学科（subject=''）时，仅凭主题关键词（如"行列式"）也能
    识别为可视化主题并插入 manim 动画。
    """
    if is_manim_subject(subject):
        return True
    t = (topic or "").lower()
    return any(k in t for k in _MANIM_TOPIC_KEYWORDS)


def validate_manim_code(code: str):
    """AST 校验：拒绝危险 import/调用，必须有 Scene 子类 + construct"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    has_scene = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split('.')[0] in _BLOCKED_IMPORTS:
                    return False, f"Blocked import: {a.name}"
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split('.')[0] in _BLOCKED_IMPORTS:
                return False, f"Blocked import: {node.module}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _BLOCKED_CALLS:
                return False, f"Blocked call: {node.func.id}"
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in ('Scene', 'ThreeDScene'):
                    has_scene = True
                    has_construct = any(isinstance(i, ast.FunctionDef) and i.name == 'construct'
                                        for i in node.body)
                    if not has_construct:
                        return False, f"Scene missing construct()"
    if not has_scene:
        return False, "No Scene class found"
    return True, ""


def _sanitize_code_no_latex(code: str) -> str:
    """§3.97 ⭐ 代码清洗：MathTex/Tex → Text 降级 + 全角标点转半角 + LaTeX 残留剥离。

    - 无 LaTeX：MathTex/Tex → Text（避免 latex.exe FileNotFound）
    - 全角标点（U+FF0C/U+FF1A 等）在 Python 代码中导致 SyntaxError → 转半角
    - LaTeX 残留 $ 符号（LLM 常混入数学记号）剥离
    """
    if not code:
        return code
    _orig = code
    # 1) MathTex/Tex → Text（无 LaTeX 时降级）
    if not _LATEX_OK:
        code = code.replace("MathTex(", "Text(").replace("Tex(", "Text(")
    # 2) 全角标点 → 半角（保留语法结构）
    _F2H = {"，": ",", "；": ";", "：": ":", "（": "(", "）": ")",
            "！": "!", "？": "?", "“": chr(34), "”": chr(34), "‘": chr(39), "’": chr(39)}
    code = "".join(_F2H.get(_ch, _ch) for _ch in code)
    # 3) 剥离 LaTeX $ 符号残留
    code = code.replace("$", "")
    if code != _orig:
        print("[manim_service] 代码清洗：MathTex/全角标点/LaTeX 残留已处理")
    return code

def render_manim(code: str, scene_class: str = None, quality: str = '-qm',
                 timeout: int = 180):
    """渲染 Manim 代码 → mp4 路径。返回 (path, error)"""
    os.makedirs(_MEDIA_DIR, exist_ok=True)
    job_id = str(uuid.uuid4())[:8]
    temp_dir = os.path.join(_MEDIA_DIR, 'jobs', job_id)
    os.makedirs(temp_dir, exist_ok=True)
    try:
        # §3.97 ⭐ 无 LaTeX 环境降级
        code = _sanitize_code_no_latex(code)
        code_file = os.path.join(temp_dir, 'scene.py')
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        # 找 Scene 类名
        if not scene_class:
            m = re.search(r'class\s+(\w+)\s*\(', code)
            scene_class = m.group(1) if m else 'Scene'
        cmd = [_MANIM_CLI, 'render', quality, '--media_dir', temp_dir,
               code_file, scene_class]
        # §3.79 Round 4 ⭐ 运维修复：Windows 下 manim 输出含 UTF-8 中文/转义码，
        # 默认 GBK 解码会 UnicodeDecodeError → 指定 utf-8（errors=replace 兜底），
        # 并禁用 text 模式的 locale 猜测（encoding='utf-8' 显式传入）
        # §3.97 ⭐ 注入 ffmpeg + LaTeX PATH：manim 需要 ffmpeg（视频）与 latex（公式）
        _env = dict(os.environ)
        # MiKTeX LaTeX bin 注入（MathTex 数学公式渲染）
        if os.path.isdir(_MIKTEX_BIN) and _MIKTEX_BIN not in _env.get("PATH", ""):
            _env["PATH"] = _MIKTEX_BIN + os.pathsep + _env.get("PATH", "")
            print(f"[manim_service] LaTeX PATH 注入: {_MIKTEX_BIN}")
        try:
            # §3.97 修复：优先 manim_env 内 ffmpeg（系统 PATH 无），次选 imageio_ffmpeg
            _ff = ""
            _manim_ff = os.path.join(_BASE, "..", "manim_env", "venv",
                                     "Lib", "site-packages", "imageio_ffmpeg",
                                     "binaries", "ffmpeg-win-x86_64-v7.1.exe")
            if os.path.isfile(_manim_ff):
                _ff = _manim_ff
            else:
                import imageio_ffmpeg as _iif
                _ff = _iif.get_ffmpeg_exe()
            _ff_dir = os.path.dirname(_ff)
            if _ff_dir and _ff_dir not in _env.get("PATH", ""):
                _env["PATH"] = _ff_dir + os.pathsep + _env.get("PATH", "")
                print(f"[manim_service] ffmpeg PATH 注入: {_ff_dir}")
        except Exception:
            pass
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='replace',
                                    cwd=temp_dir, timeout=timeout, shell=False,
                                    env=_env)
        except UnicodeDecodeError:
            # 极老 Python 不支持 encoding 参数：降级 bytes 手动解码
            result = subprocess.run(cmd, capture_output=True,
                                    cwd=temp_dir, timeout=timeout, shell=False)
            result.stdout = result.stdout.decode('utf-8', errors='replace')
            result.stderr = result.stderr.decode('utf-8', errors='replace')
        if result.returncode != 0:
            return None, result.stderr[-500:]
        # 定位输出：-qml/-ql/-qm/-qh/-qk 对应 480p15/720p30/1080p60/1440p60/2160p60
        for q in ('480p15', '720p30', '1080p60', '1440p60', '2160p60'):
            cand = os.path.join(temp_dir, 'videos', os.path.basename(code_file).replace('.py', ''),
                                q, f'{scene_class}.mp4')
            if os.path.exists(cand):
                return cand, None
        return None, "Video file not found"
    except subprocess.TimeoutExpired:
        return None, f"Render timed out ({timeout}s)"
    except FileNotFoundError:
        return None, "Manim not found - check manim_env installation"
    except Exception as e:
        return None, str(e)


# ─── LLM 生成 Manim 代码（接入现有 LLM）───
_MANIM_SYSTEM = """你是 Manim 数学动画代码生成助手。为教学问题生成 Manim Community 代码。
要求：
1. from manim import *
2. Scene 类实现 construct(self)
3. 数学曲线用 axes.plot()，几何用 Circle/Square 等
4. 总时长 60-100 秒
5. 纯几何动画（不用 Text/MathTex 避免依赖问题）
6. 输出完整可运行 Python 代码""" + _SPEED_STANDARD_TEXT


def _get_llm_for_manim():
    """获取 LLM 实例（供流水线使用）。"""
    try:
        from llm_adapter import create_llm
        return create_llm("auto")
    except Exception:
        return None


def generate_manim_video(topic: str, subject: str = 'math',
                         learner_id: str = 'anon',
                         llm=None, grade: str = "high_school",
                         intuition: str = "", objectives: str = "",
                         prerequisites: str = "", style: str = "3blue1brown",
                         duration_target_sec: int = 120,
                         job_id: str = "", progress_callback=None,
                         user_requirements: str = "") -> dict:
    """LLM 生成 Manim 代码 → 渲染视频。返回 {ok, path, url, error}

    §3.94 ⭐ 分阶段联通（Oracle 方案）：
    - intuition/objectives/prerequisites/style/duration：用户要求透传 phase1_plan
    - user_requirements：用户详细要求（拼进 intuition）
    - job_id/progress_callback：阶段进度 + 产物落盘
    """
    # 接受 caller llm，无则新建（兼容旧调用）
    _llm = llm or _get_llm_for_manim()
    # 学段中文化（注入 audience）
    _grade_cn = {"middle_school": "初中", "high_school": "高中",
                 "undergraduate": "大学", "graduate_exam": "考研"}.get(grade, "高中")
    # v1.1 ⭐ 优先：script.json 流水线（若存在规划产物）
    try:
        from manim_pipeline import run_pipeline
        # 尝试用现有流水线（含 Phase1 规划→门控→草稿→实现→修复）
        _r = run_pipeline(
            llm=_llm,
            topic=topic, audience=_grade_cn, duration_target_sec=duration_target_sec,
            style=style, prerequisites=prerequisites,
            intuition=intuition, objectives=objectives,
            job_id=job_id, progress_callback=progress_callback,
            user_requirements=user_requirements)
        if _r.get("ok"):
            return {"ok": True, "path": _r.get("video_path", ""),
                    "url": _r.get("url", ""), "error": "",
                    "pipeline": "multi-stage",
                    "job_id": _r.get("job_id", ""),
                    "artifacts": _r.get("artifacts", {}),
                    "stages": _r.get("stages", {})}
        # 流水线未 ok 但仍产出脚本/代码 → 返回部分产物（供 UI 展示/下载）
        if _r.get("artifacts"):
            return {"ok": False, "path": _r.get("video_path", ""),
                    "url": _r.get("url", ""),
                    "error": "; ".join(_r.get("errors", ["渲染失败"])),
                    "pipeline": "multi-stage",
                    "job_id": _r.get("job_id", ""),
                    "artifacts": _r.get("artifacts", {}),
                    "stages": _r.get("stages", {})}
    except Exception as _pe:
        print(f"[manim_service] 流水线尝试失败（回退单段）: {_pe}")
    # v0.63 ⭐ 意图匹配：简单话 → 场景 prompt + 模板 key
    intent = None
    try:
        from manim_prompts import match_manim_intent
        intent = match_manim_intent(topic)
    except Exception:
        intent = None
    _scene_prompt = (intent or {}).get("prompt", "")
    _template_key = (intent or {}).get("template_key", "")

    # 1. LLM 生成代码（场景 prompt 优先；失败用通用）——v0.66 重试 2 次防 API 波动
    code = None
    try:
        from subagents import _safe_chat
        _sys = _MANIM_SYSTEM
        # v0.66 ⭐ 统一资源门面：注入 KB/用户物料/网络检索（动画主题有事实依据）
        # §3.92 修复：llm 传 _llm（此前误传 _safe_chat 函数）
        try:
            from services.library import collect_all_resources
            _res = collect_all_resources(learner_id, topic, llm=_llm,
                                         subject=subject, include_web=False)
            if _res.get("has_any"):
                _sys += "\n\n## 可用资源（动画应基于这些事实）\n" + _res["block"]
        except Exception:
            pass
        if _scene_prompt:
            _sys = _sys + "\n\n## 本次动画要求（场景专属）\n" + _scene_prompt
        for _attempt in range(3):
            # §3.92 修复：_safe_chat 必须传 llm（此前缺参静默失败→走模板）
            code = _safe_chat(_llm, _sys,
                              f"教学问题：{topic}\n学科：{subject}\n生成 Manim 动画代码",
                              max_tokens=4000)
            if code and 'class ' in code:
                break
            import time as _t
            _t.sleep(1.0)
    except Exception as e:
        code = None
        last_err = f"LLM 调用失败: {e}"

    # LLM 失败则用模板兜底（按意图 key 选择，非通用）
    if not code or 'class ' not in code:
        from manim_templates import template_for, template_by_key
        code = template_by_key(_template_key, topic) if _template_key else template_for(topic, subject)

    # §3.92 ⭐ 代码清洗：LLM 输出可能含 markdown 代码块/LaTeX $/说明文字——剥离后 AST 校验
    if code:
        _orig = code
        # 1) 剥离 ```python ... ``` / ``` ... ``` 代码块外壳
        _m = re.search(r"```(?:python)?\s*\n(.*?)```", code, re.S)
        if _m:
            code = _m.group(1)
        # 2) 剥离 LaTeX $ 符号（LLM 误用数学记号）
        code = code.replace("$", "")
        # 3) 剥离首尾说明文字（无 class 定义的行）
        _lines = [ln for ln in code.split("\n")]
        # 找第一个含 "class " 或 "from manim" 或 "import" 的行作为起点
        _start = 0
        for _i, _ln in enumerate(_lines):
            if "class " in _ln or "from manim" in _ln or _ln.strip().startswith("import "):
                _start = _i
                break
        code = "\n".join(_lines[_start:])

    # 2. AST 校验
    ok, err = validate_manim_code(code)
    if not ok:
        return {"ok": False, "path": "", "url": "", "error": f"校验失败: {err}"}

    # 3. 渲染
    path, rerr = render_manim(code)
    # §3.97 ⭐ 渲染失败（如 LLM 代码 NameError/API 不兼容）→ 模板代码兜底重试
    if not path:
        try:
            from manim_templates import template_for, template_by_key
            _tpl = template_by_key(_template_key, topic) if _template_key else template_for(topic, subject)
            if _tpl and _tpl != code:
                print(f"[manim_service] LLM 代码渲染失败({rerr[:60]}) → 模板兜底重试")
                path2, rerr2 = render_manim(_tpl)
                if path2:
                    code = _tpl
                    path = path2
                    rerr = rerr2
        except Exception:
            pass
    if not path:
        return {"ok": False, "path": "", "url": "", "error": f"渲染失败: {rerr}"}

    # v0.66 ⭐ 修复：URL 需含 jobs/<job>/videos/scene/<q>/ 完整路径（否则下载 404）
    try:
        _rel = os.path.relpath(path, _MEDIA_DIR).replace('\\', '/')
        _url = f"/api/download/manim/{_rel}"
    except Exception:
        _url = f"/api/download/manim/{os.path.basename(path)}"

    # §3.81 P2-② ⭐ Manim 教学叙事复核（LLM 评审动画是否表达概念；降级不阻塞）
    # §3.92 修复：传 llm（此前缺参 → dims 永远空，评审是装饰）
    _narr = {"checked": False}
    try:
        if os.environ.get("PAEG_NO_MANIM_JUDGE") != "1":
            from services.manim_judge import judge_manim_narrative
            _narr = judge_manim_narrative(topic, subject, code, path, llm=_llm)
    except Exception as _nj_e:
        print(f"[manim_service] 动画叙事复核跳过: {_nj_e}")

    return {"ok": True, "path": path, "url": _url,
            "error": "", "narrative_judge": _narr}


if __name__ == '__main__':
    # 测试：模板渲染（不依赖 LLM）
    from manim_templates import template_for
    code = template_for('导数', 'math')
    print("模板代码生成 OK, 长度:", len(code))
    ok, err = validate_manim_code(code)
    print("校验:", "OK" if ok else err)
    path, rerr = render_manim(code)
    print("渲染:", path or rerr)
