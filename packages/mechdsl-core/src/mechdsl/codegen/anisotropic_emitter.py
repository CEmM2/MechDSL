"""Emit a Taichi constitutive ``@ti.func`` from a LaTeX-derived *anisotropic*
(fiber-reinforced, HGO) energy.

The straight-line emitter in :mod:`mechdsl.codegen.energy_emitter` prints one
unconditional assignment per stress component. The Holzapfel-Gasser-Ogden (HGO)
family needs two things it structurally cannot do (see :issue:`288`):

1. a **data-dependent branch** — the fiber term is gated to tension by the
   Macaulay bracket ``<Ibar4 - 1>`` (active only when ``Ibar4 > 1``); and
2. a **per-element fiber-direction gather** — the fiber stress depends on a
   direction ``a`` that is per-element field data (P5-1
   ``ProblemIR.fiber_field`` -> ``ElementIR.fiber_field``), not authored in the
   LaTeX, so the constitutive function gains a fiber-direction argument that the
   call site reads from the gathered field.

This module supplies :func:`emit_anisotropic_constitutive_func`, which emits a
``constitutive_update(F, a, *params)`` that:

* computes the always-on isotropic + volumetric stress ``S_iso(E)`` (identical
  in form to the proven neo-Hookean emission);
* normalises the fiber direction ``a`` (as the oracle does), computes the fiber
  pseudo-invariant ``Ibar4(E, a)``; and
* adds the active-branch fiber stress ``S_fib(E, a)`` only when ``Ibar4 > 1``.

It reproduces :meth:`AnisotropicEnergyModel.pk2_stress` for a single fiber family
(the ``fiber_dispersion = 0`` perfectly-aligned case), so the emitted Taichi and
the NumPy oracle agree to FP noise.

Conventions (07-CONVENTIONS.md): tension-positive stress; float64. Material
parameters keep their sanitised LaTeX names as ``ti.f64`` arguments, matching
:mod:`mechdsl.codegen.energy_emitter`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import Symbol, pycode

from mechdsl.codegen.energy_emitter import _to_numpy_math, _to_taichi_math

if TYPE_CHECKING:
    from mechdsl.symbolic.anisotropic_energy import AnisotropicEnergyModel

__all__ = [
    "ANISOTROPIC_PK2_NUMPY_NAME",
    "anisotropic_param_names",
    "emit_anisotropic_constitutive_func",
    "emit_anisotropic_pk2_numpy_source",
    "emit_anisotropic_tangent_matvec_body",
]

_STRAIN = "EDD"

# Name of the emitted host-NumPy PK2 helper the FD tangent calls.
ANISOTROPIC_PK2_NUMPY_NAME = "_pk2_anisotropic"


def anisotropic_param_names(model: AnisotropicEnergyModel) -> list[str]:
    """Sorted union of isotropic and fiber material-parameter names.

    These name the ``ti.f64`` arguments of the emitted ``constitutive_update``
    (in the same sorted order the body forwards them), mirroring
    :func:`mechdsl.codegen.energy_emitter.derived_param_names`. The union (not
    just the isotropic params) guarantees a fiber-only parameter (e.g. ``k1`` /
    ``k2``) is still plumbed into the signature.
    """
    names = {s.name for s in model.iso_param_symbols}
    names |= {s.name for s in model.fiber_param_symbols}
    return sorted(names)


def emit_anisotropic_constitutive_func(
    model: AnisotropicEnergyModel,
    *,
    func_name: str = "constitutive_update",
    param_names: list[str] | None = None,
    fiber_arg: str = "a",
) -> str:
    """Return a Taichi ``@ti.func`` computing PK2 stress ``S(F, a)`` from a
    derived *anisotropic* (HGO) energy model.

    The emitted function takes the deformation gradient ``F``, a per-element
    fiber-direction vector ``a`` (``ti.Vector(3)``, gathered from the fiber
    field at the call site), and one ``ti.f64`` argument per material parameter.
    It builds the Green-Lagrange strain, assigns the always-on isotropic stress,
    then conditionally adds the fiber stress when the tension gate
    ``Ibar4(E, a) > 1`` is open.

    ``param_names`` overrides the argument list (default:
    :func:`anisotropic_param_names`); pass an explicit list to keep the
    signature aligned with the unified solver parameter vocabulary, as
    :mod:`mechdsl.codegen.energy_emitter` does. ``fiber_arg`` names the fiber
    vector argument (default ``a``, matching the ``a0``/``a1``/``a2`` symbols the
    derivation uses).
    """
    # Strain symbols EDDij -> the per-component locals Eij the body declares.
    strain_subs = {
        model.strain_symbols[i][j]: Symbol(f"E{i}{j}") for i in range(3) for j in range(3)
    }

    args = param_names if param_names is not None else anisotropic_param_names(model)
    # @ti.func arguments are untyped: Taichi infers their types from the call site.
    arglist = ", ".join(["F", fiber_arg, *args])
    head = [
        "@ti.func",
        f"def {func_name}({arglist}):",
    ]
    body = [
        '"""PK2 stress from a fiber-reinforced (HGO) strain energy; fiber term'
        ' tension-gated by the Macaulay bracket <Ibar4 - 1>."""',
        "C = F.transpose() @ F",
        "I3 = ti.Matrix.identity(ti.f64, 3)",
        "E = 0.5 * (C - I3)",
    ]
    for i in range(3):
        for j in range(3):
            body.append(f"E{i}{j} = E[{i}, {j}]")
    # Normalise the gathered fiber direction (the oracle normalises before
    # evaluating). The derivation's a0/a1/a2 symbols bind to these locals, so
    # pycode references resolve directly.
    body.append(
        f"_anorm = ti.sqrt({fiber_arg}[0] * {fiber_arg}[0] + {fiber_arg}[1] * {fiber_arg}[1]"
        f" + {fiber_arg}[2] * {fiber_arg}[2])"
    )
    for k in range(3):
        body.append(f"a{k} = {fiber_arg}[{k}] / _anorm")
    # Always-on isotropic + volumetric stress.
    body.append("S = ti.Matrix.zero(ti.f64, 3, 3)")
    for i in range(3):
        for j in range(3):
            expr = model.iso_pk2[i, j].xreplace(strain_subs)
            body.append(f"S[{i}, {j}] = {_to_taichi_math(pycode(expr))}")
    # Fiber gate: the Macaulay bracket makes the fiber term active in tension
    # only (Ibar4 > 1) -- the data-dependent branch the straight-line emitter
    # structurally lacks.
    ibar4_expr = model.fiber_ibar4.xreplace(strain_subs)
    body.append(f"ibar4 = {_to_taichi_math(pycode(ibar4_expr))}")
    body.append("if ibar4 > 1.0:")
    for i in range(3):
        for j in range(3):
            expr = model.fiber_pk2[i, j].xreplace(strain_subs)
            if expr == 0:
                continue
            body.append(f"    S[{i}, {j}] += {_to_taichi_math(pycode(expr))}")
    body.append("return 0.5 * (S + S.transpose())")

    indent = "    "
    return "\n".join(head + [indent + line for line in body]) + "\n"


