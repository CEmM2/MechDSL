"""Task P10-9: Fiber-reinforced strip benchmark (TL x HGO x Hex8).

Reference
---------
Holzapfel, Gasser & Ogden (2000)
    "A new constitutive framework for arterial wall mechanics and a
    comparative study of material models", Journal of Elasticity 61(1-3):
    1-48.

Gasser, Ogden & Holzapfel (2006)
    "Hyperelastic modelling of arterial layers with distributed collagen
    fibre orientations", J.R. Soc. Interface 3(6): 15-35 — extends the 2000
    model with the dispersion parameter kappa_disp used in
    ``mechdsl.symbolic.models.hgo``.

Parameter set
-------------
The widely-used "HGO benchmark" arterial-wall set:

    mu    = 7.64 kPa   (Neo-Hookean matrix shear modulus)
    k1    = 996.6 kPa  (fiber stress-like parameter)
    k2    = 524.6      (dimensionless exponential stiffening)
    kappa_disp = 0.226 (fiber dispersion; 0 = aligned, 1/3 = isotropic)

The volumetric bulk modulus is picked kappa_bulk = 1e3 * mu for
near-incompressibility (arterial-wall regime).  Stretches are bounded to
lambda in [1.0, 1.15] — well below the arterial failure regime and small
enough that the HGO tangent remains well-conditioned and the ref solver
converges in a handful of Newton iterations per load step.

Reference approach
------------------
*Closed-form analytical* reference curve: the HGO strain energy is an
algebraic function of F, so for a homogeneous uniaxial deformation we
solve a 2x2 nonlinear system for the lateral stretches enforcing zero
transverse PK2 stress.  This gives an analytical PK1 axial stress that is
independent of the FEM discretisation — the 5% envelope in the acceptance
criteria therefore measures FEM discretisation error only.

Acceptance criteria (from dev/tasks/PLAN-B/json/P10-9.json)
-----------------------------------------------------------
  AC-1. Longitudinal stress-stretch curve within 5% of Holzapfel reference.
  AC-2. Transverse stress-stretch curve within 5% of Holzapfel reference.
  AC-3. Longitudinal stiffness > transverse stiffness (anisotropy sanity).
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.models.hgo import HGOMaterial
from mechdsl.verify.benchmarks import (
    hgo_analytical_uniaxial_stress,
    run_hgo_uniaxial,
)
from tests.ref.ref_hex8_hgo import assemble_internal_force, solve_hgo

# ---------------------------------------------------------------------------
# HGO benchmark parameters (arterial-wall set; kPa)
# ---------------------------------------------------------------------------
_MU = 7.64
_K1 = 996.6
_K2 = 524.6
_KAPPA_DISP = 0.226
_KAPPA_BULK = 1.0e3 * _MU  # near-incompressible

_MATERIAL = HGOMaterial(
    mu=_MU,
    k1=_K1,
    k2=_K2,
    kappa=_KAPPA_BULK,
    fiber_dispersion=_KAPPA_DISP,
)

# Stretches for the benchmark sweep.  Keep the range modest so the
# closed-form lateral-stretch solve converges and the FEM Newton iteration
# stays well-behaved on a 1-element mesh.
_STRETCHES = (1.02, 1.05, 1.08, 1.12)

# 5% relative-error envelope from the task JSON.
_REL_ERR_TOL = 0.05


def _run_sweep(fiber_dir: np.ndarray, load_axis: int) -> dict:
    """Run a stretch sweep and collect FEM vs analytical axial stresses.

    Uses a 1-element mesh (homogeneous deformation) so the FEM solution and
    the closed-form analytical solution should agree to Newton tolerance.
    A 4-step displacement ramp keeps the Newton iteration well-conditioned
    even at the stiffest lambda = 1.12 case.
    """
    P_fem = np.empty(len(_STRETCHES), dtype=np.float64)
    P_ana = np.empty(len(_STRETCHES), dtype=np.float64)
    for i, lam in enumerate(_STRETCHES):
        result = run_hgo_uniaxial(
            stretch_lambda=lam,
            fiber_dir=fiber_dir,
            material=_MATERIAL,
            solve_hgo=solve_hgo,
            assemble_internal_force=assemble_internal_force,
            Lx=1.0,
            Ly=1.0,
            Lz=1.0,
            nx=1,
            ny=1,
            nz=1,
            load_axis=load_axis,
            n_load_steps=4,
        )
        P_fem[i] = result.extras["P_axial_fem"]
        P_ana[i] = result.extras["P_axial_analytical"]

    rel_err = np.abs(P_fem - P_ana) / np.abs(P_ana)
    return {
        "stretches": np.asarray(_STRETCHES),
        "P_fem": P_fem,
        "P_ana": P_ana,
        "rel_err": rel_err,
    }


class TestTaskP10_9:
    """Acceptance tests for Task P10-9: HGO fiber-reinforced strip benchmark."""

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_hgo_longitudinal_stress_stretch_within_5pct(self) -> None:
        """AC-1: longitudinal stress-stretch curve within 5% of HGO reference.

        Fiber along the loading axis (x).  A 1-element strip is stretched
        uniaxially in x; FEM axial PK1 is recovered from the reaction force
        on the loaded face and compared to the closed-form HGO stress.
        """
        fiber_dir = np.array([1.0, 0.0, 0.0])
        data = _run_sweep(fiber_dir, load_axis=0)
        max_err = float(np.max(data["rel_err"]))
        assert max_err < _REL_ERR_TOL, (
            f"Longitudinal max rel-err = {max_err:.4%} exceeds {_REL_ERR_TOL:.0%}. "
            f"FEM = {data['P_fem']}, analytical = {data['P_ana']}."
        )
        # Stress must also be monotonically increasing with stretch (model sanity).
        assert np.all(np.diff(data["P_fem"]) > 0.0), (
            f"Longitudinal FEM stress not monotone: {data['P_fem']}"
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_hgo_transverse_stress_stretch_within_5pct(self) -> None:
        """AC-2: transverse stress-stretch curve within 5% of HGO reference.

        Fiber along y but loading applied along x (perpendicular to fiber).
        The fiber term contributes very little — the response is close to
        the isotropic Neo-Hookean matrix.
        """
        fiber_dir = np.array([0.0, 1.0, 0.0])
        data = _run_sweep(fiber_dir, load_axis=0)
        max_err = float(np.max(data["rel_err"]))
        assert max_err < _REL_ERR_TOL, (
            f"Transverse max rel-err = {max_err:.4%} exceeds {_REL_ERR_TOL:.0%}. "
            f"FEM = {data['P_fem']}, analytical = {data['P_ana']}."
        )
        assert np.all(np.diff(data["P_fem"]) > 0.0), (
            f"Transverse FEM stress not monotone: {data['P_fem']}"
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_hgo_longitudinal_stiffer_than_transverse(self) -> None:
        """AC-3: longitudinal tangent modulus > transverse at matched stretch.

        At the same axial stretch lambda, the along-fiber PK1 stress must
        exceed the across-fiber stress for any stretch that activates the
        fiber (E_fi > 0).  With the arterial-wall k1 / k2 the along-fiber
        response is orders of magnitude stiffer for lambda >= 1.05.
        """
        stretch = 1.10
        long_result = run_hgo_uniaxial(
            stretch_lambda=stretch,
            fiber_dir=np.array([1.0, 0.0, 0.0]),
            material=_MATERIAL,
            solve_hgo=solve_hgo,
            assemble_internal_force=assemble_internal_force,
            load_axis=0,
            n_load_steps=4,
        )
        trans_result = run_hgo_uniaxial(
            stretch_lambda=stretch,
            fiber_dir=np.array([0.0, 1.0, 0.0]),
            material=_MATERIAL,
            solve_hgo=solve_hgo,
            assemble_internal_force=assemble_internal_force,
            load_axis=0,
            n_load_steps=4,
        )
        P_long = long_result.extras["P_axial_fem"]
        P_trans = trans_result.extras["P_axial_fem"]
        assert P_long > P_trans, (
            f"Expected longitudinal stiffer than transverse at lambda={stretch}: "
            f"P_long={P_long:.4e}, P_trans={P_trans:.4e}"
        )
        # Anisotropy should be strong: stiffness ratio >> 1 at this stretch.
        ratio = P_long / max(P_trans, 1e-30)
        assert ratio > 5.0, (
            f"Anisotropy ratio = {ratio:.2f} is too small; expected > 5 for arterial-wall HGO."
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_analytical_reference_matches_at_identity(self) -> None:
        """Sanity: closed-form axial stress vanishes at lambda = 1."""
        P, S, lateral = hgo_analytical_uniaxial_stress(
            stretch_lambda=1.0,
            fiber_dir=np.array([1.0, 0.0, 0.0]),
            material=_MATERIAL,
            load_axis=0,
        )
        assert abs(P) < 1.0e-6, f"P_axial at lambda=1 should vanish; got {P:.3e}"
        assert abs(S) < 1.0e-6, f"S_axial at lambda=1 should vanish; got {S:.3e}"
        # Lateral stretches at F=I must be 1.
        assert abs(lateral[0] - 1.0) < 1.0e-4, f"lam_T1 = {lateral[0]}"
        assert abs(lateral[1] - 1.0) < 1.0e-4, f"lam_T2 = {lateral[1]}"
