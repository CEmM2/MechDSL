"""Tests for Task P5-1: dev/algorithms/radial_return_j2.tex algpseudocode source.

Acceptance criteria covered:
1. File exists at canonical path.
2. algo2code algo_parser smoke-parses the algpseudocode block.
3. Algorithm body references power-law hardening symbols.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from algo2code.algo_parser import parse_algorithm
from algo2code.library.radial_return_j2 import (
    RADIAL_RETURN_J2_LATEX,
    get_radial_return_j2_latex,
)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "dev").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _algorithm_path() -> Path:
    return _repo_root() / "dev" / "algorithms" / "radial_return_j2.tex"


class TestTaskP5_1:
    """Tests for Task P5-1: J2 radial-return algpseudocode source."""

    @pytest.mark.unit
    def test_algorithm_file_exists(self) -> None:
        path = _algorithm_path()
        assert path.is_file(), f"P5-1 deliverable missing: {path}"
        assert path.stat().st_size > 0

    @pytest.mark.unit
    def test_algo2code_smoke_parse(self) -> None:
        algo = parse_algorithm(RADIAL_RETURN_J2_LATEX)
        assert algo.name == "radial_return_j2"
        assert algo.backend == "taichi"
        assert len(algo.args) > 0, "algorithm must declare at least one arg"
        assert len(algo.body) > 0, "algorithm body must be non-empty"

    @pytest.mark.unit
    def test_algorithm_references_power_law_hardening(self) -> None:
        text = _algorithm_path().read_text(encoding="utf-8")
        # Power-law hardening σ_y(α) = σ_y0 + K · α^n requires K, n, σ_y0
        # — we expose them as args K, n, sigy0 respectively.
        for token in ("K", "n", "sigy0"):
            assert f" {token}:scalar" in text, (
                f"algorithm must declare {token!r} as a power-law arg"
            )
        # The wrapper docstring (or the LaTeX preamble) must mention
        # power-law hardening so the contract is greppable.
        assert "power-law" in text.lower(), "algorithm header must mention power-law hardening"

    @pytest.mark.unit
    def test_library_loader_round_trips_text(self) -> None:
        """``algo2code.library.radial_return_j2`` exposes the LaTeX as
        ``RADIAL_RETURN_J2_LATEX`` and via the accessor function."""
        assert get_radial_return_j2_latex() == RADIAL_RETURN_J2_LATEX
        assert _algorithm_path().read_text(encoding="utf-8") == RADIAL_RETURN_J2_LATEX
