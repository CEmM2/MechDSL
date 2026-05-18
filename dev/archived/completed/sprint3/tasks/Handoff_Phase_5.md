# Phase 4 Handoff

> **From**: Phase 4 agent  
> **To**: Phase 5 agent  
> **Date**: 2026-04-12  
> **Branch**: `SOSOVSKI/sprint3-phase4`  
> **Plan**: `dev/plans/sprint3.md`  

---

## Skills to Load Before Starting

- `spec-sync`
- `repo-documentor`

---

## Phase 4 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P4-1 | Create `test_full_pipeline.py` exercising all 6 compiler layers | `8d0758c` | 2/2 | None |
| P4-2 | Add nightly e2e schedule to CI | `a1e661c` | 2/2 | None |
| P4-3 | Implement failure protocol (benchmark regressions create issues) | `04d613d` | 2/2 | None |

**Overall test status**: 6/6 task-dedicated tests passing across the phase.

---

## Architecture and State After Phase 4

- **Modified files**:
  - `packages/mechdsl-core/tests/test_full_pipeline.py` — real end-to-end pipeline tests now start at `build_context()` and cover the frontend-to-codegen path for elastic and plastic cases, plus golden regression checks.
  - `packages/mechdsl-core/tests/test_ci_config.py` — CI workflow config is now asserted by real YAML-based tests for both the tier split and the failure protocol.
  - `.github/workflows/ci.yml` — CI is split into fast, PR slow, and scheduled nightly e2e tiers; nightly failures now file GitHub issues instead of blocking merges.
- **New files created**:
  - `dev/tasks/sprint3/Phase_4_Tasks_analysis.md`
  - `dev/tasks/sprint3/gates/phase_4_gates.md`
- **New Taichi fields/kernels**: none.
- **Data layout changes**: none.
- **Interfaces added or changed**: none in production code. Test-only local adapter logic exists inside `test_full_pipeline.py`.

---

## Assumptions Made During Phase 4

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| The Phase 4 golden comparison can reuse the existing `.npz` solver artifacts without executing emitted Taichi code | `test_full_pipeline.py` | The plan requires build_context -> emit plus golden comparison, but only asks `ast.parse()` to validate emitted source syntax | If Phase 5 or later wants numerical execution of emitted code here, this test will need to expand |
| Creating the `benchmark-regression` label on demand is acceptable inside the workflow | `.github/workflows/ci.yml` | The repo did not appear to have that label pre-created, and issue filing would otherwise be brittle | If repository policy forbids label creation from Actions, the fallback will need to move elsewhere |

---

## Known Issues and Deferred Concerns

### Failing tests (quantified)
| Test name/file | Failure reason | Impact on Phase 5 |
|----------------|---------------|-------------------|
| None in task-dedicated Phase 4 verification | -- | None |

### Known bugs or behavioral limitations

- The benchmark-regression issue deduplication uses issue title only, so repeated nightly failures of distinct root causes will reuse one open issue title until it is closed.

### Test coverage gaps

- `test_ci_config.py` validates workflow structure, not live GitHub Actions execution. The failure protocol is config-verified but not end-to-end exercised inside Actions from this phase alone.

---

## Lessons Learned

### Process

- The tracker and GitHub issue states had diverged before Phase 4 started; reconciling `P3-4` first was necessary before the skill could proceed legally.
- Keeping P4-2 and P4-3 as separate commits was worth the extra bookkeeping because both tasks touch the same workflow file for different reasons.

### Physics and numerics

- The full-pipeline test needed slightly looser residual-history tolerances than displacement/alpha comparisons because late Newton iterations show small machine-dependent floating-point drift, while the main regression signals remain stable.

---

## What Phase 5 Must Know Before Starting

- **Critical dependencies**: Phase 5 documentation/examples should reflect the new public reality that there is now a dedicated `test_full_pipeline.py` and a nightly `e2e-benchmarks` CI tier with non-blocking regression issue creation.
- **High-risk tasks in Phase 5**: `P5-2` (5 example scripts) is the riskiest because it depends on existing mesh/material conventions and can easily drift from the validated test setups; `P5-5` also needs care because UnsupportedError messages are now already relied on by frontend tests.
- **Recommended starting point**: `P5-1` (README) first, because it can document the verified phase-4 CI/test structure before examples and docstrings branch off from it.
- **Time-saver**: reuse the local helper patterns from `test_full_pipeline.py` when writing examples that need to bridge `build_context()` inputs into validated IR objects without adding production-only adapter APIs.
