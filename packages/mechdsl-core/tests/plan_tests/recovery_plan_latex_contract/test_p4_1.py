"""Live audit for recovery-plan P4-1: ElementIR execution-contract enrichment.

Asserts that:

1. The four optional enrichment dataclasses (``GeometrySummary``,
   ``MaterialEvalContract``, ``LocalForceDescriptor``,
   ``LocalTangentDescriptor``) round-trip standalone and reject malformed
   inputs at construction time.
2. ``ElementIR`` carries the four optional fields with safe ``None``
   defaults so legacy callers continue working.
3. ``ElementIR.to_dict / from_dict`` round-trip both legacy and enriched
   forms.
4. Construction-time consistency checks fire on mismatched descriptors —
   wrong ``n_dof``, wrong ``n_quad``, formulation / stress-measure
   conflict.
5. The exported ``ALLOWED_STRESS_MEASURES`` / ``ALLOWED_STRAIN_MEASURES``
   sets stay aligned with the dataclass validators.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mechdsl.ir.element_ir import (
    ALLOWED_STRAIN_MEASURES,
    ALLOWED_STRESS_MEASURES,
    ElementIR,
    GeometrySummary,
    LocalForceDescriptor,
    LocalTangentDescriptor,
    MaterialEvalContract,
    create_hex8_element_ir,
)

# ---------------------------------------------------------------------------
# 1. Enrichment dataclasses round-trip and validate
# ---------------------------------------------------------------------------


class TestGeometrySummary:
    @pytest.mark.integration
    def test_round_trip(self) -> None:
        g = GeometrySummary(n_quad=8, reference_volume=8.0, natural_coord_dim=3)
        assert GeometrySummary.from_dict(g.to_dict()) == g

    @pytest.mark.integration
    def test_rejects_zero_n_quad(self) -> None:
        with pytest.raises(ValueError, match=r"n_quad must be >= 1"):
            GeometrySummary(n_quad=0, reference_volume=8.0)

    @pytest.mark.integration
    def test_rejects_nonpositive_volume(self) -> None:
        with pytest.raises(ValueError, match=r"reference_volume must be > 0"):
            GeometrySummary(n_quad=8, reference_volume=-1.0)

    @pytest.mark.integration
    def test_rejects_invalid_natural_dim(self) -> None:
        with pytest.raises(ValueError, match=r"natural_coord_dim must be 1, 2, or 3"):
            GeometrySummary(n_quad=8, reference_volume=8.0, natural_coord_dim=4)


class TestMaterialEvalContract:
    @pytest.mark.integration
    def test_round_trip(self) -> None:
        me = MaterialEvalContract(
            stress_measure="pk2",
            strain_measure="green_lagrange",
            tangent_rank=4,
            voigt_size=6,
            metadata={"family": "elastic"},
        )
        assert MaterialEvalContract.from_dict(me.to_dict()) == me

    @pytest.mark.integration
    def test_rejects_unknown_stress_measure(self) -> None:
        with pytest.raises(ValueError, match=r"stress_measure='kirchhoff'"):
            MaterialEvalContract(stress_measure="kirchhoff")

    @pytest.mark.integration
    def test_rejects_unknown_strain_measure(self) -> None:
        with pytest.raises(ValueError, match=r"strain_measure='hencky'"):
            MaterialEvalContract(strain_measure="hencky")

    @pytest.mark.integration
    def test_rejects_invalid_tangent_rank(self) -> None:
        with pytest.raises(ValueError, match=r"tangent_rank must be 2"):
            MaterialEvalContract(tangent_rank=3)

    @pytest.mark.integration
    def test_metadata_is_immutable(self) -> None:
        me = MaterialEvalContract(metadata={"k": 1})
        with pytest.raises(TypeError):
            me.metadata["k"] = 2  # type: ignore[index]
        with pytest.raises(AttributeError):
            me.metadata.pop("k")  # type: ignore[attr-defined]

    @pytest.mark.integration
    def test_allowed_measure_sets_are_frozensets(self) -> None:
        assert isinstance(ALLOWED_STRESS_MEASURES, frozenset)
        assert isinstance(ALLOWED_STRAIN_MEASURES, frozenset)
        assert frozenset({"pk2", "cauchy"}) == ALLOWED_STRESS_MEASURES


class TestLocalForceAndTangentDescriptors:
    @pytest.mark.integration
    def test_force_round_trip(self) -> None:
        lf = LocalForceDescriptor(n_dof=24, contraction_sketch="aI,iI->ai")
        assert LocalForceDescriptor.from_dict(lf.to_dict()) == lf

    @pytest.mark.integration
    def test_tangent_round_trip(self) -> None:
        lt = LocalTangentDescriptor(n_dof=24, is_symmetric=True)
        assert LocalTangentDescriptor.from_dict(lt.to_dict()) == lt

    @pytest.mark.integration
    def test_force_rejects_zero_n_dof(self) -> None:
        with pytest.raises(ValueError, match=r"LocalForceDescriptor.n_dof"):
            LocalForceDescriptor(n_dof=0)

    @pytest.mark.integration
    def test_tangent_rejects_zero_n_dof(self) -> None:
        with pytest.raises(ValueError, match=r"LocalTangentDescriptor.n_dof"):
            LocalTangentDescriptor(n_dof=0)


# ---------------------------------------------------------------------------
# 2. ElementIR carries the four optional fields with safe defaults
# ---------------------------------------------------------------------------


class TestElementIREnrichmentFields:
    @pytest.mark.integration
    def test_legacy_ir_has_safe_default_enrichment(self) -> None:
        ir = create_hex8_element_ir()
        assert ir.geometry is None
        assert ir.material_eval is None
        assert ir.local_force is None
        assert ir.local_tangent is None

    @pytest.mark.integration
    def test_enriched_ir_carries_populated_fields(self) -> None:
        legacy = create_hex8_element_ir()
        enriched = replace(
            legacy,
            geometry=GeometrySummary(n_quad=8, reference_volume=8.0),
            material_eval=MaterialEvalContract(),
            local_force=LocalForceDescriptor(n_dof=24),
            local_tangent=LocalTangentDescriptor(n_dof=24),
        )
        assert enriched.geometry is not None and enriched.geometry.n_quad == 8
        assert enriched.material_eval is not None
        assert enriched.local_force is not None and enriched.local_force.n_dof == 24
        assert enriched.local_tangent is not None and enriched.local_tangent.is_symmetric


# ---------------------------------------------------------------------------
# 3. Construction-time consistency checks
# ---------------------------------------------------------------------------


class TestEnrichmentConsistencyChecks:
    @pytest.mark.integration
    def test_geometry_n_quad_must_match_quadrature_n_points(self) -> None:
        legacy = create_hex8_element_ir()
        with pytest.raises(ValueError, match=r"GeometrySummary.n_quad"):
            replace(legacy, geometry=GeometrySummary(n_quad=4, reference_volume=8.0))

    @pytest.mark.integration
    def test_local_force_n_dof_must_match_n_nodes_times_dim(self) -> None:
        legacy = create_hex8_element_ir()
        with pytest.raises(ValueError, match=r"LocalForceDescriptor.n_dof"):
            replace(legacy, local_force=LocalForceDescriptor(n_dof=12))

    @pytest.mark.integration
    def test_local_tangent_n_dof_must_match_n_nodes_times_dim(self) -> None:
        legacy = create_hex8_element_ir()
        with pytest.raises(ValueError, match=r"LocalTangentDescriptor.n_dof"):
            replace(legacy, local_tangent=LocalTangentDescriptor(n_dof=12))

    @pytest.mark.integration
    def test_reference_configuration_requires_pk2(self) -> None:
        legacy = create_hex8_element_ir()
        with pytest.raises(ValueError, match=r"configuration='reference' requires"):
            replace(legacy, material_eval=MaterialEvalContract(stress_measure="cauchy"))

    @pytest.mark.integration
    def test_current_configuration_requires_cauchy(self) -> None:
        legacy = create_hex8_element_ir(formulation="updated_lagrangian", configuration="current")
        with pytest.raises(ValueError, match=r"configuration='current' requires"):
            replace(legacy, material_eval=MaterialEvalContract(stress_measure="pk2"))


# ---------------------------------------------------------------------------
# 4. ElementIR.to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


class TestElementIRRoundTrip:
    @pytest.mark.integration
    def test_legacy_round_trip(self) -> None:
        legacy = create_hex8_element_ir()
        rebuilt = ElementIR.from_dict(legacy.to_dict())
        assert rebuilt.element_type == legacy.element_type
        assert rebuilt.n_nodes == legacy.n_nodes
        assert rebuilt.formulation == legacy.formulation
        assert rebuilt.configuration == legacy.configuration
        assert rebuilt.geometry is None
        assert rebuilt.material_eval is None
        assert rebuilt.local_force is None
        assert rebuilt.local_tangent is None

    @pytest.mark.integration
    def test_enriched_round_trip(self) -> None:
        legacy = create_hex8_element_ir()
        enriched = replace(
            legacy,
            geometry=GeometrySummary(n_quad=8, reference_volume=8.0),
            material_eval=MaterialEvalContract(metadata={"family": "elastic"}),
            local_force=LocalForceDescriptor(n_dof=24, contraction_sketch="aI,iI->ai"),
            local_tangent=LocalTangentDescriptor(n_dof=24, is_symmetric=True),
        )
        rebuilt = ElementIR.from_dict(enriched.to_dict())
        assert rebuilt.geometry == enriched.geometry
        assert rebuilt.material_eval == enriched.material_eval
        assert rebuilt.local_force == enriched.local_force
        assert rebuilt.local_tangent == enriched.local_tangent

    @pytest.mark.integration
    def test_to_dict_always_emits_enrichment_keys(self) -> None:
        legacy = create_hex8_element_ir()
        d = legacy.to_dict()
        for key in ("geometry", "material_eval", "local_force", "local_tangent"):
            assert key in d, f"to_dict() must always emit `{key}` for forward consumers"
            assert d[key] is None  # safe default for the legacy IR

    @pytest.mark.integration
    def test_from_dict_accepts_legacy_dict(self) -> None:
        # Pre-P4-1 golden dict — no enrichment keys, no integration_rule key.
        legacy_dict = {
            "element_type": "hex8",
            "n_nodes": 8,
            "dim": 3,
            "formulation": "total_lagrangian",
            "configuration": "reference",
        }
        rebuilt = ElementIR.from_dict(legacy_dict)
        assert rebuilt.element_type == "hex8"
        assert rebuilt.geometry is None
