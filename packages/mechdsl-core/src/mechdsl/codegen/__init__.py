"""Einsum optimizer, Taichi code generation, boundary condition codegen.

Backend support tiers
---------------------
The MVP-stable canonical backend is :mod:`mechdsl.codegen.taichi_printer`.
:mod:`mechdsl.codegen.mfem_printer` and :mod:`mechdsl.codegen.moose_printer`
are preserved in-tree as **experimental** surfaces (see
``dev/plans/recovery_plan_latex_contract.md`` Phase 5 (R4)).

The ``__experimental__`` convention
-----------------------------------
Every experimental printer module exposes a module-level constant::

    __experimental__: bool = True

so callers and tests can detect experimental status programmatically::

    from mechdsl.codegen import mfem_printer
    assert mfem_printer.__experimental__ is True

Stable backends do **not** set this flag.  On the first call to its public
``emit`` function, each experimental printer additionally raises a single
:class:`mechdsl.codegen._experimental.ExperimentalBackendWarning` that can
be filtered with the standard :mod:`warnings` machinery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mechdsl.codegen._experimental import ExperimentalBackendWarning
from mechdsl.codegen.taichi_printer import TaichiCodegenFacade

if TYPE_CHECKING:
    from mechdsl.codegen.artifact import ArtifactBundle
    from mechdsl.ir.mechanics_ir import ProblemIR

__all__ = ["ExperimentalBackendWarning", "TaichiCodegenFacade", "compile"]


def compile(problem_ir: ProblemIR) -> ArtifactBundle:
    """Compile a ProblemIR into a self-contained Taichi solver.

    Runs the full pipeline: localise → optimise → emit.

    **Backend stability:** Taichi is the only MVP-stable backend on the
    canonical LaTeX compile path.  MFEM and MOOSE printers exist in the
    tree as experimental surfaces (see ``mechdsl.codegen.mfem_printer``
    and ``mechdsl.codegen.moose_printer``) but they are not part of the
    stable contract and may not be supported in future recovery phases
    without explicit roadmap work (Plan B §B8).

    Parameters
    ----------
    problem_ir : ProblemIR
        The semantic problem specification.

    Returns
    -------
    ArtifactBundle
        Bundle with ``emitted_source`` populated. Contains all
        intermediate products (IRs, contraction plans).

    Raises
    ------
    ValueError
        Propagated when the IR contains an unsupported formulation,
        element type, or material model for the MVP pipeline.
    BudgetExceededError
        Propagated when einsum optimisation exceeds the absolute JIT
        budget ceiling.
    """
    from mechdsl.codegen.artifact import ArtifactBundle as _AB
    from mechdsl.codegen.taichi_printer import emit
    from mechdsl.lowering.fe_localise import localise_and_optimize

    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = _AB.from_pipeline(problem_ir, loc_result, plans)
    source = emit(bundle)

    return _AB(
        problem_ir_dict=bundle.problem_ir_dict,
        element_ir_summary=bundle.element_ir_summary,
        contraction_plans=bundle.contraction_plans,
        emitted_source=source,
        metadata=bundle.metadata,
    )
