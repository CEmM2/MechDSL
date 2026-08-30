"""MOOSE backend code printer — ArtifactBundle -> ComputeStressBase subclass.

Support tier: **experimental** (see ``README.md`` Support tiers and
``dev/plans/recovery_plan_latex_contract.md`` Phase 5 (R4)).
The MVP-stable canonical compile path is Taichi only; this backend is
preserved in tree but is not part of the contract surface.

Plan B Phase 8, Task P8-2.  Emits a MOOSE-flavoured C++ material class that
subclasses ``ComputeStressBase`` and maps MVP tensor types to MOOSE's
``RankTwoTensor`` / ``RankFourTensor``.  The printer also fills a shipped
``moose_template/input_template.i`` deck so users get a ready-to-run tension
test wired to the emitted material.

Supported subset (MVP)
----------------------
* Element type: Hex8 only (Plan B P5 extends to tet4/tet10/hex20 but the MOOSE
  backend is MVP-scoped to hex8 for now; other types raise
  :class:`NotImplementedError`).
* Dynamics: :attr:`mechdsl.ir.mechanics_ir.DynamicsMode.STATIC`.  Explicit
  dynamics via MOOSE ``CentralDifference`` is deferred until a later phase.
* Voigt layout: MVP tensorial ordering ``[xx, yy, zz, xy, xz, yz]`` with
  unscaled shears.  MOOSE's ``RankTwoTensor`` is a natural 3x3 object so the
  emission path converts tensorial-Voigt back to a full 3x3 layout.

Entry points
------------
:func:`emit`
    Returns a dict ``{"cpp": str, "header": str}``.  MOOSE material classes
    always ship as a ``.h`` declaration + ``.C`` implementation pair, so the
    printer returns both.  Tests and downstream callers select either key.

:func:`emit_input_file`
    Returns the filled ``.i`` deck (a string) loaded from
    ``moose_template/input_template.i``.

:func:`to_rank_two_tensor`, :func:`from_rank_two_tensor`
    Tensorial-Voigt <-> 3x3 round-trip helpers for use in tests and future
    verification harnesses.

:func:`to_rank_four_tensor`, :func:`from_rank_four_tensor`
    Full symmetric 3x3x3x3 <-> MOOSE C(i,j,k,l) round-trip helpers.
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
#: Tooling and tests check ``moose_printer.__experimental__ is True`` instead
#: of parsing docstrings.  See :mod:`mechdsl.codegen._experimental`.
__experimental__: bool = True

# ``ExperimentalBackendWarning`` is re-exported so callers can do
# ``from mechdsl.codegen.moose_printer import ExperimentalBackendWarning``
# without reaching into the private :mod:`mechdsl.codegen._experimental`
# module.  Listing it in ``__all__`` keeps autoflake from stripping the import.
__all__ = ["ExperimentalBackendWarning", "emit", "emit_input_file"]

_logger = logging.getLogger(__name__)

# One-shot warning flag: emit ExperimentalBackendWarning only once per session.
# Held in a dict so it can be flipped from the helper without ``global``.
_warn_state: dict = {"warned": False}

if TYPE_CHECKING:
    from collections.abc import Callable

    from mechdsl.codegen.artifact import ArtifactBundle


# ---------------------------------------------------------------------------
# Per-family emitters (MOOSE backend)
# ---------------------------------------------------------------------------
#
# The MOOSE emission path is action-driven: ``ComputeStressBase`` writes
# ``_stress[_qp]`` and ``_Jacobian_mult[_qp]`` that the
# ``TensorMechanicsAction`` consumes — the printer never spells out a
# per-node internal-force loop. The two contractions the printer *does*
# spell out are the stress-from-strain sandwich (material-tangent) and
# the full 4th-order tangent assembly. Each gets its own family emitter
# below so the dispatch table is exercised at generation time.


def _emit_family_material_tangent_contraction_moose(ctx: EmissionContext) -> None:
    """Emit the MOOSE stress update ``stress = 2 mu E + lam tr(E) I``.

    Family :class:`Family.MATERIAL_TANGENT_CONTRACTION` (per the registry
    this covers the SVK PK2 form collapsed for MOOSE). Assumes ``E``,
    ``trE``, ``stress``, ``_mu``, ``_lambda`` are in scope.
    """
    ctx.emit("for (unsigned int i = 0; i < 3; ++i)")
    with ctx.indent_block():
        ctx.emit("for (unsigned int j = 0; j < 3; ++j)")
        with ctx.indent_block():
            ctx.emit("stress(i, j) = 2.0 * _mu * E(i, j);")
    ctx.emit("for (unsigned int i = 0; i < 3; ++i)")
    with ctx.indent_block():
        ctx.emit("stress(i, i) += _lambda * trE;")


def _emit_family_tangent_double_contraction_moose(ctx: EmissionContext) -> None:
    """Emit the RankFourTensor ``C(i,j,k,l)`` assembly (SVK tangent).

    Family :class:`Family.TANGENT_DOUBLE_CONTRACTION`. In the MOOSE
    action-driven path the 4th-order tangent is assembled and written to
    ``_Jacobian_mult[_qp]`` — the actual ``C : eps`` contraction happens
    downstream inside the framework.
    """
    ctx.emit("for (unsigned int i = 0; i < 3; ++i)")
    with ctx.indent_block():
        ctx.emit("for (unsigned int j = 0; j < 3; ++j)")
        with ctx.indent_block():
            ctx.emit("for (unsigned int k = 0; k < 3; ++k)")
            with ctx.indent_block():
                ctx.emit("for (unsigned int l = 0; l < 3; ++l)")
                with ctx.indent_block():
                    ctx.emit("{")
                    with ctx.indent_block():
                        ctx.emit("Real val = 0.0;")
                        ctx.emit("if (i == j && k == l) val += _lambda;")
                        ctx.emit("if (i == k && j == l) val += _mu;")
                        ctx.emit("if (i == l && j == k) val += _mu;")
                        ctx.emit("C(i, j, k, l) = val;")
                    ctx.emit("}")


def _emit_family_fallback_moose(ctx: EmissionContext) -> None:
    """MOOSE fallback marker. Unused on the SVK Hex8 happy path."""
    ctx.emit("// (P9-2 fallback: no MOOSE template override)")


family_emitters: dict[Family, Callable[..., None]] = {
    Family.MATERIAL_TANGENT_CONTRACTION: _emit_family_material_tangent_contraction_moose,
    Family.TANGENT_DOUBLE_CONTRACTION: _emit_family_tangent_double_contraction_moose,
    Family.DISPLACEMENT_GRADIENT: _emit_family_fallback_moose,
    Family.FORCE_INTEGRATION: _emit_family_fallback_moose,
    Family.RANK2_OUTER: _emit_family_fallback_moose,
    Family.RANK2_SYMMETRIC_OUTER: _emit_family_fallback_moose,
    Family.PUSH_FORWARD_RANK4: _emit_family_fallback_moose,
    Family.FALLBACK: _emit_family_fallback_moose,
}


def _dispatch_family(family: Family, ctx: EmissionContext, *args: object) -> bool:
    """Dispatch to :data:`family_emitters`; return ``True`` iff invoked."""
    if not family_emitters_enabled():
        return False
    emitter = family_emitters.get(family, _emit_family_fallback_moose)
    if emitter is _emit_family_fallback_moose:
        _logger.debug("moose_printer: family %s routed to legacy body", family.name)
        return False
    emitter(ctx, *args)
    return True


# ---------------------------------------------------------------------------
# Voigt <-> RankTwoTensor / RankFourTensor mapping helpers
# ---------------------------------------------------------------------------

# MVP tensorial Voigt ordering: [xx, yy, zz, xy, xz, yz], unscaled shears.
# Matches 07-CONVENTIONS.md.
_VOIGT_INDEX: tuple[tuple[int, int], ...] = (
    (0, 0),  # xx
    (1, 1),  # yy
    (2, 2),  # zz
    (0, 1),  # xy
    (0, 2),  # xz
    (1, 2),  # yz
)


def to_rank_two_tensor(voigt: np.ndarray) -> np.ndarray:
    """Expand a length-6 tensorial-Voigt vector to a symmetric 3x3 matrix.

    MOOSE's ``RankTwoTensor`` is a general 3x3 object; there is no Voigt
    packing on the MOOSE side.  This helper is the inverse of
    :func:`from_rank_two_tensor`.
    """
    voigt = np.asarray(voigt, dtype=np.float64)
    if voigt.shape != (6,):
        raise ValueError(f"Expected length-6 Voigt vector, got shape {voigt.shape}")
    out = np.zeros((3, 3), dtype=np.float64)
    for v, (i, j) in enumerate(_VOIGT_INDEX):
        out[i, j] = voigt[v]
        out[j, i] = voigt[v]
    return out


def from_rank_two_tensor(tensor: np.ndarray) -> np.ndarray:
    """Pack a symmetric 3x3 matrix into a length-6 tensorial-Voigt vector.

    The input is assumed symmetric; the helper reads the upper-triangular
    entries following the MVP ``[xx, yy, zz, xy, xz, yz]`` ordering.
    """
    tensor = np.asarray(tensor, dtype=np.float64)
    if tensor.shape != (3, 3):
        raise ValueError(f"Expected 3x3 tensor, got shape {tensor.shape}")
    out = np.zeros(6, dtype=np.float64)
    for v, (i, j) in enumerate(_VOIGT_INDEX):
        out[v] = tensor[i, j]
    return out


def to_rank_four_tensor(c66: np.ndarray) -> np.ndarray:
    """Expand a 6x6 tensorial-Voigt tangent to a 3x3x3x3 with minor symmetries.

    Output matches MOOSE's ``RankFourTensor`` ``C(i,j,k,l)`` layout.  The
    helper enforces both minor symmetries: ``C[i,j,k,l] == C[j,i,k,l] ==
    C[i,j,l,k]``.
    """
    c66 = np.asarray(c66, dtype=np.float64)
    if c66.shape != (6, 6):
        raise ValueError(f"Expected 6x6 Voigt tangent, got shape {c66.shape}")
    c3333 = np.zeros((3, 3, 3, 3), dtype=np.float64)
    for a, (i, j) in enumerate(_VOIGT_INDEX):
        for b, (k, m) in enumerate(_VOIGT_INDEX):
            val = c66[a, b]
            c3333[i, j, k, m] = val
            c3333[j, i, k, m] = val
            c3333[i, j, m, k] = val
            c3333[j, i, m, k] = val
    return c3333


def from_rank_four_tensor(c3333: np.ndarray) -> np.ndarray:
    """Contract a 3x3x3x3 RankFourTensor layout to a 6x6 tensorial-Voigt matrix.

    The helper assumes minor symmetries and reads only the canonical Voigt
    entries (``(i,j)`` with ``i <= j`` under the MVP ordering).
    """
    c3333 = np.asarray(c3333, dtype=np.float64)
    if c3333.shape != (3, 3, 3, 3):
        raise ValueError(f"Expected 3x3x3x3 tensor, got shape {c3333.shape}")
    out = np.zeros((6, 6), dtype=np.float64)
    for a, (i, j) in enumerate(_VOIGT_INDEX):
        for b, (k, m) in enumerate(_VOIGT_INDEX):
            out[a, b] = c3333[i, j, k, m]
    return out


# ---------------------------------------------------------------------------
# Emission context and helpers
# ---------------------------------------------------------------------------


@dataclass
class EmissionContext:
    """Tracks state while emitting C++ source line by line."""

    indent: int = 0
    lines: list[str] = field(default_factory=list)

    def emit(self, line: str = "") -> None:
        if line:
            self.lines.append("  " * self.indent + line)
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


# ---------------------------------------------------------------------------
# Bundle unpacking
# ---------------------------------------------------------------------------


def _material_class_name(model: str) -> str:
    """Turn a material model identifier into a MOOSE-style class name."""
    mapping = {
        "svk": "MechDSLSaintVenantKirchhoff",
        "j2_power_law": "MechDSLJ2PowerLaw",
        "perzyna": "MechDSLPerzyna",
        "johnson_cook": "MechDSLJohnsonCook",
        "neo_hookean": "MechDSLNeoHookean",
        "mooney_rivlin": "MechDSLMooneyRivlin",
        "ogden": "MechDSLOgden",
        "hgo": "MechDSLHGO",
        "lemaitre": "MechDSLLemaitre",
    }
    return mapping.get(model, f"MechDSLMaterial_{model}")


def _extract_material(bundle: ArtifactBundle) -> tuple[str, dict[str, Any]]:
    material = bundle.problem_ir_dict.get("material", {})
    model = str(material.get("model", "svk"))
    params = dict(material.get("params", {}))
    return model, params


def _guard_supported(bundle: ArtifactBundle) -> None:
    """Raise :class:`NotImplementedError` for unsupported bundle shapes.

    The MOOSE backend is MVP-scoped to Hex8 + static dynamics.  Any other
    combination should fail loudly with a pointer to the plan phase that
    would add support.
    """
    element_type = bundle.element_ir_summary.get("element_type")
    if element_type != "hex8":
        raise NotImplementedError(
            f"MOOSE printer supports element_type='hex8' only, got {element_type!r}. "
            "Other element families are planned for a later Plan B phase."
        )

    dynamics = bundle.problem_ir_dict.get("dynamics_mode", "static")
    if dynamics != "static":
        raise NotImplementedError(
            f"MOOSE printer supports DynamicsMode.STATIC only, got {dynamics!r}. "
            "Explicit MOOSE dynamics (central difference) is planned for a "
            "later Plan B phase."
        )


# ---------------------------------------------------------------------------
# Header emission (.h)
# ---------------------------------------------------------------------------


def emit_header(bundle: ArtifactBundle) -> str:
    """Emit the ``.h`` declaration for the MOOSE material class."""
    _guard_supported(bundle)
    model, params = _extract_material(bundle)
    class_name = _material_class_name(model)

    ctx = EmissionContext()
    ctx.emit(f"// Auto-generated by mechdsl.codegen.moose_printer (model={model}).")
    ctx.emit("// Do not edit by hand — regenerate from the ArtifactBundle.")
    ctx.emit("#pragma once")
    ctx.emit()
    ctx.emit('#include "ComputeStressBase.h"')
    ctx.emit('#include "RankTwoTensor.h"')
    ctx.emit('#include "RankFourTensor.h"')
    ctx.emit()
    ctx.emit(f"class {class_name};")
    ctx.emit()
    ctx.emit("template <>")
    ctx.emit(f"InputParameters validParams<{class_name}>();")
    ctx.emit()
    ctx.emit(f"class {class_name} : public ComputeStressBase")
    ctx.emit("{")
    ctx.emit("public:")
    with ctx.indent_block():
        ctx.emit(f"{class_name}(const InputParameters & parameters);")
        ctx.emit(f"virtual ~{class_name}() = default;")
    ctx.emit()
    ctx.emit("protected:")
    with ctx.indent_block():
        ctx.emit("virtual void computeQpStress() override;")
        ctx.emit("virtual void computeQpJacobian();")
        ctx.emit()
        ctx.emit("// Material parameters parsed from the input deck.")
        ctx.emit("const Real _youngs_modulus;")
        ctx.emit("const Real _poissons_ratio;")
        for p_name in sorted(params.keys()):
            if p_name in ("E", "nu"):
                # E/nu are the canonical ones above; skip duplicate decl.
                continue
            ctx.emit(f"const Real _{p_name.lower()};")
        ctx.emit()
        ctx.emit("// Derived Lame parameters.")
        ctx.emit("Real _lambda;")
        ctx.emit("Real _mu;")
    ctx.emit("};")
    ctx.emit()
    return ctx.get_source()


# ---------------------------------------------------------------------------
# Implementation emission (.C)
# ---------------------------------------------------------------------------


def emit_cpp(bundle: ArtifactBundle) -> str:
    """Emit the ``.C`` implementation file for the MOOSE material class."""
    _guard_supported(bundle)
    model, params = _extract_material(bundle)
    class_name = _material_class_name(model)

    ctx = EmissionContext()
    ctx.emit(f"// Auto-generated by mechdsl.codegen.moose_printer (model={model}).")
    ctx.emit("// Subclass of ComputeStressBase; uses RankTwoTensor & RankFourTensor.")
    ctx.emit()
    ctx.emit(f'#include "{class_name}.h"')
    ctx.emit()
    ctx.emit(f'registerMooseObject("MechDSLApp", {class_name});')
    ctx.emit()
    ctx.emit("template <>")
    ctx.emit(f"InputParameters validParams<{class_name}>()")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("InputParameters params = validParams<ComputeStressBase>();")
        ctx.emit('params.addRequiredParam<Real>("youngs_modulus", "Young\'s modulus (E).");')
        ctx.emit('params.addRequiredParam<Real>("poissons_ratio", "Poisson\'s ratio (nu).");')
        for p_name in sorted(params.keys()):
            if p_name in ("E", "nu"):
                continue
            ctx.emit(
                f'params.addRequiredParam<Real>("{p_name.lower()}", '
                f'"{p_name} material parameter.");'
            )
        ctx.emit(
            'params.addClassDescription("MechDSL-generated '
            f'{model} material (ComputeStressBase).");'
        )
        ctx.emit("return params;")
    ctx.emit("}")
    ctx.emit()

    # Constructor
    ctx.emit(f"{class_name}::{class_name}(const InputParameters & parameters)")
    with ctx.indent_block():
        ctx.emit(": ComputeStressBase(parameters),")
        ctx.emit('  _youngs_modulus(getParam<Real>("youngs_modulus")),')
        close = '  _poissons_ratio(getParam<Real>("poissons_ratio"))'
        extras = [p_name for p_name in sorted(params.keys()) if p_name not in ("E", "nu")]
        if extras:
            ctx.emit(close + ",")
            for idx, p_name in enumerate(extras):
                suffix = "," if idx < len(extras) - 1 else ""
                ctx.emit(f'  _{p_name.lower()}(getParam<Real>("{p_name.lower()}")){suffix}')
        else:
            ctx.emit(close)
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("const Real E = _youngs_modulus;")
        ctx.emit("const Real nu = _poissons_ratio;")
        ctx.emit("_lambda = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu));")
        ctx.emit("_mu = E / (2.0 * (1.0 + nu));")
    ctx.emit("}")
    ctx.emit()

    # computeQpStress: writes _stress[_qp] as a RankTwoTensor.
    ctx.emit(f"void {class_name}::computeQpStress()")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("// Total-Lagrangian SVK stress update. Plan B Phase 8 MVP.")
        ctx.emit("// Reads _mechanical_strain[_qp] (a RankTwoTensor) and emits")
        ctx.emit("// _stress[_qp] = 2*mu*E + lambda*tr(E)*I as a RankTwoTensor.")
        ctx.emit("const RankTwoTensor E = _mechanical_strain[_qp];")
        ctx.emit("const Real trE = E.trace();")
        ctx.emit("RankTwoTensor stress;")
        ctx.emit("stress.zero();")
        # Dispatch through the family emitter table. Legacy body is
        # retained as the fallback when the flag is off so byte-identical
        # emission is preserved under ``MECHDSL_FAMILY_EMITTERS=0``.
        if not _dispatch_family(Family.MATERIAL_TANGENT_CONTRACTION, ctx):
            ctx.emit("for (unsigned int i = 0; i < 3; ++i)")
            with ctx.indent_block():
                ctx.emit("for (unsigned int j = 0; j < 3; ++j)")
                with ctx.indent_block():
                    ctx.emit("stress(i, j) = 2.0 * _mu * E(i, j);")
            ctx.emit("for (unsigned int i = 0; i < 3; ++i)")
            with ctx.indent_block():
                ctx.emit("stress(i, i) += _lambda * trE;")
        ctx.emit("_stress[_qp] = stress;")
        ctx.emit("computeQpJacobian();")
    ctx.emit("}")
    ctx.emit()

    # computeQpJacobian: writes _Jacobian_mult[_qp] as a RankFourTensor.
    ctx.emit(f"void {class_name}::computeQpJacobian()")
    ctx.emit("{")
    with ctx.indent_block():
        ctx.emit("// SVK algorithmic tangent as a RankFourTensor in MOOSE")
        ctx.emit("// C(i, j, k, l) = lambda * delta_ij * delta_kl")
        ctx.emit("//               + mu * (delta_ik * delta_jl + delta_il * delta_jk)")
        ctx.emit("RankFourTensor C;")
        ctx.emit("C.zero();")
        # Dispatch through the family emitter table; legacy inline body
        # retained as the fallback for byte-identical emission when the flag
        # is off.
        if not _dispatch_family(Family.TANGENT_DOUBLE_CONTRACTION, ctx):
            ctx.emit("for (unsigned int i = 0; i < 3; ++i)")
            with ctx.indent_block():
                ctx.emit("for (unsigned int j = 0; j < 3; ++j)")
                with ctx.indent_block():
                    ctx.emit("for (unsigned int k = 0; k < 3; ++k)")
                    with ctx.indent_block():
                        ctx.emit("for (unsigned int l = 0; l < 3; ++l)")
                        with ctx.indent_block():
                            ctx.emit("{")
                            with ctx.indent_block():
                                ctx.emit("Real val = 0.0;")
                                ctx.emit("if (i == j && k == l) val += _lambda;")
                                ctx.emit("if (i == k && j == l) val += _mu;")
                                ctx.emit("if (i == l && j == k) val += _mu;")
                                ctx.emit("C(i, j, k, l) = val;")
                            ctx.emit("}")
        ctx.emit("_Jacobian_mult[_qp] = C;")
    ctx.emit("}")
    ctx.emit()

    return ctx.get_source()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def emit(bundle: ArtifactBundle) -> dict[str, str]:
    """Emit the MOOSE ``.h`` + ``.C`` pair for a bundle.

    Returns a dict with keys ``"header"`` and ``"cpp"``.  Both strings end in
    ``\\n``.  Use :func:`emit_input_file` to produce the companion ``.i`` deck.
    """
    warn_experimental_backend_once(_warn_state, "MOOSE")

    _guard_supported(bundle)
    return {
        "header": emit_header(bundle),
        "cpp": emit_cpp(bundle),
    }


# ---------------------------------------------------------------------------
# Input file emission (.i)
# ---------------------------------------------------------------------------


_TEMPLATE_PATH = Path(__file__).parent / "moose_template" / "input_template.i"


def _load_template() -> str:
    if not _TEMPLATE_PATH.is_file():
        raise FileNotFoundError(
            f"MOOSE input template not found at {_TEMPLATE_PATH!s}. "
            "Ensure mechdsl.codegen.moose_template is installed alongside "
            "the printer module."
        )
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def emit_input_file(bundle: ArtifactBundle) -> str:
    """Load ``input_template.i`` and fill MechDSL placeholders.

    Placeholders (``{{...}}``) are filled from the bundle's material spec and
    a handful of sensible defaults for a tension test.  The returned string
    contains no remaining placeholders — any leftover ``{{...}}`` indicates a
    template mismatch and raises :class:`ValueError`.
    """
    _guard_supported(bundle)
    model, params = _extract_material(bundle)
    class_name = _material_class_name(model)

    # Young's modulus / Poisson's ratio defaults (steel-ish) if absent.
    youngs = float(params.get("E", 200e3))
    poissons = float(params.get("nu", 0.3))

    formulation = str(bundle.problem_ir_dict.get("formulation", "total_lagrangian"))

    substitutions = {
        "MATERIAL_NAME": class_name,
        "MATERIAL_MODEL": model,
        "FORMULATION": formulation,
        "YOUNGS_MODULUS": f"{youngs:.17g}",
        "POISSONS_RATIO": f"{poissons:.17g}",
        "MESH_NX": "4",
        "MESH_NY": "2",
        "MESH_NZ": "2",
        "PULL_AMPLITUDE": "0.01",
        "TIME_STEP": "0.1",
        "NUM_STEPS": "10",
    }

    text = _load_template()
    for key, value in substitutions.items():
        text = text.replace("{{" + key + "}}", value)

    if "{{" in text and "}}" in text:
        # Template still has unfilled placeholders — fail loudly.
        raise ValueError(
            "MOOSE input template still contains unfilled placeholders after "
            f"substitution: {text!r}"
        )
    return text
