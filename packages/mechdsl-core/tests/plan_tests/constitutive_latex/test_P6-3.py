"""Tests for Task P6-3: J2 mixed hardening + numpy reference + reduction checks.

The J2 MIXED-hardening return-map (isotropic power-law radius
``sigma_y(alpha) = sigy0 + K*alpha^n`` PLUS linear kinematic back-stress
``beta``, simultaneously) is authored as algpseudocode in
``dev/algorithms/radial_return_j2_mixed.tex`` and transpiled to Taichi by
algo2code. Yield is on the RELATIVE stress ``xi = dev(S) - beta`` against the
EXPANDING radius ``sigma_y(alpha)``. Because the isotropic part is a nonlinear
power law in ``alpha``, the consistency residual is nonlinear in the plastic
multiplier ``dl`` and is solved by a scalar Newton loop (P6-1) with the kinematic
``(3*mu + H_kin)*dl`` term added (P6-2). There is NO existing mechdsl oracle for
mixed hardening, so a small, independent numpy 1D-cyclic reference lives in
``packages/mechdsl-core/tests/ref/ref_j2_mixed.py``.

Two INDEPENDENT computation paths are compared on the cyclic differential-test
(NOT the same code run twice):

- Path (a): the algo2code-TRANSPILED scalar Newton solve, wrapped by the 3D
  tensor orchestration in ``mechdsl.lib.plasticity_mixed`` (deviatoric split,
  relative stress, von Mises of ``xi``, Prager tensor back-stress + plastic-strain
  + accumulated-plastic-strain ``alpha`` updates, algorithmic tangent).
- Path (b): the hand-written 1D mixed model in ``ref_j2_mixed.py`` — classical
  scalar (sigma, eps) plasticity with its OWN independent 1D Newton solve for the
  nonlinear power-law consistency. It shares no code with path (a): different
  state, different algebra, a separate scalar solver.

The strongest correctness signal is the pair of REDUCTION cross-checks, which
compare the mixed law against the ALREADY-VALIDATED P6-1 isotropic and P6-2
kinematic implementations (independent of the self-authored numpy reference):

- ``H_kin = 0`` -> the mixed law must match the P6-1 isotropic variant
  (``models/j2_power_law.radial_return``).
- ``K = 0`` -> the mixed law must match the P6-2 kinematic variant
  (``lib/plasticity_kinematic.radial_return_kinematic``).

Even a wrong numpy reference cannot mask a mixed-law error: the reductions tie
the law back to two independently-validated models.

Acceptance criteria:
- AC-1: Mixed variant matches the numpy reference on a cyclic path.
- AC-2: Reduces to isotropic when kinematic modulus = 0.
- AC-3: Reduces to kinematic when isotropic modulus = 0.
- AC-4: Generated code within JIT budget.
"""

from __future__ import annotations

import ast

import numpy as np
import pytest

from algo2code.library.radial_return_j2_mixed import (
    transpile_radial_return_j2_mixed,
)
from mechdsl.lib.plasticity_kinematic import (
    J2KinematicMaterial,
    radial_return_kinematic,
)
from mechdsl.lib.plasticity_mixed import (
    J2MixedMaterial,
    radial_return_mixed,
)
from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
)
from mechdsl.symbolic.models.j2_power_law import (
    radial_return as iso_radial_return,
)
from tests.ref.ref_j2_mixed import (
    Mixed1D,
    analytic_first_yield,
    simulate_uniaxial_cyclic,
)

# Material parameters shared across tests.
_E = 200_000.0
_NU = 0.3
_MU = _E / (2.0 * (1.0 + _NU))
_SIGMA_Y0 = 250.0
_K = 500.0  # isotropic power-law coefficient
_N = 0.5  # isotropic power-law exponent
_H_KIN = 20_000.0  # linear kinematic (Prager) modulus

