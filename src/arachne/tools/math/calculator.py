"""Math calculations tool."""

import ast
import math
import operator

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}

_ALLOWED_FUNCTIONS = {
    "math.sqrt": math.sqrt,
    "math.sin": math.sin,
    "math.cos": math.cos,
    "math.tan": math.tan,
    "math.log": math.log,
    "math.log10": math.log10,
    "math.exp": math.exp,
    "math.pi": math.pi,
    "math.e": math.e,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
}


def _eval_expr(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, int | float):
            return node.value
        raise TypeError(f"Unsupported constant type: {type(node.value)}")
    elif isinstance(node, ast.BinOp):
        return _ALLOWED_OPERATORS[type(node.op)](_eval_expr(node.left), _eval_expr(node.right))
    elif isinstance(node, ast.UnaryOp):
        return _ALLOWED_OPERATORS[type(node.op)](_eval_expr(node.operand))
    elif isinstance(node, ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            func_name = f"{node.func.value.id}.{node.func.attr}"

        if func_name in _ALLOWED_FUNCTIONS:
            args = [_eval_expr(arg) for arg in node.args]
            return _ALLOWED_FUNCTIONS[func_name](*args)
        raise ValueError(f"Unsupported function: {func_name}")
    elif isinstance(node, ast.Name):
        if node.id in _ALLOWED_FUNCTIONS:
            return _ALLOWED_FUNCTIONS[node.id]
        raise ValueError(f"Unsupported variable: {node.id}")
    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        attr_name = f"{node.value.id}.{node.attr}"
        if attr_name in _ALLOWED_FUNCTIONS:
            return _ALLOWED_FUNCTIONS[attr_name]
        raise ValueError(f"Unsupported attribute: {attr_name}")
    else:
        raise TypeError(f"Unsupported AST node type: {type(node)}")


def evaluate_math(expression: str) -> str:
    """Evaluate a mathematical expression safely.

    Supports basic arithmetic (+, -, *, /, //, %, **), and functions like
    math.sqrt, math.sin, math.log, abs, round, min, max, sum.

    Args:
        expression: The mathematical expression to evaluate (e.g., '2 + 2', 'math.sqrt(16)')
    """
    try:
        # Strip newlines and spaces that might confuse the parser
        expr = expression.strip()
        tree = ast.parse(expr, mode="eval").body
        result = _eval_expr(tree)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression '{expression}': {e}"
