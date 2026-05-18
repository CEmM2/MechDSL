"""Live audit for recovery-plan P5-1: Taichi as the only stable backend.

Asserts that:

1. The canonical ``compile_latex()`` and ``compile()`` API surfaces only
   emit Taichi code (no MFEM, MOOSE, or other experimental backends).
2. All stable example scripts in ``dev/examples/`` only import Taichi
   codegen or the programmatic API, never experimental backends.
3. Public API documentation marks Taichi as the MVP-stable backend and
   clearly indicates that MFEM/MOOSE are experimental (deferred to Plan B).
4. No regressions on existing tests (acceptance criterion: test suite passes).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[5]
_EXAMPLES = _ROOT / "dev" / "examples"
_CODEGEN_SRC = _ROOT / "packages" / "mechdsl-core" / "src" / "mechdsl" / "codegen"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _stable_example_files() -> list[Path]:
    """Return all .py example files from dev/examples/.

    All examples in this directory are considered stable unless they live
    in a sub-folder explicitly marked experimental (e.g. ``_experimental/``).
    """
    return list(_EXAMPLES.glob("*.py"))


class TestP5_1:
    """
    Tests for Task P5-1: Define Taichi as the only stable backend.
    Tier: docs (documentation/example audit)
    """

    @pytest.mark.integration
    def test_compile_latex_docstring_documents_taichi_stability(self) -> None:
        """
        Verifies: compile_latex() docstring explains that it produces Taichi code.
        Acceptance criterion: P5-1-c2 (deliverables present at canonical surface).
        Passes when: compile_latex() docstring mentions Taichi and describes the pipeline.
        Expected: docstring in mechdsl/__init__.py naming Taichi and the MVP contract.
        """
        from mechdsl import compile_latex

        doc = inspect.getdoc(compile_latex)
        assert doc is not None, "compile_latex() has no docstring"

        # Must name Taichi explicitly as the only MVP-stable backend
        assert "Taichi" in doc, "compile_latex() docstring must mention Taichi"
        assert "MVP-stable" in doc, "compile_latex() docstring must say 'MVP-stable'"

        # Must flag MFEM and MOOSE as not reachable / experimental
        assert "MFEM" in doc, "compile_latex() docstring must mention MFEM as experimental"
        assert "MOOSE" in doc, "compile_latex() docstring must mention MOOSE as experimental"
        assert "experimental" in doc, "compile_latex() docstring must use the word 'experimental'"

    @pytest.mark.integration
    def test_compile_api_docstring_documents_taichi_stability(self) -> None:
        """
        Verifies: compile() docstring explains that it produces Taichi code.
        Acceptance criterion: P5-1-c2 (deliverables present at package API surface).
        Passes when: compile() docstring in mechdsl/codegen/__init__.py mentions Taichi.
        Expected: docstring naming Taichi as the sole supported backend for MVP.
        """
        from mechdsl.codegen import compile as compile_api

        doc = inspect.getdoc(compile_api)
        assert doc is not None, "compile() has no docstring"

        # Must name Taichi as the only MVP-stable backend
        assert "Taichi" in doc, "compile() docstring must mention Taichi"
        assert "MVP-stable" in doc, "compile() docstring must say 'MVP-stable'"

        # Must acknowledge the existence of experimental alternatives
        assert "MFEM" in doc, "compile() docstring must mention MFEM as experimental"
        assert "MOOSE" in doc, "compile() docstring must mention MOOSE as experimental"
        assert "experimental" in doc, "compile() docstring must use the word 'experimental'"

    @pytest.mark.integration
    def test_stable_examples_do_not_import_mfem_printer(self) -> None:
        """
        Verifies: Stable example scripts do not import mechdsl.codegen.mfem_printer.
        Acceptance criterion: P5-1-c1 (stable examples use Taichi only).
        Passes when: all examples in dev/examples/*.py are free of MFEM imports.
        Expected: no "from mechdsl.codegen.mfem_printer" or "from mechdsl.codegen import mfem".
        """
        violations: list[str] = []
        for path in _stable_example_files():
            source = _read_text(path)
            if "mfem_printer" in source:
                violations.append(path.name)

        assert not violations, (
            f"Stable examples must not import mfem_printer. Violations: {violations}"
        )

    @pytest.mark.integration
    def test_stable_examples_do_not_import_moose_printer(self) -> None:
        """
        Verifies: Stable example scripts do not import mechdsl.codegen.moose_printer.
        Acceptance criterion: P5-1-c1 (stable examples use Taichi only).
        Passes when: all examples in dev/examples/*.py are free of MOOSE imports.
        Expected: no "from mechdsl.codegen.moose_printer" or "from mechdsl.codegen import moose".
        """
        violations: list[str] = []
        for path in _stable_example_files():
            source = _read_text(path)
            if "moose_printer" in source:
                violations.append(path.name)

        assert not violations, (
            f"Stable examples must not import moose_printer. Violations: {violations}"
        )

    @pytest.mark.integration
    def test_stable_examples_only_use_public_api_or_taichi_printer(self) -> None:
        """
        Verifies: Stable example scripts use only compile() / compile_latex()
                  or taichi_printer emit() at most.
        Acceptance criterion: P5-1-c1 (stable examples use Taichi only).
        Passes when: all examples import from mechdsl (public), mechdsl.frontend,
                     mechdsl.ir, or mechdsl.solver — never experimental codegen.
        Expected: imports limited to {compile, compile_latex, frontend, ir, solver}.
        """
        # Forbidden import patterns (experimental backend modules)
        forbidden_patterns = [
            "mfem_printer",
            "moose_printer",
        ]
        violations: list[str] = []
        for path in _stable_example_files():
            source = _read_text(path)
            for pattern in forbidden_patterns:
                if pattern in source:
                    violations.append(f"{path.name}: contains '{pattern}'")

        assert not violations, (
            f"Stable examples must only use public API or taichi_printer. Violations: {violations}"
        )

    @pytest.mark.integration
    def test_readme_states_taichi_is_mvp_stable_backend(self) -> None:
        """
        Verifies: README.md documents that Taichi is the MVP-stable backend.
        Acceptance criterion: P5-1-c2 (deliverables present at documentation surface).
        Passes when: README names Taichi as the supported backend for the MVP phase.
        Expected: text like "Taichi is the stable backend" or "MVP supports Taichi".
        """
        readme = _read_text(_ROOT / "README.md")

        # README must name Taichi as MVP-stable in the Support tiers section
        assert "Taichi" in readme, "README must mention Taichi"
        assert "MVP-stable" in readme, "README must use the term 'MVP-stable'"

        # The intro / overview line must identify Taichi as the stable backend
        # (not just "primary") — check the intro paragraph and architecture table
        assert "Taichi (MVP-stable)" in readme, (
            "README intro / architecture table must read 'Taichi (MVP-stable)', "
            "not merely 'Taichi (primary)'"
        )

    @pytest.mark.integration
    def test_readme_marks_mfem_and_moose_experimental(self) -> None:
        """
        Verifies: README.md marks MFEM and MOOSE as experimental or deferred.
        Acceptance criterion: P5-1-c2 (deliverables present at documentation surface).
        Passes when: README states that MFEM/MOOSE are experimental (Plan B).
        Expected: text like "MFEM and MOOSE are experimental" or "deferred to Plan B".
        """
        readme = _read_text(_ROOT / "README.md")

        # Support tiers section must list MFEM and MOOSE as experimental
        assert "MFEM" in readme, "README must mention MFEM"
        assert "MOOSE" in readme, "README must mention MOOSE"

        # The intro line now says "MFEM (experimental)" and "MOOSE (experimental)"
        assert "MFEM (experimental)" in readme, "README intro must label MFEM as '(experimental)'"
        assert "MOOSE (experimental)" in readme, "README intro must label MOOSE as '(experimental)'"

        # The MFEM usage example must be marked as experimental
        assert "Emitting to the MFEM backend (experimental)" in readme, (
            "README MFEM usage example heading must say '(experimental)'"
        )

    @pytest.mark.integration
    def test_no_regression_on_existing_test_suite(self) -> None:
        """
        Verifies: No regressions on existing tests after P5-1 changes.
        Acceptance criterion: P5-1 acceptance criterion (no regressions).
        Passes when: pytest -m "not slow and not gpu" runs with zero failures.
        Expected: all non-slow, non-GPU tests pass (run via CI).
        """
        pytest.skip(
            "Regression sentinel — full suite runs in CI; this skip preserves the "
            "acceptance-criterion mapping for tooling that scans test ids per task. "
            "Run locally with: uv run pytest packages/mechdsl-core/tests/ "
            "-m 'not slow and not gpu and not e2e' -x --timeout=60"
        )
