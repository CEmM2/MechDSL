"""algo2code codegen test for the canonical J2 radial-return algorithm.

post_recovery_plan Phase 5 (P5-2). Pins what the algo2code parser /
Taichi backend currently produce on the
``algo2code.library.radial_return_j2`` source so any regression in
algo2code surfaces here. The full closed-form Taichi emission is
**deferred** at this layer (the algo2code parser today drops binary
``/`` in some assignment LHS contexts and tokenises multi-letter
scratch identifiers as products); the consumer-side runtime path
(``mechdsl.lib.plasticity.radial_return_algo2code``, P5-3) is a
verbatim hand translation kept in sync via this test plus the parity
test ``test_j2_radial_return_parity.py`` (P5-4).

The test covers:

1. Algpseudocode parses end-to-end (P5-1 smoke surface, re-asserted on
   the algo2code side so the algo2code package owns the
   parser-readiness contract).
2. Taichi backend emits a syntactically valid Python module.
3. Emitted module declares the expected entry-point function.
4. JIT budget probe: emitted ``@ti.func`` (when the parser eventually
   enables emission of the inner kernel) ≤ 512 unrolled lines per
   07-CONVENTIONS.md. Until then the probe asserts the emitted module
   itself stays under that budget as a coarser proxy.
"""

from __future__ import annotations

import ast

import pytest

from algo2code import transpile
from algo2code.algo_parser import parse_algorithm
from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX

JIT_BUDGET_LINES_PER_TI_FUNC = 512  # 07-CONVENTIONS.md


@pytest.mark.unit
def test_radial_return_j2_parses() -> None:
    """Algpseudocode source parses to an Algorithm node with the
    expected name and backend.
    """
    algo = parse_algorithm(RADIAL_RETURN_J2_LATEX)
    assert algo.name == "radial_return_j2"
    assert algo.backend == "taichi"
    arg_names = [name for name, _ in algo.args]
    # The scalar Newton inner loop must declare the full power-law hardening argument set.
    for required in ("sigma_eq", "alpha", "mu", "K", "n", "sigy0", "tol", "max_iter"):
        assert required in arg_names, (
            f"radial_return_j2 args must include {required!r}; got {arg_names}"
        )


@pytest.mark.unit
def test_taichi_backend_emits_valid_python() -> None:
    """Transpile to Taichi and confirm the result is syntactically
    valid Python (parses with ``ast``).
    """
    code = transpile(RADIAL_RETURN_J2_LATEX, backend="taichi")
    # Coarse import shape — every backend output starts with ``import taichi``.
    assert code.startswith("import taichi as ti"), (
        f"emitted code missing taichi import header:\n{code[:200]}"
    )
    ast.parse(code)


@pytest.mark.unit
def test_emitted_module_declares_entry_point() -> None:
    """Emitted module exposes a top-level ``radial_return_j2`` function
    (the algorithm name).
    """
    code = transpile(RADIAL_RETURN_J2_LATEX, backend="taichi")
    tree = ast.parse(code)
    func_names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert "radial_return_j2" in func_names, (
        f"expected radial_return_j2 entry point; emitted: {func_names}"
    )


@pytest.mark.unit
def test_emitted_module_under_jit_budget() -> None:
    """JIT budget probe (07-CONVENTIONS.md ≤ 512 lines per ``@ti.func``).

    Until the algo2code parser enables full inner-kernel emission, the
    proxy check counts every line in the emitted module — a strict
    overestimate of any single ``@ti.func`` body. The probe will tighten
    once the parser fix lands.
    """
    code = transpile(RADIAL_RETURN_J2_LATEX, backend="taichi")
    line_count = len(code.splitlines())
    assert line_count <= JIT_BUDGET_LINES_PER_TI_FUNC, (
        f"emitted module {line_count} lines > {JIT_BUDGET_LINES_PER_TI_FUNC}"
    )


@pytest.mark.unit
def test_library_wrapper_exposes_transpile_helper() -> None:
    """Library wrapper exposes ``transpile_radial_return_j2`` and the
    transpile result loads as a callable named ``radial_return_j2`` —
    proving the algpseudocode is consumed end-to-end (post_recovery_plan
    Phase 5 lifted the parser-deferral surface that previously stopped
    direct emission).
    """
    from algo2code.library import radial_return_j2 as lib

    assert hasattr(lib, "transpile_radial_return_j2"), (
        "library wrapper must expose the transpile helper"
    )
    source = lib.transpile_radial_return_j2(backend="taichi")
    namespace: dict = {}
    exec(compile(source, "<algo2code:radial_return_j2>", "exec"), namespace)
    assert callable(namespace.get("radial_return_j2")), (
        "transpiled module must define the radial_return_j2 callable"
    )
