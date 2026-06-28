"""Tests for Task P3-1: BC handoff paragraph in compile_latex docstring.

Acceptance criteria covered:
1. compile_latex.__doc__ mentions BoundaryCondition.
2. Docstring covers the f_ext caller-provisioning contract.
3. Docstring linter passes on the modified module.
"""

from __future__ import annotations

import inspect
import re
import subprocess
from pathlib import Path

import pytest

_CALLER_PROVISIONING_TOKENS = ("caller", "supplied", "supplies", "provisioning")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


class TestTaskP3_1:
    """Tests for Task P3-1: BC handoff paragraph in compile_latex docstring."""

    @pytest.mark.docs
    def test_docstring_mentions_boundary_condition(self) -> None:
        from mechdsl import compile_latex

        doc = inspect.getdoc(compile_latex)
        assert doc is not None, "compile_latex has no docstring"
        assert "BoundaryCondition" in doc, (
            "compile_latex docstring must reference BoundaryCondition "
            "(the IR slot populated by `% mechanics boundary` directives)"
        )

    @pytest.mark.docs
    def test_docstring_covers_f_ext_caller_provisioning(self) -> None:
        from mechdsl import compile_latex

        doc = inspect.getdoc(compile_latex)
        assert doc is not None, "compile_latex has no docstring"
        assert "f_ext" in doc, "compile_latex docstring must mention f_ext"
        lowered = doc.lower()
        assert any(token in lowered for token in _CALLER_PROVISIONING_TOKENS), (
            "compile_latex docstring must describe f_ext as caller-provisioned "
            f"(any of {_CALLER_PROVISIONING_TOKENS} expected)"
        )

    @pytest.mark.docs
    def test_docstring_linter_passes_on_module(self) -> None:
        root = _repo_root()
        target = root / "packages" / "mechdsl-core" / "src" / "mechdsl" / "__init__.py"
        assert target.is_file(), f"missing {target}"
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "D", str(target)],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        # Ruff exits 0 when clean; any D-rule violation should fail this test.
        assert result.returncode == 0, (
            f"docstring lint failed (rc={result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        # Defensive: no lingering D-rule violations even if returncode is 0.
        assert not re.search(r"\bD\d{3}\b", result.stdout), (
            f"docstring lint reported D-rule code in stdout:\n{result.stdout}"
        )
