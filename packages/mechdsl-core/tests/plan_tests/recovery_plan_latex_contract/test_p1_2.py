"""Live audit for recovery-plan P1-2: Mark experimental surfaces.

Asserts that MFEM/MOOSE printers, the explicit-dynamics solver helper,
the non-MVP material model package, and the non-canonical element types
all carry an experimental-tier marker in their module/class documentation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
SRC = REPO_ROOT / "packages" / "mechdsl-core" / "src" / "mechdsl"

MFEM_PRINTER = SRC / "codegen" / "mfem_printer.py"
MOOSE_PRINTER = SRC / "codegen" / "moose_printer.py"
LUMPED_MASS = SRC / "solver" / "lumped_mass.py"
MODELS_INIT = SRC / "symbolic" / "models" / "__init__.py"
MECHANICS_IR = SRC / "ir" / "mechanics_ir.py"

EXPERIMENTAL_MARKER = "experimental"


def _module_doc(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestTaskP1_2:
    """
    Tests for Task P1-2: Mark MFEM/MOOSE codegen, explicit dynamics, non-MVP
    materials, and non-canonical elements as experimental.
    Tier: docs
    """

    @pytest.mark.audit
    def test_mfem_printer_marked_experimental(self) -> None:
        text = _module_doc(MFEM_PRINTER)
        assert EXPERIMENTAL_MARKER in text.lower(), (
            "mfem_printer.py module docstring should mark backend as experimental"
        )

    @pytest.mark.audit
    def test_moose_printer_marked_experimental(self) -> None:
        text = _module_doc(MOOSE_PRINTER)
        assert EXPERIMENTAL_MARKER in text.lower(), (
            "moose_printer.py module docstring should mark backend as experimental"
        )

    @pytest.mark.audit
    def test_explicit_dynamics_marked_experimental(self) -> None:
        text = _module_doc(LUMPED_MASS)
        assert EXPERIMENTAL_MARKER in text.lower(), (
            "lumped_mass.py module docstring should mark explicit dynamics as experimental"
        )

    @pytest.mark.audit
    def test_non_mvp_materials_called_out(self) -> None:
        text = _module_doc(MODELS_INIT)
        for stable in ("svk", "j2_power_law"):
            assert stable in text, f"models/__init__.py should name MVP-stable model {stable!r}"
        for experimental in (
            "neo_hookean",
            "mooney_rivlin",
            "ogden",
            "hgo",
            "perzyna",
            "johnson_cook",
            "lemaitre",
        ):
            assert experimental in text, (
                f"models/__init__.py should name experimental model {experimental!r}"
            )

    @pytest.mark.audit
    def test_non_canonical_elements_called_out(self) -> None:
        text = _module_doc(MECHANICS_IR)
        enum_match = re.search(r"class ElementType.*?(?=class \w)", text, flags=re.DOTALL)
        assert enum_match, "ElementType class not located in mechanics_ir.py"
        block = enum_match.group(0).lower()
        assert "hex8" in block and "mvp-stable" in block, (
            "ElementType docstring should call out HEX8 as MVP-stable"
        )
        assert EXPERIMENTAL_MARKER in block, (
            "ElementType docstring should label non-canonical elements experimental"
        )
        for non_canonical in ("tet4", "tet10", "hex20"):
            assert non_canonical in block, (
                f"ElementType docstring should mention non-canonical element {non_canonical!r}"
            )
