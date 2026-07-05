"""Generated-tests emitter, one pytest file per scalar plasticity law (Task P3-2).

MFront-mimic Cycle M0, Phase 3 (``dev/plans/mfront_cycleM0.md`` lines 101-103).

:func:`emit_tests` writes a **self-contained, valid-Python** pytest file that
exercises one :class:`~mechdsl.lawgen.contracts.PlasticityCarrierSpec`. The file
that :func:`emit_tests` writes contains, in order:

* ``test_reference_eval`` — reconstructs the R/H/Q expressions, ``lambdify``\\ s
  them over the spec's symbol map (parameters ∪ variable bindings) and evaluates
  them at ``N = 10`` sample points of the primary free variable (the accumulated
  plastic strain ``p``), asserting every result is finite.
* ``test_fd_derivative`` — a ``pytest.mark.parametrize``\\ d test covering **all
  three factors** R/H/Q. R, H and Q are three *independent* scalar factors, not a
  value and its derivative (matching Cycle 0's ``swift_voce.py``
  ``get_R``/``get_H``/``get_Q``): R is the isotropic-hardening flow stress
  (function of the plastic strain ``p``), H the strain-rate factor (function of
  ``edot``), Q the thermal factor (function of ``T``). For each factor the test
  compares a central finite-difference derivative w.r.t. that factor's **own**
  primary variable against the *analytic* derivative (``sympy.diff``, lowered
  through the same ``lambdify`` path) at the sample points, to ``rtol = 1e-5``
  (standard FD precision — deliberately **not** the ``1e-10`` P4-2 equivalence
  gate). A factor that is constant in its primary (e.g. a rate-independent
  ``H = 1``) has analytic derivative ``0`` and FD ``≈ 0``, so the general
  FD-vs-analytic check passes without any special-casing.
* ``test_monotonicity`` — emitted **iff** ``spec.monotone_check`` is ``True``:
  asserts ``R`` is non-decreasing in the accumulated plastic strain across the
  sorted sample points.
* ``test_taichi_smoke`` — **optional and guarded**: ``pytest.importorskip`` skips
  it cleanly when Taichi is not installed; otherwise it JIT-compiles the lowered
  R into a ``@ti.kernel`` and calls it once.

Self-containedness (why ``srepr``)
----------------------------------
The generated file must run under ``pytest`` on its own, so it cannot import the
spec back. Instead each expression is serialised with :func:`sympy.srepr` — a
loss-free, ``eval``-free round-trip string that the generated file rebuilds with
:func:`sympy.sympify`. No SymPy code-printer and no regex string surgery is used
(plan rule R4): the *expression* is carried as data and re-parsed by SymPy, and
the file *body* is assembled from plain f-strings.

Fixed placeholder parameters
----------------------------
The generated tests are self-consistency checks that hold for *any* fixed
parameter values (the FD identity ``f'(x) ≈ (f(x+h) − f(x−h))/2h`` and
monotonicity of a well-formed hardening law do not depend on the specific
material constants). So every material parameter and every non-primary variable
binding is pinned to :data:`PLACEHOLDER_PARAM_VALUE` (``1.0``); the generated file
documents this inline. This keeps the emitted file dependency-free and
deterministic without needing a real material card.

No silent fallback (R2)
-----------------------
If the spec's ``R`` cannot be lowered to Taichi (an unsupported node),
:func:`emit_tests` calls :func:`~mechdsl.lawgen.sympy_to_taichi.lower_expression`,
which raises :class:`~mechdsl.lawgen.diagnostics.LawgenError`. The emitter never
writes a partial or silently-degraded file.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import sympy as sp

from mechdsl.lawgen.sympy_to_taichi import lower_expression

if TYPE_CHECKING:
    from mechdsl.lawgen.contracts import PlasticityCarrierSpec

__all__ = [
    "FACTOR_PRIMARY_VARIABLE",
    "FD_RTOL",
    "FD_STEP",
    "N_SAMPLE_POINTS",
    "PLACEHOLDER_PARAM_VALUE",
    "PRIMARY_VARIABLE_NAME",
    "emit_tests",
]

# ---------------------------------------------------------------------------
# Emission constants (mirrored verbatim into the generated file so a reader of
# the test does not have to import this module to know the numbers).
# ---------------------------------------------------------------------------

#: Number of sample points of the primary variable used by every generated test.
N_SAMPLE_POINTS: int = 10

#: Fixed value pinned to every material parameter and every non-primary variable
#: binding in the generated tests. ``1.0`` — the checks are self-consistency
#: identities that hold for any fixed params (see module docstring).
PLACEHOLDER_PARAM_VALUE: float = 1.0

#: Central finite-difference step for the FD-derivative test. ``1e-6`` balances
#: truncation error (``O(h^2)``) against float64 round-off (``O(eps/h)``); the
#: sweet spot for a central difference in double precision is ~``eps**(1/3) ≈
#: 6e-6``, so ``1e-6`` sits comfortably in that band.
FD_STEP: float = 1e-6

#: Relative tolerance for the FD-vs-analytic derivative comparison. ``1e-5`` is
#: standard central-difference precision — NOT the ``1e-10`` P4-2 equivalence
#: gate. The generated test uses this as ``rtol`` (with a small ``atol`` so a
#: near-zero analytic derivative does not force an unreachable relative match).
FD_RTOL: float = 1e-5

#: The free-variable name the generated tests treat as the primary sweep axis
#: (the accumulated plastic strain). If a spec has no ``"p"`` binding the emitter
#: falls back to the first variable binding.
PRIMARY_VARIABLE_NAME: str = "p"

# Per-factor primary-variable convention (the FD-derivative axis for each of the
# three shipped factors). R/H/Q are THREE SEPARATE scalar factors, not a value and
# its derivative — matching Cycle 0's ``swift_voce.py`` ``get_R``/``get_H``/
# ``get_Q``:
#   * R = isotropic HARDENING flow-stress, primarily a function of the accumulated
#     plastic strain ``p`` (a.k.a. peeq);
#   * H = strain-RATE factor, primarily a function of the rate ``edot``;
#   * Q = THERMAL factor, primarily a function of temperature ``T``.
# The generator auto-differentiates each factor w.r.t. its OWN primary variable
# via ``sympy.diff`` — H is NOT ``d(R)/dp``. A factor with no dependence on its
# conventional primary (e.g. a rate-independent ``H = 1``) has analytic derivative
# ``0`` and FD ``≈ 0``: the general FD-vs-analytic check passes without any
# special-casing. Each role's primary is resolved against the spec's
# ``variable_bindings`` (falling back to the global primary if the conventional
# binding is absent — see :func:`_factor_primary_name`).
FACTOR_PRIMARY_VARIABLE: dict[str, str] = {"R": "p", "H": "edot", "Q": "T"}

# Sample-point window for the primary variable. A strictly positive, increasing
# range so hardening laws with ``sqrt``/``log``/``pow`` of the plastic strain are
# evaluated in-domain and the monotonicity check is meaningful (a hardening law
# is monotone in ``p >= 0``). Kept away from exactly 0 so FD ``x - h`` stays
# positive.
_SAMPLE_START: float = 1e-3
_SAMPLE_STOP: float = 1.0


def _primary_variable(spec: PlasticityCarrierSpec) -> tuple[str, sp.Symbol]:
    """Return the ``(name, symbol)`` of the primary sweep variable.

    Prefers the accumulated plastic strain binding (``PRIMARY_VARIABLE_NAME``,
    ``"p"``); falls back to the first variable binding if the spec does not bind
    ``"p"``. The spec guarantees at least one binding (``__post_init__``), so this
    never returns ``None``.
    """
    bindings = dict(spec.variable_bindings)
    if PRIMARY_VARIABLE_NAME in bindings:
        return PRIMARY_VARIABLE_NAME, bindings[PRIMARY_VARIABLE_NAME]
    name, symbol = next(iter(bindings.items()))
    return name, symbol


def _factor_primary_name(spec: PlasticityCarrierSpec, role: str, global_primary: str) -> str:
    """Return the FD-derivative axis name for factor ``role`` (``"R"``/``"H"``/``"Q"``).

    Uses the :data:`FACTOR_PRIMARY_VARIABLE` convention (R→``p``, H→``edot``,
    Q→``T``) resolved against the spec's ``variable_bindings``: if the conventional
    binding exists it is the factor's primary; otherwise fall back to
    ``global_primary`` (the spec's ``p``/first binding). The fallback keeps the FD
    check well-defined even for a spec that does not bind ``edot``/``T`` — the
    factor simply has no dependence on the fallback axis and its analytic
    derivative is ``0`` (FD ``≈ 0``), which the general assertion accepts.
    """
    conventional = FACTOR_PRIMARY_VARIABLE.get(role, global_primary)
    if conventional in spec.variable_bindings:
        return conventional
    return global_primary


def _ordered_symbol_names(spec: PlasticityCarrierSpec, primary_name: str) -> list[str]:
    """Deterministic argument order for the generated ``lambdify`` calls.

    Primary variable first, then the remaining variable bindings, then the
    material parameters — each group in the spec's own declaration order and with
    duplicates removed. A stable order keeps the generated file byte-deterministic
    (P3-3 lists these tests in the manifest) and lets the reference/FD/monotone
    tests share one argument tuple.
    """
    ordered: list[str] = [primary_name]
    for name in spec.variable_bindings:
        if name not in ordered:
            ordered.append(name)
    for name in spec.parameters:
        if name not in ordered:
            ordered.append(name)
    return ordered


def emit_tests(
    spec: PlasticityCarrierSpec,
    lowered_r: str | None = None,
    target_test_path: str | Path | None = None,
) -> Path:
    """Write a self-contained pytest file for ``spec`` and return its path.

    Parameters
    ----------
    spec:
        The plasticity carrier law to generate tests for. Its ``expressions``
        (R/H/Q), ``parameters``, ``variable_bindings`` and ``monotone_check`` flag
        drive the emitted file.
    lowered_r:
        Optional pre-lowered Taichi return-source for ``R`` (the Taichi expression
        string used by the guarded JIT smoke test). When ``None`` (the usual
        call), the emitter lowers ``spec.R`` itself via
        :func:`~mechdsl.lawgen.sympy_to_taichi.lower_expression` — which raises
        :class:`~mechdsl.lawgen.diagnostics.LawgenError` for an unsupported node
        (R2, no silent fallback), so an inexpressible law fails here rather than
        emitting a broken test.
    target_test_path:
        Where to write the file. Required. A ``str`` or :class:`~pathlib.Path`;
        parent directories are created if missing.

    Returns
    -------
    pathlib.Path
        The path the test file was written to (``target_test_path`` as a
        :class:`~pathlib.Path`).
    """
    if target_test_path is None:
        raise ValueError("emit_tests requires target_test_path (where to write the pytest file).")

    # Lowering ``R`` here is the fail-loud gate (R2): an unsupported node raises
    # LawgenError before any file is written. The returned Taichi source is what
    # the guarded JIT smoke test compiles. Guards on so the smoke test matches the
    # production (guarded) emission path.
    if lowered_r is None:
        lowered = lower_expression(spec.R, guards=True)
        lowered_r = lowered.returns[0]

    primary_name, _primary_symbol = _primary_variable(spec)
    arg_names = _ordered_symbol_names(spec, primary_name)

    # Per-factor FD-derivative axis: R→p, H→edot, Q→T (resolved against the spec's
    # bindings; see FACTOR_PRIMARY_VARIABLE). Each factor is FD-vs-analytic checked
    # w.r.t. its OWN primary — R/H/Q are three independent factors, not a value and
    # its derivative.
    factor_primaries = {
        role: _factor_primary_name(spec, role, primary_name) for role in ("R", "H", "Q")
    }

    source = _render_test_file(
        spec=spec,
        primary_name=primary_name,
        arg_names=arg_names,
        factor_primaries=factor_primaries,
        lowered_r=lowered_r,
    )

    path = Path(target_test_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _render_test_file(
    *,
    spec: PlasticityCarrierSpec,
    primary_name: str,
    arg_names: list[str],
    factor_primaries: dict[str, str],
    lowered_r: str,
) -> str:
    """Assemble the full generated pytest-file source as one string.

    Pure string assembly from f-strings over data (``srepr`` expression strings,
    the ordered argument names, the numeric constants). No SymPy code-printer and
    no regex rewriting is used (R4) — the expressions travel as ``srepr`` data and
    are rebuilt by ``sympy.sympify`` inside the generated file.
    """
    r_srepr = sp.srepr(spec.R)
    h_srepr = sp.srepr(spec.H)
    q_srepr = sp.srepr(spec.Q)

    args_literal = ", ".join(repr(name) for name in arg_names)
    # Placeholder value for EVERY argument (params and all variable bindings,
    # including the global primary). ``_args_at`` overrides just the one variable
    # it is sweeping and leaves the rest at the placeholder, so the dict must cover
    # every name — otherwise sweeping a non-``p`` factor primary (H->edot, Q->T)
    # would leave ``p`` unset. Built as a literal dict for readability.
    placeholder_items = ", ".join(f"{name!r}: {PLACEHOLDER_PARAM_VALUE!r}" for name in arg_names)

    # (role, SREPR-const-name, factor-primary-name) triples for the parametrized
    # FD-derivative test — one row per shipped factor, each differentiated w.r.t.
    # its OWN primary axis.
    fd_cases_literal = ", ".join(
        f"({role!r}, {srepr_const!r}, {factor_primaries[role]!r})"
        for role, srepr_const in (("R", "R_SREPR"), ("H", "H_SREPR"), ("Q", "Q_SREPR"))
    )

    monotone_block = _render_monotone_block(primary_name) if spec.monotone_check else ""
    header = _render_header(spec)

    # NB: the generated file deliberately does NOT use ``from __future__ import
    # annotations``. PEP 563 stringizes every annotation, and Taichi reads a
    # ``@ti.kernel``'s parameter annotation as a *type object* (``ti.f64``) — a
    # string ``"ti.f64"`` makes it raise ``Invalid type annotation``. The file
    # uses no forward references, so omitting the future-import is harmless.
    return f'''{header}
import math

import pytest
import sympy as sp

# --- Law data (loss-free ``srepr`` round-trip; rebuilt with ``sympy.sympify``) ---
R_SREPR = {r_srepr!r}
H_SREPR = {h_srepr!r}
Q_SREPR = {q_srepr!r}

# Ordered lambdify argument names: primary variable first, then the other
# variable bindings, then the material parameters.
ARG_NAMES = ({args_literal},)
PRIMARY_NAME = {primary_name!r}

# Fixed placeholder value for every argument (``_args_at`` overrides just the one
# variable it sweeps). The reference/FD/monotonicity checks are self-consistency
# identities that hold for any fixed params, so a real material card is
# unnecessary (value = {PLACEHOLDER_PARAM_VALUE!r}).
PLACEHOLDERS = {{{placeholder_items}}}

N_SAMPLE_POINTS = {N_SAMPLE_POINTS!r}
FD_STEP = {FD_STEP!r}
FD_RTOL = {FD_RTOL!r}
FD_ATOL = 1e-9
_SAMPLE_START = {_SAMPLE_START!r}
_SAMPLE_STOP = {_SAMPLE_STOP!r}

# Per-factor FD-derivative cases: (role, srepr, primary-variable-name). R/H/Q are
# three INDEPENDENT factors (hardening / rate / thermal), each auto-differentiated
# by the generator (``sympy.diff``) w.r.t. its OWN primary variable — R w.r.t. the
# plastic strain, H w.r.t. the rate, Q w.r.t. temperature. H is NOT ``d(R)/dp``.
# A factor that is constant in its primary (e.g. rate-independent ``H = 1``) has
# analytic derivative 0 and FD ~ 0, so the general FD-vs-analytic check still
# passes — no special-casing needed.
FD_CASES = ({fd_cases_literal},)

# Init Taichi at most once per process. ``ti.init`` resets Taichi's global runtime,
# so the guarded smoke test calls it only on first use — avoiding a redundant
# re-init if several generated law-test modules run in one pytest session.
_TAICHI_INITED = False


def _sample_points():
    """N evenly spaced, strictly positive, increasing values of the swept variable."""
    step = (_SAMPLE_STOP - _SAMPLE_START) / (N_SAMPLE_POINTS - 1)
    return [_SAMPLE_START + i * step for i in range(N_SAMPLE_POINTS)]


def _rebuild(srepr_str):
    """Rebuild a SymPy expression from its ``srepr`` string (loss-free, no eval)."""
    return sp.sympify(srepr_str)


def _symbols():
    """Return the ordered tuple of SymPy symbols for the lambdify arguments."""
    return tuple(sp.Symbol(name) for name in ARG_NAMES)


def _lambdified(expr):
    """``lambdify`` ``expr`` over the ordered argument symbols using math backend."""
    return sp.lambdify(_symbols(), expr, "math")


def _args_at(x, primary_name=PRIMARY_NAME):
    """Positional argument tuple with ``primary_name`` set to ``x``, rest pinned.

    Every other argument (params and the non-swept bindings) is fixed to its
    placeholder value, so this builds the evaluation point for both the reference
    sweep (``primary_name`` defaults to the global primary) and the per-factor FD
    test (which passes each factor's own primary)."""
    values = dict(PLACEHOLDERS)
    values[primary_name] = x
    return tuple(values[name] for name in ARG_NAMES)


def test_reference_eval():
    """R/H/Q evaluate to finite numbers at N sample points (reference eval)."""
    fns = [_lambdified(_rebuild(s)) for s in (R_SREPR, H_SREPR, Q_SREPR)]
    for x in _sample_points():
        args = _args_at(x)
        for fn in fns:
            value = fn(*args)
            assert math.isfinite(value), f"non-finite reference value {{value!r}} at p={{x!r}}"


@pytest.mark.parametrize(("role", "srepr_str", "primary_name"), FD_CASES)
def test_fd_derivative(role, srepr_str, primary_name):
    """Central FD derivative of each factor matches its analytic derivative.

    Covers ALL THREE factors R/H/Q, each differentiated w.r.t. its OWN primary
    variable (R->plastic strain, H->rate, Q->temperature), FD vs analytic
    ``sympy.diff`` at the N sample points, rtol <= 1e-5 (+ atol)."""
    expr = _rebuild(srepr_str)
    primary = sp.Symbol(primary_name)
    fn = _lambdified(expr)
    dfn = _lambdified(sp.diff(expr, primary))

    primary_index = ARG_NAMES.index(primary_name)
    for x in _sample_points():
        def _perturbed(delta, _x=x):
            args = list(_args_at(_x, primary_name))
            args[primary_index] = _x + delta
            return fn(*args)

        fd = (_perturbed(FD_STEP) - _perturbed(-FD_STEP)) / (2.0 * FD_STEP)
        analytic = dfn(*_args_at(x, primary_name))
        assert math.isclose(fd, analytic, rel_tol=FD_RTOL, abs_tol=FD_ATOL), (
            f"FD {{fd!r}} != analytic {{analytic!r}} for factor {{role!r}} "
            f"at {{primary_name}}={{x!r}} (rtol={{FD_RTOL!r}})"
        )
{monotone_block}

def _run_lowered_r({primary_name}_value):
    """JIT-compile the lowered Taichi R and evaluate it once at ``{primary_name}_value``.

    Defined at module scope (Taichi's source inspection cannot reliably compile a
    ``@ti.kernel`` nested inside a pytest test function). ``ti`` is imported here,
    not at module import, so the generated file imports cleanly without Taichi.
    Material constants are kernel-local, pinned to the placeholder value.
    """
    import taichi as ti

    global _TAICHI_INITED
    if not _TAICHI_INITED:
        ti.init(arch=ti.cpu)
        _TAICHI_INITED = True

    @ti.kernel
    def _kernel({primary_name}: ti.f64) -> ti.f64:
{_render_taichi_placeholder_assignments(spec, primary_name)}        return {lowered_r}

    return _kernel({primary_name}_value)


@pytest.mark.slow
def test_taichi_smoke():
    """Guarded Taichi JIT smoke: compile the lowered R once and call it.

    Skipped cleanly when Taichi is not installed (``importorskip``)."""
    pytest.importorskip("taichi")
    result = _run_lowered_r(0.5)
    assert math.isfinite(result), f"non-finite Taichi R output {{result!r}}"
'''


def _render_header(spec: PlasticityCarrierSpec) -> str:
    """Module docstring for the generated file, naming the source law."""
    monotone = "yes" if spec.monotone_check else "no"
    return (
        f'"""Auto-generated tests for plasticity carrier {spec.name!r} '
        f"(MechDSL lawgen P3-2).\n\n"
        f"DO NOT EDIT BY HAND — regenerate via mechdsl.lawgen.test_emitter.emit_tests.\n\n"
        f"Reference eval + per-factor FD-derivative (rtol={FD_RTOL!r}) self-consistency\n"
        f"checks over {N_SAMPLE_POINTS} sample points, with fixed placeholder parameters "
        f"(= {PLACEHOLDER_PARAM_VALUE!r}).\n"
        f"R/H/Q are three independent factors (hardening/rate/thermal); each is FD-checked\n"
        f"against its own analytic derivative w.r.t. its own primary variable.\n"
        f"Monotonicity block emitted: {monotone}. Taichi JIT smoke test is guarded\n"
        f'(skips when Taichi is unavailable).\n"""'
    )


def _render_monotone_block(primary_name: str) -> str:
    """The monotonicity test, emitted only when ``spec.monotone_check`` is True."""
    return f'''

def test_monotonicity():
    """R is non-decreasing in the accumulated plastic strain {primary_name!r}."""
    r_fn = _lambdified(_rebuild(R_SREPR))
    points = _sample_points()  # already strictly increasing
    values = [r_fn(*_args_at(x)) for x in points]
    for (x_lo, v_lo), (x_hi, v_hi) in zip(
        list(zip(points, values)), list(zip(points, values))[1:], strict=False
    ):
        assert v_lo <= v_hi + FD_ATOL, (
            f"R not monotone: R(p={{x_lo!r}})={{v_lo!r}} > R(p={{x_hi!r}})={{v_hi!r}}"
        )
'''


def _render_taichi_placeholder_assignments(spec: PlasticityCarrierSpec, primary_name: str) -> str:
    """Emit ``name = 1.0`` lines for every symbol the lowered R references but the
    kernel does not take as an argument (the material params and non-primary vars).

    The lowered R Taichi source references parameter and binding names directly;
    the smoke kernel only takes the primary variable, so every other referenced
    name must be a local constant. Pinned to the documented placeholder value.
    """
    names: list[str] = []
    for name in spec.parameters:
        if name != primary_name and name not in names:
            names.append(name)
    for name in spec.variable_bindings:
        if name != primary_name and name not in names:
            names.append(name)
    indent = " " * 8
    lines = [
        f"{indent}# Placeholder material constants pinned to "
        f"{PLACEHOLDER_PARAM_VALUE!r} (see PLACEHOLDERS).\n"
    ]
    lines += [f"{indent}{name}: ti.f64 = {PLACEHOLDER_PARAM_VALUE!r}\n" for name in names]
    return "".join(lines)
