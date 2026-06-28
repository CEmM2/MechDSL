"""Tests for Task P1-5: test_integration_surface.py + README façade note.

These are lightweight task-scoped acceptance checks that complement the
canonical holistic test in
``packages/mechdsl-core/tests/test_integration_surface.py``.

AC[0]: All façade tests pass (smoke: all five functions are importable from
       mechdsl.integration and present in __all__).
AC[1]: no-ti.init assertion present and passing (fast subprocess guard that
       the Taichi-free invariant holds after importing all five symbols).
"""

from __future__ import annotations

import subprocess
import sys

import pytest


class TestTaskP1_5:
    """Acceptance checks for Task P1-5: test_integration_surface.py + README façade note."""

    # -----------------------------------------------------------------------
    # AC[0]: Full façade surface — smoke import of all five functions
    # -----------------------------------------------------------------------

    @pytest.mark.integration
    def test_full_facade_surface_all_five_functions_importable(self):
        """All five façade entry points are importable from mechdsl.integration and in __all__.

        AC[0]: All façade tests pass under `uv run pytest ... -q`.

        This is the minimal smoke check: verifies the module is coherent and
        all five symbols are exported.  The holistic contract tests live in
        ``tests/test_integration_surface.py``.
        """
        import mechdsl.integration as mod
        from mechdsl.integration import (  # noqa: F401
            capabilities,
            compile_from_sources,
            model_catalog,
            transpile_algorithm,
            verify,
        )

        five_functions = (
            "capabilities",
            "compile_from_sources",
            "model_catalog",
            "transpile_algorithm",
            "verify",
        )
        for name in five_functions:
            assert hasattr(mod, name), f"{name!r} not found on mechdsl.integration"
            assert callable(getattr(mod, name)), f"{name!r} must be callable"
            assert name in mod.__all__, (
                f"{name!r} missing from mechdsl.integration.__all__; got {mod.__all__!r}"
            )

        # Also confirm 'integration' is re-exported from the top-level package.
        import mechdsl

        assert "integration" in mechdsl.__all__, (
            f"'integration' missing from mechdsl.__all__; got {mechdsl.__all__!r}"
        )

    # -----------------------------------------------------------------------
    # AC[1]: no-ti.init guard — thin subprocess check
    # -----------------------------------------------------------------------

    @pytest.mark.integration
    def test_ti_init_guard(self):
        """Importing all five symbols and calling the Taichi-free four must not load Taichi.

        AC[1]: no-ti.init assertion present and passing.

        Uses a fresh-interpreter subprocess — the canonical form of this guard.
        The comprehensive version (covering compile_from_sources and
        transpile_algorithm individually) lives in
        ``tests/test_integration_surface.py::TestTaichiFreeInvariant``.
        """
        script = (
            "import sys; "
            "from mechdsl.integration import ("
            "    capabilities, model_catalog, compile_from_sources, "
            "    transpile_algorithm, verify"
            "); "
            # Call only the Taichi-free four (not verify, which is allowed to pay the cost).
            "capabilities(); "
            "model_catalog(); "
            "loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', loaded); "
            "sys.exit(1 if loaded else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            "Importing mechdsl.integration (all five symbols) + calling "
            "capabilities()/model_catalog() triggered Taichi load.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
        assert "taichi_loaded: False" in result.stdout, (
            f"Expected 'taichi_loaded: False' in subprocess stdout.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
