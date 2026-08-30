"""End-to-end tests for a LaTeX-derived Ogden (spectral) constitutive solver (#288).

The spectral path is the new wiring: `compile_latex(..., energy_file=ogden.tex)`
detects the principal-stretch authoring, derives a `SpectralEnergyModel`, and the
Taichi printer emits a full runnable solver whose constitutive law is the
symmetric-eigensolver + principal-stress reassembly `@ti.func`, and whose
matrix-free `tangent_matvec` linearises about the central-difference FD tangent
(the spectral tangent has no stable closed form).

The slow gate mirrors the Neo-Hookean E2E (`test_derived_solver_e2e.py`): the
generated `tangent_matvec` must equal the central finite difference of
`compute_internal_force` w.r.t. the nodal displacements -- exercising the derived
spectral stress (inside `compute_internal_force`, via the device eigensolver) and
the derived FD tangent (inside `tangent_matvec`, via the host eigensolver) through
the whole emitted program. Pointwise stress agreement with the oracle is already
pinned by `test_spectral_eigensolver.py`.
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
_OGDEN_TEX = _EXAMPLES_DIR / "ogden_energy.tex"

# Two-term compressible Ogden. Positive exponents keep the directive scalars free
# of leading-dash tokens (the arg parser would read `--eta -2` ambiguously) while
# still exercising both Ogden terms; the physics validity (J>0) is what matters,
# the gate is self-consistency, not a specific material.
_PARAM_VALUES = {"mu": 80.0, "alpha": 2.0, "nu": 20.0, "eta": 1.3, "kappa": 1000.0}
# The spectral energy derives parameters sorted by name; the whole solver speaks
# this vocabulary. Kept explicit so the tests assert the emitted order.
_DERIVED_PARAMS = ("alpha", "eta", "kappa", "mu", "nu")

_PROBLEM_TEX = """% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material ogden --mu 80 --alpha 2.0 --nu 20 --eta 1.3 --kappa 1000
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "0 0 -1000"
"""


def _compile_ogden_bundle():
    """Compile the Ogden problem with the energy block auto-populated."""
    return compile_latex(_PROBLEM_TEX, energy_file=_OGDEN_TEX)


def _ordered_params() -> list[float]:
    """Material-parameter values in the derived (sorted-name) signature order."""
    return [_PARAM_VALUES[name] for name in _DERIVED_PARAMS]


# ---------------------------------------------------------------------------
# Fast tests — façade routing + emitted spectral vocabulary (no JIT)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_energy_file_routes_to_spectral_model():
    """`compile_latex(..., energy_file=ogden.tex)` attaches a SpectralEnergyModel
    and the emitted constitutive block is the spectral (eigensolver) path."""
    from mechdsl.symbolic.spectral_energy import SpectralEnergyModel

    bundle = _compile_ogden_bundle()
    assert isinstance(bundle.derived_energy, SpectralEnergyModel)
    assert "derived from LaTeX energy" in bundle.emitted_source
    assert "def sym_eig_3x3(A):" in bundle.emitted_source


@pytest.mark.integration
def test_emitted_solver_parameterised_on_spectral_params(tmp_path):
    """The whole emitted solver speaks the derived Ogden vocabulary and byte-compiles."""
    src = _compile_ogden_bundle().emitted_source
    derived_sig = ", ".join(_DERIVED_PARAMS)

    assert f"def constitutive_update(F, {derived_sig}):" in src
    assert f"def compute_internal_force({_DERIVED_PARAMS[0]}: ti.f64" in src
    assert f"S = constitutive_update(F, {derived_sig})" in src
    assert f"def tangent_matvec(v_flat: np.ndarray, {_DERIVED_PARAMS[0]}: float" in src
    assert f"def newton_solve({_DERIVED_PARAMS[0]}: float" in src
    # Spectral tangent is FD of the host PK2 helper, not a closed-form C : dE.
    assert "def _pk2_spectral(E, " in src
    assert "dS = (_S_plus - _S_minus) / (2.0 * _fd_eps)" in src
    # The derived program must not fall back to the SVK Lamé plumbing.
    assert "lam_val" not in src

    out = tmp_path / "derived_ogden_solver.py"
    out.write_text(src, encoding="utf-8")
    py_compile.compile(str(out), doraise=True)


# ---------------------------------------------------------------------------
# Slow e2e tests — the generated solver runs under Taichi JIT (the real gate)
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
class TestDerivedOgdenSolverE2E:
    """The emitted Ogden solver JIT-compiles, runs, and is self-consistent."""

    def test_tangent_matvec_matches_finite_difference(self, tmp_path):
        """Generated `tangent_matvec` == central FD of `compute_internal_force`.

        Gate for the spectral solver wiring: at a deformed state, the assembled
        `K @ v` (FD spectral tangent + geometric term) must match
        `[f_int(u + h v) - f_int(u - h v)] / (2 h)` for random directions `v`,
        exercising the device eigensolver stress and the host FD tangent through
        the full emitted program.
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from tests._e2e_helpers import _import_generated_module

        src = _compile_ogden_bundle().emitted_source
        mod = _import_generated_module(src, tmp_path, "derived_ogden_fd")
        coords, _ = _load_unit_cube(mod)
        n_dof = coords.shape[0] * 3
        params = _ordered_params()

        rng = np.random.default_rng(20260617)
        # Non-trivial deformed state (~3% strain): well inside Ogden validity,
        # large enough to exercise the geometric + material tangent.
        u = 0.03 * rng.standard_normal((coords.shape[0], 3))

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
            f"spectral tangent_matvec vs finite-difference of f_int: "
            f"max rel-err {max_rel:.3e} >= 1e-5 (tangent/stress wiring inconsistent)"
        )

    def test_newton_solve_converges_to_nontrivial_solution(self, tmp_path):
        """The emitted `newton_solve` drives a derived-Ogden problem to convergence."""
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from tests._e2e_helpers import _import_generated_module

        src = _compile_ogden_bundle().emitted_source
        mod = _import_generated_module(src, tmp_path, "derived_ogden_newton")
        coords, _ = _load_unit_cube(mod)

        bc_mask = np.zeros((coords.shape[0], 3), dtype=bool)
        left = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left, :] = True
        bc_dofs = np.where(bc_mask.ravel())[0].astype(np.int64)

        f_ext = np.zeros((coords.shape[0], 3), dtype=np.float64)
        right = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]
        for n_idx in right:
            f_ext[n_idx, 0] = 5.0
        mod.f_ext.from_numpy(f_ext)

        n_iters = mod.newton_solve(*_ordered_params(), bc_dofs=bc_dofs)

        assert n_iters >= 1
        u_arr = mod.u.to_numpy()
        assert float(np.max(np.abs(u_arr))) > 1e-10, "displacement trivially zero"
