"""W3 (issue #307, F7) — accept ``^T`` / ``^{T}`` as a transpose alias.

``^\\top`` and ``^{T}`` already parsed as transpose; bare ``^T`` did not.
All three should be equivalent, while a genuine power like ``x^2`` is unaffected.
"""

from __future__ import annotations

from algo2code.ast_nodes import BinOp, Expr, UnaryOp
from algo2code.expr_parser import parse_latex_expr


def _has_transpose(node: Expr) -> bool:
    if isinstance(node, UnaryOp):
        return node.op == "transpose" or _has_transpose(node.operand)
    if isinstance(node, BinOp):
        return _has_transpose(node.left) or _has_transpose(node.right)
    return False


def test_bare_caret_T_is_transpose():
    assert _has_transpose(parse_latex_expr("A^T b"))


def test_braced_T_is_transpose():
    assert _has_transpose(parse_latex_expr("A^{T} b"))


def test_top_macro_still_transpose():
    assert _has_transpose(parse_latex_expr(r"r^\top z"))


def test_all_three_forms_agree():
    forms = [parse_latex_expr(s) for s in ("x^T", "x^{T}", r"x^\top")]
    assert all(isinstance(f, UnaryOp) and f.op == "transpose" for f in forms)


def test_numeric_power_is_not_transpose():
    """A real exponent must still parse as a power, not a transpose."""
    expr = parse_latex_expr("x^2")
    assert isinstance(expr, BinOp) and expr.op == "pow"
    assert not _has_transpose(expr)
