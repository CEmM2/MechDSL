"""Parametric patch test over every ElementFactory triple (Task P5-7).

Acceptance criteria:
- AC-1: All element types pass the patch test to 1e-12 (1e-8 for reduced + FB).
- AC-2: Existing Hex8 full patch test continues to pass (regression guard).

Covered triples:
- hex8 full (existing baseline — single-element version)
- tet4 full  (nu < 0.4 to avoid volumetric locking; Plan B §B5.1)
- tet10 full
- hex20 full
- hex8 reduced + flanagan_belytschko
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.ir.element_factory import ElementFactory
from mechdsl.verify.patch_test import PatchTestResult, run_patch_test_parametric

# SVK material: mild-stiffness steel, nu = 0.3 (well away from Tet4's volumetric
# locking regime at nu -> 0.5). See Plan B phase B5 §B5.1 risk note.
_YOUNG = 200.0e9
_NU = 0.3
_LAM = _YOUNG * _NU / ((1.0 + _NU) * (1.0 - 2.0 * _NU))
_MU = _YOUNG / (2.0 * (1.0 + _NU))
_MATERIAL = {"lam": _LAM, "mu": _MU}

# Mild uniaxial stretch — constant Green-Lagrange strain.
_STRAIN = np.diag([0.01, 0.0, 0.0]).astype(np.float64)

_TOL_FULL = 1.0e-12
_TOL_REDUCED_FB = 1.0e-8


class TestTaskP5_7PatchTestAllElements:
    """Phase 5 acceptance: patch test over every ElementFactory triple.

    Acceptance criteria covered: AC-1 (all element types pass patch test),
    AC-2 (existing regression).
    """

    @pytest.mark.integration
    def test_patch_test_hex8_full(self):
        """Verifies: Hex8 full-integration patch test passes (regression guard).
        Acceptance criterion: AC-2 — baseline preserved.
        Passes when: normalised equilibrium residual < 1e-12.
        """
        ir = ElementFactory.create("hex8", integration="full")
        result = run_patch_test_parametric(ir, _MATERIAL, strain=_STRAIN, tol=_TOL_FULL)
        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Hex8 full patch test FAILED: error={result.error:.3e} "
            f">= tol={result.tol:.3e}\n  {result}"
        )
        assert result.error < _TOL_FULL

    @pytest.mark.integration
    def test_patch_test_tet4(self):
        """Verifies: Tet4 reproduces a constant strain exactly.
        Acceptance criterion: AC-1 — Tet4 patch test.
        Passes when: normalised equilibrium residual < 1e-12 at nu = 0.3.

        Notes
        -----
        Tet4 is susceptible to volumetric locking as nu approaches 0.5 (see
        Plan B §B5.1).  The fixed material uses nu = 0.3 to stay well away
        from the near-incompressible regime; B-bar / F-bar stabilisation for
        near-incompressible tets is deferred to Plan B §B5.3.
        """
        ir = ElementFactory.create("tet4", integration="full")
        result = run_patch_test_parametric(ir, _MATERIAL, strain=_STRAIN, tol=_TOL_FULL)
        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Tet4 patch test FAILED: error={result.error:.3e} >= tol={result.tol:.3e}\n  {result}"
        )
        assert result.error < _TOL_FULL

    @pytest.mark.integration
    def test_patch_test_tet10(self):
        """Verifies: Tet10 reproduces a constant strain exactly.
        Acceptance criterion: AC-1 — Tet10 patch test.
        Passes when: normalised equilibrium residual < 1e-12.
        """
        ir = ElementFactory.create("tet10", integration="full")
        result = run_patch_test_parametric(ir, _MATERIAL, strain=_STRAIN, tol=_TOL_FULL)
        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Tet10 patch test FAILED: error={result.error:.3e} >= tol={result.tol:.3e}\n  {result}"
        )
        assert result.error < _TOL_FULL

    @pytest.mark.integration
    def test_patch_test_hex20(self):
        """Verifies: Hex20 reproduces a constant strain exactly.
        Acceptance criterion: AC-1 — Hex20 patch test.
        Passes when: normalised equilibrium residual < 1e-12.
        """
        ir = ElementFactory.create("hex20", integration="full")
        result = run_patch_test_parametric(ir, _MATERIAL, strain=_STRAIN, tol=_TOL_FULL)
        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Hex20 patch test FAILED: error={result.error:.3e} >= tol={result.tol:.3e}\n  {result}"
        )
        assert result.error < _TOL_FULL

    @pytest.mark.integration
    def test_patch_test_hex8_reduced_with_hourglass(self):
        """Verifies: reduced Hex8 + Flanagan-Belytschko reproduces constant strain.
        Acceptance criterion: AC-1 — reduced Hex8 with hourglass patch test.
        Passes when: normalised equilibrium residual < 1e-8 on a reduced-Hex8
        element with Flanagan-Belytschko hourglass control active.

        The looser tolerance (vs. 1e-12 for full integration) comes from the
        FB geometric projection (FB 1981 eq. 2.33), which introduces
        ``O(1e-10)`` round-off when subtracting the linear-mode content.
        """
        ir = ElementFactory.create("hex8", integration="reduced", hourglass="flanagan_belytschko")
        result = run_patch_test_parametric(ir, _MATERIAL, strain=_STRAIN, tol=_TOL_REDUCED_FB)
        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Reduced Hex8 + FB patch test FAILED: error={result.error:.3e} "
            f">= tol={result.tol:.3e}\n  {result}"
        )
        assert result.error < _TOL_REDUCED_FB
