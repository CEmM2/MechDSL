"""End-to-end tests for a LaTeX-derived HGO (anisotropic / fiber) solver (#288).

The anisotropic path is the new wiring: `compile_latex(..., energy_file=hgo.tex)`
detects the fiber pseudo-invariant `Ibar4`, derives an `AnisotropicEnergyModel`,
and the Taichi printer emits a full runnable solver whose constitutive law is the
fiber-gated `@ti.func` `constitutive_update(F, a, *params)` — the fiber direction
`a` gathered from the declared family at the call site (the field-gather the
straight-line emitter could not express) — and whose matrix-free `tangent_matvec`
linearises about the central-difference FD tangent (FD is robust across the
non-smooth Macaulay gate).

The slow gate mirrors the Ogden / Neo-Hookean E2Es: the generated `tangent_matvec`
must equal the central finite difference of `compute_internal_force` w.r.t. the
nodal displacements. The base deformation is a uniaxial stretch along the fiber so
the tension gate (`Ibar4 > 1`) is firmly open and the FD probes do not straddle the
non-smooth boundary. Pointwise stress agreement with the oracle is pinned by
`test_anisotropic_emission.py`.
"""

from __future__ import annotations

import py_compile
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

from mechdsl import compile_latex

if TYPE_CHECKING:
    from types import ModuleType

_EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples"
_HGO_TEX = _EXAMPLES_DIR / "hgo_energy.tex"

# Single-family HGO; fiber along x. The energy derives params {k1, k2, kappa, mu}.
_PARAM_VALUES = {"mu": 100.0, "kappa": 1000.0, "k1": 50.0, "k2": 5.0}
_DERIVED_PARAMS = ("k1", "k2", "kappa", "mu")

_PROBLEM_TEX = """% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material hgo --mu 100 --kappa 1000 --k1 50 --k2 5
% mechanics fiber --family "1, 0, 0"
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "0 0 -1000"
"""


def _compile_hgo_bundle():
    """Compile the HGO problem with the energy block auto-populated."""
    return compile_latex(_PROBLEM_TEX, energy_file=_HGO_TEX)


def _ordered_params() -> list[float]:
    """Material-parameter values in the derived (sorted-name) signature order."""
    return [_PARAM_VALUES[name] for name in _DERIVED_PARAMS]


# ---------------------------------------------------------------------------
# Fast tests — façade routing + emitted anisotropic vocabulary (no JIT)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_energy_file_routes_to_anisotropic_model():
    """`compile_latex(..., energy_file=hgo.tex)` attaches an AnisotropicEnergyModel
    and the emitted constitutive block is the fiber-gated path."""
    from mechdsl.symbolic.anisotropic_energy import AnisotropicEnergyModel

    bundle = _compile_hgo_bundle()
    assert isinstance(bundle.derived_energy, AnisotropicEnergyModel)
    assert "derived from LaTeX energy" in bundle.emitted_source
    assert "if ibar4 > 1.0:" in bundle.emitted_source


@pytest.mark.integration
def test_emitted_solver_gathers_fiber_and_is_parameterised(tmp_path):
    """The emitted solver gathers the fiber direction, speaks the HGO vocabulary,
    and byte-compiles."""
    src = _compile_hgo_bundle().emitted_source
    derived_sig = ", ".join(_DERIVED_PARAMS)

    assert f"def constitutive_update(F, a, {derived_sig}):" in src
    # Fiber direction gathered (family 0 = (1, 0, 0)) and passed to the func.
    assert "a_fiber = ti.Vector([1.0, 0.0, 0.0])" in src
    assert f"S = constitutive_update(F, a_fiber, {derived_sig})" in src
    # Host FD tangent calls the fiber-aware host PK2 helper.
    assert "def _pk2_anisotropic(E, a, " in src
    assert "a_fiber = np.array([1.0, 0.0, 0.0]" in src
    assert "dS = (_S_plus - _S_minus) / (2.0 * _fd_eps)" in src
    assert "lam_val" not in src

    out = tmp_path / "derived_hgo_solver.py"
    out.write_text(src, encoding="utf-8")
    py_compile.compile(str(out), doraise=True)


# ---------------------------------------------------------------------------
# Slow e2e tests — the generated solver actually runs under Taichi JIT
# ---------------------------------------------------------------------------


