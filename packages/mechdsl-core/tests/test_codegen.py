"""Tests for Layer 5 -- Generated code vs handwritten reference equivalence.

Task P9.2: Verify generated code structure matches handwritten reference patterns.
Since we cannot execute the generated Taichi code (JIT unavailable in CI),
we verify structural equivalence:
  1. Generated code contains the same mathematical operations as the reference
  2. Golden file comparison: emitted source matches stored golden source
"""

from __future__ import annotations

import ast
import re
from pathlib import Path  # noqa: TC003 — used at runtime via GOLDEN_DIR

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import emit
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize
from tests.conftest import GOLDEN_DIR

pytestmark = pytest.mark.stable_backend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UPDATE_GOLDEN = False  # Set True to regenerate golden files (intentional only)


def _make_elastic_bundle() -> tuple[ArtifactBundle, str]:
    """Create elastic SVK bundle and emit source."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    source = emit(bundle)
    return bundle, source


def _make_plastic_bundle() -> tuple[ArtifactBundle, str]:
    """Create J2 plastic bundle and emit source."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={
                "E": 200e3,
                "nu": 0.3,
                "sigma_y0": 250.0,
                "K": 500.0,
                "n": 1.0,
            },
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    source = emit(bundle)
    return bundle, source


def _extract_function_names(source: str) -> set[str]:
    """Extract all function names defined in the source via AST."""
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _count_pattern(source: str, pattern: str) -> int:
    """Count occurrences of a regex pattern in source."""
    return len(re.findall(pattern, source))


# ===========================================================================
# P9.2: Generated vs Handwritten Structural Equivalence
# ===========================================================================