def emit_anisotropic_pk2_numpy_source(
    model: AnisotropicEnergyModel,
    *,
    func_name: str = ANISOTROPIC_PK2_NUMPY_NAME,
    param_names: list[str] | None = None,
    fiber_arg: str = "a",
) -> str:
    """Return a host-NumPy ``def`` computing PK2 stress ``S(E, a)`` for the HGO
    energy, used as the central-difference reference of the FD tangent.

    The internal force is computed by the device ``@ti.func``
    (:func:`emit_anisotropic_constitutive_func`); the matrix-free
    ``tangent_matvec`` is host NumPy and needs a host stress to finite-difference.
    This emits exactly :meth:`AnisotropicEnergyModel.pk2_stress` for a single
    fiber family: the always-on isotropic stress plus the tension-gated fiber
    stress (``Ibar4 > 1``), with the fiber direction normalised, so the device
    and host stresses stay numerically identical.
    """
    strain_subs = {
        model.strain_symbols[i][j]: Symbol(f"E{i}{j}") for i in range(3) for j in range(3)
    }
    args = param_names if param_names is not None else anisotropic_param_names(model)
    arglist = ", ".join(["E", fiber_arg, *args])
    head = [f"def {func_name}({arglist}):"]
    body = [
        '"""Host-NumPy PK2 stress for the HGO energy (FD-tangent reference)."""',
    ]
    for i in range(3):
        for j in range(3):
            body.append(f"E{i}{j} = E[{i}, {j}]")
    body.append(
        f"_anorm = np.sqrt({fiber_arg}[0] ** 2 + {fiber_arg}[1] ** 2 + {fiber_arg}[2] ** 2)"
    )
    for k in range(3):
        body.append(f"a{k} = {fiber_arg}[{k}] / _anorm")
    body.append("S = np.zeros((3, 3), dtype=np.float64)")
    for i in range(3):
        for j in range(3):
            expr = model.iso_pk2[i, j].xreplace(strain_subs)
            body.append(f"S[{i}, {j}] = {_to_numpy_math(pycode(expr))}")
    ibar4_expr = model.fiber_ibar4.xreplace(strain_subs)
    body.append(f"ibar4 = {_to_numpy_math(pycode(ibar4_expr))}")
    body.append("if ibar4 > 1.0:")
    for i in range(3):
        for j in range(3):
            expr = model.fiber_pk2[i, j].xreplace(strain_subs)
            if expr == 0:
                continue
            body.append(f"    S[{i}, {j}] += {_to_numpy_math(pycode(expr))}")
    body.append("return 0.5 * (S + S.T)")

    indent = "    "
    return "\n".join(head + [indent + line for line in body]) + "\n"


def emit_anisotropic_tangent_matvec_body(
    model: AnisotropicEnergyModel,
    *,
    pk2_name: str = ANISOTROPIC_PK2_NUMPY_NAME,
    param_names: list[str] | None = None,
    fiber_local: str = "a_fiber",
) -> list[str]:
    """Host-NumPy lines for the HGO material term inside ``tangent_matvec``.

    Returns statements (no leading indent) that, given the Green-Lagrange strain
    ``E``, the linearised strain ``dE`` (both ``(3, 3)`` ``np.ndarray``), the
    fiber direction ``fiber_local`` (a 3-vector in scope), and the material
    parameters already in scope, assign ``S`` (derived PK2 stress) and ``dS``
    (``C : dE`` via the directional central difference). FD is the correct method
    across the non-smooth Macaulay gate (it matches
    :meth:`AnisotropicEnergyModel.material_tangent_4th`).
    """
    args = param_names if param_names is not None else anisotropic_param_names(model)
    fwd = ", ".join(args)
    return [
        "# Derived HGO constitutive law: PK2 stress + central-difference FD tangent.",
        f"S = {pk2_name}(E, {fiber_local}, {fwd})",
        "_fd_eps = 1e-6",
        f"_S_plus = {pk2_name}(E + _fd_eps * dE, {fiber_local}, {fwd})",
        f"_S_minus = {pk2_name}(E - _fd_eps * dE, {fiber_local}, {fwd})",
        "dS = (_S_plus - _S_minus) / (2.0 * _fd_eps)",
    ]
