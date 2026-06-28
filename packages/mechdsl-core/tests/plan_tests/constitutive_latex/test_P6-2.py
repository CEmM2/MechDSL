"""Tests for Task P6-2: J2 kinematic linear hardening + numpy reference (cyclic).

The J2 linear kinematic (Prager) hardening return-map is authored as
algpseudocode in ``dev/algorithms/radial_return_j2_kinematic.tex`` and transpiled
to Taichi by algo2code. The yield surface *translates* (back-stress ``beta``)
rather than *expands*: yield is on the RELATIVE stress ``xi = dev(S) - beta`` with
a constant radius ``sigma_y0``. There is NO existing mechdsl oracle for kinematic
hardening, so a small, independent numpy 1D-cyclic reference lives in
``packages/mechdsl-core/tests/ref/ref_j2_kinematic.py``.

Two INDEPENDENT computation paths are compared (NOT the same code run twice):

- Path (a): the algo2code-TRANSPILED scalar plastic-multiplier solve, wrapped by
  the 3D tensor orchestration in ``mechdsl.lib.plasticity_kinematic`` (deviatoric
  split, relative stress, von Mises of ``xi``, Prager tensor back-stress + plastic
  strain update, algorithmic tangent). This is a finite-strain SVK radial return.
- Path (b): the hand-written 1D bilinear kinematic model in
  ``ref_j2_kinematic.py`` — classical scalar (sigma, eps) plasticity. It shares no
  code with path (a): different state (scalar q/ep vs tensor beta/Ep), different
  algebra (1D Hooke vs deviatoric tensor return), no shared scalar solver.

The two paths agree only because they encode the same *physics*, integrated by
different algebra — the genuine differential test the plan (lines 200, 207) calls
for. (Phase 2 was bitten by a tautological oracle re-running one code path; this
test deliberately drives two distinct integrators.)

Acceptance criteria:
- AC-1: Kinematic variant matches the numpy reference on a cyclic path.
- AC-2: Bauschinger effect demonstrated on the cyclic path.
- AC-3: Generated code within JIT budget.
"""

from __future__ import annotations

import ast

import numpy as np
import pytest

from algo2code.library.radial_return_j2_kinematic import (
    transpile_radial_return_j2_kinematic,
)
from mechdsl.lib.plasticity_kinematic import (
    J2KinematicMaterial,
    radial_return_kinematic,
)
from tests.ref.ref_j2_kinematic import (
    Bilinear1D,
    analytic_bilinear_landmarks,
    simulate_uniaxial_cyclic,
)

# Material parameters shared across tests.
_E = 200_000.0
_NU = 0.3
_MU = _E / (2.0 * (1.0 + _NU))
_SIGMA_Y0 = 250.0
_H_KIN = 20_000.0

# Cyclic-path differential-test tolerance.
#
# Both integrators are EXACT for the bilinear kinematic response: each strain
# increment is a single closed-form return step (the consistency residual is
# linear in dl), and within each monotone segment the response is path-history-
# independent. So the 3D deviatoric return and the 1D bilinear agree to machine
# precision regardless of step count (verified: max diff 0.0 at 200 / 800 / 3200
# steps; the relative-stress norm ||xi||_eq sits at exactly sigma_y0 on every
# plastic step, confirming the return map truly returns to the surface).
#
# The tolerance is therefore tight — 1e-6 MPa, ~4e-9 of the ~300 MPa peak. A
# WRONG transpile (mis-scaled dl) or a wrong flow-normal normalisation would
# leave ||xi||_eq off the yield surface and shift the curve by tens of MPa,
# blowing past this bound. This is a strict, non-tautological gate: the two paths
# share no code, yet a physics error in either surfaces immediately.
_CYCLIC_TOL_MPA = 1e-6

JIT_BUDGET_LINES_PER_TI_FUNC = 512  # 07-CONVENTIONS.md


def _material() -> J2KinematicMaterial:
    return J2KinematicMaterial(E=_E, nu=_NU, sigma_y0=_SIGMA_Y0, H_kin=_H_KIN)


def _reference() -> Bilinear1D:
    """1D bilinear analog of the 3D kinematic model on a deviatoric uniaxial path.

    Effective deviatoric parameters: E_1d = 3*mu (signed von-Mises trial slope vs
    the axial deviatoric strain), H_1d = H_kin (Prager), Y = sigma_y0.
    """
    return Bilinear1D(E=3.0 * _MU, H=_H_KIN, sigma_y0=_SIGMA_Y0)


