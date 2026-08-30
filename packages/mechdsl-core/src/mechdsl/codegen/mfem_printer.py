"""MFEM C++ printer: ArtifactBundle → standalone ``.cpp`` file.

Support tier: **experimental** (see ``README.md`` Support tiers and
``dev/plans/recovery_plan_latex_contract.md`` Phase 5 (R4)).
The MVP-stable canonical compile path is Taichi only; this backend is
preserved in tree but is not part of the contract surface.

Emits a deterministic, syntactically valid C++ source file that uses
``mfem::ParNonlinearForm`` and a custom ``mfem::NonlinearFormIntegrator``
subclass to solve the same problem that the Taichi printer emits.

The MVP scope (Plan B §8, task P8-1):

* Hex8 only - other element types raise ``NotImplementedError``.
* :class:`~mechdsl.ir.mechanics_ir.DynamicsMode.STATIC` only - explicit
  central-difference emission is deferred to a post-MVP task.
* St. Venant-Kirchhoff material only.  Plastic / viscoplastic / damage
  models are legal in the IR but not yet supported by this emitter.
* Converts between MVP *tensorial* Voigt (unscaled shears) and MFEM
  *engineering* Voigt (``gamma_xy = 2 eps_xy``) via the dedicated helper
  :func:`voigt_tensorial_to_engineering` / :func:`voigt_engineering_to_tensorial`.

Parse-only verification: no local MFEM install is required.  Tests use
``clang-format`` (or a structural fallback) - see
``packages/mechdsl-core/tests/test_mfem_printer.py`` - and the emitted app
is compiled against MFEM in CI (Plan B task P8-3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from mechdsl.codegen._experimental import (
    ExperimentalBackendWarning,
    warn_experimental_backend_once,
)
from mechdsl.codegen.einsum_optimizer import family_emitters_enabled
from mechdsl.codegen.family_registry import Family

#: Programmatically-detectable experimental-backend marker.
#: Tooling and tests check ``mfem_printer.__experimental__ is True`` instead
#: of parsing docstrings.  See :mod:`mechdsl.codegen._experimental`.
__experimental__: bool = True

# ``ExperimentalBackendWarning`` is re-exported so callers can do
# ``from mechdsl.codegen.mfem_printer import ExperimentalBackendWarning``
# without reaching into the private :mod:`mechdsl.codegen._experimental`
# module.  Listing it here keeps autoflake from stripping the import.
__all__ = ["ExperimentalBackendWarning", "emit"]

_logger = logging.getLogger(__name__)

# One-shot warning flag: emit ExperimentalBackendWarning only once per session.
# Held in a dict so it can be flipped from the helper without ``global``.
_warn_state: dict = {"warned": False}

if TYPE_CHECKING:
    from collections.abc import Callable

    from mechdsl.codegen.artifact import ArtifactBundle

# ---------------------------------------------------------------------------
# Voigt convention conversion helpers (see 07-CONVENTIONS.md)
# ---------------------------------------------------------------------------

# Shear component indices in the shared [xx, yy, zz, xy, xz, yz] ordering.
_SHEAR_INDICES: tuple[int, ...] = (3, 4, 5)


# ---------------------------------------------------------------------------
# Per-family emitters (MFEM backend)
# ---------------------------------------------------------------------------
#
# MFEM emission is largely structural — the integrator-class skeleton is
# static boilerplate. The per-contraction shapes that vary are the
# deformation-gradient scatter, the force integrand, and the tangent
# contraction (all inside AssembleElementVector / AssembleElementGrad).
# Each helper owns one shape; the call sites below dispatch through the
# :data:`family_emitters` table so the happy path actually exercises the
# table (define-but-don't-call is a silent failure).


def _emit_family_displacement_gradient_mfem(ctx: EmissionContext) -> None:
    """Emit the ``F(i, j) += u_el(a, i) * DS(a, j)`` scatter (Hex8 MFEM).

    Family :class:`Family.DISPLACEMENT_GRADIENT`. The einsum exemplar is
    ``qaI,ai->qiI`` but MFEM loops over (a, i, j) flat rather than using
    a BLAS-style contraction.
    """
    ctx.emit("// F = I + grad(u)")
    ctx.emit("F = 0.0;")
    ctx.emit("for (int i = 0; i < dim; ++i) { F(i, i) = 1.0; }")
    ctx.emit("for (int a = 0; a < dof; ++a) {")
    with ctx.indent_block():
        ctx.emit("for (int i = 0; i < dim; ++i) {")
        with ctx.indent_block():
            ctx.emit("for (int j = 0; j < dim; ++j) {")
            with ctx.indent_block():
                ctx.emit("F(i, j) += u_el(a, i) * DS(a, j);")
            ctx.emit("}")
        ctx.emit("}")
    ctx.emit("}")


def _emit_family_force_integration_mfem(ctx: EmissionContext) -> None:
    """Emit the MFEM internal-force integrand ``elvect += w * FS^T . DS``.

    Family :class:`Family.FORCE_INTEGRATION`. Assumes ``FS``, ``DS``,
    ``w``, ``dof``, ``dim`` and ``elvect`` are in scope.
    """
    ctx.emit("for (int a = 0; a < dof; ++a) {")
    with ctx.indent_block():
        ctx.emit("for (int i = 0; i < dim; ++i) {")
        with ctx.indent_block():
            ctx.emit("double acc = 0.0;")
            ctx.emit("for (int j = 0; j < dim; ++j) { acc += FS(i, j) * DS(a, j); }")
            ctx.emit("elvect(a + i * dof) += w * acc;")
        ctx.emit("}")
    ctx.emit("}")


def _emit_family_material_tangent_contraction_mfem(ctx: EmissionContext) -> None:
    """Emit the ``elmat += w * B^T C_eng B`` sandwich (Hex8 MFEM).

    Family :class:`Family.MATERIAL_TANGENT_CONTRACTION`. Assumes ``B``,
    ``CB``, ``w``, ``ndof_total`` and ``elmat`` are in scope; ``CB`` has
    already been formed via ``Mult(C_eng, B, CB)``.
    """
    ctx.emit("for (int p = 0; p < ndof_total; ++p) {")
    with ctx.indent_block():
        ctx.emit("for (int r = 0; r < ndof_total; ++r) {")
        with ctx.indent_block():
            ctx.emit("double acc = 0.0;")
            ctx.emit("for (int v = 0; v < 6; ++v) { acc += B(v, p) * CB(v, r); }")
            ctx.emit("elmat(p, r) += w * acc;")
        ctx.emit("}")
    ctx.emit("}")


def _emit_family_fallback_mfem(ctx: EmissionContext) -> None:
    """MFEM fallback marker.  Unused on the MVP Hex8 + SVK happy path."""
    ctx.emit("// (P9-2 fallback: no MFEM template override)")


family_emitters: dict[Family, Callable[..., None]] = {
    Family.DISPLACEMENT_GRADIENT: _emit_family_displacement_gradient_mfem,
    Family.FORCE_INTEGRATION: _emit_family_force_integration_mfem,
    Family.MATERIAL_TANGENT_CONTRACTION: _emit_family_material_tangent_contraction_mfem,
    Family.TANGENT_DOUBLE_CONTRACTION: _emit_family_fallback_mfem,
    Family.RANK2_OUTER: _emit_family_fallback_mfem,
    Family.RANK2_SYMMETRIC_OUTER: _emit_family_fallback_mfem,
    Family.PUSH_FORWARD_RANK4: _emit_family_fallback_mfem,
    Family.FALLBACK: _emit_family_fallback_mfem,
}


def _dispatch_family(family: Family, ctx: EmissionContext, *args: object) -> bool:
    """Dispatch to :data:`family_emitters`; return ``True`` iff invoked."""
    if not family_emitters_enabled():
        return False
    emitter = family_emitters.get(family, _emit_family_fallback_mfem)
    if emitter is _emit_family_fallback_mfem:
        _logger.debug("mfem_printer: family %s routed to legacy body", family.name)
        return False
    emitter(ctx, *args)
    return True


def voigt_tensorial_to_engineering(v: np.ndarray) -> np.ndarray:
    """Convert MVP tensorial Voigt (unscaled shears) → MFEM engineering Voigt.

    MVP Voigt ordering is ``[xx, yy, zz, xy, xz, yz]`` with *tensorial* shears
    (``eps_xy`` stored as-is).  MFEM expects *engineering* shears
    (``gamma_xy = 2 eps_xy``).  This helper multiplies the shear components by 2.

    The mapping is its own inverse up to a factor - use
    :func:`voigt_engineering_to_tensorial` for the round trip.

    Parameters
    ----------
    v
        6-vector in tensorial Voigt ordering.

    Returns
    -------
    numpy.ndarray
        New 6-vector in engineering Voigt ordering.  Input is not mutated.
    """
    v = np.asarray(v, dtype=np.float64)
    if v.shape != (6,):
        raise ValueError(
            f"voigt_tensorial_to_engineering expects a shape-(6,) array, got {v.shape}"
        )
    out = v.copy()
    for idx in _SHEAR_INDICES:
        out[idx] *= 2.0
    return out


def voigt_engineering_to_tensorial(v: np.ndarray) -> np.ndarray:
    """Convert MFEM engineering Voigt → MVP tensorial Voigt (unscaled shears).

    Inverse of :func:`voigt_tensorial_to_engineering`.  Shear components are
    halved so that ``gamma_xy = 2 eps_xy`` becomes ``eps_xy`` again.

    Parameters
    ----------
    v
        6-vector in engineering Voigt ordering.

    Returns
    -------
    numpy.ndarray
        New 6-vector in tensorial Voigt ordering.  Input is not mutated.
    """
    v = np.asarray(v, dtype=np.float64)
    if v.shape != (6,):
        raise ValueError(
            f"voigt_engineering_to_tensorial expects a shape-(6,) array, got {v.shape}"
        )
    out = v.copy()
    for idx in _SHEAR_INDICES:
        out[idx] *= 0.5
    return out


# ---------------------------------------------------------------------------
# Emission helpers
# ---------------------------------------------------------------------------


@dataclass
class EmissionContext:
    """Tracks state during C++ emission.  Mirrors the Taichi printer's context.

    Indentation uses three spaces — the MFEM upstream style — so generated
    files format cleanly under ``clang-format`` with the default LLVM style.
    """

    indent: int = 0
    lines: list[str] = field(default_factory=list)

    def emit(self, line: str = "") -> None:
        if line:
            self.lines.append("   " * self.indent + line)
        else:
            self.lines.append("")

    def indent_block(self) -> _IndentCtx:
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


def _fmt_double(v: float) -> str:
    """Format a Python float as a C++ ``double`` literal deterministically."""
    s = f"{float(v):.17g}"
    # Ensure the literal is unambiguously a floating-point value for C++.
    if not any(c in s for c in ".eE") and "nan" not in s and "inf" not in s:
        s += ".0"
    return s


# ---------------------------------------------------------------------------
# Material-parameter extraction
# ---------------------------------------------------------------------------


def _lame_from_params(params: dict[str, Any]) -> tuple[float, float]:
    """Return the ``(lambda, mu)`` Lamé pair from an SVK parameter dict.

    Accepts either the ``(lambda, mu)`` pair or the engineering pair
    ``(E, nu)`` — the Taichi printer accepts both and this keeps the MFEM
    emitter symmetric with that behaviour.
    """
    if "lambda" in params and "mu" in params:
        return float(params["lambda"]), float(params["mu"])
    if "lam" in params and "mu" in params:
        return float(params["lam"]), float(params["mu"])
    if "E" in params and "nu" in params:
        E = float(params["E"])
        nu = float(params["nu"])
        lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
        mu = E / (2.0 * (1.0 + nu))
        return lam, mu
    raise ValueError(
        "SVK material requires either (E, nu) or (lambda, mu) parameters; "
        f"got keys {sorted(params)}."
    )


# ---------------------------------------------------------------------------
# Emission sections
# ---------------------------------------------------------------------------


def emit_preamble(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit the file header: includes, using declarations, SPDX-like banner."""
    material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    element_type = bundle.problem_ir_dict.get("element_type", "hex8")

    ctx.emit("// =====================================================================")
    ctx.emit("// MechDSL-generated MFEM application.")
    ctx.emit("//")
    ctx.emit(f"// Element type : {element_type}")
    ctx.emit(f"// Material     : {material_model}")
    ctx.emit("// Integrator   : mfem::NonlinearFormIntegrator subclass (SVK).")
    ctx.emit("// Dynamics     : static (implicit Newton via mfem::ParNonlinearForm).")
    ctx.emit("// Voigt        : MVP tensorial -> MFEM engineering (gamma = 2 eps).")
    ctx.emit("//")
    ctx.emit("// Do not edit by hand — regenerate via mechdsl.codegen.mfem_printer.emit.")
    ctx.emit("// =====================================================================")
    ctx.emit("")
    ctx.emit('#include "mfem.hpp"')
    ctx.emit("")
    ctx.emit("#include <cmath>")
    ctx.emit("#include <iostream>")
    ctx.emit("#include <memory>")
    ctx.emit("")
    ctx.emit("using namespace mfem;")
    ctx.emit("")


