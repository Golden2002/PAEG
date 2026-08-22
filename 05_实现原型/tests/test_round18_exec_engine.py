# -*- coding: utf-8 -*-
"""Round 12 ⭐ 受控子进程执行引擎测试（test_round18_exec_engine.py）。

Codex Harness 借鉴（A8）：物料生产重活下沉受控子进程。
守护：
1. 合法代码正常执行并返回 stdout
2. 恶意 import（os/subprocess）被 AST 拦截
3. 恶意调用（eval/open）被拦截
4. 语法错误被拦截
5. 超时防护（死循环代码超时中止）
6. 输出截断
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.exec_engine import exec_code, validate_code


class TestValidateCode:
    def test_valid_code_ok(self):
        ok, err = validate_code("print('hello')")
        assert ok, err

    def test_blocked_import_os(self):
        ok, err = validate_code("import os\nos.system('rm -rf /')")
        assert not ok
        assert "禁止" in err

    def test_blocked_import_subprocess(self):
        ok, err = validate_code("import subprocess\nsubprocess.run(['echo', 'x'])")
        assert not ok
        assert "禁止" in err

    def test_blocked_eval_call(self):
        ok, err = validate_code("eval('1+1')")
        assert not ok

    def test_blocked_open(self):
        ok, err = validate_code("open('/etc/passwd')")
        assert not ok

    def test_syntax_error(self):
        ok, err = validate_code("def broken(:")
        assert not ok
        assert "语法错误" in err

    def test_benign_math_allowed(self):
        ok, _ = validate_code("import math\nprint(math.sqrt(16))")
        assert ok, "math 应允许"


class TestExecCode:
    def test_exec_python(self):
        r = exec_code("print('PAEG-EXEC-OK')", timeout=20)
        assert r["ok"], r
        assert "PAEG-EXEC-OK" in r["stdout"]
        assert r["returncode"] == 0

    def test_exec_malicious_blocked(self):
        r = exec_code("import os\nos.system('echo hacked')", timeout=20)
        assert not r["ok"]
        assert "禁止" in r["error"] or "禁止" in r["stderr"]

    def test_exec_timeout(self):
        r = exec_code("while True:\n    pass", timeout=3)
        assert not r["ok"]
        assert "超时" in r["error"] or "超时" in r["stderr"]

    def test_exec_output_truncated(self):
        r = exec_code("print('x' * 10000)", timeout=20, max_output=200)
        assert r["ok"]
        assert len(r["stdout"]) <= 200, "输出应被截断"

    def test_exec_syntax_error(self):
        r = exec_code("def broken(:", timeout=20)
        assert not r["ok"]
        assert "语法错误" in r["error"] or "语法错误" in r["stderr"]

    def test_exec_elapsed_reported(self):
        r = exec_code("print('t')", timeout=20)
        assert r["elapsed"] >= 0
