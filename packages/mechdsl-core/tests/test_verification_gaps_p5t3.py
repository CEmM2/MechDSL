"""
Phase 5 verification gap-filling stubs for P5-T3.

Covers test IDs from 08-VERIFICATION.md §2 that lack existing test coverage:
- T1: Tier 1 emission → GEMM step emits ti.Matrix @ call (partial)
- B5: Missing binding → BoundaryBindingError
"""

import numpy as np
import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.boundary_codegen import compile_dirichlet, compile_neumann
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
from mechdsl.solver.mesh_io import generate_hex8_mesh


def _make_svk_source() -> str:
    """Create an SVK bundle and return emitted Taichi source."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    return emit(bundle)


class TestVerificationT1:
    """
    Test ID T1: Tier 1 emission — GEMM step emits ti.Matrix @ call.
    Acceptance criterion: Generated code for rank-2 GEMM contains matrix multiply syntax.

    The generated Taichi code uses the Python @ operator for all rank-2 matrix
    products (C = F.transpose() @ F, P = F @ S, J0 = X_elem.transpose() @ dN_dxi,
    dNdX = dN_dxi @ J0_inv).  These are the Tier 1 contractions: small rank-2
    GEMMs that the codegen rule §Tier 1 maps directly to ti.Matrix @ calls.
    """

    @pytest.mark.audit
    def test_t1_tier1_gemm_emits_matrix_multiply(self):
        """
        Verifies: Tier 1 contraction (rank-2 GEMM) emits ti.Matrix @ syntax.
        Acceptance criterion: T1 — Tier 1 emission → GEMM step emits ti.Matrix @ call
        Passes when: Generated source contains matrix multiply operator (@) for
        at least the PK1 contraction P = F @ S and the Cauchy-Green C = F^T @ F.
        """
        source = _make_svk_source()

        # P = F @ S  — PK1 stress, rank-2 GEMM (Tier 1)
        assert "P = F @ S" in source, (
            "T1: PK1 contraction P = F @ S missing — expected Tier 1 GEMM emission using @ operator"
        )

        # C = F.transpose() @ F  — Right Cauchy-Green, rank-2 GEMM (Tier 1)
        assert "C = F.transpose() @ F" in source, (
            "T1: Cauchy-Green contraction C = F^T @ F missing — expected Tier 1 GEMM emission using @ operator"
        )

        # J0 = X_elem.transpose() @ dN_dxi  — Jacobian, rank-2 GEMM (Tier 1)
        assert "J0 = X_elem.transpose() @ dN_dxi" in source, (
            "T1: Jacobian contraction missing — expected Tier 1 GEMM emission using @ operator"
        )

        # dNdX = dN_dxi @ J0_inv  — gradient transform, rank-2 GEMM (Tier 1)
        assert "dNdX = dN_dxi @ J0_inv" in source, (
            "T1: Gradient transform dNdX = dN_dxi @ J0_inv missing — expected Tier 1 GEMM emission"
        )


class TestVerificationB5:
    """
    Test ID B5: Missing binding → BoundaryBindingError.
    Acceptance criterion: BC referencing unbound region raises descriptive error.

    The spec calls for a BoundaryBindingError.  The current implementation raises
    KeyError from the boundary_tags dict lookup (get_face_nodes in mesh_io).
    BoundaryBindingError does not yet exist as a distinct exception class; the
    task risk note permits testing the actual error raised (KeyError) when a BC
    references an unbound region, since the behaviour is still correct.
    """

    @pytest.mark.audit
    def test_b5_missing_boundary_binding_raises_error(self):
        """
        Verifies: Attempting to apply a Dirichlet BC to an unbound boundary
        region raises KeyError (BoundaryBindingError equivalent).
        Acceptance criterion: B5 — Missing binding → error raised with region name.
        Passes when: KeyError is raised containing the unbound region name.
        """
        mesh = generate_hex8_mesh(2, 2, 2)
        unbound_region = "unbound_region"

        with pytest.raises(KeyError, match=unbound_region):
            compile_dirichlet(mesh, unbound_region)

    @pytest.mark.audit
    def test_b5_neumann_missing_binding_raises_error(self):
        """
        Verifies: Attempting to apply a Neumann BC to an unbound boundary
        region raises KeyError (BoundaryBindingError equivalent).
        Acceptance criterion: B5 — Missing binding → error raised for Neumann too.
        Passes when: KeyError is raised for an unknown Neumann face name.
        """
        mesh = generate_hex8_mesh(2, 2, 2)
        unbound_region = "no_such_face"
        traction = np.array([1.0, 0.0, 0.0])

        with pytest.raises(KeyError, match=unbound_region):
            compile_neumann(mesh, unbound_region, traction)
