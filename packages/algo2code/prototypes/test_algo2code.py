"""
Tests for algo2code: LaTeX algorithmic → Taichi transpiler.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from algo2code.expr_parser import parse_latex_expr, parse_assignment, tokenize
from algo2code.algo_parser import parse_algorithm
from algo2code.type_inference import infer_types
from algo2code.ast_nodes import (
    Var, Number, BinOp, UnaryOp, FuncCall, VarType,
    Assign, ForLoop, Branch, Return, Break, Algorithm
)
from algo2code import transpile


# ═══════════════════════════════════════════════════════════════════════════
#  Expression parser tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTokenizer:
    def test_simple_var(self):
        toks = tokenize('x')
        assert len(toks) == 1
        assert toks[0].kind == 'LETTER'

    def test_greek(self):
        toks = tokenize(r'\alpha')
        assert len(toks) == 1
        assert toks[0].kind == 'GREEK'
        assert toks[0].value == 'alpha'

    def test_styled(self):
        toks = tokenize(r'\mathbf{r}')
        assert len(toks) == 1
        assert toks[0].kind == 'STYLED'
        assert toks[0].value == 'r'

    def test_frac(self):
        toks = tokenize(r'\frac{a}{b}')
        kinds = [t.kind for t in toks]
        assert 'FRAC' in kinds

    def test_norm(self):
        toks = tokenize(r'\|r\|')
        kinds = [t.kind for t in toks]
        assert kinds.count('NORMPIPE') == 2

    def test_whitespace_skipped(self):
        toks = tokenize(r'a + b')
        assert all(t.kind != 'WS' for t in toks)


class TestExprParser:
    def test_number(self):
        e = parse_latex_expr('42')
        assert isinstance(e, Number)
        assert e.value == 42.0

    def test_variable(self):
        e = parse_latex_expr('x')
        assert isinstance(e, Var)
        assert e.name == 'x'

    def test_greek_var(self):
        e = parse_latex_expr(r'\alpha')
        assert isinstance(e, Var)
        assert e.name == 'alpha'

    def test_addition(self):
        e = parse_latex_expr('a + b')
        assert isinstance(e, BinOp)
        assert e.op == '+'

    def test_subtraction(self):
        e = parse_latex_expr('a - b')
        assert isinstance(e, BinOp)
        assert e.op == '-'

    def test_fraction(self):
        e = parse_latex_expr(r'\frac{a}{b}')
        assert isinstance(e, BinOp)
        assert e.op == '/'
        assert isinstance(e.left, Var) and e.left.name == 'a'
        assert isinstance(e.right, Var) and e.right.name == 'b'

    def test_cdot(self):
        e = parse_latex_expr(r'A \cdot p')
        assert isinstance(e, BinOp)
        assert e.op == '*'

    def test_transpose(self):
        e = parse_latex_expr(r'r^\top z')
        # This should be implicit mul: transpose(r) * z
        assert isinstance(e, BinOp)
        assert e.op == '*'
        assert isinstance(e.left, UnaryOp) and e.left.op == 'transpose'

    def test_transpose_braces(self):
        e = parse_latex_expr(r'r^{\top} z')
        assert isinstance(e, BinOp)
        assert isinstance(e.left, UnaryOp) and e.left.op == 'transpose'

    def test_norm(self):
        e = parse_latex_expr(r'\|r\|')
        assert isinstance(e, UnaryOp)
        assert e.op == 'norm'

    def test_styled_vars(self):
        e = parse_latex_expr(r'\mathbf{A} \cdot \mathbf{p}')
        assert isinstance(e, BinOp)
        assert isinstance(e.left, Var) and e.left.name == 'A'
        assert isinstance(e.right, Var) and e.right.name == 'p'

    def test_subscript(self):
        e = parse_latex_expr(r'\rho_{\text{new}}')
        assert isinstance(e, Var)
        assert e.name == 'rho'
        assert e.subscript == 'new'

    def test_inverse_func(self):
        e = parse_latex_expr(r'M^{-1}(r)')
        assert isinstance(e, FuncCall)
        assert isinstance(e.func, UnaryOp) and e.func.op == 'inverse'

    def test_nested_frac(self):
        e = parse_latex_expr(r'\frac{\rho_{\text{new}}}{\rho}')
        assert isinstance(e, BinOp)
        assert e.op == '/'

    def test_frac_with_dot(self):
        """Test: \\frac{\\rho}{p^\\top q}"""
        e = parse_latex_expr(r'\frac{\rho}{p^\top q}')
        assert isinstance(e, BinOp)
        assert e.op == '/'
        # Denominator should be p^T * q
        den = e.right
        assert isinstance(den, BinOp) and den.op == '*'


class TestAssignment:
    def test_simple(self):
        result = parse_assignment('r = b - A')
        assert result is not None
        target, rhs = result
        assert target.name == 'r'
        assert isinstance(rhs, BinOp)

    def test_not_assignment(self):
        result = parse_assignment('a + b')
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
#  Algorithm parser tests
# ═══════════════════════════════════════════════════════════════════════════

PCG_LATEX = r"""
% algorithm pcg
% backend taichi
% args A:matrix, b:vector, x:vector, M_inv:callable, tol:scalar, maxiter:scalar

