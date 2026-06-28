"""Tests for Task P1-2: compile_from_sources() — Taichi-free compile_latex wrapper.

AC[0]: Returns the documented keys for an SVK energy source.
AC[1]: Does NOT call ti.init (guard via monkeypatch/subprocess sentinel).
AC[2]: content_hash stable for identical input.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Minimal 3-D Hex8 problem with SVK named model (E/nu params) — used for
# named-model and Taichi-free tests that do not supply an energy block.
_PROBLEM_SOURCE = """\
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""

# St. Venant-Kirchhoff strain-energy density authored in named invariants
# (same source used by dev/examples/svk_energy.tex).
#
# The derived energy uses \lambda (sanitised to ``aleph`` to avoid the Python
# keyword) and \mu as its symbolic parameter names.  The companion problem
# source below must therefore supply those names in its material params, NOT
# E/nu — the codegen checks at emission time that every derived parameter is
# present in MaterialSpec.params.
_SVK_ENERGY_SOURCE = """\
% declare metric gDD --dim 3
% declare EDD --dim 3
% declare \\lambda \\mu --const
\\Psi = \\frac{\\lambda}{2} E^{I}_{I} E^{J}_{J} + \\mu E^{I J} E_{I J}
"""

# E=200e3, nu=0.3  =>  lam = E*nu/((1+nu)(1-2nu)) ≈ 115384.6,
#                       mu  = E/(2*(1+nu))          ≈  76923.1
# ``aleph`` is the sanitised placeholder for \lambda (avoids Python keyword).
_PROBLEM_SOURCE_WITH_ENERGY = """\
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --aleph 115384.6 --mu 76923.1
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""


class TestTaskP1_2:
    """Tests for Task P1-2: compile_from_sources() — Taichi-free compile_latex wrapper."""

    # -----------------------------------------------------------------------
    # AC[0]: compile SVK energy -> summary — documented keys with right types
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_compile_svk_energy_summary(self):
        """Verifies: compile SVK energy -> summary.

        AC[0]: Returns the documented keys for an SVK energy source.
        The four keys must be present; element_ir_summary must contain the
        five stable scalar fields; emitted_source must be a non-empty string;
        content_hash must be a 64-char hex string; derived_energy_present
        must be True when an energy block is supplied.
        """
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(
            problem_source=_PROBLEM_SOURCE_WITH_ENERGY,
            energy_source=_SVK_ENERGY_SOURCE,
        )

        # --- top-level keys ---
        required_keys = {
            "element_ir_summary",
            "emitted_source",
            "content_hash",
            "derived_energy_present",
        }
        assert set(result.keys()) == required_keys, (
            f"compile_from_sources() keys mismatch.\n"
            f"Missing: {required_keys - set(result.keys())!r}\n"
            f"Extra: {set(result.keys()) - required_keys!r}"
        )

        # --- element_ir_summary ---
        summary = result["element_ir_summary"]
        assert isinstance(summary, dict), "element_ir_summary must be a dict"
        summary_required = {"element_type", "dim", "n_nodes", "n_quadrature_points", "formulation"}
        assert summary_required <= set(summary.keys()), (
            f"element_ir_summary missing keys: {summary_required - set(summary.keys())!r}"
        )
        assert summary["element_type"] == "hex8", (
            f"element_type must be 'hex8', got {summary['element_type']!r}"
        )
        assert summary["dim"] == 3, f"dim must be 3, got {summary['dim']!r}"
        assert isinstance(summary["n_nodes"], int) and summary["n_nodes"] > 0, (
            "n_nodes must be a positive int"
        )
        assert (
            isinstance(summary["n_quadrature_points"], int) and summary["n_quadrature_points"] > 0
        ), "n_quadrature_points must be a positive int"
        assert summary["formulation"] == "total_lagrangian", (
            f"formulation must be 'total_lagrangian', got {summary['formulation']!r}"
        )

        # --- emitted_source ---
        assert isinstance(result["emitted_source"], str) and result["emitted_source"], (
            "emitted_source must be a non-empty string"
        )

        # --- content_hash ---
        h = result["content_hash"]
        assert isinstance(h, str) and len(h) == 64, (
            f"content_hash must be a 64-char hex string (sha256), got {h!r}"
        )
        assert all(c in "0123456789abcdef" for c in h), (
            f"content_hash must be lowercase hex, got {h!r}"
        )

        # --- derived_energy_present ---
        assert result["derived_energy_present"] is True, (
            "derived_energy_present must be True when energy_source is supplied"
        )

    @pytest.mark.unit
    def test_compile_named_model_no_energy(self):
        """compile_from_sources with a named model and no energy_source returns
        derived_energy_present=False and still produces all four keys.
        """
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(problem_source=_PROBLEM_SOURCE)

        required_keys = {
            "element_ir_summary",
            "emitted_source",
            "content_hash",
            "derived_energy_present",
        }
        assert set(result.keys()) == required_keys

        assert result["derived_energy_present"] is False, (
            "derived_energy_present must be False for a named-model run (no energy_source)"
        )
        assert isinstance(result["emitted_source"], str) and result["emitted_source"]
        assert isinstance(result["content_hash"], str) and len(result["content_hash"]) == 64

    @pytest.mark.unit
    def test_compile_requires_problem_source(self):
        """compile_from_sources raises ValueError when problem_source is None."""
        from mechdsl.integration import compile_from_sources

        with pytest.raises(ValueError, match="problem_source"):
            compile_from_sources()

    # -----------------------------------------------------------------------
    # AC[1]: no ti.init — subprocess sentinel (most robust)
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_no_ti_init_subprocess(self):
        """compile_from_sources must not trigger ti.init.

        Uses a subprocess with a fresh interpreter so no parent-process state
        can contaminate the result.  The subprocess exits with code 0 on
        success or code 1 if taichi appears in sys.modules after the call.
        """
        script = (
            "import sys; "
            "from mechdsl.integration import compile_from_sources; "
            "compile_from_sources("
            "    problem_source=("
            "        '% mechanics dim 3\\n'"
            "        '% mechanics cell hex8\\n'"
            "        '% mechanics formulation total_lagrangian\\n'"
            "        '% mechanics material svk --E 200e3 --nu 0.3\\n'"
            "        '% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2\\n'"
            "        '% mechanics boundary load --type neumann --traction \"t_bar\"\\n'"
            "    )"
            "); "
            "taichi_loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', taichi_loaded); "
            "sys.exit(1 if taichi_loaded else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            "compile_from_sources() triggered ti.init (taichi was loaded in subprocess).\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
        assert "taichi_loaded: False" in result.stdout, (
            f"Expected 'taichi_loaded: False' in subprocess stdout.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )

    @pytest.mark.unit
    def test_no_ti_init(self):
        """Secondary guard: if ti.init were called during compile_from_sources,
        the monkeypatched version would raise immediately.

        Complements the subprocess test — runs in-process using a fake taichi
        module whose init() raises, then calls compile_from_sources.  Because
        the compile path is Taichi-free this must not raise.
        """
        import types

        fake_ti = types.ModuleType("taichi")

        def _init_raises(*args, **kwargs):
            raise RuntimeError("ti.init was called — Taichi-free guarantee violated!")

        fake_ti.init = _init_raises  # type: ignore[attr-defined]

        import sys as _sys

        original = _sys.modules.get("taichi")
        _sys.modules["taichi"] = fake_ti
        try:
            from mechdsl.integration import compile_from_sources

            # Must not raise even with the sentinel taichi installed.
            result = compile_from_sources(problem_source=_PROBLEM_SOURCE)
            assert isinstance(result, dict)
        finally:
            if original is None:
                _sys.modules.pop("taichi", None)
            else:
                _sys.modules["taichi"] = original

    # -----------------------------------------------------------------------
    # AC[2]: stable content_hash — same input twice -> identical hash
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_stable_content_hash(self):
        """Verifies: stable content_hash.

        AC[2]: content_hash is deterministic — calling compile_from_sources
        twice with identical inputs must produce the same hash.
        """
        from mechdsl.integration import compile_from_sources

        result_a = compile_from_sources(
            problem_source=_PROBLEM_SOURCE_WITH_ENERGY,
            energy_source=_SVK_ENERGY_SOURCE,
        )
        result_b = compile_from_sources(
            problem_source=_PROBLEM_SOURCE_WITH_ENERGY,
            energy_source=_SVK_ENERGY_SOURCE,
        )

        assert result_a["content_hash"] == result_b["content_hash"], (
            f"content_hash is not stable across two identical calls.\n"
            f"First:  {result_a['content_hash']!r}\n"
            f"Second: {result_b['content_hash']!r}"
        )

    @pytest.mark.unit
    def test_stable_content_hash_named_model(self):
        """content_hash is also stable for named-model runs (no energy_source)."""
        from mechdsl.integration import compile_from_sources

        result_a = compile_from_sources(problem_source=_PROBLEM_SOURCE)
        result_b = compile_from_sources(problem_source=_PROBLEM_SOURCE)

        assert result_a["content_hash"] == result_b["content_hash"], (
            f"content_hash is not stable for named-model runs.\n"
            f"First:  {result_a['content_hash']!r}\n"
            f"Second: {result_b['content_hash']!r}"
        )
