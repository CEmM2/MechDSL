"""algo2code codegen test for the J2 kinematic linear-hardening return-map.

constitutive_latex Phase 6 (P6-2). Pins what the algo2code parser / Taichi
backend produce on the ``algo2code.library.radial_return_j2_kinematic`` source so
any regression in algo2code surfaces here. Mirrors
``test_radial_return_codegen.py`` (the isotropic power-law variant).

The kinematic scalar source owns only the plastic-multiplier solve. Because the
discrete consistency condition is linear, ``dl`` has the closed form
``(xi_eq - sigma_y0) / (3*mu + H_kin)``; the source is authored as a
fixed-iteration Newton loop (denominator ``3*mu + H_kin``) that reaches the exact
root in one iteration, for transpile-pattern parity with the isotropic variant.
"""

from __future__ import annotations

import ast

import pytest

from algo2code import transpile
from algo2code.algo_parser import parse_algorithm
from algo2code.library.radial_return_j2_kinematic import (
    RADIAL_RETURN_J2_KINEMATIC_LATEX,
    transpile_radial_return_j2_kinematic,
)

JIT_BUDGET_LINES_PER_TI_FUNC = 512  # 07-CONVENTIONS.md


@pytest.mark.unit
def test_radial_return_j2_kinematic_parses() -> None:
    """Algpseudocode parses to an Algorithm node with the expected name,
    backend, and kinematic argument set (relative-stress equivalent + Prager
    modulus, no isotropic-hardening params)."""
    algo = parse_algorithm(RADIAL_RETURN_J2_KINEMATIC_LATEX)
    assert algo.name == "radial_return_j2_kinematic"
    assert algo.backend == "taichi"
    arg_names = [name for name, _ in algo.args]
    for required in ("xi_eq", "mu", "H_kin", "sigy0", "tol", "max_iter"):
        assert required in arg_names, (
            f"radial_return_j2_kinematic args must include {required!r}; got {arg_names}"
        )
    # Kinematic hardening has a constant yield radius — no isotropic K / n.
    assert "K" not in arg_names, "kinematic variant must not carry isotropic K"
    assert "n" not in arg_names, "kinematic variant must not carry isotropic n"


@pytest.mark.unit
def test_taichi_backend_emits_valid_python() -> None:
    """Transpile to Taichi and confirm the result is syntactically valid."""
    code = transpile(RADIAL_RETURN_J2_KINEMATIC_LATEX, backend="taichi")
    assert code.startswith("import taichi as ti"), (
        f"emitted code missing taichi import header:\n{code[:200]}"
    )
    ast.parse(code)


@pytest.mark.unit
def test_emitted_module_declares_entry_point() -> None:
    """Emitted module exposes a top-level ``radial_return_j2_kinematic``."""
    code = transpile(RADIAL_RETURN_J2_KINEMATIC_LATEX, backend="taichi")
    tree = ast.parse(code)
    func_names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert "radial_return_j2_kinematic" in func_names, (
        f"expected radial_return_j2_kinematic entry point; emitted: {func_names}"
    )


@pytest.mark.unit
def test_emitted_module_under_jit_budget() -> None:
    """JIT budget probe (07-CONVENTIONS.md <= 512 lines per @ti.func).

    The scalar return-map emits as a single plain function; the whole-module
    line count is a strict overestimate of any single @ti.func body.
    """
    code = transpile(RADIAL_RETURN_J2_KINEMATIC_LATEX, backend="taichi")
    line_count = len(code.splitlines())
    assert line_count <= JIT_BUDGET_LINES_PER_TI_FUNC, (
        f"emitted module {line_count} lines > {JIT_BUDGET_LINES_PER_TI_FUNC}"
    )


@pytest.mark.unit
def test_library_wrapper_exposes_transpile_helper() -> None:
    """Library wrapper exposes ``transpile_radial_return_j2_kinematic`` and the
    transpile result loads as a callable — proving end-to-end consumption."""
    from algo2code.library import radial_return_j2_kinematic as lib

    assert hasattr(lib, "transpile_radial_return_j2_kinematic"), (
        "library wrapper must expose the transpile helper"
    )
    source = lib.transpile_radial_return_j2_kinematic(backend="taichi")
    namespace: dict = {}
    exec(compile(source, "<algo2code:radial_return_j2_kinematic>", "exec"), namespace)
    assert callable(namespace.get("radial_return_j2_kinematic")), (
        "transpiled module must define the radial_return_j2_kinematic callable"
    )


@pytest.mark.unit
def test_transpile_is_deterministic() -> None:
    """Transpiling twice yields byte-identical output (golden-stable)."""
    first = transpile_radial_return_j2_kinematic(backend="taichi")
    second = transpile_radial_return_j2_kinematic(backend="taichi")
    assert first == second, "transpile output is not deterministic (byte-unstable)"


@pytest.mark.unit
def test_closed_form_plastic_multiplier() -> None:
    """The transpiled scalar solve reproduces the closed-form ``dl``.

    For linear kinematic hardening ``dl = (xi_eq - sigy0) / (3*mu + H_kin)``
    exactly (the loop residual is linear, root reached in one Newton step).
    Also checks the elastic branch returns ``(0, 0)``.
    """
    source = transpile_radial_return_j2_kinematic(backend="taichi")
    namespace: dict = {}
    exec(compile(source, "<algo2code:radial_return_j2_kinematic>", "exec"), namespace)
    fn = namespace["radial_return_j2_kinematic"]

    mu = 76_923.0
    h_kin = 20_000.0
    sigy0 = 250.0

    # Elastic: xi_eq below the yield radius.
    plastic, dl = fn(xi_eq=200.0, mu=mu, H_kin=h_kin, sigy0=sigy0, tol=1e-12, max_iter=5)
    assert plastic == 0
    assert dl == 0

    # Plastic: closed form.
    xi_eq = 350.0
    plastic, dl = fn(xi_eq=xi_eq, mu=mu, H_kin=h_kin, sigy0=sigy0, tol=1e-12, max_iter=5)
    assert plastic == 1
    expected = (xi_eq - sigy0) / (3.0 * mu + h_kin)
    assert abs(dl - expected) < 1e-12, f"dl {dl} != closed form {expected}"
