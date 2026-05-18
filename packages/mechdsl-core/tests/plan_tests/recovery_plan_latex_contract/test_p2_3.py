"""Live audit for recovery-plan P2-3: define the frontend split.

Asserts that each frontend module's docstring identifies its role
(scanner / normalizer / validator / index resolver) and that an
ARCHITECTURE.md exists alongside the source documenting the split.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
FRONTEND = REPO_ROOT / "packages" / "mechdsl-core" / "src" / "mechdsl" / "frontend"

ARCHITECTURE = FRONTEND / "ARCHITECTURE.md"
PARSER = FRONTEND / "parser.py"
DIRECTIVES = FRONTEND / "directives.py"
TWO_POINT = FRONTEND / "two_point.py"
INIT = FRONTEND / "__init__.py"


def _doc(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestTaskP2_3:
    """
    Tests for Task P2-3: Define the frontend split — NRPyLaTeX = parser of record;
    local code = adapter/normalizer/validator.
    Tier: unit
    """

    @pytest.mark.unit
    def test_architecture_md_present(self) -> None:
        assert ARCHITECTURE.is_file(), (
            f"frontend ARCHITECTURE.md missing at {ARCHITECTURE.relative_to(REPO_ROOT)}"
        )

    @pytest.mark.unit
    def test_architecture_describes_parser_of_record_split(self) -> None:
        text = _doc(ARCHITECTURE)
        # Both halves must be named explicitly so the split is unambiguous.
        assert "parser of record" in text.lower(), (
            "ARCHITECTURE.md should use the phrase 'parser of record' to name NRPyLaTeX's role"
        )
        assert "NRPyLaTeX" in text, "ARCHITECTURE.md should name NRPyLaTeX explicitly"
        # The local-code triad should be enumerated.
        for role in ("normalization", "validation"):
            assert role.lower() in text.lower(), (
                f"ARCHITECTURE.md should name local-code role: {role!r}"
            )

    @pytest.mark.unit
    def test_parser_module_docstring_calls_out_role(self) -> None:
        text = _doc(PARSER)
        assert "ARCHITECTURE.md" in text, (
            "parser.py docstring should reference frontend/ARCHITECTURE.md"
        )
        # Parser scans + dispatches; it does NOT do math grammar.
        assert "directive" in text.lower()
        assert "NRPyLaTeX" in text or "math grammar" in text.lower(), (
            "parser.py docstring should contrast itself with the math-grammar parser"
        )

    @pytest.mark.unit
    def test_directives_module_docstring_calls_out_role(self) -> None:
        text = _doc(DIRECTIVES)
        assert "ARCHITECTURE.md" in text
        assert "normalization" in text.lower() or "normalizer" in text.lower(), (
            "directives.py docstring should identify itself as the normalization layer"
        )

    @pytest.mark.unit
    def test_two_point_module_docstring_calls_out_role(self) -> None:
        text = _doc(TWO_POINT)
        assert "ARCHITECTURE.md" in text
        assert "validator" in text.lower(), (
            "two_point.py docstring should identify itself as a validator"
        )

    @pytest.mark.unit
    def test_init_module_docstring_separates_canonical_from_secondary(self) -> None:
        text = _doc(INIT)
        # P2-2 already added Canonical / Secondary split; P2-3 leans on it.
        assert "Canonical" in text and "Secondary" in text, (
            "frontend/__init__.py module docstring should split entry points "
            "into Canonical and Secondary sections"
        )
