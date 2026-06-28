"""Tests for the Taichi code generation backend."""

from algo2code import transpile
from algo2code.backends.taichi_codegen import TaichiEmitter


class TestTaichiCodegen:
    def test_code_has_imports(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        assert "import taichi as ti" in code

    def test_code_has_kernels(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        assert "@ti.kernel" in code
        assert "_dot(" in code or "def _dot" in code

    def test_code_has_driver(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        assert "def pcg(" in code

    def test_code_has_matvec(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        assert "_matvec" in code

    def test_code_has_convergence_check(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        assert "_norm(" in code
        assert "tol" in code

    def test_code_has_loop(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        assert "for k in range" in code


class TestNegateCoefficientPrecedence:
    """WI-4 / gemini MED: ``_negate`` must parenthesise compound coefficients.

    A bare ``f"-{coeff}"`` on a top-level sum/difference (``a + b``) emits the
    precedence-wrong ``-a + b`` instead of ``-(a + b)``; the symmetric
    ``coeff[1:]`` strip is wrong for a compound leading-minus. These pin the fix.
    """

    def test_compound_sum_is_parenthesised(self):
        # The defect this fixes: -a + b != -(a + b).
        assert TaichiEmitter._negate("a + b") == "-(a + b)"
        assert TaichiEmitter._negate("a - b") == "-(a - b)"

    def test_compound_leading_minus_is_not_naively_stripped(self):
        # coeff[1:] would give the wrong "a + b"; wrapping is correct (== a - b).
        assert TaichiEmitter._negate("-a + b") == "-(-a + b)"

    def test_atoms_and_products_stay_tidy(self):
        # Unary minus already binds tighter than * / and groups an atom, so no
        # parens are added (keeps emitted code clean on the common path).
        assert TaichiEmitter._negate("alpha") == "-alpha"
        assert TaichiEmitter._negate("-alpha") == "alpha"
        assert TaichiEmitter._negate("a * b") == "-a * b"
        assert TaichiEmitter._negate("rho / pq") == "-rho / pq"

    def test_already_parenthesised_and_exponent_are_not_compound(self):
        # A parenthesised sum is depth-1 (already grouped); a float exponent's
        # '-' carries no surrounding spaces -- neither is a top-level sum.
        assert TaichiEmitter._negate("(a + b)") == "-(a + b)"
        assert TaichiEmitter._negate("1.5e-3") == "-1.5e-3"
