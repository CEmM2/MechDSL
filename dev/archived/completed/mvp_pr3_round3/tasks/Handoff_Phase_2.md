# Phase 2 Handoff — Error Handling Fixes

## Phase 1 Completion Summary

**All 10 Phase 1 tasks completed and verified.**

### Changes Made

**`packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py`** (primary file):
- **C1**: J2 Newton loop changed from `ti.static(range(20))` to `range(20)` — enables runtime `break`
- **C2**: Quadrature loop changed from `range(N_QP)` to `ti.static(range(N_QP))` — enables Python list access for GRAD_AT_QUAD and QUAD_WEIGHTS
- **C4**: Newton non-convergence now emits `raise RuntimeError(...)` instead of `return max_iter`
- **C4b**: NaN/Inf guard added after `res_norm` computation — catches constitutive model failures
- **C5**: Three node loops (lines 429, 460, 490) changed from `ti.static(range(N_NODES))` to `range(N_NODES)`. GRAD_AT_QUAD gather loop at line 443 kept as `ti.static` for Python list access.
- **H1**: Convergence check added after J2 return mapping Newton loop — sets `dl = NaN` on non-convergence
- **H2**: `dl = ti.max(dl, 0.0)` clamp added before stress update
- **H9**: Material model validation at top of `emit()` — raises `ValueError` for unknown models
- **CM3**: Function renamed `emit_constitutive_stub` → `emit_constitutive_update`
- **CM4**: Fixed `_fmt_float` comment
- **CM5**: Added convention reference to emitted Newton tolerance
- **CM7**: Changed PLAN-A line reference to phase reference

**`.claude/rules/codegen.md`**: Updated index treatment with quadrature point and node index carve-outs

**Test files updated** (8 existing assertions + 12 new tests):
- `test_plastic_emission.py:114` — updated for C1
- `test_taichi_printer.py:216-234` — updated for C2, C5 (split into 4 more specific tests)
- `test_emission_verification.py:280-292` — updated for C2
- `test_emission_verification.py:370-380` — updated for C5 (split into 2 tests)
- `test_emission_verification.py:650-653` — updated for C4
- `test_codegen.py:156-190` — updated for C2, C5
- `test_phase1_codegen_fixes.py` — 12 new tests covering C4, C4b, H1, H2, H9, CM3

### Verification Evidence
- 633/633 fast tests passed (excluding golden snapshots)
- 12/12 new Phase 1 tests passed
- 2 golden snapshot failures — **expected**, deferred to Phase 6
- Ruff check: all passed

### Known State for Phase 2
- **Golden files are stale** — do NOT regenerate until Phase 6 (after all codegen changes are complete)
- `taichi_printer.py` has grown from 733 to ~755 lines due to convergence check, NaN guard, dl clamp, and validation additions
- Phase 2 task R3.2.3 also modifies `taichi_printer.py` (CG failure counter) — be aware of line number shifts

### Files NOT touched by Phase 1 (Phase 2 targets)
- `solver/import_adapter.py` — C3 (CG/PCG breakdown warning)
- `symbolic/models/j2_power_law.py` — H3 (radial_return stall guard)
- `codegen/einsum_optimizer.py` — H5 (FLOPS sentinel)
- `tests/ref/ref_hex8_elastic.py` — H6 (Newton non-convergence)
- `codegen/boundary_codegen.py` — H7+H8 (face area/axis guards)
