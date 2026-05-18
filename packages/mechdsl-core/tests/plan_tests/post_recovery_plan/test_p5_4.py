"""Tests for Task P5-4: imported vs algo2code parity test deliverable.

P5-4's deliverable IS a new test file
``packages/mechdsl-core/tests/test_j2_radial_return_parity.py``. This
stub set is the meta-spec asserting the deliverable exists and pins
the three required parity cases plus the baseline-derived tolerance
contract.

Acceptance criteria covered:
1. Parity test passes for elastic, elastoplastic, unloading load steps.
2. Tolerance derived from imported-path baseline, not absolute zero.
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
    return _repo_root() / "packages" / "mechdsl-core" / "tests" / "test_j2_radial_return_parity.py"


class TestTaskP5_4:
    """Tests for Task P5-4: parity-test deliverable."""

    @pytest.mark.integration
    def test_deliverable_file_exists(self) -> None:
        path = _deliverable_path()
        assert path.is_file(), f"P5-4 deliverable missing: {path}"
        assert path.stat().st_size > 0

    @pytest.mark.integration
    def test_deliverable_covers_elastic_step(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "test_parity_elastic_load_step" in text, (
            "deliverable must define an elastic-step parity test"
        )

    @pytest.mark.integration
    def test_deliverable_covers_elastoplastic_step(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "test_parity_elastoplastic_load_step" in text, (
            "deliverable must define an elastoplastic-step parity test"
        )

    @pytest.mark.integration
    def test_deliverable_covers_unloading_step(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "test_parity_unloading_load_step" in text, (
            "deliverable must define an unloading-step parity test"
        )

    @pytest.mark.integration
    def test_deliverable_uses_baseline_derived_tolerance(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        # Tolerance contract: the deliverable must define and document a
        # baseline-derived tolerance constant rather than asserting
        # exact equality.
        assert "BASELINE_TOL" in text, "deliverable must declare a BASELINE_TOL constant"
        assert "imported-path baseline" in text or "Newton tolerance" in text, (
            "deliverable must reference the imported-path baseline as the "
            "tolerance source (per plan line 267-268)"
        )
