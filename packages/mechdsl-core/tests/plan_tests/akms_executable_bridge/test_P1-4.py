"""Tests for Task P1-4: verify() — verify harness wrapper (Taichi-paying path).

Acceptance criteria:
  AC[0]: verify('patch_test', ...) runs and returns a result dict.
  AC[1]: unknown kind raises a clear error.
  AC[2]: calling verify() does NOT break the module-level Taichi-free invariant
         (the lazy-import structure is confirmed by the P1-1 subprocess test,
         but we add a fast in-process guard here too).
"""

from __future__ import annotations

import subprocess
import sys
import types

import pytest


class TestTaskP1_4:
    """Tests for Task P1-4: verify() — verify harness wrapper (Taichi-paying path)."""

    # -----------------------------------------------------------------------
    # AC[1]: unknown kind error — fast, no Taichi
    # -----------------------------------------------------------------------

    @pytest.mark.integration
    def test_unknown_kind_error(self):
        """verify('nonsense_kind', {}) raises ValueError mentioning supported kinds.

        AC[1]: unknown kind raises a clear error.
        """
        from mechdsl.integration import verify

        with pytest.raises(ValueError, match=r"Supported kinds:") as exc_info:
            verify("nonsense_kind", {})

        msg = str(exc_info.value)
        # The error must name at least one supported kind so callers can self-correct.
        assert "patch_test" in msg, (
            f"ValueError should mention 'patch_test' as a supported kind. Got: {msg!r}"
        )
        # The new benchmark kind must also be listed
        assert "benchmark" in msg, (
            f"ValueError should mention 'benchmark' as a supported kind. Got: {msg!r}"
        )

    # -----------------------------------------------------------------------
    # AC[2]: lazy-import invariant — fast, in-process guard
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_verify_importable_without_taichi(self, monkeypatch):
        """In-process attribute-access guard: importing mechdsl.integration and
        reading the ``verify`` attribute does not invoke ``ti.init``.

        This test only proves that attribute access and calling the cheap
        (non-Taichi) entry points does not trigger ``ti.init`` in-process.
        It is NOT the authoritative Taichi-free guard — the subprocess test
        ``test_no_ti_init_on_import_includes_verify_symbol`` (below) is the
        load-bearing check, because a fresh interpreter is used there so no
        parent-process Taichi state can contaminate the result.
        """
        import importlib

        # Fake taichi that explodes if imported
        fake_ti = types.ModuleType("taichi")

        def _init_raises(*args, **kwargs):
            raise RuntimeError("ti.init was called — Taichi-free guarantee violated!")

        fake_ti.init = _init_raises  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "taichi", fake_ti)

        # Importing the module and accessing `verify` must not trigger ti.init.
        integration = importlib.import_module("mechdsl.integration")
        verify_fn = integration.verify

        # verify itself is callable and in __all__
        assert callable(verify_fn), "verify must be callable"
        assert "verify" in integration.__all__, "verify must be listed in __all__"

    @pytest.mark.unit
    def test_verify_in_all(self):
        """verify is exported in mechdsl.integration.__all__."""
        import mechdsl.integration as mod

        assert "verify" in mod.__all__, f"'verify' missing from __all__; got {mod.__all__!r}"

    # -----------------------------------------------------------------------
    # AC[0]: verify('patch_test') runs and returns a result dict — slow
    # -----------------------------------------------------------------------

    @pytest.mark.integration
    @pytest.mark.slow
    def test_verify_patch_test_runs_slow(self):
        """verify('patch_test', ...) runs and returns a passing result dict.

        AC[0]: verify('patch_test', ...) runs and returns a result dict.

        Uses a minimal 2×2×2 mesh with unit Lame parameters so the test
        completes quickly while still exercising the full call path.
        """
        from mechdsl.integration import verify

        result = verify(
            "patch_test",
            {
                "lam": 1.0,
                "mu": 1.0,
                "nx": 2,
                "ny": 2,
                "nz": 2,
                "tol": 1e-12,
            },
        )

        # Shape contract: must be a dict with the three top-level keys
        assert isinstance(result, dict), f"verify() must return a dict; got {type(result)!r}"
        assert "kind" in result, f"result must have 'kind' key; got {result!r}"
        assert "passed" in result, f"result must have 'passed' key; got {result!r}"
        assert "details" in result, f"result must have 'details' key; got {result!r}"

        # kind echoes back the input
        assert result["kind"] == "patch_test", (
            f"result['kind'] must be 'patch_test'; got {result['kind']!r}"
        )

        # passed must be a plain bool
        assert isinstance(result["passed"], bool), (
            f"result['passed'] must be bool; got {type(result['passed'])!r}"
        )

        # The patch test should pass on a regular mesh with unit material
        assert result["passed"], f"Patch test FAILED — details: {result['details']!r}"

        # details shape: verify the mandatory diagnostic fields are present
        details = result["details"]
        assert isinstance(details, dict), f"result['details'] must be a dict; got {type(details)!r}"
        for key in (
            "error",
            "tol",
            "interior_force_max",
            "boundary_force_sum",
            "n_nodes",
            "n_elements",
        ):
            assert key in details, f"details must contain '{key}'; got keys {list(details)!r}"

        # Numeric sanity on error field
        assert isinstance(details["error"], float), (
            f"details['error'] must be float; got {type(details['error'])!r}"
        )
        assert details["error"] < 1e-12, f"Patch-test error {details['error']:.3e} must be < 1e-12"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_verify_patch_test_custom_strain(self):
        """verify('patch_test') accepts an explicit strain tensor in params."""
        from mechdsl.integration import verify

        # Hydrostatic strain — should also pass the patch test
        strain = [[1e-4, 0.0, 0.0], [0.0, 1e-4, 0.0], [0.0, 0.0, 1e-4]]
        result = verify("patch_test", {"lam": 1.0, "mu": 1.0, "strain": strain})

        assert result["kind"] == "patch_test"
        assert isinstance(result["passed"], bool)
        assert result["passed"], f"Patch test with hydrostatic strain failed: {result['details']}"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_verify_result_is_json_friendly(self):
        """The result dict from verify('patch_test') round-trips through json.dumps."""
        import json

        from mechdsl.integration import verify

        result = verify("patch_test", {"lam": 1.0, "mu": 1.0, "nx": 1, "ny": 1, "nz": 1})

        # Should not raise
        serialised = json.dumps(result)
        recovered = json.loads(serialised)
        assert recovered["kind"] == "patch_test"

    # -----------------------------------------------------------------------
    # Subprocess confirmation: verify present in module + module still Taichi-free
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_no_ti_init_on_import_includes_verify_symbol(self):
        """Subprocess: importing mechdsl.integration (including verify symbol) stays
        Taichi-free — complements the P1-1 subprocess test."""
        script = (
            "import sys; "
            "from mechdsl.integration import capabilities, model_catalog, verify; "
            "capabilities(); "
            "model_catalog(); "
            # Do NOT call verify() — we are testing the import path only.
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
            "Importing mechdsl.integration.verify triggered ti.init.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
        assert "taichi_loaded: False" in result.stdout, (
            f"Expected 'taichi_loaded: False' in subprocess stdout.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # AC[new]: verify("benchmark", ...) — new benchmark kind
    # -----------------------------------------------------------------------

    @pytest.mark.integration
    def test_benchmark_kind_accepted_by_kind_guard(self):
        """'benchmark' is in _VERIFY_KINDS — it is accepted by the kind guard."""
        from mechdsl.integration import _VERIFY_KINDS

        assert "benchmark" in _VERIFY_KINDS, (
            f"'benchmark' must be in _VERIFY_KINDS; got {_VERIFY_KINDS!r}"
        )

    @pytest.mark.integration
    def test_benchmark_missing_name_raises_value_error(self):
        """verify('benchmark', {}) raises ValueError (fast, no Taichi) for missing name."""
        from mechdsl.integration import verify

        with pytest.raises(ValueError):
            verify("benchmark", {})

    @pytest.mark.integration
    def test_benchmark_unknown_name_raises_value_error(self):
        """verify('benchmark', {'name': 'unknown'}) raises ValueError."""
        from mechdsl.integration import verify

        with pytest.raises(ValueError, match="unknown"):
            verify("benchmark", {"name": "unknown"})

    @pytest.mark.integration
    @pytest.mark.slow
    def test_verify_benchmark_cantilever_result_shape(self):
        """verify('benchmark', {'name':'cantilever'}) returns the normalised dict.

        AC[new]: benchmark kind returns {kind, passed, details} with the
        documented details keys.  Marked slow because it runs a full solve.
        """
        import json

        from mechdsl.integration import verify

        result = verify("benchmark", {"name": "cantilever"})

        # Top-level shape
        assert isinstance(result, dict)
        assert result["kind"] == "benchmark"
        assert isinstance(result["passed"], bool)
        assert isinstance(result["details"], dict)

        # details keys
        details = result["details"]
        for key in ("benchmark", "newton_iters", "wallclock_s", "n_nodes", "extras_keys"):
            assert key in details, f"details must contain '{key}'; got {list(details)!r}"

        assert details["benchmark"] == "cantilever"
        assert isinstance(details["newton_iters"], int)
        assert isinstance(details["wallclock_s"], float)
        assert isinstance(details["n_nodes"], int) and details["n_nodes"] > 0
        assert isinstance(details["extras_keys"], list)

        # Result must be JSON-friendly
        json.dumps(result)  # must not raise

        # The benchmark must report passed=True
        assert result["passed"], f"Cantilever benchmark FAILED — details: {details!r}"
