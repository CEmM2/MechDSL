# Task P1-7: TL/UL equivalence + rigid rotation tests — Complete

**Phase 1 exit criterion: met.**

## Implementation Summary

Added a handwritten UL reference solver (`ref_hex8_ul.py`) and four integration tests that serve as the Phase 1 exit gate. The UL solver mirrors the TL reference solver structure with Updated Lagrangian residual (Cauchy stress, spatial gradients, current volume) and tangent (Truesdell spatial tangent + standard geometric stiffness).

The cantilever test solves the same 4x2x1 beam problem with both TL and UL Newton solvers and asserts the converged displacements agree within 1e-8. Three rigid rotation tests verify that all three objective rates (Jaumann, Truesdell, Green-Naghdi) produce zero Cauchy stress rate under a 30-degree rotation with general pre-stress.

Additionally resolved the P1-4 deferred tangent stub with a finite-difference verification of the reference UL tangent matvec.

## Gate History

**Gate A:** 1 attempt -> Pass
**Gate B:** 1 attempt -> Pass (10/10)
**Gate C:** Tests 1031/1031 (100%)

No failures across any gate.

## Files Changed

| File | Change |
|------|--------|
| `packages/mechdsl-core/tests/ref/ref_hex8_ul.py` | New handwritten UL reference solver: element force, tangent matvec, global assembly, Newton solver |
| `packages/mechdsl-core/tests/test_ul_equivalence.py` | 4 stubs replaced: cantilever TL/UL equivalence (slow), 3 rigid rotation rate tests (fast) |
| `packages/mechdsl-core/tests/test_taichi_printer_ul.py` | Resolved P1-4 deferred skip with FD tangent verification |

## Test Evidence

- Full fast suite: **1031 passed**, 0 skipped, 51 deselected, 0 failed (19.56s)
- Task-scoped: `test_ul_equivalence.py` -> 4/4 PASSED (2.97s incl. slow)
- Resolved P1-4 deferred: `test_ul_tangent_matches_handwritten_reference` -> PASSED
- Ruff: clean. Mypy: clean.

## Physics Note: Tangent Decomposition

The reference solver uses `truesdell_tangent + standard geometric stiffness` while the P1-4 emitted code uses `jaumann_tangent + Hadamard geometric stiffness`. These are different decompositions of the same total tangent operator (`c^Jau = c^tau + T(sigma)` moves part of the geometric term into the material term). The cantilever test confirms both decompositions converge to the same solution — mathematical equivalence verified numerically.

## Open Questions

None. **Phase 1 is complete** — all 7 tasks done, zero remaining skips. Downstream phases (P2-P10) are unblocked at their Phase 1 entry points.
