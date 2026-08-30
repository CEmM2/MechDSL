"""Layer 5 -- Taichi code printer: ArtifactBundle -> self-contained .py file.

Emits deterministic, syntactically valid Python/Taichi source code from an
:class:`~mechdsl.codegen.artifact.ArtifactBundle`.  The emitted file contains:

* Taichi imports and ``ti.init``
* Hex8 quadrature tables (shape functions and gradients as literal arrays)
* ``ti.field`` declarations (dimensions set by a mesh loader at runtime)
* SVK or J2 constitutive update ``@ti.func``
* Internal-force ``@ti.kernel``
* Tangent matrix-free matvec ``@ti.kernel``
* Newton-Raphson driver (Python level)

The output is deterministic: same bundle -> identical source string.

Uses ``ti.f64`` throughout.  Physics indices -> ``ti.static`` in emitted code;
mesh indices -> runtime loops.  See ``dev/design_docs/07-CONVENTIONS.md``.

Recovery P5-4 — enriched IR consumption
---------------------------------------
The printer prefers :attr:`ArtifactBundle.element_ir_dict` (the canonical
post-P4-5 contract surface carrying ``ElementIR.to_dict()``) over the
legacy :attr:`ArtifactBundle.element_ir_summary` for element-identity
fields (``element_type``, ``dim``, ``n_nodes``, ``n_quadrature_points``).
The :func:`_ir_field` helper performs the priority lookup and falls back
to ``element_ir_summary`` when ``element_ir_dict`` is empty (pre-P4-5
bundles), keeping legacy callers byte-identical.

When enrichment blocks (``geometry``, ``material_eval``, ``local_force``,
``local_tangent``) are populated and ``EmissionContext.verbose=True``,
:func:`emit_preamble` surfaces each block's key fields as auditability
comments in the emitted file's docstring.  The ``verbose`` flag defaults
to ``False`` so existing golden files (byte-equality regression guards)
remain stable; tests that exercise the auditability path opt-in
explicitly.

P9-2 template-family dispatch
-----------------------------
Per-contraction shape choices (displacement-gradient scatter, force
integration, tangent contractions) are routed through the module-level
:data:`family_emitters` dict, keyed on :class:`Family`.  Every contraction
emitted by this printer goes through the dispatch on the happy path when
:func:`mechdsl.codegen.einsum_optimizer.family_emitters_enabled` is ``True``
(the default).  The legacy tier-only path is reachable via the
``MECHDSL_FAMILY_EMITTERS=0`` env-var for rollout-time A/B equivalence
tests; both paths call the same underlying helpers, so the emitted source
is byte-identical.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np  # noqa: TC002 — used at runtime for table formatting

from mechdsl.codegen.einsum_optimizer import family_emitters_enabled
from mechdsl.codegen.family_registry import Family
from mechdsl.codegen.hex8_tables import (
    GRAD_AT_QUAD,
    HEX8_QUAD_WEIGHTS,
    SHAPE_AT_QUAD,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from mechdsl.codegen.artifact import ArtifactBundle, ContractionPlan

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Emission helpers
# ---------------------------------------------------------------------------


@dataclass
class EmissionContext:
    """Tracks state during code emission.

    The ``verbose`` flag (default ``False``) gates auditability comments
    that surface enriched-IR contract fields (P5-4) in the emitted file's
    docstring header.  Defaults to off so existing golden snapshots remain
    byte-identical; tests / debugging callers may set it to ``True`` to
    inspect the contract surface that drove the emission.
    """

    indent: int = 0
    lines: list[str] = field(default_factory=list)
    verbose: bool = False

    def emit(self, line: str = "") -> None:
        """Emit a line at current indentation."""
        if line:
            self.lines.append("    " * self.indent + line)
        else:
            self.lines.append("")

    def indent_block(self) -> _IndentCtx:
        """Context manager for indentation."""
        return _IndentCtx(self)

    def get_source(self) -> str:
        return "\n".join(self.lines) + "\n"


class _IndentCtx:
    def __init__(self, ctx: EmissionContext) -> None:
        self.ctx = ctx

    def __enter__(self) -> EmissionContext:
        self.ctx.indent += 1
        return self.ctx

    def __exit__(self, *args: object) -> None:
        self.ctx.indent -= 1


# ---------------------------------------------------------------------------
# Enriched-IR consumption helpers
#
# The printer historically read element identity fields from
# ``ArtifactBundle.element_ir_summary`` (the legacy 4-key dict).  The
# canonical carrier is now ``ArtifactBundle.element_ir_dict``, which is
# ``ElementIR.to_dict()`` and includes the four execution-contract blocks
# (``geometry``, ``material_eval``, ``local_force``, ``local_tangent``).
#
# ``_ir_field`` performs the priority lookup so every consumer site funnels
# through a single definition of "prefer enriched, fall back to legacy".
# ``_ir_block`` returns one of the four enrichment blocks (or ``None``).
# ---------------------------------------------------------------------------


def _ir_field(bundle: ArtifactBundle, key: str, default: Any) -> Any:
    """Read an element-identity field, preferring enriched IR.

    Parameters
    ----------
    bundle : ArtifactBundle
        The pipeline artifact bundle.  Post-P4-5 bundles carry both
        ``element_ir_dict`` (canonical) and ``element_ir_summary`` (legacy).
    key : str
        The field name to read.  Note that ``element_ir_dict`` uses
        ``ElementIR.to_dict()`` keys; the legacy summary uses the same
        names for the four overlap fields (``element_type``, ``dim``,
        ``n_nodes``).  The quadrature-point count maps:
        ``element_ir_dict["geometry"]["n_quad"]`` (when geometry block is
        present) ↔ ``element_ir_summary["n_quadrature_points"]``.  This
        helper handles only the flat overlap; callers that need the
        quadrature count from the geometry block call :func:`_ir_block`
        directly.
    default : Any
        Returned when neither dict carries the key.

    Returns
    -------
    Any
        The value from ``element_ir_dict[key]`` if present and the dict is
        non-empty (post-P4-5 path); else from ``element_ir_summary[key]``
        (legacy back-compat); else *default*.  Typed as ``Any`` because
        ``ArtifactBundle`` dict payloads are heterogeneous (``int`` for
        ``n_nodes``/``dim``, ``str`` for ``element_type``, nested ``dict``
        for enrichment blocks); typing as ``object`` would force every
        numeric call site (e.g. ``n_nodes * dim``) to add a redundant
        ``cast(int, ...)`` while providing no real safety since the values
        originate from untyped JSON-shaped dicts.
    """
    enriched = bundle.element_ir_dict
    if enriched and key in enriched:
        return enriched[key]
    return bundle.element_ir_summary.get(key, default)


def _ir_block(bundle: ArtifactBundle, block_name: str) -> dict[str, object] | None:
    """Return one of the four P4-1 enrichment blocks, or ``None``.

    The enrichment blocks live under :attr:`ArtifactBundle.element_ir_dict`
    (canonical) with a redundant copy under :attr:`element_ir_summary`
    (P4-3).  This helper prefers the canonical dict and falls back to the
    summary when ``element_ir_dict`` is empty (pre-P4-5 bundles).

    Parameters
    ----------
    bundle : ArtifactBundle
    block_name : str
        One of ``"geometry"``, ``"material_eval"``, ``"local_force"``,
        ``"local_tangent"``.

    Returns
    -------
    dict | None
        The block dict, or ``None`` if neither carrier holds it (or both
        carriers store ``None``).
    """
    enriched = bundle.element_ir_dict
    if enriched:
        block = enriched.get(block_name)
        if isinstance(block, dict):
            return block
    block = bundle.element_ir_summary.get(block_name)
    if isinstance(block, dict):
        return block
    return None


def _n_quadrature_points(bundle: ArtifactBundle, default: int = 8) -> int:
    """Quadrature-point count, preferring the geometry block over summary.

    Post-P4-5 bundles expose ``n_quad`` via ``element_ir_dict["geometry"]``;
    legacy bundles only expose ``n_quadrature_points`` on the summary.
    Both paths converge here so the printer's emit_constants only has one
    code path.
    """
    geom = _ir_block(bundle, "geometry")
    if geom is not None and "n_quad" in geom:
        return int(geom["n_quad"])  # type: ignore[call-overload,no-any-return]
    legacy = bundle.element_ir_summary.get("n_quadrature_points", default)
    return int(legacy)  # type: ignore[call-overload]


# ---------------------------------------------------------------------------
# Material-model classification
# ---------------------------------------------------------------------------


def _is_plastic_material(model: str) -> bool:
    """Return True when *model* follows the plastic/damage history-field path.

    Models that need per-QP ``alpha`` history plus a radial-return
    ``constitutive_update_plastic`` in the emitted kernel.  Lemaitre (Plan B
    phase B6, task P6-2) layers a damage update on top of the J2 power-law
    return map, so it shares the same ``alpha``/``plastic_strain`` plumbing
    plus its own ``damage_D``/``is_deleted`` fields (see
    :func:`mechdsl.solver.history_fields.create_lemaitre_history`).
    """
    return model in ("j2_power_law", "lemaitre")


def _is_damage_material(model: str) -> bool:
    """Return True when *model* carries scalar damage and element deletion."""
    return model == "lemaitre"


def _emits_generated_tangent_matvec(bundle: ArtifactBundle) -> bool:
    """True when the generated matrix-free tangent matvec ``@ti.kernel`` is emitted.

    The runtime-q kernels (PlanJune14 WI-1) from
    :func:`emit_svk_tangent_matvec_kernel` / :func:`emit_j2_tangent_matvec_kernel`
    are the SOLE consumers of the device-resident quadrature fields
    ``_GRAD_AT_QUAD_F`` / ``_QUAD_WEIGHTS_F``. They are emitted only for the
    SVK or J2 / Total-Lagrangian / reference / non-derived path (see the dispatch
    in :func:`emit`, ~L3239/3247). Gating the quad-field emission on this same
    predicate keeps every other golden (Lemaitre, UL, derived, explicit)
    byte-identical — otherwise dead quad-field declarations leak into formulations
    that never use them (the WI-1 regression the UL golden test caught).
    """
    model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    configuration = bundle.problem_ir_dict.get("configuration", "reference")
    # The matvec kernel is emitted ONLY in the static (implicit Newton) branch
    # (see :func:`emit`, ~L3275): the EXPLICIT central-difference driver skips it.
    # Explicit dynamics also declares its own fields (``v``, ``M_lumped``) placed
    # in ``allocate_explicit_fields`` (not the shared ``allocate_fields``), so
    # emitting the quad-field ``from_numpy`` here would force materialisation
    # while those are still unplaced — a "field(s) not placed" RuntimeError.
    dynamics_mode = bundle.problem_ir_dict.get("dynamics_mode", "static")
    return (
        model in ("svk", "j2_power_law")
        and bundle.derived_energy is None
        and configuration != "current"
        and dynamics_mode != "explicit"
    )


def _derived_params(bundle: ArtifactBundle) -> list[str] | None:
    """Ordered material-parameter names for a LaTeX-derived bundle, or ``None``.

    When a bundle carries a ``derived_energy`` model, the whole generated solver
    is parameterised on this list (the union of the parameters in the derived
    stress and tangent) instead of the hard-coded SVK/J2 ``(lam, mu)`` names.
    Returning ``None`` selects the unchanged named-model emission path.
    """
    if bundle.derived_energy is None:
        return None
    from mechdsl.symbolic.anisotropic_energy import AnisotropicEnergyModel
    from mechdsl.symbolic.spectral_energy import SpectralEnergyModel

    de = bundle.derived_energy
    # Each model class names its own parameter vocabulary; the closed-form
    # invariant path scans the rank-4 tangent, the spectral / fiber paths carry
    # their parameter symbols directly (their tangent is FD, not symbolic).
    if isinstance(de, SpectralEnergyModel):
        from mechdsl.codegen.spectral_emitter import spectral_param_names

        names = spectral_param_names(de)
    elif isinstance(de, AnisotropicEnergyModel):
        from mechdsl.codegen.anisotropic_emitter import anisotropic_param_names

        names = anisotropic_param_names(de)
    else:
        from mechdsl.codegen.energy_emitter import derived_param_names

        names = derived_param_names(de)
    if not names:
        # A derived energy with zero material parameters is degenerate: the
        # solver would be parameterised on nothing, and the constitutive_update
        # / tangent_matvec / newton_solve signatures would emit malformed
        # (empty-argument) Python. Fail fast at this boundary rather than
        # generating broken code downstream.
        raise ValueError(
            "LaTeX-derived constitutive model exposes no material parameters; "
            "a strain-energy function must depend on at least one material "
            "constant (e.g. mu, kappa) to generate a runnable solver."
        )
    return names


def _fiber_family0(bundle: ArtifactBundle) -> tuple[float, float, float] | None:
    """The single declared fiber-direction family, or ``None`` if no fiber field.

    Read from the serialised fiber-field carry (``FiberFieldSpec.to_dict`` ->
    ``{"families": [[x, y, z], ...]}``), which the codegen layer now consumes for
    anisotropic (HGO) models. Only the first family is used — the MVP
    perfectly-aligned single-family case; per-element heterogeneous fiber fields
    (a placed ``ti.Vector.field`` gathered as ``fiber_dir[e]``) are a future
    extension for when the IR carries per-element fiber data.
    """
    fiber_field = bundle.problem_ir_dict.get("fiber_field")
    if not fiber_field:
        return None
    families = fiber_field.get("families") or []
    if not families:
        return None
    a = families[0]
    return (float(a[0]), float(a[1]), float(a[2]))


# ---------------------------------------------------------------------------
# Formatting helpers (deterministic)
# ---------------------------------------------------------------------------


def _fmt_float(v: float) -> str:
    """Format a float deterministically for code emission."""
    # 17 significant digits for deterministic round-trip
    s = f"{v:.17g}"
    return s


def _fmt_matrix_literal(arr: np.ndarray, name: str) -> list[str]:
    """Format a 2-D numpy array as a list-of-lists literal, one row per line."""
    rows: list[str] = []
    rows.append(f"{name} = [")
    for i in range(arr.shape[0]):
        vals = ", ".join(_fmt_float(float(arr[i, j])) for j in range(arr.shape[1]))
        rows.append(f"    [{vals}],")
    rows.append("]")
    return rows


def _fmt_3d_literal(arr: np.ndarray, name: str) -> list[str]:
    """Format a 3-D numpy array as a nested list literal."""
    lines: list[str] = []
    lines.append(f"{name} = [")
    for q in range(arr.shape[0]):
        lines.append("    [")
        for a in range(arr.shape[1]):
            vals = ", ".join(_fmt_float(float(arr[q, a, j])) for j in range(arr.shape[2]))
            lines.append(f"        [{vals}],")
        lines.append("    ],")
    lines.append("]")
    return lines


def _fmt_1d_literal(arr: np.ndarray, name: str) -> str:
    """Format a 1-D numpy array as a list literal."""
    vals = ", ".join(_fmt_float(float(v)) for v in arr)
    return f"{name} = [{vals}]"


# ---------------------------------------------------------------------------
# Per-family emitters (Taichi backend)
# ---------------------------------------------------------------------------
#
# These helpers emit the per-contraction code shapes that the Taichi MVP
# uses today. Each helper is the single owner of its family's emission
# pattern; the legacy inline bodies that used to sit in the force /
# tangent kernels now delegate to these helpers via :data:`family_emitters`
# so the dispatch is exercised on the happy path (define-but-don't-call
# is a silent failure).
#
# Every helper is **source-identical** to the inline body it replaces —
# this is a pure refactor. The cross-backend equivalence tests and the
# regenerated goldens are the regression guard.


def _emit_family_displacement_gradient_taichi(ctx: EmissionContext) -> None:
    """Emit the Hex8 TL displacement-gradient (F = I + grad u) scatter.

    Family :class:`Family.DISPLACEMENT_GRADIENT`, Taichi backend. The
    mathematical einsum is ``qaI,ai->qiI`` but here we emit the classical
    ``F = I + sum_a u_a otimes (dN_a/dX)`` scatter directly into a
    ``ti.Matrix`` ``F``. The caller has already emitted ``dNdX``; this
    helper owns every line from the identity seed through the scatter
    loop body.
    """
    ctx.emit("# Deformation gradient F = I + grad_u")
    ctx.emit("# grad_u_{iI} = sum_a u_{ai} * dN_a/dX_I")
    ctx.emit("F = ti.Matrix.identity(ti.f64, DIM)")
    ctx.emit("for a in range(N_NODES):")
    with ctx.indent_block():
        ctx.emit("nid = elem_nodes[e, a]")
        ctx.emit("for i in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("for I in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("F[i, I] += u[nid][i] * dNdX[a, I]")


def _emit_family_force_integration_taichi(ctx: EmissionContext) -> None:
    """Emit the Hex8 TL internal-force integrand ``B^T P``.

    Family :class:`Family.FORCE_INTEGRATION`, Taichi backend. The
    mathematical einsum is ``qaI,qiI->qai``; here this is the per-QP
    contraction ``f_a_i += w_q * detJ0 * P_{iI} * dNdX_{aI}``. Assumes
    ``P``, ``dNdX``, ``w_q``, ``detJ0`` are already in scope.
    """
    ctx.emit("# Integrate internal force: f_a_i += w_q * detJ0 * P_{iI} * dNdX_{aI}")
    ctx.emit("w_q = QUAD_WEIGHTS[q]")
    ctx.emit("for a in range(N_NODES):")
    with ctx.indent_block():
        ctx.emit("nid = elem_nodes[e, a]")
        ctx.emit("force_a = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)")
        ctx.emit("for i in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("val = ti.f64(0.0)")
            ctx.emit("for I in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("val += P[i, I] * dNdX[a, I]")
            ctx.emit("force_a[i] = val")
        ctx.emit("for i in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("f_int[nid][i] += w_q * detJ0 * force_a[i]")


def _emit_family_material_tangent_contraction_taichi(
    ctx: EmissionContext, is_plastic: bool
) -> None:
    """Emit the TL tangent sandwich (B^T C B collapsed to SVK or J2 form).

    Family :class:`Family.MATERIAL_TANGENT_CONTRACTION`, Taichi backend.
    The mathematical einsum is ``qaI,qiIjJ,qbJ->qaibj``; for SVK the
    4th-order tangent collapses into ``lam*tr(dE)*I + 2*mu*dE`` so the
    emission is a short closed form, while J2 re-invokes ``radial_return``
    and performs the ``ijkl,kl->ij`` sub-contraction (TANGENT_DOUBLE_
    CONTRACTION) explicitly. The legacy body in
    :func:`_emit_tl_tangent_qp_body` is preserved verbatim.
    """
    if is_plastic:
        ctx.emit("# J2 algorithmic consistent tangent: re-run the return map")
        ctx.emit("# with the stored alpha.  The result supplies both the")
        ctx.emit("# current PK2 stress and the 4th-order tangent C_ep.")
        ctx.emit("rm = radial_return(_j2_mat, E, float(alpha_np[e, q]))")
        ctx.emit("S = rm.stress")
        ctx.emit("dS = np.einsum('ijkl,kl->ij', rm.tangent, dE)")
    else:
        ctx.emit("# SVK PK2 stress: S = lambda tr(E) I + 2 mu E.")
        ctx.emit("tr_E = float(np.trace(E))")
        ctx.emit("S = lam * tr_E * I3 + 2.0 * mu * E")
        ctx.emit("")
        ctx.emit("# SVK material tangent C is constant; the contraction C : dE")
        ctx.emit("# collapses to the same closed form as the stress update.")
        ctx.emit("tr_dE = float(np.trace(dE))")
        ctx.emit("dS = lam * tr_dE * I3 + 2.0 * mu * dE")


def _emit_family_tangent_double_contraction_taichi(ctx: EmissionContext) -> None:
    """Emit the rank-4:rank-2 contraction ``ijkl,kl->ij`` (UL spatial tangent).

    Family :class:`Family.TANGENT_DOUBLE_CONTRACTION`, Taichi backend.
    Only used on the Updated Lagrangian tangent path where the spatial
    tangent ``c_tau`` must be contracted with ``grad_v``. Source-identical
    to the legacy line in :func:`_emit_ul_tangent_qp_body`.
    """
    ctx.emit("# Material term: dsigma_mat_{ij} = c^tau_{ijkl} * grad_v_{kl}")
    ctx.emit("dsigma_mat = np.einsum('ijkl,kl->ij', c_tau, grad_v)")


def _emit_family_fallback_taichi(ctx: EmissionContext) -> None:
    """No-op fallback. Contractions without a Taichi-specific template
    land here; the caller is responsible for emitting a runtime-loop
    body. For the MVP scope (Hex8 + SVK/J2/Lemaitre on TL or UL) no
    contraction hits this path, but the entry exists so the dispatch
    table is total over :data:`FAMILIES`.
    """
    ctx.emit("# (P9-2 fallback: no template override — caller emits inline)")


# Family-emitter dispatch table. Keyed on :class:`Family`; each
# entry is callable with ``(ctx, *args)`` at the relevant emission site.
# Heterogeneous signatures are intentional — families emit into different
# containing scopes. The table is total over :data:`family_registry.FAMILIES`
# so :func:`family_emitters_enabled` cannot hit a KeyError at runtime.
family_emitters: dict[Family, Callable[..., None]] = {
    Family.DISPLACEMENT_GRADIENT: _emit_family_displacement_gradient_taichi,
    Family.FORCE_INTEGRATION: _emit_family_force_integration_taichi,
    Family.MATERIAL_TANGENT_CONTRACTION: _emit_family_material_tangent_contraction_taichi,
    Family.TANGENT_DOUBLE_CONTRACTION: _emit_family_tangent_double_contraction_taichi,
    Family.RANK2_OUTER: _emit_family_fallback_taichi,
    Family.RANK2_SYMMETRIC_OUTER: _emit_family_fallback_taichi,
    Family.PUSH_FORWARD_RANK4: _emit_family_fallback_taichi,
    Family.FALLBACK: _emit_family_fallback_taichi,
}


def _dispatch_family(family: Family, ctx: EmissionContext, *args: object) -> bool:
    """Dispatch emission to :data:`family_emitters` if the flag is on.

    Returns ``True`` when the family emitter was invoked (and the caller
    must skip the legacy inline body), ``False`` when the legacy path
    should run. Encapsulating the flag check here keeps the
    "define-but-don't-call" failure mode impossible — every call site
    that consults the table funnels through this helper.
    """
    if not family_emitters_enabled():
        return False
    emitter = family_emitters.get(family, _emit_family_fallback_taichi)
    if emitter is _emit_family_fallback_taichi:
        # Fallback intentionally defers to the legacy body; signal the
        # caller to emit the inline code path. Log at DEBUG so that
        # silent-fallback collisions are observable.
        _logger.debug("taichi_printer: family %s routed to legacy body", family.name)
        return False
    emitter(ctx, *args)
    return True


# ---------------------------------------------------------------------------
# Section emitters
# ---------------------------------------------------------------------------


def emit_preamble(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit imports and ti.init.

    Recovery P5-4: element identity fields are sourced from
    ``element_ir_dict`` first (post-P4-5 canonical contract surface),
    falling back to ``element_ir_summary`` for legacy bundles.  When
    ``ctx.verbose`` is true and the four P4-1 enrichment blocks are
    populated, additional auditability comments surface
    ``material_eval`` / ``geometry`` / ``local_force`` / ``local_tangent``
    fields in the docstring header.  Verbose comments are gated to keep
    existing golden snapshots byte-identical.
    """
    # Extract material model for the header comment
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    formulation = bundle.problem_ir_dict.get("formulation", "total_lagrangian")
    # Prefer element_ir_dict over element_ir_summary for identity fields.
    element_type = _ir_field(bundle, "element_type", "hex8")
    dim = _ir_field(bundle, "dim", 3)

    ctx.emit('"""Auto-generated Taichi FEM solver. DO NOT EDIT.')
    ctx.emit("")
    ctx.emit(f"Formulation : {formulation}")
    ctx.emit(f"Material    : {material_model}")
    ctx.emit(f"Element     : {element_type}")
    ctx.emit(f"Dimension   : {dim}")
    # Auditability — opt-in, never on by default. Surface enriched-IR
    # contract fields so users can see WHY the codegen made specific
    # decisions (stress measure, integration count, force/tangent layout).
    if ctx.verbose:
        _emit_enrichment_audit(ctx, bundle)
    ctx.emit('"""')
    ctx.emit("")
    ctx.emit("import taichi as ti")
    ctx.emit("import numpy as np")
    ctx.emit("")
    ctx.emit("ti.init(default_fp=ti.f64, arch=ti.cpu)")
    ctx.emit("")


