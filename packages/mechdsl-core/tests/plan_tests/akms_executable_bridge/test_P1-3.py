"""Tests for Task P1-3: transpile_algorithm() — algo2code.transpile wrapper (Taichi-free).

AC[0]: Transpiles algo2code.library RADIAL_RETURN_J2_LATEX to valid Python,
        returning all four documented keys with the correct types.
AC[1]: valid_python reflects a compile() check (True for known-good input).
AC[2]: Calling transpile_algorithm() does not trigger ti.init.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


class TestTaskP1_3:
    """Tests for Task P1-3: transpile_algorithm() — algo2code.transpile wrapper (Taichi-free)."""

    # -----------------------------------------------------------------------
    # AC[0]: return-dict shape and types
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_transpile_radial_return_j2_latex(self):
        """Verifies: transpile RADIAL_RETURN_J2_LATEX.

        AC[0]: transpile_algorithm() returns all four documented keys with
        correct types when given the known-good RADIAL_RETURN_J2_LATEX input.
        """
        from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX
        from mechdsl.integration import transpile_algorithm

        result = transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend="taichi")

        # All four keys must be present.
        required_keys = {"code", "entry_point", "line_count", "valid_python"}
        assert set(result.keys()) == required_keys, (
            f"transpile_algorithm() keys mismatch.\n"
            f"Missing: {required_keys - set(result.keys())!r}\n"
            f"Extra: {set(result.keys()) - required_keys!r}"
        )

        # code: non-empty string
        assert isinstance(result["code"], str) and result["code"], "code must be a non-empty string"

        # entry_point: non-empty string — must be the J2 radial-return function name
        assert isinstance(result["entry_point"], str) and result["entry_point"], (
            "entry_point must be a non-empty string"
        )
        assert result["entry_point"] == "radial_return_j2", (
            f"entry_point must be 'radial_return_j2', got {result['entry_point']!r}"
        )

        # line_count: positive int consistent with code
        assert isinstance(result["line_count"], int) and result["line_count"] > 0, (
            "line_count must be a positive int"
        )
        assert result["line_count"] == len(result["code"].splitlines()), (
            "line_count must equal len(code.splitlines())"
        )

        # valid_python: bool
        assert isinstance(result["valid_python"], bool), "valid_python must be a bool"

    # -----------------------------------------------------------------------
    # AC[1]: valid_python reflects compile() check
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_valid_python_true(self):
        """Verifies: valid_python True.

        AC[1]: valid_python is True for RADIAL_RETURN_J2_LATEX because the
        transpiled source is syntactically valid Python.  Also verifies that
        the result's code field can itself be compiled (double-check).
        """
        from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX
        from mechdsl.integration import transpile_algorithm

        result = transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend="taichi")

        assert result["valid_python"] is True, (
            f"valid_python must be True for RADIAL_RETURN_J2_LATEX.\n"
            f"Transpiled code:\n{result['code']}"
        )

        # Belt-and-suspenders: confirm the code field actually compiles.
        try:
            compile(result["code"], "<transpiled>", "exec")
        except SyntaxError as exc:
            pytest.fail(
                f"result['code'] does not compile, but valid_python is True.\n"
                f"SyntaxError: {exc}\n"
                f"Code:\n{result['code']}"
            )

    @pytest.mark.unit
    def test_valid_python_false_on_invalid_code(self, monkeypatch):
        """valid_python is False when the transpiled source has a SyntaxError.

        Uses monkeypatch to inject a SyntaxError-producing stub so the test
        does not rely on algo2code ever emitting broken Python.
        """
        # Replace algo2code.transpile with a stub that returns broken Python.
        import algo2code
        import mechdsl.integration as integration_mod

        original_transpile = algo2code.transpile

        def _broken_transpile(source: str, backend: str = "taichi") -> str:
            return "def broken(:\n    pass"  # deliberate SyntaxError

        monkeypatch.setattr(algo2code, "transpile", _broken_transpile)
        # Also patch the name inside the integration module's lazy import scope.
        # Since integration uses `from algo2code import transpile` lazily inside
        # the function, we need to also patch the algo2code module attribute so
        # the lazy import picks up the stub.  The monkeypatch above handles that.

        try:
            # We need to import algo2code inside the function; monkeypatching the
            # module-level attribute is sufficient because Python's import system
            # returns the same module object.
            from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX

            # Call the real transpile_algorithm but with a patched algo2code.transpile.
            # Because the lazy import inside transpile_algorithm does
            # `from algo2code import transpile`, we need the stub to be on the
            # algo2code module object (which monkeypatch.setattr above did).
            # However, `from X import Y` inside a function binds the local name Y
            # to the current value of algo2code.transpile at call time — so our
            # monkeypatch does take effect.
            result = integration_mod.transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend="taichi")
            assert result["valid_python"] is False, (
                "valid_python must be False when transpiled code has a SyntaxError"
            )
        finally:
            monkeypatch.setattr(algo2code, "transpile", original_transpile)

    # -----------------------------------------------------------------------
    # AC[2]: no ti.init
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_no_ti_init(self):
        """Verifies: no ti.init.

        AC[2]: Calling transpile_algorithm() must not trigger ti.init.

        Uses a subprocess with a fresh interpreter so no parent-process state
        can contaminate the result.  The subprocess exits with code 0 on
        success or code 1 if taichi appears in sys.modules after the call.

        Note: the *transpiled source string* contains ``ti.init(...)`` as text
        (that is what the Taichi backend emits), but transpile_algorithm() only
        returns it as a string — it never executes it.  The subprocess check
        confirms this invariant holds end-to-end.
        """
        script = (
            "import sys; "
            "from mechdsl.integration import transpile_algorithm; "
            "from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX; "
            "result = transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend='taichi'); "
            "assert result['entry_point'] == 'radial_return_j2'; "
            "taichi_loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', taichi_loaded); "
            "sys.exit(1 if taichi_loaded else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            "transpile_algorithm() triggered ti.init (taichi was loaded in subprocess).\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
        assert "taichi_loaded: False" in result.stdout, (
            f"Expected 'taichi_loaded: False' in subprocess stdout.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )

    @pytest.mark.unit
    def test_no_ti_init_monkeypatch(self, monkeypatch):
        """Secondary guard: if ti.init were called during transpile_algorithm(),
        the monkeypatched version would raise immediately.

        Complements the subprocess test — runs in-process using a fake taichi
        module whose init() raises, then calls transpile_algorithm().  Because
        the transpile path is Taichi-free this must not raise.
        """
        import types

        fake_ti = types.ModuleType("taichi")

        def _init_raises(*args, **kwargs):
            raise RuntimeError("ti.init was called — Taichi-free guarantee violated!")

        fake_ti.init = _init_raises  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "taichi", fake_ti)

        from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX
        from mechdsl.integration import transpile_algorithm

        # Must not raise even with the sentinel taichi installed.
        result = transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend="taichi")
        assert isinstance(result, dict), "transpile_algorithm() must return a dict"
        assert result["entry_point"] == "radial_return_j2", (
            f"entry_point must be 'radial_return_j2', got {result['entry_point']!r}"
        )