% type r vector
% type z vector
% type p vector
% type q vector
% type rho scalar
% type alpha scalar
% type beta scalar

\begin{algorithmic}
\State $r = b - A \cdot x$                     % vector
\State $z = M^{-1}(r)$                         % vector
\State $p = z$                                  % vector
\State $\rho = r^\top z$                        % scalar
\For{$k = 0, 1, \ldots, \text{maxiter}$}
    \State $q = A \cdot p$                      % vector
    \State $\alpha = \frac{\rho}{p^\top q}$     % scalar
    \State $x = x + \alpha \, p$                % vector
    \State $r = r - \alpha \, q$                % vector
    \If{$\|r\| < \text{tol}$}
        \Return $x, k$
    \EndIf
    \State $z = M^{-1}(r)$                      % vector
    \State $\rho_{\text{new}} = r^\top z$        % scalar
    \State $\beta = \frac{\rho_{\text{new}}}{\rho}$
    \State $p = z + \beta \, p$                  % vector
    \State $\rho = \rho_{\text{new}}$
\EndFor
\Return $x, \text{maxiter}$
\end{algorithmic}
"""


class TestAlgoParser:
    def test_parses_name(self):
        algo = parse_algorithm(PCG_LATEX)
        assert algo.name == 'pcg'

    def test_parses_backend(self):
        algo = parse_algorithm(PCG_LATEX)
        assert algo.backend == 'taichi'

    def test_parses_args(self):
        algo = parse_algorithm(PCG_LATEX)
        assert len(algo.args) == 6
        names = [n for n, _ in algo.args]
        assert 'A' in names
        assert 'b' in names

    def test_parses_type_directives(self):
        algo = parse_algorithm(PCG_LATEX)
        assert algo.type_annotations['r'] == VarType.VECTOR
        assert algo.type_annotations['rho'] == VarType.SCALAR

    def test_body_structure(self):
        algo = parse_algorithm(PCG_LATEX)
        # Should have: 4 assignments, 1 for loop, 1 return
        assert len(algo.body) == 6
        assert isinstance(algo.body[0], Assign)
        assert isinstance(algo.body[1], Assign)
        assert isinstance(algo.body[2], Assign)
        assert isinstance(algo.body[3], Assign)
        assert isinstance(algo.body[4], ForLoop)
        assert isinstance(algo.body[5], Return)

    def test_for_loop(self):
        algo = parse_algorithm(PCG_LATEX)
        for_stmt = algo.body[4]
        assert isinstance(for_stmt, ForLoop)
        assert for_stmt.var == 'k'
        assert for_stmt.start == 0
        assert for_stmt.end_expr == 'maxiter'

    def test_if_branch(self):
        algo = parse_algorithm(PCG_LATEX)
        for_body = algo.body[4].body
        # Find the If statement
        if_stmts = [s for s in for_body if isinstance(s, Branch)]
        assert len(if_stmts) == 1
        if_stmt = if_stmts[0]
        # Should have a Return in the body
        assert len(if_stmt.if_body) == 1
        assert isinstance(if_stmt.if_body[0], Return)

    def test_return_values(self):
        algo = parse_algorithm(PCG_LATEX)
        ret = algo.body[5]
        assert isinstance(ret, Return)
        assert len(ret.values) == 2


# ═══════════════════════════════════════════════════════════════════════════
#  Type inference tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTypeInference:
    def test_dot_product(self):
        algo = parse_algorithm(PCG_LATEX)
        infer_types(algo)
        # rho = r^T z should be scalar
        rho_assign = algo.body[3]
        assert rho_assign.value.inferred_type == VarType.SCALAR

    def test_matvec(self):
        algo = parse_algorithm(PCG_LATEX)
        infer_types(algo)
        # r = b - A·x : the A·x part should be matvec
        r_assign = algo.body[0]
        rhs = r_assign.value
        assert rhs.inferred_type == VarType.VECTOR

    def test_norm_is_scalar(self):
        algo = parse_algorithm(PCG_LATEX)
        infer_types(algo)
        # Find the If condition: ||r|| < tol
        for_body = algo.body[4].body
        if_stmt = [s for s in for_body if isinstance(s, Branch)][0]
        cond = if_stmt.condition
        assert isinstance(cond, BinOp)
        assert cond.left.inferred_type == VarType.SCALAR  # norm result


# ═══════════════════════════════════════════════════════════════════════════
#  Full pipeline test
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_transpile_produces_code(self):
        code = transpile(PCG_LATEX, backend='taichi')
        assert isinstance(code, str)
        assert len(code) > 100

    def test_code_has_imports(self):
        code = transpile(PCG_LATEX, backend='taichi')
        assert 'import taichi as ti' in code

    def test_code_has_kernels(self):
        code = transpile(PCG_LATEX, backend='taichi')
        assert '@ti.kernel' in code
        assert '_dot(' in code or 'def _dot' in code

    def test_code_has_driver(self):
        code = transpile(PCG_LATEX, backend='taichi')
        assert 'def pcg(' in code

    def test_code_has_matvec(self):
        code = transpile(PCG_LATEX, backend='taichi')
        assert '_matvec' in code

    def test_code_has_convergence_check(self):
        code = transpile(PCG_LATEX, backend='taichi')
        assert '_norm(' in code
        assert 'tol' in code

    def test_code_has_loop(self):
        code = transpile(PCG_LATEX, backend='taichi')
        assert 'for k in range' in code

    def test_code_is_syntactically_valid_python(self):
        code = transpile(PCG_LATEX, backend='taichi')
        # Should compile without SyntaxError (won't run without Taichi)
        try:
            compile(code, '<test>', 'exec')
            valid = True
        except SyntaxError as e:
            print(f"SyntaxError: {e}")
            print("Generated code:")
            for i, line in enumerate(code.split('\n'), 1):
                print(f"  {i:3d}  {line}")
            valid = False
        assert valid, "Generated code has syntax errors"


# ═══════════════════════════════════════════════════════════════════════════
#  Run tests
# ═══════════════════════════════════════════════════════════════════════════

def run_tests():
    """Simple test runner (no pytest dependency needed)."""
    import traceback

    test_classes = [
        TestTokenizer, TestExprParser, TestAssignment,
        TestAlgoParser, TestTypeInference, TestFullPipeline,
    ]

    total = 0
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        for method_name in sorted(methods):
            total += 1
            method = getattr(instance, method_name)
            try:
                method()
                passed += 1
                print(f"  ✓ {cls.__name__}.{method_name}")
            except AssertionError as e:
                failed += 1
                errors.append((cls.__name__, method_name, e, traceback.format_exc()))
                print(f"  ✗ {cls.__name__}.{method_name}")
            except Exception as e:
                failed += 1
                errors.append((cls.__name__, method_name, e, traceback.format_exc()))
                print(f"  ✗ {cls.__name__}.{method_name} (ERROR: {e})")

    print(f"\n{'═' * 60}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"{'═' * 60}")

    if errors:
        print("\nFailures:")
        for cls_name, method, exc, tb in errors:
            print(f"\n  {cls_name}.{method}:")
            # Print last 5 lines of traceback
            for line in tb.strip().split('\n')[-5:]:
                print(f"    {line}")

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
