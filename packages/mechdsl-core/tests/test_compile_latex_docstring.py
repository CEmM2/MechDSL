"""Regression guard for the BC handoff paragraph in compile_latex.__doc__.

post_recovery_plan Phase 3 added a "Boundary conditions" section to the
public compile_latex docstring (P3-1). This test asserts the section
remains present so the contract cannot silently drift.

The assertions key on literal tokens (BoundaryCondition, f_ext) and a
small set of caller-provisioning synonyms checked in lowercase rather
than full sentences, to keep the regression guard robust against
incidental copy-edits while still failing if the substantive contract
terms disappear.
"""

from __future__ import annotations

import inspect

import pytest

CALLER_PROVISIONING_TOKENS = ("caller", "supplied", "supplies", "provisioning")


@pytest.mark.docs
def test_compile_latex_docstring_mentions_boundary_condition() -> None:
    """compile_latex.__doc__ contains the literal token ``BoundaryCondition``."""
    from mechdsl import compile_latex

    doc = inspect.getdoc(compile_latex)
    assert doc is not None, "compile_latex has no docstring"
    assert "BoundaryCondition" in doc, (
        "compile_latex docstring lost its reference to BoundaryCondition — "
        "the BC handoff contract paragraph must remain (post_recovery_plan P3-1)."
    )


@pytest.mark.docs
def test_compile_latex_docstring_describes_f_ext_caller_provisioning() -> None:
    """compile_latex.__doc__ documents f_ext as caller-provisioned."""
    from mechdsl import compile_latex

    doc = inspect.getdoc(compile_latex)
    assert doc is not None, "compile_latex has no docstring"
    assert "f_ext" in doc, "compile_latex docstring must mention f_ext"
    lowered = doc.lower()
    assert any(token in lowered for token in CALLER_PROVISIONING_TOKENS), (
        "compile_latex docstring must describe f_ext as caller-provisioned "
        f"(any of {CALLER_PROVISIONING_TOKENS} expected post_recovery_plan P3-1)."
    )


@pytest.mark.docs
def test_compile_latex_docstring_names_dirichlet_and_neumann() -> None:
    """The BC handoff paragraph enumerates the supported BC kinds explicitly."""
    from mechdsl import compile_latex

    doc = inspect.getdoc(compile_latex)
    assert doc is not None, "compile_latex has no docstring"
    for kind in ("Dirichlet", "Neumann"):
        assert kind in doc, (
            f"compile_latex docstring must name {kind} as a supported BC kind "
            "(post_recovery_plan P3-1)."
        )
