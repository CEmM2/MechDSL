# Phase 8 Scaffold Validation

**Plan:** `dev/design_docs/PLAN-B.md` §B8 (lines 223-239)
**Phase:** 8 — MFEM and MOOSE backend printers
**Branch:** `plan-b_phase-8` (off `plan-b_phase-7` tip)
**Date:** 2026-04-17

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P8-1 | MFEM printer (C++ NonlinearFormIntegrator + Voigt + MPI) | none — all fields populated | auto-filled `test_artifacts` + `verification_commands` |
| P8-2 | MOOSE printer (ComputeStressBase + RankTwoTensor + input files) | none — all fields populated | auto-filled `test_artifacts` + `verification_commands` |
| P8-3 | Cross-backend verification (Taichi/MFEM/MOOSE match within 1e-8) | `test_plan.tier` was `"regression"` (marker not registered) → swapped to `"integration"` to match `@pytest.mark.integration` | auto-filled `test_artifacts` + `verification_commands` + tier correction |

## Existing Test Coverage Found

Pre-scaffold grep (case-insensitive) for `mfem`, `moose`, `cross.?backend` across `packages/mechdsl-core` returned **zero** existing source or test files — Phase 8 is net-new scaffold. Nothing to deduplicate.

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| — | — | — | — | none (Phase 8 is net-new territory) |

## Stubs Generated

- `packages/mechdsl-core/tests/test_mfem_printer.py` — 3 `@unit` stubs covering P8-1 acceptance criteria (MFEM emission structural, Voigt round-trip, CMakeLists template).
- `packages/mechdsl-core/tests/test_moose_printer.py` — 3 `@unit` stubs covering P8-2 (MOOSE C++ emission, input `.i` file, RankTwoTensor mapping).
- `packages/mechdsl-core/tests/test_cross_backend.py` — 3 `@slow @integration` stubs covering P8-3 pairwise cross-backend verification (Taichi/MFEM, Taichi/MOOSE, MFEM/MOOSE).

All 9 stubs collect cleanly under pytest (`--collect-only` → 9 tests, 0 warnings after marker correction). Bodies all `pytest.skip("stub — implement after Task P8-X is complete")`.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 9 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 9 |
| New stub files created | 3 |
| Total new stubs generated | 9 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_artifacts`, `verification_commands` on all three JSONs; tier correction on P8-3 (`regression` → `integration`) |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| — | — | — | none |

## Ready for Execute

Fully scaffolded:
- P8-1: MFEM printer (C++ NonlinearFormIntegrator + Voigt + MPI)
- P8-2: MOOSE printer (ComputeStressBase + RankTwoTensor + input files)
- P8-3: Cross-backend verification (Taichi/MFEM/MOOSE match within 1e-8)

## Risk Carry-forward from Phase 7

1. **`allocate_explicit_fields` call-ordering gotcha** (`Handoff_Phase_8.md` item 1) — Phase 8 fix opportunity when extending codegen. The MFEM/MOOSE printers don't use Taichi's lazy materialise, so they sidestep the issue, but a small Taichi-printer edit (merge allocators or add docstring) is a reasonable Phase 8 side-quest.
2. **MFEM and MOOSE installs are heavyweight** — P8-3 must skip gracefully on local dev machines without binaries. CI integration needs a Docker image with both pre-installed.
3. **Voigt convention conversion must be consistent** — MVP uses tensorial Voigt (unscaled shears); MFEM/MOOSE use engineering Voigt (γ = 2ε). Phase 8 round-trip tests must verify exact invertibility.
4. **Tier-mismatch hazard**: `regression` pytest marker is not registered in root `pyproject.toml`. I corrected P8-3 to `integration` + `slow`. If future Plan B phases call for a true "regression" tier, register the marker first.

## Dependency order (for ExecPhase)

1. **P8-1** (MFEM printer) — blocked_by P1-1 (done). Ready to execute.
2. **P8-2** (MOOSE printer) — blocked_by P1-1 (done). Ready to execute. **Parallelisable with P8-1** — different printer modules, no shared files beyond Mechanics IR (read-only).
3. **P8-3** (Cross-backend verification) — blocked_by P8-1 AND P8-2. Sequential after both printers land.

## Notes for ExecPhase dispatcher

- P8-1 and P8-2 can run in parallel (first time in Plan B — all prior phases were strictly sequential).
- Both printers are net-new files; low risk of integration breaks on existing suite.
- P8-3 cross-backend test should skip cleanly on the local dev machine (no MFEM/MOOSE binaries). Acceptance evidence will come from CI.
