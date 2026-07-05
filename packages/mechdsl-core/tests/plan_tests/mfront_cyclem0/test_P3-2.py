"""Plan tests for Task P3-2: generated-tests emitter per scalar law.

Plan: dev/plans/mfront_cycleM0.md (lines 101-103) — MFront-mimic Cycle M0, Phase 3.
Deliverable under test:
  packages/mechdsl-core/src/mechdsl/lawgen/test_emitter.py

emit_tests(spec, ..., target_test_path) writes a VALID-Python pytest file (must pass
ast.parse) with: a Python reference eval (lambdify over the spec's symbol map), an
FD-derivative comparison (rtol <= 1e-5 — NOT the 1e-10 P4-2 gate), an optional
monotonicity assertion (iff spec.monotone_check), and an optional guarded Taichi JIT
smoke test. De-stubbed for the P3-2 exec.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
import sympy as sp

from mechdsl.lawgen.contracts import PlasticityCarrierSpec
from mechdsl.lawgen.test_emitter import emit_tests

if TYPE_CHECKING:
    from pathlib import Path


def _voce_spec(*, monotone_check: bool = False) -> PlasticityCarrierSpec:
    """A Voce + power-law hardening carrier (monotone in ``p``)."""
    p, edot, T = sp.symbols("p edot T")
    sigma_y0, Q, b, K, n = sp.symbols("sigma_y0 Q b K n")
    R = sigma_y0 + Q * (1 - sp.exp(-b * p)) + K * p**n
    return PlasticityCarrierSpec(
        name="voce",
        parameters=("sigma_y0", "Q", "b", "K", "n"),
        expressions={"R": R, "H": sp.diff(R, p), "Q": sp.Integer(1)},
        variable_bindings={"p": p, "edot": edot, "T": T},
        monotone_check=monotone_check,
    )


class TestTaskP3_2:
    """Tests for Task P3-2: generated-tests emitter. AC covered: 1-5."""

    @pytest.mark.integration
    def test_emitted_file_has_reference_and_fd_tests(self, tmp_path: Path) -> None:
        """AC2/AC5: reference eval + FD derivative (rtol <= 1e-5) test functions present.

        The FD test covers all three factors R/H/Q (hardening/rate/thermal), each
        vs its own analytic derivative — not H conflated with d(R)/dp.
        """
        out = emit_tests(_voce_spec(), target_test_path=tmp_path / "test_gen.py")
        source = out.read_text(encoding="utf-8")
        assert "def test_reference_eval(" in source
        assert "def test_fd_derivative(" in source
        # All three per-factor FD cases (role, srepr, own-primary) must be emitted.
        assert "('R', 'R_SREPR', 'p')" in source
        assert "('H', 'H_SREPR', 'edot')" in source
        assert "('Q', 'Q_SREPR', 'T')" in source
        # FD tolerance is the standard-FD 1e-5, never the 1e-10 P4-2 equivalence gate.
        assert "FD_RTOL = 1e-05" in source
        assert "1e-10" not in source

    @pytest.mark.integration
    def test_monotone_check_true_emits_monotonicity_assertion(self, tmp_path: Path) -> None:
        """AC3: monotonicity test present iff monotone_check is True."""
        out = emit_tests(_voce_spec(monotone_check=True), target_test_path=tmp_path / "test_gen.py")
        source = out.read_text(encoding="utf-8")
        assert "def test_monotonicity(" in source
        assert "not monotone" in source

    @pytest.mark.integration
    def test_monotone_check_false_omits_monotonicity(self, tmp_path: Path) -> None:
        """AC3: no monotonicity block when the flag is off."""
        out = emit_tests(
            _voce_spec(monotone_check=False), target_test_path=tmp_path / "test_gen.py"
        )
        source = out.read_text(encoding="utf-8")
        assert "def test_monotonicity(" not in source

    @pytest.mark.integration
    def test_generated_file_is_valid_python(self, tmp_path: Path) -> None:
        """AC1: generated file is valid Python; the Taichi block is guarded."""
        out = emit_tests(_voce_spec(monotone_check=True), target_test_path=tmp_path / "test_gen.py")
        source = out.read_text(encoding="utf-8")
        # Must not raise SyntaxError.
        ast.parse(source)
        # AC4: the Taichi JIT smoke test is guarded (skips without Taichi).
        assert 'pytest.importorskip("taichi")' in source
