# Phase 8 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P8-1 | Public Taylor impact benchmark API | `test_artifacts`, `verification_commands` were placeholder strings | auto-filled |
| P8-2 | Taylor impact benchmark test activation | `test_artifacts`, `verification_commands` were placeholder strings | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 2 |
| Test cases assessed | 6 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs already exist) | 3 |
| Cases with no existing tests (new stubs generated) | 3 |
| New stub files created | 1 |
| Total new stubs generated | 3 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_artifacts`, `verification_commands` |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P8-2 | final length tolerance | `packages/mechdsl-core/tests/test_taylor_impact.py` | `TestTaskP10_7::test_taylor_impact_final_length_within_5pct` | partial — stub exists with `@nightly @regression @slow`, currently `pytest.skip`; P8-2 activates it |
| P8-2 | mushroom radius tolerance | `packages/mechdsl-core/tests/test_taylor_impact.py` | `TestTaskP10_7::test_taylor_impact_mushroom_diameter_within_5pct` | partial — same as above; note the existing stub is named "mushroom *diameter*" while the runtime helper is `mushroom_radius` (factor of 2) |
| P8-2 | equivalent plastic strain localization | `packages/mechdsl-core/tests/test_taylor_impact.py` | `TestTaskP10_7::test_taylor_impact_peak_peeq_within_10pct` | partial — same as above |
| P7-1/P7-2 cross-check | runtime composition | `packages/mechdsl-core/tests/test_phase10_taylor_runtime.py`, `test_phase10_taylor_state.py` | full P7-1 and P7-2 suites | covered (19/19 must remain green as P8 regression guard) |

The existing `test_taylor_impact.py` was created in an earlier sprint (PLAN-B P10-7) and was stubbed out pending the runtime that Phase 7 just shipped. P8-2's job is to remove the `pytest.skip` and wire the assertions to `run_taylor_impact_benchmark`. **No new file is needed for P8-2.**

## Generated Stubs

| Task ID | Stub file | Test function | Acceptance criterion covered |
|---------|-----------|---------------|------------------------------|
| P8-1 | `packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py` | `TestTaskP8_1::test_public_import` | AC-1 + AC-3 (importable from `mechdsl.verify.benchmarks`; reuses `BenchmarkResult` schema) |
| P8-1 | `packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py` | `TestTaskP8_1::test_smoke_sized_taylor_run` | AC-2 (smoke profile is deterministic and fast) |
| P8-1 | `packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py` | `TestTaskP8_1::test_parameter_validation` | AC-2 (parameter contracts enforced upfront) |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| - | - | - | - |

## Ready for Execute

Fully scaffolded:
- Task P8-1: Public Taylor impact benchmark API
- Task P8-2: Taylor impact benchmark test activation

Needs human review before execution:
- None

## Notes for the P8 Implementer

- **Reuse `BenchmarkResult` verbatim.** The plan forbids changes to that schema (impact: CRITICAL per the plan's analysis). Map Taylor metrics into `extras` (e.g. `extras["final_length"]`, `extras["mushroom_radius"]`, `extras["peak_peeq"]`) plus `displacements` for the deformed configuration.
- **HEX8-only.** Lumped mass and the Phase 7 runtime are HEX8-only — `TaylorImpactParameters` should reject non-Hex8 element types upfront.
- **Mushroom diameter vs radius.** The existing stub at `test_taylor_impact.py::test_taylor_impact_mushroom_diameter_within_5pct` asserts on diameter; the Phase 7 helper returns radius. P8-2 should either expose a diameter helper or apply the factor-of-2 conversion in the public runner / test, and document the choice.
- **Smoke vs nightly profiles.** Cantilever uses `@classmethod smoke()` / `@classmethod nightly()`. Mirror that pattern. Smoke should run in seconds (small bar, short horizon, integration tier). Nightly uses the full Johnson & Cook (1985) calibration (slow + nightly + regression marks).
- **Carry-forward from Phase 7 P7-2:** `dt` sizing must match wave physics. `c = sqrt(E/rho)`, `dt_crit ≈ smallest_edge / c`. Use `n_steps * dt` >> bar-traversal time so the wave actually does its work. Document in `TaylorImpactParameters`.

## GitHub Issue Mirroring

Skipped. `dev/tasks/ph10_preq/github_issue_map.json` does not exist; Plan-2-Tasks recorded that GitHub mirroring was disabled during initial generation due to an invalid token. All local scaffold artifacts are complete and unaffected. Same posture as Phase 7.
