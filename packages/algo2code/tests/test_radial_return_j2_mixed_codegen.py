"""algo2code codegen test for the J2 mixed-hardening return-map.

constitutive_latex Phase 6 (P6-3). Pins what the algo2code parser / Taichi
backend produce on the ``algo2code.library.radial_return_j2_mixed`` source so any
regression in algo2code surfaces here. Mirrors
``test_radial_return_j2_kinematic_codegen.py``.

The mixed scalar source owns only the plastic-multiplier solve. Yield is on the
trial RELATIVE-stress equivalent ``xi_eq`` against the EXPANDING radius
``sigma_y(alpha) = sigy0 + K*alpha^n``. Because the isotropic part is a nonlinear
power law in ``alpha = alpha_old + dl``, the consistency condition is NONLINEAR
in ``dl`` and is solved by the scalar Newton loop (isotropic-variant structure)
with the linear kinematic ``(3*mu + H_kin)*dl`` term added to the residual.
"""

from __future__ import annotations

import ast

import pytest

from algo2code import transpile
from algo2code.algo_parser import parse_algorithm
from algo2code.library.radial_return_j2_mixed import (
    RADIAL_RETURN_J2_MIXED_LATEX,
    transpile_radial_return_j2_mixed,
)

JIT_BUDGET_LINES_PER_TI_FUNC = 512  # 07-CONVENTIONS.md


@pytest.mark.unit
def test_radial_return_j2_mixed_parses() -> None:
    """Algpseudocode parses to an Algorithm node with the expected name, backend,
    and mixed argument set: relative-stress equivalent + accumulated plastic
    strain + BOTH the isotropic (K, n) and kinematic (H_kin) hardening params."""
    algo = parse_algorithm(RADIAL_RETURN_J2_MIXED_LATEX)
    assert algo.name == "radial_return_j2_mixed"
    assert algo.backend == "taichi"
    arg_names = [name for name, _ in algo.args]
    for required in (
        "xi_eq",
        "alpha",
        "mu",
        "K",
        "n",
        "H_kin",
        "sigy0",
        "tol",
        "max_iter",
    ):
        assert required in arg_names, (
            f"radial_return_j2_mixed args must include {required!r}; got {arg_names}"
        )


@pytest.mark.unit
def test_taichi_backend_emits_valid_python() -> None:
    """Transpile to Taichi and confirm the result is syntactically valid."""
    code = transpile(RADIAL_RETURN_J2_MIXED_LATEX, backend="taichi")
    assert code.startswith("import taichi as ti"), (
        f"emitted code missing taichi import header:\n{code[:200]}"
    )
    ast.parse(code)


@pytest.mark.unit
def test_emitted_module_declares_entry_point() -> None:
    """Emitted module exposes a top-level ``radial_return_j2_mixed``."""
    code = transpile(RADIAL_RETURN_J2_MIXED_LATEX, backend="taichi")
    tree = ast.parse(code)
    func_names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert "radial_return_j2_mixed" in func_names, (
        f"expected radial_return_j2_mixed entry point; emitted: {func_names}"
    )


@pytest.mark.unit
def test_emitted_module_under_jit_budget() -> None:
    """JIT budget probe (07-CONVENTIONS.md <= 512 lines per @ti.func).

    The scalar return-map emits as a single plain function; the whole-module
    line count is a strict overestimate of any single @ti.func body.
    """
    code = transpile(RADIAL_RETURN_J2_MIXED_LATEX, backend="taichi")
    line_count = len(code.splitlines())
    assert line_count <= JIT_BUDGET_LINES_PER_TI_FUNC, (
        f"emitted module {line_count} lines > {JIT_BUDGET_LINES_PER_TI_FUNC}"
    )


@pytest.mark.unit
def test_library_wrapper_exposes_transpile_helper() -> None:
    """Library wrapper exposes ``transpile_radial_return_j2_mixed`` and the
    transpile result loads as a callable — proving end-to-end consumption."""
    from algo2code.library import radial_return_j2_mixed as lib

    assert hasattr(lib, "transpile_radial_return_j2_mixed"), (
        "library wrapper must expose the transpile helper"
    )
    source = lib.transpile_radial_return_j2_mixed(backend="taichi")
    namespace: dict = {}
    exec(compile(source, "<algo2code:radial_return_j2_mixed>", "exec"), namespace)
    assert callable(namespace.get("radial_return_j2_mixed")), (
        "transpiled module must define the radial_return_j2_mixed callable"
    )


@pytest.mark.unit
def test_transpile_is_deterministic() -> None:
    """Transpiling twice yields byte-identical output (golden-stable)."""
    first = transpile_radial_return_j2_mixed(backend="taichi")
    second = transpile_radial_return_j2_mixed(backend="taichi")
    assert first == second, "transpile output is not deterministic (byte-unstable)"


@pytest.mark.unit
def test_newton_solve_satisfies_mixed_consistency() -> None:
    """The transpiled scalar Newton solve returns to the (expanding) surface.

    The mixed consistency residual ``r(dl) = xi_eq - (3*mu + H_kin)*dl -
    sigma_y(alpha_old + dl)`` is nonlinear in ``dl`` (power-law isotropic part),
    so there is no closed form — instead the converged ``dl`` must drive ``r`` to
    ~0. Starts from a pre-yielded ``alpha_old > 0`` to stay clear of the n<1
    alpha->0 slope-guard boundary. Also checks the elastic branch returns
    ``(0, alpha, 0)``.
    """
    source = transpile_radial_return_j2_mixed(backend="taichi")
    namespace: dict = {}
    exec(compile(source, "<algo2code:radial_return_j2_mixed>", "exec"), namespace)
    fn = namespace["radial_return_j2_mixed"]

    mu = 76_923.0
    k = 500.0
    n = 0.5
    h_kin = 20_000.0
    sigy0 = 250.0
    alpha_old = 0.01  # pre-yielded — past the n<1 alpha->0 boundary

    def sigma_y(a: float) -> float:
        return sigy0 + k * a**n

    # Elastic: xi_eq below the (already-expanded) yield radius.
    plastic, alpha_new, dl = fn(
        xi_eq=sigma_y(alpha_old) - 10.0,
        alpha=alpha_old,
        mu=mu,
        K=k,
        n=n,
        H_kin=h_kin,
        sigy0=sigy0,
        tol=1e-12,
        max_iter=50,
    )
    assert plastic == 0
    assert alpha_new == alpha_old
    assert dl == 0

    # Plastic: converged dl must satisfy the nonlinear consistency residual.
    xi_eq = sigma_y(alpha_old) + 200.0
    plastic, alpha_new, dl = fn(
        xi_eq=xi_eq,
        alpha=alpha_old,
        mu=mu,
        K=k,
        n=n,
        H_kin=h_kin,
        sigy0=sigy0,
        tol=1e-12,
        max_iter=50,
    )
    assert plastic == 1
    assert abs(alpha_new - (alpha_old + dl)) < 1e-14
    residual = xi_eq - (3.0 * mu + h_kin) * dl - sigma_y(alpha_old + dl)
    assert abs(residual) < 1e-8, f"converged dl leaves residual {residual:.3e}"