def _emit_enrichment_audit(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit auditability comments for the four P4-1 enrichment blocks.

    Called from :func:`emit_preamble` only when ``ctx.verbose`` is true.
    Each line is a ``# Field: value`` comment surfacing one fact from the
    enriched IR's contract surface; the comments are descriptive, not
    behavioural, so they are safe to add or remove without affecting the
    emitted kernels.
    """
    material_eval = _ir_block(bundle, "material_eval")
    geometry = _ir_block(bundle, "geometry")
    local_force = _ir_block(bundle, "local_force")
    local_tangent = _ir_block(bundle, "local_tangent")

    if not any((material_eval, geometry, local_force, local_tangent)):
        # Legacy bundle without enrichment blocks — nothing to surface.
        return

    ctx.emit("")
    ctx.emit("Enriched-IR contract surface (recovery P5-4 audit):")
    if material_eval is not None:
        if "stress_measure" in material_eval:
            ctx.emit(f"  Stress measure   : {material_eval['stress_measure']}")
        if "strain_measure" in material_eval:
            ctx.emit(f"  Strain measure   : {material_eval['strain_measure']}")
        if "tangent_rank" in material_eval:
            ctx.emit(f"  Tangent rank     : {material_eval['tangent_rank']}")
        if "support_tier" in material_eval:
            ctx.emit(f"  Support tier     : {material_eval['support_tier']}")
    if geometry is not None and "n_quad" in geometry:
        ctx.emit(f"  Quadrature       : {geometry['n_quad']}-point")
    if local_force is not None and "n_dof" in local_force:
        n_dof = local_force["n_dof"]
        # Annotate with derived breakdown when identity fields are available.
        n_nodes = _ir_field(bundle, "n_nodes", None)
        dim = _ir_field(bundle, "dim", None)
        if n_nodes is not None and dim is not None:
            ctx.emit(f"  Force n_dof      : {n_dof} ({n_nodes} × {dim})")
        else:
            ctx.emit(f"  Force n_dof      : {n_dof} (n_nodes × dim)")
    if local_tangent is not None:
        if "n_dof" in local_tangent:
            ctx.emit(f"  Tangent n_dof    : {local_tangent['n_dof']}")
        # The descriptor key is ``is_symmetric`` per LocalTangentDescriptor;
        # accept ``symmetric`` as a fallback for any future renames.
        if "is_symmetric" in local_tangent:
            ctx.emit(f"  Tangent symmetric: {local_tangent['is_symmetric']}")
        elif "symmetric" in local_tangent:
            ctx.emit(f"  Tangent symmetric: {local_tangent['symmetric']}")


def emit_constants(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit mesh/element constants from the IR.

    Writes Hex8 quadrature tables as Python list literals that Taichi
    kernels can index into at compile time via ``ti.static``.

    Recovery P5-4: ``n_nodes`` and ``dim`` come from
    :func:`_ir_field` (prefers ``element_ir_dict`` over the legacy
    ``element_ir_summary``); the quadrature-point count comes from
    :func:`_n_quadrature_points`, which prefers the
    ``geometry`` enrichment block's ``n_quad`` field over the legacy
    ``n_quadrature_points`` summary key.
    """
    n_nodes = _ir_field(bundle, "n_nodes", 8)
    n_qp = _n_quadrature_points(bundle, default=8)
    dim = _ir_field(bundle, "dim", 3)

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Element constants: Hex8, 2x2x2 Gauss quadrature")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit(f"N_NODES = {n_nodes}")
    ctx.emit(f"N_QP = {n_qp}")
    ctx.emit(f"DIM = {dim}")
    ctx.emit(f"N_DOF_ELEM = N_NODES * DIM  # {n_nodes * dim}")
    ctx.emit("")

    # Quadrature weights
    ctx.emit(_fmt_1d_literal(HEX8_QUAD_WEIGHTS, "QUAD_WEIGHTS"))
    ctx.emit("")

    # Shape functions at quadrature points: SHAPE_AT_QUAD[q, a]
    for line in _fmt_matrix_literal(SHAPE_AT_QUAD, "SHAPE_AT_QUAD"):
        ctx.emit(line)
    ctx.emit("")

    # Shape function gradients at quadrature points: GRAD_AT_QUAD[q, a, i]
    for line in _fmt_3d_literal(GRAD_AT_QUAD, "GRAD_AT_QUAD"):
        ctx.emit(line)
    ctx.emit("")


def emit_field_declarations(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit ti.field declarations for mesh data, solution, forces.

    Actual dimensions are set by the mesh loader at runtime.
    Here we emit the declarations with placeholder sizes.

    For J2 plasticity, also emits history fields (alpha per element per
    quadrature point).
    """
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Field declarations (dimensions set by mesh loader at runtime)")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("# Placeholder dimensions -- overwritten by load_mesh()")
    ctx.emit("n_nodes = 0")
    ctx.emit("n_elem = 0")
    ctx.emit("")
    ctx.emit("# Taichi fields -- allocated after mesh is loaded")
    ctx.emit("x_ref = ti.Vector.field(3, dtype=ti.f64)       # reference coords")
    ctx.emit("x_cur = ti.Vector.field(3, dtype=ti.f64)       # current coords")
    ctx.emit("u = ti.Vector.field(3, dtype=ti.f64)            # displacement")
    ctx.emit("f_int = ti.Vector.field(3, dtype=ti.f64)        # internal force")
    ctx.emit("f_ext = ti.Vector.field(3, dtype=ti.f64)        # external force")
    ctx.emit("residual = ti.Vector.field(3, dtype=ti.f64)     # residual = f_int - f_ext")
    ctx.emit("du = ti.Vector.field(3, dtype=ti.f64)           # displacement increment")
    ctx.emit("Kv = ti.Vector.field(3, dtype=ti.f64)           # tangent matvec result")
    ctx.emit("elem_nodes = ti.field(dtype=ti.i32)             # connectivity")
    if _emits_generated_tangent_matvec(bundle):
        ctx.emit("")
        ctx.emit("# Quadrature tables as ti.fields (PlanJune14 WI-1): the matrix-free")
        ctx.emit("# tangent matvec kernels run the q-loop at RUNTIME (the ÷8 JIT-budget")
        ctx.emit("# lever), so they cannot index the Python-list constants GRAD_AT_QUAD /")
        ctx.emit("# QUAD_WEIGHTS by a runtime q. These device-resident copies are filled")
        ctx.emit("# from those constants in allocate_fields(). The Python lists are kept")
        ctx.emit("# for the ti.static-q residual kernel and the host-NumPy paths.")
        ctx.emit("_GRAD_AT_QUAD_F = ti.field(dtype=ti.f64)         # (N_QP, N_NODES, DIM)")
        ctx.emit("_QUAD_WEIGHTS_F = ti.field(dtype=ti.f64)         # (N_QP,)")

    if _is_plastic_material(material_model):
        if _is_damage_material(material_model):
            ctx.emit("# History fields for plastic (and optionally damaged) constitutive model")
        else:
            ctx.emit("# History fields for J2 plasticity")
        ctx.emit(
            "alpha = ti.field(dtype=ti.f64)                    "
            "# accumulated plastic strain (n_elem x N_QP)"
        )
        # Committed (step-start) history mirror. The Newton driver snapshots the
        # committed history into these fields once per step and restores from
        # them each iteration via on-device copy_from (no host round-trip).
        # Populated at runtime by copy_from, so they need NO from_numpy fill.
        ctx.emit(
            "_alpha_committed = ti.field(dtype=ti.f64)         "
            "# committed alpha snapshot (n_elem x N_QP)"
        )
        if _is_damage_material(material_model):
            ctx.emit(
                "damage_D = ti.field(dtype=ti.f64)                 # scalar damage (n_elem x N_QP)"
            )
            ctx.emit(
                "is_deleted = ti.field(dtype=ti.i32)               "
                "# per-element deletion flag (n_elem,)"
            )
            ctx.emit(
                "_damage_D_committed = ti.field(dtype=ti.f64)      "
                "# committed damage snapshot (n_elem x N_QP)"
            )
            ctx.emit(
                "_is_deleted_committed = ti.field(dtype=ti.i32)    "
                "# committed deletion snapshot (n_elem,)"
            )

    ctx.emit("")
    ctx.emit("")
    ctx.emit("def allocate_fields(nn: int, ne: int) -> None:")
    with ctx.indent_block():
        ctx.emit('"""Allocate Taichi fields after mesh dimensions are known."""')
        ctx.emit("global n_nodes, n_elem")
        ctx.emit("n_nodes = nn")
        ctx.emit("n_elem = ne")
        ctx.emit(
            "ti.root.dense(ti.i, n_nodes).place(x_ref, x_cur, u, f_int, f_ext, residual, du, Kv)"
        )
        ctx.emit("ti.root.dense(ti.ij, (n_elem, N_NODES)).place(elem_nodes)")
        emits_matvec = _emits_generated_tangent_matvec(bundle)
        if emits_matvec:
            # Quadrature tables: mesh-independent, but placed +
            # filled here because allocate_fields() is guaranteed (by the seam
            # contract) to run after the caller's ti.init and before any kernel
            # launch — so the fill never races Taichi materialisation. The runtime-q
            # tangent matvec kernels read these device copies.
            ctx.emit("ti.root.dense(ti.ijk, (N_QP, N_NODES, DIM)).place(_GRAD_AT_QUAD_F)")
            ctx.emit("ti.root.dense(ti.i, N_QP).place(_QUAD_WEIGHTS_F)")
        if _is_plastic_material(material_model):
            ctx.emit("ti.root.dense(ti.ij, (n_elem, N_QP)).place(alpha)")
            # Committed-history mirror (same shape as alpha); filled at runtime
            # by copy_from in newton_solve, so no from_numpy fill is needed here.
            ctx.emit("ti.root.dense(ti.ij, (n_elem, N_QP)).place(_alpha_committed)")
        if _is_damage_material(material_model):
            ctx.emit("ti.root.dense(ti.ij, (n_elem, N_QP)).place(damage_D)")
            ctx.emit("ti.root.dense(ti.i, n_elem).place(is_deleted)")
            ctx.emit("ti.root.dense(ti.ij, (n_elem, N_QP)).place(_damage_D_committed)")
            ctx.emit("ti.root.dense(ti.i, n_elem).place(_is_deleted_committed)")
        if emits_matvec:
            # Fill the quad tables LAST: .from_numpy forces field materialisation, so
            # every field above must be placed first (else Taichi sees an unplaced
            # field — e.g. alpha — and raises). Values come from the kept Python-list
            # constants GRAD_AT_QUAD / QUAD_WEIGHTS.
            ctx.emit("_GRAD_AT_QUAD_F.from_numpy(np.asarray(GRAD_AT_QUAD, dtype=np.float64))")
            ctx.emit("_QUAD_WEIGHTS_F.from_numpy(np.asarray(QUAD_WEIGHTS, dtype=np.float64))")
    ctx.emit("")


def emit_constitutive_update(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit constitutive model function.

    For elastic SVK: S = lambda*tr(E)*I + 2*mu*E
    For J2 power-law plasticity: radial return with Newton iteration.
    """
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    material_params = bundle.problem_ir_dict.get("material", {}).get("params", {})

    # When the bundle carries a LaTeX-derived energy model, emit the
    # constitutive ``@ti.func`` from the derived PK2 stress (via the proven
    # energy_emitter path) instead of the hard-coded named-model switch. This
    # replaces the advisory-only LatexSemantics path: the derived energy now
    # reaches codegen through the real ProblemIR -> ArtifactBundle channel.
    # The named-model dispatch below stays the fallback for IRs built without
    # a derived energy (svk / j2_power_law / lemaitre), so their emission is
    # byte-identical.
    if bundle.derived_energy is not None:
        from mechdsl.symbolic.anisotropic_energy import AnisotropicEnergyModel
        from mechdsl.symbolic.spectral_energy import SpectralEnergyModel

        de = bundle.derived_energy
        params = _derived_params(bundle)

        ctx.emit("# " + "=" * 70)
        ctx.emit(f"# Constitutive model: {material_model} (derived from LaTeX energy)")
        ctx.emit("# " + "=" * 70)
        ctx.emit("")

        def _emit_block(src: str) -> None:
            for line in src.splitlines():
                ctx.emit(line)

        # The constitutive ``@ti.func`` shape depends on the derivation path. All
        # three force the signature to the unified derived-parameter vocabulary so
        # the ``constitutive_update(F, ...)`` call site in compute_internal_force
        # matches (a tangent-only parameter rides along as an unused argument).
        if isinstance(de, SpectralEnergyModel):
            # Ogden: emit the symmetric eigensolver once, then the spectral
            # constitutive func (device) + its host-NumPy twin for the FD tangent.
            from mechdsl.codegen.spectral_emitter import (
                SYM_EIG_3X3_SOURCE,
                emit_spectral_constitutive_func,
                emit_spectral_pk2_numpy_source,
            )

            _emit_block(SYM_EIG_3X3_SOURCE)
            ctx.emit("")
            _emit_block(emit_spectral_constitutive_func(de, param_names=params))
            ctx.emit("")
            _emit_block(emit_spectral_pk2_numpy_source(de, param_names=params))
        elif isinstance(de, AnisotropicEnergyModel):
            # HGO: emit the fiber-gated constitutive func (device, takes the
            # gathered fiber direction `a`) + its host-NumPy twin for the FD
            # tangent. The call site (compute_internal_force / tangent_matvec)
            # supplies `a` from the declared fiber family (_fiber_family0).
            from mechdsl.codegen.anisotropic_emitter import (
                emit_anisotropic_constitutive_func,
                emit_anisotropic_pk2_numpy_source,
            )

            _emit_block(emit_anisotropic_constitutive_func(de, param_names=params))
            ctx.emit("")
            _emit_block(emit_anisotropic_pk2_numpy_source(de, param_names=params))
        else:
            from mechdsl.codegen.energy_emitter import emit_constitutive_func

            _emit_block(emit_constitutive_func(de, param_names=params))
        ctx.emit("")
        return

    ctx.emit("# " + "=" * 70)
    ctx.emit(f"# Constitutive model: {material_model}")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")

    if material_model == "j2_power_law":
        _emit_j2_constitutive(ctx, material_params)
    elif material_model == "lemaitre":
        # Emit both the underlying J2 return map and the Lemaitre wrapper
        # that layers scalar damage (D) on top.  Keeping the J2 function
        # lets the D=0 path (test_d_zero_matches_j2_emission) reuse the
        # same inner Newton iteration.
        _emit_j2_constitutive(ctx, material_params)
        _emit_lemaitre_constitutive(ctx, material_params)
    else:
        _emit_svk_constitutive(ctx, material_params)


def _emit_svk_constitutive(ctx: EmissionContext, params: dict[str, object]) -> None:
    """Emit St. Venant-Kirchhoff constitutive update.

    S_{IJ} = lambda * tr(E) * delta_{IJ} + 2 * mu * E_{IJ}
    where E = 0.5 * (C - I), C = F^T F.
    """
    ctx.emit("@ti.func")
    ctx.emit("def constitutive_update(F: ti.types.matrix(3, 3, ti.f64),")
    ctx.emit("                        lam: ti.f64, mu: ti.f64")
    ctx.emit("                        ) -> ti.types.matrix(3, 3, ti.f64):")
    with ctx.indent_block():
        ctx.emit('"""SVK constitutive model: S = lam*tr(E)*I + 2*mu*E."""')
        ctx.emit("# Right Cauchy-Green tensor C = F^T @ F")
        ctx.emit("C = F.transpose() @ F")
        ctx.emit("# Green-Lagrange strain E = 0.5*(C - I)")
        ctx.emit("I3 = ti.Matrix.identity(ti.f64, 3)")
        ctx.emit("E = 0.5 * (C - I3)")
        ctx.emit("# Trace of E (physics index sum -- ti.static range)")
        ctx.emit("tr_E = ti.f64(0.0)")
        ctx.emit("for i in ti.static(range(3)):")
        with ctx.indent_block():
            ctx.emit("tr_E += E[i, i]")
        ctx.emit("# 2nd Piola-Kirchhoff stress: S = lam*tr(E)*I + 2*mu*E")
        ctx.emit("S = lam * tr_E * I3 + 2.0 * mu * E")
        ctx.emit("return S")
    ctx.emit("")


def _emit_j2_constitutive(ctx: EmissionContext, params: dict[str, object]) -> None:
    """Emit J2 power-law plasticity constitutive update with radial return.

    Emits a complete ``@ti.func`` that performs:

    1. Kinematics: C = F^T F, E = 0.5*(C - I)
    2. Elastic trial stress: S_trial = lam*tr(E)*I + 2*mu*E
    3. Deviatoric/volumetric split
    4. Von Mises equivalent stress with near-zero guard
    5. Yield check: f_trial = sigma_eq - sigma_y(alpha_old)
    6. Plastic corrector: radial return Newton iteration for delta_lambda
    7. Stress and alpha update

    The function returns (S, alpha_new) so the caller can write back
    the updated hardening variable.
    """
    ctx.emit("@ti.func")
    ctx.emit("def constitutive_update_plastic(")
    ctx.emit("    F: ti.types.matrix(3, 3, ti.f64),")
    ctx.emit("    lam: ti.f64, mu: ti.f64,")
    ctx.emit("    sigma_y0: ti.f64, K_hard: ti.f64, n_hard: ti.f64,")
    ctx.emit("    alpha_old: ti.f64,")
    ctx.emit("):")
    with ctx.indent_block():
        ctx.emit('"""J2 power-law plasticity: radial return with Newton iteration.')
        ctx.emit("")
        ctx.emit("Returns (S, alpha_new) -- updated 2nd Piola-Kirchhoff stress")
        ctx.emit("and accumulated plastic strain.")
        ctx.emit('"""')
        ctx.emit("# 1. Kinematics: right Cauchy-Green and Green-Lagrange strain")
        ctx.emit("C = F.transpose() @ F")
        ctx.emit("I3 = ti.Matrix.identity(ti.f64, 3)")
        ctx.emit("E = 0.5 * (C - I3)")
        ctx.emit("")
        ctx.emit("# 2. Elastic trial stress")
        ctx.emit("tr_E = ti.f64(0.0)")
        ctx.emit("for i in ti.static(range(3)):")
        with ctx.indent_block():
            ctx.emit("tr_E += E[i, i]")
        ctx.emit("S_trial = lam * tr_E * I3 + 2.0 * mu * E")
        ctx.emit("")
        ctx.emit("# 3. Deviatoric / volumetric split")
        ctx.emit("tr_S = S_trial[0, 0] + S_trial[1, 1] + S_trial[2, 2]")
        ctx.emit("S_dev = S_trial - (tr_S / 3.0) * I3")
        ctx.emit("")
        ctx.emit("# 4. Von Mises equivalent stress")
        ctx.emit("s_sq = ti.f64(0.0)")
        ctx.emit("for i in ti.static(range(3)):")
        with ctx.indent_block():
            ctx.emit("for j in ti.static(range(3)):")
            with ctx.indent_block():
                ctx.emit("s_sq += S_dev[i, j] * S_dev[i, j]")
        ctx.emit("sigma_eq = ti.sqrt(1.5 * s_sq)")
        ctx.emit("")
        ctx.emit("# 5. Yield check")
        ctx.emit("sigma_y = sigma_y0 + K_hard * ti.pow(alpha_old, n_hard)")
        ctx.emit("alpha_new = alpha_old")
        ctx.emit("S = S_trial")
        ctx.emit("")
        ctx.emit("if sigma_eq > 1e-12 * sigma_y and sigma_eq > sigma_y:")
        with ctx.indent_block():
            ctx.emit("# 6. Radial return: Newton iteration for delta_lambda")
            ctx.emit("dl = ti.f64(0.0)")
            ctx.emit("# Stress-scaled tolerance: f has units of stress (MPa), so an")
            ctx.emit("# absolute tol is unreachable at steel-scale sigma. Mirrors the")
            ctx.emit("# reference radial_return (j2_power_law.py) with tol=1e-12.")
            ctx.emit("stress_ref = ti.max(ti.max(ti.abs(sigma_eq), sigma_y), 1.0)")
            ctx.emit("effective_tol = ti.max(1e-12, 1e-12 * stress_ref)")
            ctx.emit("converged = 0")
            ctx.emit("for _it in range(20):")
            with ctx.indent_block():
                ctx.emit("alpha_trial = alpha_old + dl")
                ctx.emit("sy = sigma_y0 + K_hard * ti.pow(alpha_trial, n_hard)")
                ctx.emit("f = sigma_eq - 3.0 * mu * dl - sy")
                ctx.emit("if ti.abs(f) < effective_tol:  # tol per 07-CONVENTIONS.md §6")
                with ctx.indent_block():
                    ctx.emit("converged = 1")
                    ctx.emit("break")
                ctx.emit(
                    "H_prime = K_hard * n_hard * ti.pow(alpha_trial, n_hard - 1.0) "
                    "if alpha_trial > 1e-12 else 0.0"
                )
                ctx.emit("df = -3.0 * mu - H_prime")
                ctx.emit("dl -= f / df")
            ctx.emit("")
            ctx.emit("# Guard: flag ANY non-convergence of the return-map Newton loop.")
            ctx.emit("# COUPLING: the converged flag is set by the in-loop check, which")
            ctx.emit("# keys off effective_tol (change one -> revisit the other). Using an")
            ctx.emit("# explicit flag (vs a post-loop residual-magnitude test) closes the")
            ctx.emit("# band gap where a result in (effective_tol, 1e3*effective_tol] would")
            ctx.emit("# be silently accepted; the reference raises on loop exhaustion.")
            ctx.emit("if converged == 0:")
            with ctx.indent_block():
                ctx.emit("# Non-converged: set NaN flag (propagates to Newton driver)")
                ctx.emit("dl = ti.f64(float('nan'))")
            ctx.emit("else:")
            with ctx.indent_block():
                ctx.emit("# Converged: clamp dl >= 0 (negative plastic multiplier is")
                ctx.emit("# non-physical). Gated under else: so the NaN sentinel on the")
                ctx.emit("# non-converged branch survives -- a GPU fmax(NaN, 0.0) -> 0.0")
                ctx.emit("# would erase it and let Newton silently accept a return map")
                ctx.emit("# that never converged.")
                ctx.emit("dl = ti.max(dl, 0.0)")
            ctx.emit("")
            ctx.emit("# 7. Update stress and hardening variable")
            ctx.emit("factor = 1.0 - 3.0 * mu * dl / sigma_eq")
            ctx.emit("S_vol = (tr_S / 3.0) * I3")
            ctx.emit("S = S_vol + factor * S_dev")
            ctx.emit("alpha_new = alpha_old + dl")
        ctx.emit("")
        ctx.emit("return S, alpha_new")
    ctx.emit("")


def _emit_lemaitre_constitutive(ctx: EmissionContext, params: dict[str, object]) -> None:
    """Emit Lemaitre damage-coupled J2 power-law constitutive update.

    Plan B phase B6, task P6-2.  Wraps :func:`_emit_j2_constitutive`'s
    ``constitutive_update_plastic`` (which implements the undamaged radial
    return on the elastic predictor — i.e. the effective-stress field by
    strain equivalence).  After the J2 step the wrapper evaluates the de
    Souza Neto triaxiality factor, the elastic energy release rate, and
    advances damage with

        dD = (Y / S_d)^{s_d} * delta_lambda      (if alpha_new > eps_D)

    then forms the nominal PK2 stress  ``sigma_nominal = (1 - D_new) * sigma_eff``.

    The returned ``alpha_new`` and ``D_new`` are written back by the caller.
    Caveat (Gate B medium, P6-1 forward-warning): the tangent used by
    ``tangent_matvec`` is the **undamaged J2** algorithmic tangent, not a
    damage-aware consistent tangent.  Under actively evolving damage Newton
    drops from super-linear to sub-linear convergence; this is acceptable
    for P6-2/P6-3 because the notched bar runs quasi-statically with small
    D increments per step.  A damage-aware tangent is a Phase 10 V&V item.
    """
    ctx.emit("@ti.func")
    ctx.emit("def constitutive_update_lemaitre(")
    ctx.emit("    F: ti.types.matrix(3, 3, ti.f64),")
    ctx.emit("    lam: ti.f64, mu: ti.f64,")
    ctx.emit("    sigma_y0: ti.f64, K_hard: ti.f64, n_hard: ti.f64,")
    ctx.emit("    S_d: ti.f64, s_d_exp: ti.f64, eps_D: ti.f64,")
    ctx.emit("    E_mod: ti.f64, nu_poisson: ti.f64,")
    ctx.emit("    alpha_old: ti.f64, D_old: ti.f64,")
    ctx.emit("):")
    with ctx.indent_block():
        ctx.emit('"""Lemaitre damage coupled to J2 power-law (strain equivalence).')
        ctx.emit("")
        ctx.emit("Returns (S_nominal, alpha_new, D_new).")
        ctx.emit('"""')
        ctx.emit("# --- 1. Effective-stress J2 radial return ---")
        ctx.emit("# sigma_eff IS the J2 result because the elastic predictor uses")
        ctx.emit("# the undamaged stiffness (strain-equivalence assumption).")
        ctx.emit(
            "S_eff, alpha_new = constitutive_update_plastic("
            "F, lam, mu, sigma_y0, K_hard, n_hard, alpha_old)"
        )
        ctx.emit("")
        ctx.emit("# delta_lambda recovered from alpha history (J2 has alpha_new = alpha_old + dl)")
        ctx.emit("delta_lambda = alpha_new - alpha_old")
        ctx.emit("")
        ctx.emit("# --- 2. Effective von Mises and triaxiality ---")
        ctx.emit("tr_Seff = S_eff[0, 0] + S_eff[1, 1] + S_eff[2, 2]")
        ctx.emit("sigma_H = tr_Seff / 3.0")
        ctx.emit("I3 = ti.Matrix.identity(ti.f64, 3)")
        ctx.emit("S_eff_dev = S_eff - sigma_H * I3")
        ctx.emit("s_sq = ti.f64(0.0)")
        ctx.emit("for i in ti.static(range(3)):")
        with ctx.indent_block():
            ctx.emit("for j in ti.static(range(3)):")
            with ctx.indent_block():
                ctx.emit("s_sq += S_eff_dev[i, j] * S_eff_dev[i, j]")
        ctx.emit("sigma_eq = ti.sqrt(1.5 * s_sq)")
        ctx.emit("")
        ctx.emit("# Triaxiality factor R_v = 2/3(1+nu) + 3(1-2nu)*(sigma_H/sigma_eq)^2")
        ctx.emit("base_Rv = 2.0 / 3.0 * (1.0 + nu_poisson)")
        ctx.emit("R_v = base_Rv")
        ctx.emit("if sigma_eq > 1e-30:")
        with ctx.indent_block():
            ctx.emit("tr_ratio = sigma_H / sigma_eq")
            ctx.emit("R_v = base_Rv + 3.0 * (1.0 - 2.0 * nu_poisson) * tr_ratio * tr_ratio")
        ctx.emit("")
        ctx.emit("# --- 3. Energy release rate Y = sigma_eq^2 * R_v / (2 E (1 - D)^2) ---")
        ctx.emit("one_minus_D = 1.0 - D_old")
        ctx.emit("if one_minus_D <= 0.0:")
        with ctx.indent_block():
            # D_MAX = 1 - 1e-6; guard against singularity
            ctx.emit("one_minus_D = 1.0e-6")
        ctx.emit("Y_rel = ti.f64(0.0)")
        ctx.emit("if sigma_eq > 0.0:")
        with ctx.indent_block():
            ctx.emit(
                "Y_rel = sigma_eq * sigma_eq * R_v / (2.0 * E_mod * one_minus_D * one_minus_D)"
            )
        ctx.emit("")
        ctx.emit("# --- 4. Damage evolution (rate-independent, step-based) ---")
        ctx.emit("D_new = D_old")
        ctx.emit("if delta_lambda > 0.0 and alpha_new > eps_D and Y_rel > 0.0:")
        with ctx.indent_block():
            ctx.emit("dD = ti.pow(Y_rel / S_d, s_d_exp) * delta_lambda")
            ctx.emit("D_new = D_old + dD")
        ctx.emit("")
        ctx.emit("# --- 5. Clamp D_new to [0, 1 - 1e-6] ---")
        ctx.emit("if D_new > 0.999999:")
        with ctx.indent_block():
            ctx.emit("D_new = 0.999999")
        ctx.emit("if D_new < 0.0:")
        with ctx.indent_block():
            ctx.emit("D_new = 0.0")
        ctx.emit("")
        ctx.emit("# --- 6. Nominal stress: sigma_nominal = (1 - D_new) * sigma_eff ---")
        ctx.emit("S_nominal = (1.0 - D_new) * S_eff")
        ctx.emit("")
        ctx.emit("return S_nominal, alpha_new, D_new")
    ctx.emit("")


def _emit_ul_force_qp_inner(ctx: EmissionContext, material_model: str) -> None:
    """Emit the Updated Lagrangian QP-inner body for the internal force kernel.

    Plan B B1.1 -- integrates the Cauchy stress over the current (deformed)
    configuration using spatial shape gradients and det(j):

        f_int[a, i] += w_q * detj * sigma_{ij} * dN_a/dx_j

    where sigma = (1/J) * F @ S @ F^T (push-forward from PK2 to Cauchy).

    This helper is called from ``emit_internal_force_kernel`` when the
    bundle's configuration is ``"current"`` (Updated Lagrangian). The caller
    has already emitted the parametric shape gradient gather (dN_dxi); this
    helper picks up from there and emits the full UL QP body at the current
    indent level.

    The constitutive branch dispatches on *material_model*: ``"j2_power_law"``
    → J2 radial return; ``"lemaitre"`` → damage-coupled radial return with
    ``alpha`` and ``damage_D`` writeback; anything else → SVK.
    """
    is_plastic = _is_plastic_material(material_model)
    is_damage = _is_damage_material(material_model)
    ctx.emit("# --- Updated Lagrangian QP body (Plan B B1.1) ---")
    ctx.emit("")
    ctx.emit("# Current Jacobian j = x_elem^T @ dN/dxi  (3x3)")
    ctx.emit("j = x_elem.transpose() @ dN_dxi")
    ctx.emit("detj = j.determinant()")
    ctx.emit("# UL element inversion guard: detj depends on current iterate")
    ctx.emit("# (unlike TL detJ0, validated upfront by validate_mesh).")
    ctx.emit("# Negative detj = fold-over: poison residual for Newton detection.")
    ctx.emit("if detj < 0.0:")
    with ctx.indent_block():
        ctx.emit("for a_err in range(N_NODES):")
        with ctx.indent_block():
            ctx.emit("nid_err = elem_nodes[e, a_err]")
            ctx.emit("for i_err in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("f_int[nid_err][i_err] += 1.0e300")
    ctx.emit("elif detj > 1e-15:")
    with ctx.indent_block():
        ctx.emit("j_inv = j.inverse()")
        ctx.emit("")
        ctx.emit("# Spatial shape gradients dN/dx = dN/dxi @ j^{-1}  (N_NODES x DIM)")
        ctx.emit("dNdx = dN_dxi @ j_inv")
        ctx.emit("")
        ctx.emit("# Reference Jacobian (needed for deformation gradient F)")
        ctx.emit("J0 = X_elem.transpose() @ dN_dxi")
        ctx.emit("J0_inv = J0.inverse()")
        ctx.emit("dNdX = dN_dxi @ J0_inv")
        ctx.emit("")
        ctx.emit("# Deformation gradient F = I + grad_u")
        ctx.emit("# grad_u_{iI} = sum_a u_{ai} * dN_a/dX_I")
        ctx.emit("F = ti.Matrix.identity(ti.f64, DIM)")
        ctx.emit("for a in range(N_NODES):")
        with ctx.indent_block():
            ctx.emit("nid = elem_nodes[e, a]")
            ctx.emit("for i in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("for I in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("F[i, I] += u[nid][i] * dNdX[a, I]")
        ctx.emit("")

        if is_damage:
            ctx.emit(
                "# Constitutive update (Lemaitre damage + J2): read alpha & D, compute, write back"
            )
            ctx.emit("alpha_old = alpha[e, q]")
            ctx.emit("D_old = damage_D[e, q]")
            ctx.emit(
                "S, alpha_new, D_new = constitutive_update_lemaitre("
                "F, lam, mu, sigma_y0, K_hard, n_hard, "
                "S_d_val, s_d_val, eps_D_val, E_mod_val, nu_val, "
                "alpha_old, D_old)"
            )
            ctx.emit("alpha[e, q] = alpha_new")
            ctx.emit("damage_D[e, q] = D_new")
        elif is_plastic:
            ctx.emit("# Constitutive update (J2 plasticity): read alpha, compute, write back")
            ctx.emit("alpha_old = alpha[e, q]")
            ctx.emit(
                "S, alpha_new = constitutive_update_plastic("
                "F, lam, mu, sigma_y0, K_hard, n_hard, alpha_old)"
            )
            ctx.emit("alpha[e, q] = alpha_new")
        else:
            ctx.emit("# Constitutive update: S = constitutive_update(F, lam, mu)")
            ctx.emit("S = constitutive_update(F, lam, mu)")

        ctx.emit("")
        ctx.emit("# Push-forward PK2 -> Cauchy: sigma = (1/J) F @ S @ F^T")
        ctx.emit("J = F.determinant()")
        ctx.emit("sigma = (1.0 / J) * F @ S @ F.transpose()")
        ctx.emit("")
        ctx.emit("# Integrate internal force (UL): f_a_i += w_q * detj * sigma_{ij} * dNdx_{aj}")
        ctx.emit("w_q = QUAD_WEIGHTS[q]")
        ctx.emit("for a in range(N_NODES):")
        with ctx.indent_block():
            ctx.emit("nid = elem_nodes[e, a]")
            ctx.emit("force_a = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)")
            ctx.emit("for i in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("val = ti.f64(0.0)")
                ctx.emit("for j in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("val += sigma[i, j] * dNdx[a, j]")
                ctx.emit("force_a[i] = val")
            ctx.emit("for i in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("f_int[nid][i] += w_q * detj * force_a[i]")


def emit_internal_force_kernel(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit internal force computation kernel.

    Dispatches between Total Lagrangian (TL, reference configuration) and
    Updated Lagrangian (UL, current configuration) based on the ``configuration``
    field in the artifact bundle's ``problem_ir_dict``.

    **TL (default, Plan A):**

        f_int[a, i] += w_q * detJ0 * P_{iI} * dN_a/dX_I

    where P = F @ S (1st Piola-Kirchhoff stress).

    **UL (Plan B B1.1):**

        f_int[a, i] += w_q * detj * sigma_{ij} * dN_a/dx_j

    where sigma = (1/J) * F @ S @ F^T (Cauchy, push-forward from PK2).

    For J2 plasticity the kernel reads ``alpha[e, q]`` before the
    constitutive call and writes ``alpha_new`` back afterwards.

    Physics index loops (i, j, I, J over range 3) use ti.static.
    Mesh index loops (elements, quadrature points, nodes) use runtime loops.
    """
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    is_plastic = _is_plastic_material(material_model)
    is_damage = _is_damage_material(material_model)
    configuration = bundle.problem_ir_dict.get("configuration", "reference")
    derived = _derived_params(bundle)
    if derived is not None and configuration == "current":
        raise NotImplementedError(
            "LaTeX-derived constitutive models are only wired for Total Lagrangian "
            "(reference configuration); Updated Lagrangian push-forward of a derived "
            "tangent is planned for a later phase."
        )

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Internal force kernel")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")

    # Document the element-deletion contract so downstream readers
    # know the generated residual shape mutates across Newton steps only
    # by dropping elements (never by bringing them back).
    if is_damage:
        ctx.emit("# NOTE (P6-2, Plan B phase B6): element deletion is one-way.  Once")
        ctx.emit("# ``is_deleted[e] != 0`` the element contributes zero to both the")
        ctx.emit("# internal force and the tangent matvec.  The residual-norm sum")
        ctx.emit("# therefore ranges only over active DOFs; Newton's convergence")
        ctx.emit("# tolerances are unaffected because deleted-element residual rows")
        ctx.emit("# are already zeroed here.  Tangent uses the undamaged J2 tangent")
        ctx.emit("# (see P6-1 forward-warning, Option A).")
        ctx.emit("")

    if is_damage:
        ctx.emit("@ti.kernel")
        ctx.emit("def compute_internal_force(lam: ti.f64, mu: ti.f64,")
        ctx.emit("                           sigma_y0: ti.f64, K_hard: ti.f64,")
        ctx.emit("                           n_hard: ti.f64,")
        ctx.emit("                           S_d_val: ti.f64, s_d_val: ti.f64,")
        ctx.emit("                           eps_D_val: ti.f64,")
        ctx.emit("                           E_mod_val: ti.f64, nu_val: ti.f64,")
        ctx.emit("                           D_crit: ti.f64):")
    elif is_plastic:
        ctx.emit("@ti.kernel")
        ctx.emit("def compute_internal_force(lam: ti.f64, mu: ti.f64,")
        ctx.emit("                           sigma_y0: ti.f64, K_hard: ti.f64,")
        ctx.emit("                           n_hard: ti.f64):")
    elif derived is not None:
        ctx.emit("@ti.kernel")
        sig = ", ".join(f"{name}: ti.f64" for name in derived)
        ctx.emit(f"def compute_internal_force({sig}):")
    else:
        ctx.emit("@ti.kernel")
        ctx.emit("def compute_internal_force(lam: ti.f64, mu: ti.f64):")

    with ctx.indent_block():
        ctx.emit('"""Compute internal force vector over all elements."""')
        ctx.emit("# Zero internal force")
        ctx.emit("for i in range(n_nodes):")
        with ctx.indent_block():
            ctx.emit("f_int[i] = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)")
        ctx.emit("")
        ctx.emit("# Loop over elements (runtime -- mesh index)")
        ctx.emit("for e in range(n_elem):")
        with ctx.indent_block():
            if is_damage:
                ctx.emit("# P6-2 element deletion: skip elements flagged as failed")
                ctx.emit("if is_deleted[e] != 0:")
                with ctx.indent_block():
                    ctx.emit("continue")
                ctx.emit("")
            ctx.emit("# Gather element nodal coordinates (reference and current)")
            ctx.emit("X_elem = ti.Matrix.zero(ti.f64, N_NODES, DIM)")
            ctx.emit("x_elem = ti.Matrix.zero(ti.f64, N_NODES, DIM)")
            ctx.emit("for a in range(N_NODES):")
            with ctx.indent_block():
                ctx.emit("nid = elem_nodes[e, a]")
                ctx.emit("for d in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("X_elem[a, d] = x_ref[nid][d]")
                    ctx.emit("x_elem[a, d] = x_ref[nid][d] + u[nid][d]")
            ctx.emit("")
            ctx.emit("# Quadrature loop (ti.static -- N_QP=8 is element-type constant,")
            ctx.emit("#   enables Python list access for GRAD_AT_QUAD and QUAD_WEIGHTS)")
            ctx.emit("for q in ti.static(range(N_QP)):")
            with ctx.indent_block():
                ctx.emit("# Shape function gradients in parametric space")
                ctx.emit("dN_dxi = ti.Matrix.zero(ti.f64, N_NODES, DIM)")
                ctx.emit("for a in ti.static(range(N_NODES)):")
                with ctx.indent_block():
                    ctx.emit("for d in ti.static(range(DIM)):")
                    with ctx.indent_block():
                        ctx.emit("dN_dxi[a, d] = GRAD_AT_QUAD[q][a][d]")
                ctx.emit("")

                # ----- Configuration dispatch -----
                # Python-time branch: emits EITHER the TL body (P = F@S,
                # detJ0) or the UL body (sigma = F@S@F.T/J, detj).
                # The generated source file contains only ONE path.
                if configuration == "current":
                    _emit_ul_force_qp_inner(ctx, material_model)
                else:
                    # === TL body (reference configuration) ===
                    ctx.emit("# Reference Jacobian J0 = X^T @ dN/dxi  (3x3)")
                    ctx.emit("J0 = X_elem.transpose() @ dN_dxi")
                    ctx.emit("detJ0 = J0.determinant()")
                    ctx.emit(
                        "# Guard: degenerate element (07-CONVENTIONS.md"
                        " \u00a76) -- skip QP if detJ0 <= 1e-15"
                    )
                    ctx.emit("if detJ0 > 1e-15:")
                    with ctx.indent_block():
                        ctx.emit("J0_inv = J0.inverse()")
                        ctx.emit("")
                        ctx.emit("# dN/dX = dN/dxi @ J0^{-1}  (N_NODES x DIM)")
                        ctx.emit("dNdX = dN_dxi @ J0_inv")
                        ctx.emit("")
                        # Family-emitter dispatch for DISPLACEMENT_GRADIENT.
                        # Emits the F = I + grad_u scatter ('qaI,ai->qiI').
                        # When the feature flag is OFF we fall through to the
                        # legacy inline body below (byte-identical output).
                        if not _dispatch_family(Family.DISPLACEMENT_GRADIENT, ctx):
                            ctx.emit("# Deformation gradient F = I + grad_u")
                            ctx.emit("# grad_u_{iI} = sum_a u_{ai} * dN_a/dX_I")
                            ctx.emit("F = ti.Matrix.identity(ti.f64, DIM)")
                            ctx.emit("for a in range(N_NODES):")
                            with ctx.indent_block():
                                ctx.emit("nid = elem_nodes[e, a]")
                                ctx.emit("for i in ti.static(range(DIM)):")
                                with ctx.indent_block():
                                    ctx.emit("for I in ti.static(range(DIM)):")
                                    with ctx.indent_block():
                                        ctx.emit("F[i, I] += u[nid][i] * dNdX[a, I]")
                        ctx.emit("")

                        if is_damage:
                            ctx.emit(
                                "# Constitutive update (Lemaitre damage + J2):"
                                " read alpha & D, compute, write back"
                            )
                            ctx.emit("alpha_old = alpha[e, q]")
                            ctx.emit("D_old = damage_D[e, q]")
                            ctx.emit(
                                "S, alpha_new, D_new = constitutive_update_lemaitre("
                                "F, lam, mu, sigma_y0, K_hard, n_hard, "
                                "S_d_val, s_d_val, eps_D_val, E_mod_val, nu_val, "
                                "alpha_old, D_old)"
                            )
                            ctx.emit("alpha[e, q] = alpha_new")
                            ctx.emit("damage_D[e, q] = D_new")
                        elif is_plastic:
                            ctx.emit(
                                "# Constitutive update (J2 plasticity):"
                                " read alpha, compute, write back"
                            )
                            ctx.emit("alpha_old = alpha[e, q]")
                            ctx.emit(
                                "S, alpha_new = constitutive_update_plastic("
                                "F, lam, mu, sigma_y0, K_hard, n_hard, alpha_old)"
                            )
                            ctx.emit("alpha[e, q] = alpha_new")
                        elif derived is not None:
                            fiber = _fiber_family0(bundle)
                            if fiber is not None:
                                # Anisotropic (HGO): the constitutive func takes
                                # the per-element fiber direction. Supply it from
                                # the declared family (element-constant in the MVP).
                                a0, a1, a2 = fiber
                                ctx.emit(
                                    f"a_fiber = ti.Vector([{a0!r}, {a1!r}, {a2!r}])"
                                    "  # fiber direction (family 0)"
                                )
                                call_args = ", ".join(["F", "a_fiber", *derived])
                            else:
                                call_args = ", ".join(["F", *derived])
                            ctx.emit(f"# Constitutive update: S = constitutive_update({call_args})")
                            ctx.emit(f"S = constitutive_update({call_args})")
                        else:
                            ctx.emit("# Constitutive update: S = constitutive_update(F, lam, mu)")
                            ctx.emit("S = constitutive_update(F, lam, mu)")

                        ctx.emit("")
                        ctx.emit("# 1st Piola-Kirchhoff stress P = F @ S")
                        ctx.emit("P = F @ S")
                        ctx.emit("")
                        # Family-emitter dispatch for FORCE_INTEGRATION
                        # (einsum 'qaI,qiI->qai'). Legacy inline body below
                        # is the fallback when the flag is off.
                        if not _dispatch_family(Family.FORCE_INTEGRATION, ctx):
                            ctx.emit(
                                "# Integrate internal force: "
                                "f_a_i += w_q * detJ0 * P_{iI} * dNdX_{aI}"
                            )
                            ctx.emit("w_q = QUAD_WEIGHTS[q]")
                            ctx.emit("for a in range(N_NODES):")
                            with ctx.indent_block():
                                ctx.emit("nid = elem_nodes[e, a]")
                                ctx.emit("force_a = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)")
                                ctx.emit("for i in ti.static(range(DIM)):")
                                with ctx.indent_block():
                                    ctx.emit("val = ti.f64(0.0)")
                                    ctx.emit("for I in ti.static(range(DIM)):")
                                    with ctx.indent_block():
                                        ctx.emit("val += P[i, I] * dNdX[a, I]")
                                    ctx.emit("force_a[i] = val")
                                ctx.emit("for i in ti.static(range(DIM)):")
                                with ctx.indent_block():
                                    ctx.emit("f_int[nid][i] += w_q * detJ0 * force_a[i]")

            # --- End of QP loop: damage may have advanced; check deletion ---
            if is_damage:
                ctx.emit("")
                ctx.emit("# P6-2: flag element as deleted if any QP breaches D_crit.")
                ctx.emit("# One-way: once set, stays set (see module docstring note).")
                ctx.emit("elem_failed = 0")
                ctx.emit("for q_chk in ti.static(range(N_QP)):")
                with ctx.indent_block():
                    ctx.emit("if damage_D[e, q_chk] > D_crit:")
                    with ctx.indent_block():
                        ctx.emit("elem_failed = 1")
                ctx.emit("if elem_failed != 0:")
                with ctx.indent_block():
                    ctx.emit("is_deleted[e] = 1")
                    ctx.emit("# Zero the contributions this element just scattered")
                    ctx.emit("# so the next force norm reflects the deletion directly.")
                    ctx.emit("# Contributions land on nodes shared with live elements,")
                    ctx.emit("# so we cannot zero them here without breaking neighbours.")
                    ctx.emit("# The next compute_internal_force() call already skips this")
                    ctx.emit("# element via the is_deleted guard at the element-loop head.")
    ctx.emit("")


def _emit_tl_tangent_qp_body(
    ctx: EmissionContext,
    is_plastic: bool,
    derived_lines: list[str] | None = None,
) -> None:
    """Emit the Total Lagrangian QP-inner body for the tangent matvec.

    Factored out of ``emit_tangent_matvec_kernel`` by P1-4 to enable TL/UL
    dispatch. ``derived_lines`` (when given) replaces the SVK/J2 material branch
    with the LaTeX-derived stress + ``dS = C_IJKL : dE`` lines from
    :func:`energy_emitter.emit_derived_tangent_matvec_body`, so a derived bundle
    linearises about its own tangent instead of the SVK closed form.
    """
    ctx.emit("J0 = X_elem.T @ dN_dxi")
    ctx.emit("detJ0 = float(np.linalg.det(J0))")
    ctx.emit("if detJ0 <= 1e-15:")
    with ctx.indent_block():
        ctx.emit("# Mirrors the runtime guard in compute_internal_force.")
        ctx.emit("continue")
    ctx.emit("dN_dX = dN_dxi @ np.linalg.inv(J0)")
    ctx.emit("")
    ctx.emit("# Current kinematics at this quadrature point.")
    ctx.emit("grad_u = u_elem.T @ dN_dX")
    ctx.emit("F = I3 + grad_u")
    ctx.emit("E = 0.5 * (F.T @ F - I3)")
    ctx.emit("")
    ctx.emit("# Linearised strain in direction v.")
    ctx.emit("grad_v = v_elem.T @ dN_dX")
    ctx.emit("dE = 0.5 * (F.T @ grad_v + grad_v.T @ F)")
    ctx.emit("")

    # A LaTeX-derived bundle linearises about its own rank-4 tangent: emit the
    # derived PK2 stress and dS = C_IJKL : dE (host NumPy), skipping both the
    # family dispatch and the SVK/J2 closed form.
    if derived_lines is not None:
        for line in derived_lines:
            ctx.emit(line)
    # Family-emitter dispatch for MATERIAL_TANGENT_CONTRACTION
    # (einsum 'qaI,qiIjJ,qbJ->qaibj' — collapsed for SVK into the short
    # closed form). Legacy inline body below is the fallback.
    elif not _dispatch_family(Family.MATERIAL_TANGENT_CONTRACTION, ctx, is_plastic):
        if is_plastic:
            ctx.emit("# J2 algorithmic consistent tangent: re-run the return map")
            ctx.emit("# with the stored alpha.  The result supplies both the")
            ctx.emit("# current PK2 stress and the 4th-order tangent C_ep.")
            ctx.emit("rm = radial_return(_j2_mat, E, float(alpha_np[e, q]))")
            ctx.emit("S = rm.stress")
            ctx.emit("dS = np.einsum('ijkl,kl->ij', rm.tangent, dE)")
        else:
            ctx.emit("# SVK PK2 stress: S = lambda tr(E) I + 2 mu E.")
            ctx.emit("tr_E = float(np.trace(E))")
            ctx.emit("S = lam * tr_E * I3 + 2.0 * mu * E")
            ctx.emit("")
            ctx.emit("# SVK material tangent C is constant; the contraction C : dE")
            ctx.emit("# collapses to the same closed form as the stress update.")
            ctx.emit("tr_dE = float(np.trace(dE))")
            ctx.emit("dS = lam * tr_dE * I3 + 2.0 * mu * dE")

    ctx.emit("")
    ctx.emit("# dP = (geometric term) + (material term)")
    ctx.emit("dP = grad_v @ S + F @ dS")
    ctx.emit("")
    ctx.emit("Kv_e += w_q * detJ0 * (dN_dX @ dP.T)")


def _emit_ul_tangent_qp_body(ctx: EmissionContext, is_plastic: bool) -> None:
    """Emit the Updated Lagrangian QP-inner body for the tangent matvec.

    Plan B B1.2 -- the linearised UL tangent has two terms::

        (Kv)_{ai} = w_q * detj * (dNdx @ dsigma_mat.T + dNdx @ G_geo)

    where::

        dsigma_mat_{ij} = c^tau_{ijkl} * grad_v_{kl}   (Truesdell material term)
        G_geo_{ji}       = sigma_{jl} * grad_v_{il}     (geometric stiffness)

    The Truesdell spatial tangent ``c^tau`` is the Piola push-forward of the
    Lagrangian material tangent ``C_IJKL``, via
    :func:`mechdsl.symbolic.objective_rates.truesdell_tangent`.
    """
    ctx.emit("# --- Updated Lagrangian tangent QP body (Plan B B1.2) ---")
    ctx.emit("")
    ctx.emit("# Reference Jacobian (needed for deformation gradient F)")
    ctx.emit("J0 = X_elem.T @ dN_dxi")
    ctx.emit("detJ0 = float(np.linalg.det(J0))")
    ctx.emit("if detJ0 <= 1e-15:")
    with ctx.indent_block():
        ctx.emit("continue")
    ctx.emit("dN_dX = dN_dxi @ np.linalg.inv(J0)")
    ctx.emit("")
    ctx.emit("# Current Jacobian (UL: integrate over deformed configuration)")
    ctx.emit("j_cur = x_elem.T @ dN_dxi")
    ctx.emit("detj = float(np.linalg.det(j_cur))")
    ctx.emit("if detj < 0.0:")
    with ctx.indent_block():
        ctx.emit(
            "raise ValueError("
            'f"UL element inversion at element {e}, QP {q}: '
            'detj={detj:.3e}. Newton step too large.")'
        )
    ctx.emit("if detj <= 1e-15:")
    with ctx.indent_block():
        ctx.emit("continue")
    ctx.emit("dNdx = dN_dxi @ np.linalg.inv(j_cur)")
    ctx.emit("")
    ctx.emit("# Current kinematics at this quadrature point.")
    ctx.emit("grad_u = u_elem.T @ dN_dX")
    ctx.emit("F = I3 + grad_u")
    ctx.emit("E = 0.5 * (F.T @ F - I3)")
    ctx.emit("")

    if is_plastic:
        ctx.emit("# J2 algorithmic consistent tangent: re-run the return map")
        ctx.emit("rm = radial_return(_j2_mat, E, float(alpha_np[e, q]))")
        ctx.emit("S = rm.stress")
        ctx.emit("C4_mat = rm.tangent")
    else:
        ctx.emit("# SVK PK2 stress: S = lambda tr(E) I + 2 mu E.")
        ctx.emit("tr_E = float(np.trace(E))")
        ctx.emit("S = lam * tr_E * I3 + 2.0 * mu * E")

    ctx.emit("")
    ctx.emit("# Push-forward PK2 -> Cauchy: sigma = (1/J) F @ S @ F^T")
    ctx.emit("J_det = detj / detJ0")
    ctx.emit("sigma = (1.0 / J_det) * F @ S @ F.T")
    ctx.emit("")
    ctx.emit("# Truesdell spatial tangent: Piola push-forward of C_IJKL")
    if is_plastic:
        ctx.emit("c_tau = truesdell_tangent(C4_mat, sigma, F)")
    else:
        ctx.emit("c_tau = truesdell_tangent(C4_svk, sigma, F)")
    ctx.emit("")
    ctx.emit("# Spatial gradient of v (using dN/dx, not dN/dX)")
    ctx.emit("grad_v = v_elem.T @ dNdx")
    ctx.emit("")
    # Family-emitter dispatch for TANGENT_DOUBLE_CONTRACTION
    # (einsum 'ijkl,kl->ij'). Legacy inline body below is the fallback.
    if not _dispatch_family(Family.TANGENT_DOUBLE_CONTRACTION, ctx):
        ctx.emit("# Material term: dsigma_mat_{ij} = c^tau_{ijkl} * grad_v_{kl}")
        ctx.emit("dsigma_mat = np.einsum('ijkl,kl->ij', c_tau, grad_v)")
    ctx.emit("")
    ctx.emit("# Geometric (initial-stress) stiffness: G_{ji} = sigma_{jl} * grad_v_{il}")
    ctx.emit("G_geo = sigma @ grad_v.T")
    ctx.emit("")
    ctx.emit("Kv_e += w_q * detj * (dNdx @ dsigma_mat.T + dNdx @ G_geo)")


def emit_tangent_matvec_kernel(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit tangent stiffness matrix-free matvec function.

    Implements PLAN-A §A7.5 (SVK push-forward) and §A9.2 (J2 algorithmic
    consistent tangent).  The emitted ``tangent_matvec`` function computes
    ``K(u) @ v`` exactly (up to floating-point round-off) via
    element-by-element linearisation of the internal force::

        K_e @ v_e = sum_q  w_q * detJ0 *
                    (dN/dX) @ dP^T

    where at each quadrature point::

        grad_u = u_e^T @ dN/dX              (current displacement gradient)
        F      = I + grad_u                 (deformation gradient)
        E      = 0.5 (F^T F - I)            (Green-Lagrange strain)
        S      = PK2 stress (SVK or J2)
        grad_v = v_e^T @ dN/dX              (direction gradient)
        dE     = 0.5 (F^T grad_v + grad_v^T F)  (linearised strain)
        dS     = C : dE                      (linearised stress, material part)
        dP     = grad_v @ S + F @ dS         (linearised PK1 — material + geometric)

    For **SVK** the material tangent C_IJKL is constant
    (C_IJKL = lambda delta_IJ delta_KL + mu (delta_IK delta_JL + delta_IL delta_JK)),
    so the contraction C:dE collapses to ``lam*tr(dE)*I + 2*mu*dE`` — no
    fourth-order array is constructed in the hot loop.

    For **J2 plasticity** the consistent algorithmic tangent C_ep is
    state-dependent.  It is obtained per quadrature point by re-running
    :func:`mechdsl.symbolic.models.j2_power_law.radial_return` with the
    current strain E and the stored ``alpha[e, q]`` (which holds the
    converged equivalent plastic strain from the most recent residual
    evaluation, consistent with Simo & Hughes §3.4 Box 3.5).  The return
    map itself is a no-op when the local stress state is elastic, so
    elastic quadrature points pay only a dozen extra floating-point
    operations relative to the pure-SVK path.

    Relative to the earlier finite-difference implementation this costs
    **one** internal-force evaluation per matvec (the FD central-difference
    path cost two) and restores **quadratic Newton convergence** for both
    elastic and plastic problems.

    Implementation notes
    --------------------
    - The function is a plain Python/NumPy routine, not a ``@ti.kernel``,
      mirroring the FD baseline's pattern.  The element loop is serial
      NumPy; Taichi fields are read once via ``.to_numpy()`` at function
      entry.  This keeps the generated file compact and avoids growing a
      second JIT-compiled tangent kernel on top of ``compute_internal_force``.
    - For J2 the return map is invoked through an import of
      :func:`mechdsl.symbolic.models.j2_power_law.radial_return`.  This
      mirrors the existing pattern of importing ``CGSolver`` from
      ``mechdsl.solver.import_adapter`` inside the Newton driver —
      generated code depends on the shipped ``mechdsl`` package at
      runtime rather than being fully hermetic.

    Index convention
    ----------------
    Physics indices (spatial i,j,k,l; material I,J,K,L) are handled by
    NumPy tensor operations (range = 3 each).  Mesh indices (elements,
    quadrature points, nodes) are Python ``range`` loops.
    """
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    is_plastic = _is_plastic_material(material_model)
    is_damage = _is_damage_material(material_model)
    configuration = bundle.problem_ir_dict.get("configuration", "reference")
    derived = _derived_params(bundle)

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Tangent matvec (analytical consistent tangent)")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")

    if is_plastic:
        ctx.emit("def tangent_matvec(v_flat: np.ndarray, lam: float, mu: float,")
        ctx.emit("                   sigma_y0: float, K_hard: float,")
        ctx.emit("                   n_hard: float) -> np.ndarray:")
    elif derived is not None:
        sig = ", ".join(f"{name}: float" for name in derived)
        ctx.emit(f"def tangent_matvec(v_flat: np.ndarray, {sig}) -> np.ndarray:")
    else:
        ctx.emit("def tangent_matvec(v_flat: np.ndarray, lam: float, mu: float) -> np.ndarray:")

    with ctx.indent_block():
        ctx.emit('"""Matrix-free tangent matvec: K(u) @ v via analytical linearisation.')
        ctx.emit("")
        ctx.emit("Parameters")
        ctx.emit("----------")
        ctx.emit("v_flat : np.ndarray, shape (n_nodes * 3,)")
        ctx.emit("    Direction vector.")
        if derived is not None:
            ctx.emit(f"{', '.join(derived)} : float")
            ctx.emit("    Material parameters of the LaTeX-derived strain energy.")
        else:
            ctx.emit("lam, mu : float")
            ctx.emit("    Lame parameters.")
        if is_plastic:
            ctx.emit("sigma_y0, K_hard, n_hard : float")
            ctx.emit("    J2 plasticity parameters (used to reconstruct the")
            ctx.emit("    algorithmic consistent tangent per quadrature point).")
        if is_damage:
            ctx.emit("")
            ctx.emit("Notes")
            ctx.emit("-----")
            ctx.emit("Lemaitre path (P6-2) uses the **undamaged J2** algorithmic tangent.")
            ctx.emit("A damage-aware consistent tangent is a Phase 10 V&V item — see the")
            ctx.emit("P6-1 forward-warning at ``symbolic/models/lemaitre.py:244-252``.")
            ctx.emit("Under actively evolving damage Newton drops from super-linear to")
            ctx.emit("sub-linear convergence; acceptable for quasi-static notched-bar runs.")
            ctx.emit("Deleted elements (``is_deleted[e] != 0``) contribute zero to K @ v.")
        ctx.emit("")
        ctx.emit("Returns")
        ctx.emit("-------")
        ctx.emit("np.ndarray, shape (n_nodes * 3,)")
        ctx.emit("    Exact tangent-vector product K @ v.")
        ctx.emit('"""')

        if is_plastic:
            ctx.emit("from mechdsl.symbolic.models.j2_power_law import (")
            ctx.emit("    J2PowerLawMaterial,")
            ctx.emit("    radial_return,")
            ctx.emit(")")
            ctx.emit("")
            ctx.emit("# Reconstruct the material object used by the symbolic return map.")
            ctx.emit("# The J2 material dataclass takes (E, nu) rather than (lam, mu);")
            ctx.emit("# recover them algebraically.")
            ctx.emit("_E = mu * (3.0 * lam + 2.0 * mu) / (lam + mu)")
            ctx.emit("_nu = lam / (2.0 * (lam + mu))")
            ctx.emit(
                "_j2_mat = J2PowerLawMaterial(E=_E, nu=_nu, sigma_y0=sigma_y0, K=K_hard, n=n_hard)"
            )
            ctx.emit("")

        if configuration == "current":
            ctx.emit("from mechdsl.symbolic.objective_rates import truesdell_tangent")
            ctx.emit("")

        ctx.emit("v = v_flat.reshape((-1, 3))")
        ctx.emit("Kv = np.zeros_like(v)")
        ctx.emit("")
        ctx.emit("# Snapshot Taichi fields into NumPy for the serial element loop.")
        ctx.emit("u_np = u.to_numpy()")
        ctx.emit("coords_np = x_ref.to_numpy()")
        ctx.emit("conn_np = elem_nodes.to_numpy()")

        if is_plastic:
            ctx.emit("alpha_np = alpha.to_numpy()")

        if is_damage:
            ctx.emit("is_deleted_np = is_deleted.to_numpy()")

        ctx.emit("")
        ctx.emit("I3 = np.eye(3, dtype=np.float64)")
        ctx.emit(
            "grad_at_quad_np = np.asarray(GRAD_AT_QUAD, dtype=np.float64)  # (N_QP, N_NODES, DIM)"
        )
        ctx.emit("")

        if configuration == "current" and not is_plastic:
            ctx.emit("# 4th-order SVK material tangent (constant, built once)")
            ctx.emit("C4_svk = lam * np.einsum('ij,kl->ijkl', I3, I3) + mu * (")
            ctx.emit("    np.einsum('ik,jl->ijkl', I3, I3) + np.einsum('il,jk->ijkl', I3, I3))")
            ctx.emit("")

        ctx.emit("for e in range(n_elem):")
        with ctx.indent_block():
            if is_damage:
                ctx.emit("# P6-2: deleted elements contribute zero to the tangent matvec")
                ctx.emit("if is_deleted_np[e] != 0:")
                with ctx.indent_block():
                    ctx.emit("continue")
            ctx.emit("nodes = conn_np[e]")
            ctx.emit("u_elem = u_np[nodes]")
            ctx.emit("X_elem = coords_np[nodes]")
            ctx.emit("v_elem = v[nodes]")
            if configuration == "current":
                ctx.emit("x_elem = X_elem + u_elem  # current coordinates")
            ctx.emit("Kv_e = np.zeros((N_NODES, DIM), dtype=np.float64)")
            ctx.emit("")
            ctx.emit("for q in range(N_QP):")
            with ctx.indent_block():
                ctx.emit("dN_dxi = grad_at_quad_np[q]  # (N_NODES, DIM)")
                ctx.emit("w_q = QUAD_WEIGHTS[q]")
                ctx.emit("")

                if configuration == "current":
                    _emit_ul_tangent_qp_body(ctx, is_plastic)
                else:
                    derived_lines: list[str] | None = None
                    if derived is not None:
                        from mechdsl.symbolic.anisotropic_energy import AnisotropicEnergyModel
                        from mechdsl.symbolic.spectral_energy import SpectralEnergyModel

                        de = bundle.derived_energy
                        assert de is not None  # implied by `derived`
                        # Spectral / fiber models linearise about a
                        # central-difference FD tangent (no stable closed form);
                        # the invariant path uses its symbolic rank-4 C : dE.
                        if isinstance(de, SpectralEnergyModel):
                            from mechdsl.codegen.spectral_emitter import (
                                emit_spectral_tangent_matvec_body,
                            )

                            derived_lines = emit_spectral_tangent_matvec_body(
                                de, param_names=derived
                            )
                        elif isinstance(de, AnisotropicEnergyModel):
                            from mechdsl.codegen.anisotropic_emitter import (
                                emit_anisotropic_tangent_matvec_body,
                            )

                            fiber = _fiber_family0(bundle)
                            assert fiber is not None  # HGO problems always declare a fiber
                            fa0, fa1, fa2 = fiber
                            derived_lines = [
                                f"a_fiber = np.array([{fa0!r}, {fa1!r}, {fa2!r}], dtype=np.float64)"
                                "  # fiber direction (family 0)",
                                *emit_anisotropic_tangent_matvec_body(de, param_names=derived),
                            ]
                        else:
                            from mechdsl.codegen.energy_emitter import (
                                emit_derived_tangent_matvec_body,
                            )

                            derived_lines = emit_derived_tangent_matvec_body(de)
                    _emit_tl_tangent_qp_body(ctx, is_plastic, derived_lines)
            ctx.emit("")
            ctx.emit("# Scatter element contribution to global tangent-vector product.")
            ctx.emit("for a in range(N_NODES):")
            with ctx.indent_block():
                ctx.emit("Kv[nodes[a]] += Kv_e[a]")
        ctx.emit("")
        ctx.emit("return Kv.ravel()")
    ctx.emit("")


# ---------------------------------------------------------------------------
# Generated @ti.kernel matrix-free SVK tangent operator
#
# The function above (``emit_tangent_matvec_kernel``) emits a host-NumPy
# ``tangent_matvec`` consumed by the imported ``CGSolver`` in the emitted
# Newton driver. This section adds — *alongside* it, not replacing it — a
# generated ``@ti.kernel`` that applies the SVK tangent ``K(u)·v`` **fully
# matrix-free** (never store element tangents), routing the tangent
# contraction through the einsum optimiser (``ContractionPlan``) and
# calling the Tier-1 ``ti_runtime`` ``@ti.func`` helpers. The kernel
# targets the ``ti_runtime`` ``apply_A(out, x)`` seam so a generated
# PCG / Newton driver can inject it.
#
# Why alongside, not in place: the host ``tangent_matvec`` name, its
# closed-form ``dS = lam*tr(dE)*I + 2*mu*dE`` body, and the
# ``def tangent_matvec(`` signature are pinned by the printer/codegen tests
# and the ``*.py.golden`` snapshots, and the host function is wired into
# the emitted Newton driver's ``CGSolver`` call. A wholesale swap would
# cascade through every e2e/golden/J2/UL path, so the generated
# ``@ti.kernel`` SVK route ships with <1e-10 parity + JIT-budget gates
# while the host route stays the default.
#
# The A-formation. The contraction ``qaI,qiIjJ,qbJ,bj->qai`` applies the
# consistent **two-point** tangent ``A(i,I,j,J)`` such that
# ``dP_{iI} = A_{iIjJ} (∂v_j/∂X_J)``. For SVK that A (matching
# ``dP = grad_v·S + F·(C:dE)``) collapses to the closed form, per
# quadrature point,
#
#     A_{iIjJ} = δ_{ij} S_{JI}                (geometric / initial-stress)
#              + λ F_{iI} F_{jJ}
#              + μ (F F^T)_{ij} δ_{IJ}
#              + μ F_{iJ} F_{jI}              (material, F·(C:dE))
#
# (the constant SVK ``C_{KLMN} = λ δ_{KL}δ_{MN} + μ(δ_{KM}δ_{LN}+δ_{KN}δ_{LM})``
# is folded analytically, so no rank-4 array is built in the hot loop). Verified
# to machine precision vs ``tests/ref/ref_hex8_elastic.element_tangent_matvec``.
# ---------------------------------------------------------------------------


def _emit_svk_consistent_tangent_A(ctx: EmissionContext) -> None:
    """Emit the per-QP consistent two-point SVK tangent ``A[i,I,j,J]``.

    Forms the rank-4 array ``A`` (a 9×9 ``ti.Matrix`` flattened on the
    ``(i,I)`` × ``(j,J)`` pairs) from the in-scope ``F`` (deformation
    gradient) and ``S`` (PK2 stress). The SVK material tangent ``C`` is the
    constant closed form, so the contraction ``F·(C:dE)`` collapses to the
    closed form ``λ F_{iI}F_{jJ} + μ (FF^T)_{ij}δ_{IJ} + μ F_{iJ}F_{jI}`` — no
    fourth-order ``C`` array is materialised. All four indices are physics
    indices (range 3) and therefore ``ti.static``-unrolled per 07-CONVENTIONS;
    81 cells × a handful of terms keeps the assembly comfortably inside the
    ``@ti.kernel`` budget.

    Assumes ``lam`` / ``mu`` and the 3×3 ``F`` / ``S`` matrices are already
    in scope. Emits ``A`` as a ``ti.Matrix`` of shape (9, 9) with row index
    ``i*DIM + I`` and column index ``j*DIM + J`` so the optimiser-path
    contraction below can index it as ``A[i*DIM + I, j*DIM + J]``.
    """
    ctx.emit("# Consistent two-point SVK tangent A[i,I,j,J] such that")
    ctx.emit("#   dP_{iI} = A_{iIjJ} * grad_v_{jJ}   (grad_v_{jJ} = sum_b v_{bj} dNdX_{bJ}).")
    ctx.emit("# SVK closed form (no rank-4 C array; C:dE collapses analytically):")
    ctx.emit("#   A_{iIjJ} = delta_{ij} S_{JI}        (geometric / initial stress)")
    ctx.emit("#            + lam F_{iI} F_{jJ}")
    ctx.emit("#            + mu (F F^T)_{ij} delta_{IJ}")
    ctx.emit("#            + mu F_{iJ} F_{jI}          (material, F.(C:dE))")
    ctx.emit("# Stored 9x9 on the (i,I)x(j,J) pairs (row i*DIM+I, col j*DIM+J).")
    ctx.emit("FFt = F @ F.transpose()")
    ctx.emit("A = ti.Matrix.zero(ti.f64, DIM * DIM, DIM * DIM)")
    ctx.emit("for i in ti.static(range(DIM)):")
    with ctx.indent_block():
        ctx.emit("for I in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("for j in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("for J in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("# material: lam F_{iI} F_{jJ} + mu F_{iJ} F_{jI}")
                    ctx.emit("a_iIjJ = lam * F[i, I] * F[j, J] + mu * F[i, J] * F[j, I]")
                    ctx.emit("# geometric: delta_{ij} S_{JI}")
                    ctx.emit("if i == j:")
                    with ctx.indent_block():
                        ctx.emit("a_iIjJ += S[J, I]")
                    ctx.emit("# material: mu (F F^T)_{ij} delta_{IJ}")
                    ctx.emit("if I == J:")
                    with ctx.indent_block():
                        ctx.emit("a_iIjJ += mu * FFt[i, j]")
                    ctx.emit("A[i * DIM + I, j * DIM + J] = a_iIjJ")


def _emit_optimised_matvec_contraction(ctx: EmissionContext, plan: ContractionPlan) -> None:
    """Emit the P3-1 optimiser-recorded matvec contraction as ``ti.static`` loops.

    The matrix-free tangent contraction is ``qaI,qiIjJ,qbJ,bj->qai`` with the
    operand order ``(dN, A, dN, v)``. We do **not** hand-roll a contraction
    order: we consume ``plan.contraction_path`` (the opt_einsum path produced
    by Layer-4b for this exact einsum) and realise the recorded pairwise steps.
    For the SVK Hex8 matvec opt_einsum records the path
    ``[(2, 3), (1, 2), (0, 1)]``, i.e. the three steps

        step 1:  bj, qbJ -> jqJ        (grad_v_{jJ} = sum_b v_{bj} dNdX_{bJ})
        step 2:  jqJ, qiIjJ -> qiI     (dP_{iI}    = grad_v_{jJ} A_{iIjJ})
        step 3:  qiI, qaI -> qai       (Kv_{ai}    = dP_{iI} dNdX_{aI})

    each emitted here as ``ti.static`` physics-index loops (i,I,j,J range 3)
    with the node dummies ``b``/``a`` (range 8) as runtime gathers. The quad
    index ``q`` is the kernel's enclosing ``ti.static`` quadrature loop, so it
    is fixed in this block (the recorded ``q`` axis is a no-op per call). This
    keeps the contraction optimiser-derived rather than hand-written, while
    fitting the JIT budget (203 estimated lines, Tier 2).

    Guard: P3-2's MVP path assumes the canonical 3-step SVK Hex8 path. If a
    future ElementIR yields a different path the emitter fails loud rather than
    silently emitting a mismatched contraction.
    """
    expected_path = [(2, 3), (1, 2), (0, 1)]
    if list(plan.contraction_path) != expected_path:
        raise NotImplementedError(
            "P3-2 generated matrix-free SVK tangent expects the canonical "
            f"opt_einsum path {expected_path} for '{plan.einsum_string}', got "
            f"{plan.contraction_path}. A path-generic emitter is planned for a "
            "later phase (multi-element support); for the Hex8 SVK MVP the "
            "optimiser is deterministic, so this guard should never trip."
        )

    ctx.emit(f"# Optimiser-recorded contraction path {list(plan.contraction_path)} for")
    ctx.emit(f"#   {plan.einsum_string}   operands (dNdX, A, dNdX, v).")
    ctx.emit("# Realised as the three recorded pairwise steps; physics indices")
    ctx.emit("# (i, I, j, J in range DIM) are ti.static, node dummies (a, b) runtime.")
    ctx.emit("")
    # Step 1: grad_v_{jJ} = sum_b v_{bj} dNdX_{bJ}  (path step (2, 3): v ⊗ dN over b)
    ctx.emit("# step 1  (path (2, 3)):  bj, qbJ -> jJ    grad_v_{jJ}")
    ctx.emit("grad_v = ti.Matrix.zero(ti.f64, DIM, DIM)")
    ctx.emit("for b in range(N_NODES):")
    with ctx.indent_block():
        ctx.emit("nid_b = elem_nodes[e, b]")
        ctx.emit("for j in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("for J in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("grad_v[j, J] += v[nid_b][j] * dNdX[b, J]")
    ctx.emit("")
    # Step 2: dP_{iI} = sum_{jJ} grad_v_{jJ} A_{iIjJ}  (path step (1, 2))
    ctx.emit("# step 2  (path (1, 2)):  jJ, iIjJ -> iI    dP_{iI} = A_{iIjJ} grad_v_{jJ}")
    ctx.emit("dP = ti.Matrix.zero(ti.f64, DIM, DIM)")
    ctx.emit("for i in ti.static(range(DIM)):")
    with ctx.indent_block():
        ctx.emit("for I in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("acc = ti.f64(0.0)")
            ctx.emit("for j in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("for J in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("acc += A[i * DIM + I, j * DIM + J] * grad_v[j, J]")
            ctx.emit("dP[i, I] = acc")
    ctx.emit("")
    # Step 3: Kv_{ai} = sum_I dP_{iI} dNdX_{aI}  (path step (0, 1)), scattered to nodes
    ctx.emit("# step 3  (path (0, 1)):  iI, aI -> ai    Kv_{ai} = dP_{iI} dNdX_{aI}")
    ctx.emit("# scattered to global nodes with the quadrature weight (atomic add).")
    ctx.emit("for a in range(N_NODES):")
    with ctx.indent_block():
        ctx.emit("nid_a = elem_nodes[e, a]")
        ctx.emit("for i in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("kv_ai = ti.f64(0.0)")
            ctx.emit("for I in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("kv_ai += dP[i, I] * dNdX[a, I]")
            ctx.emit("out[nid_a][i] += w_q * detJ0 * kv_ai")


def emit_svk_tangent_matvec_kernel(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit the generated ``@ti.kernel`` matrix-free SVK tangent operator (P3-2).

    Emits ``svk_tangent_matvec_apply(out, v, lam, mu)`` — a ``@ti.kernel``
    that applies ``K(u)·v`` fully matrix-free over all elements. It recomputes
    the tangent per matvec (locked decision D-A; element tangents are never
    stored), forms the consistent two-point SVK tangent ``A(i,I,j,J)`` per
    quadrature point from the Tier-1 ``ti_runtime`` kinematics helpers, and
    applies it to ``v`` via the **P3-1 optimiser-recorded contraction path**
    (consumed from :func:`build_tangent_matvec_plan`). The result scatters to
    the global ``out`` field via atomic add, targeting the ``ti_runtime``
    ``apply_A(out, x)`` injection seam.

    Only emitted for the SVK / Total-Lagrangian / reference / named-model path
    (see :func:`emit`). J2's algorithmic tangent (P5-1), the LaTeX-derived
    tangent, and the Updated-Lagrangian push-forward stay on the host
    ``tangent_matvec`` route for now.

    The kernel reads the live displacement field ``u`` (so it always reflects
    the current Newton iterate) and the mesh fields ``x_ref`` / ``elem_nodes``
    declared by :func:`emit_field_declarations`; ``out`` and ``v`` are
    ``ti.template()`` vector fields supplied by the caller (the seam binding).
    """
    from mechdsl.ir.element_ir import create_hex8_element_ir
    from mechdsl.lowering.einsum_extract import build_tangent_matvec_plan

    # Route the tangent contraction through the einsum optimiser: this is
    # the ContractionPlan (opt_einsum path + JIT-budget-checked tier), not a
    # hand-rolled einsum. The path drives the loop structure emitted below.
    element_ir = create_hex8_element_ir(formulation="total_lagrangian", configuration="reference")
    plan = build_tangent_matvec_plan(element_ir)

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Generated matrix-free SVK tangent @ti.kernel (PlanJune14 P3-2)")
    ctx.emit("#")
    ctx.emit("# Applies K(u)·v fully matrix-free (D-A: element tangents never stored),")
    ctx.emit("# recomputed per matvec. The tangent contraction rides the P3-1")
    ctx.emit(
        f"# opt_einsum ContractionPlan ('{plan.einsum_string}', path {list(plan.contraction_path)},"
    )
    ctx.emit(f"# tier {plan.tier}). Kinematics use the Tier-1 ti_runtime @ti.func")
    ctx.emit("# helpers; the kernel targets the ti_runtime apply_A(out, x) seam.")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("from ti_runtime import tensor_ti as _tt")
    ctx.emit("")
    ctx.emit("")
    ctx.emit("@ti.kernel")
    ctx.emit("def svk_tangent_matvec_apply(")
    ctx.emit("    out: ti.template(),")
    ctx.emit("    v: ti.template(),")
    ctx.emit("    lam: ti.f64,")
    ctx.emit("    mu: ti.f64,")
    ctx.emit("):")
    with ctx.indent_block():
        ctx.emit('"""Matrix-free SVK tangent: out = K(u) · v, recomputed per call.')
        ctx.emit("")
        ctx.emit("D-A (06-CODEGEN §3.3): no element stiffness is ever formed or stored.")
        ctx.emit("``out`` is zeroed here, then element contributions are scattered via")
        ctx.emit("Taichi's implicit atomic add. ``u`` (current Newton iterate) and the")
        ctx.emit("mesh fields ``x_ref`` / ``elem_nodes`` are read live.")
        ctx.emit("")
        ctx.emit("The tangent contraction is the P3-1 opt_einsum ContractionPlan for")
        ctx.emit(f"``{plan.einsum_string}`` (operands dNdX, A, dNdX, v), realised as the")
        ctx.emit(f"recorded path {list(plan.contraction_path)} (tier {plan.tier}, within")
        ctx.emit("the 512-line @ti.func JIT budget).")
        ctx.emit('"""')
        ctx.emit("# Zero the output field (mesh loop — runtime).")
        ctx.emit("for n in range(n_nodes):")
        with ctx.indent_block():
            ctx.emit("out[n] = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)")
        ctx.emit("")
        ctx.emit("# Loop over elements (runtime — mesh index).")
        ctx.emit("for e in range(n_elem):")
        with ctx.indent_block():
            ctx.emit("# Gather element reference coordinates.")
            ctx.emit("X_elem = ti.Matrix.zero(ti.f64, N_NODES, DIM)")
            ctx.emit("for a in range(N_NODES):")
            with ctx.indent_block():
                ctx.emit("nid = elem_nodes[e, a]")
                ctx.emit("for d in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("X_elem[a, d] = x_ref[nid][d]")
            ctx.emit("")
            ctx.emit("# Quadrature loop (RUNTIME — PlanJune14 WI-1 JIT-budget lever).")
            ctx.emit("# Runtime q divides the per-QP unroll by N_QP (8); physics indices")
            ctx.emit("# i,I,j,J,a,d stay ti.static. The body can no longer index the")
            ctx.emit("# Python-list quad constants by a runtime q, so it reads the")
            ctx.emit("# device-resident _GRAD_AT_QUAD_F / _QUAD_WEIGHTS_F filled in")
            ctx.emit("# allocate_fields() (codegen.md: runtime-q is convention-clean once")
            ctx.emit("# the body no longer indexes Python-list constants).")
            ctx.emit("for q in range(N_QP):")
            with ctx.indent_block():
                ctx.emit("w_q = _QUAD_WEIGHTS_F[q]")
                ctx.emit("# Parametric shape gradients dN/dxi at this quad point.")
                ctx.emit("dN_dxi = ti.Matrix.zero(ti.f64, N_NODES, DIM)")
                ctx.emit("for a in ti.static(range(N_NODES)):")
                with ctx.indent_block():
                    ctx.emit("for d in ti.static(range(DIM)):")
                    with ctx.indent_block():
                        ctx.emit("dN_dxi[a, d] = _GRAD_AT_QUAD_F[q, a, d]")
                ctx.emit("")
                ctx.emit("# Reference Jacobian J0 = X^T @ dN/dxi and dNdX = dN/dxi @ J0^{-1}.")
                ctx.emit("J0 = X_elem.transpose() @ dN_dxi")
                ctx.emit("detJ0 = _tt.det3(J0)")
                ctx.emit("# Degenerate-element guard (07-CONVENTIONS §6).")
                ctx.emit("if detJ0 > 1e-15:")
                with ctx.indent_block():
                    ctx.emit("dNdX = dN_dxi @ _tt.inv3(J0)")
                    ctx.emit("")
                    ctx.emit("# Material displacement gradient grad_u = sum_a u_a (x) dNdX_a.")
                    ctx.emit("grad_u = ti.Matrix.zero(ti.f64, DIM, DIM)")
                    ctx.emit("for a in range(N_NODES):")
                    with ctx.indent_block():
                        ctx.emit("nid = elem_nodes[e, a]")
                        ctx.emit("for i in ti.static(range(DIM)):")
                        with ctx.indent_block():
                            ctx.emit("for I in ti.static(range(DIM)):")
                            with ctx.indent_block():
                                ctx.emit("grad_u[i, I] += u[nid][i] * dNdX[a, I]")
                    ctx.emit("")
                    ctx.emit("# Kinematics + PK2 (SVK) via Tier-1 ti_runtime helpers.")
                    ctx.emit("F = _tt.deformation_gradient(grad_u)")
                    ctx.emit("E = _tt.green_lagrange(F)")
                    ctx.emit("S = lam * _tt.trace3(E) * _tt.identity3() + 2.0 * mu * E")
                    ctx.emit("")
                    _emit_svk_consistent_tangent_A(ctx)
                    ctx.emit("")
                    _emit_optimised_matvec_contraction(ctx, plan)
    ctx.emit("")


# ---------------------------------------------------------------------------
# PlanJune14 P5-1 — generated @ti.kernel matrix-free J2 algorithmic tangent
#
# The dissipative-model counterpart of ``emit_svk_tangent_matvec_kernel``
# (P3-2). J2 plasticity is dissipative, so the tangent is the **algorithmic
# consistent tangent** — the linearisation of the radial-return map, NOT
# ∂²Ψ/∂E² (``.claude/rules/symbolic.md``). It is state-dependent: every matvec
# re-runs the return map per quadrature point with the **on-device** history
# field ``alpha[e, q]`` (read-only — the matvec never advances history) to
# recover the current PK2 stress ``S`` and the rank-4 algorithmic tangent
# ``C_ep``.
#
# The two-point tangent ``A(i,I,j,J)`` reuses the SVK structure (geometric +
# material) but folds the J2 ``C_ep`` instead of the SVK closed form:
#
#     A_{iIjJ} = δ_{ij} S_{JI}                    (geometric / initial stress)
#              + sum_{K,M} F_{iK} C_ep_{KIMJ} F_{jM}   (material, F·(C_ep:dE))
#
# (matching ``ref_hex8_plastic.element_tangent_matvec_plastic``:
# ``dP = grad_v @ S + F @ (C_ep : dE)`` with ``dE = sym(F^T grad_v)``). Once
# ``A`` is formed the matvec rides the **same** P3-1 opt_einsum ContractionPlan
# (``qaI,qiIjJ,qbJ,bj->qai``) realised by ``_emit_optimised_matvec_contraction``
# — the contraction is path-driven and JIT-budget-checked exactly as for SVK
# (Tier 2, ~203 lines, primary PJ risk). The on-device ``C_ep`` assembly uses
# the closed Simo & Hughes §3.4 Box 3.5 form, byte-for-byte the algebra of
# ``j2_power_law.assemble_j2_like_tangent`` / ``elastic_tangent``, so the
# generated operator matches the reference algorithmic tangent to f64 precision.
# ---------------------------------------------------------------------------


def _emit_j2_algorithmic_tangent_C(ctx: EmissionContext) -> None:
    """Emit the on-device J2 PK2 stress ``S`` and algorithmic tangent ``C_ep``.

    Recomputes the radial-return map from the in-scope deformation gradient
    ``F``, Green-Lagrange strain ``E``, the stored history ``alpha_old``, and
    the material parameters ``lam`` / ``mu`` / ``sigma_y0`` / ``K_hard`` /
    ``n_hard``. Assigns two names into the kernel scope:

    * ``S``    — current PK2 stress (3×3 ``ti.Matrix``), and
    * ``C_ep`` — the rank-4 algorithmic consistent tangent stored as a 9×9
      ``ti.Matrix`` flattened on the ``(K,I)`` × ``(M,J)`` index pairs
      (row ``K*DIM + I``, column ``M*DIM + J``).

    The tangent is the **algorithmic** consistent tangent (linearisation of the
    return map), per the dissipative-model rule — NOT ∂²Ψ/∂E². The elastic
    branch returns the isotropic elastic tangent
    ``C_IJKL = λ δ_IJ δ_KL + μ(δ_IK δ_JL + δ_IL δ_JK)``; the plastic branch
    returns the Simo & Hughes Box 3.5 form

        C_ep = κ (I⊗I) + 2μθ P_dev + (9μ²dl/q − 9μ²/(3μ+H')) (n⊗n)

    with κ = λ + 2μ/3, θ = 1 − 3μ dl/q, q = σ_eq^trial, n = S_dev^trial/q,
    H' = K n_hard alpha_new^(n_hard−1). All indices are physics indices
    (range 3) → ``ti.static`` per 07-CONVENTIONS; the return-map Newton loop
    mirrors ``_emit_j2_constitutive`` (same tol/guards, 07-CONVENTIONS §6).
    """
    ctx.emit("# J2 algorithmic consistent tangent (dissipative model — this is the")
    ctx.emit("# linearisation of the radial-return map, NOT d2Psi/dE2). Recomputed")
    ctx.emit("# per matvec from the on-device history alpha[e, q] (read-only here).")
    ctx.emit("I3 = _tt.identity3()")
    ctx.emit("# Elastic trial PK2 stress S_trial = lam tr(E) I + 2 mu E.")
    ctx.emit("tr_E = _tt.trace3(E)")
    ctx.emit("S_trial = lam * tr_E * I3 + 2.0 * mu * E")
    ctx.emit("# Deviatoric / volumetric split.")
    ctx.emit("tr_S = _tt.trace3(S_trial)")
    ctx.emit("S_vol = (tr_S / 3.0) * I3")
    ctx.emit("S_dev_trial = S_trial - S_vol")
    ctx.emit("# von Mises equivalent trial stress.")
    ctx.emit("s_sq = ti.f64(0.0)")
    ctx.emit("for i in ti.static(range(DIM)):")
    with ctx.indent_block():
        ctx.emit("for j in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("s_sq += S_dev_trial[i, j] * S_dev_trial[i, j]")
    ctx.emit("sigma_eq = ti.sqrt(1.5 * s_sq)")
    ctx.emit("")
    ctx.emit("# Yield check against the stored hardening state.")
    ctx.emit("sigma_y = sigma_y0 + K_hard * ti.pow(alpha_old, n_hard)")
    ctx.emit("# Defaults: elastic step keeps the trial stress and the elastic tangent.")
    ctx.emit("S = S_trial")
    ctx.emit("dl = ti.f64(0.0)")
    ctx.emit("is_plastic = 0")
    ctx.emit("# Near-zero deviatoric guard (07-CONVENTIONS §6) folds into the yield test.")
    ctx.emit("if sigma_eq > 1e-12 * sigma_y and sigma_eq > sigma_y:")
    with ctx.indent_block():
        ctx.emit("is_plastic = 1")
        ctx.emit("# Radial return: Newton iteration for the plastic multiplier dl.")
        ctx.emit("# Stress-scaled tolerance: f has units of stress (MPa), so an")
        ctx.emit("# absolute tol is unreachable at steel-scale sigma. Mirrors the")
        ctx.emit("# reference radial_return (j2_power_law.py) with tol=1e-12.")
        ctx.emit("stress_ref = ti.max(ti.max(ti.abs(sigma_eq), sigma_y), 1.0)")
        ctx.emit("effective_tol = ti.max(1e-12, 1e-12 * stress_ref)")
        ctx.emit("converged = 0")
        ctx.emit("for _it in range(20):")
        with ctx.indent_block():
            ctx.emit("alpha_trial = alpha_old + dl")
            ctx.emit("sy = sigma_y0 + K_hard * ti.pow(alpha_trial, n_hard)")
            ctx.emit("f = sigma_eq - 3.0 * mu * dl - sy")
            ctx.emit("if ti.abs(f) < effective_tol:  # tol per 07-CONVENTIONS §6")
            with ctx.indent_block():
                ctx.emit("converged = 1")
                ctx.emit("break")
            ctx.emit(
                "H_prime = K_hard * n_hard * ti.pow(alpha_trial, n_hard - 1.0) "
                "if alpha_trial > 1e-12 else 0.0"
            )
            ctx.emit("df = -3.0 * mu - H_prime")
            ctx.emit("dl -= f / df")
        ctx.emit("# Guard: flag ANY non-convergence of the return map (parity with the")
        ctx.emit("# host constitutive_update_plastic emitter) — a non-converged return")
        ctx.emit("# map poisons the tangent with NaN rather than silently emitting a")
        ctx.emit("# wrong C_ep; the NaN propagates through C_ep to the matvec output.")
        ctx.emit("# COUPLING: the converged flag is set by the in-loop check, which keys")
        ctx.emit("# off effective_tol (change one -> revisit the other). The explicit")
        ctx.emit("# flag (vs a post-loop residual-magnitude test) closes the band gap")
        ctx.emit("# where a result in (effective_tol, 1e3*effective_tol] would be")
        ctx.emit("# silently accepted; the reference raises on loop exhaustion.")
        ctx.emit("if converged == 0:")
        with ctx.indent_block():
            ctx.emit("# Non-converged: set NaN flag (propagates to the Newton driver).")
            ctx.emit("dl = ti.f64(float('nan'))")
        ctx.emit("else:")
        with ctx.indent_block():
            ctx.emit("# Converged: clamp dl >= 0 (negative plastic multiplier is")
            ctx.emit("# non-physical). Gated under else: so the NaN sentinel on the")
            ctx.emit("# non-converged branch survives -- a GPU fmax(NaN, 0.0) -> 0.0")
            ctx.emit("# would erase it and silently poison the tangent.")
            ctx.emit("dl = ti.max(dl, 0.0)")
        ctx.emit("# Updated PK2 stress: radial scaling of the deviatoric trial.")
        ctx.emit("factor = 1.0 - 3.0 * mu * dl / sigma_eq")
        ctx.emit("S = S_vol + factor * S_dev_trial")
    ctx.emit("")
    ctx.emit("# Assemble the rank-4 tangent C_ep, stored 9x9 on the (K,I)x(M,J) pairs.")
    ctx.emit("# Elastic: C_IJKL = lam dKL dMN + mu(dKM dLN + dKN dLM).")
    ctx.emit("# Plastic (Simo & Hughes Box 3.5):")
    ctx.emit("#   C_ep = kappa (I (x) I) + 2 mu theta P_dev")
    ctx.emit("#        + (9 mu^2 dl / q - 9 mu^2 / (3 mu + H')) (n (x) n)")
    ctx.emit("# with kappa = lam + 2 mu/3, theta = 1 - 3 mu dl / q, q = sigma_eq,")
    ctx.emit("# n = S_dev_trial / q, H' = K n_hard alpha_new^(n_hard-1).")
    ctx.emit("kappa = lam + 2.0 * mu / 3.0")
    ctx.emit("theta = ti.f64(1.0)")
    ctx.emit("nn_coeff = ti.f64(0.0)")
    ctx.emit("n_flow = ti.Matrix.zero(ti.f64, DIM, DIM)")
    ctx.emit("if is_plastic != 0:")
    with ctx.indent_block():
        ctx.emit("alpha_new = alpha_old + dl")
        ctx.emit(
            "H_prime_final = K_hard * n_hard * ti.pow(alpha_new, n_hard - 1.0) "
            "if alpha_new > 1e-12 else 0.0"
        )
        ctx.emit("theta = 1.0 - 3.0 * mu * dl / sigma_eq")
        ctx.emit(
            "nn_coeff = 9.0 * mu * mu * dl / sigma_eq - 9.0 * mu * mu / (3.0 * mu + H_prime_final)"
        )
        ctx.emit("n_flow = S_dev_trial / sigma_eq")
    ctx.emit("C_ep = ti.Matrix.zero(ti.f64, DIM * DIM, DIM * DIM)")
    ctx.emit("for K in ti.static(range(DIM)):")
    with ctx.indent_block():
        ctx.emit("for I in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("for M in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("for J in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("# Symmetric identity I4_sym and volumetric I (x) I terms.")
                    ctx.emit("dKI = 1.0 if K == I else 0.0")
                    ctx.emit("dMJ = 1.0 if M == J else 0.0")
                    ctx.emit("dKM = 1.0 if K == M else 0.0")
                    ctx.emit("dIJ = 1.0 if I == J else 0.0")
                    ctx.emit("dKJ = 1.0 if K == J else 0.0")
                    ctx.emit("dIM = 1.0 if I == M else 0.0")
                    ctx.emit("i4_sym = 0.5 * (dKM * dIJ + dKJ * dIM)")
                    ctx.emit("ixi = dKI * dMJ")
                    ctx.emit("# P_dev = I4_sym - (1/3) I (x) I.")
                    ctx.emit("p_dev = i4_sym - (1.0 / 3.0) * ixi")
                    ctx.emit("c_val = kappa * ixi + 2.0 * mu * theta * p_dev")
                    ctx.emit("c_val += nn_coeff * n_flow[K, I] * n_flow[M, J]")
                    ctx.emit("C_ep[K * DIM + I, M * DIM + J] = c_val")


def _emit_j2_consistent_tangent_A(ctx: EmissionContext) -> None:
    """Emit the per-QP consistent two-point J2 tangent ``A[i,I,j,J]``.

    Folds the in-scope rank-4 algorithmic tangent ``C_ep`` (9×9 on the
    ``(K,I)`` × ``(M,J)`` pairs, from :func:`_emit_j2_algorithmic_tangent_C`)
    and PK2 stress ``S`` into the same two-point structure the SVK path uses,
    so the downstream optimiser-recorded contraction is identical::

        A_{iIjJ} = δ_{ij} S_{JI}                     (geometric / initial stress)
                 + sum_{K,M} F_{iK} C_ep_{KIMJ} F_{jM}   (material, F·(C_ep:dE))

    matching ``ref_hex8_plastic`` (``dP = grad_v @ S + F @ (C_ep : dE)`` with
    ``dE = sym(F^T grad_v)``; the symmetrisation is absorbed by the minor
    symmetry of ``C_ep`` in ``(M,J)``). All six indices (i,I,j,J,K,M) are
    physics indices (range 3) → ``ti.static`` per 07-CONVENTIONS; the result is
    a 9×9 ``ti.Matrix`` indexed ``A[i*DIM + I, j*DIM + J]`` for the contraction
    below.
    """
    ctx.emit("# Consistent two-point J2 tangent A[i,I,j,J] such that")
    ctx.emit("#   dP_{iI} = A_{iIjJ} * grad_v_{jJ}   (grad_v_{jJ} = sum_b v_{bj} dNdX_{bJ}).")
    ctx.emit("#   A_{iIjJ} = delta_{ij} S_{JI}                       (geometric / initial stress)")
    ctx.emit("#            + sum_{K,M} F_{iK} C_ep_{KIMJ} F_{jM}     (material, F.(C_ep:dE))")
    ctx.emit("# Stored 9x9 on the (i,I)x(j,J) pairs (row i*DIM+I, col j*DIM+J).")
    ctx.emit("A = ti.Matrix.zero(ti.f64, DIM * DIM, DIM * DIM)")
    ctx.emit("for i in ti.static(range(DIM)):")
    with ctx.indent_block():
        ctx.emit("for I in ti.static(range(DIM)):")
        with ctx.indent_block():
            ctx.emit("for j in ti.static(range(DIM)):")
            with ctx.indent_block():
                ctx.emit("for J in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("# material: sum_{K,M} F_{iK} C_ep_{KIMJ} F_{jM}")
                    ctx.emit("a_iIjJ = ti.f64(0.0)")
                    ctx.emit("for K in ti.static(range(DIM)):")
                    with ctx.indent_block():
                        ctx.emit("for M in ti.static(range(DIM)):")
                        with ctx.indent_block():
                            ctx.emit("a_iIjJ += F[i, K] * C_ep[K * DIM + I, M * DIM + J] * F[j, M]")
                    ctx.emit("# geometric: delta_{ij} S_{JI}")
                    ctx.emit("if i == j:")
                    with ctx.indent_block():
                        ctx.emit("a_iIjJ += S[J, I]")
                    ctx.emit("A[i * DIM + I, j * DIM + J] = a_iIjJ")


def emit_j2_tangent_matvec_kernel(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit the generated ``@ti.kernel`` matrix-free J2 tangent operator (P5-1).

    Emits ``j2_tangent_matvec_apply(out, v, lam, mu, sigma_y0, K_hard, n_hard)``
    — a ``@ti.kernel`` that applies the **J2 algorithmic consistent tangent**
    ``K(u)·v`` fully matrix-free over all elements, the dissipative-model
    counterpart of :func:`emit_svk_tangent_matvec_kernel`.

    Per quadrature point it re-runs the radial-return map with the **on-device**
    history ``alpha[e, q]`` (read-only — history advances only in
    ``compute_internal_force``, never in the matvec) to obtain the current PK2
    stress ``S`` and the rank-4 algorithmic tangent ``C_ep``
    (:func:`_emit_j2_algorithmic_tangent_C`), folds them into the consistent
    two-point tangent ``A(i,I,j,J)`` (:func:`_emit_j2_consistent_tangent_A`),
    and applies it to ``v`` via the **same** P3-1 optimiser-recorded contraction
    path as SVK (:func:`_emit_optimised_matvec_contraction`). The result
    scatters to the global ``out`` field via atomic add, targeting the
    ``ti_runtime`` ``apply_A(out, x)`` injection seam.

    No NumPy touches the operator: ``alpha`` is read from the device field, the
    return map runs in the kernel, and the contraction is the same Tier-1
    ``ti_runtime`` / ``ti.static`` path. Only emitted for the J2 /
    Total-Lagrangian / reference path (see :func:`emit`).
    """
    from mechdsl.ir.element_ir import create_hex8_element_ir
    from mechdsl.lowering.einsum_extract import build_tangent_matvec_plan

    # Same Layer-4b ContractionPlan as the SVK generated kernel: the tangent
    # contraction (qaI,qiIjJ,qbJ,bj->qai) is identical once A is formed; only
    # the per-QP A-formation differs (J2 algorithmic tangent vs SVK closed form).
    element_ir = create_hex8_element_ir(formulation="total_lagrangian", configuration="reference")
    plan = build_tangent_matvec_plan(element_ir)

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Generated matrix-free J2 algorithmic-tangent @ti.kernel (PlanJune14 P5-1)")
    ctx.emit("#")
    ctx.emit("# Applies the J2 ALGORITHMIC CONSISTENT TANGENT K(u)·v fully matrix-free")
    ctx.emit("# (D-A: element tangents never stored), recomputed per matvec. The tangent")
    ctx.emit("# is the linearisation of the radial-return map (NOT d2Psi/dE2 — J2 is")
    ctx.emit("# dissipative; see .claude/rules/symbolic.md). History alpha[e, q] is read")
    ctx.emit("# on-device (read-only); it advances only in compute_internal_force. The")
    ctx.emit(f"# contraction rides the P3-1 opt_einsum ContractionPlan ('{plan.einsum_string}',")
    ctx.emit(f"# path {list(plan.contraction_path)}, tier {plan.tier}) — the same path as the")
    ctx.emit("# SVK kernel; kinematics use the Tier-1 ti_runtime @ti.func helpers.")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("from ti_runtime import tensor_ti as _tt")
    ctx.emit("")
    ctx.emit("")
    ctx.emit("@ti.kernel")
    ctx.emit("def j2_tangent_matvec_apply(")
    ctx.emit("    out: ti.template(),")
    ctx.emit("    v: ti.template(),")
    ctx.emit("    lam: ti.f64,")
    ctx.emit("    mu: ti.f64,")
    ctx.emit("    sigma_y0: ti.f64,")
    ctx.emit("    K_hard: ti.f64,")
    ctx.emit("    n_hard: ti.f64,")
    ctx.emit("):")
    with ctx.indent_block():
        ctx.emit('"""Matrix-free J2 algorithmic tangent: out = K(u) · v, per call.')
        ctx.emit("")
        ctx.emit("D-A (06-CODEGEN §3.3): no element stiffness is ever formed or stored.")
        ctx.emit("``out`` is zeroed here, then element contributions are scattered via")
        ctx.emit("Taichi's implicit atomic add. ``u`` (current Newton iterate), the mesh")
        ctx.emit("fields ``x_ref`` / ``elem_nodes``, and the history ``alpha`` are read")
        ctx.emit("live; ``alpha`` is NOT written (history advances in compute_internal_force).")
        ctx.emit("")
        ctx.emit("The tangent is the J2 algorithmic consistent tangent (linearisation of")
        ctx.emit("the radial-return map). The contraction is the P3-1 opt_einsum")
        ctx.emit(f"ContractionPlan for ``{plan.einsum_string}`` (operands dNdX, A, dNdX, v),")
        ctx.emit(f"realised as the recorded path {list(plan.contraction_path)} (tier {plan.tier}).")
        ctx.emit('"""')
        ctx.emit("# Zero the output field (mesh loop — runtime).")
        ctx.emit("for n in range(n_nodes):")
        with ctx.indent_block():
            ctx.emit("out[n] = ti.Vector([0.0, 0.0, 0.0], dt=ti.f64)")
        ctx.emit("")
        ctx.emit("# Loop over elements (runtime — mesh index).")
        ctx.emit("for e in range(n_elem):")
        with ctx.indent_block():
            ctx.emit("# Gather element reference coordinates.")
            ctx.emit("X_elem = ti.Matrix.zero(ti.f64, N_NODES, DIM)")
            ctx.emit("for a in range(N_NODES):")
            with ctx.indent_block():
                ctx.emit("nid = elem_nodes[e, a]")
                ctx.emit("for d in ti.static(range(DIM)):")
                with ctx.indent_block():
                    ctx.emit("X_elem[a, d] = x_ref[nid][d]")
            ctx.emit("")
            ctx.emit("# Quadrature loop (RUNTIME — PlanJune14 WI-1 JIT-budget lever).")
            ctx.emit("# Runtime q divides the per-QP unroll by N_QP (8); physics indices")
            ctx.emit("# i,I,j,J,K,M,a,d stay ti.static. The body can no longer index the")
            ctx.emit("# Python-list quad constants by a runtime q, so it reads the")
            ctx.emit("# device-resident _GRAD_AT_QUAD_F / _QUAD_WEIGHTS_F filled in")
            ctx.emit("# allocate_fields() (codegen.md: runtime-q is convention-clean once")
            ctx.emit("# the body no longer indexes Python-list constants).")
            ctx.emit("for q in range(N_QP):")
            with ctx.indent_block():
                ctx.emit("w_q = _QUAD_WEIGHTS_F[q]")
                ctx.emit("# Parametric shape gradients dN/dxi at this quad point.")
                ctx.emit("dN_dxi = ti.Matrix.zero(ti.f64, N_NODES, DIM)")
                ctx.emit("for a in ti.static(range(N_NODES)):")
                with ctx.indent_block():
                    ctx.emit("for d in ti.static(range(DIM)):")
                    with ctx.indent_block():
                        ctx.emit("dN_dxi[a, d] = _GRAD_AT_QUAD_F[q, a, d]")
                ctx.emit("")
                ctx.emit("# Reference Jacobian J0 = X^T @ dN/dxi and dNdX = dN/dxi @ J0^{-1}.")
                ctx.emit("J0 = X_elem.transpose() @ dN_dxi")
                ctx.emit("detJ0 = _tt.det3(J0)")
                ctx.emit("# Degenerate-element guard (07-CONVENTIONS §6).")
                ctx.emit("if detJ0 > 1e-15:")
                with ctx.indent_block():
                    ctx.emit("dNdX = dN_dxi @ _tt.inv3(J0)")
                    ctx.emit("")
                    ctx.emit("# Material displacement gradient grad_u = sum_a u_a (x) dNdX_a.")
                    ctx.emit("grad_u = ti.Matrix.zero(ti.f64, DIM, DIM)")
                    ctx.emit("for a in range(N_NODES):")
                    with ctx.indent_block():
                        ctx.emit("nid = elem_nodes[e, a]")
                        ctx.emit("for i in ti.static(range(DIM)):")
                        with ctx.indent_block():
                            ctx.emit("for I in ti.static(range(DIM)):")
                            with ctx.indent_block():
                                ctx.emit("grad_u[i, I] += u[nid][i] * dNdX[a, I]")
                    ctx.emit("")
                    ctx.emit("# Kinematics via Tier-1 ti_runtime helpers.")
                    ctx.emit("F = _tt.deformation_gradient(grad_u)")
                    ctx.emit("E = _tt.green_lagrange(F)")
                    ctx.emit("# Read the stored history (on-device, read-only).")
                    ctx.emit("alpha_old = alpha[e, q]")
                    ctx.emit("")
                    _emit_j2_algorithmic_tangent_C(ctx)
                    ctx.emit("")
                    _emit_j2_consistent_tangent_A(ctx)
                    ctx.emit("")
                    _emit_optimised_matvec_contraction(ctx, plan)
    ctx.emit("")


def emit_newton_driver(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit Newton-Raphson driver.

    The driver iterates:
        1. Compute internal force
        2. Form residual = f_int - f_ext
        3. Solve K @ du = -residual (using tangent_matvec + external CG)
        4. Update u += du
        5. Check convergence

    For J2 plasticity the driver passes extra material params to
    ``compute_internal_force`` and ``tangent_matvec``.
    """
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    is_plastic = _is_plastic_material(material_model)
    is_damage = _is_damage_material(material_model)
    derived = _derived_params(bundle)

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Newton-Raphson driver")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("")

    if derived is not None:
        sig = ", ".join(f"{name}: float" for name in derived)
        ctx.emit(f"def newton_solve({sig},")
        ctx.emit("                 bc_dofs: np.ndarray | None = None,")
        ctx.emit("                 bc_values: np.ndarray | None = None,")
        ctx.emit("                 max_iter: int = 20,")
        ctx.emit("                 tol_abs: float = 1.0e-10,")
        ctx.emit("                 tol_rel: float = 1.0e-8) -> int:")
    elif is_damage:
        ctx.emit("def newton_solve(lam: float, mu: float,")
        ctx.emit("                 sigma_y0: float, K_hard: float, n_hard: float,")
        ctx.emit("                 S_d_val: float, s_d_val: float, eps_D_val: float,")
        ctx.emit("                 E_mod_val: float, nu_val: float,")
        ctx.emit("                 D_crit: float = 0.95,")
        ctx.emit("                 bc_dofs: np.ndarray | None = None,")
        ctx.emit("                 bc_values: np.ndarray | None = None,")
        ctx.emit("                 max_iter: int = 20,")
        ctx.emit("                 tol_abs: float = 1.0e-10,")
        ctx.emit("                 tol_rel: float = 1.0e-8) -> int:")
    elif is_plastic:
        ctx.emit("def newton_solve(lam: float, mu: float,")
        ctx.emit("                 sigma_y0: float, K_hard: float, n_hard: float,")
        ctx.emit("                 bc_dofs: np.ndarray | None = None,")
        ctx.emit("                 bc_values: np.ndarray | None = None,")
        ctx.emit("                 max_iter: int = 20,")
        ctx.emit("                 tol_abs: float = 1.0e-10,")
        ctx.emit("                 tol_rel: float = 1.0e-8) -> int:")
    else:
        ctx.emit("def newton_solve(lam: float, mu: float,")
        ctx.emit("                 bc_dofs: np.ndarray | None = None,")
        ctx.emit("                 bc_values: np.ndarray | None = None,")
        ctx.emit("                 max_iter: int = 20,")
        ctx.emit("                 tol_abs: float = 1.0e-10,")
        ctx.emit("                 tol_rel: float = 1.0e-8) -> int:")

    with ctx.indent_block():
        ctx.emit('"""Newton-Raphson nonlinear solver with Dirichlet BC enforcement.')
        ctx.emit("")
        ctx.emit("Convergence is declared when ``res_norm < max(tol_abs, tol_rel * r0_norm)``.")
        ctx.emit("")
        ctx.emit("Parameters")
        ctx.emit("----------")
        if derived is not None:
            ctx.emit(f"{', '.join(derived)} : float")
            ctx.emit("    Material parameters of the LaTeX-derived strain energy.")
        else:
            ctx.emit("lam, mu : float")
            ctx.emit("    Lame parameters.")
        if is_plastic:
            ctx.emit("sigma_y0, K_hard, n_hard : float")
            ctx.emit("    J2 plasticity parameters.")
        ctx.emit("bc_dofs : np.ndarray | None")
        ctx.emit("    Flat indices of constrained DOFs.  Residual, tangent matvec,")
        ctx.emit("    and displacement update are zeroed at these DOFs.")
        ctx.emit("bc_values : np.ndarray | None")
        ctx.emit("    Flat array of prescribed displacement values at constrained DOFs.")
        ctx.emit("    Must have the same length as bc_dofs.  When provided, ``u`` is")
        ctx.emit("    seeded with these values before the Newton loop (10-BOUNDARIES.md §6).")
        ctx.emit("max_iter : int")
        ctx.emit("    Maximum Newton iterations.")
        ctx.emit("tol_abs : float")
        ctx.emit("    Absolute convergence tolerance on residual norm.")
        ctx.emit("tol_rel : float")
        ctx.emit("    Relative convergence tolerance (multiplied by initial residual norm).")
        ctx.emit("")
        ctx.emit("Returns")
        ctx.emit("-------")
        ctx.emit("int")
        ctx.emit("    Number of iterations performed.")
        ctx.emit('"""')
        ctx.emit("from mechdsl.solver.import_adapter import CGSolver")
        ctx.emit("")
        ctx.emit("# Pre-flight: reject degenerate elements before solving")
        ctx.emit("validate_mesh()")
        ctx.emit("")
        ctx.emit("n_dof = n_nodes * DIM")
        ctx.emit("res_norm = float('inf')")
        ctx.emit("r0_norm: float | None = None")
        ctx.emit("")
        ctx.emit("# Seed prescribed displacements (10-BOUNDARIES.md §4.2, §6)")
        ctx.emit("if bc_dofs is not None and bc_values is not None:")
        with ctx.indent_block():
            ctx.emit("u_arr = u.to_numpy().reshape(-1)")
            ctx.emit("u_arr[bc_dofs] = bc_values")
            ctx.emit("u.from_numpy(u_arr.reshape((-1, 3)))")
        ctx.emit("")
        if is_plastic:
            # Plastic history is held in a SINGLE `alpha` field that
            # `compute_internal_force` mutates in place each call
            # (alpha_old = alpha[e, q]; ...; alpha[e, q] = alpha_new). Newton
            # iterations are *trial* states for one load step: every residual /
            # tangent evaluation must read the COMMITTED (step-start) history as
            # alpha_old, exactly like the reference solve_plastic, which keeps
            # alpha_old/alpha_current separate and assembles each iteration from
            # alpha_old. Without this, iteration k's return map would read
            # iteration k-1's trial alpha as alpha_old, ratcheting plastic strain
            # and stalling Newton. Snapshot the committed history here, restore it
            # at the top of every iteration (below). After the converged
            # iteration `alpha` holds the correct alpha_new (committed + Δλ at the
            # converged u) — the commit is implicit/by-construction.
            #
            # PERF NOTE: the committed history is held in device-resident mirror
            # fields (_alpha_committed, and _damage_D_committed / _is_deleted_committed
            # for damage materials). Snapshot/restore/rollback are on-device
            # ti.field.copy_from() calls — an O(field) device-to-device copy of the
            # (n_elem, N_QP) history, with NO host round-trip per iteration. This
            # replaces the earlier alpha.to_numpy() / from_numpy() compatibility
            # path, which moved the history host<->device every Newton iteration.
            ctx.emit("# Snapshot committed plastic history (see comment below).")
            ctx.emit("_alpha_committed.copy_from(alpha)")
            if is_damage:
                # Damage materials (Lemaitre) carry two more mutable history
                # fields that compute_internal_force advances in place each call:
                # damage_D[e, q] (D_old -> D_new) and the one-way is_deleted[e].
                # Both must follow the same committed/trial discipline as alpha —
                # they are TRIAL state within a step (rolled back on a failed
                # iteration; committed by construction once the step converges),
                # matching the reference Lemaitre rollback-both (see
                # tests/test_lemaitre_acceptance.py::_newton_step_lemaitre, which
                # snapshots+restores alpha AND damage_D around every residual eval).
                # Without this, damage_D / is_deleted would drift across Newton
                # iterations just as alpha would without its committed mirror.
                # copy_from is dtype-agnostic: it works for the f64 damage_D and
                # the i32 is_deleted alike (raw same-shape field copy on device).
                ctx.emit("_damage_D_committed.copy_from(damage_D)")
                ctx.emit("_is_deleted_committed.copy_from(is_deleted)")
            ctx.emit("")
        ctx.emit("for iteration in range(max_iter):")
        with ctx.indent_block():
            if is_plastic:
                ctx.emit("# Restore committed history so this iteration's return")
                ctx.emit("# map reads the step-start alpha_old (not the previous")
                ctx.emit("# iteration's trial). Matches ref solve_plastic, which")
                ctx.emit("# assembles every iteration from the committed alpha_old.")
                ctx.emit("# On-device copy_from — no host round-trip.")
                ctx.emit("alpha.copy_from(_alpha_committed)")
                if is_damage:
                    ctx.emit("# Same trial-state discipline for the damage history:")
                    ctx.emit("# restore committed damage_D and is_deleted so this")
                    ctx.emit("# iteration's constitutive update advances them from the")
                    ctx.emit("# step-start state, not the previous trial.")
                    ctx.emit("damage_D.copy_from(_damage_D_committed)")
                    ctx.emit("is_deleted.copy_from(_is_deleted_committed)")
                ctx.emit("")
            ctx.emit("# Step 1: Compute internal force")
            if is_damage:
                ctx.emit("compute_internal_force(lam, mu, sigma_y0, K_hard, n_hard,")
                ctx.emit("                       S_d_val, s_d_val, eps_D_val,")
                ctx.emit("                       E_mod_val, nu_val, D_crit)")
            elif is_plastic:
                ctx.emit("compute_internal_force(lam, mu, sigma_y0, K_hard, n_hard)")
            elif derived is not None:
                ctx.emit(f"compute_internal_force({', '.join(derived)})")
            else:
                ctx.emit("compute_internal_force(lam, mu)")
            ctx.emit("")
            ctx.emit("# Step 2: Form residual = f_int - f_ext")
            ctx.emit("r = f_int.to_numpy() - f_ext.to_numpy()")
            ctx.emit("r_flat = r.ravel()")
            ctx.emit("")
            ctx.emit("# Enforce Dirichlet BCs: zero residual at constrained DOFs")
            ctx.emit("if bc_dofs is not None:")
            with ctx.indent_block():
                ctx.emit("r_flat[bc_dofs] = 0.0")
            ctx.emit("")
            ctx.emit("res_norm = np.linalg.norm(r_flat)")
            ctx.emit("")
            ctx.emit("# Record initial residual for relative tolerance")
            ctx.emit("if r0_norm is None:")
            with ctx.indent_block():
                ctx.emit("r0_norm = res_norm")
            ctx.emit("")
            ctx.emit("if not np.isfinite(res_norm):")
            with ctx.indent_block():
                ctx.emit(
                    'raise RuntimeError("NaN or Inf detected in Newton residual. '
                    'Constitutive model may have failed to converge.")'
                )
            ctx.emit("")
            ctx.emit('print(f"  Newton iter {iteration}: ||R|| = {res_norm:.6e}")')
            ctx.emit("")
            ctx.emit("# Converge when residual is below absolute OR relative threshold")
            ctx.emit("conv_threshold = max(tol_abs, tol_rel * r0_norm)")
            ctx.emit("if res_norm < conv_threshold:")
            with ctx.indent_block():
                ctx.emit('print(f"  Converged in {iteration} iterations.")')
                ctx.emit("return iteration")
            ctx.emit("")
            ctx.emit("# Step 3: Solve K @ du = -R using CG with tangent matvec")
            ctx.emit("def matvec(v: np.ndarray) -> np.ndarray:")
            with ctx.indent_block():
                ctx.emit("v_bc = v.copy() if bc_dofs is not None else v")
                ctx.emit("if bc_dofs is not None:")
                with ctx.indent_block():
                    ctx.emit("v_bc[bc_dofs] = 0.0")
                if is_plastic:
                    ctx.emit("Kv = tangent_matvec(v_bc, lam, mu, sigma_y0, K_hard, n_hard)")
                elif derived is not None:
                    ctx.emit(f"Kv = tangent_matvec(v_bc, {', '.join(derived)})")
                else:
                    ctx.emit("Kv = tangent_matvec(v_bc, lam, mu)")
                ctx.emit("if bc_dofs is not None:")
                with ctx.indent_block():
                    ctx.emit("Kv[bc_dofs] = v[bc_dofs]")
                ctx.emit("return Kv")
            ctx.emit("")
            ctx.emit("solver = CGSolver()")
            ctx.emit("du_flat, cg_iters, cg_res = solver.solve(")
            ctx.emit("    matvec_fn=matvec, rhs=-r_flat,")
            ctx.emit("    x0=np.zeros(n_dof), tol=1.0e-10, max_iter=2000,")
            ctx.emit(")")
            ctx.emit("")
            ctx.emit("# Enforce Dirichlet BCs on displacement update")
            ctx.emit("if bc_dofs is not None:")
            with ctx.indent_block():
                ctx.emit("du_flat[bc_dofs] = 0.0")
            ctx.emit("")
            ctx.emit("# Step 4: Update displacement")
            ctx.emit("du_arr = du_flat.reshape((-1, 3))")
            ctx.emit("u_arr = u.to_numpy()")
            ctx.emit("u.from_numpy(u_arr + du_arr)")
        ctx.emit("")
        if is_plastic:
            # Non-convergence: leave committed history intact (mirror the
            # reference solve_plastic's history.rollback() before raising) — a
            # failed step must not advance plastic strain.
            ctx.emit("# Non-convergence: roll plastic history back to the committed")
            ctx.emit("# state before raising (ref solve_plastic does history.rollback()).")
            ctx.emit("# On-device copy_from — no host round-trip.")
            ctx.emit("alpha.copy_from(_alpha_committed)")
            if is_damage:
                ctx.emit("# Roll the damage history back too (is_deleted is trial")
                ctx.emit("# state within a step; a failed iteration must not commit a")
                ctx.emit("# one-way element deletion). Mirrors the reference")
                ctx.emit("# _newton_step_lemaitre rollback-both before raising.")
                ctx.emit("damage_D.copy_from(_damage_D_committed)")
                ctx.emit("is_deleted.copy_from(_is_deleted_committed)")
        ctx.emit(
            "raise RuntimeError("
            'f"Newton did not converge in {max_iter} iterations. '
            'Final |R| = {res_norm:.3e}")'
        )
    ctx.emit("")


def emit_explicit_driver(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit central-difference explicit-dynamics driver (Plan B §B7, P7-1).

    Emits:
      * a Taichi velocity field ``v`` of shape ``(n_nodes, 3)`` storing the
        half-step-centred velocity ``v^{n-1/2}`` (central difference) —
        see the in-source comment;
      * a Taichi lumped-mass field ``M_lumped`` of shape ``(n_nodes, 3)``;
      * an ``allocate_explicit_fields(nn)`` helper that places ``v`` and
        ``M_lumped`` alongside the existing displacement fields;
      * an ``@ti.kernel`` ``advance_one_step(dt)`` performing one
        central-difference update

          v^{n+1/2} = v^{n-1/2} + dt * M_inv * (f_ext - f_int)
          u^{n+1}   = u^{n}      + dt * v^{n+1/2}

        with the deleted-element guard ``if is_deleted[e] != 0: continue``
        baked into the internal-force accumulation so deleted elements
        contribute zero inertia / internal force (Phase 6 carry-forward).

    Callers drive the time loop externally: compute ``f_int`` via the
    already-emitted ``compute_internal_force`` helper, then call
    ``advance_one_step(dt)``.  No Newton solver is emitted in this mode.
    """
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    is_damage = _is_damage_material(material_model)

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Explicit-dynamics driver (central difference + lumped mass)")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("# Velocity field v stores the half-step-centred v^{n-1/2} in the")
    ctx.emit("# central-difference scheme; advance_one_step(dt) updates it in-place")
    ctx.emit("# to v^{n+1/2}, then uses the new velocity to step u^{n} -> u^{n+1}.")
    ctx.emit("v = ti.Vector.field(3, dtype=ti.f64)             # nodal velocity")
    ctx.emit("M_lumped = ti.Vector.field(3, dtype=ti.f64)      # row-sum lumped mass")
    ctx.emit("")
    ctx.emit("")
    ctx.emit("def allocate_explicit_fields(nn: int) -> None:")
    with ctx.indent_block():
        ctx.emit('"""Place the explicit-dynamics fields (v, M_lumped) for n_nodes=nn."""')
        ctx.emit("ti.root.dense(ti.i, nn).place(v, M_lumped)")
    ctx.emit("")
    ctx.emit("")
    ctx.emit("@ti.kernel")
    ctx.emit("def advance_one_step(dt: ti.f64):")
    with ctx.indent_block():
        ctx.emit('"""One central-difference step (Plan B §B7, P7-1).')
        ctx.emit("")
        ctx.emit("    v^{n+1/2} = v^{n-1/2} + dt * M_inv * (f_ext - f_int)")
        ctx.emit("    u^{n+1}   = u^{n}      + dt * v^{n+1/2}")
        ctx.emit("")
        ctx.emit("M_inv is computed per-DoF as 1/M_lumped.  Nodes with zero mass")
        ctx.emit("(e.g. unattached after element deletion) are skipped.")
        ctx.emit('"""')
        ctx.emit("# Update velocity from net force / lumped mass.")
        ctx.emit("for a in range(n_nodes):")
        with ctx.indent_block():
            ctx.emit("for i in ti.static(range(3)):")
            with ctx.indent_block():
                ctx.emit("m = M_lumped[a][i]")
                ctx.emit("if m > 0.0:")
                with ctx.indent_block():
                    ctx.emit("v[a][i] += dt * (f_ext[a][i] - f_int[a][i]) / m")
        ctx.emit("# Update displacement from the new half-step velocity.")
        ctx.emit("for a in range(n_nodes):")
        with ctx.indent_block():
            ctx.emit("for i in ti.static(range(3)):")
            with ctx.indent_block():
                ctx.emit("u[a][i] += dt * v[a][i]")
    ctx.emit("")

    if is_damage:
        ctx.emit("# Note: deleted elements (is_deleted[e] != 0) contribute zero to")
        ctx.emit("# f_int via the guard already emitted in compute_internal_force.")
        ctx.emit("")


def emit_validate_mesh(ctx: EmissionContext) -> None:
    """Emit pre-flight mesh validation function.

    Checks that all element Jacobian determinants are positive before running
    the Newton solver.  This catches degenerate (zero-volume) elements that
    would otherwise be silently skipped by the runtime guard, producing a
    false-converged zero-displacement result.
    """
    ctx.emit("# " + "=" * 70)
    ctx.emit("# Mesh validation")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("")
    ctx.emit("def validate_mesh() -> None:")
    with ctx.indent_block():
        ctx.emit('"""Check all elements for degenerate Jacobians before solving.')
        ctx.emit("")
        ctx.emit("Raises ValueError if any quadrature point has det(J0) <= 0.")
        ctx.emit('"""')
        ctx.emit("coords_np = x_ref.to_numpy()")
        ctx.emit("conn_np = elem_nodes.to_numpy()")
        ctx.emit("n_elem_val = conn_np.shape[0]")
        ctx.emit("for e in range(n_elem_val):")
        with ctx.indent_block():
            ctx.emit("X_e = coords_np[conn_np[e]]  # (8, 3)")
            ctx.emit("for q in range(N_QP):")
            with ctx.indent_block():
                ctx.emit("dN = np.array(GRAD_AT_QUAD[q])  # (8, 3)")
                ctx.emit("J0 = X_e.T @ dN  # (3, 3)")
                ctx.emit("detJ0 = np.linalg.det(J0)")
                ctx.emit("if detJ0 <= 0.0:")
                with ctx.indent_block():
                    ctx.emit(
                        "raise ValueError("
                        'f"Degenerate element {e}: det(J0) = {detJ0:.6e} at quadrature point {q}. "'
                    )
                    ctx.emit('f"Check element connectivity and node coordinates.")')
    ctx.emit("")
    ctx.emit("")


# ---------------------------------------------------------------------------
# Neumann f_ext init kernel
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NeumannKernelSpec:
    """Description of a single Neumann BC's emitted ``init_f_ext`` kernel.

    The lowering pass (``mechdsl.lowering.boundary.lower_neumann``) produces
    one of these per Neumann BoundaryCondition; codegen translates each
    into a ``@ti.kernel`` that initialises ``f_ext`` from the BC's
    pre-distributed per-node force.

    ``per_node_force`` is the already-distributed nodal force vector
    (i.e. ``traction * face_area / n_face_nodes``), so the emitted kernel
    just writes it onto each tagged node — no quadrature or area logic in
    the kernel itself, matching the index-partitioning rule (mesh indices
    runtime, physics indices ``ti.static``).
    """

    bc_name: str
    surface_tag: str
    per_node_force: tuple[float, float, float]


def _sanitize_kernel_suffix(name: str) -> str:
    """Convert a BC name into a Python-identifier-safe suffix.

    BC names come from LaTeX directives (``% mechanics boundary <name>``)
    and may include hyphens, dots, or other tokens that Python forbids in
    identifiers. We keep alnum+underscore and replace everything else with
    a single underscore so the emitted kernel name is always parseable.
    """
    out = []
    for ch in name:
        out.append(ch if ch.isalnum() or ch == "_" else "_")
    sanitized = "".join(out).strip("_") or "bc"
    if sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


def emit_neumann_f_ext_kernel(
    ctx: EmissionContext,
    spec: NeumannKernelSpec,
) -> str:
    """Emit one ``init_f_ext_from_neumann_<bc>`` kernel for *spec*.

    The emitted kernel takes a 1-D ``ti.types.ndarray`` of surface node
    indices (length determined at call-site by the Python driver) and
    three pre-distributed force scalars. It zeroes ``f_ext`` globally,
    then writes the force onto each tagged surface node.

    Returns the emitted kernel function name so callers can reference it
    when wiring up the Newton driver. Side effect: lines appended to
    ``ctx``.

    Acceptance contract (post_recovery_plan P1-4):

    1. Generated source zeroes ``f_ext`` for every node before applying
       the Neumann contribution; nodes outside the tagged surface stay
       zero by construction.
    2. JIT budget honoured. Kernel body is a runtime ``for i in range(n_nodes)``
       zero loop plus a runtime ``for k in range(...)`` apply loop; the
       only ``ti.static`` loops are over the 3 spatial components, so
       per-kernel unrolled-line count stays well under the 2000-line cap.
    3. Kernel signature is stable and documented in the emitted docstring.
    """
    suffix = _sanitize_kernel_suffix(spec.bc_name)
    fn_name = f"init_f_ext_from_neumann_{suffix}"
    fx, fy, fz = spec.per_node_force

    ctx.emit("# " + "=" * 70)
    ctx.emit(f"# Neumann f_ext kernel for BC '{spec.bc_name}' (surface '{spec.surface_tag}')")
    ctx.emit("# Emitted by post_recovery_plan P1-4 (Taichi printer Neumann emitter)")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("@ti.kernel")
    ctx.emit(f"def {fn_name}(surface_nodes: ti.types.ndarray(dtype=ti.i32, ndim=1)):")
    with ctx.indent_block():
        ctx.emit(f'"""Initialise f_ext from Neumann BC \'{spec.bc_name}\'.')
        ctx.emit("")
        ctx.emit(f"Surface tag: '{spec.surface_tag}'.")
        ctx.emit(
            "Per-node force (pre-distributed: traction * face_area / n_face_nodes): "
            f"({_fmt_float(fx)}, {_fmt_float(fy)}, {_fmt_float(fz)})."
        )
        ctx.emit("")
        ctx.emit("Mesh indices (i, k) are runtime; spatial component (d) is ti.static.")
        ctx.emit('"""')
        # Zero f_ext globally — runtime mesh loop, ti.static over the 3 components.
        ctx.emit("for i in range(n_nodes):")
        with ctx.indent_block():
            ctx.emit("for d in ti.static(range(3)):")
            with ctx.indent_block():
                ctx.emit("f_ext[i][d] = 0.0")
        ctx.emit("")
        # Apply per-node force on tagged surface — runtime mesh loop, ti.static
        # over the 3 components written from the per-axis literal scalars.
        ctx.emit("n_surface = surface_nodes.shape[0]")
        ctx.emit("for k in range(n_surface):")
        with ctx.indent_block():
            ctx.emit("nid = surface_nodes[k]")
            ctx.emit(f"f_ext[nid][0] = {_fmt_float(fx)}")
            ctx.emit(f"f_ext[nid][1] = {_fmt_float(fy)}")
            ctx.emit(f"f_ext[nid][2] = {_fmt_float(fz)}")
    ctx.emit("")
    ctx.emit("")
    return fn_name


def emit_neumann_f_ext_kernel_for_ir(
    ctx: EmissionContext,
    bc_name: str,
    surface_tag: str,
    traction: tuple[float, float, float],
) -> str:
    """Emit a Neumann ``f_ext`` kernel parametric in face-area factor.

    Companion to :func:`emit_neumann_f_ext_kernel`. The literal-baked form
    (P1-4) is right for golden tests where the lowering pre-distributes
    the per-node force; this parametric form is right for the canonical
    LaTeX façade (P1-5), which builds the kernel from the IR
    ``BoundaryCondition`` alone — no mesh, no face area available at
    compile time.

    The emitted kernel signature is::

        @ti.kernel
        def init_f_ext_from_neumann_<bc>(
            surface_nodes: ti.types.ndarray(dtype=ti.i32, ndim=1),
            f_factor: ti.f64,
        ): ...

    where ``f_factor = face_area / n_face_nodes`` is computed by the
    Python driver from the runtime mesh. The traction components are
    baked as deterministic float literals.
    """
    suffix = _sanitize_kernel_suffix(bc_name)
    fn_name = f"init_f_ext_from_neumann_{suffix}"
    tx, ty, tz = traction

    ctx.emit("# " + "=" * 70)
    ctx.emit(f"# Neumann f_ext kernel for BC '{bc_name}' (surface '{surface_tag}')")
    ctx.emit("# Emitted by post_recovery_plan P1-5 (façade-driven, parametric form)")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("@ti.kernel")
    ctx.emit(
        f"def {fn_name}(surface_nodes: ti.types.ndarray(dtype=ti.i32, ndim=1), f_factor: ti.f64):"
    )
    with ctx.indent_block():
        ctx.emit(f'"""Initialise f_ext from Neumann BC \'{bc_name}\'.')
        ctx.emit("")
        ctx.emit(f"Surface tag: '{surface_tag}'.")
        ctx.emit(f"Traction (literal): ({_fmt_float(tx)}, {_fmt_float(ty)}, {_fmt_float(tz)}).")
        ctx.emit("f_factor: face_area / n_face_nodes — supplied at runtime.")
        ctx.emit("")
        ctx.emit("Mesh indices (i, k) are runtime; spatial component (d) is ti.static.")
        ctx.emit('"""')
        ctx.emit("for i in range(n_nodes):")
        with ctx.indent_block():
            ctx.emit("for d in ti.static(range(3)):")
            with ctx.indent_block():
                ctx.emit("f_ext[i][d] = 0.0")
        ctx.emit("")
        ctx.emit("n_surface = surface_nodes.shape[0]")
        ctx.emit("for k in range(n_surface):")
        with ctx.indent_block():
            ctx.emit("nid = surface_nodes[k]")
            ctx.emit(f"f_ext[nid][0] = {_fmt_float(tx)} * f_factor")
            ctx.emit(f"f_ext[nid][1] = {_fmt_float(ty)} * f_factor")
            ctx.emit(f"f_ext[nid][2] = {_fmt_float(tz)} * f_factor")
    ctx.emit("")
    ctx.emit("")
    return fn_name


def emit_postprocess(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit save_results() function for displacement output.

    Saves displacement as ``.npz`` (numpy only — no external deps).
    Optionally exports VTK via meshio if available.
    """
    ctx.emit("# " + "=" * 70)
    ctx.emit("# Postprocessing")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("")
    ctx.emit("def save_results(output_path: str = 'results.npz') -> None:")
    with ctx.indent_block():
        ctx.emit('"""Save displacement results to .npz file."""')
        ctx.emit("u_arr = u.to_numpy()")
        ctx.emit("x_ref_arr = x_ref.to_numpy()")
        ctx.emit("np.savez(")
        with ctx.indent_block():
            ctx.emit("output_path,")
            ctx.emit("displacement=u_arr,")
            ctx.emit("reference_coords=x_ref_arr,")
        ctx.emit(")")
        ctx.emit('print(f"Results saved to {output_path}")')
        ctx.emit("")
        ctx.emit("# Optional VTK export via meshio")
        ctx.emit("try:")
        with ctx.indent_block():
            ctx.emit("import meshio")
            ctx.emit("points = x_ref_arr + u_arr")
            ctx.emit("conn_arr = elem_nodes.to_numpy()")
            ctx.emit("mesh = meshio.Mesh(")
            ctx.emit("    points=points,")
            ctx.emit('    cells=[("hexahedron", conn_arr)],')
            ctx.emit('    point_data={"displacement": u_arr},')
            ctx.emit(")")
            ctx.emit("vtk_path = output_path.replace('.npz', '.vtk')")
            ctx.emit("meshio.write(vtk_path, mesh)")
            ctx.emit('print(f"VTK written to {vtk_path}")')
        ctx.emit("except ImportError:")
        with ctx.indent_block():
            ctx.emit("pass  # meshio not available")
    ctx.emit("")
    ctx.emit("")


def emit_main(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit ``if __name__ == '__main__'`` block.

    Emits mesh loading from ``.npz``, Taichi field allocation, material
    parameter setup, Newton solve call, and convergence summary.
    """
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    is_plastic = _is_plastic_material(material_model)
    is_damage = _is_damage_material(material_model)
    params = bundle.problem_ir_dict.get("material", {}).get("params", {})
    dynamics_mode = bundle.problem_ir_dict.get("dynamics_mode", "static")
    derived = _derived_params(bundle)

    # Explicit-dynamics __main__: no Newton solve; the generated module exposes
    # advance_one_step(dt) so the user drives time stepping externally. We emit
    # a minimal informational main here so the module is still importable and
    # the file is self-contained.
    if dynamics_mode == "explicit":
        ctx.emit("# " + "=" * 70)
        ctx.emit("# Main entry point (explicit dynamics)")
        ctx.emit("# " + "=" * 70)
        ctx.emit("")
        ctx.emit("")
        ctx.emit('if __name__ == "__main__":')
        with ctx.indent_block():
            ctx.emit('"""Explicit dynamics emits advance_one_step(dt); no Newton solve."""')
            ctx.emit("print(")
            with ctx.indent_block():
                ctx.emit('"Generated explicit-dynamics module. "')
                ctx.emit('"Import and drive advance_one_step(dt) from your own time loop."')
            ctx.emit(")")
        ctx.emit("")
        return

    ctx.emit("# " + "=" * 70)
    ctx.emit("# Main entry point")
    ctx.emit("# " + "=" * 70)
    ctx.emit("")
    ctx.emit("")
    ctx.emit('if __name__ == "__main__":')
    with ctx.indent_block():
        ctx.emit("import sys")
        ctx.emit("")
        ctx.emit("# Load mesh")
        ctx.emit('mesh_path = sys.argv[1] if len(sys.argv) > 1 else "mesh.npz"')
        ctx.emit('print(f"Loading mesh from {mesh_path}")')
        ctx.emit("mesh_data = np.load(mesh_path)")
        ctx.emit('coords = mesh_data["coords"]')
        ctx.emit('conn = mesh_data["conn"]')
        ctx.emit("")
        ctx.emit("# Allocate Taichi fields and load mesh data")
        ctx.emit("n_nodes_mesh = coords.shape[0]")
        ctx.emit("n_elem_mesh = conn.shape[0]")
        ctx.emit("allocate_fields(n_nodes_mesh, n_elem_mesh)")
        ctx.emit("x_ref.from_numpy(coords)")
        ctx.emit("elem_nodes.from_numpy(conn)")
        ctx.emit("")
        ctx.emit("# Load boundary conditions from mesh file")
        ctx.emit('if "f_ext" in mesh_data:')
        with ctx.indent_block():
            ctx.emit("f_ext.from_numpy(mesh_data['f_ext'])")
        ctx.emit("else:")
        with ctx.indent_block():
            ctx.emit('print("Warning: no f_ext in mesh file; external forces default to zero.")')
        ctx.emit("")
        ctx.emit('bc_dofs = mesh_data["bc_dofs"] if "bc_dofs" in mesh_data else None')
        ctx.emit("")
        ctx.emit("# Normalize bc_values: accept (n_nodes, 3) or flat array matching bc_dofs")
        ctx.emit('bc_values_raw = mesh_data["bc_values"] if "bc_values" in mesh_data else None')
        ctx.emit("bc_values = None")
        ctx.emit("if bc_values_raw is not None and bc_dofs is not None:")
        with ctx.indent_block():
            ctx.emit("if bc_values_raw.ndim == 2:")
            with ctx.indent_block():
                ctx.emit("bc_values = bc_values_raw.ravel()[bc_dofs]")
            ctx.emit("else:")
            with ctx.indent_block():
                ctx.emit("bc_values = bc_values_raw")
        ctx.emit("")
        ctx.emit("# Material parameters")

        if derived is not None:
            # LaTeX-derived model: emit one ``<name>_val`` per derived parameter,
            # sourced by name from the IR material params (fail loud if missing
            # rather than defaulting to a silently-wrong zero).
            missing = [name for name in derived if name not in params]
            if missing:
                raise ValueError(
                    f"derived material parameters {missing} are absent from the IR "
                    f"material params {sorted(params)}; the strain-energy LaTeX uses "
                    "them, so they must be supplied via MaterialSpec(params={...})."
                )
            for name in derived:
                ctx.emit(f"{name}_val = {_fmt_float(float(params[name]))}")
        else:
            # Compute Lamé parameters: use direct lam/mu if available, else derive from E/nu
            if "lam" in params and "mu" in params:
                lam = params["lam"]
                mu = params["mu"]
            elif "E" in params and "nu" in params:
                E_val = params["E"]
                nu_val = params["nu"]
                lam = E_val * nu_val / ((1 + nu_val) * (1 - 2 * nu_val))
                mu = E_val / (2 * (1 + nu_val))
            else:
                lam = params.get("lam", 0.0)
                mu = params.get("mu", 0.0)
            ctx.emit(f"lam_val = {_fmt_float(lam)}")
            ctx.emit(f"mu_val = {_fmt_float(mu)}")

        if is_plastic:
            ctx.emit(f"sigma_y0_val = {_fmt_float(params.get('sigma_y0', 0.0))}")
            ctx.emit(f"K_hard_val = {_fmt_float(params.get('K', 0.0))}")
            ctx.emit(f"n_hard_val = {_fmt_float(params.get('n', 0.0))}")

        if is_damage:
            ctx.emit(f"S_d_val = {_fmt_float(params.get('S_d', 1.0))}")
            ctx.emit(f"s_d_val = {_fmt_float(params.get('s_d', 1.0))}")
            ctx.emit(f"eps_D_val = {_fmt_float(params.get('eps_D', 0.0))}")
            # E and nu are preserved as raw parameters for the damage evolution
            # (the Lemaitre energy-release rate Y needs E and nu directly, not
            # lam/mu derivations).  When only lam/mu are supplied, recover E/nu
            # via the standard relation E = mu(3 lam + 2 mu)/(lam + mu).
            if "E" in params and "nu" in params:
                E_main = float(params["E"])
                nu_main = float(params["nu"])
            else:
                _lam = float(lam)
                _mu = float(mu)
                if _lam + _mu == 0:
                    E_main = 0.0
                    nu_main = 0.0
                else:
                    E_main = _mu * (3.0 * _lam + 2.0 * _mu) / (_lam + _mu)
                    nu_main = _lam / (2.0 * (_lam + _mu))
            ctx.emit(f"E_mod_val = {_fmt_float(E_main)}")
            ctx.emit(f"nu_val = {_fmt_float(nu_main)}")
            ctx.emit(f"D_crit_val = {_fmt_float(params.get('D_crit', 0.95))}")

        ctx.emit("")
        ctx.emit("# Run Newton solver")
        if is_damage:
            ctx.emit("# NOTE (P6-2): Lemaitre damage requires incremental load stepping")
            ctx.emit("# with alpha/D snapshot-rollback on non-convergence.  The standalone")
            ctx.emit("# __main__ path does not implement this; use the newton_solve() API")
            ctx.emit("# directly with your own load-stepping driver.  bc_values is")
            ctx.emit("# intentionally NOT forwarded here.")
            ctx.emit("if bc_values is not None:")
            with ctx.indent_block():
                ctx.emit('print("WARNING: bc_values ignored for Lemaitre __main__ path. "')
                ctx.emit('"Damage evolution requires load stepping. Use newton_solve() "')
                ctx.emit('"API with a custom driver.")')
            ctx.emit("n_iters = newton_solve(lam_val, mu_val,")
            ctx.emit("                       sigma_y0_val, K_hard_val, n_hard_val,")
            ctx.emit("                       S_d_val, s_d_val, eps_D_val,")
            ctx.emit("                       E_mod_val, nu_val,")
            ctx.emit("                       D_crit=D_crit_val,")
            ctx.emit("                       bc_dofs=bc_dofs)")
        elif is_plastic:
            ctx.emit("# NOTE: Displacement-controlled plastic loading requires incremental")
            ctx.emit("# load stepping with alpha snapshot/rollback.  The standalone __main__")
            ctx.emit("# path does not implement this; use the newton_solve() API directly")
            ctx.emit("# with your own load-stepping driver (see test_e2e_plastic.py for an")
            ctx.emit("# example).  bc_values is intentionally NOT forwarded here.")
            ctx.emit("if bc_values is not None:")
            with ctx.indent_block():
                ctx.emit('print("WARNING: bc_values ignored for plastic __main__ path. "')
                ctx.emit('"Displacement-controlled J2 requires load stepping with alpha "')
                ctx.emit('"management. Use newton_solve() API with a custom driver.")')
            ctx.emit("n_iters = newton_solve(lam_val, mu_val,")
            ctx.emit("                       sigma_y0_val, K_hard_val, n_hard_val,")
            ctx.emit("                       bc_dofs=bc_dofs)")
        elif derived is not None:
            vals = ", ".join(f"{name}_val" for name in derived)
            ctx.emit(f"n_iters = newton_solve({vals}, bc_dofs=bc_dofs, bc_values=bc_values)")
        else:
            ctx.emit(
                "n_iters = newton_solve(lam_val, mu_val, bc_dofs=bc_dofs, bc_values=bc_values)"
            )

        ctx.emit("")
        ctx.emit('print(f"Newton converged in {n_iters} iterations.")')
        ctx.emit("")
        ctx.emit("# Save results")
        ctx.emit("save_results()")
    ctx.emit("")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def emit(bundle: ArtifactBundle) -> str:
    """Main entry point: emit complete Taichi source from artifact bundle.

    Returns the emitted source code as a string.
    The result is deterministic: same bundle -> same output.

    Parameters
    ----------
    bundle : ArtifactBundle
        Pipeline artifact containing the ProblemIR, ElementIR summary,
        contraction plans, and metadata.

    Returns
    -------
    str
        Self-contained Python/Taichi source file as a string.

    Raises
    ------
    ValueError
        If the artifact bundle carries a material model that the MVP
        emitter does not support.
    """
    ctx = EmissionContext()

    # Validate material model before emission. A bundle carrying a
    # LaTeX-derived energy model emits its constitutive @ti.func from that
    # energy (see emit_constitutive_update), so the named-model allow-list
    # does not gate it — any model whose law was derived from a strain-energy
    # density (e.g. neo_hookean) is admissible through the derived branch.
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    if bundle.derived_energy is None and material_model not in (
        "svk",
        "j2_power_law",
        "lemaitre",
    ):
        raise ValueError(
            f"Unsupported material model '{material_model}' for Taichi codegen. "
            f"Supported for emission: svk, j2_power_law, lemaitre. "
            f"Perzyna/Johnson-Cook Taichi emission is planned for a future integration task."
        )

    # Dynamics mode branch. STATIC (or missing) keeps the
    # existing Newton-driver emission byte-identical; EXPLICIT swaps the driver
    # for central-difference ``advance_one_step`` and skips the tangent matvec
    # that only the implicit Newton solver consumes.
    dynamics_mode = bundle.problem_ir_dict.get("dynamics_mode", "static")

    emit_preamble(ctx, bundle)
    emit_constants(ctx, bundle)
    ctx.emit("")
    emit_field_declarations(ctx, bundle)
    ctx.emit("")
    emit_constitutive_update(ctx, bundle)
    emit_internal_force_kernel(ctx, bundle)
    if dynamics_mode == "explicit":
        emit_validate_mesh(ctx)
        emit_explicit_driver(ctx, bundle)
    else:
        emit_tangent_matvec_kernel(ctx, bundle)
        # PlanJune14 P3-2: emit the generated matrix-free SVK tangent @ti.kernel
        # *alongside* the host tangent_matvec, for the SVK / Total-Lagrangian /
        # reference / named-model path only. The host route stays the default
        # the emitted Newton driver drives (flipping the default is P4-3); the
        # generated @ti.kernel is the optimiser-routed, ti_runtime-seam operator
        # that downstream tasks (P4-3, P5-1, P7-2) consume. Gating on this exact
        # path keeps every other golden (Lemaitre, UL, derived, explicit)
        # byte-identical.
        configuration = bundle.problem_ir_dict.get("configuration", "reference")
        if material_model == "svk" and bundle.derived_energy is None and configuration != "current":
            emit_svk_tangent_matvec_kernel(ctx, bundle)
        # J2's dissipative counterpart — the generated matrix-free
        # *algorithmic consistent tangent* @ti.kernel, emitted alongside the host
        # tangent_matvec for the J2 / Total-Lagrangian / reference path only (NOT
        # Lemaitre, which layers damage and stays on the host route until a
        # damage-aware tangent lands). Same opt_einsum contraction path as SVK;
        # only the per-QP A-formation re-runs the return map on-device.
        elif (
            material_model == "j2_power_law"
            and bundle.derived_energy is None
            and configuration != "current"
        ):
            emit_j2_tangent_matvec_kernel(ctx, bundle)
        emit_validate_mesh(ctx)
        emit_newton_driver(ctx, bundle)
    emit_postprocess(ctx, bundle)
    emit_main(ctx, bundle)

    return ctx.get_source()


# ---------------------------------------------------------------------------
# Design-doc-aligned façade
# ---------------------------------------------------------------------------


class TaichiCodegenFacade:
    """Design-doc-aligned façade over the module-level ``emit_*`` helpers.

    This class presents the codegen pipeline as a single entry-point object
    whose method names map 1-to-1 onto the underlying module-level
    ``emit_preamble``, ``emit_constants``, etc. helpers.  It adds **no
    logic** of its own — every method body is a direct delegation call —
    so the emitted source code is byte-for-byte identical to calling the
    module-level functions directly.

    The underlying module-level functions remain the implementation; they
    are importable and callable without going through this façade.  This
    façade exists purely to satisfy the design-doc-aligned API shape
    described in ``dev/design_docs/05-CODEGEN.md`` and the recovery plan
    §Phase 5 (R4.3).

    Usage
    -----
    ::

        from mechdsl.codegen.taichi_printer import TaichiCodegenFacade

        facade = TaichiCodegenFacade()
        source = facade.emit_all(bundle)   # full pipeline

        # Implicit (Newton) path:
        ctx = facade.make_context()
        facade.preamble(ctx, bundle)
        facade.constants(ctx, bundle)
        facade.field_declarations(ctx, bundle)
        facade.constitutive_update(ctx, bundle)
        facade.internal_force_kernel(ctx, bundle)
        facade.tangent_matvec_kernel(ctx, bundle)
        facade.validate_mesh(ctx)
        facade.newton_driver(ctx, bundle)
        facade.postprocess(ctx, bundle)
        facade.main(ctx, bundle)
        source = ctx.get_source()

        # Explicit dynamics path:
        ctx = facade.make_context()
        facade.preamble(ctx, bundle)
        facade.constants(ctx, bundle)
        facade.field_declarations(ctx, bundle)
        facade.constitutive_update(ctx, bundle)
        facade.internal_force_kernel(ctx, bundle)
        facade.validate_mesh(ctx)
        facade.explicit_driver(ctx, bundle)
        facade.postprocess(ctx, bundle)
        facade.main(ctx, bundle)
        source = ctx.get_source()

        # Verbose audit (recovery P5-4):
        ctx = facade.make_context(verbose=True)
        facade.preamble(ctx, bundle)
        # ... ctx.code now includes enriched-IR audit block.
    """

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    def make_context(self, *, verbose: bool = False) -> EmissionContext:
        """Construct a fresh EmissionContext.

        Parameters
        ----------
        verbose : bool, default False
            When True, the emission pipeline appends an "Enriched-IR contract
            surface (recovery P5-4 audit)" block to the emitted file's
            docstring whenever the bundle carries enrichment data. Default
            emission is byte-identical to legacy output.
        """
        return EmissionContext(verbose=verbose)

    # ------------------------------------------------------------------
    # Step-wise emitters — each delegates to the module-level function
    # ------------------------------------------------------------------

    def preamble(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_preamble`."""
        return emit_preamble(ctx, bundle)

    def constants(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_constants`."""
        return emit_constants(ctx, bundle)

    def field_declarations(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_field_declarations`."""
        return emit_field_declarations(ctx, bundle)

    def constitutive_update(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_constitutive_update`."""
        return emit_constitutive_update(ctx, bundle)

    def internal_force_kernel(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_internal_force_kernel`."""
        return emit_internal_force_kernel(ctx, bundle)

    def tangent_matvec_kernel(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_tangent_matvec_kernel`."""
        return emit_tangent_matvec_kernel(ctx, bundle)

    def svk_tangent_matvec_kernel(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_svk_tangent_matvec_kernel` (P3-2 generated kernel)."""
        return emit_svk_tangent_matvec_kernel(ctx, bundle)

    def j2_tangent_matvec_kernel(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_j2_tangent_matvec_kernel` (P5-1 generated kernel)."""
        return emit_j2_tangent_matvec_kernel(ctx, bundle)

    def validate_mesh(self, ctx: EmissionContext) -> None:
        """Delegate to :func:`emit_validate_mesh`."""
        return emit_validate_mesh(ctx)

    def newton_driver(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_newton_driver`."""
        return emit_newton_driver(ctx, bundle)

    def explicit_driver(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_explicit_driver`."""
        return emit_explicit_driver(ctx, bundle)

    def postprocess(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_postprocess`."""
        return emit_postprocess(ctx, bundle)

    def main(self, ctx: EmissionContext, bundle: ArtifactBundle) -> None:
        """Delegate to :func:`emit_main`."""
        return emit_main(ctx, bundle)

    # ------------------------------------------------------------------
    # Top-level orchestrator — mirrors the module-level emit()
    # ------------------------------------------------------------------

    def emit_all(self, bundle: ArtifactBundle) -> str:
        """Emit a complete Taichi source file from *bundle*.

        Delegates to :func:`emit`, which is the canonical top-level
        orchestrator.  Output is byte-for-byte identical to calling
        ``emit(bundle)`` directly.

        Parameters
        ----------
        bundle : ArtifactBundle
            Pipeline artifact containing the ProblemIR, ElementIR summary,
            contraction plans, and metadata.

        Returns
        -------
        str
            Self-contained Python/Taichi source file as a string.
        """
        return emit(bundle)
