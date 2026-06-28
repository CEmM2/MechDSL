"""Tests for Task P6-1: J2 isotropic power-law return-map via algo2code.

The isotropic power-law hardening return-map (``sigma_y(alpha) = sigy0 + K
alpha^n``) is authored as algpseudocode in ``dev/algorithms/radial_return_j2.tex``
and transpiled to Taichi by algo2code. This file differential-tests the
transpiled scalar return-map against the hand-written ``models/j2_power_law.py``
oracle on a monotonic uniaxial path (< 1e-8), and pins transpile determinism.

Two INDEPENDENT computation paths are compared (NOT the same code run twice):

- Path (a): the algo2code-TRANSPILED scalar Newton loop. Exercised via
  ``mechdsl.lib.plasticity._radial_return_algo2code``, whose plastic-multiplier
  solve is the function emitted by ``transpile_radial_return_j2()`` (a fixed
  ``for k in range(1, max_iter)`` loop generated from the .tex), wrapped with
  Python tensor orchestration.
- Path (b): the hand-written ``j2_power_law.radial_return`` oracle, whose own
  ``while``-style Newton loop (with a convergence break) solves the same scalar
  problem independently.

The scalar return-map solve in path (a) comes solely from the transpiled module;
in path (b) it comes from the oracle's own Newton loop. The two share no scalar
solver. (Phase 2 was bitten by a tautological oracle that re-ran one code path;
this test deliberately drives two distinct solvers.)

Acceptance criteria:
- AC-1: Isotropic variant matches j2_power_law.py on a monotonic path < 1e-8.
- AC-2: Generated code within JIT budget (covered by algo2code codegen test).
- AC-3: Transpile is deterministic (golden-stable).
"""

from __future__ import annotations

import numpy as np
import pytest

from algo2code.library.radial_return_j2 import transpile_radial_return_j2
from mechdsl.lib.plasticity import (
    FEATURE_FLAG_ENV,
    _radial_return_algo2code,
)
from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
)
from mechdsl.symbolic.models.j2_power_law import (
    radial_return as oracle_radial_return,
)

# Acceptance tolerance from the plan (line 206) and AC-1.
ORACLE_TOL = 1e-8


def _material() -> J2PowerLawMaterial:
    """Power-law isotropic-hardening J2 material: sigma_y = 250 + 500*alpha^0.5."""
    return J2PowerLawMaterial(E=200_000.0, nu=0.3, sigma_y0=250.0, K=500.0, n=0.5)


def _uniaxial_strain(eps_axial: float) -> np.ndarray:
    """Isochoric-style uniaxial Green-Lagrange strain (axial + lateral)."""
    return np.diag([eps_axial, -0.5 * eps_axial, -0.5 * eps_axial]).astype(float)


class TestTaskP6_1:
    """Tests for Task P6-1: J2 isotropic power-law return-map via algo2code.

    AC covered here: AC-1 (oracle match), AC-3 (deterministic transpile).
    AC-2 (JIT budget / transpile validity) covered by
    packages/algo2code/tests/test_radial_return_codegen.py.
    """

    @pytest.mark.integration
    def test_monotonic_path_matches_j2_power_law_oracle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies: generated stress/tangent matches models/j2_power_law.py on a
        monotonic uniaxial path. AC-1. Passes when: max abs diff < 1e-8.

        Path (a) drives ``_radial_return_algo2code`` (the algo2code-transpiled
        scalar Newton loop); path (b) drives ``oracle_radial_return`` (the
        hand-written oracle's own Newton loop). The two scalar solvers are
        independent — only the surrounding NumPy tensor algebra is shared — so a
        non-zero error is observable if the transpiled loop ever diverges.
        """
        # Ensure path (a) really routes through the algo2code transpile, not the
        # imported fallback.
        monkeypatch.delenv(FEATURE_FLAG_ENV, raising=False)

        mat = _material()

        # Independent accumulated-plastic-strain history per path: each path
        # consumes ONLY its own alpha_new, so a divergence in either scalar
        # solver compounds and is detectable.
        alpha_algo = 0.0
        alpha_oracle = 0.0

        # Monotonically increasing uniaxial axial strain: elastic for the first
        # several steps, then sustained plastic flow with growing delta_lambda.
        saw_elastic = False
        saw_plastic = False
        max_diff = 0.0
        for i in range(1, 21):
            eps = 1e-4 * i  # strictly increasing → monotonic path
            E = _uniaxial_strain(eps)

            # Path (a): algo2code-transpiled scalar return-map.
            res_algo = _radial_return_algo2code(mat, E, alpha_algo)
            # Path (b): hand-written oracle.
            res_oracle = oracle_radial_return(mat, E, alpha_oracle)

            saw_elastic = saw_elastic or not res_oracle.is_plastic
            saw_plastic = saw_plastic or res_oracle.is_plastic

            # Plastic-flag agreement is a hard requirement at every step.
            assert res_algo.is_plastic == res_oracle.is_plastic, (
                f"step {i}: is_plastic disagreement "
                f"(algo={res_algo.is_plastic}, oracle={res_oracle.is_plastic})"
            )

            # PK2 stress parity.
            stress_diff = float(np.max(np.abs(res_algo.stress - res_oracle.stress)))
            # Algorithmic tangent parity.
            tangent_diff = float(np.max(np.abs(res_algo.tangent - res_oracle.tangent)))
            dl_diff = abs(res_algo.delta_lambda - res_oracle.delta_lambda)
            alpha_diff = abs(res_algo.alpha_new - res_oracle.alpha_new)

            step_max = max(stress_diff, tangent_diff, dl_diff, alpha_diff)
            max_diff = max(max_diff, step_max)

            assert step_max < ORACLE_TOL, (
                f"step {i} (eps={eps:.2e}): max abs diff {step_max:.3e} >= "
                f"{ORACLE_TOL:.1e} "
                f"(stress={stress_diff:.3e}, tangent={tangent_diff:.3e}, "
                f"dl={dl_diff:.3e}, alpha={alpha_diff:.3e})"
            )

            alpha_algo = res_algo.alpha_new
            alpha_oracle = res_oracle.alpha_new

        # The path must genuinely cross the yield surface — otherwise the test
        # would never exercise the plastic branch of the transpiled loop.
        assert saw_elastic, "monotonic path never had an elastic step"
        assert saw_plastic, "monotonic path never yielded — plastic branch untested"
        assert max_diff < ORACLE_TOL

    @pytest.mark.integration
    def test_transpile_is_deterministic(self) -> None:
        """Verifies: transpiling the radial_return_j2.tex twice yields
        byte-identical output. AC-3. Passes when: outputs are golden-stable."""
        first = transpile_radial_return_j2(backend="taichi")
        second = transpile_radial_return_j2(backend="taichi")
        assert first == second, "transpile output is not deterministic (byte-unstable)"
        # Sanity: the emitted module actually contains the power-law entry point.
        assert "def radial_return_j2(" in first, (
            "transpiled module missing radial_return_j2 entry point"
        )