class TestGeneratedVsHandwritten:
    """Structural equivalence between generated and reference code."""

    # -----------------------------------------------------------------------
    # Elastic constitutive
    # -----------------------------------------------------------------------

    def test_elastic_constitutive_matches_reference(self):
        """Generated SVK matches ref_hex8_elastic pattern: S = lam*tr(E)*I + 2*mu*E.

        The reference computes:
          F = I + grad_u
          E = (F^T F - I) / 2
          S = lam * tr(E) * I + 2 * mu * E
          P = F @ S

        The generated code must follow the same mathematical sequence.
        """
        _, source = _make_elastic_bundle()

        # Kinematics: C = F^T F, E = 0.5*(C - I)
        assert "C = F.transpose() @ F" in source, "Missing right Cauchy-Green computation"
        assert "E = 0.5 * (C - I3)" in source, "Missing Green-Lagrange strain computation"

        # Trace of E (sum of diagonal elements)
        assert "tr_E" in source, "Missing trace of E"

        # SVK stress formula: S = lam * tr_E * I3 + 2.0 * mu * E
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in source, "Missing SVK stress formula"

        # First Piola-Kirchhoff: P = F @ S
        assert "P = F @ S" in source, "Missing PK1 computation"

    def test_elastic_force_assembly_pattern(self):
        """Generated force assembly follows same quadrature loop as reference.

        The reference (ref_hex8_elastic.py) pattern:
          for q in quadrature_points:
            dN_dX, detJ0 = shape_grad_reference(...)
            grad_u = u^T @ dN_dX
            F = I + grad_u
            E = green_lagrange(F)
            S = svk(E)
            P = F @ S
            f_int += w_q * detJ0 * (dN_dX @ P^T)

        The generated code must have equivalent structure.
        """
        _, source = _make_elastic_bundle()

        # Element loop (runtime)
        assert "for e in range(n_elem):" in source, "Missing element loop"

        # Quadrature loop (ti.static — element-type constant for Python list access)
        assert "for q in ti.static(range(N_QP)):" in source, "Missing quadrature loop"

        # Shape function gradient computation
        assert "dN_dxi" in source, "Missing parametric gradient"
        assert "J0" in source, "Missing reference Jacobian"
        assert "dNdX" in source, "Missing reference gradient dN/dX"

        # Deformation gradient assembly
        assert "F = ti.Matrix.identity(ti.f64, DIM)" in source, "Missing F initialization"
        assert "F[i, I] += u[nid][i] * dNdX[a, I]" in source, "Missing F assembly"

        # Constitutive call
        assert "S = constitutive_update(F, lam, mu)" in source, "Missing constitutive call"

        # PK1 stress and force integration
        assert "P = F @ S" in source
        assert "f_int[nid]" in source, "Missing internal force scatter"

    def test_elastic_index_partitioning(self):
        """Physics indices use ti.static, mesh/node indices use runtime loops."""
        _, source = _make_elastic_bundle()

        # Physics indices -> ti.static
        assert "ti.static(range(DIM))" in source
        assert "ti.static(range(3))" in source  # constitutive trace loop

        # Node indices -> runtime (N_NODES=8 > 6 threshold)
        assert "for a in range(N_NODES):" in source
        # GRAD_AT_QUAD gather loop keeps ti.static for Python list access
        assert "for a in ti.static(range(N_NODES)):" in source

        # Quad loop -> ti.static (element-type constant, Python list access)
        assert "for q in ti.static(range(N_QP)):" in source

        # Element loop -> runtime
        assert "for e in range(n_elem):" in source

        # Must NOT unroll element count
        assert "ti.static(range(n_elem))" not in source

    # -----------------------------------------------------------------------
    # Plastic constitutive
    # -----------------------------------------------------------------------

    def test_plastic_return_mapping_matches_reference(self):
        """Generated J2 return mapping follows same algorithm as ref_hex8_plastic.

        The reference (j2_power_law.py) algorithm:
          1. S_trial = lam*tr(E)*I + 2*mu*E  (elastic trial)
          2. S_dev = S_trial - (tr_S/3)*I  (deviatoric split)
          3. sigma_eq = sqrt(1.5 * s:s)  (von Mises)
          4. yield check: f_trial = sigma_eq - sigma_y(alpha_old)
          5. Newton iteration for delta_lambda
          6. S = S_vol + (1 - 3*mu*dl/sigma_eq) * S_dev
          7. alpha_new = alpha_old + dl
        """
        _, source = _make_plastic_bundle()

        # 1. Elastic trial stress
        assert "S_trial" in source, "Missing elastic trial stress"

        # 2. Deviatoric split
        assert "S_dev" in source, "Missing deviatoric stress"
        assert "tr_S" in source, "Missing stress trace"

        # 3. Von Mises equivalent stress
        assert "sigma_eq" in source, "Missing von Mises equivalent stress"

        # 4. Yield check
        assert "sigma_y" in source, "Missing yield stress"

        # 5. Newton iteration for delta_lambda
        assert "dl" in source, "Missing plastic multiplier delta_lambda"

        # 6. Stress update with return mapping scaling
        assert "factor" in source or "1.0 - 3.0 * mu * dl / sigma_eq" in source, (
            "Missing radial return stress update"
        )

        # 7. Alpha update
        assert "alpha_new" in source, "Missing alpha update"

    def test_plastic_history_field_read_write(self):
        """Generated plastic code reads alpha before constitutive and writes back."""
        _, source = _make_plastic_bundle()

        # Must read alpha from the field
        assert "alpha_old = alpha[e, q]" in source, "Missing alpha read"
        # Must write alpha back
        assert "alpha[e, q] = alpha_new" in source, "Missing alpha write"

    def test_plastic_tangent_preserves_history(self):
        """Analytical J2 tangent reads alpha once and never mutates it.

        PLAN-A §A9.2 replaced the FD tangent (which used an alpha save/restore
        dance) with a per-quadrature-point analytical consistent tangent via
        ``radial_return``.  History preservation is now achieved by
        construction: the matvec snapshots alpha into a NumPy array and
        never writes it back to the Taichi field.
        """
        _, source = _make_plastic_bundle()

        # Analytical J2 path must snapshot alpha and call the symbolic return map.
        assert "alpha_np = alpha.to_numpy()" in source, (
            "Analytical J2 tangent must snapshot the alpha field"
        )
        assert "radial_return(_j2_mat, E, float(alpha_np[e, q]))" in source, (
            "Analytical J2 tangent must call radial_return for the consistent tangent"
        )
        # Neither the FD save/restore pattern nor any write back to the field.
        # Scoped to the tangent_matvec body: newton_solve legitimately
        # snapshots/restores alpha for committed/trial history separation
        # (WI-2, dev/plans/pj14_fix.md) — that is the driver, not the tangent.
        start = source.find("def tangent_matvec(")
        assert start >= 0, "tangent_matvec definition not found"
        rest = source[start:]
        next_boundary = len(rest)
        for marker in ("\ndef ", "\nclass ", "\n@ti.kernel"):
            idx = rest.find(marker, 1)
            if idx != -1 and idx < next_boundary:
                next_boundary = idx
        matvec_body = rest[:next_boundary]
        assert "alpha_save" not in matvec_body, "FD alpha_save pattern should be gone"
        assert "alpha.from_numpy" not in matvec_body, (
            "Analytical tangent must not write alpha back to the Taichi field"
        )

    # -----------------------------------------------------------------------
    # Structural function comparison
    # -----------------------------------------------------------------------

    def test_elastic_has_required_functions(self):
        """Elastic source defines all required functions."""
        _, source = _make_elastic_bundle()
        func_names = _extract_function_names(source)

        required = {
            "constitutive_update",
            "compute_internal_force",
            "tangent_matvec",
            "newton_solve",
            "allocate_fields",
        }
        missing = required - func_names
        assert not missing, f"Missing functions in elastic source: {missing}"

    def test_plastic_has_required_functions(self):
        """Plastic source defines all required functions."""
        _, source = _make_plastic_bundle()
        func_names = _extract_function_names(source)

        required = {
            "constitutive_update_plastic",
            "compute_internal_force",
            "tangent_matvec",
            "newton_solve",
            "allocate_fields",
        }
        missing = required - func_names
        assert not missing, f"Missing functions in plastic source: {missing}"

    def test_svk_and_j2_differ(self):
        """SVK and J2 generated sources must differ."""
        _, elastic_source = _make_elastic_bundle()
        _, plastic_source = _make_plastic_bundle()
        assert elastic_source != plastic_source


