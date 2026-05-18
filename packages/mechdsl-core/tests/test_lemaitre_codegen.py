"""Tests for Phase 6: Lemaitre damage coupling and element deletion (Task P6-2).

Covers plasticity coupling with damage evolution and element deletion at D > D_crit:
    1. Lemaitre emission compiles as valid Python
    2. Element deletion skip-in-assembly (element with D > D_crit contributes zero force)
    3. D = 0 everywhere reproduces J2 power-law structural behaviour (no damage paths active)
"""

from __future__ import annotations

import ast

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

# ---------------------------------------------------------------------------
# Bundle factories
# ---------------------------------------------------------------------------


def _make_lemaitre_bundle(*, D_crit: float = 0.95, eps_D: float = 0.01) -> ArtifactBundle:
    """Create a TL Hex8 bundle with the Lemaitre damage material."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="lemaitre",
            params={
                "E": 200e3,
                "nu": 0.3,
                "sigma_y": 250.0,
                "n_exp": 10.0,
                "S_d": 1.0,
                "s_d": 1.0,
                "eps_D": eps_D,
                "D_crit": D_crit,
            },
        ),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc, plans)


def _make_j2_bundle() -> ArtifactBundle:
    """Create a TL Hex8 bundle with the J2 power-law plasticity material."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y": 250.0, "n_exp": 10.0},
        ),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc, plans)


# ============================================================================
# P6-2: Lemaitre damage coupling + element deletion
# ============================================================================