def _load_unit_cube(mod: ModuleType):
    """Allocate fields and load a single unit-cube Hex8 element into `mod`."""
    from tests.ref.ref_hex8_elastic import generate_hex8_mesh

    coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
    mod.allocate_fields(coords.shape[0], conn.shape[0])
    mod.x_ref.from_numpy(coords)
    for e in range(conn.shape[0]):
        for a in range(8):
            mod.elem_nodes[e, a] = int(conn[e, a])
    mod.f_ext.from_numpy(np.zeros_like(coords))
    return coords, conn


@pytest.mark.slow
@pytest.mark.e2e
class TestDerivedHGOSolverE2E:
    """The emitted HGO solver JIT-compiles, runs, and is self-consistent."""

    def test_tangent_matvec_matches_finite_difference(self, tmp_path):
        """Generated `tangent_matvec` == central FD of `compute_internal_force`.

        Gate for the HGO solver wiring: at a fiber-tension state (gate firmly
        open, so the FD probes stay on the smooth branch), the assembled `K @ v`
        (FD fiber tangent + geometric term) must match
        `[f_int(u + h v) - f_int(u - h v)] / (2 h)` for random directions `v`,
        exercising the fiber-gated device stress and the host FD tangent through
        the whole emitted program.
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from tests._e2e_helpers import _import_generated_module

        src = _compile_hgo_bundle().emitted_source
        mod = _import_generated_module(src, tmp_path, "derived_hgo_fd")
        coords, _ = _load_unit_cube(mod)
        n_dof = coords.shape[0] * 3
        params = _ordered_params()

        rng = np.random.default_rng(20260617)
        # Base state: ~6% uniaxial stretch along the fiber (x) keeps Ibar4 firmly
        # > 1 everywhere, so the Macaulay gate is open and smooth; a small random
        # perturbation exercises the off-axis tangent without crossing the gate.
        u = np.zeros((coords.shape[0], 3), dtype=np.float64)
        u[:, 0] = 0.06 * coords[:, 0]
        u += 0.01 * rng.standard_normal((coords.shape[0], 3))

        def f_int_at(u_state: np.ndarray) -> np.ndarray:
            mod.u.from_numpy(u_state)
            mod.compute_internal_force(*params)
            return mod.f_int.to_numpy().ravel().copy()

        h = 1e-6
        max_rel = 0.0
        for _ in range(4):
            v = rng.standard_normal(n_dof)
            v /= np.linalg.norm(v)
            v_mat = v.reshape((-1, 3))

            mod.u.from_numpy(u)
            kv = mod.tangent_matvec(v, *params)

            kv_fd = (f_int_at(u + h * v_mat) - f_int_at(u - h * v_mat)) / (2.0 * h)

            scale = max(1.0, float(np.linalg.norm(kv_fd)))
            max_rel = max(max_rel, float(np.linalg.norm(kv - kv_fd) / scale))

        assert max_rel < 1e-5, (
            f"HGO tangent_matvec vs finite-difference of f_int: "
            f"max rel-err {max_rel:.3e} >= 1e-5 (tangent/stress wiring inconsistent)"
        )

    def test_newton_solve_converges_to_nontrivial_solution(self, tmp_path):
        """The emitted `newton_solve` drives a derived-HGO problem to convergence."""
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from tests._e2e_helpers import _import_generated_module

        src = _compile_hgo_bundle().emitted_source
        mod = _import_generated_module(src, tmp_path, "derived_hgo_newton")
        coords, _ = _load_unit_cube(mod)

        bc_mask = np.zeros((coords.shape[0], 3), dtype=bool)
        left = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left, :] = True
        bc_dofs = np.where(bc_mask.ravel())[0].astype(np.int64)

        # Pull along the fiber (x) so the fiber term activates.
        f_ext = np.zeros((coords.shape[0], 3), dtype=np.float64)
        right = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]
        for n_idx in right:
            f_ext[n_idx, 0] = 5.0
        mod.f_ext.from_numpy(f_ext)

        n_iters = mod.newton_solve(*_ordered_params(), bc_dofs=bc_dofs)

        assert n_iters >= 1
        u_arr = mod.u.to_numpy()
        assert float(np.max(np.abs(u_arr))) > 1e-10, "displacement trivially zero"
