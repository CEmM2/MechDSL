"""Tests for Task P4-5: dev/examples/svk_latex_math.tex + README inventory.

Acceptance criteria covered:
1. Example file present and runs end-to-end through parse_with_math
   (returns a populated context with a math block).
2. README inventory contains an entry referencing svk_latex_math.tex.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "dev").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _example_path() -> Path:
    return _repo_root() / "dev" / "examples" / "svk_latex_math.tex"


def _examples_readme() -> Path:
    return _repo_root() / "dev" / "examples" / "README.md"


class TestTaskP4_5:
    """Tests for Task P4-5: SVK LaTeX-math example."""

    @pytest.mark.integration
    def test_example_file_exists(self) -> None:
        path = _example_path()
        assert path.is_file(), f"P4-5 example missing: {path}"
        assert path.stat().st_size > 0

    @pytest.mark.integration
    def test_example_compiles_end_to_end(self) -> None:
        """``parse_with_math`` on the example returns a context with a
        populated ``math`` key, ``F`` and ``A`` tensors converted, and
        the directive-side fields (``dim``, ``cell_type``, …) intact.
        """
        from mechdsl.frontend import parse_with_math
        from mechdsl.symbolic.bridge import SymbolicNode

        source = _example_path().read_text(encoding="utf-8")
        ctx = parse_with_math(source)

        # Directive side intact.
        assert ctx.get("dim") == 3
        assert ctx.get("cell_type") == "hex8"
        assert ctx.get("formulation") == "total_lagrangian"

        # Math side populated.
        assert "math" in ctx
        tensors = ctx["math"]["tensors"]
        assert "FUU" in tensors and isinstance(tensors["FUU"], SymbolicNode)
        assert tensors["FUU"].rank == 2

        # Two-point classification preserved end-to-end.
        f_class = ctx["math"]["classifications"]["FUU"]
        assert 0 in f_class.spatial_axes
        assert 1 in f_class.material_axes

    @pytest.mark.integration
    def test_examples_readme_lists_new_example(self) -> None:
        text = _examples_readme().read_text(encoding="utf-8")
        assert "svk_latex_math.tex" in text, (
            "dev/examples/README.md must list svk_latex_math.tex in the inventory"
        )
        # The entry should describe the LaTeX-math integration.
        assert "math" in text.lower(), "README entry should describe the math integration"
