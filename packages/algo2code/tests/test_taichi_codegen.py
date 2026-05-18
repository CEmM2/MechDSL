"""Tests for the Taichi code generation backend."""

from algo2code import transpile


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
