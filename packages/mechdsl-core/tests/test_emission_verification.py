"""Verification tests for emitted Taichi code structure and correctness.

Tasks covered:
    P6.3 — Elastic constitutive emission (SVK stress formula, kinematics, CSE)
    P6.4 — Internal force kernel emission (element/quad loops, PK1, scatter)
    P6.5 — Tangent matvec emission (FD perturbation, BC enforcement, infra reuse)
    P7.1 — Newton driver emission (loop structure, residual, convergence, update)

Verification strategy:
    Since Taichi JIT is slow and may not be available in CI, we verify emitted
    code via source-level pattern checks, AST structural analysis, and
    cross-referencing constitutive expressions against the symbolic models.
"""

from __future__ import annotations

import ast
import re

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

pytestmark = pytest.mark.stable_backend

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_svk_problem_ir() -> ProblemIR:
    """Create an SVK ProblemIR for testing."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )


def _make_svk_bundle() -> ArtifactBundle:
    """Create a test bundle with SVK material."""
    problem_ir = _make_svk_problem_ir()
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


@pytest.fixture
def svk_bundle() -> ArtifactBundle:
    return _make_svk_bundle()


@pytest.fixture
def svk_source(svk_bundle: ArtifactBundle) -> str:
    return emit(svk_bundle)


@pytest.fixture
def svk_ast(svk_source: str) -> ast.Module:
    """Parse emitted source into an AST module."""
    return ast.parse(svk_source)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _find_function_defs(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Extract all top-level function definitions from an AST, keyed by name."""
    funcs: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            funcs[node.name] = node
    return funcs


def _get_source_lines_for_function(source: str, func_name: str) -> str:
    """Extract the source lines for a named function from the emitted code.

    Uses a regex approach: finds ``def func_name(`` and captures until the
    next top-level ``def ``, the next top-level ``# ====`` section banner, or
    end of file. Stopping at the banner keeps a function's slice from absorbing
    the comment header of the *following* emitted section (e.g. the P3-2
    generated ``@ti.kernel`` banner that follows the host ``tangent_matvec``).
    """
    pattern = (
        rf"((?:@\w+[\.\w]*\n)?def {re.escape(func_name)}\(.*?)"
        r"(?=\ndef |\n# ={5,}|\Z)"
    )
    match = re.search(pattern, source, re.DOTALL)
    if match:
        return match.group(1)
    return ""


def _count_pattern(source: str, pattern: str) -> int:
    """Count occurrences of a regex pattern in source."""
    return len(re.findall(pattern, source))


# ===========================================================================
# Elastic constitutive emission tests
# ===========================================================================