class TestTaskP6_2:
    """Tests for Lemaitre damage integration (plasticity coupling + D_crit deletion)."""

    @pytest.mark.integration
    def test_lemaitre_emission_compiles(self) -> None:
        """Emitted Lemaitre code parses as valid Python and exposes the
        expected damage symbols.

        Asserts:
        * ``ast.parse`` succeeds (no SyntaxError).
        * The constitutive wrapper ``constitutive_update_lemaitre`` is defined.
        * The element-deletion fields ``damage_D`` and ``is_deleted`` are
          declared.
        * The damage critical threshold ``D_crit`` is threaded into the
          internal-force kernel signature.
        """
        bundle = _make_lemaitre_bundle()
        source = emit(bundle)

        # Valid Python -- catches every emitter-side syntactic regression.
        ast.parse(source)

        # Constitutive wrapper is defined and called.
        assert "def constitutive_update_lemaitre(" in source
        assert "constitutive_update_lemaitre(" in source

        # Damage history fields declared and allocated.
        assert "damage_D = ti.field" in source
        assert "is_deleted = ti.field" in source
        assert ".place(damage_D)" in source
        assert ".place(is_deleted)" in source

        # The internal-force kernel takes D_crit and uses it for deletion
        # detection.
        assert "D_crit: ti.f64" in source
        assert "D_crit" in source
        assert "is_deleted[e] = 1" in source

    @pytest.mark.integration
    def test_element_deletion_skip_in_assembly(self) -> None:
        """Element deletion is wired in both the assembly (force) and the
        tangent matvec.

        We assert at the *source* level (cheap, no Taichi compile required):
        the generated kernels must contain a one-way ``is_deleted`` guard at
        the element-loop head that ``continue``s past failed elements.  The
        runtime compile + numerical check is exercised by the Phase 6
        acceptance test (P6-3, ``test_lemaitre_acceptance.py``) which is
        marked ``slow``.

        Asserts:
        * Internal-force kernel checks ``is_deleted[e] != 0`` and ``continue``s.
        * Tangent matvec checks the snapshotted ``is_deleted_np[e]`` and
          ``continue``s.
        * Damage breach (``damage_D[e, q_chk] > D_crit``) sets
          ``is_deleted[e] = 1`` -- the one-way deletion contract.
        """
        bundle = _make_lemaitre_bundle(D_crit=0.95)
        source = emit(bundle)

        # ----- Internal-force assembly skips deleted elements ----------
        # Look for the deletion guard inside compute_internal_force.
        force_marker = "def compute_internal_force("
        force_idx = source.find(force_marker)
        assert force_idx != -1, "compute_internal_force kernel must be emitted"
        # Slice from the kernel start to the next top-level def (or EOF) and
        # check the guard appears within the kernel body.
        next_def = source.find("\ndef ", force_idx + 1)
        force_body = source[force_idx : next_def if next_def != -1 else len(source)]
        assert "if is_deleted[e] != 0:" in force_body, (
            "Internal-force kernel must guard on is_deleted before the QP loop"
        )
        assert "continue" in force_body, "Internal-force kernel must continue past deleted elements"

        # ----- Tangent matvec skips deleted elements -------------------
        tangent_marker = "def tangent_matvec("
        tangent_idx = source.find(tangent_marker)
        assert tangent_idx != -1, "tangent_matvec must be emitted"
        # Slice the tangent matvec body (Python function, may contain a kernel
        # inside).
        next_def_t = source.find("\ndef ", tangent_idx + 1)
        tangent_body = source[tangent_idx : next_def_t if next_def_t != -1 else len(source)]
        assert "is_deleted_np = is_deleted.to_numpy()" in tangent_body, (
            "Tangent matvec must snapshot is_deleted to numpy before scatter"
        )
        assert "if is_deleted_np[e] != 0:" in tangent_body, (
            "Tangent matvec must guard on the is_deleted snapshot"
        )

        # ----- Deletion is one-way: damage breach sets is_deleted = 1 --
        assert "if damage_D[e, q_chk] > D_crit:" in source, (
            "Deletion detector must compare damage_D against D_crit"
        )
        assert "is_deleted[e] = 1" in source, (
            "Once detected, is_deleted must be set to 1 (one-way deletion)"
        )

    @pytest.mark.integration
    def test_d_zero_matches_j2_emission(self) -> None:
        """When the Lemaitre source is generated, the underlying J2 radial
        return is emitted verbatim and the damage layer is a strict superset.

        Strategy: the Lemaitre emission re-uses ``constitutive_update_plastic``
        for the effective-stress radial return.  When damage never grows
        (D = 0 throughout), the wrapper degenerates to ``S_eff`` -- so the
        J2 return-map source must appear **byte-identically** inside the
        Lemaitre source.  This is a structural regression guard: if a future
        refactor diverges the J2 inner kernel between materials, this test
        catches it before any numerical drift can occur.

        We also assert the Lemaitre source is a strict superset (contains the
        damage symbols ``D_new``, ``constitutive_update_lemaitre``,
        ``damage_D``) that the J2 source does not.
        """
        j2_source = emit(_make_j2_bundle())
        lem_source = emit(_make_lemaitre_bundle())

        # ----- J2 inner kernel is emitted verbatim inside Lemaitre ------
        # The J2 return-map function is the bytecode-stable identifier of
        # plastic behaviour at D=0.  Extract its definition from the J2
        # source and assert the same definition appears in the Lemaitre
        # source.
        marker = "def constitutive_update_plastic("
        j2_start = j2_source.find(marker)
        assert j2_start != -1, "J2 source must define constitutive_update_plastic"
        # The J2 function body ends at the next top-level def or the next
        # ``# ===`` banner.
        j2_end_def = j2_source.find("\ndef ", j2_start + 1)
        j2_end_banner = j2_source.find("\n# ====", j2_start + 1)
        candidates = [x for x in (j2_end_def, j2_end_banner) if x != -1]
        j2_end = min(candidates) if candidates else len(j2_source)
        j2_func_block = j2_source[j2_start:j2_end].rstrip()

        assert j2_func_block in lem_source, (
            "Lemaitre emission must contain the J2 constitutive_update_plastic "
            "function byte-for-byte (D=0 path delegates to it)."
        )

        # ----- Lemaitre is a strict superset --------------------------
        damage_only_symbols = (
            "constitutive_update_lemaitre",
            "damage_D",
            "is_deleted",
            "D_new",
            "D_crit",
        )
        for sym in damage_only_symbols:
            assert sym in lem_source, f"Lemaitre source must contain '{sym}'"
            assert sym not in j2_source, f"J2 source must not contain damage-only symbol '{sym}'"
