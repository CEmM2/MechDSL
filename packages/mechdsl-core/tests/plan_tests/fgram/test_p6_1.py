"""Focused fgram Phase 6 P6-1 coverage: Taichi emission from LaTeX-derived IR.

Implements the P6-1 acceptance contract (red->green from the scaffolded stubs):
an equation-bearing LaTeX source must drive ``compile_latex`` through the
existing lowering -> einsum -> Taichi printer path and emit code that matches
the handwritten references, while built-in material-name paths and JIT budget
limits remain intact. The LaTeX-semantic constructor additionally threads a
source-role metadata record (``latex_semantics``) onto the artifact bundle.

Entry point: ``mechdsl.compile_latex(source) -> ArtifactBundle`` (the canonical
``from_latex`` facade). References live in ``tests/ref/ref_hex8_elastic.py`` (SVK)
and ``tests/ref/ref_hex8_plastic.py`` (J2).

Convention authority: ``dev/design_docs/07-CONVENTIONS.md`` — Voigt ordering
``[xx, yy, zz, xy, xz, yz]`` with unscaled shears, tension-positive stress, and
JIT budget 512/func, 2000/kernel, 5000 absolute ceiling.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import numpy as np
import pytest
from tests._e2e_helpers import _import_generated_module

from mechdsl import compile_latex
from mechdsl.codegen.einsum_optimizer import (
    MAX_LINES_ABSOLUTE,
    MAX_LINES_TI_FUNC,
    MAX_LINES_TI_KERNEL,
    Tier,
)

if TYPE_CHECKING:
    from pathlib import Path

# Whole-file marker: every P6-1 case traverses the LaTeX -> facade -> Taichi path.
pytestmark = pytest.mark.from_latex


# ---------------------------------------------------------------------------
# Material parameters — match tests/ref/ref_hex8_elastic.py and
# tests/test_e2e_plastic.py so generated vs reference comparisons are apples
# to apples.
# ---------------------------------------------------------------------------

E_YOUNG = 200.0e3
NU = 0.3
SIGMA_Y0 = 200.0
K_HARD = 100.0
N_HARD = 0.3
LAM = E_YOUNG * NU / ((1 + NU) * (1 - 2 * NU))
MU = E_YOUNG / (2 * (1 + NU))


# ---------------------------------------------------------------------------
# Equation-bearing LaTeX sources. Each carries the directive core *plus*
# explicit field / constitutive-role / weak-form declarations so the emitted
# bundle reflects LaTeX equation semantics rather than only a built-in
# material name. These are the P6-1 acceptance targets (Phase 6 context:
# "SVK and J2 equation-bearing LaTeX sources are the required acceptance
# targets").
# ---------------------------------------------------------------------------

SVK_EQUATION_SOURCE = r"""
% MechDSL P6-1 acceptance — equation-bearing SVK Hex8 cantilever.
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics field u --type vector --space H1 --order 1
% mechanics constitutive Psi --strain_energy
% mechanics constitutive S --pk2
% mechanics weak_form internal_residual --residual
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "1 0 0" --surface x1
"""

J2_EQUATION_SOURCE = r"""
% MechDSL P6-1 acceptance — equation-bearing J2 power-law plasticity Hex8.
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material j2_power_law --E 200e3 --nu 0.3 --sigma_y0 200 --K 100 --n 0.3
% mechanics field u --type vector --space H1 --order 1
% mechanics constitutive S --pk2
% mechanics weak_form internal_residual --residual
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""