class TestElasticConstitutiveEmission:
    """P6.3 — Verify the SVK constitutive function emission is mathematically correct."""

    # -- SVK stress formula --

    def test_svk_stress_formula_complete(self, svk_source: str) -> None:
        """SVK stress: S = lam * tr_E * I + 2 * mu * E must be present."""
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in svk_source

    def test_svk_stress_uses_correct_lame_parameters(self, svk_source: str) -> None:
        """Stress formula must use both Lame parameters (lam and mu)."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        assert "lam" in func_src
        assert "mu" in func_src

    def test_svk_stress_factor_of_two(self, svk_source: str) -> None:
        """The mu term must have the factor 2.0 (not 1.0 or missing)."""
        assert "2.0 * mu * E" in svk_source

    # -- Deformation gradient --

    def test_deformation_gradient_identity_plus_grad_u(self, svk_source: str) -> None:
        """Constitutive receives F; the kernel computes F = I + grad_u."""
        # The kernel builds F starting from identity
        assert "F = ti.Matrix.identity(ti.f64, DIM)" in svk_source
        # Then accumulates displacement gradient
        assert "F[i, I] += u[nid][i] * dNdX[a, I]" in svk_source

    def test_deformation_gradient_comment(self, svk_source: str) -> None:
        """Emitted code documents F = I + grad_u semantics."""
        assert "Deformation gradient F = I + grad_u" in svk_source

    # -- Green-Lagrange strain --

    def test_green_lagrange_strain(self, svk_source: str) -> None:
        """E = 0.5 * (C - I) must be computed in the constitutive function."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        assert "E = 0.5 * (C - I3)" in func_src

    def test_green_lagrange_strain_half_factor(self, svk_source: str) -> None:
        """Green-Lagrange strain uses exactly 0.5 (not 1/2 or missing)."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        assert "0.5 * (C" in func_src

    # -- Right Cauchy-Green tensor --

    def test_right_cauchy_green(self, svk_source: str) -> None:
        """C = F^T @ F must be present in constitutive function."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        assert "C = F.transpose() @ F" in func_src

    def test_cauchy_green_before_strain(self, svk_source: str) -> None:
        """C must be computed before E (ordering matters)."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        pos_c = func_src.find("C = F.transpose() @ F")
        pos_e = func_src.find("E = 0.5 * (C - I3)")
        assert pos_c < pos_e, "C must be computed before E"

    # -- Identity matrix --

    def test_identity_matrix_3x3(self, svk_source: str) -> None:
        """Constitutive uses a properly sized 3x3 identity."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        assert "ti.Matrix.identity(ti.f64, 3)" in func_src

    # -- CSE opportunity — tr_E computed once and reused --

    def test_trace_computed_once(self, svk_source: str) -> None:
        """tr_E should be computed exactly once (CSE opportunity)."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        # tr_E is initialized once and accumulated in a loop
        assert func_src.count("tr_E = ti.f64(0.0)") == 1
        # And then used in the stress formula
        assert "tr_E * I3" in func_src

    def test_trace_uses_static_loop(self, svk_source: str) -> None:
        """Trace computation uses ti.static loop (physics index)."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        # The trace loop is a ti.static physics index loop
        assert "for i in ti.static(range(3)):" in func_src
        assert "tr_E += E[i, i]" in func_src

    def test_trace_not_recomputed_in_stress(self, svk_source: str) -> None:
        """The stress formula uses the cached tr_E, not a recomputation."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        # Should not have E.trace() — we use the precomputed tr_E
        assert "E.trace()" not in func_src

    # -- Constitutive function signature and decorator --

    def test_constitutive_is_ti_func(self, svk_ast: ast.Module) -> None:
        """constitutive_update must be decorated with @ti.func."""
        funcs = _find_function_defs(svk_ast)
        func = funcs["constitutive_update"]
        decorator_names: list[str] = []
        for dec in func.decorator_list:
            decorator_names.append(ast.dump(dec))
        # At least one decorator should reference ti.func
        assert any("func" in d for d in decorator_names)

    def test_constitutive_takes_F_lam_mu(self, svk_source: str) -> None:
        """constitutive_update signature accepts (F, lam, mu)."""
        # Signature spans multiple lines, so use DOTALL to capture across them
        match = re.search(r"def constitutive_update\((.+?)\)\s*(?:->|:)", svk_source, re.DOTALL)
        assert match is not None
        sig = match.group(1)
        assert "F" in sig
        assert "lam" in sig
        assert "mu" in sig

    def test_constitutive_returns_matrix(self, svk_source: str) -> None:
        """constitutive_update returns a 3x3 matrix type."""
        # Signature spans multiple lines; return type annotation follows ')'
        match = re.search(
            r"def constitutive_update\(.+?\)\s*->\s*(\S+)",
            svk_source,
            re.DOTALL,
        )
        assert match is not None
        ret_type = match.group(1)
        assert "matrix" in ret_type.lower() or "ti.types.matrix" in ret_type

    def test_constitutive_returns_S(self, svk_source: str) -> None:
        """constitutive_update returns S (2nd Piola-Kirchhoff stress)."""
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        assert "return S" in func_src

    # -- Cross-reference with symbolic model --

    def test_svk_matches_symbolic_kinematics_chain(self, svk_source: str) -> None:
        """The constitutive function follows the kinematics chain F -> C -> E -> S.

        This cross-references the emitted code against the symbolic model in
        mechdsl.symbolic.kinematics which defines the same chain.
        """
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")

        # The chain must appear in order: C from F, E from C, S from E
        pos_c = func_src.find("C = F.transpose() @ F")
        pos_e = func_src.find("E = 0.5 * (C - I3)")
        pos_s = func_src.find("S = lam * tr_E * I3 + 2.0 * mu * E")

        assert pos_c >= 0, "Missing C = F^T @ F"
        assert pos_e >= 0, "Missing E = 0.5*(C - I)"
        assert pos_s >= 0, "Missing S = lam*tr_E*I + 2*mu*E"
        assert pos_c < pos_e < pos_s, "Kinematics chain out of order"


# ===========================================================================
# Internal force kernel emission tests
# ===========================================================================


class TestInternalForceEmission:
    """P6.4 — Verify the internal force kernel emission is structurally correct."""

    # -- Element loop is present and uses runtime range --

    def test_element_loop_runtime(self, svk_source: str) -> None:
        """Element loop must use runtime range (not ti.static)."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "for e in range(n_elem):" in kernel_src

    def test_element_loop_not_static(self, svk_source: str) -> None:
        """Element loop must NOT use ti.static (mesh index)."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "ti.static(range(n_elem))" not in kernel_src

    # -- Quadrature loop is present --

    def test_quadrature_loop_static(self, svk_source: str) -> None:
        """Quadrature loop uses ti.static (N_QP=8 is element-type constant)."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "for q in ti.static(range(N_QP)):" in kernel_src

    def test_quadrature_loop_inside_element_loop(self, svk_source: str) -> None:
        """Quadrature loop must be inside the element loop."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        pos_e = kernel_src.find("for e in range(n_elem):")
        pos_q = kernel_src.find("for q in ti.static(range(N_QP)):")
        assert pos_e >= 0, "Element loop missing"
        assert pos_q >= 0, "Quadrature loop missing"
        assert pos_e < pos_q, "Quadrature loop must be nested inside element loop"

    # -- Constitutive call present --

    def test_constitutive_call_inside_kernel(self, svk_source: str) -> None:
        """Internal force kernel must call constitutive_update."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "S = constitutive_update(F, lam, mu)" in kernel_src

    def test_constitutive_call_after_F_computation(self, svk_source: str) -> None:
        """Constitutive call must come after F is computed."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        pos_f = kernel_src.find("F = ti.Matrix.identity(ti.f64, DIM)")
        pos_s = kernel_src.find("S = constitutive_update(F, lam, mu)")
        assert pos_f < pos_s, "F must be computed before calling constitutive_update"

    # -- PK1 computation (P = F @ S) --

    def test_pk1_stress(self, svk_source: str) -> None:
        """1st Piola-Kirchhoff stress P = F @ S must be computed."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "P = F @ S" in kernel_src

    def test_pk1_after_constitutive(self, svk_source: str) -> None:
        """P = F @ S must come after S = constitutive_update(...)."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        pos_s = kernel_src.find("S = constitutive_update(F, lam, mu)")
        pos_p = kernel_src.find("P = F @ S")
        assert pos_s < pos_p, "P must be computed after S"

    # -- Force scatter --

    def test_force_scatter_accumulation(self, svk_source: str) -> None:
        """Internal force kernel accumulates into f_int via atomic-safe pattern."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "f_int[nid][i] +=" in kernel_src

    def test_force_scatter_uses_quadrature_weight(self, svk_source: str) -> None:
        """Force scatter includes quadrature weight w_q."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "w_q = QUAD_WEIGHTS[q]" in kernel_src
        assert "w_q * detJ0" in kernel_src

    def test_force_scatter_uses_detJ(self, svk_source: str) -> None:
        """Force scatter includes Jacobian determinant detJ0."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "detJ0 = J0.determinant()" in kernel_src
        assert "w_q * detJ0 * force_a[i]" in kernel_src

    # -- Nodal gathering --

    def test_reference_coords_gathered(self, svk_source: str) -> None:
        """Element gathers reference coordinates from x_ref."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "X_elem[a, d] = x_ref[nid][d]" in kernel_src

    def test_displacements_gathered(self, svk_source: str) -> None:
        """Element gathers displacements from u field."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "x_elem[a, d] = x_ref[nid][d] + u[nid][d]" in kernel_src

    def test_connectivity_used(self, svk_source: str) -> None:
        """Element uses elem_nodes for connectivity."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "nid = elem_nodes[e, a]" in kernel_src

    # -- Kernel decorator --

    def test_internal_force_is_ti_kernel(self, svk_source: str) -> None:
        """compute_internal_force must be decorated with @ti.kernel."""
        # Find @ti.kernel immediately before def compute_internal_force
        pattern = r"@ti\.kernel\s+def compute_internal_force\("
        assert re.search(pattern, svk_source), (
            "compute_internal_force must be decorated with @ti.kernel"
        )

    # -- Index partitioning correctness --

    def test_node_loops_use_runtime(self, svk_source: str) -> None:
        """Node loops (N_NODES=8 > 6) use runtime range per convention."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "for a in range(N_NODES):" in kernel_src

    def test_grad_gather_node_loop_static(self, svk_source: str) -> None:
        """GRAD_AT_QUAD gather node loop keeps ti.static for Python list access."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "for a in ti.static(range(N_NODES)):" in kernel_src

    def test_dim_loops_use_static(self, svk_source: str) -> None:
        """Dimension loops within the kernel use ti.static."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "for d in ti.static(range(DIM)):" in kernel_src
        assert "for i in ti.static(range(DIM)):" in kernel_src
        assert "for I in ti.static(range(DIM)):" in kernel_src

    # -- f_int zeroed before accumulation --

    def test_f_int_zeroed(self, svk_source: str) -> None:
        """Internal force must be zeroed before the element loop."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        pos_zero = kernel_src.find("f_int[i] = ti.Vector([0.0, 0.0, 0.0]")
        pos_elem = kernel_src.find("for e in range(n_elem):")
        assert pos_zero >= 0, "f_int zeroing not found"
        assert pos_elem >= 0, "Element loop not found"
        assert pos_zero < pos_elem, "f_int must be zeroed before element loop"

    # -- Jacobian computation --

    def test_jacobian_computation(self, svk_source: str) -> None:
        """Reference Jacobian J0, its inverse, and determinant are computed."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "J0 = X_elem.transpose() @ dN_dxi" in kernel_src
        assert "J0_inv = J0.inverse()" in kernel_src
        assert "detJ0 = J0.determinant()" in kernel_src

    def test_shape_function_gradient_transform(self, svk_source: str) -> None:
        """dN/dX = dN/dxi @ J0^{-1} must be present."""
        kernel_src = _get_source_lines_for_function(svk_source, "compute_internal_force")
        assert "dNdX = dN_dxi @ J0_inv" in kernel_src

    # -- AST structural checks --

    def test_kernel_has_for_loops(self, svk_ast: ast.Module) -> None:
        """compute_internal_force must contain For loop nodes in its AST."""
        funcs = _find_function_defs(svk_ast)
        func = funcs["compute_internal_force"]
        for_nodes = [n for n in ast.walk(func) if isinstance(n, ast.For)]
        # Must have at least: zeroing loop, element loop, quad loop, node loops
        assert len(for_nodes) >= 4, (
            f"Expected at least 4 for-loops in internal force kernel, found {len(for_nodes)}"
        )


