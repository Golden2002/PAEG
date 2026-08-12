# -*- coding: utf-8 -*-
"""v6.1 ⭐ Manim 数学动画服务（独立模块）
LLM 生成 Manim 代码 → 隔离渲染 → 数学动画视频
- 独立于 video_service.py（不互相依赖）
- 渲染用隔离 venv（manim_env/venv，Python 3.12）
- AST 校验防恶意代码 + subprocess 超时
"""
import os, re, ast, subprocess, tempfile, uuid, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 隔离环境路径（可移植：相对项目根）
_BASE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_BASE)
_MANIM_ENV = os.path.join(_PROJ, 'manim_env', 'venv', 'Scripts')
_MANIM_PY = os.path.join(_MANIM_ENV, 'python.exe')
_MANIM_CLI = os.path.join(_MANIM_ENV, 'manim.exe')
_MEDIA_DIR = os.path.join(_PROJ, 'downloads', 'manim')

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


def render_manim(code: str, scene_class: str = None, quality: str = '-qm',
                 timeout: int = 180):
    """渲染 Manim 代码 → mp4 路径。返回 (path, error)"""
    os.makedirs(_MEDIA_DIR, exist_ok=True)
    job_id = str(uuid.uuid4())[:8]
    temp_dir = os.path.join(_MEDIA_DIR, 'jobs', job_id)
    os.makedirs(temp_dir, exist_ok=True)
    try:
        code_file = os.path.join(temp_dir, 'scene.py')
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        # 找 Scene 类名
        if not scene_class:
            m = re.search(r'class\s+(\w+)\s*\(', code)
            scene_class = m.group(1) if m else 'Scene'
        cmd = [_MANIM_CLI, 'render', quality, '--media_dir', temp_dir,
               code_file, scene_class]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                cwd=temp_dir, timeout=timeout, shell=False)
        if result.returncode != 0:
            return None, result.stderr[-500:]
        # 定位输出
        for q in ('480p15', '720p30', '1080p60'):
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
4. 总时长 90-150 秒（v0.63.1 ⭐ 教学慢速：run_time 不得低于 3s，wait 不得低于 2s，
   每个元素单独 Create（不并行），创建后 wait 观察，标题展示后停留 3s，结尾停留 4s）
5. 纯几何动画（不用 Text/MathTex 避免依赖问题）
6. 输出完整可运行 Python 代码"""


def generate_manim_video(topic: str, subject: str = 'math',
                         learner_id: str = 'anon') -> dict:
    """LLM 生成 Manim 代码 → 渲染视频。返回 {ok, path, url, error}

    v0.63 ⭐ 意图层：match_manim_intent 把简单话（"画个抛物线"）映射为
    场景专属 prompt（含教学叙事）+ 对应模板 key，LLM 按精确指令生成。
    """
    # v0.63 ⭐ 意图匹配：简单话 → 场景 prompt + 模板 key
    intent = None
    try:
        from manim_prompts import match_manim_intent
        intent = match_manim_intent(topic)
    except Exception:
        intent = None
    _scene_prompt = (intent or {}).get("prompt", "")
    _template_key = (intent or {}).get("template_key", "")

    # 1. LLM 生成代码（场景 prompt 优先；失败用通用）
    code = None
    try:
        from subagents import _safe_chat
        _sys = _MANIM_SYSTEM
        if _scene_prompt:
            _sys = _sys + "\n\n## 本次动画要求（场景专属）\n" + _scene_prompt
        code = _safe_chat(_sys, f"教学问题：{topic}\n学科：{subject}\n生成 Manim 动画代码")
    except Exception as e:
        code = None
        last_err = f"LLM 调用失败: {e}"

    # LLM 失败则用模板兜底（按意图 key 选择，非通用）
    if not code or 'class ' not in code:
        from manim_templates import template_for, template_by_key
        code = template_by_key(_template_key, topic) if _template_key else template_for(topic, subject)

    # 2. AST 校验
    ok, err = validate_manim_code(code)
    if not ok:
        return {"ok": False, "path": "", "url": "", "error": f"校验失败: {err}"}

    # 3. 渲染
    path, rerr = render_manim(code)
    if not path:
        return {"ok": False, "path": "", "url": "", "error": f"渲染失败: {rerr}"}

    return {"ok": True, "path": path, "url": f"/api/download/manim/{os.path.basename(path)}",
            "error": ""}


if __name__ == '__main__':
    # 测试：模板渲染（不依赖 LLM）
    from manim_templates import template_for
    code = template_for('导数', 'math')
    print("模板代码生成 OK, 长度:", len(code))
    ok, err = validate_manim_code(code)
    print("校验:", "OK" if ok else err)
    path, rerr = render_manim(code)
    print("渲染:", path or rerr)
