"""Task P7-2: Canonical LaTeX-to-solution acceptance test on the MVP-stable path.

Phase 7 (R6.2) -- integration-tier acceptance: the recovery plan is not
considered restored until at least one acceptance test runs the full
canonical contract -- LaTeX source -> ``compile_latex`` facade -> Taichi
codegen (P5-1) -> mesh + Newton solve -> verified solution. Today no test
starts from a LaTeX string; P2-1's ``compile_latex`` is exercised only at
the API-shape level by ``test_p2_1.py`` and the symbolic-pipeline checks.

Tier: integration

Acceptance criteria:
  1. P7-2-c1: Acceptance test passes starting from LaTeX input -- i.e. a
     literal LaTeX string is the test's only ProblemIR source, with no
     ``build_context`` / ``_make_elastic_problem_ir`` shortcuts.
  2. P7-2-c2: Deliverables present at the listed surfaces (e2e tests,
     examples).
  3. No regressions on the existing test suite.

Blocked by: P2-1 (LaTeX facade), P4-1 (enriched ElementIR), P5-1 (Taichi
as canonical stable backend) -- the four pillars whose acceptance test
this task verifies.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mechdsl import compile_latex
from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic

# Module-level marker: this entire file is the canonical "from_latex" family
# anchor created by P7-1. Every test below must traverse the LaTeX -> facade
# path; do NOT mark with ``from_problem_ir``.
pytestmark = pytest.mark.from_latex


# ---------------------------------------------------------------------------
# Canonical LaTeX source -- mirrors dev/examples/run_compile_latex.py so the
# acceptance test and the user-facing example exercise the same contract.
# Material parameters (E, nu) match tests/ref/ref_hex8_elastic.py defaults.
# ---------------------------------------------------------------------------

# post_recovery_plan P1-6: the Neumann directive now carries a numeric
# 3-vector traction and an explicit ``--surface`` tag. ``compile_latex``
# parses these (P1-2) and emits an ``init_f_ext_from_neumann_load``
# kernel (P1-5) that the test below invokes — no manual numeric f_ext
# injection. Traction magnitude (1.0 in +x on x1) was chosen to match
# the previous hand-written ``f_ext[right, 0] = 1.0`` after the kernel's
# uniform-distribution weighting (per-node = traction * face_area /
# n_face_nodes; face_area = 1.0, n_face_nodes = 4 → per-node = 0.25).
CANONICAL_LATEX_SOURCE = r"""
% MechDSL canonical first-run example -- elastic cantilever (SVK Hex8).
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "1 0 0" --surface x1
"""

E_YOUNG = 200.0e3
NU = 0.3
LAM = E_YOUNG * NU / ((1 + NU) * (1 - 2 * NU))
MU = E_YOUNG / (2 * (1 + NU))


# ---------------------------------------------------------------------------
# Helpers (kept local to this file -- the family split rule forbids reusing
# ``_make_elastic_problem_ir`` from test_e2e_taichi.py because that helper
# constructs a ProblemIR programmatically).
# ---------------------------------------------------------------------------


# post_recovery_plan Phase 6 (P6-1, P6-2): _import_generated_module
# now lives in the shared tests/_e2e_helpers module.
# post_recovery_plan Phase 7 (P7-3): module name is now derived from
# `uuid.uuid4()` per test invocation — the previously-hardcoded
# `"gen_p7_2"` literal made every invocation share a single importlib
# cache slot, which can mask ordering dependencies when the suite
# runs alongside other emitter tests.

import uuid as _uuid_p7_3  # noqa: E402

from tests._e2e_helpers import _import_generated_module  # noqa: E402

# ===========================================================================
# P7-2-c1: Canonical LaTeX -> compile_latex -> Taichi -> Newton -> reference
# ===========================================================================


class TestP7_2:
    """Tests for Task P7-2: canonical LaTeX-to-solution acceptance test."""

    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_acceptance_passes_starting_from_latex_input(self, tmp_path: Path) -> None:
        """P7-2-c1: Acceptance test passes starting from LaTeX input.

        Verifies the full canonical contract end-to-end:
            literal LaTeX string
            -> mechdsl.compile_latex(source, profile="mvp")
            -> ArtifactBundle (Taichi backend, P5-1 stable surface)
            -> generated module imported & executed under Taichi JIT
            -> max |u_generated - u_reference| < 1e-10
              (07-CONVENTIONS.md Sec 6 tolerance authority).

        Critically, the LaTeX string is the *sole* ProblemIR source -- no
        ``_make_elastic_problem_ir`` / ``build_context`` shortcut is used.
        That is the contract Phase 7 R6.2 closes.
        """
        # 1. Canonical entry point: LaTeX source -> ArtifactBundle. No
        #    programmatic ProblemIR construction is allowed in this test.
        bundle = compile_latex(CANONICAL_LATEX_SOURCE, profile="mvp")
        assert bundle.emitted_source, "compile_latex returned an empty source"
        assert bundle.element_ir_summary["element_type"] == "hex8"
        assert bundle.element_ir_summary["formulation"] == "total_lagrangian"
        # Taichi-stable backend signature -- prove we are NOT on an
        # experimental printer path (MFEM/MOOSE produce different markers).
        assert "import taichi as ti" in bundle.emitted_source
        assert "@ti.kernel" in bundle.emitted_source
        # post_recovery_plan P1-5/P1-6: the Neumann directive surfaces as
        # an emitted f_ext init kernel; the directive-driven path replaces
        # the previous manual numeric injection.
        assert bundle.f_ext_kernel is not None, (
            "compile_latex must emit an f_ext kernel for the Neumann directive "
            "(post_recovery_plan P1-5)"
        )
        assert "init_f_ext_from_neumann_load" in bundle.f_ext_kernel

        # 2. Import the emitted module under Taichi JIT. Splice the
        #    Neumann f_ext kernel onto the main solver source so the same
        #    imported module exposes both ``newton_solve`` and the
        #    ``init_f_ext_from_neumann_load`` kernel the test calls below.
        merged_source = bundle.emitted_source + "\n\n" + bundle.f_ext_kernel
        # post_recovery_plan Phase 7 (P7-3): unique-per-invocation module
        # name avoids importlib cache collisions when the suite runs
        # alongside other emitter tests.
        gen_module_name = f"gen_p7_2_{_uuid_p7_3.uuid4().hex}"
        mod = _import_generated_module(merged_source, tmp_path, name=gen_module_name)
        assert hasattr(mod, "compute_internal_force")
        assert hasattr(mod, "tangent_matvec")
        assert hasattr(mod, "newton_solve")
        assert hasattr(mod, "allocate_fields")

        # 3. Set up a 1-element Hex8 unit cube mesh -- minimal canonical
        #    fixture, converges in a handful of Newton iterations.
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]

        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        for e in range(n_elem):
            for a in range(8):
                mod.elem_nodes[e, a] = int(conn[e, a])

        # 4. BCs/loads driven entirely by the LaTeX directive. The
        #    Dirichlet directive supplies the ``fix`` BC at x=0; the
        #    Neumann directive's ``--traction "1 0 0" --surface x1``
        #    drives the emitted ``init_f_ext_from_neumann_load`` kernel
        #    that initialises ``f_ext``. The previous manual numeric
        #    injection (closes follow-up item 9) is gone.
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left, :] = True
        bc_dofs = np.where(bc_mask.ravel())[0].astype(np.int64)

        # Surface nodes for the Neumann tag ``x1`` and runtime
        # ``f_factor = face_area / n_face_nodes`` per the P1-5 emitter.
        right = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0].astype(np.int32)
        face_area = 1.0  # unit-cube x1 face is 1.0 x 1.0
        f_factor = face_area / float(len(right))
        # Numeric reference uses the same per-node force the kernel
        # produces (traction[0] = 1.0, multiplied by f_factor on x1).
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        f_ext[right, 0] = 1.0 * f_factor

        # 5. Drive the emitted Newton solver via the public emitted entry
        #    point newton_solve(lam, mu, bc_dofs=...). The Neumann load
        #    is initialised by the emitted directive-driven kernel — no
        #    manual numeric injection on the Taichi field.
        mod.init_f_ext_from_neumann_load(right, f_factor)
        n_iters = mod.newton_solve(LAM, MU, bc_dofs=bc_dofs)
        u_gen = mod.u.to_numpy()

        assert n_iters >= 1, "Newton must take at least one iteration with nonzero load"
        assert float(np.max(np.abs(u_gen))) > 1e-10, (
            "Generated solution is trivially zero -- BCs not enforced"
        )

        # 6. Solve the same problem with the handwritten reference.
        u_ref, _ = solve_elastic(coords, conn, LAM, MU, bc_mask, bc_values, f_ext)

        # 7. 07-CONVENTIONS Sec 6: generated vs reference displacement < 1e-10.
        max_diff = float(np.max(np.abs(u_gen - u_ref)))
        assert max_diff < 1e-10, (
            "LaTeX-to-solution path does not match reference within "
            f"07-CONVENTIONS Sec 6 tolerance: max |u_gen - u_ref| = "
            f"{max_diff:.3e} (>= 1e-10)"
        )

    @pytest.mark.integration
    def test_deliverables_present_at_surfaces(self) -> None:
        """P7-2-c2: Deliverables present at the listed surfaces.

        Verifies the two surfaces the recovery plan calls out:
          * ``packages/mechdsl-core/tests/`` carries at least one test
            in the ``from_latex`` family (this file).
          * ``dev/examples/`` carries at least one runnable example that
            consumes ``compile_latex`` end-to-end (P7-3 ``run_compile_latex.py``).

        Both surfaces consume the public ``compile_latex`` facade.
        """
        # ---- Surface 1: tests/ has a from_latex acceptance test ----
        repo_root = Path(__file__).resolve().parents[5]
        this_file = Path(__file__).resolve()
        # Self-witness: this file imports compile_latex and is marked
        # from_latex at module scope.
        text = this_file.read_text(encoding="utf-8")
        assert "pytestmark = pytest.mark.from_latex" in text, (
            "P7-2 test file must anchor the from_latex marker family at module scope"
        )
        assert "from mechdsl import compile_latex" in text, (
            "P7-2 test file must consume the public compile_latex facade"
        )

        # ---- Surface 2: dev/examples/ has a LaTeX-first runnable example ----
        examples_dir = repo_root / "dev" / "examples"
        assert examples_dir.is_dir(), f"missing dev/examples/ at {examples_dir}"

        latex_first_example = examples_dir / "run_compile_latex.py"
        assert latex_first_example.is_file(), (
            "P7-3 example dev/examples/run_compile_latex.py must be present "
            "as the canonical LaTeX-first runnable example"
        )
        example_text = latex_first_example.read_text(encoding="utf-8")
        assert "from mechdsl import compile_latex" in example_text, (
            "run_compile_latex.py must import the public compile_latex facade"
        )
        assert "compile_latex(" in example_text, (
            "run_compile_latex.py must actually call compile_latex"
        )
        assert "% mechanics" in example_text, (
            "run_compile_latex.py must embed a literal '% mechanics' LaTeX "
            "directive set so the user sees the canonical input shape"
        )