# Cyclic-path differential-test tolerance.
#
# Path (a) (3D tensor return, algo2code scalar Newton) and path (b) (independent
# 1D mixed model, own scalar Newton) agree to ~2e-11 MPa on the cyclic path
# (verified) — both Newton solves drive the same nonlinear consistency residual
# to ~1e-13 each step, and the deviatoric uniaxial map is exact, so the only
# residual is accumulated Newton/float round-off. A WRONG transpile (mis-scaled
# dl, wrong back-stress factor, wrong alpha increment, or a missing isotropic
# term) would leave ||xi||_eq off the (expanding) yield surface and shift the
# curve by MPa, blowing past this bound. Set at 1e-6 MPa (~3e-9 of the ~300 MPa
# peak) — a strict, non-tautological gate.
_CYCLIC_TOL_MPA = 1e-6

# Reduction tolerances. The reductions are the strongest correctness signal.
#
# K=0 reduces the residual to linear (constant radius) and the mixed and kinematic
# paths share the SAME tensor state (Ep, beta) advanced identically, so they agree
# to machine precision (verified: 0.0 over the full cyclic path).
_KIN_REDUCTION_TOL_MPA = 1e-9
# H_kin=0 zeroes the back-stress so the mixed law collapses to the isotropic
# return; compared single-step from the zero state (P6-1's isotropic return does
# not subtract a plastic-strain tensor, so a per-step-from-zero sweep is the
# apples-to-apples comparison). Measured: stress diff 5.7e-14, tangent diff
# 1.16e-10. Set to 1e-9 — strict (well below the design-doc <1e-8 target) yet
# safely above the achieved tangent diff (1e-10 would be tighter than the
# measured 1.16e-10 and would flake).
_ISO_REDUCTION_TOL = 1e-9

JIT_BUDGET_LINES_PER_TI_FUNC = 512  # 07-CONVENTIONS.md


def _mixed_material(K: float = _K, H_kin: float = _H_KIN) -> J2MixedMaterial:
    return J2MixedMaterial(E=_E, nu=_NU, sigma_y0=_SIGMA_Y0, K=K, n=_N, H_kin=H_kin)


def _reference(K: float = _K, H_kin: float = _H_KIN) -> Mixed1D:
    """1D mixed analog of the 3D model on a deviatoric uniaxial path.

    Effective deviatoric parameters: E_1d = 3*mu (signed von-Mises trial slope vs
    the axial deviatoric strain), H_kin = H_kin (Prager), (K, n) unchanged,
    Y0 = sigma_y0.
    """
    return Mixed1D(E=3.0 * _MU, H_kin=H_kin, K=K, n=_N, sigma_y0=_SIGMA_Y0)


def _cyclic_strain_path(eps_peak: float = 0.004, n_fwd: int = 800) -> np.ndarray:
    """Uniaxial cyclic strain amplitudes: load -> reverse -> reload."""
    fwd = np.linspace(0.0, eps_peak, n_fwd)
    rev = np.linspace(eps_peak, -eps_peak, 2 * n_fwd)
    reload_ = np.linspace(-eps_peak, eps_peak, 2 * n_fwd)
    return np.concatenate([fwd, rev[1:], reload_[1:]])


