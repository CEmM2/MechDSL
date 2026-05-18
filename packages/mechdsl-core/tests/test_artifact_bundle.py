"""Tests for artifact bundle model (ContractionPlan + ArtifactBundle).

Covers round-trip serialisation, content hashing semantics, error handling,
and file I/O.  Separate from test_artifacts.py which tests golden-file
regression.
"""

from __future__ import annotations

import json

import pytest

from mechdsl.codegen.artifact import ArtifactBundle, ContractionPlan

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_PROBLEM_IR: dict = {
    "formulation": "total_lagrangian",
    "element": "hex8",
    "material": {"type": "svk", "E": 200e3, "nu": 0.3},
}

SAMPLE_ELEMENT_IR: dict = {
    "element_type": "hex8",
    "n_nodes": 8,
    "n_quad": 8,
    "dim": 3,
}

SAMPLE_PLAN = ContractionPlan(
    einsum_string="ij,jk->ik",
    contraction_path=[(0, 1)],
    estimated_flops=54,
    tier=1,
)


def _make_bundle(**overrides: object) -> ArtifactBundle:
    defaults: dict = dict(
        problem_ir_dict=SAMPLE_PROBLEM_IR,
        element_ir_summary=SAMPLE_ELEMENT_IR,
        contraction_plans=(SAMPLE_PLAN,),
        emitted_source="# generated\nimport taichi as ti\n",
        metadata={"compiler_version": "0.1.0"},
    )
    defaults.update(overrides)
    return ArtifactBundle(**defaults)


# ---------------------------------------------------------------------------
# 1. dict round-trip
# ---------------------------------------------------------------------------


class TestDictRoundTrip:
    def test_to_dict_from_dict_preserves_all_fields(self) -> None:
        bundle = _make_bundle()
        d = bundle.to_dict()
        restored = ArtifactBundle.from_dict(d)

        assert restored.problem_ir_dict == bundle.problem_ir_dict
        assert restored.element_ir_summary == bundle.element_ir_summary
        assert len(restored.contraction_plans) == len(bundle.contraction_plans)
        cp_orig = bundle.contraction_plans[0]
        cp_rest = restored.contraction_plans[0]
        assert cp_rest.einsum_string == cp_orig.einsum_string
        assert cp_rest.contraction_path == cp_orig.contraction_path
        assert cp_rest.estimated_flops == cp_orig.estimated_flops
        assert cp_rest.tier == cp_orig.tier
        assert restored.emitted_source == bundle.emitted_source
        assert restored.metadata == bundle.metadata


# ---------------------------------------------------------------------------
# 2. JSON round-trip
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    def test_to_json_from_json_preserves_all_fields(self) -> None:
        bundle = _make_bundle()
        json_str = bundle.to_json()
        restored = ArtifactBundle.from_json(json_str=json_str)

        assert restored.problem_ir_dict == bundle.problem_ir_dict
        assert restored.element_ir_summary == bundle.element_ir_summary
        assert len(restored.contraction_plans) == len(bundle.contraction_plans)
        assert restored.emitted_source == bundle.emitted_source
        assert restored.metadata == bundle.metadata


# ---------------------------------------------------------------------------
# 3. Content hash matches after round-trip
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_hash_stable_after_round_trip(self) -> None:
        bundle = _make_bundle()
        json_str = bundle.to_json()
        restored = ArtifactBundle.from_json(json_str=json_str)
        assert restored.content_hash() == bundle.content_hash()

    # -----------------------------------------------------------------------
    # 4. Content hash changes when IR changes
    # -----------------------------------------------------------------------

    def test_hash_changes_when_ir_changes(self) -> None:
        bundle_a = _make_bundle()
        modified_ir = {**SAMPLE_PROBLEM_IR, "element": "tet4"}
        bundle_b = _make_bundle(problem_ir_dict=modified_ir)
        assert bundle_a.content_hash() != bundle_b.content_hash()

    # -----------------------------------------------------------------------
    # 5. Content hash NOT affected by emitted_source changes
    # -----------------------------------------------------------------------

    def test_hash_unaffected_by_source_change(self) -> None:
        bundle_a = _make_bundle(emitted_source="# v1")
        bundle_b = _make_bundle(emitted_source="# v2 with extra whitespace")
        assert bundle_a.content_hash() == bundle_b.content_hash()

    def test_hash_unaffected_by_metadata_change(self) -> None:
        bundle_a = _make_bundle(metadata={"v": 1})
        bundle_b = _make_bundle(metadata={"v": 2})
        assert bundle_a.content_hash() == bundle_b.content_hash()


