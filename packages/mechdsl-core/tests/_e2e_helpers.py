"""Shared helpers for end-to-end / integration tests in mechdsl-core.

post_recovery_plan Phase 6 (P6-1) — single source of truth for test
helpers that were previously duplicated across four sites:

- ``test_e2e_taichi.py``           (promoted in P6-2)
- ``plan_tests/recovery_plan_latex_contract/test_p7_2.py``  (promoted in P6-2)
- ``test_e2e_plastic.py``          (promoted in P7 cleanup)
- ``test_explicit_dynamics_acceptance.py``  (promoted in P7 cleanup)

All four call sites now import from this module. The family-split
rule (cross-test imports allowed once a third caller appears) is
satisfied. Future helpers used in 3+ test files belong here.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

# Element constants for resolving ``ti.static(range(...))`` trip counts when
# weighting unrolled lines (Hex8, 2x2x2 Gauss). Used by
# :func:`count_unrolled_kernel_lines` (PlanJune14 WI-1 honest JIT-budget test).
_UNROLL_CONSTS = {"DIM": 3, "N_QP": 8, "N_NODES": 8}


def _slice_kernel_body(source: str, fn: str) -> str:
    """Return the source text of the named function/kernel ``fn`` from *source*.

    Slices from ``def {fn}(`` to the next top-level boundary (next ``def`` /
    ``class`` / ``@ti.kernel`` / section banner), so the count below sees only
    one kernel body. Mirrors the diagnostic in ``/tmp/measure_j2_budget.py``.
    """
    start = source.find(f"def {fn}(")
    assert start >= 0, f"{fn} not found in generated source"
    rest = source[start:]
    nxt = len(rest)
    for boundary in ("\ndef ", "\nclass ", "\n@ti.kernel", "\n# ===="):
        i = rest.find(boundary, 1)
        if i != -1:
            nxt = min(nxt, i)
    return rest[:nxt]


def count_unrolled_kernel_lines(source: str, fn: str) -> int:
    """Count the *unrolled* statement count of kernel ``fn`` in generated *source*.

    The project's "unrolled lines" semantics (07-CONVENTIONS §JIT-budget): each
    executable statement is weighted by the product of the enclosing
    ``ti.static(range(...))`` trip counts. ``ti.static`` loop headers vanish on
    unroll and multiply their body; runtime ``for`` headers appear once per
    enclosing static unroll (body weight x1). Comments / blanks / the kernel
    docstring are excluded. ``DIM`` / ``N_QP`` / ``N_NODES`` resolve to the Hex8
    constants. This is the same logic validated in ``/tmp/measure_j2_budget.py``
    and is what makes the budget test honest about the *full* ``@ti.kernel``
    (PlanJune14 WI-1), not just the inner contraction ``@ti.func``.
    """
    body = _slice_kernel_body(source, fn)
    stack: list[tuple[int, int]] = []  # (header_indent, static_factor); runtime -> 1
    unrolled = 0
    in_doc = False
    for line in body.split("\n"):
        s = line.strip()
        if not s:
            continue
        if in_doc:
            if '"""' in s:
                in_doc = False
            continue
        if s.startswith('"""') or s.startswith("'''"):
            if s.count('"""') < 2 and s.count("'''") < 2:
                in_doc = True
            continue
        if s.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        while stack and indent <= stack[-1][0]:
            stack.pop()
        factor = 1
        for _, f in stack:
            factor *= f
        if s.startswith("for ") and "ti.static(range(" in s:
            inner = s.split("ti.static(range(", 1)[1].split(")", 1)[0].strip()
            trip = int(inner) if inner.isdigit() else _UNROLL_CONSTS.get(inner, 1)
            stack.append((indent, trip))
            continue  # static header vanishes on unroll
        if s.startswith("for "):
            unrolled += factor  # runtime header appears once per enclosing static unroll
            stack.append((indent, 1))
            continue
        unrolled += factor
    return unrolled


def _import_generated_module(source: str, tmp_path: Path, name: str = "gen_e2e") -> ModuleType:
    """Write generated Taichi source to ``tmp_path/<name>.py`` and import
    it via ``importlib`` so tests can drive the emitted kernels.

    Identical signature and behaviour to the four previously-duplicated
    copies. Returns the loaded module object.
    """
    mod_path = tmp_path / f"{name}.py"
    mod_path.write_text(source, encoding="utf-8")

    spec = importlib.util.spec_from_file_location(name, mod_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


__all__ = ["_import_generated_module", "count_unrolled_kernel_lines"]
