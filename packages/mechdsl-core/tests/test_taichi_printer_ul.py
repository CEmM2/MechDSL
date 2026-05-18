"""Tests for Tasks P1-3 and P1-4: UL residual and tangent emission.

Plan: dev/design_docs/PLAN-B.md lines 25-46 (B1.1 residual, B1.2 tangent).

Covers both tasks because they emit into the same ``taichi_printer.py`` and
share the UL golden snapshot file ``generated_ul_svk.py.golden``.

P1-3 tests (TestTaskP1_3InternalForce) verify that the UL emission branch
of ``emit_internal_force_kernel`` emits text containing:
  - The push-forward from PK2 to Cauchy (sigma, not P = F @ S)
  - Spatial shape gradients (dNdx, not dNdX)
  - Current Jacobian determinant (detj, not detJ0 in the scatter)
and that the TL emission is unchanged (golden byte-comparison).

P1-4 tests (TestTaskP1_4TangentMatvec) verify that the UL tangent emission
contains both the Jaumann material term and the geometric stiffness term,
and that TL tangent emission is unchanged.
"""

from __future__ import annotations

import ast

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import emit
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    Configuration,
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


def _make_ul_elastic_bundle() -> tuple[ArtifactBundle, str]:
    """Create an Updated Lagrangian SVK bundle and emit source."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.UPDATED_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
        configuration=Configuration.CURRENT,
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    source = emit(bundle)
    return bundle, source


def _make_tl_elastic_bundle() -> tuple[ArtifactBundle, str]:
    """Create a Total Lagrangian SVK bundle and emit source (Plan A baseline)."""
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


# ---------------------------------------------------------------------------
# P1-3: UL residual emission
# ---------------------------------------------------------------------------


class TestTaskP1_3InternalForce:
    """
    Tests for Task P1-3: UL residual emission.

    Acceptance criteria covered:
      1. UL emission produces syntactically valid Python
      2. UL source contains Cauchy stress + dN/dx + det(j) (not det(J0))
      3. TL emission is byte-identical to the Plan A baseline
    """

    @pytest.mark.unit
    def test_ul_internal_force_source_contains_push_forward_and_spatial_gradients(
        self,
    ) -> None:
        """Verifies: the UL branch emits the Cauchy push-forward and spatial gradients.

        Acceptance criterion: "UL source contains the push-forward from S to
        sigma and uses dN/dx, det(j)."
        Passes when: the emitted source matches the four substring checks:
          1. "sigma" is present (Cauchy stress variable)
          2. "dNdx" is present (spatial shape gradients)
          3. "detj" is present (current Jacobian determinant)
          4. "F @ S @ F.transpose()" is present (push-forward formula)
        and does NOT contain "P = F @ S" (PK1 stress, which is TL-only).
        """
        _, source = _make_ul_elastic_bundle()

        # Must contain UL-specific constructs.
        assert "sigma" in source, "UL source must contain Cauchy stress variable 'sigma'"
        assert "dNdx" in source, "UL source must contain spatial shape gradients 'dNdx'"
        assert "detj" in source, "UL source must contain current Jacobian determinant 'detj'"
        assert "F @ S @ F.transpose()" in source, (
            "UL source must contain the push-forward formula 'F @ S @ F.transpose()'"
        )

        # Must NOT contain TL-specific constructs in the internal force kernel.
        # (Note: the tangent kernel may still reference J0 for now -- we only
        # check the internal force region.)
        force_section = source.split("# Internal force kernel")[1].split("# Tangent")[0]
        assert "P = F @ S" not in force_section, (
            "UL internal force section must NOT contain 'P = F @ S' (PK1 is TL-only)"
        )

    @pytest.mark.unit
    def test_tl_emission_unchanged_byte_equal_to_existing_golden(self) -> None:
        """Verifies: TL emission is byte-identical to the existing goldens.

        Acceptance criterion: "TL emission source is byte-identical to the
        Plan A baseline (regression guard)."
        """
        _, tl_source = _make_tl_elastic_bundle()
        golden_path = GOLDEN_DIR / "generated_elastic.py.golden"
        assert golden_path.exists(), f"TL golden file not found: {golden_path}"
        golden = golden_path.read_text(encoding="utf-8")
        assert tl_source == golden, (
            "TL emission differs from existing golden after P1-3 UL branch addition. "
            "The TL path must remain byte-identical to Plan A. "
            f"Golden: {golden_path}"
        )

    @pytest.mark.unit
    def test_ul_golden_snapshot_parses_as_valid_python(self) -> None:
        """Verifies: the UL golden file is syntactically valid Python.

        Acceptance criterion: "UL emission produces a syntactically valid Python file."
        """
        _, source = _make_ul_elastic_bundle()
        golden_path = GOLDEN_DIR / "generated_ul_svk.py.golden"

        if _UPDATE_GOLDEN or not golden_path.exists():
            golden_path.write_text(source, encoding="utf-8")
            pytest.skip(f"UL golden written to {golden_path} -- rerun to verify")

        golden = golden_path.read_text(encoding="utf-8")
        # The golden must parse without SyntaxError.
        ast.parse(golden)
        # And the current emission must match the golden.
        assert source == golden, (
            f"UL emission differs from golden file {golden_path}.\n"
            "If the change is intentional, delete the golden file and rerun "
            "to regenerate it."
        )

    @pytest.mark.unit
    def test_ul_source_differs_from_tl_source(self) -> None:
        """UL and TL source bodies must differ (they use different formulations).

        This is a smoke test ensuring the configuration dispatch actually
        produces different generated code.
        """
        _, ul_source = _make_ul_elastic_bundle()
        _, tl_source = _make_tl_elastic_bundle()
        assert ul_source != tl_source, "UL and TL emission produced identical source"


# ---------------------------------------------------------------------------
# P1-4: UL tangent emission
# ---------------------------------------------------------------------------


def _get_tangent_section(source: str) -> str:
    """Extract the tangent_matvec section from full emitted source."""
    start = source.find("# Tangent matvec")
    end = (
        source.find("# Mesh validation")
        if "# Mesh validation" in source
        else source.find("# Newton")
    )
    assert start >= 0, "tangent_matvec section not found in emitted source"
    assert end > start, "could not find end boundary for tangent section"
    return source[start:end]


class TestTaskP1_4TangentMatvec:
    """
    Tests for Task P1-4: UL tangent operator emission.

    Acceptance criteria covered:
      1. UL tangent contains Jaumann material term (c^Jau contraction)
      2. UL tangent contains geometric stiffness term (sigma * grad_v)
      3. TL tangent golden unchanged (regression guard)
      4. UL tangent matches handwritten UL reference within 1e-10 (deferred to P1-7)
    """

    @pytest.mark.unit
    def test_ul_tangent_contains_truesdell_material_term(self) -> None:
        """Verifies: the UL tangent branch imports truesdell_tangent and
        contracts c^tau with grad_v via einsum.

        Acceptance criterion: "UL tangent source contains the material term
        (using c^tau via Truesdell push-forward)."
        """
        _, source = _make_ul_elastic_bundle()
        tangent = _get_tangent_section(source)

        # Import of the Truesdell tangent
        assert "from mechdsl.symbolic.objective_rates import truesdell_tangent" in source, (
            "UL tangent must import truesdell_tangent from objective_rates"
        )
        # Call to truesdell_tangent with C4_svk, sigma, F
        assert "c_tau = truesdell_tangent(C4_svk, sigma, F)" in tangent, (
            "UL tangent must compute c_tau via truesdell_tangent(C4_svk, sigma, F)"
        )
        # Einsum contraction of c^tau with grad_v
        assert "np.einsum('ijkl,kl->ij', c_tau, grad_v)" in tangent, (
            "UL tangent must contract c_tau with grad_v via einsum('ijkl,kl->ij')"
        )
        # The result is stored as dsigma_mat
        assert "dsigma_mat" in tangent, (
            "UL tangent must store the material contribution as dsigma_mat"
        )

    @pytest.mark.unit
    def test_ul_tangent_contains_geometric_stiffness_term(self) -> None:
        """Verifies: the UL tangent branch computes the standard geometric
        (initial-stress) stiffness G_{ji} = sigma_{jl} * grad_v_{il}.

        Acceptance criterion: "UL tangent source contains the geometric
        stiffness term."
        """
        _, source = _make_ul_elastic_bundle()
        tangent = _get_tangent_section(source)

        # Geometric stiffness: G_geo = sigma @ grad_v.T
        assert "G_geo = sigma @ grad_v.T" in tangent, (
            "UL tangent must compute geometric stiffness as sigma @ grad_v.T"
        )
        # Assembly uses separate material and geometric terms
        assert "dNdx @ dsigma_mat.T + dNdx @ G_geo" in tangent, (
            "UL tangent must assemble material (dsigma_mat.T) and geometric (G_geo) separately"
        )
        # Scatter uses spatial gradients dNdx and current-config detj
        assert "dNdx @" in tangent, "UL tangent scatter must use spatial shape gradients dNdx"
        assert "w_q * detj *" in tangent, (
            "UL tangent must integrate with current-config volume w_q * detj"
        )

    @pytest.mark.unit
    def test_tl_tangent_golden_unchanged(self) -> None:
        """Verifies: TL tangent emission is byte-identical to the Plan A
        golden after the P1-4 UL tangent addition.

        Acceptance criterion: "Plan A analytical TL tangent emission is
        unchanged (regression on the existing elastic golden)."
        """
        _, tl_source = _make_tl_elastic_bundle()
        golden_path = GOLDEN_DIR / "generated_elastic.py.golden"
        assert golden_path.exists(), f"TL golden file not found: {golden_path}"
        golden = golden_path.read_text(encoding="utf-8")
        assert tl_source == golden, (
            "TL emission differs from existing golden after P1-4 UL tangent "
            "addition.  The TL path must remain byte-identical to Plan A. "
            f"Golden: {golden_path}"
        )

    @pytest.mark.unit
    def test_reference_ul_tangent_fd_verification(self) -> None:
        """Handwritten UL reference tangent matches finite-difference approximation.

        Resolved by P1-7: the handwritten UL reference solver now exists at
        ``tests/ref/ref_hex8_ul.py``. This test verifies the *reference solver's*
        element tangent matvec against FD of the UL internal force, confirming
        that the Truesdell + geometric stiffness decomposition is correct.

        NOTE: This does NOT exercise the emitted codegen path — see
        ``test_emitted_ul_tangent_matches_reference`` for that.
        """
        import numpy as np

        from tests.ref.ref_hex8_ul import (
            element_internal_force_ul,
            element_tangent_matvec_ul,
        )

        X_elem = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 1.0],
                [1.0, 1.0, 1.0],
                [0.0, 1.0, 1.0],
            ],
            dtype=np.float64,
        )
        # Small strain state
        u_elem = np.zeros_like(X_elem)
        u_elem[:, 0] = 1e-3 * X_elem[:, 0]

        rng = np.random.default_rng(42)
        v_elem = rng.standard_normal((8, 3)) * 1e-4

        E_mod, nu = 1000.0, 0.3
        lam = E_mod * nu / ((1 + nu) * (1 - 2 * nu))
        mu = E_mod / (2 * (1 + nu))

        Kv = element_tangent_matvec_ul(u_elem, X_elem, v_elem, lam, mu)

        # FD check
        h = 5e-8 * max(float(np.linalg.norm(u_elem)), 1.0)
        f_p = element_internal_force_ul(u_elem + h * v_elem, X_elem, lam, mu)
        f_m = element_internal_force_ul(u_elem - h * v_elem, X_elem, lam, mu)
        Kv_fd = (f_p - f_m) / (2.0 * h)

        np.testing.assert_allclose(Kv, Kv_fd, rtol=1e-3)

    @pytest.mark.unit
    def test_emitted_ul_tangent_matches_reference(self) -> None:
        """Emitted UL tangent matvec matches handwritten reference solver.

        Exercises the EMITTED codegen path (taichi_printer output) by
        extracting the tangent_matvec function from the generated source,
        running it with mock Taichi fields on a single-element unit cube,
        and comparing against the handwritten reference solver.

        This closes the gap identified by Codex review: the FD test above
        only covers the reference solver, not the emitted code. The golden
        snapshot catches structural regressions, but this test catches
        numerical regressions in the emitted tangent matvec.
        """
        import numpy as np

        from tests.ref.ref_hex8_ul import element_tangent_matvec_ul

        _, source = _make_ul_elastic_bundle()

        # --- Extract constants + tangent_matvec from emitted source ---
        # Constants: between "Element constants" and "Field declarations"
        const_start = source.find("N_NODES = ")
        const_end = source.find("# Field declarations")
        if const_end < 0:
            const_end = source.find("n_nodes = 0")
        assert const_start > 0 and const_end > const_start

        # tangent_matvec: between "def tangent_matvec" and next "# ===="
        tm_start = source.find("def tangent_matvec(")
        tm_end = source.find("\n# ====", tm_start + 1)
        assert tm_start > 0 and tm_end > tm_start

        constants_src = source[const_start:const_end]
        tangent_src = source[tm_start:tm_end]

        # --- Set up a single-element unit cube ---
        X_ref = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 1.0],
                [1.0, 1.0, 1.0],
                [0.0, 1.0, 1.0],
            ],
            dtype=np.float64,
        )
        u_arr = np.zeros_like(X_ref)
        u_arr[:, 0] = 1e-3 * X_ref[:, 0]  # small uniaxial strain

        rng = np.random.default_rng(42)
        v_arr = rng.standard_normal((8, 3)) * 1e-4
        conn = np.array([[0, 1, 2, 3, 4, 5, 6, 7]], dtype=np.int32)

        E_mod, nu = 200e3, 0.3
        lam = E_mod * nu / ((1 + nu) * (1 - 2 * nu))
        mu_val = E_mod / (2 * (1 + nu))

        # --- Mock Taichi fields as objects with .to_numpy() ---
        class _MockField:
            def __init__(self, arr: np.ndarray) -> None:
                self._arr = arr

            def to_numpy(self) -> np.ndarray:
                return self._arr

        # --- Build namespace and exec emitted code ---
        ns: dict = {"np": np, "__builtins__": __builtins__}
        exec(compile(constants_src, "<constants>", "exec"), ns)
        ns["u"] = _MockField(u_arr)
        ns["x_ref"] = _MockField(X_ref)
        ns["elem_nodes"] = _MockField(conn)
        ns["n_elem"] = 1
        exec(compile(tangent_src, "<tangent_matvec>", "exec"), ns)

        # --- Run emitted tangent_matvec ---
        emitted_Kv = ns["tangent_matvec"](v_arr.ravel(), lam, mu_val)

        # --- Run reference tangent matvec (element-level, no BCs) ---
        ref_Kv = element_tangent_matvec_ul(u_arr, X_ref, v_arr, lam, mu_val).ravel()

        np.testing.assert_allclose(
            emitted_Kv,
            ref_Kv,
            rtol=1e-10,
            err_msg=(
                "Emitted UL tangent matvec (Jaumann + Hadamard) diverges "
                "from reference solver (Truesdell + standard geometric). "
                "Both decompositions must produce the same total tangent."
            ),
        )
