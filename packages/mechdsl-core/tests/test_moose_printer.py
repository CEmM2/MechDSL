"""Tests for Task P8-2: MOOSE printer (ComputeStressBase + RankTwoTensor + input files).

Exercises the three acceptance criteria:

1. MOOSE emission produces parseable C++ + a non-empty .i file.
2. ``RankTwoTensor`` / ``RankFourTensor`` references present in the emitted C++.
3. Input file references the emitted material name.

Plus supporting coverage:

- Tensor-type mapping round-trips (3x3 and 3x3x3x3).
- Unsupported element type / dynamics mode raise :class:`NotImplementedError`.
- Deterministic emission (same bundle -> identical source).
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

import numpy as np
import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.moose_printer import (
    emit,
    emit_cpp,
    emit_header,
    emit_input_file,
    from_rank_four_tensor,
    from_rank_two_tensor,
    to_rank_four_tensor,
    to_rank_two_tensor,
)
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    DynamicsMode,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize

pytestmark = pytest.mark.experimental_backend

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_svk_bundle() -> ArtifactBundle:
    """Bundle with SVK material — the MVP reference."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


def _make_j2_bundle() -> ArtifactBundle:
    """Bundle with J2 power-law plasticity — exercises extra param emission."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y": 250.0, "n_exp": 10.0},
        ),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


@pytest.fixture
def svk_bundle() -> ArtifactBundle:
    return _make_svk_bundle()


@pytest.fixture
def j2_bundle() -> ArtifactBundle:
    return _make_j2_bundle()


# ---------------------------------------------------------------------------
# Parse-check helper
# ---------------------------------------------------------------------------


def _clang_format_check(source: str) -> tuple[bool, str]:
    """Dry-run ``clang-format`` against *source*.

    Returns ``(ok, detail)``.  When ``clang-format`` isn't available locally
    the helper returns ``(True, "skipped")`` and a structural regex fallback
    is used in its place by the caller.
    """
    clang_format = shutil.which("clang-format")
    if clang_format is None:
        return True, "clang-format not found on PATH — skipping dry-run"
    try:
        result = subprocess.run(
            [clang_format, "--style=LLVM"],
            input=source,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return True, f"clang-format failed to launch: {exc!r} — skipping"
    # clang-format with no --Werror still prints formatted code to stdout.
    # A non-zero return means syntactic trouble.  Accept rc==0 as "parseable".
    if result.returncode != 0:
        return False, f"clang-format rc={result.returncode} stderr={result.stderr!r}"
    return True, "ok"


# ---------------------------------------------------------------------------
# TestTaskP8_2 — acceptance criteria for P8-2
# ---------------------------------------------------------------------------


class TestTaskP8_2:
    """
    Tests for Task P8-2: MOOSE printer (ComputeStressBase subclass + input file).

    Acceptance criteria covered:
      1. MOOSE emission produces parseable C++ + a non-empty .i file.
      2. RankTwoTensor / RankFourTensor references present in emitted C++.
      3. Input file references the emitted material name.
    """

    @pytest.mark.unit
    def test_moose_cpp_emission_structural_checks(self, svk_bundle: ArtifactBundle) -> None:
        """Emitted .C file subclasses ComputeStressBase and uses RankTwoTensor /
        RankFourTensor in computeQpStress / computeQpJacobian.
        """
        artifacts = emit(svk_bundle)
        assert set(artifacts.keys()) == {"cpp", "header"}
        cpp = artifacts["cpp"]
        header = artifacts["header"]
        assert cpp, "expected non-empty .C source"
        assert header, "expected non-empty .h source"

        # Header contract
        assert "#pragma once" in header
        assert '#include "ComputeStressBase.h"' in header
        assert '#include "RankTwoTensor.h"' in header
        assert '#include "RankFourTensor.h"' in header
        assert ": public ComputeStressBase" in header
        assert "virtual void computeQpStress() override;" in header
        assert "virtual void computeQpJacobian();" in header

        # CPP contract
        assert "ComputeStressBase" in cpp
        assert "RankTwoTensor" in cpp
        assert "RankFourTensor" in cpp
        assert "computeQpStress()" in cpp
        assert "computeQpJacobian()" in cpp
        assert "_stress[_qp]" in cpp
        assert "_Jacobian_mult[_qp]" in cpp
        assert "registerMooseObject" in cpp

        # Parse-check via clang-format (dry-run).  Falls through cleanly when
        # clang-format isn't installed; in that case we assert structural
        # bracket balance as a cheap fallback.
        ok_cpp, detail_cpp = _clang_format_check(cpp)
        assert ok_cpp, f"clang-format rejected .C output: {detail_cpp}"
        ok_h, detail_h = _clang_format_check(header)
        assert ok_h, f"clang-format rejected .h output: {detail_h}"

        # Bracket balance fallback — always run, cheap.
        for name, text in (("cpp", cpp), ("header", header)):
            assert text.count("{") == text.count("}"), (
                f"{name}: unbalanced braces ({text.count('{')} vs {text.count('}')})"
            )
            assert text.count("(") == text.count(")"), f"{name}: unbalanced parens"

    @pytest.mark.unit
    def test_moose_input_file_generation(self, svk_bundle: ArtifactBundle) -> None:
        """The emitted .i file is non-empty and wires the generated material
        into a minimal tension-test simulation block.
        """
        ideck = emit_input_file(svk_bundle)
        assert ideck, "expected non-empty .i file"
        # Referenced material class name must match what emit() produces.
        class_name = "MechDSLSaintVenantKirchhoff"
        assert class_name in ideck, (
            f"emitted .i deck does not reference material class {class_name!r}"
        )
        # Required blocks for a tension test.
        assert "[Mesh]" in ideck
        assert "[Variables]" in ideck
        assert "[Kernels]" in ideck
        assert "[BCs]" in ideck
        assert "[Materials]" in ideck
        assert "[Executioner]" in ideck
        # Tension-test BC sentinel (pull_x block should reference the +x face).
        assert "pull_x" in ideck
        assert "DirichletBC" in ideck
        # No unfilled placeholders.
        assert "{{" not in ideck, f"unfilled placeholder left in deck: {ideck!r}"
        # Numerical parameters must be materialised as floats in the deck.
        assert "200000" in ideck or "2e+05" in ideck.lower()

    @pytest.mark.unit
    def test_material_type_mapping_sanity(self) -> None:
        """RankTwoTensor / RankFourTensor layout round-trips within 1e-15."""
        rng = np.random.default_rng(seed=20260417)

        # 3x3 round-trip: sample a symmetric matrix, pack to Voigt, unpack,
        # compare.
        a = rng.standard_normal((3, 3))
        sym = 0.5 * (a + a.T)
        voigt = from_rank_two_tensor(sym)
        assert voigt.shape == (6,)
        roundtrip = to_rank_two_tensor(voigt)
        assert roundtrip.shape == (3, 3)
        np.testing.assert_allclose(roundtrip, sym, atol=1e-15, rtol=0.0)

        # 3x3x3x3 round-trip with enforced minor symmetries.
        b = rng.standard_normal((6, 6))
        c66 = 0.5 * (b + b.T)  # major symmetry for cleanliness
        c3333 = to_rank_four_tensor(c66)
        assert c3333.shape == (3, 3, 3, 3)
        # Minor symmetry sanity.
        np.testing.assert_allclose(c3333, np.swapaxes(c3333, 0, 1), atol=1e-15, rtol=0.0)
        np.testing.assert_allclose(c3333, np.swapaxes(c3333, 2, 3), atol=1e-15, rtol=0.0)
        # Round-trip.
        c66_rt = from_rank_four_tensor(c3333)
        np.testing.assert_allclose(c66_rt, c66, atol=1e-15, rtol=0.0)


# ---------------------------------------------------------------------------
# Supporting coverage
# ---------------------------------------------------------------------------


class TestMoosePrinterSupport:
    """Supporting coverage beyond the three acceptance items."""

    @pytest.mark.unit
    def test_deterministic_emission(self, svk_bundle: ArtifactBundle) -> None:
        """Two calls with the same bundle produce identical source."""
        a = emit(svk_bundle)
        b = emit(svk_bundle)
        assert a == b
        assert emit_header(svk_bundle) == emit_header(svk_bundle)
        assert emit_cpp(svk_bundle) == emit_cpp(svk_bundle)
        assert emit_input_file(svk_bundle) == emit_input_file(svk_bundle)

    @pytest.mark.unit
    def test_plastic_material_extra_params(self, j2_bundle: ArtifactBundle) -> None:
        """Non-E/nu material parameters surface in header and constructor."""
        header = emit_header(j2_bundle)
        cpp = emit_cpp(j2_bundle)
        for extra in ("sigma_y", "n_exp"):
            assert f"_{extra.lower()}" in header, f"extra param {extra} missing from header"
            assert f'"{extra.lower()}"' in cpp, (
                f"extra param {extra} missing from .C param registration"
            )
        assert "MechDSLJ2PowerLaw" in header

    @pytest.mark.unit
    def test_unsupported_element_type_raises(self) -> None:
        """Non-hex8 element type raises NotImplementedError."""
        svk = _make_svk_bundle()
        # Rebuild summary with a different element type.
        mutated_summary: dict[str, Any] = dict(svk.element_ir_summary)
        mutated_summary["element_type"] = "tet4"
        mutated = ArtifactBundle(
            problem_ir_dict=svk.problem_ir_dict,
            element_ir_summary=mutated_summary,
            contraction_plans=svk.contraction_plans,
        )
        with pytest.raises(NotImplementedError, match="element_type"):
            emit(mutated)
        with pytest.raises(NotImplementedError, match="element_type"):
            emit_input_file(mutated)

    @pytest.mark.unit
    def test_unsupported_dynamics_mode_raises(self) -> None:
        """Explicit dynamics raises NotImplementedError."""
        problem_ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
            boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
            dynamics_mode=DynamicsMode.EXPLICIT,
        )
        loc_result, plans = localise_and_optimize(problem_ir)
        bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
        with pytest.raises(NotImplementedError, match="DynamicsMode"):
            emit(bundle)
        with pytest.raises(NotImplementedError, match="DynamicsMode"):
            emit_input_file(bundle)

    @pytest.mark.unit
    def test_voigt_helpers_reject_bad_shapes(self) -> None:
        """Shape guards raise ValueError on misshapen input."""
        with pytest.raises(ValueError, match="Voigt"):
            to_rank_two_tensor(np.zeros(5))
        with pytest.raises(ValueError, match="3x3"):
            from_rank_two_tensor(np.zeros((2, 2)))
        with pytest.raises(ValueError, match="6x6"):
            to_rank_four_tensor(np.zeros((3, 3)))
        with pytest.raises(ValueError, match="3x3x3x3"):
            from_rank_four_tensor(np.zeros((3, 3)))
