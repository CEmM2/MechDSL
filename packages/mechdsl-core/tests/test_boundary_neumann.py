"""Golden test for the Neumann ``f_ext`` init Taichi kernel emitter.

Locks the codegen output for a single hex8 face Neumann BC into
``tests/golden/boundary_neumann.ti.txt`` so any future change to the
emitter (`mechdsl.codegen.taichi_printer.emit_neumann_f_ext_kernel`)
surfaces as an explicit diff in PR review.

Introduced by post_recovery_plan task P1-7.

Regenerating
------------
If a codegen change is intentional, set ``_UPDATE_GOLDEN = True`` below
and run the test once; review the diff in the regenerated
``boundary_neumann.ti.txt`` before committing. Then set the flag back
to ``False``. The same pattern is used in ``test_codegen.py`` for the
SVK / J2 solver goldens.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    NeumannKernelSpec,
    emit_neumann_f_ext_kernel,
)

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
_GOLDEN_PATH = _GOLDEN_DIR / "boundary_neumann.ti.txt"

# Set True to regenerate the golden file in a single test run, then
# revert. Never commit with this set to True.
_UPDATE_GOLDEN = False


# Canonical fixture: traction "0 0 -1000" on hex8 face tagged 'z1'.
_CANONICAL_SPEC = NeumannKernelSpec(
    bc_name="load",
    surface_tag="z1",
    per_node_force=(0.0, 0.0, -1000.0),
)


def _emit_source(spec: NeumannKernelSpec) -> str:
    ctx = EmissionContext()
    emit_neumann_f_ext_kernel(ctx, spec)
    return ctx.get_source()


class TestBoundaryNeumannGolden:
    """Golden snapshot for the Neumann f_ext kernel emitter."""

    @pytest.mark.integration
    def test_emitted_source_matches_golden(self):
        """Acceptance criterion #1: golden test passes on a clean
        checkout.

        Acceptance criterion #3: an intentional codegen change shows
        up as a diff in tests/golden/boundary_neumann.ti.txt — the
        ``assert source == golden`` makes any drift visible immediately.
        """
        source = _emit_source(_CANONICAL_SPEC)

        if _UPDATE_GOLDEN or not _GOLDEN_PATH.exists():
            _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
            _GOLDEN_PATH.write_text(source, encoding="utf-8")
            pytest.skip(
                f"Golden file {_GOLDEN_PATH} created/updated — "
                "rerun the test to verify the snapshot."
            )

        golden = _GOLDEN_PATH.read_text(encoding="utf-8")
        assert source == golden, (
            f"Emitted Neumann f_ext kernel diverged from golden "
            f"{_GOLDEN_PATH}. If the change is intentional, set "
            "_UPDATE_GOLDEN = True or delete the golden file and "
            "rerun to regenerate."
        )

    @pytest.mark.integration
    def test_golden_artifact_committed(self):
        """Acceptance criterion #2: the golden file lives under
        tests/golden/ alongside the test."""
        assert _GOLDEN_PATH.is_file(), (
            f"golden artifact {_GOLDEN_PATH} must be committed alongside "
            "this test (run the test once to auto-generate)"
        )

    @pytest.mark.integration
    def test_golden_is_syntactically_valid_python(self):
        """The emitted (and stored) kernel must parse as valid Python so
        a Taichi-side compile error never sneaks past the printer."""
        if not _GOLDEN_PATH.exists():
            pytest.skip("golden file not yet generated; run the snapshot test first")
        text = _GOLDEN_PATH.read_text(encoding="utf-8")
        # Wrap in a stub preamble so the kernel body's references to
        # `n_nodes`, `f_ext`, and `ti` parse without surrounding context.
        preamble = "import taichi as ti\nn_nodes = 0\nf_ext = []\n"
        ast.parse(preamble + text)
