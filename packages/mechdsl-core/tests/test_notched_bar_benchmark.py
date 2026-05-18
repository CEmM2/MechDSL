"""Task P10-8: Notched bar benchmark (TL x Lemaitre damage x Hex8).

Extends the Phase 6 P6-3 unit test (Lemaitre damage localisation) to full
benchmark status: full mesh + parameter set locked in, load-displacement
history compared against a reference, damage-field localisation verified.

Acceptance criteria (dev/tasks/PLAN-B/json/P10-8.json):
  1. Load-displacement curve within 10% of reference.
  2. Damage localisation at the notch root (as in the Phase 6 unit test,
     but with the full benchmark geometry/parameter set).

Reference selection (explicit)
------------------------------
Canonical notched-bar damage benchmarks in the literature:

  [1] Lemaitre, J. (1985). "A continuous damage mechanics model for ductile
      fracture." ASME J. Eng. Mater. Technol., 107(1), 83-89 -- the
      original Lemaitre notched bar.
  [2] Lemaitre, J. & Desmorat, R. (2005). "Engineering Damage Mechanics",
      Springer -- textbook with notched-bar example around Fig. 2.29.
  [3] de Souza Neto, E., Peric, D. & Owen, D.R.J. (2008). "Computational
      Methods for Plasticity", Wiley, Ch. 12 -- detailed worked notched
      bar with Lemaitre damage.

None of these ships a mesh + parameter set + digitised load-displacement
curve we can lift verbatim; in particular, [2] Fig. 2.29 is drawn with
analog-redrawn axis scales, and [3]'s mesh data is tied to their in-house
code.

Per the P10-8 task plan and the MechDSL testing rules ("when a reference
curve is not available, use a self-consistent approach: document your
mesh + parameters + step schedule and store the resulting curve as the
reference; the tolerance then detects regressions rather than absolute
correctness"), we adopt the self-consistent approach:

  - Mesh = Phase 6 P6-3 geometry (6 x 3 x 1 Hex8, L=6 H=3 T=1,
    notch_depth=0.75, notch_halfwidth=1.0), which is the same mesh whose
    damage-localisation invariant is proven in P6-3.
  - Parameters = P6-3 parameters (documented below).
  - Reference load-displacement curve = the curve produced by this same
    harness at commit time, recorded to six significant figures.

Baseline capture notes
----------------------
Captured 2026-04-18 from this same module at the locked mesh + parameter
set.  Peak damage of D_max ~ 0.062 localises at notch-root element 14
(centroid just below the notch), consistent with the Phase 6 unit test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from mechdsl.verify.benchmarks import (
    build_notched_bar_mesh,
    run_notched_bar_benchmark,
)

if TYPE_CHECKING:
    from mechdsl.verify.benchmarks import BenchmarkResult


# ---------------------------------------------------------------------------
# Reference (self-consistent) mesh + parameters + load schedule
# ---------------------------------------------------------------------------

# Mesh: matches the P6-3 unit-test geometry exactly.
_N_LEN = 6
_N_HEIGHT = 3
_N_THICK = 1
_L = 6.0
_H = 3.0
_T = 1.0
_NOTCH_DEPTH = 0.75
_NOTCH_HALFWIDTH = 1.0

# Material (steel-like, MPa/mm), mirrors _lemaitre_acceptance defaults plus
# the P6-3 notched-bar overrides (linear hardening + active damage).
_MATERIAL = {
    "E": 200.0e3,  # MPa
    "nu": 0.3,
    "sigma_y0": 200.0,  # MPa
    "K": 100.0,  # MPa, linear hardening modulus
    "n": 1.0,  # linear hardening (n=1) -- see P6-3 docstring
    "S_d": 2.0,  # MPa, Lemaitre damage denominator
    "s_d": 1.0,  # linear damage evolution
    "eps_D": 0.0,  # damage active as soon as alpha > 0
    "D_crit": 0.95,
}

# Load schedule: 2% engineering strain in 8 equal steps (0.25% per step).
# Matches the P6-2 Gate B forward-warning that the undamaged-J2 tangent
# needs <=0.5 %/step for super-linear Newton convergence under active
# damage.
_TARGET_ENG_STRAIN = 0.02
_TOTAL_DISPLACEMENT = _TARGET_ENG_STRAIN * _L
_N_STEPS = 8
_NEWTON_TOL = 1e-7
_NEWTON_MAX_ITER = 40

# Reference load-displacement curve captured on 2026-04-18 from this very
# harness at the mesh + parameters + step schedule above.  Values are the
# sum of f_int[x=L face, component x] after every converged step, units =
# MPa * mm^2 = N (with L=6 mm, H=3 mm, T=1 mm the face area is 3 mm^2).
# Step 0 is the undeformed zero-load state; subsequent steps are equally
# spaced in applied displacement (0 -> _TOTAL_DISPLACEMENT).
_REFERENCE_DISPLACEMENT = np.array(
    [
        0.0,
        0.015,
        0.030,
        0.045,
        0.060,
        0.075,
        0.090,
        0.105,
        0.120,
    ],
    dtype=np.float64,
)
_REFERENCE_LOAD = np.array(
    [
        0.0,
        570.28345,
        587.78470,
        601.11349,
        614.43222,
        628.22324,
        642.52067,
        657.27557,
        672.38685,
    ],
    dtype=np.float64,
)

# Per-sample tolerance.  The task JSON specifies 10%.
_LOAD_TOL_REL = 0.10


# ---------------------------------------------------------------------------
# Module-scoped fixture: single expensive benchmark run shared by both tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def notched_bar_result(tmp_path_factory: pytest.TempPathFactory) -> BenchmarkResult:
    """Run the notched-bar benchmark once; share the result across tests."""
    tmp_path = tmp_path_factory.mktemp("p10_8_notched_bar")
    mesh = build_notched_bar_mesh(
        n_len=_N_LEN,
        n_height=_N_HEIGHT,
        n_thick=_N_THICK,
        L=_L,
        H=_H,
        T=_T,
        notch_depth=_NOTCH_DEPTH,
        notch_halfwidth=_NOTCH_HALFWIDTH,
    )
    return run_notched_bar_benchmark(
        mesh=mesh,
        material_params=_MATERIAL,
        total_displacement=_TOTAL_DISPLACEMENT,
        n_steps=_N_STEPS,
        tmp_path=tmp_path,
        newton_tol=_NEWTON_TOL,
        newton_max_iter=_NEWTON_MAX_ITER,
    )


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


class TestTaskP10_8:
    """Tests for Task P10-8: Notched bar benchmark (TL x Lemaitre x Hex8)."""

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_load_displacement_curve_within_10pct_of_reference(
        self, notched_bar_result: BenchmarkResult
    ) -> None:
        """Load-displacement curve within 10% of the locked reference.

        Compares ``load_history`` from the benchmark run against
        :data:`_REFERENCE_LOAD` at every recorded displacement sample
        (nine points total: zero-load start + eight load steps).  Step 0
        carries zero load in both arrays and is skipped from the relative-
        error check (division-by-zero guard).
        """
        disp_hist = notched_bar_result.extras["displacement_history"]
        load_hist = notched_bar_result.extras["load_history"]

        assert disp_hist.shape == _REFERENCE_DISPLACEMENT.shape, (
            f"displacement_history shape {disp_hist.shape} does not match "
            f"reference {_REFERENCE_DISPLACEMENT.shape}"
        )
        np.testing.assert_allclose(
            disp_hist,
            _REFERENCE_DISPLACEMENT,
            atol=1e-12,
            rtol=0.0,
            err_msg="Displacement schedule drifted from the locked reference.",
        )

        # Skip the zero-load starting point (rel-err undefined).
        nonzero = _REFERENCE_LOAD != 0.0
        rel_err = np.abs(load_hist[nonzero] - _REFERENCE_LOAD[nonzero]) / np.abs(
            _REFERENCE_LOAD[nonzero]
        )
        max_rel_err = float(rel_err.max())

        assert max_rel_err < _LOAD_TOL_REL, (
            f"Load-displacement curve exceeds {_LOAD_TOL_REL * 100:.1f}% tolerance "
            f"vs reference.\n"
            f"  max rel-err = {max_rel_err:.4f} at sample {int(np.argmax(rel_err))}\n"
            f"  reference load = {_REFERENCE_LOAD[nonzero].tolist()}\n"
            f"  actual    load = {load_hist[nonzero].tolist()}\n"
            f"  rel-err        = {rel_err.tolist()}"
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_damage_localises_at_notch_root(self, notched_bar_result: BenchmarkResult) -> None:
        """Peak damage localises at the notch root (full-benchmark variant).

        Mirrors the P6-3 unit-test invariant on the identical mesh:
          - ``max(damage_elem) > 0`` (damage actually grew -- guards against
            a vacuously-passing test if damage stays frozen at zero).
          - ``argmax(damage_elem)`` is within one face-neighbour hop of the
            geometric notch-root element (threshold: 1.5 * max-edge-length).
        """
        extras = notched_bar_result.extras
        max_damage = float(extras["max_damage"])
        argmax_elem = int(extras["damage_argmax_element"])
        near_notch = extras["near_notch_elements"]
        notch_root_elem = int(extras["notch_root_element"])
        dist = float(extras["distance_argmax_to_root"])
        h = float(extras["element_scale_h"])
        damage_elem = extras["damage_elem"]
        argmax_centroid = extras["damage_argmax_centroid"]
        notch_root_xyz = extras["notch_root_xyz"]

        # Vacuity guard: damage must actually have grown somewhere.
        assert max_damage > 0.0, (
            f"Lemaitre damage never activated; benchmark test is vacuous "
            f"(max_damage={max_damage:.3e})."
        )

        # Localisation: argmax must sit within one element hop of the root.
        assert argmax_elem in set(near_notch), (
            f"Damage did not localise at the notch root.\n"
            f"  argmax element = {argmax_elem} at centroid {argmax_centroid}"
            f" (D = {damage_elem[argmax_elem]:.3e})\n"
            f"  notch-root element = {notch_root_elem} at centroid "
            f"{notch_root_xyz} (D = {damage_elem[notch_root_elem]:.3e})\n"
            f"  near-notch elements = {near_notch}\n"
            f"  distance(argmax -> notch root) = {dist:.4f}  "
            f"(threshold 1.5*h = {1.5 * h:.4f})\n"
            f"  per-element damage = {np.asarray(damage_elem).tolist()}"
        )

        # Damage drops off with distance from the notch root: argmax must
        # strictly exceed the weakest element (``argmin(damage_elem)``).
        far_idx = int(np.argmin(damage_elem))
        assert damage_elem[argmax_elem] > damage_elem[far_idx], (
            f"Peak damage does not exceed the weakest element:\n"
            f"  D(argmax e={argmax_elem}) = {damage_elem[argmax_elem]:.3e}\n"
            f"  D(far    e={far_idx})     = {damage_elem[far_idx]:.3e}"
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_benchmark_records_expected_extras(self, notched_bar_result: BenchmarkResult) -> None:
        """The orchestrator must populate every key consumed by downstream P10 tests.

        This guards against silent regressions in the benchmark contract;
        if a future refactor drops ``load_history`` or renames
        ``damage_argmax_element``, the other two tests here might still
        pass on a stub, so this test checks the surface area explicitly.
        """
        extras = notched_bar_result.extras
        expected_keys = {
            "displacement_history",
            "load_history",
            "max_damage",
            "damage_elem",
            "damage_argmax_element",
            "damage_argmax_centroid",
            "notch_root_xyz",
            "notch_root_element",
            "near_notch_elements",
            "distance_argmax_to_root",
            "element_scale_h",
        }
        missing = expected_keys - set(extras)
        assert not missing, f"BenchmarkResult.extras missing keys: {sorted(missing)}"

        assert notched_bar_result.newton_iters == _N_STEPS
        assert notched_bar_result.wallclock_s > 0.0
        assert notched_bar_result.displacements.shape[1] == 3