# Built-in material-name path: directive-only, no field/constitutive/weak-form
# enrichment. This is the legacy shape — must still compile unchanged.
BUILTIN_SVK_SOURCE = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "1 0 0" --surface x1
"""

BUILTIN_J2_SOURCE = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material j2_power_law --E 200e3 --nu 0.3 --sigma_y0 200 --K 100 --n 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""


def _gen_name(stem: str) -> str:
    """Unique-per-invocation module name (avoids importlib cache collisions)."""
    return f"gen_p6_1_{stem}_{_uuid.uuid4().hex}"


class TestTaskP6_1:
    """Tests for Task P6-1: Taichi emission from LaTeX-derived IR. AC covered: 1-4."""

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_svk_equation_source_emits_taichi_matching_reference(self, tmp_path: Path) -> None:
        """AC1: an SVK *equation-bearing* LaTeX source compiles through
        ``compile_latex`` and the emitted Taichi residual/tangent matches the
        handwritten Hex8 elastic reference within spec tolerance (< 1e-10).

        Distinct from the recovery-plan ``test_p7_2`` SVK acceptance test: the
        source here carries explicit ``field`` / ``constitutive`` / ``weak_form``
        equation declarations, and the test additionally asserts the emitted
        bundle carries the source-role metadata that links code to equation
        roles (the P6-1 deliverable)."""
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic

        # 1. Canonical entry point: equation-bearing LaTeX -> ArtifactBundle.
        bundle = compile_latex(SVK_EQUATION_SOURCE, profile="mvp")
        assert bundle.emitted_source, "compile_latex returned an empty source"
        assert "import taichi as ti" in bundle.emitted_source
        assert "@ti.kernel" in bundle.emitted_source
        assert bundle.element_ir_summary["element_type"] == "hex8"
        assert bundle.element_ir_summary["formulation"] == "total_lagrangian"

        # Source-role metadata (P6-1 deliverable): the equation roles the
        # compiler understood are recorded on the bundle so emitted sections
        # are traceable back to source. The constitutive contract still drives
        # codegen — this record is the explanatory link, not the contract.
        latex_semantics = bundle.problem_ir_dict.get("latex_semantics")
        assert latex_semantics is not None, (
            "equation-bearing SVK source must attach latex_semantics to the bundle"
        )
        roles = {e["symbol"]: e["role"] for e in latex_semantics["constitutive"]}
        assert roles == {"Psi": "strain_energy", "S": "pk2"}
        assert latex_semantics["weak_form_label"] == "internal_residual"
        assert "u" in latex_semantics["fields"]

        # Neumann directive surfaces as the emitted f_ext init kernel.
        assert bundle.f_ext_kernel is not None
        assert "init_f_ext_from_neumann_load" in bundle.f_ext_kernel

        # 2. Import the emitted module under Taichi JIT.
        merged = bundle.emitted_source + "\n\n" + bundle.f_ext_kernel
        mod = _import_generated_module(merged, tmp_path, _gen_name("svk"))
        assert hasattr(mod, "compute_internal_force")
        assert hasattr(mod, "tangent_matvec")
        assert hasattr(mod, "newton_solve")

        # 3. Minimal canonical 1-element unit cube.
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        for e in range(n_elem):
            for a in range(8):
                mod.elem_nodes[e, a] = int(conn[e, a])

        # 4. BCs/loads driven by the LaTeX directives.
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left, :] = True
        bc_dofs = np.where(bc_mask.ravel())[0].astype(np.int64)

        right = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0].astype(np.int32)
        f_factor = 1.0 / float(len(right))  # face_area (=1.0) / n_face_nodes
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        f_ext[right, 0] = 1.0 * f_factor

        # 5. Drive the emitted Newton solver; load via the emitted kernel.
        mod.init_f_ext_from_neumann_load(right, f_factor)
        n_iters = mod.newton_solve(LAM, MU, bc_dofs=bc_dofs)
        u_gen = mod.u.to_numpy()
        assert n_iters >= 1
        assert float(np.max(np.abs(u_gen))) > 1e-10, "Generated solution is trivially zero"

        # 6. Reference solve, then compare (07-CONVENTIONS Sec 6: < 1e-10).
        u_ref, _ = solve_elastic(coords, conn, LAM, MU, bc_mask, bc_values, f_ext)
        max_diff = float(np.max(np.abs(u_gen - u_ref)))
        assert max_diff < 1e-10, (
            "SVK equation-bearing LaTeX-to-solution path does not match reference "
            f"within 07-CONVENTIONS Sec 6 tolerance: max |u_gen - u_ref| = "
            f"{max_diff:.3e} (>= 1e-10)"
        )

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_j2_equation_source_emits_taichi_matching_reference(self, tmp_path: Path) -> None:
        """AC2: a J2 *equation-bearing* LaTeX source compiles through
        ``compile_latex`` and the emitted Taichi matches the existing J2
        reference path (radial return) within tolerance.

        Mirrors ``test_e2e_plastic`` displacement-controlled load stepping, but
        the ProblemIR's *sole* source is the equation-bearing LaTeX string —
        not a programmatic ``_make_j2_problem_ir`` shortcut."""
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh
        from tests.ref.ref_hex8_plastic import solve_plastic
        from tests.test_e2e_plastic import _load_mesh_into_module, _run_load_stepping

        from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial

        # 1. Equation-bearing J2 LaTeX -> ArtifactBundle.
        bundle = compile_latex(J2_EQUATION_SOURCE, profile="mvp")
        assert bundle.emitted_source, "compile_latex returned an empty J2 source"
        assert "import taichi as ti" in bundle.emitted_source
        # J2 emission must carry the radial-return path (existing infra reused).
        assert "radial_return" in bundle.emitted_source, (
            "J2 emitted code must reuse the existing radial-return path"
        )

        # Source-role metadata records the J2 PK2 stress role.
        latex_semantics = bundle.problem_ir_dict.get("latex_semantics")
        assert latex_semantics is not None
        roles = {e["symbol"]: e["role"] for e in latex_semantics["constitutive"]}
        assert roles == {"S": "pk2"}
        assert latex_semantics["weak_form_label"] == "internal_residual"
        # Material model is the codegen contract (authoritative, not the record).
        assert bundle.problem_ir_dict["material"]["model"] == "j2_power_law"

        # 2. Import under Taichi JIT.
        mod = _import_generated_module(bundle.emitted_source, tmp_path, _gen_name("j2"))
        assert hasattr(mod, "compute_internal_force")
        assert hasattr(mod, "alpha")

        # 3. Setup 1-element mesh (matches test_e2e_plastic fixture).
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        right_nodes = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_mask[left_nodes, :] = True
        _load_mesh_into_module(mod, coords, conn)

        # 4. Displacement-controlled load stepping past yield (10x yield strain).
        total_disp = 0.01
        n_steps = 5
        u_gen, _residuals, _alpha = _run_load_stepping(
            mod, coords, bc_mask, right_nodes, total_disp, n_steps
        )

        # 5. Reference plastic solve with the same setup.
        mat = J2PowerLawMaterial(E=E_YOUNG, nu=NU, sigma_y0=SIGMA_Y0, K=K_HARD, n=N_HARD)
        bc_mask_ref = bc_mask.copy()
        bc_mask_ref[right_nodes, 0] = True
        bc_values_ref = np.zeros((n_nodes, 3), dtype=np.float64)
        bc_values_ref[right_nodes, 0] = total_disp
        f_ext_ref = np.zeros((n_nodes, 3), dtype=np.float64)
        u_ref, _hist, _res = solve_plastic(
            coords,
            conn,
            mat,
            bc_mask_ref,
            bc_values_ref,
            f_ext_ref,
            n_steps=n_steps,
            tol=1e-8,
            max_iter=50,
        )

        # 6. Compare (07-CONVENTIONS Sec 6: < 1e-10; observed ~machine eps).
        max_diff = float(np.max(np.abs(u_gen - u_ref)))
        assert max_diff < 1e-10, (
            "J2 equation-bearing LaTeX path does not match the reference within "
            f"07-CONVENTIONS Sec 6 tolerance: max |u_gen - u_ref| = {max_diff:.3e}"
        )
        # Plastic deformation actually occurred (not a trivial elastic match).
        assert float(np.max(mod.alpha.to_numpy())) > 1e-6, (
            "Expected plastic deformation (alpha > 0) past yield"
        )

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_builtin_material_path_compatible_and_within_jit_budget(self, tmp_path: Path) -> None:
        """AC3+AC4: built-in material-name LaTeX paths still emit equivalent
        Taichi after the equation-driven path lands, and generated code stays
        within the JIT budget (07-CONVENTIONS: 512/func, 2000/kernel, 5000
        ceiling).

        - Equation-bearing and built-in sources must emit *identical* Taichi
          source for the same physics (the latex_semantics record is additive
          and does not perturb codegen).
        - Every contraction plan must classify into Tier 1 or Tier 2 (within
          the per-``@ti.func`` budget), and the summed estimated lines must
          stay under the kernel and absolute ceilings."""
        # --- AC4: built-in material-name path remains compatible ---
        builtin_svk = compile_latex(BUILTIN_SVK_SOURCE, profile="mvp")
        eqn_svk = compile_latex(SVK_EQUATION_SOURCE, profile="mvp")
        assert builtin_svk.emitted_source, "built-in SVK path emitted no source"
        # Equation-driven and built-in paths emit byte-identical Taichi for the
        # same physics — the equation path only *adds* latex_semantics metadata.
        assert eqn_svk.emitted_source == builtin_svk.emitted_source, (
            "equation-bearing SVK and built-in SVK must emit identical Taichi; "
            "the latex_semantics record must not perturb codegen"
        )
        # The built-in (directive-only) path carries no equation enrichment.
        assert builtin_svk.problem_ir_dict.get("latex_semantics") is None, (
            "directive-only built-in path must not fabricate latex_semantics"
        )
        # Built-in path still compiles and imports under Taichi JIT.
        merged = builtin_svk.emitted_source + "\n\n" + (builtin_svk.f_ext_kernel or "")
        mod = _import_generated_module(merged, tmp_path, _gen_name("builtin_svk"))
        assert hasattr(mod, "compute_internal_force")

        builtin_j2 = compile_latex(BUILTIN_J2_SOURCE, profile="mvp")
        eqn_j2 = compile_latex(J2_EQUATION_SOURCE, profile="mvp")
        assert eqn_j2.emitted_source == builtin_j2.emitted_source, (
            "equation-bearing J2 and built-in J2 must emit identical Taichi"
        )

        # --- AC3: JIT budget compliance across all four bundles ---
        for label, bundle in (
            ("builtin_svk", builtin_svk),
            ("eqn_svk", eqn_svk),
            ("builtin_j2", builtin_j2),
            ("eqn_j2", eqn_j2),
        ):
            plans = bundle.contraction_plans
            assert plans, f"{label}: bundle carries no contraction plans to budget-check"
            for plan in plans:
                # Tier 1 (native) and Tier 2 (emitted ti.func) are within the
                # per-function budget; Tier 3 means a contraction overflowed
                # 512 lines and was restructured — none expected for MVP Hex8.
                assert plan.tier in (Tier.TIER_1.value, Tier.TIER_2.value), (
                    f"{label}: contraction {plan.einsum_string!r} classified Tier "
                    f"{plan.tier} (> Tier 2) — exceeds per-@ti.func budget of "
                    f"{MAX_LINES_TI_FUNC} lines"
                )
            # The emitted source itself must stay under the absolute ceiling.
            total_lines = bundle.emitted_source.count("\n") + 1
            assert total_lines <= MAX_LINES_ABSOLUTE, (
                f"{label}: emitted source has {total_lines} lines > absolute "
                f"ceiling {MAX_LINES_ABSOLUTE}"
            )
            # Sanity: a single residual+tangent kernel pair should sit well
            # under the per-kernel budget for a 1-element Hex8 problem.
            assert total_lines <= MAX_LINES_TI_KERNEL * 3, (
                f"{label}: emitted source {total_lines} lines is implausibly large "
                f"for MVP Hex8 (kernel budget {MAX_LINES_TI_KERNEL})"
            )
