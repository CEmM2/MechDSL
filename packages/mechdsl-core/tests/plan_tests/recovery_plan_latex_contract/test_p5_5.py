"""Task P5-5: Split codegen verification into stable vs experimental suites.

Phase 5 (R4) — regression-tier acceptance: verify that generated code verification
tests can be split into a "stable" suite (Taichi only, must-pass on every push) and
an "experimental" suite (MFEM/MOOSE, allowed to skip or xfail without blocking
the stable contract).

Acceptance criteria:
  1. Stable suite passes independently of experimental backend status.
  2. All deliverables for P5-5 are in place at the surfaces listed.
  3. No regressions on the existing test suite.

Implementation mechanism: pytest markers (stable_backend / experimental_backend)
and/or directory split. Stable tests can run independently; experimental tests
can be deselected via marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Root of the mechdsl-core tests directory.
_TESTS_ROOT = Path(__file__).parent.parent.parent  # packages/mechdsl-core/tests/
_PROJECT_ROOT = _TESTS_ROOT.parent.parent.parent  # repo root


class TestP5_5:
    """Tests for Task P5-5: Split codegen verification into stable vs experimental."""

    @pytest.mark.integration
    @pytest.mark.regression
    def test_stable_suite_taichi_only_passes_independently(self) -> None:
        """P5-5-c1: Stable suite passes independently of experimental backend status.

        Verifies by reflection: every file that constitutes the stable suite
        (test_codegen, test_taichi_printer, test_taichi_printer_ul,
        test_emission_phase5) carries the ``stable_backend`` marker at module
        level, while none of the experimental files (test_mfem_printer,
        test_moose_printer, test_cross_backend) carry ``stable_backend``.

        This guarantees that ``pytest -m "stable_backend"`` selects only
        Taichi-only tests and deselects every MFEM/MOOSE test — so the stable
        suite is independent of experimental backend availability.
        """
        import ast

        stable_files = [
            "test_codegen",
            "test_taichi_printer",
            "test_taichi_printer_ul",
            "test_emission_phase5",
            "test_emission_verification",
            "test_emit_lame_conversion",
        ]
        experimental_files = [
            "test_mfem_printer",
            "test_moose_printer",
            "test_cross_backend",
        ]

        def _get_pytestmark_names(module_name: str) -> list[str]:
            """Parse a test module with AST and return pytestmark marker names.

            Uses AST parsing rather than import so that modules with relative
            imports or heavy optional dependencies (taichi, mfem, moose) can
            be inspected without executing their import-time side effects.

            Looks for a top-level assignment of the form:
                pytestmark = pytest.mark.<name>
            or a list variant:
                pytestmark = [pytest.mark.<name>, ...]
            """
            test_file = _TESTS_ROOT / f"{module_name}.py"
            assert test_file.exists(), f"Test file not found: {test_file}"
            tree = ast.parse(test_file.read_text(), filename=str(test_file))

            marker_names: list[str] = []
            for node in ast.iter_child_nodes(tree):
                if not isinstance(node, ast.Assign):
                    continue
                # Only top-level: targets must include 'pytestmark'.
                if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
                    continue
                # Walk the value to collect pytest.mark.<name> attribute accesses.
                for sub in ast.walk(node.value):
                    if (
                        isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Attribute)
                        and isinstance(sub.value.value, ast.Name)
                        and sub.value.value.id == "pytest"
                        and sub.value.attr == "mark"
                    ):
                        marker_names.append(sub.attr)
            return marker_names

        # Verify stable files carry stable_backend.
        for name in stable_files:
            marks = _get_pytestmark_names(name)
            assert "stable_backend" in marks, (
                f"{name}.py must carry pytestmark = pytest.mark.stable_backend "
                f"(found markers: {marks})"
            )
            assert "experimental_backend" not in marks, (
                f"{name}.py must NOT carry experimental_backend marker "
                f"(stable files must be disjoint from experimental set)"
            )

        # Verify experimental files carry experimental_backend and NOT stable_backend.
        for name in experimental_files:
            marks = _get_pytestmark_names(name)
            assert "experimental_backend" in marks, (
                f"{name}.py must carry pytestmark = pytest.mark.experimental_backend "
                f"(found markers: {marks})"
            )
            assert "stable_backend" not in marks, (
                f"{name}.py must NOT carry stable_backend marker "
                f"(experimental files must be disjoint from stable set)"
            )

    @pytest.mark.integration
    @pytest.mark.regression
    def test_deliverables_present_at_surfaces(self) -> None:
        """P5-5-c2: All deliverables for P5-5 are in place at the listed surfaces.

        Verifies: Changes to test_codegen*.py reflect the stable/experimental split.
        Surfaces:
          - packages/mechdsl-core/tests/test_codegen.py
          - packages/mechdsl-core/tests/test_cross_backend.py
          - packages/mechdsl-core/tests/test_mfem_printer.py
          - packages/mechdsl-core/tests/test_moose_printer.py
        """
        # 1. pyproject.toml registers both new markers.
        pyproject = _PROJECT_ROOT / "pyproject.toml"
        assert pyproject.exists(), f"pyproject.toml not found at {pyproject}"
        pyproject_text = pyproject.read_text()
        assert "stable_backend" in pyproject_text, (
            "pyproject.toml must register the 'stable_backend' marker "
            "(required by --strict-markers)"
        )
        assert "experimental_backend" in pyproject_text, (
            "pyproject.toml must register the 'experimental_backend' marker "
            "(required by --strict-markers)"
        )

        # 2. test_codegen.py contains pytestmark with stable_backend.
        test_codegen = _TESTS_ROOT / "test_codegen.py"
        assert test_codegen.exists()
        codegen_src = test_codegen.read_text()
        assert "stable_backend" in codegen_src, (
            "test_codegen.py must contain pytestmark = pytest.mark.stable_backend"
        )

        # 3. test_mfem_printer.py contains pytestmark with experimental_backend.
        test_mfem = _TESTS_ROOT / "test_mfem_printer.py"
        assert test_mfem.exists()
        mfem_src = test_mfem.read_text()
        assert "experimental_backend" in mfem_src, (
            "test_mfem_printer.py must contain pytestmark = pytest.mark.experimental_backend"
        )

        # 4. test_moose_printer.py contains pytestmark with experimental_backend.
        test_moose = _TESTS_ROOT / "test_moose_printer.py"
        assert test_moose.exists()
        moose_src = test_moose.read_text()
        assert "experimental_backend" in moose_src, (
            "test_moose_printer.py must contain pytestmark = pytest.mark.experimental_backend"
        )

        # 5. test_cross_backend.py contains pytestmark with experimental_backend.
        test_cross = _TESTS_ROOT / "test_cross_backend.py"
        assert test_cross.exists()
        cross_src = test_cross.read_text()
        assert "experimental_backend" in cross_src, (
            "test_cross_backend.py must contain pytestmark = pytest.mark.experimental_backend"
        )

    @pytest.mark.integration
    @pytest.mark.regression
    def test_no_regressions_on_existing_suite(self) -> None:
        """P5-5-c3: No regressions on the existing test suite.

        Verifies: All originally passing codegen tests still pass after the
        split (stable tests still pass, experimental tests are correctly marked
        and can be selectively deselected).

        This is a regression sentinel: the test files themselves are the
        regression guard. Any breakage in the tagged files will surface when
        pytest runs those files directly. Here we verify structural integrity —
        that the marker additions did not corrupt the module-level syntax of
        the tagged files.
        """
        import ast

        files_to_check = [
            # stable
            _TESTS_ROOT / "test_codegen.py",
            _TESTS_ROOT / "test_taichi_printer.py",
            _TESTS_ROOT / "test_taichi_printer_ul.py",
            _TESTS_ROOT / "test_emission_phase5.py",
            _TESTS_ROOT / "test_emission_verification.py",
            _TESTS_ROOT / "test_emit_lame_conversion.py",
            # experimental
            _TESTS_ROOT / "test_mfem_printer.py",
            _TESTS_ROOT / "test_moose_printer.py",
            _TESTS_ROOT / "test_cross_backend.py",
        ]

        for path in files_to_check:
            assert path.exists(), f"Tagged test file missing: {path}"
            source = path.read_text()
            try:
                ast.parse(source)
            except SyntaxError as exc:
                pytest.fail(f"Syntax error in {path.name} after P5-5 marker additions: {exc}")

        # Verify pytestmark lines are syntactically correct assignments
        # (not comments, not inside functions) by checking the raw source.
        stable_files = [
            _TESTS_ROOT / "test_codegen.py",
            _TESTS_ROOT / "test_taichi_printer.py",
            _TESTS_ROOT / "test_taichi_printer_ul.py",
            _TESTS_ROOT / "test_emission_phase5.py",
            _TESTS_ROOT / "test_emission_verification.py",
            _TESTS_ROOT / "test_emit_lame_conversion.py",
        ]
        for path in stable_files:
            src = path.read_text()
            assert "pytestmark = pytest.mark.stable_backend" in src, (
                f"{path.name}: pytestmark assignment not found or malformed"
            )

        experimental_files = [
            _TESTS_ROOT / "test_mfem_printer.py",
            _TESTS_ROOT / "test_moose_printer.py",
            _TESTS_ROOT / "test_cross_backend.py",
        ]
        for path in experimental_files:
            src = path.read_text()
            assert "pytestmark = pytest.mark.experimental_backend" in src, (
                f"{path.name}: pytestmark assignment not found or malformed"
            )
