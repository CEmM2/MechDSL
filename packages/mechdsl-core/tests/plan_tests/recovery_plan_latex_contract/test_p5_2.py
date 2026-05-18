"""Live audit for recovery-plan P5-2: Mark MFEM/MOOSE printers as experimental backend surfaces.

Asserts that MFEM and MOOSE printers are explicitly marked as experimental
backend surfaces for Phase 5 (R4), which re-anchors Taichi codegen as the
only stable compile path. The experimental marker surfaces in:

1. Module docstrings with explicit "experimental" tier label (P1-2 marker
   preserved from the prior tier statement).
2. Module-level ``__experimental__: bool = True`` constant for
   programmatic detection.
3. ``ExperimentalBackendWarning`` raised on first call to each printer's
   public ``emit`` function.
4. Module docstring of :mod:`mechdsl.codegen` describing the convention.

This task preserves the experimental backend work while making the stable
contract unambiguous — Taichi is the canonical path; MFEM/MOOSE are
research/compatibility layers.
"""

from __future__ import annotations

import importlib
import warnings

import pytest

from mechdsl.codegen import mfem_printer, moose_printer
from mechdsl.codegen._experimental import ExperimentalBackendWarning
from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize


def _make_svk_bundle() -> ArtifactBundle:
    """Minimal Hex8 / SVK bundle accepted by both experimental printers."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc, plans)


class TestP5_2:
    """
    Tests for Task P5-2: Mark MFEM/MOOSE printers as experimental backend surfaces.
    Tier: docs
    """

    @pytest.mark.integration
    def test_p5_2_c1_experimental_marker_in_module_docstrings(self) -> None:
        """
        Verify that both mfem_printer.py and moose_printer.py module docstrings
        explicitly label their support tier as experimental (P1-2 marker
        preserved) and expose ``__experimental__ is True``.

        Criterion: P5-2-c1 — Tests/docs label these backends as experimental.
        """
        # P1-2 docstring marker still present.
        assert mfem_printer.__doc__ is not None
        assert "experimental" in mfem_printer.__doc__.lower(), (
            "mfem_printer module docstring must retain the 'experimental' "
            "support-tier marker established in P1-2."
        )
        assert moose_printer.__doc__ is not None
        assert "experimental" in moose_printer.__doc__.lower(), (
            "moose_printer module docstring must retain the 'experimental' "
            "support-tier marker established in P1-2."
        )

        # Programmatic flag for tooling/tests.
        assert mfem_printer.__experimental__ is True, (
            "mfem_printer must expose `__experimental__ = True` for programmatic detection."
        )
        assert moose_printer.__experimental__ is True, (
            "moose_printer must expose `__experimental__ = True` for programmatic detection."
        )

    @pytest.mark.integration
    def test_p5_2_c2_deliverables_present_at_surfaces(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Verify that all deliverables for P5-2 are in place at the listed surfaces:

        - ``ExperimentalBackendWarning`` exists and subclasses ``UserWarning``.
        - Each experimental printer re-exports it.
        - First call to ``mfem_printer.emit`` and ``moose_printer.emit`` raises
          a single ``ExperimentalBackendWarning``.
        - ``mechdsl.codegen`` module docstring describes the
          ``__experimental__`` convention.

        Criterion: P5-2-c2 — deliverables present at the listed surfaces.
        """
        # Warning class shape.
        assert issubclass(ExperimentalBackendWarning, UserWarning), (
            "ExperimentalBackendWarning must subclass UserWarning so it is "
            "filterable with the standard warnings machinery."
        )

        # Re-exports on each experimental printer.
        assert mfem_printer.ExperimentalBackendWarning is ExperimentalBackendWarning
        assert moose_printer.ExperimentalBackendWarning is ExperimentalBackendWarning

        # codegen package docstring covers the convention (terse).
        codegen_pkg = importlib.import_module("mechdsl.codegen")
        assert codegen_pkg.__doc__ is not None
        assert "__experimental__" in codegen_pkg.__doc__, (
            "mechdsl.codegen package docstring must describe the `__experimental__` convention."
        )

        # First-use warning behaviour: reset the one-shot warn-state via
        # monkeypatch so the assertion is hermetic, then check both printers
        # raise on the next emit() call.
        bundle = _make_svk_bundle()

        monkeypatch.setattr(mfem_printer, "_warn_state", {"warned": False})
        with warnings.catch_warnings():
            warnings.simplefilter("always", ExperimentalBackendWarning)
            with pytest.warns(ExperimentalBackendWarning):
                mfem_printer.emit(bundle)

        monkeypatch.setattr(moose_printer, "_warn_state", {"warned": False})
        with warnings.catch_warnings():
            warnings.simplefilter("always", ExperimentalBackendWarning)
            with pytest.warns(ExperimentalBackendWarning):
                moose_printer.emit(bundle)

    @pytest.mark.integration
    def test_experimental_warning_only_fires_once_per_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Verify the one-shot semantics: after a fresh ``_warn_state``, the first
        ``emit()`` call raises ``ExperimentalBackendWarning`` exactly once and a
        second call in the same session is silent.

        Criterion: P5-2 follow-up — one warning per session, not per call.
        """
        bundle = _make_svk_bundle()

        # MFEM: first call warns, second call must be silent.
        monkeypatch.setattr(mfem_printer, "_warn_state", {"warned": False})
        with warnings.catch_warnings():
            warnings.simplefilter("always", ExperimentalBackendWarning)
            with pytest.warns(ExperimentalBackendWarning):
                mfem_printer.emit(bundle)

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always", ExperimentalBackendWarning)
            mfem_printer.emit(bundle)
        experimental = [w for w in recorded if issubclass(w.category, ExperimentalBackendWarning)]
        assert experimental == [], (
            "Second mfem_printer.emit call must NOT raise ExperimentalBackendWarning "
            f"in the same session; got {len(experimental)} warning(s)."
        )

        # MOOSE: same contract.
        monkeypatch.setattr(moose_printer, "_warn_state", {"warned": False})
        with warnings.catch_warnings():
            warnings.simplefilter("always", ExperimentalBackendWarning)
            with pytest.warns(ExperimentalBackendWarning):
                moose_printer.emit(bundle)

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always", ExperimentalBackendWarning)
            moose_printer.emit(bundle)
        experimental = [w for w in recorded if issubclass(w.category, ExperimentalBackendWarning)]
        assert experimental == [], (
            "Second moose_printer.emit call must NOT raise ExperimentalBackendWarning "
            f"in the same session; got {len(experimental)} warning(s)."
        )
