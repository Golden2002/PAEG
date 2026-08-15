# -*- coding: utf-8 -*-
"""services/condition_eval.py —— #4 !!js 条件启停（Harness 30 项 P1，§3.46.2，2026-08-16）

dsh Harness 借鉴（config `disabled: !!js expr`，commit 47f9438）：
条件启停配置化，不改代码调启停。

安全设计（关键）：
- 不引入真 JS 引擎（quickjs 重依赖 + AI 已可写 patch（#27）→ JS 求值=任意代码执行风险）
- 用 ast 白名单受限求值器：只允许布尔/比较/常量/成员访问/受限函数调用
- 拒绝：导入/属性链/下标/调用任意函数/复合语句/lambda——任何越界 → False（不抛异常）
- 白名单函数：platform()/env('VAR')/module('id')（环境感知条件）

用法：
    from services.condition_eval import evaluate_condition
    evaluate_condition("module('weather') and platform() == 'win'")   # → bool
"""
from __future__ import annotations

import ast
import os
import sys
from typing import Any, Dict, Optional


# 白名单二元运算符（布尔 + 比较 + 算术基本）
_BIN_OPS = {
    ast.And: lambda a, b: bool(a) and bool(b),
    ast.Or: lambda a, b: bool(a) or bool(b),
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
}

# 白名单一元运算符
_UNARY_OPS = {
    ast.Not: lambda a: not bool(a),
    ast.USub: lambda a: -a,
}


class _SafeEvaluator(ast.NodeVisitor):
    """ast 白名单求值器：只允许安全节点，越界抛 ValueError。"""

    def __init__(self, ctx: Dict[str, Any]):
        self._ctx = ctx

    def visit_Expression(self, node):  # noqa: N802
        return self.visit(node.body)

    def visit_Constant(self, node):  # noqa: N802
        if isinstance(node.value, (bool, int, float, str)):
            return node.value
        raise ValueError(f"非法常量: {type(node.value).__name__}")

    def visit_Name(self, node):  # noqa: N802
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id in self._ctx:
            return self._ctx[node.id]
        raise ValueError(f"未知变量: {node.id}")

    def visit_Load(self, node):  # noqa: N802
        return None

    def visit_BoolOp(self, node):  # noqa: N802
        values = [self.visit(v) for v in node.values]
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError("非法布尔运算符")
        result = values[0]
        for v in values[1:]:
            result = op(result, v)
        return result

    def visit_BinOp(self, node):  # noqa: N802
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError("非法二元运算符")
        return op(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node):  # noqa: N802
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("非法一元运算符")
        return op(self.visit(node.operand))

    def visit_Compare(self, node):  # noqa: N802
        left = self.visit(node.left)
        for op, comp in zip(node.ops, node.comparators):
            fn = _BIN_OPS.get(type(op))
            if fn is None:
                raise ValueError("非法比较运算符")
            right = self.visit(comp)
            left = fn(left, right)
        return left

    # ─── 白名单函数调用（仅 platform/env/module） ───
    def visit_Call(self, node):  # noqa: N802
        fn = node.func
        if not isinstance(fn, ast.Name):
            raise ValueError("非法调用目标")
        name = fn.id
        args = [self.visit(a) for a in node.args]
        if any(kw.arg is not None for kw in node.keywords):
            raise ValueError("关键字参数不允许")
        if name == "platform":
            if len(args) != 0:
                raise ValueError("platform() 无参数")
            return "win" if sys.platform.startswith("win") else \
                ("mac" if sys.platform == "darwin" else "linux")
        if name == "env":
            if len(args) != 1 or not isinstance(args[0], str):
                raise ValueError("env('VAR') 需要 1 个字符串参数")
            return os.environ.get(args[0], "")
        if name == "module":
            if len(args) != 1 or not isinstance(args[0], str):
                raise ValueError("module('id') 需要 1 个字符串参数")
            try:
                from module_registry import is_enabled
                return bool(is_enabled(args[0]))
            except Exception:
                return False
        raise ValueError(f"非法函数: {name}")

    # ─── 显式拒绝（安全边界：不进入，直接抛） ───
    def visit_Import(self, node):  # noqa: N802
        raise ValueError("import 不允许")

    def visit_ImportFrom(self, node):  # noqa: N802
        raise ValueError("import 不允许")

    def visit_Attribute(self, node):  # noqa: N802
        raise ValueError("属性访问不允许")

    def visit_Subscript(self, node):  # noqa: N802
        raise ValueError("下标访问不允许")

    def visit_Lambda(self, node):  # noqa: N802
        raise ValueError("lambda 不允许")

    def visit_List(self, node):  # noqa: N802
        raise ValueError("列表不允许")

    def visit_Dict(self, node):  # noqa: N802
        raise ValueError("字典不允许")

    def visit_Tuple(self, node):  # noqa: N802
        raise ValueError("元组不允许")

    def visit_ListComp(self, node):  # noqa: N802
        raise ValueError("推导式不允许")

    def visit_DictComp(self, node):  # noqa: N802
        raise ValueError("推导式不允许")

    def visit_Set(self, node):  # noqa: N802
        raise ValueError("集合不允许")

    def visit_Starred(self, node):  # noqa: N802
        raise ValueError("星号展开不允许")

    def visit_FString(self, node):  # noqa: N802
        raise ValueError("f-string 不允许")

    def visit_JoinedStr(self, node):  # noqa: N802
        raise ValueError("拼接字符串不允许")

    def visit_Slice(self, node):  # noqa: N802
        raise ValueError("切片不允许")

    def generic_visit(self, node):
        raise ValueError(f"非法节点: {type(node).__name__}")


def evaluate_condition(expr: str, ctx: Optional[Dict[str, Any]] = None) -> bool:
    """求值受限条件表达式（安全子集）。

    Args:
        expr: 条件表达式（如 "module('weather') and platform() == 'win'"）
        ctx: 额外上下文变量（可选）

    返回：表达式为真 → True；任何越界/语法错误/空串 → False（不抛异常）
    """
    if not expr or not isinstance(expr, str):
        return False
    try:
        tree = ast.parse(expr, mode="eval")
        result = _SafeEvaluator(ctx or {}).visit(tree)
        return bool(result)
    except Exception:
        return False


__all__ = ["evaluate_condition"]
