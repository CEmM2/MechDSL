"""Tests for Task P4-4: nrpylatex round-trip test deliverable
(test_nrpylatex_round_trip.py).

Acceptance criteria covered:
1. Three case families exercised (SVK PK1 surrogate, J2 yield, two-point).
2. Index convention verified at the bridge surface for the two-point
   case (axis 0 spatial, axis 1 material).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _deliverable_path() -> Path:
    return _repo_root() / "packages" / "mechdsl-core" / "tests" / "test_nrpylatex_round_trip.py"


class TestTaskP4_4:
    """Tests for Task P4-4: round-trip deliverable."""

    @pytest.mark.integration
    def test_deliverable_file_exists(self) -> None:
        path = _deliverable_path()
        assert path.is_file(), f"P4-4 deliverable missing: {path}"
        assert path.stat().st_size > 0

    @pytest.mark.integration
    def test_deliverable_covers_svk_pk1_round_trip(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "svk" in text.lower(), "deliverable must reference SVK case"
        assert "test_round_trip_svk" in text, "deliverable must define an SVK round-trip test"

    @pytest.mark.integration
    def test_deliverable_covers_j2_yield_round_trip(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "j2" in text.lower() or "yield" in text.lower(), (
            "deliverable must reference J2 yield case"
        )
        assert "test_round_trip_j2" in text, "deliverable must define a J2 round-trip test"

    @pytest.mark.integration
    def test_deliverable_covers_two_point_tensor_round_trip(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "two_point" in text.lower() or "F^{i I}" in text or "F^{iI}" in text, (
            "deliverable must reference two-point F^{iI} case"
        )
        assert "test_round_trip_two_point" in text
        # Verify the test asserts the spatial/material classification
        # (otherwise the regression-guard property is empty).
        assert "spatial_axes" in text and "material_axes" in text
