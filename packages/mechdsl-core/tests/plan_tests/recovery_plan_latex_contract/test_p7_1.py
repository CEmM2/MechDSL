"""Task P7-1: Split end-to-end tests into ``from_latex`` and ``from_problem_ir`` families.

Phase 7 (R6.1) — integration-tier acceptance: the recovery plan requires that
e2e coverage make the LaTeX-input vs. programmatic-IR-input boundary explicit.
Today every test under ``packages/mechdsl-core/tests/`` that exercises the full
pipeline constructs ``ProblemIR`` directly (see ``test_e2e.py:_make_elastic_problem_ir``);
no test starts from a LaTeX string. Until P7-1 lands, CI / pytest selection
cannot meaningfully distinguish "tests that exercise the LaTeX contract" from
"tests that bypass the frontend".

Tier: integration

Acceptance criteria:
  1. P7-1-c1: CI/test selection makes the boundary explicit (e.g. via
     ``-m from_latex`` / ``-m from_problem_ir``, separate folders, or naming
     convention queryable by ``pytest -k``).
  2. P7-1-c2: Deliverables present at the listed surfaces
     (``packages/mechdsl-core/tests/**``).
  3. No regressions on the existing test suite.

Blocked by: P5-1 (Taichi as the only stable backend — the family split is
defined relative to the canonical Taichi compile path).

Implementation note:
  P7-1 introduces two pytest markers — ``from_latex`` and
  ``from_problem_ir`` — registered in the root ``pyproject.toml``'s
  ``[tool.pytest.ini_options]`` ``markers`` list. The existing top-level
  e2e modules (``test_e2e.py``, ``test_e2e_taichi.py``,
  ``test_e2e_plastic.py``, ``test_full_pipeline.py``,
  ``test_compile_pipeline.py``) all construct ``ProblemIR`` programmatically
  and therefore receive ``pytestmark = pytest.mark.from_problem_ir``.
  The ``from_latex`` family is intentionally empty at the close of P7-1 —
  the first member lands in P7-2 (canonical LaTeX-to-solution acceptance
  test). Per recovery-plan scope, only top-level e2e modules carry these
  markers; per-task ``plan_tests/`` files are not relabelled.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Repository root:
#   packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_1.py
#   parents[0]=recovery_plan_latex_contract, [1]=plan_tests, [2]=tests,
#   [3]=mechdsl-core, [4]=packages, [5]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_E2E_TEST_DIR = _REPO_ROOT / "packages" / "mechdsl-core" / "tests"


def _read_registered_markers() -> list[str]:
    """Parse the ``markers`` list under ``[tool.pytest.ini_options]``.

    The pyproject style is a TOML array of ``"<name>: <description>"``
    strings (one per line, comma-separated). We use the stdlib TOML parser
    so escaped inner quotes (``'-m \\"not slow\\"'``) round-trip cleanly.
    """
    import tomllib

    with _PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    markers = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers")
    assert isinstance(markers, list), (
        "pyproject.toml [tool.pytest.ini_options].markers must be a list"
    )
    return [str(entry) for entry in markers]


def _collect_node_ids(marker_expr: str) -> list[str]:
    """Run ``pytest --collect-only -q -m <marker_expr>`` and return node IDs."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            marker_expr,
            str(_E2E_TEST_DIR),
        ],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        check=False,
    )
    # pytest exits 5 when no tests are collected — that's a valid outcome
    # for the ``from_latex`` family today and must not crash this harness.
    lines = (proc.stdout + proc.stderr).splitlines()
    node_ids: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Collected node IDs look like "path/to/test.py::TestClass::test_x".
        if "::" in stripped and not stripped.startswith(("=", "-", "<", "!")):
            node_ids.append(stripped)
    return node_ids


