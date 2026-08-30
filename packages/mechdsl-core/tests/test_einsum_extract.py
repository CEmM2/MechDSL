"""Tests for Phase 2: einsum string extraction from ElementIR.

Covers tasks P2-T1 (extract_einsum_specs implementation) and
P2-T3 (regression guards for correctness and determinism).
"""

from __future__ import annotations

import pytest

from mechdsl.ir.element_ir import ElementIR, create_hex8_element_ir
from mechdsl.lowering.einsum_extract import extract_einsum_specs
from mechdsl.lowering.fe_localise import EinsumSpec


@pytest.fixture()
def hex8_ir() -> ElementIR:
    """Standard Hex8 TL ElementIR."""
    return create_hex8_element_ir()


# ============================================================================
# extract_einsum_specs implementation
# ============================================================================


class TestExtractEinsumSpecs:
    """Tests for Task P2-T1: Implement extract_einsum_specs().

    Acceptance criteria: returns 3 keys, correct einsum strings,
    correct shapes, rejects non-hex8.
    """

    def test_returns_three_specs(self, hex8_ir: ElementIR):
        """Returns dict with exactly 3 keys for Hex8 TL."""
        result = extract_einsum_specs(hex8_ir)
        assert len(result) == 3
        assert set(result.keys()) == {
            "strain_displacement",
            "internal_force",
            "tangent_matvec",
        }

    def test_strain_displacement_einsum_string(self, hex8_ir: ElementIR):
        """strain_displacement einsum matches expected value."""
        result = extract_einsum_specs(hex8_ir)
        assert result["strain_displacement"].einsum_string == "qaI,ai->qiI"

    def test_internal_force_einsum_string(self, hex8_ir: ElementIR):
        """internal_force einsum matches expected value."""
        result = extract_einsum_specs(hex8_ir)
        assert result["internal_force"].einsum_string == "qaI,qiI->qai"

    def test_tangent_matvec_einsum_string(self, hex8_ir: ElementIR):
        """tangent_matvec einsum matches expected value."""
        result = extract_einsum_specs(hex8_ir)
        assert result["tangent_matvec"].einsum_string == "qaI,qiIjJ,qbJ->qaibj"

    def test_operand_shapes_hex8(self, hex8_ir: ElementIR):
        """Operand shapes consistent with Hex8 geometry (n_qp=8, n_nodes=8, dim=3)."""
        result = extract_einsum_specs(hex8_ir)
        sd = result["strain_displacement"]
        # dN shape: (8, 8, 3), u shape: (8, 3)
        assert sd.operand_shapes == ((8, 8, 3), (8, 3))
        assert sd.result_shape == (8, 3, 3)

    def test_rejects_non_hex8_element(self):
        """Non-hex8 element type raises ValueError.

        ElementIR.__post_init__ also rejects non-hex8, so we bypass it
        using object.__setattr__ on a real Hex8 IR to test the extraction
        function's own validation.
        """
        hex8 = create_hex8_element_ir()
        # Bypass frozen dataclass to inject non-hex8 element type
        object.__setattr__(hex8, "element_type", "tet4")
        with pytest.raises(ValueError, match="Unsupported element type"):
            extract_einsum_specs(hex8)


# ============================================================================
# Regression guards
# ============================================================================


class TestEinsumExtractionRegression:
    """Tests for Task P2-T3: Regression guards for einsum extraction."""

    def test_deterministic_output(self, hex8_ir: ElementIR):
        """Calling extract_einsum_specs twice returns identical results."""
        r1 = extract_einsum_specs(hex8_ir)
        r2 = extract_einsum_specs(hex8_ir)
        for key in r1:
            assert r1[key].einsum_string == r2[key].einsum_string
            assert r1[key].operand_shapes == r2[key].operand_shapes
            assert r1[key].result_shape == r2[key].result_shape

    def test_all_specs_are_einsum_spec_instances(self, hex8_ir: ElementIR):
        """All returned values are EinsumSpec instances."""
        result = extract_einsum_specs(hex8_ir)
        for val in result.values():
            assert isinstance(val, EinsumSpec)

    def test_spec_names_match_dict_keys(self, hex8_ir: ElementIR):
        """Each EinsumSpec.name matches its dict key."""
        result = extract_einsum_specs(hex8_ir)
        for key, spec in result.items():
            assert key == spec.name