def _cyclic_strain_path(eps_peak: float = 0.004, n_fwd: int = 800) -> np.ndarray:
    """Uniaxial cyclic strain amplitudes: load -> reverse -> reload."""
    fwd = np.linspace(0.0, eps_peak, n_fwd)
    rev = np.linspace(eps_peak, -eps_peak, 2 * n_fwd)
    reload_ = np.linspace(-eps_peak, eps_peak, 2 * n_fwd)
    return np.concatenate([fwd, rev[1:], reload_[1:]])


def _drive_3d_eq_stress(path: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Drive the 3D orchestration on a deviatoric uniaxial path.

    For ``E = diag(e, -e/2, -e/2)`` (traceless) the elastic predictor is purely
    deviatoric, with no volumetric / lateral-strain coupling. The comparable
    signed von-Mises equivalent stress is recovered as ``1.5 * dev(S)[0,0]`` (for
    a uniaxial deviatoric tensor the axial component scales to the equivalent
    stress by 3/2), giving the exact 1D analog the reference integrates.

    Returns
    -------
    (signed_eq_stress, is_plastic) arrays aligned with ``path``.
    """
    mat = _material()
    Ep = np.zeros((3, 3))
    beta = np.zeros((3, 3))
    eq_stress = np.empty(path.size, dtype=np.float64)
    plastic = np.empty(path.size, dtype=bool)
    for i, e in enumerate(path):
        E_strain = np.diag([e, -0.5 * e, -0.5 * e]).astype(float)
        res = radial_return_kinematic(mat, E_strain, Ep, beta)
        Ep = res.plastic_strain
        beta = res.back_stress
        s_dev = res.stress - (np.trace(res.stress) / 3.0) * np.eye(3)
        eq_stress[i] = 1.5 * s_dev[0, 0]
        plastic[i] = res.is_plastic
    return eq_stress, plastic


class TestTaskP6_2J2Kinematic:
    """Tests for Task P6-2: J2 kinematic linear hardening + numpy reference.

    AC covered: AC-1 (reference match), AC-2 (Bauschinger), AC-3 (JIT budget).

    Class name carries the ``J2`` token so the plan's verification command
    ``pytest -k 'j2 and (kinematic or cyclic)'`` selects these tests.
    """

    @pytest.mark.integration
    def test_numpy_reference_cross_validates_analytically(self) -> None:
        """Verifies: the self-authored numpy reference matches a hand-computable
        analytical cyclic segment. AC-1 (guards a wrong oracle). Passes when: the
        simulated bilinear response reproduces the closed-form landmarks
        (first-yield, post-yield tangent, forward back-stress, reverse-yield).

        This runs FIRST conceptually: it is what makes the reference trustworthy
        ground truth before it is used to validate the transpile.
        """
        model = _reference()
        eps_peak = 0.004
        landmarks = analytic_bilinear_landmarks(model, eps_peak=eps_peak)

        # Sanity: the peak strain is genuinely past yield (otherwise the landmark
        # formulas, which assume plastic flow, are vacuous).
        assert eps_peak > landmarks["eps_yield"], "peak strain below yield"

        # Forward monotonic load to the peak.
        fwd = np.linspace(0.0, eps_peak, 4000)
        res = simulate_uniaxial_cyclic(model, fwd)

        # (1) First-yield stress == sigma_y0 (constant radius, no isotropic part).
        first_plastic = int(np.argmax(res["is_plastic"]))
        assert res["is_plastic"][first_plastic], "path never yielded"
        sigma_at_yield = res["stress"][first_plastic - 1]
        assert abs(sigma_at_yield - landmarks["sigma_yield"]) < 1.0, (
            f"first-yield stress {sigma_at_yield:.3f} != {landmarks['sigma_yield']:.3f}"
        )

        # (2) Post-yield tangent modulus E_t = E*H/(E+H), fit on the plastic
        # segment.
        plastic_mask = res["is_plastic"]
        slope = np.polyfit(fwd[plastic_mask], res["stress"][plastic_mask], 1)[0]
        assert abs(slope - landmarks["E_tangent"]) < 1e-6 * landmarks["E_tangent"], (
            f"E_t {slope:.6f} != analytic {landmarks['E_tangent']:.6f}"
        )

        # (3) Forward peak stress and back-stress.
        assert abs(res["stress"][-1] - landmarks["sigma_peak"]) < 1e-8, (
            f"peak stress {res['stress'][-1]:.6f} != {landmarks['sigma_peak']:.6f}"
        )
        assert abs(res["back_stress"][-1] - landmarks["back_stress_peak"]) < 1e-8, (
            f"peak back-stress {res['back_stress'][-1]:.6f} != {landmarks['back_stress_peak']:.6f}"
        )

        # (4) Reverse-yield stress == q_f - sigma_y0 (Bauschinger center shift).
        full = np.concatenate([fwd, np.linspace(eps_peak, -eps_peak, 8000)[1:]])
        res_full = simulate_uniaxial_cyclic(model, full)
        n_fwd = fwd.size
        reverse_plastic = [
            i
            for i in range(n_fwd, full.size)
            if res_full["is_plastic"][i] and res_full["stress"][i] < landmarks["sigma_peak"] - 1.0
        ]
        assert reverse_plastic, "reverse branch never re-yielded"
        ri = reverse_plastic[0]
        sigma_reverse = res_full["stress"][ri]
        assert abs(sigma_reverse - landmarks["sigma_reverse"]) < 1.0, (
            f"reverse-yield stress {sigma_reverse:.3f} != analytic {landmarks['sigma_reverse']:.3f}"
        )

    @pytest.mark.integration
    def test_cyclic_path_matches_numpy_reference(self) -> None:
        """Verifies: generated kinematic stress matches the new numpy 1D-cyclic
        reference on a loading/unloading/reverse path. AC-1. Passes when: max abs
        diff within tolerance.

        Path (a) drives ``radial_return_kinematic`` (algo2code-transpiled scalar
        solve + 3D Prager tensor orchestration); path (b) drives
        ``simulate_uniaxial_cyclic`` (independent 1D bilinear). They share no code.
        """
        path = _cyclic_strain_path()

        # Path (a): 3D orchestration.
        eq_stress_3d, plastic_3d = _drive_3d_eq_stress(path)

        # Path (b): independent 1D reference.
        ref = simulate_uniaxial_cyclic(_reference(), path)
        stress_1d = ref["stress"]

        # The path must genuinely yield in both forward and reverse — otherwise
        # the plastic branch of the transpiled solve is never exercised.
        assert plastic_3d.any(), "3D path never yielded"
        assert (~plastic_3d).any(), "3D path never had an elastic step"

        max_diff = float(np.max(np.abs(eq_stress_3d - stress_1d)))
        assert max_diff < _CYCLIC_TOL_MPA, (
            f"max |3D - 1D| = {max_diff:.4f} MPa >= {_CYCLIC_TOL_MPA} MPa "
            f"(3D peak {eq_stress_3d.max():.2f}, 1D peak {stress_1d.max():.2f})"
        )

    @pytest.mark.integration
    def test_bauschinger_effect_present(self) -> None:
        """Verifies: reverse-yield magnitude is below the forward yield magnitude
        on the cyclic path (Bauschinger). AC-2. Passes when: reverse yield <
        forward yield — which the isotropic model cannot show.

        Asserted on path (a), the algo2code-transpiled 3D kinematic path, so the
        Bauschinger signal is a property of the generated code, not just the
        reference.
        """
        path = _cyclic_strain_path()
        eq_stress, plastic = _drive_3d_eq_stress(path)

        # Forward yield magnitude: the equivalent stress at first yield equals
        # sigma_y0 (constant radius). Take the forward peak as the reference
        # forward magnitude.
        n_fwd = 800
        forward_peak = float(np.max(eq_stress[:n_fwd]))
        assert forward_peak > _SIGMA_Y0, "forward path never exceeded initial yield"

        # Reverse re-yield: first plastic step on the reverse branch where the
        # (now negative) equivalent stress drops below the forward peak.
        reverse_yield_indices = [
            i
            for i in range(n_fwd, path.size)
            if plastic[i] and eq_stress[i] < forward_peak - 1.0 and eq_stress[i] < 0.0
        ]
        assert reverse_yield_indices, "reverse branch never re-yielded"
        reverse_yield_stress = abs(eq_stress[reverse_yield_indices[0]])

        # Bauschinger: the material re-yields in reverse at a magnitude BELOW the
        # initial forward yield stress sigma_y0. (Isotropic hardening would push
        # reverse yield ABOVE sigma_y0.)
        assert reverse_yield_stress < _SIGMA_Y0, (
            f"no Bauschinger effect: reverse-yield |sigma| = "
            f"{reverse_yield_stress:.2f} >= forward yield {_SIGMA_Y0:.2f}"
        )

    @pytest.mark.integration
    def test_multiaxial_shear_state_returns_to_yield_surface(self) -> None:
        """Verifies the 3D tensor return on a GENERAL multi-axial strain state
        with shear, not just the uniaxial deviatoric path the cyclic test uses.

        A uniaxial path keeps the back-stress diagonal, so off-diagonal (shear)
        errors in the Prager update or the consistency return can hide. Driving a
        symmetric strain with non-zero shear components exercises every tensor
        component. Two oracle-free invariants must hold on each plastic step:

        1. Consistency: the return lands ON the (constant) yield surface, i.e.
           ``||dev(S) - beta||_eq == sigma_y0`` to machine precision. A wrong
           shear-component update would leave the relative stress off the surface.
        2. The back-stress ``beta`` and plastic strain ``Ep`` stay symmetric and
           deviatoric (traceless) — J2 plastic flow is isochoric.

        The algorithmic tangent must retain minor and major symmetry. And the
        path must develop genuinely non-zero off-diagonal back-stress, otherwise
        the shear directions were never exercised.
        """
        mat = _material()

        def _dev(t: np.ndarray) -> np.ndarray:
            return t - (np.trace(t) / 3.0) * np.eye(3)

        def _eq(s: np.ndarray) -> float:
            return float(np.sqrt(1.5 * np.tensordot(s, s, axes=2)))

        # Symmetric strain direction with normal AND shear components.
        direction = np.array(
            [
                [1.0, 0.45, 0.20],
                [0.45, -0.30, 0.55],
                [0.20, 0.55, -0.70],
            ]
        )
        assert np.allclose(direction, direction.T), "strain direction must be symmetric"

        Ep = np.zeros((3, 3))
        beta = np.zeros((3, 3))
        saw_plastic = False
        for i in range(1, 13):
            E_strain = (1e-3 * i) * direction
            res = radial_return_kinematic(mat, E_strain, Ep, beta)
            Ep = res.plastic_strain
            beta = res.back_stress

            # beta and Ep symmetric + deviatoric on every step.
            assert np.allclose(beta, beta.T, atol=1e-9), f"step {i}: beta not symmetric"
            assert abs(np.trace(beta)) < 1e-7, f"step {i}: beta not deviatoric"
            assert np.allclose(Ep, Ep.T, atol=1e-12), f"step {i}: Ep not symmetric"
            assert abs(np.trace(Ep)) < 1e-12, f"step {i}: Ep not deviatoric (J2 isochoric)"

            if res.is_plastic:
                saw_plastic = True
                # (1) Consistency: relative stress sits on the constant radius.
                xi_eq = _eq(_dev(res.stress) - beta)
                assert abs(xi_eq - _SIGMA_Y0) < 1e-7, (
                    f"step {i}: ||dev(S)-beta||_eq = {xi_eq:.6f} off the yield "
                    f"surface {_SIGMA_Y0:.6f} (shear-component return error)"
                )
                # Tangent symmetries (minor + major).
                C = res.tangent
                assert np.allclose(C, np.swapaxes(C, 0, 1), rtol=1e-9, atol=1e-6), (
                    f"step {i}: tangent lacks minor symmetry (ij)"
                )
                assert np.allclose(C, np.swapaxes(C, 2, 3), rtol=1e-9, atol=1e-6), (
                    f"step {i}: tangent lacks minor symmetry (kl)"
                )
                assert np.allclose(C, np.transpose(C, (2, 3, 0, 1)), rtol=1e-9, atol=1e-6), (
                    f"step {i}: tangent lacks major symmetry"
                )

        assert saw_plastic, "multi-axial path never yielded — shear return untested"
        # The shear directions must have genuinely loaded the back-stress: at least
        # one off-diagonal component is non-trivially non-zero.
        off_diag_max = max(abs(beta[0, 1]), abs(beta[0, 2]), abs(beta[1, 2]))
        assert off_diag_max > 1.0, (
            f"off-diagonal back-stress never developed (max |beta_ij<i!=j>| = "
            f"{off_diag_max:.3e}); shear components were not exercised"
        )

    @pytest.mark.integration
    def test_generated_code_within_jit_budget(self) -> None:
        """Verifies: the transpiled kinematic return-map stays within the JIT
        budget (07-CONVENTIONS <=512 lines per @ti.func). AC-3. Passes when: line
        count within budget AND the module is valid, callable Taichi code.
        """
        code = transpile_radial_return_j2_kinematic(backend="taichi")

        # Must be syntactically valid Python and declare the entry point.
        tree = ast.parse(code)
        func_names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        assert "radial_return_j2_kinematic" in func_names, (
            f"expected radial_return_j2_kinematic entry point; emitted: {func_names}"
        )

        # JIT budget probe: the longest @ti.func body must stay within budget. The
        # scalar return-map emits as a single plain function (no @ti.func decorator
        # on scalar algorithms), so the whole-module line count is a strict
        # overestimate of any single @ti.func body — a conservative proxy.
        line_count = len(code.splitlines())
        assert line_count <= JIT_BUDGET_LINES_PER_TI_FUNC, (
            f"emitted module {line_count} lines > {JIT_BUDGET_LINES_PER_TI_FUNC}"
        )
