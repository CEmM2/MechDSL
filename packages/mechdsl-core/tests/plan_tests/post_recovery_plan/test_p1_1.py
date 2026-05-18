"""Tests for Task P1-1: Extend BoundaryCondition IR slot with traction + surface tag."""

from __future__ import annotations

import pytest

from mechdsl.ir.mechanics_ir import BCType, BoundaryCondition


class TestTaskP1_1:
    """
    Tests for Task P1-1: Extend BoundaryCondition IR slot.
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.unit
    def test_construct_neumann_with_traction_and_surface_tag(self):
        """
        Verifies: BoundaryCondition with bc_type=NEUMANN, vector traction, and surface_tag constructs cleanly.
        Acceptance criterion #1: extended IR slot accepts traction + surface_tag.
        """
        bc = BoundaryCondition(
            name="load",
            bc_type=BCType.NEUMANN,
            traction=[0.0, 0.0, -1000.0],
            surface_tag="top",
        )
        assert bc.traction == (0.0, 0.0, -1000.0)
        assert bc.surface_tag == "top"
        assert bc.effective_surface_tag == "top"
        # Round-trip through to_dict / from_dict preserves all new fields.
        restored = BoundaryCondition.from_dict(bc.to_dict())
        assert restored.traction == (0.0, 0.0, -1000.0)
        assert restored.surface_tag == "top"

    @pytest.mark.unit
    def test_neumann_missing_traction_raises_validation(self):
        """
        Verifies: Neumann BC with traction=None raises ValueError citing Phase 1.
        Acceptance criterion #2: IR validation rejects malformed Neumann.
        """
        with pytest.raises(ValueError, match="post_recovery_plan Phase 1"):
            BoundaryCondition(name="bad", bc_type=BCType.NEUMANN)

    @pytest.mark.unit
    def test_dirichlet_bc_unchanged(self):
        """
        Verifies: Dirichlet BC construction is unaffected by the new fields.
        Acceptance criterion #3: backward compatibility preserved.
        """
        bc = BoundaryCondition(
            name="fix", bc_type=BCType.DIRICHLET, components=(0, 1, 2), value=0.0
        )
        assert bc.traction is None
        assert bc.surface_tag is None
        # Falls back to .name when surface_tag is unset.
        assert bc.effective_surface_tag == "fix"

    @pytest.mark.unit
    def test_legacy_string_traction_still_supported(self):
        """
        Verifies: existing callers passing traction="t_bar" continue to work.
        Back-compat with 30+ existing test fixtures across the repo.
        """
        bc = BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar")
        assert bc.traction == "t_bar"
        assert bc.surface_tag is None
        assert bc.effective_surface_tag == "load"

    @pytest.mark.unit
    def test_traction_vector_wrong_length_raises(self):
        """
        Verifies: non-length-3 traction sequence raises with Phase 1 pointer.
        """
        with pytest.raises(ValueError, match="length 3"):
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction=[1.0, 2.0])

    @pytest.mark.unit
    def test_traction_vector_non_numeric_raises(self):
        """
        Verifies: traction sequence with non-numeric entries raises.
        """
        with pytest.raises(ValueError, match="numeric components"):
            BoundaryCondition(
                name="load",
                bc_type=BCType.NEUMANN,
                traction=["a", "b", "c"],
            )