# ===========================================================================
# Tangent matvec emission tests
# ===========================================================================


class TestTangentMatvecEmission:
    """P6.5 — Verify the analytical consistent-tangent matvec emission.

    These tests previously asserted the finite-difference tangent structure
    (``FD_EPS``, ``f_plus``, ``f_minus``, central-difference formula).
    PLAN-A §A7.5 and §A9.2 replaced that with an analytical linearisation,
    so the assertions now target the analytical source structure:

    - an element-level loop that computes F, E, and the linearised strain dE
    - SVK tangent contraction expressed in closed form
      (``lam * tr(dE) * I + 2 * mu * dE``)
    - the push-forward ``dP = grad_v @ S + F @ dS``
    - the gather / scatter pattern via ``Kv_e`` accumulated per element
    """

    # -- Analytical linearisation is element-local --

    def test_loops_over_elements(self, svk_source: str) -> None:
        """Tangent matvec iterates over elements via a Python range loop."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "for e in range(n_elem)" in matvec_src

    def test_loops_over_quadrature_points(self, svk_source: str) -> None:
        """Each element loops over quadrature points."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "for q in range(N_QP)" in matvec_src

    def test_computes_reference_jacobian(self, svk_source: str) -> None:
        """Reference Jacobian J0 = X^T @ dN/dxi with positive-det guard."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "X_elem.T @ dN_dxi" in matvec_src
        assert "np.linalg.det(J0)" in matvec_src
        assert "detJ0 <= 1e-15" in matvec_src

    def test_computes_current_kinematics(self, svk_source: str) -> None:
        """F = I + grad_u and Green-Lagrange strain E are computed per QP."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "grad_u = u_elem.T @ dN_dX" in matvec_src
        assert "F = I3 + grad_u" in matvec_src
        assert "E = 0.5 * (F.T @ F - I3)" in matvec_src

    def test_computes_linearised_strain(self, svk_source: str) -> None:
        """Linearised strain dE = 0.5 (F^T grad_v + grad_v^T F)."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "grad_v = v_elem.T @ dN_dX" in matvec_src
        assert "dE = 0.5 * (F.T @ grad_v + grad_v.T @ F)" in matvec_src

    def test_svk_material_tangent_closed_form(self, svk_source: str) -> None:
        """SVK emits the closed-form constant-tangent contraction (no einsum)."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        # Stress update
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in matvec_src
        # Linearised-stress update using the same constant closed form
        assert "dS = lam * tr_dE * I3 + 2.0 * mu * dE" in matvec_src
        # And does NOT fall back to the fourth-order contraction path
        assert "einsum" not in matvec_src

    def test_push_forward_linearisation(self, svk_source: str) -> None:
        """dP = grad_v @ S + F @ dS (geometric + material terms)."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "dP = grad_v @ S + F @ dS" in matvec_src

    def test_element_scatter(self, svk_source: str) -> None:
        """Element contribution is accumulated into Kv_e and scattered to Kv."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "Kv_e += w_q * detJ0 * (dN_dX @ dP.T)" in matvec_src
        assert "Kv[nodes[a]] += Kv_e[a]" in matvec_src

    # -- Non-mutating with respect to Taichi fields --

    def test_reads_fields_via_to_numpy(self, svk_source: str) -> None:
        """Taichi fields are read once, never written."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "u.to_numpy()" in matvec_src
        assert "x_ref.to_numpy()" in matvec_src
        assert "elem_nodes.to_numpy()" in matvec_src
        # Analytical matvec must not round-trip state back into any Taichi field.
        assert "u.from_numpy" not in matvec_src

    def test_does_not_call_internal_force(self, svk_source: str) -> None:
        """Analytical matvec must not invoke compute_internal_force."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "compute_internal_force(" not in matvec_src

    # -- Input/output shape handling --

    def test_reshapes_input_vector(self, svk_source: str) -> None:
        """Input flat vector is reshaped to (n_nodes, 3)."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert "v_flat.reshape((-1, 3))" in matvec_src

    def test_returns_flat_vector(self, svk_source: str) -> None:
        """Output is returned as a flat vector via ravel()."""
        matvec_src = _get_source_lines_for_function(svk_source, "tangent_matvec")
        assert ".ravel()" in matvec_src

    # -- Function signature --

    def test_matvec_signature(self, svk_source: str) -> None:
        """tangent_matvec takes (v_flat, lam, mu) and returns ndarray."""
        match = re.search(r"def tangent_matvec\(([^)]+)\)", svk_source)
        assert match is not None
        sig = match.group(1)
        assert "v_flat" in sig
        assert "lam" in sig
        assert "mu" in sig

    # -- Not a ti.kernel (runs at Python level for numpy ops) --

    def test_matvec_is_python_function(self, svk_source: str) -> None:
        """tangent_matvec must NOT be a @ti.kernel (it uses numpy)."""
        # Find the decorator-def pair
        pattern = r"@ti\.kernel\s+def tangent_matvec\("
        assert not re.search(pattern, svk_source), (
            "tangent_matvec should be a Python function, not a @ti.kernel"
        )


# ===========================================================================
# Newton driver emission tests
# ===========================================================================


class TestNewtonDriverEmission:
    """P7.1 — Verify the Newton-Raphson driver emission."""

    # -- Newton loop structure --

    def test_newton_iteration_loop(self, svk_source: str) -> None:
        """Newton driver has an iteration loop over max_iter."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "for iteration in range(max_iter):" in driver_src

    def test_max_iter_parameter(self, svk_source: str) -> None:
        """Newton driver accepts max_iter parameter with default."""
        match = re.search(r"def newton_solve\(([^)]+)\)", svk_source, re.DOTALL)
        assert match is not None
        sig = match.group(1)
        assert "max_iter" in sig

    def test_tolerance_parameter(self, svk_source: str) -> None:
        """Newton driver accepts tol parameter with default."""
        match = re.search(r"def newton_solve\(([^)]+)\)", svk_source, re.DOTALL)
        assert match is not None
        sig = match.group(1)
        assert "tol" in sig

    # -- Residual computation --

    def test_residual_is_fint_minus_fext(self, svk_source: str) -> None:
        """Residual = f_int - f_ext (tension-positive convention)."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "f_int.to_numpy() - f_ext.to_numpy()" in driver_src

    def test_residual_norm_computed(self, svk_source: str) -> None:
        """Residual norm is computed for convergence check."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "np.linalg.norm(r_flat)" in driver_src

    # -- Convergence check --

    def test_convergence_check_against_tol(self, svk_source: str) -> None:
        """Convergence check: res_norm < conv_threshold (dual abs/rel tolerance)."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "if res_norm < conv_threshold:" in driver_src

    def test_early_return_on_convergence(self, svk_source: str) -> None:
        """Driver returns early when converged."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "return iteration" in driver_src

    def test_convergence_check_before_solve(self, svk_source: str) -> None:
        """Convergence check must come before linear solve in the loop."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        pos_check = driver_src.find("if res_norm < conv_threshold:")
        pos_solve = driver_src.find("solver.solve(")
        assert pos_check < pos_solve, "Convergence check must precede linear solve"

    # -- Linear solve --

    def test_linear_solve_call(self, svk_source: str) -> None:
        """Newton driver calls the project's CGSolver for the linear system."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "solver.solve(" in driver_src

    def test_solver_uses_project_cg(self, svk_source: str) -> None:
        """CGSolver is imported from the project's solver adapter, not scipy."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "CGSolver" in driver_src
        assert "tangent_matvec(" in driver_src

    def test_solves_negative_residual(self, svk_source: str) -> None:
        """CG solves K @ du = -R (negative residual as RHS)."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "-r_flat" in driver_src

    def test_cg_convergence_warning(self, svk_source: str) -> None:
        """Driver warns if CG residual is not within tolerance."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "cg_res" in driver_src

    # -- Displacement update --

    def test_displacement_update(self, svk_source: str) -> None:
        """u += du update must be present."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "u_arr + du_arr" in driver_src

    def test_displacement_written_back(self, svk_source: str) -> None:
        """Updated displacement is written back via u.from_numpy(...)."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "u.from_numpy(u_arr + du_arr)" in driver_src

    # -- Newton loop ordering --

    def test_newton_step_ordering(self, svk_source: str) -> None:
        """Newton steps must be in order: f_int, residual, check, solve, update."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")

        pos_fint = driver_src.find("compute_internal_force(lam, mu)")
        pos_residual = driver_src.find("f_int.to_numpy() - f_ext.to_numpy()")
        pos_check = driver_src.find("if res_norm < conv_threshold:")
        pos_solve = driver_src.find("solver.solve(")
        pos_update = driver_src.find("u.from_numpy(u_arr + du_arr)")

        positions = [pos_fint, pos_residual, pos_check, pos_solve, pos_update]
        assert all(p >= 0 for p in positions), f"Missing Newton step(s): positions = {positions}"
        assert positions == sorted(positions), (
            "Newton steps out of order: expected f_int -> residual -> check -> solve -> update"
        )

    # -- Non-convergence handling --

    def test_raises_on_non_convergence(self, svk_source: str) -> None:
        """Driver raises RuntimeError if convergence is not reached."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "raise RuntimeError" in driver_src
        assert "did not converge" in driver_src

    # -- Internal force is called within Newton --

    def test_newton_calls_internal_force(self, svk_source: str) -> None:
        """Newton driver calls compute_internal_force."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "compute_internal_force(lam, mu)" in driver_src

    # -- Solver import --

    def test_project_solver_import(self, svk_source: str) -> None:
        """Newton driver imports the project's CGSolver, not scipy."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "from mechdsl.solver.import_adapter import CGSolver" in driver_src
        assert "scipy" not in driver_src

    # -- n_dof computation --

    def test_n_dof_computation(self, svk_source: str) -> None:
        """Newton driver computes n_dof = n_nodes * DIM."""
        driver_src = _get_source_lines_for_function(svk_source, "newton_solve")
        assert "n_dof = n_nodes * DIM" in driver_src

    # -- AST structural checks --

    def test_newton_has_for_loop(self, svk_ast: ast.Module) -> None:
        """newton_solve must contain at least one For loop (the Newton iteration)."""
        funcs = _find_function_defs(svk_ast)
        func = funcs["newton_solve"]
        for_nodes = [n for n in ast.walk(func) if isinstance(n, ast.For)]
        assert len(for_nodes) >= 1, "Newton driver must have an iteration loop"

    def test_newton_has_if_statement(self, svk_ast: ast.Module) -> None:
        """newton_solve must contain If statements (convergence check, CG check)."""
        funcs = _find_function_defs(svk_ast)
        func = funcs["newton_solve"]
        if_nodes = [n for n in ast.walk(func) if isinstance(n, ast.If)]
        assert len(if_nodes) >= 2, (
            "Newton driver must have at least 2 if-statements "
            "(convergence check + CG divergence check)"
        )

    def test_newton_is_python_function(self, svk_source: str) -> None:
        """newton_solve must NOT be a @ti.kernel (it orchestrates at Python level)."""
        pattern = r"@ti\.kernel\s+def newton_solve\("
        assert not re.search(pattern, svk_source), (
            "newton_solve should be a Python function, not a @ti.kernel"
        )


# ===========================================================================
# Cross-cutting: emitted source overall quality
# ===========================================================================


class TestEmittedSourceQuality:
    """Cross-cutting quality checks that span all four tasks."""

    def test_entire_source_parses(self, svk_source: str) -> None:
        """Full emitted source must be syntactically valid Python."""
        try:
            ast.parse(svk_source)
        except SyntaxError as exc:
            pytest.fail(f"Emitted source has syntax error: {exc}")

    def test_all_four_functions_present(self, svk_ast: ast.Module) -> None:
        """All four major functions must be present in the emitted code."""
        funcs = _find_function_defs(svk_ast)
        for name in [
            "constitutive_update",
            "compute_internal_force",
            "tangent_matvec",
            "newton_solve",
        ]:
            assert name in funcs, f"Missing function: {name}"

    def test_no_placeholder_todos_in_svk(self, svk_source: str) -> None:
        """SVK emission should not have TODO placeholders (J2 does, SVK does not)."""  # intentional-cleanup-site
        # Check specifically in the constitutive function
        func_src = _get_source_lines_for_function(svk_source, "constitutive_update")
        assert "TODO" not in func_src, (
            "SVK constitutive should not have TODO placeholders"
        )  # intentional-cleanup-site
        # The two `# intentional-cleanup-site` markers above are scanned by
        # test_phase6_exit.py in place of a hardcoded line-number whitelist.

    def test_consistent_lame_parameter_names(self, svk_source: str) -> None:
        """Lame parameters are consistently named 'lam' and 'mu' throughout."""
        # Check that kernel, constitutive, matvec, and driver all use same names
        for func_name in [
            "constitutive_update",
            "compute_internal_force",
            "tangent_matvec",
            "newton_solve",
        ]:
            func_src = _get_source_lines_for_function(svk_source, func_name)
            if func_src:
                # At least one of lam/mu should be present in each
                assert "lam" in func_src or "mu" in func_src, (
                    f"Function {func_name} does not reference Lame parameters"
                )

    def test_f64_throughout(self, svk_source: str) -> None:
        """No f32 should appear anywhere in the emitted code."""
        assert "ti.f32" not in svk_source
        assert "float32" not in svk_source

    def test_deterministic_emission(self, svk_bundle: ArtifactBundle) -> None:
        """Same bundle produces identical output on repeated calls."""
        source_a = emit(svk_bundle)
        source_b = emit(svk_bundle)
        assert source_a == source_b
