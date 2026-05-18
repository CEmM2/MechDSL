"""Task P9-1: spec-completeness tests for the contraction-family registry.

These tests assert that the registry in ``mechdsl.codegen.family_registry``
mirrors the authoritative spec at
``dev/design_docs/09-EINSUM-OPTIMISER.md §9`` and covers every contraction
that currently flows through the codegen pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mechdsl.codegen.family_registry import (
    ELEMENT_BACKEND_COVERAGE,
    EMISSION_SHAPES,
    FAMILIES,
    Family,
    classify_einsum_string,
)

_KNOWN_EINSUMS: tuple[tuple[str, list[tuple[int, ...]]], ...] = (
    ("qaI,ai->qiI", [(8, 8, 3), (8, 3)]),
    ("qaI,qiI->qai", [(8, 8, 3), (8, 3, 3)]),
    ("qaI,qiIjJ,qbJ->qaibj", [(8, 8, 3), (8, 3, 3, 3, 3), (8, 8, 3)]),
    ("ij,kl->ijkl", [(3, 3), (3, 3)]),
    ("ik,jl->ijkl", [(3, 3), (3, 3)]),
    ("il,jk->ijkl", [(3, 3), (3, 3)]),
    ("ijkl,kl->ij", [(3, 3, 3, 3), (3, 3)]),
    ("iI,jJ,kK,lL,IJKL->ijkl", [(3, 3), (3, 3), (3, 3), (3, 3), (3, 3, 3, 3)]),
)


class TestTaskP9_1:
    """Tests for Task P9-1: Design named contraction-family templates.

    Acceptance criteria covered:
      1. Every existing contraction in the codebase maps to a named family.
      2. Every (element x backend) combination has a defined emission shape
         per family.
      3. The spec distinguishes the scheduling decision (tier) from the
         realisation decision (family).
    """

    @pytest.mark.unit
    def test_every_plan_contraction_has_named_family(self) -> None:
        """Every known einsum classifies into a Family enum member."""
        for einsum_string, operand_shapes in _KNOWN_EINSUMS:
            family = classify_einsum_string(einsum_string, operand_shapes)
            assert isinstance(family, Family), (
                f"classify_einsum_string({einsum_string!r}) returned "
                f"{family!r}, not a Family member"
            )
            assert family in FAMILIES, f"Family {family!r} is not in FAMILIES registry tuple"

    @pytest.mark.unit
    def test_element_backend_combinations_have_emission_shapes(self) -> None:
        """Every required (family, backend) has an emission-shape entry."""
        assert ELEMENT_BACKEND_COVERAGE, "ELEMENT_BACKEND_COVERAGE is empty"
        for (element_type, backend), required_families in ELEMENT_BACKEND_COVERAGE.items():
            assert required_families, f"({element_type}, {backend}) has an empty family set"
            for family in required_families:
                key = (family, backend)
                assert key in EMISSION_SHAPES, (
                    f"Missing emission shape for {family.name} on backend "
                    f"{backend!r} (required by element {element_type!r})"
                )
                assert EMISSION_SHAPES[key], (
                    f"Empty emission-shape string for {family.name} on backend {backend!r}"
                )

    @pytest.mark.unit
    def test_tier_and_family_are_orthogonal(self) -> None:
        """The spec explicitly separates the tier and family axes."""
        spec_path = (
            Path(__file__).resolve().parents[3] / "dev" / "design_docs" / "09-EINSUM-OPTIMISER.md"
        )
        assert spec_path.is_file(), f"Spec not found at {spec_path}"
        text = spec_path.read_text(encoding="utf-8")

        markers = (
            "## 9  Contraction-family templates",
            "## 9  Evolution path: contraction-family templates",
        )
        matched = next((m for m in markers if m in text), None)
        assert matched is not None, f"No recognised Section 9 heading found; tried {markers!r}"
        section_9 = text.split(matched, maxsplit=1)[1]
        section_9 = section_9.split("\n## ", maxsplit=1)[0]

        lower = section_9.lower()
        assert "tier" in lower, "Section 9 must discuss 'tier'"
        assert "family" in lower or "families" in lower, (
            "Section 9 must discuss 'family' / 'families'"
        )
        assert "orthogonal" in lower or "orthogonality" in lower or "complementary" in lower, (
            "Section 9 must establish the tier/family axes as independent "
            "(orthogonal/complementary)"
        )
        assert "scheduling" in lower, "Section 9 must name the scheduling decision"
        assert "realisation" in lower or "realization" in lower, (
            "Section 9 must name the realisation decision"
        )
