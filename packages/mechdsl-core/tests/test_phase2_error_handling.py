"""Tests for Phase 2: Error Handling Fixes (R3.2.x).

These tests verify error handling improvements introduced by Phase 2 of the
PR #3 review resolution plan (dev/plans/mvp_pr3_round3.md).
"""

from __future__ import annotations

import inspect
import warnings

import numpy as np
import pytest

from mechdsl.codegen.boundary_codegen import compile_neumann
from mechdsl.codegen.einsum_optimizer import _extract_flops
from mechdsl.codegen.taichi_printer import emit
from mechdsl.solver.import_adapter import CGSolver, PCGSolver
from mechdsl.solver.mesh_io import generate_hex8_mesh

# Reuse bundle helpers from Phase 1 tests
from tests.test_phase1_codegen_fixes import _make_svk_bundle


class TestR321CGBreakdownWarning:
    """R3.2.1: CG/PCG breakdown warning on non-SPD system."""

    def test_cg_breakdown_emits_warning(self) -> None:
        """CG breakdown on non-SPD system emits RuntimeWarning."""

        # Non-SPD system: matvec returns zero (p^T A p = 0)
        def zero_matvec(v: np.ndarray) -> np.ndarray:
            return np.zeros_like(v)

        solver = CGSolver()
        rhs = np.array([1.0, 2.0, 3.0])
        x0 = np.zeros(3)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            solver.solve(zero_matvec, rhs, x0, tol=1e-10, max_iter=10)
            cg_warnings = [x for x in w if issubclass(x.category, RuntimeWarning)]
            assert len(cg_warnings) >= 1
            assert "CG breakdown" in str(cg_warnings[0].message)

    def test_pcg_breakdown_emits_warning(self) -> None:
        """PCG breakdown on non-SPD system emits RuntimeWarning."""

        def zero_matvec(v: np.ndarray) -> np.ndarray:
            return np.zeros_like(v)

        solver = PCGSolver()
        rhs = np.array([1.0, 2.0, 3.0])
        x0 = np.zeros(3)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            solver.solve(zero_matvec, rhs, x0, tol=1e-10, max_iter=10)
            pcg_warnings = [x for x in w if issubclass(x.category, RuntimeWarning)]
            assert len(pcg_warnings) >= 1
            assert "PCG breakdown" in str(pcg_warnings[0].message)

    def test_cg_existing_convergence_still_works(self) -> None:
        """CG still converges on SPD systems without warnings."""

        # 3x3 identity: trivially SPD
        def identity_matvec(v: np.ndarray) -> np.ndarray:
            return v.copy()

        solver = CGSolver()
        rhs = np.array([1.0, 2.0, 3.0])
        x0 = np.zeros(3)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            x, _iters, _res = solver.solve(identity_matvec, rhs, x0, tol=1e-10, max_iter=100)
            cg_warnings = [x for x in w if issubclass(x.category, RuntimeWarning)]
            assert len(cg_warnings) == 0
        np.testing.assert_allclose(x, rhs, atol=1e-10)


class TestR322RadialReturnStallGuard:
    """R3.2.2: J2 radial_return stall guard raises on small derivative."""

    def test_no_pragma_no_cover_on_stall_path(self) -> None:
        """The stall guard path has no pragma: no cover."""
        from mechdsl.symbolic.models import j2_power_law

        source = inspect.getsource(j2_power_law.radial_return)
        # Find the stall guard
        assert "abs(df) < 1e-30" in source
        # Verify no pragma: no cover on that path
        lines = source.split("\n")
        for line in lines:
            if "abs(df) < 1e-30" in line:
                assert "pragma: no cover" not in line


class TestR323CGSolverConfig:
    """R3.2.3: Emitted CG solver configuration in Newton driver."""

    def test_emitted_cg_solver_used(self) -> None:
        """Emitted code uses CGSolver for linear solve."""
        source = emit(_make_svk_bundle())
        assert "CGSolver()" in source

    def test_emitted_cg_tolerance_set(self) -> None:
        """Emitted code configures CG tolerance."""
        source = emit(_make_svk_bundle())
        assert "solver.solve(" in source
        assert "tol=1.0e-10" in source

    def test_emitted_newton_non_convergence_raises(self) -> None:
        """Emitted code raises RuntimeError when Newton fails to converge."""
        source = emit(_make_svk_bundle())
        assert "Newton did not converge" in source


class TestR324FlopsSentinel:
    """R3.2.4: Einsum FLOPS extraction returns -1.0 sentinel on failure."""

    def test_flops_failure_returns_sentinel(self) -> None:
        """FLOPS extraction failure returns -1.0 (not 0.0)."""
        # Pass an object with no known FLOPS attributes
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _extract_flops(object())
            assert result == -1.0
            flops_warnings = [x for x in w if issubclass(x.category, RuntimeWarning)]
            assert len(flops_warnings) >= 1
            assert "sentinel" in str(flops_warnings[0].message).lower()


class TestR326BoundaryCodegenGuards:
    """R3.2.6: Boundary codegen zero-area face and axis validation."""

    def test_invalid_axis_raises(self) -> None:
        """Face name not starting with x/y/z raises ValueError."""
        mesh = generate_hex8_mesh(2, 2, 2)
        # Inject a fake boundary tag so it doesn't raise KeyError first
        mesh.boundary_tags["w0"] = mesh.boundary_tags["x0"]
        with pytest.raises(ValueError, match="Cannot determine face orientation"):
            compile_neumann(mesh, "w0", np.array([1.0, 0.0, 0.0]))

    def test_docstring_notes_structured_mesh(self) -> None:
        """compile_neumann docstring mentions structured mesh limitation."""
        doc = compile_neumann.__doc__
        assert doc is not None
        assert "structured mesh" in doc.lower()