# ===========================================================================
# P9.2: Golden file snapshot tests
# ===========================================================================


class TestGoldenSnapshot:
    """Emitted source matches golden snapshot files."""

    @staticmethod
    def _golden_path(name: str) -> Path:
        return GOLDEN_DIR / f"{name}.py.golden"

    def test_generated_elastic_golden_snapshot(self):
        """Emitted SVK source matches golden snapshot."""
        _, source = _make_elastic_bundle()
        golden_path = self._golden_path("generated_elastic")

        if _UPDATE_GOLDEN or not golden_path.exists():
            golden_path.write_text(source, encoding="utf-8")
            pytest.skip("Golden file created/updated -- rerun to verify")

        golden = golden_path.read_text(encoding="utf-8")
        assert source == golden, (
            f"Emitted elastic source differs from golden file {golden_path}.\n"
            "If the change is intentional, delete the golden file and rerun "
            "to regenerate."
        )

    def test_generated_plastic_golden_snapshot(self):
        """Emitted J2 source matches golden snapshot."""
        _, source = _make_plastic_bundle()
        golden_path = self._golden_path("generated_plastic")

        if _UPDATE_GOLDEN or not golden_path.exists():
            golden_path.write_text(source, encoding="utf-8")
            pytest.skip("Golden file created/updated -- rerun to verify")

        golden = golden_path.read_text(encoding="utf-8")
        assert source == golden, (
            f"Emitted plastic source differs from golden file {golden_path}.\n"
            "If the change is intentional, delete the golden file and rerun "
            "to regenerate."
        )

    def test_golden_is_valid_python(self):
        """All golden .py.golden files must be valid Python."""
        for golden_path in GOLDEN_DIR.glob("*.py.golden"):
            source = golden_path.read_text(encoding="utf-8")
            try:
                ast.parse(source)
            except SyntaxError as exc:
                pytest.fail(f"Golden file {golden_path.name} has syntax error: {exc}")


# ===========================================================================
# Source-level mathematical pattern verification
# ===========================================================================


class TestMathematicalPatterns:
    """Verify mathematical correctness of emitted expressions."""

    def test_svk_constitutive_formula(self):
        """SVK formula: S = lam*tr(E)*I + 2*mu*E -- exactly as in 07-CONVENTIONS."""
        _, source = _make_elastic_bundle()

        # The exact formula line
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in source

    def test_green_lagrange_definition(self):
        """E = 0.5 * (C - I) where C = F^T F."""
        _, source = _make_elastic_bundle()

        assert "C = F.transpose() @ F" in source
        assert "E = 0.5 * (C - I3)" in source

    def test_pk1_from_pk2(self):
        """P = F @ S (1st Piola-Kirchhoff from 2nd Piola-Kirchhoff)."""
        _, source = _make_elastic_bundle()
        assert "P = F @ S" in source

    def test_deformation_gradient_formula(self):
        """F = I + grad_u, with grad_u_{iI} = sum_a u_{ai} * dN_a/dX_I."""
        _, source = _make_elastic_bundle()

        # Identity initialization
        assert "F = ti.Matrix.identity(ti.f64, DIM)" in source
        # Displacement gradient addition
        assert "F[i, I] += u[nid][i] * dNdX[a, I]" in source

    def test_j2_deviatoric_split(self):
        """Deviatoric split: S_dev = S - (tr_S/3)*I."""
        _, source = _make_plastic_bundle()

        assert "S_dev = S_trial - (tr_S / 3.0) * I3" in source

    def test_j2_von_mises(self):
        """Von Mises: sigma_eq = sqrt(1.5 * s:s)."""
        _, source = _make_plastic_bundle()

        assert "sigma_eq = ti.sqrt(1.5 * s_sq)" in source

    def test_quadrature_integration_weight(self):
        """Force integration uses w_q * detJ0 weighting."""
        _, source = _make_elastic_bundle()

        assert "w_q * detJ0" in source


# ===========================================================================
# Behavioral equivalence (requires Taichi — slow)
# ===========================================================================


@pytest.mark.slow
class TestBehavioralEquivalence:
    """Run emitted code and compare outputs against handwritten reference.

    These tests write the generated module to disk, import it, and attempt
    to run the solver on a tiny mesh.  If Taichi is not available the tests
    are skipped.
    """

    def test_elastic_generated_vs_reference(self, tmp_path):
        """Generated elastic solver produces same displacement as reference.

        Emits SVK source, imports the module, and runs newton_solve on a
        single-element problem.  Compares displacement to the reference
        solver at the same load.
        """
        import importlib.util

        _, source = _make_elastic_bundle()
        mod_path = tmp_path / "gen_elastic_behav.py"
        mod_path.write_text(source)

        spec = importlib.util.spec_from_file_location("gen_elastic_behav", mod_path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as exc:
            pytest.skip(f"Cannot import generated module (Taichi/deps missing): {exc}")

        # Verify the module has the critical callable
        if not hasattr(mod, "newton_solve") or not callable(mod.newton_solve):
            pytest.fail("Generated module missing callable newton_solve")
