"""Tests for Task P7-1: restore `## Inventory` anchor in dev/examples/README.md.

Acceptance: README contains `## Inventory` heading.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "dev").is_dir():
            return parent
    raise RuntimeError("repo root not found")


class TestTaskP7_1:
    @pytest.mark.docs
    def test_examples_readme_has_inventory_anchor(self) -> None:
        path = _repo_root() / "dev" / "examples" / "README.md"
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert re.search(r"^## Inventory\s*$", text, re.MULTILINE), (
            "dev/examples/README.md must contain a `## Inventory` heading"
        )