class TestP7_1:
    """Tests for Task P7-1: e2e family split (``from_latex`` / ``from_problem_ir``)."""

    @pytest.mark.integration
    def test_ci_test_selection_exposes_from_latex_family(self) -> None:
        """P7-1-c1: CI/test selection makes the boundary explicit.

        Verifies: a discoverable ``from_latex`` family exists — both
        ``from_latex`` and ``from_problem_ir`` are registered as pytest
        markers in ``pyproject.toml``, and the ``from_problem_ir`` family
        is non-empty (at least one e2e module carries the marker today).
        The ``from_latex`` family may be empty until P7-2 lands its
        canonical LaTeX-to-solution test; the *selector* must still be
        registered and queryable.
        """
        markers = _read_registered_markers()
        names = {entry.split(":", 1)[0].strip() for entry in markers}

        assert "from_latex" in names, (
            "pyproject.toml [tool.pytest.ini_options].markers must register "
            "`from_latex` so `pytest -m from_latex` is a queryable selector. "
            f"Registered markers: {sorted(names)}"
        )
        assert "from_problem_ir" in names, (
            "pyproject.toml [tool.pytest.ini_options].markers must register "
            "`from_problem_ir` so `pytest -m from_problem_ir` is a queryable "
            f"selector. Registered markers: {sorted(names)}"
        )

        # Every registered marker entry has the form "<name>: <description>".
        for entry in markers:
            if entry.split(":", 1)[0].strip() in {"from_latex", "from_problem_ir"}:
                assert ":" in entry, f"Marker registration must include a description: {entry!r}"
                _, description = entry.split(":", 1)
                assert description.strip(), f"Marker `{entry}` must have a non-empty description"

        # The ``from_problem_ir`` family must be non-empty today.
        problem_ir_nodes = _collect_node_ids("from_problem_ir")
        assert problem_ir_nodes, (
            "`pytest -m from_problem_ir` collected zero tests under "
            f"{_E2E_TEST_DIR} — at least one top-level e2e module must "
            "carry `pytestmark = pytest.mark.from_problem_ir`."
        )

    @pytest.mark.integration
    def test_deliverables_present_at_surfaces(self) -> None:
        """P7-1-c2: Deliverables present at the listed surfaces.

        Verifies: at least one e2e file under
        ``packages/mechdsl-core/tests/test_e2e*.py`` (or other top-level
        ``test_*.py``) carries ``pytest.mark.from_problem_ir`` at module
        level, and the marker registration in ``pyproject.toml`` follows
        the existing ``"<name>: <description>"`` convention.
        """
        # (a) At least one top-level e2e file carries
        #     ``pytestmark = ... from_problem_ir ...`` at module level.
        candidates = sorted(_E2E_TEST_DIR.glob("test_e2e*.py"))
        assert candidates, (
            f"No `test_e2e*.py` files found under {_E2E_TEST_DIR}; "
            "the from_problem_ir family has nowhere to live."
        )

        marker_pattern = re.compile(
            r"^pytestmark\s*=.*from_problem_ir",
            flags=re.MULTILINE,
        )
        carriers = [
            path for path in candidates if marker_pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert carriers, (
            "At least one `test_e2e*.py` module must declare "
            "`pytestmark = pytest.mark.from_problem_ir` (or include it in a "
            "list-form pytestmark) at module level. Inspected: "
            f"{[p.name for p in candidates]}"
        )

        # (b) Marker registration follows the existing convention.
        markers = _read_registered_markers()
        for entry in markers:
            name, _, description = entry.partition(":")
            assert name.strip(), f"Empty marker name in entry {entry!r}"
            assert description.strip(), (
                f"Marker entry {entry!r} must have a non-empty description "
                "(convention established by `slow`, `e2e`, `stable_backend`)."
            )

        registered_names = {entry.split(":", 1)[0].strip() for entry in markers}
        assert {"from_latex", "from_problem_ir"} <= registered_names, (
            "Both family markers must be registered for the split to be "
            f"structural. Registered: {sorted(registered_names)}"
        )
