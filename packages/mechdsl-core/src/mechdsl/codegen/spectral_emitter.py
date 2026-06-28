"""Emit a Taichi constitutive ``@ti.func`` from a LaTeX-derived *spectral* energy.

The straight-line emitter in :mod:`mechdsl.codegen.energy_emitter` prints one
assignment per stress component from a closed-form ``S(E)``. That works for
energies whose PK2 stress is a polynomial in the strain components
(SVK / neo-Hookean / Mooney-Rivlin) but **not** for Ogden-type energies authored
in principal stretches ``lambda_i = sqrt(eig_i(C))``: their closed-form
eigenvalues are Cardano radicals (complex branch cuts in the casus
irreducibilis, blow the JIT budget, unstable at repeated eigenvalues). See
:issue:`288`.

This module supplies the two backend capabilities the spectral path needs:

1. :data:`SYM_EIG_3X3_SOURCE` — a symmetric 3x3 eigensolver callable inside a
   ``@ti.func`` (eigenvalues **and** orthonormal eigenvectors, robust at
   repeated eigenvalues), via cyclic Jacobi rotations (no eigenvalue-difference
   denominators); and
2. :func:`emit_spectral_constitutive_func` — emission of a ``constitutive_update``
   that eigendecomposes ``C = F^T F``, evaluates the symbolic per-principal-stress
   ``S_i(lambda)`` that :mod:`mechdsl.symbolic.spectral_energy` derives, and
   reassembles ``S = sum_i S_i N_i (x) N_i``.

The reassembly reproduces :meth:`SpectralEnergyModel.pk2_stress` exactly (same
``C`` symmetrisation, eigenvalue floor, principal stresses, projector sum, final
symmetrisation), so the emitted Taichi and the NumPy oracle agree to FP noise.

Conventions (07-CONVENTIONS.md): tension-positive stress; float64. Material
parameters keep their sanitised LaTeX names as ``ti.f64`` arguments, matching
:mod:`mechdsl.codegen.energy_emitter`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import Symbol, pycode

from mechdsl.codegen.energy_emitter import _to_numpy_math, _to_taichi_math

if TYPE_CHECKING:
    from mechdsl.symbolic.spectral_energy import SpectralEnergyModel

__all__ = [
    "EIGENSOLVER_NAME",
    "SPECTRAL_PK2_NUMPY_NAME",
    "SYM_EIG_3X3_SOURCE",
    "emit_spectral_constitutive_func",
    "emit_spectral_pk2_numpy_source",
    "emit_spectral_tangent_matvec_body",
    "spectral_param_names",
]

# Name of the emitted host-NumPy PK2 helper the FD tangent calls (see
# :func:`emit_spectral_pk2_numpy_source`).
SPECTRAL_PK2_NUMPY_NAME = "_pk2_spectral"

# Name of the emitted eigensolver ``@ti.func``; the constitutive function calls
# it, so a generated file must emit :data:`SYM_EIG_3X3_SOURCE` once before the
# constitutive body.
EIGENSOLVER_NAME = "sym_eig_3x3"

# Cyclic Jacobi sweeps. Each sweep zeroes the three off-diagonal pivots once;
# the method converges quadratically, so a symmetric 3x3 reaches f64 machine
# precision in ~5-6 sweeps. A fixed count (no data-dependent loop bound) keeps
# the kernel JIT-friendly and deterministic; 12 is a safe margin.
_JACOBI_SWEEPS = 12

# Eigenvalue floor against negative C-eigenvalues from FP noise near zero stretch
# (mirrors ``_EIG_FLOOR`` in symbolic/spectral_energy.py and models/ogden.py).
_EIG_FLOOR = "1e-300"

# Canonical source of the symmetric 3x3 eigensolver. Emitted verbatim into a
# generated solver (one copy per file) and JIT-compiled directly in tests, so
# the helper that ships in generated code is the same one verified against
# ``numpy.linalg.eigh``. Returns a 3x4 matrix packing the result:
#   columns 0..2 -> orthonormal eigenvectors (eigenvector i is column i)
#   column 3     -> the corresponding eigenvalues
# (A single packed return value sidesteps any @ti.func multi-return ambiguity.)
SYM_EIG_3X3_SOURCE = f'''@ti.func
def {EIGENSOLVER_NAME}(A):
    """Symmetric 3x3 eigensolver via cyclic Jacobi rotations.

    Returns a 3x4 matrix: columns 0..2 are the orthonormal eigenvectors and
    column 3 holds the corresponding eigenvalues. Iterative (no Cardano branch
    cuts) and robust at repeated eigenvalues -- the eigenvector basis stays
    orthonormal, so the projector reassembly S = sum_i S_i N_i (x) N_i is
    basis-independent on a degenerate eigenspace.
    """
    a = A
    V = ti.Matrix.identity(ti.f64, 3)
    for _sweep in range({_JACOBI_SWEEPS}):
        for pair in ti.static(((0, 1), (0, 2), (1, 2))):
            p = pair[0]
            q = pair[1]
            apq = a[p, q]
            if ti.abs(apq) > {_EIG_FLOOR}:
                # Jacobi rotation angle that zeroes a[p, q] (Golub & Van Loan
                # Alg. 8.4.1): beta = (a_qq - a_pp) / (2 a_pq); the t-formula
                # avoids the catastrophic cancellation of tan(0.5 atan(...)).
                beta = (a[q, q] - a[p, p]) / (2.0 * apq)
                t = 1.0 / (ti.abs(beta) + ti.sqrt(beta * beta + 1.0))
                if beta < 0.0:
                    t = -t
                c = 1.0 / ti.sqrt(t * t + 1.0)
                s = t * c
                # A <- G^T A G, applied as columns (A G) then rows (G^T (A G)).
                for k in ti.static(range(3)):
                    akp = a[k, p]
                    akq = a[k, q]
                    a[k, p] = c * akp - s * akq
                    a[k, q] = s * akp + c * akq
                for k in ti.static(range(3)):
                    apk = a[p, k]
                    aqk = a[q, k]
                    a[p, k] = c * apk - s * aqk
                    a[q, k] = s * apk + c * aqk
                # Accumulate eigenvectors: V <- V G.
                for k in ti.static(range(3)):
                    vkp = V[k, p]
                    vkq = V[k, q]
                    V[k, p] = c * vkp - s * vkq
                    V[k, q] = s * vkp + c * vkq
    out = ti.Matrix.zero(ti.f64, 3, 4)
    for i in ti.static(range(3)):
        for k in ti.static(range(3)):
            out[k, i] = V[k, i]
    out[0, 3] = a[0, 0]
    out[1, 3] = a[1, 1]
    out[2, 3] = a[2, 2]
    return out
'''


def spectral_param_names(model: SpectralEnergyModel) -> list[str]:
    """Sorted material-parameter names of a spectral energy.

    These name the ``ti.f64`` arguments of the emitted ``constitutive_update``
    (in the same sorted order the body forwards them), mirroring
    :func:`mechdsl.codegen.energy_emitter.derived_param_names` for the spectral
    path. The order is the model's own ``param_symbols`` eval order.
    """
    return [s.name for s in model.param_symbols]


def emit_spectral_constitutive_func(
    model: SpectralEnergyModel,
    *,
    func_name: str = "constitutive_update",
    param_names: list[str] | None = None,
) -> str:
    """Return a Taichi ``@ti.func`` computing PK2 stress ``S(F)`` from a derived
    *spectral* energy model.

    The emitted function:

    1. forms ``C = F^T F`` and symmetrises it (matches the oracle's ``C_sym``);
    2. calls :data:`SYM_EIG_3X3_SOURCE`'s ``sym_eig_3x3`` for the eigenvalues
       ``e_i = lambda_i^2`` and orthonormal eigenvectors ``N_i``;
    3. takes the floored stretches ``lambda_i = sqrt(max(e_i, floor))``;
    4. evaluates the symbolic principal PK2 stresses ``S_i(lambda)`` derived by
       :func:`mechdsl.symbolic.spectral_energy.derive_from_spectral_energy`; and
    5. reassembles and symmetrises ``S = sum_i S_i N_i (x) N_i``.

    The caller must emit :data:`SYM_EIG_3X3_SOURCE` once into the same module
    before this function (so ``sym_eig_3x3`` is in scope).

    ``param_names`` overrides the argument list (default: the model's own
    parameter order via :func:`spectral_param_names`); pass an explicit list to
    keep the signature aligned with the unified solver parameter vocabulary, as
    :mod:`mechdsl.codegen.energy_emitter` does.
    """
    # Stretch symbols lambda_1/_2/_3 -> the per-component locals lam0/lam1/lam2
    # the body declares from the eigenvalues.
    stretch_subs = {model.stretch_symbols[i]: Symbol(f"lam{i}") for i in range(3)}

    args = param_names if param_names is not None else spectral_param_names(model)
    # @ti.func arguments are untyped: Taichi infers their types from the call site.
    arglist = ", ".join(["F", *args])
    head = [
        "@ti.func",
        f"def {func_name}({arglist}):",
    ]
    body = [
        '"""PK2 stress derived from a spectral (principal-stretch) strain energy."""',
        "C = F.transpose() @ F",
        "C = 0.5 * (C + C.transpose())",
        f"_ev = {EIGENSOLVER_NAME}(C)",
        "lam0 = ti.sqrt(ti.max(_ev[0, 3], " + _EIG_FLOOR + "))",
        "lam1 = ti.sqrt(ti.max(_ev[1, 3], " + _EIG_FLOOR + "))",
        "lam2 = ti.sqrt(ti.max(_ev[2, 3], " + _EIG_FLOOR + "))",
    ]
    for i in range(3):
        expr = model.principal_pk2[i].xreplace(stretch_subs)
        body.append(f"sprin{i} = {_to_taichi_math(pycode(expr))}")
    body.append("S = ti.Matrix.zero(ti.f64, 3, 3)")
    for i in range(3):
        body.append(f"n{i} = ti.Vector([_ev[0, {i}], _ev[1, {i}], _ev[2, {i}]])")
        body.append(f"S += sprin{i} * n{i}.outer_product(n{i})")
    body.append("return 0.5 * (S + S.transpose())")

    indent = "    "
    return "\n".join(head + [indent + line for line in body]) + "\n"


def emit_spectral_pk2_numpy_source(
    model: SpectralEnergyModel,
    *,
    func_name: str = SPECTRAL_PK2_NUMPY_NAME,
    param_names: list[str] | None = None,
) -> str:
    """Return a host-NumPy ``def`` computing PK2 stress ``S(E)`` for the spectral
    energy, used as the central-difference reference of the FD tangent.

    The generated solver computes the *internal force* through the device
    ``@ti.func`` (:func:`emit_spectral_constitutive_func`) but the matrix-free
    ``tangent_matvec`` is host NumPy (07-CONVENTIONS / the existing derived
    path), so it needs a host stress to finite-difference. This function emits
    exactly :meth:`SpectralEnergyModel.pk2_stress` (``C = 2E + I`` symmetrised,
    ``numpy.linalg.eigh``, principal stresses at the floored stretches, projector
    reassembly, final symmetrisation) so the two stay numerically identical.

    ``param_names`` overrides the argument order (default
    :func:`spectral_param_names`); pass the unified solver vocabulary so the call
    site forwards the same names.
    """
    stretch_subs = {model.stretch_symbols[i]: Symbol(f"lam{i}") for i in range(3)}
    args = param_names if param_names is not None else spectral_param_names(model)
    arglist = ", ".join(["E", *args])
    head = [f"def {func_name}({arglist}):"]
    body = [
        '"""Host-NumPy PK2 stress for the spectral energy (FD-tangent reference)."""',
        "C = 2.0 * E + np.eye(3)",
        "C = 0.5 * (C + C.T)",
        "_evals, _evecs = np.linalg.eigh(C)",
        "lam0 = np.sqrt(max(float(_evals[0]), " + _EIG_FLOOR + "))",
        "lam1 = np.sqrt(max(float(_evals[1]), " + _EIG_FLOOR + "))",
        "lam2 = np.sqrt(max(float(_evals[2]), " + _EIG_FLOOR + "))",
    ]
    for i in range(3):
        expr = model.principal_pk2[i].xreplace(stretch_subs)
        body.append(f"sprin{i} = {_to_numpy_math(pycode(expr))}")
    body.append("S = np.zeros((3, 3), dtype=np.float64)")
    for i in range(3):
        body.append(f"_n{i} = _evecs[:, {i}]")
        body.append(f"S = S + sprin{i} * np.outer(_n{i}, _n{i})")
    body.append("return 0.5 * (S + S.T)")

    indent = "    "
    return "\n".join(head + [indent + line for line in body]) + "\n"


def emit_spectral_tangent_matvec_body(
    model: SpectralEnergyModel,
    *,
    pk2_name: str = SPECTRAL_PK2_NUMPY_NAME,
    param_names: list[str] | None = None,
) -> list[str]:
    """Host-NumPy lines for the spectral material term inside ``tangent_matvec``.

    Returns statements (no leading indent) that, given the Green-Lagrange strain
    ``E`` and the linearised strain ``dE`` (both ``(3, 3)`` ``np.ndarray`` in
    scope) and the material parameters already in scope, assign:

    - ``S``  — the derived PK2 stress (needed for the geometric term), and
    - ``dS`` — the linearised stress ``C : dE``, obtained as the **directional**
      central difference ``(S(E + eps dE) - S(E - eps dE)) / (2 eps)``. Because
      ``dS = C : dE`` is linear in ``dE``, that directional difference equals the
      full contraction without ever forming the rank-4 ``C`` — and matches the
      FD method :meth:`SpectralEnergyModel.material_tangent_4th` uses.

    The spectral tangent has no stable closed form (it is singular at repeated
    stretches), so FD is the correct method here — unlike the closed-form
    invariant path's :func:`energy_emitter.emit_derived_tangent_matvec_body`.
    """
    args = param_names if param_names is not None else spectral_param_names(model)
    fwd = ", ".join(args)
    return [
        "# Derived spectral constitutive law: PK2 stress + central-difference FD tangent.",
        f"S = {pk2_name}(E, {fwd})",
        "_fd_eps = 1e-6",
        f"_S_plus = {pk2_name}(E + _fd_eps * dE, {fwd})",
        f"_S_minus = {pk2_name}(E - _fd_eps * dE, {fwd})",
        "dS = (_S_plus - _S_minus) / (2.0 * _fd_eps)",
    ]
