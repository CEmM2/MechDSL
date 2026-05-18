"""End-to-end tests: LaTeX algorithm → generated code → syntax validation."""

import pytest

from algo2code import transpile

pytestmark = pytest.mark.e2e


class TestFullPipeline:
    def test_transpile_produces_code(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        assert isinstance(code, str)
        assert len(code) > 100

    def test_code_is_syntactically_valid_python(self, pcg_latex):
        code = transpile(pcg_latex, backend="taichi")
        compile(code, "<test>", "exec")

    def test_unknown_backend_raises(self, pcg_latex):
        with pytest.raises(ValueError, match="Unknown backend"):
            transpile(pcg_latex, backend="numpy")
