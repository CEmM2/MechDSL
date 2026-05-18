"""Tests for Task P2-1: register `docs` pytest marker.

Acceptance criteria covered:
1. `uv run pytest --markers` lists `docs` alongside `slow`, `gpu`, `e2e`.
2. `.claude/rules/tests.md` mentions `docs` tier.
3. No `PytestUnknownMarkWarning` for `@pytest.mark.docs`.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Walk up until pyproject.toml with [tool.pytest.ini_options] is found."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            ini = data.get("tool", {}).get("pytest", {}).get("ini_options")
            if ini is not None:
                return parent
    raise RuntimeError("repo root with [tool.pytest.ini_options] not found")


def _registered_marker_names(pyproject: Path) -> set[str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    markers = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
    assert isinstance(markers, list)
    return {str(entry).split(":", 1)[0].strip() for entry in markers}


class TestTaskP2_1:
    """Tests for Task P2-1: Register `docs` pytest marker.

    Acceptance criteria covered: 1, 2, 3.
    """

    @pytest.mark.unit
    def test_docs_marker_registered_in_pyproject(self) -> None:
        """`docs` declared under ``[tool.pytest.ini_options].markers``."""
        root = _repo_root()
        names = _registered_marker_names(root / "pyproject.toml")
        assert "docs" in names, (
            f"pyproject.toml [tool.pytest.ini_options].markers must register "
            f"'docs'. Registered: {sorted(names)}"
        )
        for required in ("slow", "gpu", "e2e"):
            assert required in names, f"baseline marker '{required}' missing from {sorted(names)}"

    @pytest.mark.unit
    def test_tests_md_mentions_docs_tier(self) -> None:
        """`.claude/rules/tests.md` registers the `docs` tier in its Markers section."""
        root = _repo_root()
        tests_md = root / ".claude" / "rules" / "tests.md"
        assert tests_md.is_file(), f"missing {tests_md}"
        content = tests_md.read_text(encoding="utf-8")
        markers_section = re.search(r"## Markers\s*\n(.+?)(?:\n## |\Z)", content, re.DOTALL)
        assert markers_section is not None, "## Markers section missing in tests.md"
        body = markers_section.group(1)
        assert re.search(r"`@pytest\.mark\.docs`", body), (
            "tests.md ## Markers section must reference `@pytest.mark.docs`"
        )

    @pytest.mark.unit
    def test_no_unknown_mark_warning_for_docs(self, tmp_path: Path) -> None:
        """`@pytest.mark.docs` collects clean under --strict-markers."""
        probe = tmp_path / "test_docs_probe.py"
        probe.write_text(
            "import pytest\n@pytest.mark.docs\ndef test_probe():\n    assert True\n",
            encoding="utf-8",
        )
        root = _repo_root()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                str(root / "pyproject.toml"),
                "--rootdir",
                str(root),
                str(probe),
                "--collect-only",
                "-q",
                "--strict-markers",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"strict-marker collection failed (rc={result.returncode}):\n{combined}"
        )
        assert "PytestUnknownMarkWarning" not in combined, (
            f"unexpected unknown-mark warning:\n{combined}"
        )
