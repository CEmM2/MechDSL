"""End-to-end tests for a LaTeX-derived constitutive solver.

These cover the two production-wiring follow-ups deferred at the end of Phase 3
(see ``dev/tasks/constitutive_latex/Handoff_Phase_4.md`` "Known Issues"):

1. ``compile_latex`` façade auto-population — passing a strain-energy block
   (``energy_source`` / ``energy_file``) derives the symbolic stress + tangent
   and attaches them to the ``ProblemIR`` as ``derived_energy``.
2. Derived-parameter plumbing end-to-end — the generated solver
   (``compute_internal_force`` / ``tangent_matvec`` / ``newton_solve`` /
   ``__main__``) is parameterised on the energy's own material-parameter names
   (Neo-Hookean: ``kappa, mu``) instead of the named-model ``(lam, mu)`` vocab,
   and ``tangent_matvec`` linearises about the derived rank-4 tangent
   (``dS = C_IJKL : dE``) rather than the SVK closed form.

The slow gate is reference-free and rigorous: the generated ``tangent_matvec``
must equal the central finite difference of ``compute_internal_force`` w.r.t. the
nodal displacements. That simultaneously exercises the derived stress (inside
``compute_internal_force``) and the derived tangent (inside ``tangent_matvec``)
through the *whole* emitted program, so any parameter-plumbing or ``C : dE``
wiring error shows up as an inconsistency. Pointwise agreement of the derived
stress/tangent with the ``neo_hookean.py`` oracle is already pinned by
``test_P3-3.py``.
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

_EXAMPLES_DIR = Path(__file__).resolve().parents[5] / "dev" / "examples"
_NH_TEX = _EXAMPLES_DIR / "neo_hookean_energy.tex"

# Material parameters (match test_P3-3.py). mu = shear, kappa = bulk modulus.
_MU = 80.0
_KAPPA = 160.0

# The Neo-Hookean energy derives parameters {kappa, mu}; the generated solver is
# parameterised on this sorted list. Kept explicit so the tests assert the exact
# emitted vocabulary rather than re-deriving it.
_DERIVED_PARAMS = ("kappa", "mu")

_PROBLEM_TEX = """% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material neo_hookean --mu 80 --kappa 160
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "0 0 -1000"
"""


def _compile_derived_bundle():
    """Compile the Neo-Hookean problem with the energy block auto-populated."""
    return compile_latex(_PROBLEM_TEX, energy_file=_NH_TEX)


# ---------------------------------------------------------------------------
# Fast tests — façade auto-population + emitted param vocabulary (no JIT)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_energy_file_populates_derived_energy():
    """``compile_latex(..., energy_file=...)`` attaches a derived energy model.

    Passes when: the bundle carries a non-None ``derived_energy`` whose PK2 and
    tangent are present, and the emitted constitutive block is routed through the
    derived branch (its banner), not the named-model SVK switch.
    """
    bundle = _compile_derived_bundle()
    assert bundle.derived_energy is not None
    assert hasattr(bundle.derived_energy, "pk2")
    assert hasattr(bundle.derived_energy, "tangent")
    assert "derived from LaTeX energy" in bundle.emitted_source


@pytest.mark.integration
def test_energy_source_string_matches_energy_file():
    """The ``energy_source`` string path is equivalent to ``energy_file``.

    Passes when: passing the energy ``.tex`` text via ``energy_source`` produces
    the same emitted source as reading it via ``energy_file``.
    """
    by_file = compile_latex(_PROBLEM_TEX, energy_file=_NH_TEX)
    by_str = compile_latex(_PROBLEM_TEX, energy_source=_NH_TEX.read_text())
    assert by_str.derived_energy is not None
    assert by_str.emitted_source == by_file.emitted_source


@pytest.mark.unit
def test_energy_source_and_file_are_mutually_exclusive():
    """Supplying both ``energy_source`` and ``energy_file`` is rejected.

    Passes when: a ValueError naming both options is raised before any work.
    """
    with pytest.raises(ValueError, match="at most one of energy_source / energy_file"):
        compile_latex(_PROBLEM_TEX, energy_source="x", energy_file=_NH_TEX)


@pytest.mark.integration
def test_emitted_solver_parameterised_on_derived_params(tmp_path):
    """The whole emitted solver speaks the derived ``(kappa, mu)`` vocabulary.

    Passes when: the constitutive / internal-force / tangent-matvec / newton-solve
    signatures all carry the derived params, the derived tangent contraction
    ``dS = C : dE`` is present, no stray named-model ``lam``/``mu_val`` Lamé
    plumbing leaks into the derived program, and the source byte-compiles.
    """
    src = _compile_derived_bundle().emitted_source
    derived_sig = ", ".join(_DERIVED_PARAMS)

    assert f"def constitutive_update(F, {derived_sig}):" in src
    assert f"def compute_internal_force({_DERIVED_PARAMS[0]}: ti.f64" in src
    assert f"S = constitutive_update(F, {derived_sig})" in src
    assert f"def tangent_matvec(v_flat: np.ndarray, {_DERIVED_PARAMS[0]}: float" in src
    assert f"def newton_solve({_DERIVED_PARAMS[0]}: float" in src
    assert "dS = np.einsum('ijkl,kl->ij', C4, dE)" in src
    # The derived program must not fall back to the SVK Lamé plumbing.
    assert "lam_val" not in src
    assert "lam, mu : float" not in src

    out = tmp_path / "derived_nh_solver.py"
    out.write_text(src, encoding="utf-8")
    py_compile.compile(str(out), doraise=True)


# ---------------------------------------------------------------------------
# Slow e2e tests — the generated solver runs under Taichi JIT (the real gate)
# ---------------------------------------------------------------------------


def _load_unit_cube(mod: ModuleType):
    """Allocate fields and load a single unit-cube Hex8 element into ``mod``."""
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
class TestDerivedNeoHookeanSolverE2E:
    """The emitted Neo-Hookean solver JIT-compiles, runs, and is self-consistent."""

    def test_tangent_matvec_matches_finite_difference(self, tmp_path):
        """Generated ``tangent_matvec`` == central FD of ``compute_internal_force``.

        This is the gate for the derived-tangent wiring: at a non-trivial
        deformed state, the analytic ``K @ v`` (derived rank-4 ``C : dE``) must
        match ``[f_int(u + h v) - f_int(u - h v)] / (2 h)`` for random directions
        ``v``. It exercises the derived stress (in ``compute_internal_force``) and
        the derived tangent (in ``tangent_matvec``) through the full emitted
        program, so any parameter-plumbing or contraction error surfaces here.
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from tests._e2e_helpers import _import_generated_module

        src = _compile_derived_bundle().emitted_source
        mod = _import_generated_module(src, tmp_path, "derived_nh_fd")
        coords, _ = _load_unit_cube(mod)
        n_dof = coords.shape[0] * 3

        rng = np.random.default_rng(20260604)
        # Non-trivial deformed state (~3% strain) — well inside the NH validity
        # domain, large enough to exercise the geometric + material tangent.
        u = 0.03 * rng.standard_normal((coords.shape[0], 3))

        def f_int_at(u_state: np.ndarray) -> np.ndarray:
            mod.u.from_numpy(u_state)
            mod.compute_internal_force(_KAPPA, _MU)
            return mod.f_int.to_numpy().ravel().copy()

        h = 1e-6
        max_rel = 0.0
        for _ in range(4):
            v = rng.standard_normal(n_dof)
            v /= np.linalg.norm(v)
            v_mat = v.reshape((-1, 3))

            mod.u.from_numpy(u)
            kv = mod.tangent_matvec(v, _KAPPA, _MU)

            kv_fd = (f_int_at(u + h * v_mat) - f_int_at(u - h * v_mat)) / (2.0 * h)

            scale = max(1.0, float(np.linalg.norm(kv_fd)))
            max_rel = max(max_rel, float(np.linalg.norm(kv - kv_fd) / scale))

        assert max_rel < 1e-5, (
            f"derived tangent_matvec vs finite-difference of f_int: "
            f"max rel-err {max_rel:.3e} >= 1e-5 (tangent/stress wiring inconsistent)"
        )

    def test_newton_solve_converges_to_nontrivial_solution(self, tmp_path):
        """The emitted ``newton_solve`` drives a derived-NH problem to convergence.

        Passes when: with a fixed face and a small external load, the generated
        ``newton_solve(kappa, mu, bc_dofs=...)`` returns after >= 1 iteration and
        leaves a non-trivial displacement field (BCs applied, solver runs).
        """
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from tests._e2e_helpers import _import_generated_module

        src = _compile_derived_bundle().emitted_source
        mod = _import_generated_module(src, tmp_path, "derived_nh_newton")
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

        n_iters = mod.newton_solve(_KAPPA, _MU, bc_dofs=bc_dofs)

        assert n_iters >= 1
        u_arr = mod.u.to_numpy()
        assert float(np.max(np.abs(u_arr))) > 1e-10, "displacement trivially zero"


def test_derived_energy_with_no_params_raises(monkeypatch):
    """A LaTeX-derived energy exposing zero material parameters must fail fast
    with a clear error, not emit malformed (empty-argument) solver signatures.

    Guards the boundary that ``constitutive_update`` / ``tangent_matvec`` /
    ``newton_solve`` are parameterised on: an empty parameter vocabulary would
    otherwise produce ``def newton_solve(,`` / trailing-comma syntax errors in
    the generated module.
    """
    import mechdsl.codegen.energy_emitter as energy_emitter
    from mechdsl.codegen.taichi_printer import _derived_params

    bundle = _compile_derived_bundle()
    assert bundle.derived_energy is not None
    monkeypatch.setattr(energy_emitter, "derived_param_names", lambda _model: [])

    with pytest.raises(ValueError, match="no material parameters"):
        _derived_params(bundle)
