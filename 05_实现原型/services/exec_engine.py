# -*- coding: utf-8 -*-
"""services/exec_engine.py —— §3.79 Round 12 ⭐ 受控子进程执行引擎（Codex Harness 借鉴 A8）

OpenAI 2026-08-21 开源 Codex Harness：`codex exec` 让 agent 以受控子进程执行代码，
主进程只做调度与校验。PAEG 借鉴：物料生产中重活（PPT 生成脚本/manim 渲染/批处理）
统一走本引擎——崩溃不拖垮主服务、超时可配、输出结构化。

与 manim_service 的关系：manim_service 已有专用子进程渲染（AST 校验+超时）；
本引擎是其通用化——任何"代码字符串 → 受控执行"场景复用。

安全设计（对齐 manim_service 既有防线 + Codex sandbox 思想）：
- 黑名单 import/call（恶意代码防执行）
- subprocess 隔离（主进程不受影响）
- 超时 + 输出截断（防资源耗尽）
- 工作目录隔离（临时目录，防污染）
"""
from __future__ import annotations

import ast
import os
import subprocess
import tempfile
import time
import uuid
from typing import Optional, Tuple

# 与 manim_service 对齐的代码安全黑名单
_BLOCKED_IMPORTS = {"os", "sys", "subprocess", "socket", "shutil", "ctypes",
                    "pickle", "multiprocessing", "threading", "importlib",
                    "pathlib", "http", "urllib", "requests", "ftplib",
                    "winreg", "cryptography"}
_BLOCKED_CALLS = {"eval", "exec", "__import__", "compile", "globals", "locals",
                  "open", "input", "exit", "quit", "breakpoint",
                  "os.system", "os.popen", "subprocess.run", "subprocess.Popen"}


def validate_code(code: str) -> Tuple[bool, str]:
    """AST 安全校验（恶意代码拦截）。返回 (ok, error)。"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"语法错误: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _root = alias.name.split(".")[0]
                if _root in _BLOCKED_IMPORTS:
                    return False, f"禁止 import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _BLOCKED_IMPORTS:
                return False, f"禁止 from-import: {node.module}"
        elif isinstance(node, ast.Call):
            _fn = node.func
            if isinstance(_fn, ast.Name) and _fn.id in _BLOCKED_CALLS:
                return False, f"禁止调用: {_fn.id}"
            if isinstance(_fn, ast.Attribute):
                _full = f"{_fn.value.id}.{_fn.attr}" if isinstance(_fn.value, ast.Name) else ""
                if _full in _BLOCKED_CALLS:
                    return False, f"禁止调用: {_full}"
    return True, ""


def exec_code(code: str, language: str = "python",
              timeout: float = 60.0, max_output: int = 4000,
              argv: Optional[list] = None) -> dict:
    """受控子进程执行代码（Codex exec 模式）。

    Args:
        code: 要执行的代码（python 直接跑；shell 走系统解释器）
        language: python / shell
        timeout: 超时秒数
        max_output: 输出截断长度
        argv: 附加参数（如 manim render 的 scene 类名）

    Returns:
        {"ok", "stdout", "stderr", "returncode", "elapsed", "error"}
    """
    _t0 = time.time()
    if language == "python":
        ok, err = validate_code(code)
        if not ok:
            return {"ok": False, "stdout": "", "stderr": err,
                    "returncode": -1, "elapsed": 0, "error": err}
    _tmpdir = tempfile.mkdtemp(prefix="paeg_exec_")
    try:
        if language == "python":
            _file = os.path.join(_tmpdir, "job.py")
            with open(_file, "w", encoding="utf-8") as f:
                f.write(code)
            _cmd = [sys_executable(), _file] + (argv or [])
        elif language == "shell":
            _cmd = ["cmd", "/c", code] if os.name == "nt" else ["sh", "-c", code]
        else:
            return {"ok": False, "stdout": "", "stderr": f"未知语言: {language}",
                    "returncode": -1, "elapsed": 0, "error": f"未知语言: {language}"}
        try:
            result = subprocess.run(_cmd, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace",
                                    cwd=_tmpdir, timeout=timeout, shell=False)
        except UnicodeDecodeError:
            result = subprocess.run(_cmd, capture_output=True, cwd=_tmpdir,
                                    timeout=timeout, shell=False)
            result.stdout = (result.stdout or b"").decode("utf-8", errors="replace")
            result.stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        _out = (result.stdout or "")[:max_output]
        _err = (result.stderr or "")[:max_output]
        return {"ok": result.returncode == 0, "stdout": _out, "stderr": _err,
                "returncode": result.returncode,
                "elapsed": round(time.time() - _t0, 3),
                "error": "" if result.returncode == 0 else _err[-500:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"执行超时（{timeout}s）",
                "returncode": -1, "elapsed": round(time.time() - _t0, 3),
                "error": f"执行超时（{timeout}s）"}
    except FileNotFoundError as e:
        return {"ok": False, "stdout": "", "stderr": f"解释器缺失: {e}",
                "returncode": -1, "elapsed": round(time.time() - _t0, 3),
                "error": f"解释器缺失: {e}"}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e),
                "returncode": -1, "elapsed": round(time.time() - _t0, 3),
                "error": str(e)}
    finally:
        # 清理临时目录（防磁盘堆积；保留以排查时可注释）
        try:
            import shutil as _sh
            _sh.rmtree(_tmpdir, ignore_errors=True)
        except Exception:
            pass


def sys_executable() -> str:
    """当前 Python 解释器路径（子进程执行用同一解释器，保证依赖可见）。"""
    import sys as _sys
    return _sys.executable


__all__ = ["validate_code", "exec_code", "sys_executable"]
