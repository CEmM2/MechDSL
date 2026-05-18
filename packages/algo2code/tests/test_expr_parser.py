"""Tests for the LaTeX math expression parser."""

from algo2code.ast_nodes import BinOp, FuncCall, Number, UnaryOp, Var
from algo2code.expr_parser import parse_assignment, parse_latex_expr, tokenize


class TestTokenizer:
    def test_simple_var(self):
        toks = tokenize("x")
        assert len(toks) == 1
        assert toks[0].kind == "LETTER"

    def test_greek(self):
        toks = tokenize(r"\alpha")
        assert len(toks) == 1
        assert toks[0].kind == "GREEK"
        assert toks[0].value == "alpha"

    def test_styled(self):
        toks = tokenize(r"\mathbf{r}")
        assert len(toks) == 1
        assert toks[0].kind == "STYLED"
        assert toks[0].value == "r"

    def test_frac(self):
        toks = tokenize(r"\frac{a}{b}")
        kinds = [t.kind for t in toks]
        assert "FRAC" in kinds

    def test_norm(self):
        toks = tokenize(r"\|r\|")
        kinds = [t.kind for t in toks]
        assert kinds.count("NORMPIPE") == 2

    def test_whitespace_skipped(self):
        toks = tokenize(r"a + b")
        assert all(t.kind != "WS" for t in toks)


class TestExprParser:
    def test_number(self):
        e = parse_latex_expr("42")
        assert isinstance(e, Number)
        assert e.value == 42.0

    def test_variable(self):
        e = parse_latex_expr("x")
        assert isinstance(e, Var)
        assert e.name == "x"

    def test_greek_var(self):
        e = parse_latex_expr(r"\alpha")
        assert isinstance(e, Var)
        assert e.name == "alpha"

    def test_addition(self):
        e = parse_latex_expr("a + b")
        assert isinstance(e, BinOp)
        assert e.op == "+"

    def test_subtraction(self):
        e = parse_latex_expr("a - b")
        assert isinstance(e, BinOp)
        assert e.op == "-"

    def test_fraction(self):
        e = parse_latex_expr(r"\frac{a}{b}")
        assert isinstance(e, BinOp)
        assert e.op == "/"
        assert isinstance(e.left, Var) and e.left.name == "a"
        assert isinstance(e.right, Var) and e.right.name == "b"

    def test_cdot(self):
        e = parse_latex_expr(r"A \cdot p")
        assert isinstance(e, BinOp)
        assert e.op == "*"

    def test_transpose(self):
        e = parse_latex_expr(r"r^\top z")
        assert isinstance(e, BinOp)
        assert e.op == "*"
        assert isinstance(e.left, UnaryOp) and e.left.op == "transpose"

    def test_transpose_braces(self):
        e = parse_latex_expr(r"r^{\top} z")
        assert isinstance(e, BinOp)
        assert isinstance(e.left, UnaryOp) and e.left.op == "transpose"

    def test_norm(self):
        e = parse_latex_expr(r"\|r\|")
        assert isinstance(e, UnaryOp)
        assert e.op == "norm"

    def test_styled_vars(self):
        e = parse_latex_expr(r"\mathbf{A} \cdot \mathbf{p}")
        assert isinstance(e, BinOp)
        assert isinstance(e.left, Var) and e.left.name == "A"
        assert isinstance(e.right, Var) and e.right.name == "p"

    def test_subscript(self):
        e = parse_latex_expr(r"\rho_{\text{new}}")
        assert isinstance(e, Var)
        assert e.name == "rho"
        assert e.subscript == "new"

    def test_inverse_func(self):
        e = parse_latex_expr(r"M^{-1}(r)")
        assert isinstance(e, FuncCall)
        assert isinstance(e.func, UnaryOp) and e.func.op == "inverse"

    def test_nested_frac(self):
        e = parse_latex_expr(r"\frac{\rho_{\text{new}}}{\rho}")
        assert isinstance(e, BinOp)
        assert e.op == "/"

    def test_frac_with_dot(self):
        e = parse_latex_expr(r"\frac{\rho}{p^\top q}")
        assert isinstance(e, BinOp)
        assert e.op == "/"
        den = e.right
        assert isinstance(den, BinOp) and den.op == "*"


class TestAssignment:
    def test_simple(self):
        result = parse_assignment("r = b - A")
        assert result is not None
        target, rhs = result
        assert target.name == "r"
        assert isinstance(rhs, BinOp)

    def test_not_assignment(self):
        result = parse_assignment("a + b")
        assert result is None
