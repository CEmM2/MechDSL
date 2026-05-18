"""Hourglass-suppression sanity test for reduced Hex8 (Task P5-7).

Acceptance criteria:
- AC-1: With Flanagan-Belytschko control active, initialising the nodal
  displacement along an hourglass mode produces a *non-zero* resisting
  internal force.
- AC-2: Without hourglass control, the same mode is a true zero-energy
  mode of the reduced rule — pure SVK reduced integration returns an
  identically zero internal force, confirming that stabilisation is
  required for reduced Hex8.

Sign convention
---------------
In this codebase, ``f_int`` is the internal *restoring* force with the
same sign as the displacement that created it (positive-strain-energy
gradient convention, i.e. ``f_int = dE_strain / du``).  Consequently, a
resisting force satisfies ``f_int . u > 0`` — a Newton step ``du`` that
reduces the residual moves the displacement back toward equilibrium.
(The spec phrasing "f_int . u < 0" uses the alternative convention where
f_int opposes applied loads; the two are equivalent up to a sign on
``f_int``.)
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.hourglass import (
    _projected_hourglass_vectors,
    flanagan_belytschko_force,
)
from mechdsl.ir.element_factory import ElementFactory
from mechdsl.verify._patch_test_kernels import (
    element_svk_internal_force,
    reference_nodes,
)

# SVK material (steel-ish, nu = 0.3 — same as test_patch_test_all_elements.py).
_YOUNG = 200.0e9
_NU = 0.3
_LAM = _YOUNG * _NU / ((1.0 + _NU) * (1.0 - 2.0 * _NU))
_MU = _YOUNG / (2.0 * (1.0 + _NU))


class TestTaskP5_7HourglassSuppression:
    """Tests for Task P5-7: hourglass-mode suppression sanity check.

    Acceptance criteria covered: AC-1 (non-zero resisting force on HG mode),
    AC-2 (regression guard without HG control).
    """

    @pytest.mark.integration
    def test_hourglass_mode_produces_resisting_force(self):
        """Verifies: initialising u along an hourglass mode produces a
        non-zero internal force that resists the mode (with Flanagan-
        Belytschko enabled).
        Acceptance criterion: AC-1 — non-zero resisting force.
        Passes when: ||f_int|| > 0 and f_int . u > 0 on a reduced Hex8
        element with HG control.
        """
        ir = ElementFactory.create("hex8", integration="reduced", hourglass="flanagan_belytschko")
        X = reference_nodes("hex8")

        # Initialise u along hourglass mode 0 (Gamma_1 = xi * eta),
        # projected for geometric consistency.  Apply it in the x-
        # direction; modes in other components / alphas give the same
        # qualitative answer.
        gamma, _V_e = _projected_hourglass_vectors(X)
        u = np.zeros((8, 3), dtype=np.float64)
        u[:, 0] = gamma[0]

        # Reduced SVK force (should vanish — hourglass modes are zero-
        # strain at the centroid by construction).
        f_svk = element_svk_internal_force(ir, u, X, _LAM, _MU)
        # Flanagan-Belytschko stabilisation force.
        f_hg = flanagan_belytschko_force(u, X, _MU)
        f_int = f_svk + f_hg

        norm = float(np.linalg.norm(f_int))
        work = float(np.sum(f_int * u))

        assert norm > 0.0, (
            "Reduced Hex8 with FB hourglass control must produce a non-zero "
            f"force on an hourglass mode; got ||f_int|| = {norm:.3e}."
        )
        # Resisting force convention (positive strain-energy gradient):
        # f_int . u > 0 means the restoring force opposes u in the sense
        # that a Newton step shrinks the residual.
        assert work > 0.0, (
            "FB hourglass control must *resist* the hourglass mode "
            f"(f_int . u > 0); got f_int . u = {work:.3e}."
        )

    @pytest.mark.integration
    def test_hourglass_suppression_fails_without_control(self):
        """Verifies: without hourglass control, the same hourglass mode
        produces identically-zero internal force (zero-energy mode
        confirmed).
        Acceptance criterion: AC-2 — regression guard without HG control.
        Passes when: ||f_int|| < 1e-10 on an hourglass-mode initialisation
        of reduced Hex8 *without* hourglass control.

        The assertion proves that stabilisation is required: without it
        the reduced Hex8 stiffness is rank-deficient on the four
        trilinear modes that FB (1981) identifies.
        """
        ir = ElementFactory.create("hex8", integration="reduced")
        X = reference_nodes("hex8")

        gamma, _V_e = _projected_hourglass_vectors(X)
        u = np.zeros((8, 3), dtype=np.float64)
        u[:, 0] = gamma[0]

        # Pure SVK reduced force, no FB stabilisation.
        f_svk = element_svk_internal_force(ir, u, X, _LAM, _MU)
        norm = float(np.linalg.norm(f_svk))

        assert norm < 1.0e-10, (
            "Without hourglass control, reduced Hex8 must leave the "
            "hourglass mode as a zero-energy mode (||f_int|| ~ 0); got "
            f"||f_int|| = {norm:.3e} — stabilisation appears to have leaked in."
        )
