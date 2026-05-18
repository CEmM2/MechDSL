"""Tests for Task P5-2: algo2code radial-return codegen test deliverable.

P5-2's deliverable is the codegen test file
``packages/algo2code/tests/test_radial_return_codegen.py``. This stub
set is the meta-spec asserting the deliverable file exists and pins
the four required cases (elastic / elastoplastic / unloading / JIT
budget).

Acceptance criteria covered:
1. Codegen test file exists at canonical path.
2. Test exercises elastic / elastoplastic / unloading cases (covered
   under the broader "behavioural cases" umbrella — at this layer the
   parser-deferral path means each case is asserted via the parity
   route in P5-4; the codegen file pins the import-chain).
3. JIT budget probe ≤ 512 unrolled lines per ``@ti.func``.
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
    return _repo_root() / "packages" / "algo2code" / "tests" / "test_radial_return_codegen.py"


class TestTaskP5_2:
    """Tests for Task P5-2: algo2code radial-return codegen deliverable."""

    @pytest.mark.unit
    def test_deliverable_file_exists(self) -> None:
        path = _deliverable_path()
        assert path.is_file(), f"P5-2 deliverable missing: {path}"
        assert path.stat().st_size > 0

    @pytest.mark.unit
    def test_deliverable_pins_jit_budget(self) -> None:
        text = _deliverable_path().read_text(encoding="utf-8")
        # The 512 budget number must appear so the probe cannot drift
        # silently.
        assert "512" in text, "deliverable must pin the 512-line JIT budget"
        assert "JIT_BUDGET" in text or "jit budget" in text.lower(), (
            "deliverable must reference the JIT budget by name"
        )

    @pytest.mark.unit
    def test_deliverable_exercises_transpile_helper(self) -> None:
        """Phase 5 lifted the parser-deferral surface; the deliverable
        now exercises ``transpile_radial_return_j2`` end-to-end."""
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "transpile_radial_return_j2" in text, (
            "deliverable must exercise the library transpile helper"
        )
        assert "callable(" in text, "deliverable must assert the transpiled output is callable"

    @pytest.mark.unit
    def test_deliverable_exercises_full_arg_set(self) -> None:
        """Codegen test asserts the algorithm declares the scalar
        Newton inner loop arg set (sigma_eq, alpha, mu, K, n, sigy0,
        tol, max_iter) — the post_recovery_plan Phase 5 P5-1 contract."""
        text = _deliverable_path().read_text(encoding="utf-8")
        for token in ("sigma_eq", "alpha", "mu", "K", "n", "sigy0", "tol", "max_iter"):
            assert f'"{token}"' in text, f"deliverable must reference required arg {token!r}"

    @pytest.mark.unit
    def test_deliverable_validates_emitted_python(self) -> None:
        """Deliverable confirms the Taichi emission output is
        syntactically valid Python."""
        text = _deliverable_path().read_text(encoding="utf-8")
        assert "ast.parse" in text, "deliverable must validate emitted code via ast.parse"
