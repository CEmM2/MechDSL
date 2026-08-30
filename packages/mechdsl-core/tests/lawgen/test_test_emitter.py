"""Unit tests for the generated-tests emitter (Task P3-2).

Covers four emitter cases:

1. ``emit_tests`` on a simple spec → the generated source defines a reference-eval
   test function AND an FD-derivative test function.
2. ``emit_tests`` with ``monotone_check=True`` → the generated source has the
   monotonicity assertion/block.
3. ``emit_tests`` with ``monotone_check=False`` → the generated source has NO
   monotonicity block.
4. the generated file is valid Python (``ast.parse`` succeeds).

Plus the strong bonus: the emitted file for a monotone Voce law is executed
in-process with ``pytest`` and asserted to PASS — proving the reference/FD/
monotonicity tests are correct, not merely parseable. The fail-loud (R2) route
(unsupported node → ``LawgenError``) is also covered.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
import sympy as sp

from mechdsl.lawgen.contracts import PlasticityCarrierSpec
from mechdsl.lawgen.diagnostics import LawgenError
from mechdsl.lawgen.test_emitter import (
    FACTOR_PRIMARY_VARIABLE,
    FD_RTOL,
    N_SAMPLE_POINTS,
    emit_tests,
)

if TYPE_CHECKING:
    from pathlib import Path


def _voce_spec(*, monotone_check: bool = False) -> PlasticityCarrierSpec:
    """A Voce + power-law isotropic-hardening carrier, monotone in ``p``.

    ``R = sigma_y0 + Q*(1 - exp(-b*p)) + K*p**n`` — every term is non-decreasing
    in ``p >= 0`` for positive parameters, so a real run of the generated
    monotonicity test passes. H/Q here are rate-/temperature-independent, so their
    FD derivative w.r.t. edot/T is 0 (FD ~ 0) — the general per-factor check still
    passes without special-casing.
    """
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


def _rate_thermal_spec() -> PlasticityCarrierSpec:
    """A carrier with genuinely non-constant rate (H) and thermal (Q) factors.

    ``H = 1 + C*log(edot)`` (dH/dedot = C/edot != 0) and ``Q = 1 - A*(T - T0)``
    (dQ/dT = -A != 0), so the H->edot and Q->T FD checks exercise a *real*
    non-zero derivative — not just the constant-factor (derivative 0) path.
    """
    p, edot, T = sp.symbols("p edot T")
    sigma_y0, K, C, T0, A = sp.symbols("sigma_y0 K C T0 A")
    R = sigma_y0 + K * p
    H = 1 + C * sp.log(edot)
    Q = 1 - A * (T - T0)
    return PlasticityCarrierSpec(
        name="rate_thermal",
        parameters=("sigma_y0", "K", "C", "T0", "A"),
        expressions={"R": R, "H": H, "Q": Q},
        variable_bindings={"p": p, "edot": edot, "T": T},
    )


# ---------------------------------------------------------------------------
# Case 1 — reference-eval + FD-derivative test functions are present.
# ---------------------------------------------------------------------------


class TestEmittedTestFunctions:
    def test_has_reference_and_fd_tests(self, tmp_path: Path) -> None:
        out = emit_tests(_voce_spec(), target_test_path=tmp_path / "test_gen_voce.py")
        source = out.read_text(encoding="utf-8")
        assert "def test_reference_eval(" in source
        assert "def test_fd_derivative(" in source

    def test_fd_derivative_covers_all_three_factors(self, tmp_path: Path) -> None:
        """The FD test is parametrized over R/H/Q, each vs its own primary axis.

        R/H/Q are three independent factors (hardening/rate/thermal); the emitter
        must FD-check each factor's derivative w.r.t. its own primary variable
        (R->p, H->edot, Q->T), not conflate H with d(R)/dp.
        """
        out = emit_tests(_voce_spec(), target_test_path=tmp_path / "test_gen_voce.py")
        source = out.read_text(encoding="utf-8")
        # One parametrized FD test carrying all three (role, srepr, primary) rows.
        assert "@pytest.mark.parametrize" in source
        assert "FD_CASES" in source
        for role, srepr_const in (("R", "R_SREPR"), ("H", "H_SREPR"), ("Q", "Q_SREPR")):
            primary = FACTOR_PRIMARY_VARIABLE[role]
            assert f"({role!r}, {srepr_const!r}, {primary!r})" in source
        # H must NOT be asserted equal to d(R)/dp anywhere (the misread to avoid).
        assert "sp.diff(R" not in source
        assert "sp.diff(_rebuild(R_SREPR)" not in source

    def test_emit_tests_returns_written_path(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "test_gen_voce.py"
        out = emit_tests(_voce_spec(), target_test_path=target)
        assert out == target
        assert out.exists()

    def test_fd_test_uses_rtol_at_or_below_1e_5(self, tmp_path: Path) -> None:
        out = emit_tests(_voce_spec(), target_test_path=tmp_path / "test_gen_voce.py")
        source = out.read_text(encoding="utf-8")
        # The FD tolerance must be the standard-FD 1e-5, not the stricter 1e-10 reconciliation gate.
        assert FD_RTOL <= 1e-5
        assert f"FD_RTOL = {FD_RTOL!r}" in source
        assert "1e-10" not in source

    def test_reference_test_uses_ten_sample_points(self, tmp_path: Path) -> None:
        out = emit_tests(_voce_spec(), target_test_path=tmp_path / "test_gen_voce.py")
        source = out.read_text(encoding="utf-8")
        assert N_SAMPLE_POINTS == 10
        assert f"N_SAMPLE_POINTS = {N_SAMPLE_POINTS!r}" in source

    def test_taichi_smoke_block_is_guarded(self, tmp_path: Path) -> None:
        out = emit_tests(_voce_spec(), target_test_path=tmp_path / "test_gen_voce.py")
        source = out.read_text(encoding="utf-8")
        assert "def test_taichi_smoke(" in source
        assert 'pytest.importorskip("taichi")' in source


# ---------------------------------------------------------------------------
# Case 2 / Case 3 — monotonicity block presence is gated by monotone_check.
# ---------------------------------------------------------------------------


class TestMonotonicityGate:
    def test_monotone_check_true_emits_block(self, tmp_path: Path) -> None:
        out = emit_tests(
            _voce_spec(monotone_check=True), target_test_path=tmp_path / "test_gen_voce.py"
        )
        source = out.read_text(encoding="utf-8")
        assert "def test_monotonicity(" in source
        assert "not monotone" in source

    def test_monotone_check_false_omits_block(self, tmp_path: Path) -> None:
        out = emit_tests(
            _voce_spec(monotone_check=False), target_test_path=tmp_path / "test_gen_voce.py"
        )
        source = out.read_text(encoding="utf-8")
        assert "def test_monotonicity(" not in source
        assert "not monotone" not in source


# ---------------------------------------------------------------------------
# Case 4 — the generated file is valid Python.
# ---------------------------------------------------------------------------


class TestGeneratedFileIsValidPython:
    @pytest.mark.parametrize("monotone_check", [True, False])
    def test_ast_parse_succeeds(self, tmp_path: Path, monotone_check: bool) -> None:
        out = emit_tests(
            _voce_spec(monotone_check=monotone_check),
            target_test_path=tmp_path / "test_gen_voce.py",
        )
        source = out.read_text(encoding="utf-8")
        # Must not raise SyntaxError.
        tree = ast.parse(source)
        # Sanity: it really is a module with the expected top-level test defs.
        func_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        assert {"test_reference_eval", "test_fd_derivative", "test_taichi_smoke"} <= func_names

    def test_generated_file_does_not_use_future_annotations(self, tmp_path: Path) -> None:
        # PEP 563 stringizes annotations, which breaks Taichi kernel arg types —
        # the generated file must NOT carry ``from __future__ import annotations``.
        out = emit_tests(_voce_spec(), target_test_path=tmp_path / "test_gen_voce.py")
        source = out.read_text(encoding="utf-8")
        assert "from __future__ import annotations" not in source


# ---------------------------------------------------------------------------
# Strong bonus — actually RUN the generated file and assert it PASSES.
# ---------------------------------------------------------------------------


class TestGeneratedFileRuns:
    @pytest.mark.parametrize(
        ("spec_factory", "filename"),
        [
            (lambda: _voce_spec(monotone_check=True), "test_gen_voce.py"),
            (_rate_thermal_spec, "test_gen_rate_thermal.py"),
        ],
        ids=["voce_monotone", "rate_thermal"],
    )
    def test_generated_tests_pass_under_pytest(
        self, tmp_path: Path, spec_factory: object, filename: str
    ) -> None:
        """Run an emitted test file in a subprocess; expect all cases pass.

        Proves the emitted reference/FD/monotonicity tests are numerically correct,
        not merely valid Python. The ``rate_thermal`` case exercises the H->edot and
        Q->T FD checks with *non-zero* analytic derivatives (Voce's H/Q are
        constant, i.e. derivative 0), so between them both FD regimes are covered.
        The Taichi smoke test passes (Taichi installed) or skips (importorskip) —
        both are non-failing, so the run returns exit code 0.
        """
        out = emit_tests(spec_factory(), target_test_path=tmp_path / filename)  # type: ignore[operator]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(out),
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",  # ignore repo addopts (markers/coverage) for the isolated run
                "-q",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"generated test file failed under pytest:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Fail-loud — an unsupported node raises LawgenError, no file is written.
# ---------------------------------------------------------------------------


class TestFailLoud:
    def test_unsupported_node_raises_lawgen_error(self, tmp_path: Path) -> None:
        p, edot, T = sp.symbols("p edot T")
        # ``erf`` is a defined SymPy function that is NOT in the Taichi allow-list.
        bad = PlasticityCarrierSpec(
            name="bad",
            parameters=("a",),
            expressions={"R": sp.erf(p), "H": sp.Integer(0), "Q": sp.Integer(1)},
            variable_bindings={"p": p, "edot": edot, "T": T},
        )
        target = tmp_path / "test_gen_bad.py"
        with pytest.raises(LawgenError):
            emit_tests(bad, target_test_path=target)
        # No partial file was written (fail-loud before write).
        assert not target.exists()