def _drive_3d_eq_stress(mat: J2MixedMaterial, path: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Drive the 3D mixed orchestration on a deviatoric uniaxial path.

    For ``E = diag(e, -e/2, -e/2)`` (traceless) the elastic predictor is purely
    deviatoric. The comparable signed von-Mises equivalent stress is recovered as
    ``1.5 * dev(S)[0,0]`` — the exact 1D analog the reference integrates.

    Returns ``(signed_eq_stress, is_plastic)`` arrays aligned with ``path``.
    """
    Ep = np.zeros((3, 3))
    beta = np.zeros((3, 3))
    alpha = 0.0
    eq_stress = np.empty(path.size, dtype=np.float64)
    plastic = np.empty(path.size, dtype=bool)
    for i, e in enumerate(path):
        E_strain = np.diag([e, -0.5 * e, -0.5 * e]).astype(float)
        res = radial_return_mixed(mat, E_strain, alpha, Ep, beta)
        Ep = res.plastic_strain
        beta = res.back_stress
        alpha = res.alpha_new
        s_dev = res.stress - (np.trace(res.stress) / 3.0) * np.eye(3)
        eq_stress[i] = 1.5 * s_dev[0, 0]
        plastic[i] = res.is_plastic
    return eq_stress, plastic


class TestTaskP6_3J2Mixed:
    """Tests for Task P6-3: J2 mixed hardening + reduction cross-checks.

    AC covered: AC-1 (reference match), AC-2 (reduce->isotropic),
    AC-3 (reduce->kinematic), AC-4 (JIT budget).

    Class name carries the ``J2`` token so the plan's verification command
    ``pytest -k 'j2 and (mixed or cyclic)'`` selects these tests.
    """

    @pytest.mark.integration
    def test_numpy_reference_cross_validates_analytically(self) -> None:
        """Verifies: the self-authored numpy mixed reference reproduces the
        hand-computable first-yield landmarks (eps_yield, sigma_yield), and the
        independent 1D Newton solve returns the response exactly to the
        (expanding) yield surface each plastic step. AC-1 (guards a wrong oracle).

        Runs FIRST conceptually: makes the reference trustworthy ground truth
        before it is used to validate the transpile.
        """
        ref = _reference()
        lm = analytic_first_yield(ref)

        # First yield is purely elastic up to |sigma| = sigma_y0, independent of
        # K, n, H_kin (all hardening engages only after first yield).
        fwd = np.linspace(0.0, 0.004, 4000)
        res = simulate_uniaxial_cyclic(ref, fwd)

        first_plastic = int(np.argmax(res["is_plastic"]))
        assert res["is_plastic"][first_plastic], "path never yielded"
        sigma_at_yield = res["stress"][first_plastic - 1]
        assert abs(sigma_at_yield - lm["sigma_yield"]) < 1.0, (
            f"first-yield stress {sigma_at_yield:.3f} != {lm['sigma_yield']:.3f}"
        )
        # The last elastic strain is below eps_yield, the first plastic at/above.
        assert fwd[first_plastic] >= lm["eps_yield"] - 1e-6, (
            "first plastic step occurred before the analytic yield strain"
        )

        # Consistency: on every plastic step PAST the alpha->0 boundary the
        # relative stress |sigma - q| must sit on the expanded radius
        # sigma_y(alpha) (the Newton solve returns to the surface). This is the 1D
        # analog of ||xi||_eq == sigma_y(alpha).
        #
        # The first plastic increment from alpha == 0 is excluded: with n < 1 the
        # isotropic slope K*n*alpha^(n-1) diverges as alpha -> 0+, so both this
        # reference and the 3D path hold the radius at sigy0 for that first step
        # (the documented alpha->0 guard, identical to j2_power_law.py — "tests
        # with n < 1 should start from a pre-yielded state"). The exclusion uses
        # the SAME 1e-12 threshold as Mixed1D.iso_slope's regulariser, so only the
        # single genuine boundary step is dropped (verified: 1 excluded, 2915
        # checked, worst off-surface residual 2.4e-11).
        checked = 0
        for i in range(fwd.size):
            if not res["is_plastic"][i]:
                continue
            alpha = res["alpha"][i]
            if alpha <= 1e-12:  # alpha->0 boundary (n<1 slope guard) — excluded
                continue
            sigma = res["stress"][i]
            q = res["back_stress"][i]
            radius = ref.sigma_y(alpha)
            assert abs(abs(sigma - q) - radius) < 1e-6, (
                f"step {i}: |sigma-q|={abs(sigma - q):.6f} off radius {radius:.6f}"
            )
            checked += 1
        assert checked > 0, "no plastic step past the alpha->0 boundary was checked"

    @pytest.mark.integration
    def test_cyclic_path_matches_numpy_reference(self) -> None:
        """Verifies: generated mixed stress matches the new numpy 1D mixed
        reference on a loading/unloading/reverse path. AC-1. Passes when: max abs
        diff within tolerance.

        Path (a) drives ``radial_return_mixed`` (algo2code-transpiled scalar
        Newton + 3D Prager tensor orchestration); path (b) drives
        ``simulate_uniaxial_cyclic`` (independent 1D mixed model, own Newton).
        They share no code.
        """
        mat = _mixed_material()
        path = _cyclic_strain_path()

        eq_stress_3d, plastic_3d = _drive_3d_eq_stress(mat, path)
        ref = simulate_uniaxial_cyclic(_reference(), path)
        stress_1d = ref["stress"]

        # The path must genuinely yield in both forward and reverse, with elastic
        # steps too — otherwise the plastic Newton branch is never exercised.
        assert plastic_3d.any(), "3D path never yielded"
        assert (~plastic_3d).any(), "3D path never had an elastic step"

        max_diff = float(np.max(np.abs(eq_stress_3d - stress_1d)))
        assert max_diff < _CYCLIC_TOL_MPA, (
            f"max |3D - 1D| = {max_diff:.4e} MPa >= {_CYCLIC_TOL_MPA} MPa "
            f"(3D peak {eq_stress_3d.max():.2f}, 1D peak {stress_1d.max():.2f})"
        )

    @pytest.mark.integration
    def test_reduces_to_isotropic_when_kinematic_modulus_zero(self) -> None:
        """Verifies: with H_kin = 0 the mixed law matches the P6-1 isotropic
        variant (``models/j2_power_law.radial_return``). AC-2 — the STRONGEST
        correctness signal: it ties the mixed law to an already-validated model
        independent of the self-authored numpy reference.

        With H_kin = 0 the back-stress stays zero (xi == dev(S)), so the mixed
        return collapses to the isotropic power-law return. Compared single-step
        from the zero state across a strain sweep (P6-1's isotropic return does
        not subtract a plastic-strain tensor, so a per-step-from-zero sweep is the
        apples-to-apples comparison — Ep = 0 makes the mixed trial identical to
        the isotropic trial).
        """
        mat = _mixed_material(H_kin=0.0)
        iso = J2PowerLawMaterial(E=_E, nu=_NU, sigma_y0=_SIGMA_Y0, K=_K, n=_N)

        saw_plastic = False
        saw_elastic = False
        max_stress_diff = 0.0
        max_tangent_diff = 0.0
        for i in range(1, 21):
            eps = 1e-4 * i
            E_strain = np.diag([eps, -0.5 * eps, -0.5 * eps]).astype(float)

            res_mixed = radial_return_mixed(mat, E_strain, 0.0, np.zeros((3, 3)), np.zeros((3, 3)))
            res_iso = iso_radial_return(iso, E_strain, 0.0)

            assert res_mixed.is_plastic == res_iso.is_plastic, (
                f"step {i}: is_plastic disagreement "
                f"(mixed={res_mixed.is_plastic}, iso={res_iso.is_plastic})"
            )
            saw_plastic = saw_plastic or res_iso.is_plastic
            saw_elastic = saw_elastic or not res_iso.is_plastic

            max_stress_diff = max(
                max_stress_diff,
                float(np.max(np.abs(res_mixed.stress - res_iso.stress))),
            )
            max_tangent_diff = max(
                max_tangent_diff,
                float(np.max(np.abs(res_mixed.tangent - res_iso.tangent))),
            )

        assert saw_plastic, "sweep never yielded (reduction vacuous)"
        assert saw_elastic, "sweep never had an elastic step (reduction vacuous)"
        assert max_stress_diff < _ISO_REDUCTION_TOL, (
            f"H_kin=0 mixed stress != isotropic: max diff {max_stress_diff:.3e}"
        )
        assert max_tangent_diff < _ISO_REDUCTION_TOL, (
            f"H_kin=0 mixed tangent != isotropic: max diff {max_tangent_diff:.3e}"
        )

    @pytest.mark.integration
    def test_reduces_to_kinematic_when_isotropic_modulus_zero(self) -> None:
        """Verifies: with K = 0 (isotropic modulus zero) the mixed law matches the
        P6-2 kinematic variant (``lib/plasticity_kinematic.radial_return_kinematic``).
        AC-3 — a strong correctness signal independent of the numpy reference.

        With K = 0 the radius is constant (sigma_y(alpha) == sigma_y0) and the
        residual is linear; the mixed and kinematic paths advance the SAME tensor
        state (Ep, beta), so they agree to machine precision over a full cyclic
        path (where the back-stress / Bauschinger coupling is exercised).
        """
        mat = _mixed_material(K=0.0)
        kin = J2KinematicMaterial(E=_E, nu=_NU, sigma_y0=_SIGMA_Y0, H_kin=_H_KIN)
        path = _cyclic_strain_path()

        Ep_m = np.zeros((3, 3))
        beta_m = np.zeros((3, 3))
        alpha_m = 0.0
        Ep_k = np.zeros((3, 3))
        beta_k = np.zeros((3, 3))

        saw_plastic = False
        saw_reverse_plastic = False
        max_diff = 0.0
        n_fwd = 800
        for i, e in enumerate(path):
            E_strain = np.diag([e, -0.5 * e, -0.5 * e]).astype(float)
            res_mixed = radial_return_mixed(mat, E_strain, alpha_m, Ep_m, beta_m)
            res_kin = radial_return_kinematic(kin, E_strain, Ep_k, beta_k)

            Ep_m, beta_m, alpha_m = (
                res_mixed.plastic_strain,
                res_mixed.back_stress,
                res_mixed.alpha_new,
            )
            Ep_k, beta_k = res_kin.plastic_strain, res_kin.back_stress

            assert res_mixed.is_plastic == res_kin.is_plastic, (
                f"step {i}: is_plastic disagreement "
                f"(mixed={res_mixed.is_plastic}, kin={res_kin.is_plastic})"
            )
            saw_plastic = saw_plastic or res_mixed.is_plastic
            if i >= n_fwd and res_mixed.is_plastic:
                saw_reverse_plastic = True

            max_diff = max(max_diff, float(np.max(np.abs(res_mixed.stress - res_kin.stress))))

        assert saw_plastic, "cyclic path never yielded (reduction vacuous)"
        assert saw_reverse_plastic, "reverse branch never re-yielded (Bauschinger unexercised)"
        assert max_diff < _KIN_REDUCTION_TOL_MPA, (
            f"K=0 mixed stress != kinematic: max diff {max_diff:.3e} MPa"
        )

    @pytest.mark.integration
    def test_generated_code_within_jit_budget(self) -> None:
        """Verifies: the transpiled mixed return-map stays within the JIT budget
        (07-CONVENTIONS <=512 lines per @ti.func). AC-4. Passes when: line count
        within budget AND the module is valid, callable Taichi code.
        """
        code = transpile_radial_return_j2_mixed(backend="taichi")

        # Must be syntactically valid Python and declare the entry point.
        tree = ast.parse(code)
        func_names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        assert "radial_return_j2_mixed" in func_names, (
            f"expected radial_return_j2_mixed entry point; emitted: {func_names}"
        )

        # JIT budget probe: the scalar return-map emits as a single plain function
        # (no @ti.func decorator on scalar algorithms), so the whole-module line
        # count is a strict overestimate of any single @ti.func body.
        line_count = len(code.splitlines())
        assert line_count <= JIT_BUDGET_LINES_PER_TI_FUNC, (
            f"emitted module {line_count} lines > {JIT_BUDGET_LINES_PER_TI_FUNC}"
        )