# ---------------------------------------------------------------------------
# 6. Empty contraction_plans is valid
# ---------------------------------------------------------------------------


class TestEmptyPlans:
    def test_empty_contraction_plans(self) -> None:
        bundle = _make_bundle(contraction_plans=())
        assert bundle.contraction_plans == ()
        d = bundle.to_dict()
        assert d["contraction_plans"] == []
        restored = ArtifactBundle.from_dict(d)
        assert restored.contraction_plans == ()

    def test_hash_with_empty_plans(self) -> None:
        bundle = _make_bundle(contraction_plans=())
        h = bundle.content_hash()
        assert isinstance(h, str) and len(h) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# 7. ContractionPlan round-trip
# ---------------------------------------------------------------------------


class TestContractionPlanRoundTrip:
    def test_to_dict_from_dict(self) -> None:
        plan = ContractionPlan(
            einsum_string="ij,jk,kl->il",
            contraction_path=[(0, 1), (0, 1)],
            estimated_flops=162,
            tier=2,
        )
        d = plan.to_dict()
        restored = ContractionPlan.from_dict(d)
        assert restored.einsum_string == plan.einsum_string
        assert restored.contraction_path == plan.contraction_path
        assert restored.estimated_flops == plan.estimated_flops
        assert restored.tier == plan.tier

    def test_defaults(self) -> None:
        plan = ContractionPlan(einsum_string="ij->ji")
        assert plan.contraction_path == []
        assert plan.estimated_flops == 0
        assert plan.tier == 0


# ---------------------------------------------------------------------------
# 8. Missing required fields in from_dict raises error
# ---------------------------------------------------------------------------


class TestFromDictErrors:
    def test_missing_problem_ir_dict(self) -> None:
        d = {"element_ir_summary": SAMPLE_ELEMENT_IR}
        with pytest.raises(KeyError, match="problem_ir_dict"):
            ArtifactBundle.from_dict(d)

    def test_missing_element_ir_summary(self) -> None:
        d = {"problem_ir_dict": SAMPLE_PROBLEM_IR}
        with pytest.raises(KeyError, match="element_ir_summary"):
            ArtifactBundle.from_dict(d)

    def test_missing_both_required(self) -> None:
        with pytest.raises(KeyError, match=r"problem_ir_dict.*element_ir_summary"):
            ArtifactBundle.from_dict({})

    def test_contraction_plan_missing_einsum_string(self) -> None:
        with pytest.raises(KeyError, match="einsum_string"):
            ContractionPlan.from_dict({"tier": 1})


# ---------------------------------------------------------------------------
# 9. Corrupt JSON in from_json raises error
# ---------------------------------------------------------------------------


class TestFromJsonErrors:
    def test_corrupt_json(self) -> None:
        with pytest.raises(ValueError, match="invalid JSON"):
            ArtifactBundle.from_json(json_str="{not valid json!!!")

    def test_valid_json_but_missing_fields(self) -> None:
        with pytest.raises(KeyError, match="problem_ir_dict"):
            ArtifactBundle.from_json(json_str=json.dumps({"foo": "bar"}))

    def test_no_arguments(self) -> None:
        with pytest.raises(ValueError, match="provide either"):
            ArtifactBundle.from_json()

    def test_both_arguments(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            ArtifactBundle.from_json(json_str="{}", path="/tmp/x.json")


# ---------------------------------------------------------------------------
# 10. File write/read round-trip
# ---------------------------------------------------------------------------


class TestFileRoundTrip:
    def test_write_read(self, tmp_path: object) -> None:
        from pathlib import Path

        tmp = Path(str(tmp_path))
        bundle = _make_bundle()
        filepath = tmp / "artifact.json"
        bundle.to_json(path=str(filepath))

        assert filepath.exists()

        restored = ArtifactBundle.from_json(path=str(filepath))
        assert restored.problem_ir_dict == bundle.problem_ir_dict
        assert restored.element_ir_summary == bundle.element_ir_summary
        assert restored.emitted_source == bundle.emitted_source
        assert restored.content_hash() == bundle.content_hash()

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            ArtifactBundle.from_json(path="/nonexistent/path/artifact.json")
