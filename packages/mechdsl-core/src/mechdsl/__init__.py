"""MechDSL core — LaTeX tensor expressions to FEM solver code (Taichi).

The canonical MVP-stable entry point is :func:`compile_latex`, which accepts
a LaTeX source string and produces an :class:`~mechdsl.codegen.artifact.ArtifactBundle`.
The lower-level :func:`compile` is preserved as a programmatic API that
takes a pre-built :class:`~mechdsl.ir.mechanics_ir.ProblemIR`.

See ``README.md`` Support tiers and
``dev/plans/recovery_plan_latex_contract.md`` Phase 2 (R1) for the recovery
context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mechdsl.codegen import compile

if TYPE_CHECKING:
    from mechdsl.codegen.artifact import ArtifactBundle

__version__ = "0.1.0"

# Allowed values for the `profile` argument of :func:`compile_latex`. Module-
# level so callers can introspect the supported set instead of guessing from
# the docstring. Add new profiles by extending this set explicitly — never
# silently relax the gate.
ALLOWED_PROFILES: frozenset[str] = frozenset({"mvp"})

__all__ = ["ALLOWED_PROFILES", "compile", "compile_latex"]


def compile_latex(source: str, profile: str = "mvp") -> ArtifactBundle:
    """Compile a LaTeX-source mechanics problem to an artifact bundle.

    This is the canonical MVP-stable entry point. The function:

    1. Parses ``source`` through :func:`mechdsl.frontend.parse`, which
       walks the ``% mechanics`` directive set defined in
       ``dev/design_docs/02-LATEX-DSL.md``.
    2. Adapts the resulting context dict to a :class:`ProblemIR` via
       :meth:`ProblemIR.from_context` (recovery-plan P3-2).
    3. Forwards to :func:`compile` (the existing programmatic façade)
       to run localisation, einsum planning, and Taichi emission.

    **Backend stability:** Taichi is the only MVP-stable backend on the
    canonical LaTeX compile path.  All code produced by this function
    targets the Taichi runtime.  MFEM and MOOSE are experimental backends
    preserved in the tree (``mechdsl.codegen.mfem_printer`` and
    ``mechdsl.codegen.moose_printer``) but they are not reachable through
    this façade and are not part of the stable contract.  Reaching those
    surfaces requires calling the experimental printers directly; see
    ``README.md`` Support tiers and
    ``dev/plans/recovery_plan_latex_contract.md`` Phase 5 (R4).

    Parameters
    ----------
    source:
        LaTeX source text containing ``% mechanics`` directives.
    profile:
        Compile profile selector. Only ``"mvp"`` is currently accepted;
        other profiles (e.g. extended LaTeX math grammar via NRPyLaTeX,
        non-canonical backends) are deferred to later recovery phases.

    Boundary conditions
    -------------------
    LaTeX ``% mechanics boundary`` directives populate
    :class:`mechdsl.ir.mechanics_ir.BoundaryCondition` slots on the
    resulting :class:`ProblemIR`. Two boundary kinds are supported:

    - **Dirichlet** — fixed displacement components, applied at solve
      time by the runtime adapter.
    - **Neumann** — surface tractions. When the directive carries a
      numeric traction triple, post_recovery_plan P1-5 emits an
      ``f_ext`` initialisation kernel (see ``f_ext_kernel`` in
      *Returns* below) and the bundle is self-contained for that BC.
      Neumann BCs with a symbolic-string traction leave the kernel
      slot empty.

    Numeric ``f_ext`` provisioning is the **caller's responsibility**
    when no kernel is emitted (Dirichlet-only problems or
    symbolic-traction Neumann): the caller supplies the global
    external-force vector to the solver. When ``f_ext_kernel`` is
    present, the emitted kernel overrides any manual ``f_ext``
    provisioning for the directive-driven contribution; the caller
    is still responsible for compositing it with any additional body
    forces. ``BoundaryCondition`` objects therefore document intent
    at the IR level, while the artifact bundle decides whether the
    contract is satisfied entirely by emitted code or jointly by
    caller-provided ``f_ext``.

    Returns
    -------
    ArtifactBundle
        The same bundle :func:`compile` produces, ready for golden-file
        comparison or Taichi emission. When the parsed problem contains
        one or more Neumann BCs with numeric traction (post_recovery_plan
        P1-5), the bundle's optional ``f_ext_kernel`` field carries the
        emitted ``init_f_ext_from_neumann_<bc>`` kernel source. The kernel
        signature is parametric in ``f_factor`` (= face_area /
        n_face_nodes) so the runtime mesh adapter supplies the per-node
        weighting at call time. Pure Dirichlet problems and Neumann BCs
        with symbolic-string traction leave ``f_ext_kernel`` at ``None``;
        existing residual / tangent fields and ``emitted_source`` shape
        are unchanged.

    Raises
    ------
    ValueError
        When ``profile`` is anything other than ``"mvp"``.
    mechdsl.frontend.parser.ParseError
        When the LaTeX source has a malformed ``% mechanics`` directive.
    mechdsl.symbolic.convected.UnsupportedError
        When the parsed context falls outside the MVP-supported subset.

    """
    if profile not in ALLOWED_PROFILES:
        raise ValueError(
            f"compile_latex profile={profile!r} is not supported. "
            f"Allowed profiles: {sorted(ALLOWED_PROFILES)}. "
            "Broader profile support is planned for later recovery-plan "
            "phases (see dev/plans/recovery_plan_latex_contract.md)."
        )

    import dataclasses

    from mechdsl.codegen.taichi_printer import (
        EmissionContext,
        emit_neumann_f_ext_kernel_for_ir,
    )
    from mechdsl.frontend import parse
    from mechdsl.ir.mechanics_ir import BCType, ProblemIR

    ctx = parse(source)
    problem_ir = ProblemIR.from_context(ctx)
    # P3-4 / P3-5: enforce the MVP-stable contract at the canonical
    # compile-path boundary so users hitting an experimental combination
    # or a missing required-param see a clean IR-level rejection instead
    # of a deep codegen / runtime failure.
    problem_ir.assert_mvp_stable()
    bundle = compile(problem_ir)

    # post_recovery_plan P1-5: surface a Neumann ``f_ext`` initialisation
    # kernel for every Neumann BC carrying numeric traction. Symbolic
    # (string) traction stays handled by the legacy imported numeric
    # injection path so existing callers keep working unchanged. Pure
    # Dirichlet problems leave ``f_ext_kernel`` at ``None``.
    neumann_bcs = [
        bc
        for bc in problem_ir.boundaries
        if bc.bc_type == BCType.NEUMANN and isinstance(bc.traction, tuple)
    ]
    if not neumann_bcs:
        return bundle
    em_ctx = EmissionContext()
    for bc in neumann_bcs:
        emit_neumann_f_ext_kernel_for_ir(
            em_ctx,
            bc_name=bc.name,
            surface_tag=bc.effective_surface_tag,
            traction=bc.traction,  # type: ignore[arg-type]
        )
    return dataclasses.replace(bundle, f_ext_kernel=em_ctx.get_source())
