"""Plan-tests for Task P4-1: author swift_voce.yaml and compile end-to-end.

Plan: dev/plans/mfront_cycleM0.md (lines 114-116) — MFront-mimic Cycle M0, Phase 4.
Deliverable under test: laws/plasticity/swift_voce.yaml (MechDSL) + the
mechdsl-lawgen compile pipeline producing swift_voce.py + _manifest.json + a
generated test file for the SwiftVoce hardening law.

This is the MechDSL-side integration test. It exercises the full Phase 1-3
pipeline (PlasticityCarrierSpec load -> lower_expression -> budgets/guards ->
carrier + manifest + test emit) via the CLI ``main`` entry point and asserts
byte-stable output with the canonical Cycle 0 source_hash.

⚠️ EXEC-TIME CONSTRAINTS (see Phase_4_Scaffold_Validation.md):
  * PATH COLLISION — the Cycle 0 hand-authored reference already lives at
    NumerixWeave libs/ticonstit/.../generated/plasticity/swift_voce.py
    (source_hash 7b5af3a8...). P4-1 must NOT clobber it; these tests emit the
    candidate to a pytest ``tmp_path`` so nothing in NumerixWeave is touched.
  * PARAMETER SET — to reproduce Cycle 0's source_hash the YAML yields the
    canonical formula R = sigma0 + Q*(1-exp(-b*p)) + K*((p+p0)**n - p0**n)
    (params sigma0, Q, b, K, n, p0).
  * R3 — this test runs from the MechDSL venv (never NumerixWeave .venv).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mechdsl.lawgen.carrier_emitter import snake_case_module_name
from mechdsl.lawgen.cli import load_carrier_spec, main
from mechdsl.lawgen.contracts import PlasticityCarrierSpec

if TYPE_CHECKING:
    from types import ModuleType

# The authoritative law YAML this task ships (repo-relative). This test file is
# packages/mechdsl-core/tests/plan_tests/mfront_cyclem0/test_P4-1.py, so the repo
# root is five parents up (mfront_cyclem0 → plan_tests → tests → mechdsl-core →
# packages → <root>).
_REPO_ROOT = Path(__file__).resolve().parents[5]
SWIFT_VOCE_YAML = _REPO_ROOT / "laws" / "plasticity" / "swift_voce.yaml"

# Cycle 0's published source_hash — the SHA-256 of the canonical generator-input
# formula string ``"R = sigma0 + Q*(1-exp(-b*p)) + K*((p+p0)**n - p0**n)"``.
CANONICAL_SOURCE_HASH = "7b5af3a8bb79c2e44e0055a7076dd2c9de2ce8c75eb2e262b80bb4e0232d557f"


def _compile_to(out_dir: Path) -> int:
    """Invoke the CLI compile on the shipped YAML, emitting to ``out_dir``."""
    return main(["compile", str(SWIFT_VOCE_YAML), "--target", "ticonstit", "--out", str(out_dir)])


class TestTaskP4_1:
    """Tests for Task P4-1: swift_voce.yaml + end-to-end compile. AC covered: 1-5."""

    @pytest.mark.integration
    def test_swift_voce_yaml_parses_into_carrier_spec(self) -> None:
        """Verifies: laws/plasticity/swift_voce.yaml loads into PlasticityCarrierSpec.
        AC1: the YAML loads without error.
        Passes when: the loader returns a PlasticityCarrierSpec with R/H/Q expressions."""
        spec = load_carrier_spec(SWIFT_VOCE_YAML)
        assert isinstance(spec, PlasticityCarrierSpec)
        assert spec.name == "SwiftVoce"
        # The canonical Cycle 0 parameter set (Q, not the placeholder epsilon0).
        assert spec.parameters == ("sigma0", "Q", "b", "K", "n", "p0")
        # All three role expressions are present; H/Q are the neutral rate/thermal
        # factors (== 1), NOT dR/dp.
        assert set(spec.expressions) == {"R", "H", "Q"}
        assert spec.H == 1
        assert spec.Q == 1
        # R references every material parameter.
        assert {s.name for s in spec.R.free_symbols} >= {"sigma0", "Q", "b", "K", "n", "p0"}

    @pytest.mark.integration
    def test_compile_dry_run_writes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verifies: mechdsl-lawgen compile --dry-run succeeds and writes no files.
        AC2: compile exits 0 in dry-run.
        Passes when: exit code 0 and the target dir is unchanged."""
        out = tmp_path / "generated"
        rc = main(
            [
                "compile",
                str(SWIFT_VOCE_YAML),
                "--target",
                "ticonstit",
                "--out",
                str(out),
                "--dry-run",
            ]
        )
        assert rc == 0
        printed = capsys.readouterr().out
        assert "emission plan (dry-run" in printed
        assert "SwiftVoce" in printed
        # Dry-run must not create the output directory or any artifact.
        assert not out.exists()

    @pytest.mark.integration
    def test_compile_emits_swift_voce_and_manifest(self, tmp_path: Path) -> None:
        """Verifies: compile produces swift_voce.py + _manifest.json + test file.
        AC3/AC4: the emitted module and manifest are written to the (scratch) target
        and the manifest carries the correct source_hash.
        Passes when: all three artifacts exist and manifest source_hash == 7b5af3a8..."""
        out = tmp_path / "generated"
        rc = _compile_to(out)
        assert rc == 0

        module = snake_case_module_name("SwiftVoce")
        carrier = out / "plasticity" / f"{module}.py"
        manifest = out / "_manifest.json"
        test_file = out / "tests" / f"test_{module}.py"

        # AC3: all three artifacts exist.
        assert carrier.is_file()
        assert manifest.is_file()
        assert test_file.is_file()

        # The carrier is snake_case (swift_voce.py) but exports the CamelCase class.
        assert carrier.name == "swift_voce.py"
        carrier_text = carrier.read_text(encoding="utf-8")
        assert f"source_hash: {CANONICAL_SOURCE_HASH}" in carrier_text
        assert "class SwiftVoce:" in carrier_text
        # INV-DG-1: the generated runtime carrier imports Taichi only.
        assert "import taichi as ti" in carrier_text
        for forbidden in ("import sympy", "import mechdsl", "import ticonstit"):
            assert forbidden not in carrier_text

        # AC4: the manifest carries the canonical Cycle 0 source_hash + schema.
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        entry = doc["laws"][0]
        assert entry["name"] == "SwiftVoce"
        assert entry["source"] == "swift_voce.py"
        assert entry["exports"] == "SwiftVoce"
        assert entry["source_hash"] == CANONICAL_SOURCE_HASH
        assert entry["target_contract"] == "VoceHardeningModel"
        assert entry["parameters"]["required"] == ["sigma0", "Q", "b"]
        assert entry["parameters"]["optional"] == ["K", "n", "p0"]

    @pytest.mark.integration
    def test_compile_is_byte_stable_across_two_runs(self, tmp_path: Path) -> None:
        """Verifies: re-running compile yields byte-identical swift_voce.py.
        AC5: determinism — two runs produce identical file content + source_hash.
        Passes when: the two emitted files compare byte-equal."""
        module = snake_case_module_name("SwiftVoce")
        out_a = tmp_path / "run_a"
        out_b = tmp_path / "run_b"
        assert _compile_to(out_a) == 0
        assert _compile_to(out_b) == 0

        for relative in (
            Path("plasticity") / f"{module}.py",
            Path("_manifest.json"),
            Path("tests") / f"test_{module}.py",
        ):
            bytes_a = (out_a / relative).read_bytes()
            bytes_b = (out_b / relative).read_bytes()
            assert bytes_a == bytes_b, f"{relative} is not byte-stable across two compiles"

    @pytest.mark.slow
    @pytest.mark.integration
    def test_generated_smoke_kernel_runs(self, tmp_path: Path) -> None:
        """Verifies: the emitted test file's JIT smoke kernel actually compiles + runs.

        Regression guard for the smoke-kernel symbol-form bug: the generated
        ``test_taichi_smoke`` builds a ``@ti.kernel`` that pins every *bare*
        material-parameter name to a placeholder local and returns the lowered R.
        If the compiler ever feeds the carrier's rebound ``self.<param>`` R into
        ``emit_tests`` again, the kernel references ``self`` with no ``self`` in
        scope and Taichi raises ``TaichiNameError``. This test loads the emitted
        file as a module and executes ``test_taichi_smoke`` (which JIT-compiles and
        calls the kernel), so such a regression fails loudly here rather than only
        in the shipped artifact. Marked ``slow`` — it invokes the Taichi JIT."""
        pytest.importorskip("taichi")
        module = snake_case_module_name("SwiftVoce")
        out = tmp_path / "generated"
        assert _compile_to(out) == 0

        test_file = out / "tests" / f"test_{module}.py"
        generated = _load_generated_module(test_file, "generated_test_swift_voce")

        # The generated smoke test itself JIT-compiles the lowered R kernel and
        # asserts the result is finite. Running it here fails on a self/peeq leak.
        generated.test_taichi_smoke()

    @pytest.mark.integration
    def test_compile_enables_formula_matches_spec_guard(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies: the CLI real-emission path passes ``check_matches_spec=True`` to
        ``emit_manifest``, so the hashed input_formula is validated against ``spec.R``.

        Wiring guard: the emitted swift_voce.yaml is internally consistent (param
        ``Q`` in both formula and parameters), so the check passes on the happy path
        (covered by the other tests). Here we force ``formula_matches_spec`` to return
        ``False``; the compile must then fail loud (exit non-zero, spec-mismatch
        error, no files written). If ``check_matches_spec`` were dropped from the CLI
        call, the guard would never be consulted and the compile would still succeed —
        so this test fails, catching the regression."""
        import mechdsl.lawgen.manifest as manifest_mod

        monkeypatch.setattr(manifest_mod, "formula_matches_spec", lambda *_a, **_k: False)
        out = tmp_path / "generated"
        rc = _compile_to(out)
        assert rc != 0, "compile should fail when the formula does not match spec.R"
        assert "not symbolically equal" in capsys.readouterr().err
        # Fail-loud path writes nothing.
        assert (
            not (out / "plasticity" / snake_case_module_name("SwiftVoce"))
            .with_suffix(".py")
            .exists()
        )


def _load_generated_module(path: Path, module_name: str) -> ModuleType:
    """Import an emitted Python file as a module so its functions can be called.

    Used to execute the generated ``test_taichi_smoke`` in-process — the emitted
    file must be a valid, runnable Python module, and importing it here is what
    genuinely exercises the generated kernel (not just an existence check)."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"could not load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
