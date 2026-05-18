# Phase 8 Tasks Analysis

**Plan:** `dev/design_docs/PLAN-B.md` §B8 (lines 223-239)
**Phase:** 8 — MFEM and MOOSE backend printers
**Branch:** `plan-b_phase-8` (off `plan-b_phase-7` tip `f7df56d`)
**Date:** 2026-04-17

## Complexity / Risk Matrix

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined | Blocked By | Blocks | Model |
|---------|-------|-----------------:|-----------:|---------:|------------|--------|-------|
| P8-1 | MFEM printer (C++ NonlinearFormIntegrator + Voigt + MPI) | 4 | 3 | 7 | P1-1 (done) | P8-3, P9-1 | Opus |
| P8-2 | MOOSE printer (ComputeStressBase + RankTwoTensor + input files) | 4 | 3 | 7 | P1-1 (done) | P8-3, P9-1 | Opus |
| P8-3 | Cross-backend verification (Taichi/MFEM/MOOSE match within 1e-8) | 5 | 5 | 10 | P8-1, P8-2 | P9-1 | Opus |

### Complexity rationale

- **P8-1 (4/5):** Net-new C++ codegen module (~300-500 lines) mirroring `taichi_printer` structure. Must handle Voigt conversion, MFEM's `NonlinearFormIntegrator` API, MPI via `ParNonlinearForm`. Comparable in shape to the existing Taichi printer but in an unfamiliar C++ emission style.
- **P8-2 (4/5):** Similar scope to P8-1 but with a different target (MOOSE `ComputeStressBase`). Additional wrinkle: must also emit a matching `.i` input file in MOOSE's grammar.
- **P8-3 (5/5):** Integrates all three backends, requires actual MFEM/MOOSE binaries (unavailable locally), cantilever driver building, displacement-field parsing, tolerance comparison. Most of the verification happens in CI.

### Risk rationale

- **P8-1 (3/5):** No local MFEM to compile-verify — mitigated via libclang parse-only tests per design decision. Voigt conversion has sign/scaling traps (engineering γ = 2ε), but round-trip test catches misuse.
- **P8-2 (3/5):** MOOSE input-file grammar is particular; templated `.i` rather than string-concat mitigates. Same parse-only caveat as MFEM.
- **P8-3 (5/5):** Heavyweight installs (Docker image required in CI), brittle to version drift. Local skip path must be clean. Cross-backend 1e-8 tolerance is tight for three independent solver stacks.

## Parallelism

**P8-1 ∥ P8-2** — first parallelisable batch in Plan B. Different printer modules, no shared source files beyond `mechdsl.ir.mechanics_ir` / `mechdsl.codegen.artifact` (read-only).

File scope check (no overlap):
- P8-1: `src/mechdsl/codegen/mfem_printer.py`, `src/mechdsl/codegen/mfem_template/CMakeLists.txt`, `tests/test_mfem_printer.py`
- P8-2: `src/mechdsl/codegen/moose_printer.py`, `src/mechdsl/codegen/moose_template/input_template.i`, `tests/test_moose_printer.py`

Both tasks have combined score > 6 → **Opus 4.6** implementers and reviewers (per Model assignment rules).

## Execution plan

1. **Batch 1 (parallel):** P8-1 + P8-2 — dispatched concurrently, each with its own implementer subagent, each in its own commit.
2. **Batch 2 (sequential after both batch 1 tasks pass all gates):** P8-3 — sequential.

## Risk carry-forward from earlier phases

1. **Phase 5 `integration_break` pattern (3 recurrences):** Strict-key guards in `to_dict`/`from_dict` routines have tripped previous printer edits. P8-1/P8-2 don't touch `ProblemIR` or `ElementIR` serialisation — low risk, but reviewers should confirm no incidental edits.
2. **Phase 7 `allocate_explicit_fields` call-ordering gotcha (medium):** Only affects Taichi's lazy materialise — MFEM/MOOSE don't use it. Non-issue for Phase 8; flagged for future Taichi-printer cleanup.
3. **Voigt convention trap:** MVP uses **tensorial** `[xx, yy, zz, xy, xz, yz]` with unscaled shears. MFEM and MOOSE default to **engineering** Voigt (γ = 2ε). Round-trip unit tests in P8-1/P8-2 gate this explicitly.
4. **Pytest markers:** `regression` is NOT registered in root `pyproject.toml`. Scaffold already corrected P8-3 from `regression` → `integration`. Keep other stubs on registered markers.