def emit_material_constants(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit Lamé-pair constants extracted from the SVK material parameters."""
    params = bundle.problem_ir_dict.get("material", {}).get("params", {})
    lam, mu = _lame_from_params(params)
    ctx.emit("// St. Venant-Kirchhoff material constants (Lamé pair).")
    ctx.emit(f"static constexpr double kLambda = {_fmt_double(lam)};")
    ctx.emit(f"static constexpr double kMu     = {_fmt_double(mu)};")
    ctx.emit("")


def emit_voigt_helpers(ctx: EmissionContext) -> None:
    """Emit inline helpers that bridge the two Voigt orderings."""
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("// Voigt conversion: MVP tensorial [xx, yy, zz, xy, xz, yz]")
    ctx.emit("//                   <-> MFEM engineering (gamma_xy = 2 eps_xy).")
    ctx.emit("// Shear entries are indices 3, 4, 5 in both orderings.")
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("static inline void TensorialToEngineering(const Vector &tensorial,")
    ctx.emit("                                          Vector &engineering)")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("engineering = tensorial;")
        ctx.emit("for (int k = 3; k < 6; ++k) { engineering(k) *= 2.0; }")
    ctx.emit("}")
    ctx.emit("")
    ctx.emit("static inline void EngineeringToTensorial(const Vector &engineering,")
    ctx.emit("                                          Vector &tensorial)")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("tensorial = engineering;")
        ctx.emit("for (int k = 3; k < 6; ++k) { tensorial(k) *= 0.5; }")
    ctx.emit("}")
    ctx.emit("")


def emit_constitutive_update(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit an SVK 2nd-PK stress and spatial tangent evaluator.

    The helper consumes the deformation gradient ``F`` (3x3) and writes the
    Green-Lagrange strain, the 2nd-PK stress, and the 6x6 tangent.  This keeps
    the integrator body short and predictable for downstream CI compile
    verification.
    """
    del bundle  # currently SVK-only; keep signature symmetric with Taichi printer.
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("// SVK constitutive update: F -> (E, S, C) in the reference configuration.")
    ctx.emit("// E is Green-Lagrange, S is 2nd Piola-Kirchhoff, C is the material")
    ctx.emit("// tangent in tensorial Voigt.  All tensors are 3x3 (or 6x6 for C).")
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("static void SvkConstitutiveUpdate(const DenseMatrix &F,")
    ctx.emit("                                  DenseMatrix &E,")
    ctx.emit("                                  DenseMatrix &S,")
    ctx.emit("                                  DenseMatrix &C_voigt)")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("// Green-Lagrange strain: E = 0.5 (F^T F - I).")
        ctx.emit("DenseMatrix FtF(3, 3);")
        ctx.emit("MultAtB(F, F, FtF);")
        ctx.emit("E.SetSize(3, 3);")
        ctx.emit("for (int i = 0; i < 3; ++i) {")
        with ctx.indent_block():
            ctx.emit("for (int j = 0; j < 3; ++j) {")
            with ctx.indent_block():
                ctx.emit("E(i, j) = 0.5 * (FtF(i, j) - (i == j ? 1.0 : 0.0));")
            ctx.emit("}")
        ctx.emit("}")
        ctx.emit("")
        ctx.emit("// S = lambda tr(E) I + 2 mu E.")
        ctx.emit("const double trE = E(0, 0) + E(1, 1) + E(2, 2);")
        ctx.emit("S.SetSize(3, 3);")
        ctx.emit("for (int i = 0; i < 3; ++i) {")
        with ctx.indent_block():
            ctx.emit("for (int j = 0; j < 3; ++j) {")
            with ctx.indent_block():
                ctx.emit("S(i, j) = 2.0 * kMu * E(i, j);")
            ctx.emit("}")
            ctx.emit("S(i, i) += kLambda * trE;")
        ctx.emit("}")
        ctx.emit("")
        ctx.emit("// Material tangent C in tensorial Voigt [xx, yy, zz, xy, xz, yz].")
        ctx.emit("C_voigt.SetSize(6, 6);")
        ctx.emit("C_voigt = 0.0;")
        ctx.emit("for (int i = 0; i < 3; ++i) {")
        with ctx.indent_block():
            ctx.emit("for (int j = 0; j < 3; ++j) {")
            with ctx.indent_block():
                ctx.emit("C_voigt(i, j) += kLambda;")
            ctx.emit("}")
            ctx.emit("C_voigt(i, i) += 2.0 * kMu;")
        ctx.emit("}")
        ctx.emit("for (int k = 3; k < 6; ++k) { C_voigt(k, k) = 2.0 * kMu; }")
    ctx.emit("}")
    ctx.emit("")


def emit_force_integrator(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit the ``NonlinearFormIntegrator`` subclass.

    Residual comes from ``AssembleElementVector`` and the consistent tangent
    from ``AssembleElementGrad``.  The implementation is a deliberately simple
    Hex8/SVK wiring — end-to-end compile + solve verification lands in P8-3.
    """
    del bundle
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("// NonlinearFormIntegrator that implements residual + tangent for the")
    ctx.emit("// MechDSL problem on a single (Hex8) element.")
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("class MechDSLSaintVenantKirchhoff : public NonlinearFormIntegrator")
    ctx.emit("{")
    ctx.emit("public:")
    with ctx.indent_block():
        ctx.emit("MechDSLSaintVenantKirchhoff() = default;")
        ctx.emit("")
        ctx.emit("virtual void AssembleElementVector(const FiniteElement &el,")
        ctx.emit("                                   ElementTransformation &Ttr,")
        ctx.emit("                                   const Vector &elfun,")
        ctx.emit("                                   Vector &elvect) override;")
        ctx.emit("")
        ctx.emit("virtual void AssembleElementGrad(const FiniteElement &el,")
        ctx.emit("                                 ElementTransformation &Ttr,")
        ctx.emit("                                 const Vector &elfun,")
        ctx.emit("                                 DenseMatrix &elmat) override;")
    ctx.emit("};")
    ctx.emit("")
    ctx.emit("void MechDSLSaintVenantKirchhoff::AssembleElementVector(")
    ctx.emit("   const FiniteElement &el, ElementTransformation &Ttr,")
    ctx.emit("   const Vector &elfun, Vector &elvect)")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("const int dof = el.GetDof();")
        ctx.emit("const int dim = el.GetDim();")
        ctx.emit("elvect.SetSize(dof * dim);")
        ctx.emit("elvect = 0.0;")
        ctx.emit("")
        ctx.emit("DenseMatrix DSh(dof, dim);")
        ctx.emit("DenseMatrix DS(dof, dim);")
        ctx.emit("DenseMatrix Jinv(dim, dim);")
        ctx.emit("DenseMatrix F(dim, dim);")
        ctx.emit("DenseMatrix E(dim, dim);")
        ctx.emit("DenseMatrix S(dim, dim);")
        ctx.emit("DenseMatrix C_voigt(6, 6);")
        ctx.emit("DenseMatrix u_el(dof, dim);")
        ctx.emit("for (int a = 0; a < dof; ++a) {")
        with ctx.indent_block():
            ctx.emit("for (int i = 0; i < dim; ++i) { u_el(a, i) = elfun(a + i * dof); }")
        ctx.emit("}")
        ctx.emit("")
        ctx.emit("const IntegrationRule &ir = IntRules.Get(el.GetGeomType(), 2 * el.GetOrder());")
        ctx.emit("for (int q = 0; q < ir.GetNPoints(); ++q) {")
        with ctx.indent_block():
            ctx.emit("const IntegrationPoint &ip = ir.IntPoint(q);")
            ctx.emit("Ttr.SetIntPoint(&ip);")
            ctx.emit("CalcInverse(Ttr.Jacobian(), Jinv);")
            ctx.emit("el.CalcDShape(ip, DSh);")
            ctx.emit("Mult(DSh, Jinv, DS);")
            ctx.emit("")
            # DISPLACEMENT_GRADIENT dispatch ('qaI,ai->qiI' shape).
            if not _dispatch_family(Family.DISPLACEMENT_GRADIENT, ctx):
                ctx.emit("// F = I + grad(u)")
                ctx.emit("F = 0.0;")
                ctx.emit("for (int i = 0; i < dim; ++i) { F(i, i) = 1.0; }")
                ctx.emit("for (int a = 0; a < dof; ++a) {")
                with ctx.indent_block():
                    ctx.emit("for (int i = 0; i < dim; ++i) {")
                    with ctx.indent_block():
                        ctx.emit("for (int j = 0; j < dim; ++j) {")
                        with ctx.indent_block():
                            ctx.emit("F(i, j) += u_el(a, i) * DS(a, j);")
                        ctx.emit("}")
                    ctx.emit("}")
                ctx.emit("}")
            ctx.emit("")
            ctx.emit("SvkConstitutiveUpdate(F, E, S, C_voigt);")
            ctx.emit("")
            ctx.emit("// Internal force: B^T S dV in total-Lagrangian form.")
            ctx.emit("const double w = ip.weight * Ttr.Weight();")
            ctx.emit("DenseMatrix FS(dim, dim);")
            ctx.emit("Mult(F, S, FS);")
            # FORCE_INTEGRATION dispatch ('qaI,qiI->qai' shape).
            if not _dispatch_family(Family.FORCE_INTEGRATION, ctx):
                ctx.emit("for (int a = 0; a < dof; ++a) {")
                with ctx.indent_block():
                    ctx.emit("for (int i = 0; i < dim; ++i) {")
                    with ctx.indent_block():
                        ctx.emit("double acc = 0.0;")
                        ctx.emit("for (int j = 0; j < dim; ++j) { acc += FS(i, j) * DS(a, j); }")
                        ctx.emit("elvect(a + i * dof) += w * acc;")
                    ctx.emit("}")
                ctx.emit("}")
        ctx.emit("}")
    ctx.emit("}")
    ctx.emit("")


def emit_tangent_integrator(ctx: EmissionContext) -> None:
    """Emit the consistent tangent via a B^T C_eng B accumulation.

    The emitted kernel builds the engineering-Voigt strain-displacement
    operator ``B`` (6 x dof*dim) per quadrature point, constructs the full
    6x6 engineering-Voigt material tangent ``C_eng`` directly from the
    Lamé pair — so shear rows/cols (indices 3, 4, 5) are preserved — and
    accumulates ``elmat += w * det(J) * B^T C_eng B``.

    The small-strain ``B`` operator is used here; the geometric (initial-
    stress) contribution is left to the base-class / P8-3 compile pass.
    All nested loops close before ``elmat`` is written, so every index
    used in the write is in scope.
    """
    ctx.emit("void MechDSLSaintVenantKirchhoff::AssembleElementGrad(")
    ctx.emit("   const FiniteElement &el, ElementTransformation &Ttr,")
    ctx.emit("   const Vector &elfun, DenseMatrix &elmat)")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("const int dof = el.GetDof();")
        ctx.emit("const int dim = el.GetDim();")
        ctx.emit("const int ndof_total = dof * dim;")
        ctx.emit("elmat.SetSize(ndof_total);")
        ctx.emit("elmat = 0.0;")
        ctx.emit("")
        ctx.emit("DenseMatrix DSh(dof, dim);")
        ctx.emit("DenseMatrix DS(dof, dim);")
        ctx.emit("DenseMatrix Jinv(dim, dim);")
        ctx.emit("")
        ctx.emit("// Engineering-Voigt material tangent C_eng (6x6): built directly")
        ctx.emit("// from the Lamé pair so shear rows/cols (3, 4, 5) are preserved.")
        ctx.emit("// Layout [xx, yy, zz, xy, xz, yz]; shears use engineering strain.")
        ctx.emit("DenseMatrix C_eng(6, 6);")
        ctx.emit("C_eng = 0.0;")
        ctx.emit("for (int i = 0; i < 3; ++i) {")
        with ctx.indent_block():
            ctx.emit("for (int j = 0; j < 3; ++j) { C_eng(i, j) = kLambda; }")
            ctx.emit("C_eng(i, i) += 2.0 * kMu;")
        ctx.emit("}")
        ctx.emit("C_eng(3, 3) = kMu;")
        ctx.emit("C_eng(4, 4) = kMu;")
        ctx.emit("C_eng(5, 5) = kMu;")
        ctx.emit("")
        ctx.emit("// Strain-displacement operator B in engineering Voigt: 6 x ndof_total.")
        ctx.emit("// Column index for node a, spatial dim i is (a + i * dof).")
        ctx.emit("DenseMatrix B(6, ndof_total);")
        ctx.emit("DenseMatrix CB(6, ndof_total);")
        ctx.emit("")
        ctx.emit("const IntegrationRule &ir = IntRules.Get(el.GetGeomType(), 2 * el.GetOrder());")
        ctx.emit("for (int q = 0; q < ir.GetNPoints(); ++q) {")
        with ctx.indent_block():
            ctx.emit("const IntegrationPoint &ip = ir.IntPoint(q);")
            ctx.emit("Ttr.SetIntPoint(&ip);")
            ctx.emit("CalcInverse(Ttr.Jacobian(), Jinv);")
            ctx.emit("el.CalcDShape(ip, DSh);")
            ctx.emit("Mult(DSh, Jinv, DS);")
            ctx.emit("")
            ctx.emit("// Assemble B at this quadrature point.")
            ctx.emit("B = 0.0;")
            ctx.emit("for (int a = 0; a < dof; ++a) {")
            with ctx.indent_block():
                ctx.emit("const double dNdx = DS(a, 0);")
                ctx.emit("const double dNdy = DS(a, 1);")
                ctx.emit("const double dNdz = DS(a, 2);")
                ctx.emit("const int cx = a + 0 * dof;")
                ctx.emit("const int cy = a + 1 * dof;")
                ctx.emit("const int cz = a + 2 * dof;")
                ctx.emit("// Normal strains (rows 0..2).")
                ctx.emit("B(0, cx) = dNdx;")
                ctx.emit("B(1, cy) = dNdy;")
                ctx.emit("B(2, cz) = dNdz;")
                ctx.emit("// Engineering shears (rows 3..5): gamma_xy, gamma_xz, gamma_yz.")
                ctx.emit("B(3, cx) = dNdy;  B(3, cy) = dNdx;")
                ctx.emit("B(4, cx) = dNdz;  B(4, cz) = dNdx;")
                ctx.emit("B(5, cy) = dNdz;  B(5, cz) = dNdy;")
            ctx.emit("}")
            ctx.emit("")
            ctx.emit("// CB = C_eng * B, then elmat += w * B^T * CB.")
            ctx.emit("Mult(C_eng, B, CB);")
            ctx.emit("const double w = ip.weight * Ttr.Weight();")
            # MATERIAL_TANGENT_CONTRACTION dispatch
            # ('qaI,qiIjJ,qbJ->qaibj' collapsed to Voigt B^T C_eng B).
            if not _dispatch_family(Family.MATERIAL_TANGENT_CONTRACTION, ctx):
                ctx.emit("for (int p = 0; p < ndof_total; ++p) {")
                with ctx.indent_block():
                    ctx.emit("for (int r = 0; r < ndof_total; ++r) {")
                    with ctx.indent_block():
                        ctx.emit("double acc = 0.0;")
                        ctx.emit("for (int v = 0; v < 6; ++v) { acc += B(v, p) * CB(v, r); }")
                        ctx.emit("elmat(p, r) += w * acc;")
                    ctx.emit("}")
                ctx.emit("}")
            ctx.emit("")
            ctx.emit("// NOTE: geometric (initial-stress) tangent contribution is")
            ctx.emit("// Deferred to Plan B §B8 P8-3 (full compile + verification pass).")
        ctx.emit("}")
    ctx.emit("}")
    ctx.emit("")


def emit_main(ctx: EmissionContext, bundle: ArtifactBundle) -> None:
    """Emit the ``main`` that wires a minimal MPI-parallel Newton solve."""
    del bundle
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("// MPI-parallel driver.  Uses mfem::ParNonlinearForm so the problem")
    ctx.emit("// distributes across ranks out of the box.  Mesh + BC wiring is left")
    ctx.emit("// deliberately skeletal — P8-3 extends it with a real mesh reader.")
    ctx.emit("// ---------------------------------------------------------------------")
    ctx.emit("int main(int argc, char *argv[])")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("Mpi::Init(argc, argv);")
        ctx.emit("Hypre::Init();")
        ctx.emit("")
        ctx.emit('const char *mesh_file = "../data/beam-hex.mesh";')
        ctx.emit("int order = 1;")
        ctx.emit("int ref_levels = 0;")
        ctx.emit("")
        ctx.emit("OptionsParser args(argc, argv);")
        ctx.emit('args.AddOption(&mesh_file, "-m", "--mesh", "Mesh file to use.");')
        ctx.emit('args.AddOption(&order, "-o", "--order", "Finite element order.");')
        ctx.emit('args.AddOption(&ref_levels, "-r", "--refine",')
        ctx.emit('               "Number of times to refine the mesh uniformly.");')
        ctx.emit("args.Parse();")
        ctx.emit("if (!args.Good()) { args.PrintUsage(std::cout); return 1; }")
        ctx.emit("")
        ctx.emit("Mesh serial_mesh(mesh_file, 1, 1);")
        ctx.emit("for (int l = 0; l < ref_levels; ++l) { serial_mesh.UniformRefinement(); }")
        ctx.emit("ParMesh pmesh(MPI_COMM_WORLD, serial_mesh);")
        ctx.emit("serial_mesh.Clear();")
        ctx.emit("")
        ctx.emit("H1_FECollection fec(order, pmesh.Dimension());")
        ctx.emit(
            "ParFiniteElementSpace fespace(&pmesh, &fec, pmesh.Dimension(), Ordering::byNODES);"
        )
        ctx.emit("")
        ctx.emit("// NOTE: skeletal essential-BC setup — full boundary-condition")
        ctx.emit("// wiring (per-attribute Dirichlet tags, traction / Neumann loads,")
        ctx.emit("// inhomogeneous prescribed displacements) is Deferred to Plan B")
        ctx.emit("// §B8 P8-3.  The present all-attributes-fixed path is sufficient")
        ctx.emit("// for the parse-check + compile smoke-test in P8-3.")
        ctx.emit("Array<int> ess_tdof_list;")
        ctx.emit("if (pmesh.bdr_attributes.Size()) {")
        with ctx.indent_block():
            ctx.emit("Array<int> ess_bdr(pmesh.bdr_attributes.Max());")
            ctx.emit("ess_bdr = 1;")
            ctx.emit("fespace.GetEssentialTrueDofs(ess_bdr, ess_tdof_list);")
        ctx.emit("}")
        ctx.emit("")
        ctx.emit("ParNonlinearForm nlf(&fespace);")
        ctx.emit("nlf.AddDomainIntegrator(new MechDSLSaintVenantKirchhoff());")
        ctx.emit("nlf.SetEssentialTrueDofs(ess_tdof_list);")
        ctx.emit("")
        ctx.emit("ParGridFunction u(&fespace);")
        ctx.emit("u = 0.0;")
        ctx.emit("Vector U;")
        ctx.emit("u.GetTrueDofs(U);")
        ctx.emit("")
        ctx.emit("GMRESSolver gmres(MPI_COMM_WORLD);")
        ctx.emit("gmres.SetRelTol(1e-8);")
        ctx.emit("gmres.SetMaxIter(500);")
        ctx.emit("gmres.SetPrintLevel(0);")
        ctx.emit("")
        ctx.emit("NewtonSolver newton(MPI_COMM_WORLD);")
        ctx.emit("newton.SetOperator(nlf);")
        ctx.emit("newton.SetSolver(gmres);")
        ctx.emit("newton.SetRelTol(1e-8);")
        ctx.emit("newton.SetMaxIter(25);")
        ctx.emit("newton.SetPrintLevel(1);")
        ctx.emit("")
        ctx.emit("// NOTE: zero RHS placeholder — external-load plumbing is Deferred")
        ctx.emit("// to Plan B §B8 P8-3.  Size the RHS to match the true-DOF vector so")
        ctx.emit("// NewtonSolver::Mult sees a well-formed operand.")
        ctx.emit("Vector zero(U.Size());")
        ctx.emit("zero = 0.0;")
        ctx.emit("newton.Mult(zero, U);")
        ctx.emit("u.SetFromTrueDofs(U);")
        ctx.emit("")
        ctx.emit('if (Mpi::Root()) { std::cout << "MechDSL-MFEM solve complete." << std::endl; }')
        ctx.emit("return 0;")
    ctx.emit("}")
    ctx.emit("")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def emit(bundle: ArtifactBundle) -> str:
    """Emit the complete MFEM C++ source file from an :class:`ArtifactBundle`.

    Parameters
    ----------
    bundle
        Pipeline artifact produced by the mechdsl lowering + codegen stack.

    Returns
    -------
    str
        A self-contained C++ source string.

    Raises
    ------
    NotImplementedError
        When the bundle requires an element type or a dynamics mode outside the
        MVP scope (Plan B §8).
    ValueError
        When the bundle carries a material model the MFEM emitter does not
        yet support.
    """
    warn_experimental_backend_once(_warn_state, "MFEM")

    problem_ir_dict = bundle.problem_ir_dict

    element_type = problem_ir_dict.get("element_type", "hex8")
    if element_type != "hex8":
        raise NotImplementedError(
            f"MFEM printer supports Hex8 only for MVP — {element_type} is planned "
            "for post-MVP (Plan B §B5 element extensions)."
        )

    dynamics_mode = problem_ir_dict.get("dynamics_mode", "static")
    if dynamics_mode == "explicit":
        raise NotImplementedError("MFEM EXPLICIT codegen is planned for post-MVP")
    if dynamics_mode != "static":
        raise NotImplementedError(
            f"Unknown dynamics mode {dynamics_mode!r}; MFEM printer currently supports "
            "only 'static'."
        )

    material_model = problem_ir_dict.get("material", {}).get("model", "svk")
    if material_model != "svk":
        raise ValueError(
            f"MFEM emitter currently supports the SVK material only; got "
            f"{material_model!r}. Plastic/damage MFEM integrators are planned for "
            "a post-MVP task."
        )

    ctx = EmissionContext()
    emit_preamble(ctx, bundle)
    emit_material_constants(ctx, bundle)
    emit_voigt_helpers(ctx)
    emit_constitutive_update(ctx, bundle)
    emit_force_integrator(ctx, bundle)
    emit_tangent_integrator(ctx)
    emit_main(ctx, bundle)
    return ctx.get_source()


# ---------------------------------------------------------------------------
# CMakeLists template helpers
# ---------------------------------------------------------------------------


_TEMPLATE_DIR = Path(__file__).resolve().parent / "mfem_template"


def _cmakelists_template_path() -> Path:
    """Resolve the shipped CMakeLists.txt template path."""
    return _TEMPLATE_DIR / "CMakeLists.txt"


def emit_cmakelists(bundle: ArtifactBundle | None = None) -> str:
    """Return the CMakeLists.txt template populated for *bundle*.

    The template is intentionally hand-rolled (no Jinja dependency) and only
    carries a single placeholder — the executable name — so the emitter stays
    dependency-free.

    Parameters
    ----------
    bundle
        Optional bundle.  When provided, the executable name is set to
        ``mechdsl_mfem_<element>_<material>`` for readability; otherwise the
        generic ``mechdsl_mfem_app`` name is kept.
    """
    text = _cmakelists_template_path().read_text(encoding="utf-8")
    if bundle is None:
        return text
    element = bundle.problem_ir_dict.get("element_type", "hex8")
    material = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
    exe_name = f"mechdsl_mfem_{element}_{material}"
    return text.replace("@MECHDSL_EXE_NAME@", exe_name)
