# Phase 1 Handoff

> **From**: Phase 1 agent  
> **To**: Phase 2 agent  
> **Date**: 2026-04-03  
> **Branch**: `sprint1_phase-1`  
> **Plan**: `.claude/plans/serialized-booping-quokka.md`  

---

## Phase 1 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P1-T1 | Implement ConstitutiveModel ABC | sprint1_phase-1 | 10/10 (smoke) | None |
| P1-T2 | Add SVKModel wrapper class | sprint1_phase-1 | 23/23 (svk+wrapper) | None |
| P1-T3 | Add J2Model wrapper class | sprint1_phase-1 | 33/33 (j2+wrapper) | None |
| P1-T4 | Update fe_localise model validation | sprint1_phase-1 | 31/31 (localise+validation) | None |
| P1-T5 | Write constitutive ABC tests | sprint1_phase-1 | 19/19 (abc+validation) | None |

**Overall test status**: 19/19 task-dedicated tests passing. 706/706 total tests passing (687 baseline + 19 new).

---

## Architecture and State After Phase 1

- **New files created**:
  - `tests/test_constitutive_abc.py` — 16 tests for ABC, SVKModel wrapper, J2Model wrapper, integration
  - `tests/test_localise_model_validation.py` — 3 tests for model string validation in fe_localise

- **Modified files**:
  - `src/mechdsl/symbolic/constitutive.py` — stub → full ConstitutiveModel ABC (~100 lines)
  - `src/mechdsl/symbolic/models/svk.py` — appended SVKModel(ConstitutiveModel) class (~27 lines)
  - `src/mechdsl/symbolic/models/j2_power_law.py` — appended J2Model(ConstitutiveModel) class (~35 lines)
  - `src/mechdsl/lowering/fe_localise.py` — added `_SUPPORTED_MODELS` frozenset and validation check (~5 lines)

- **New Taichi fields/kernels**: None (Phase 1 is pure Python, no Taichi code)

- **Data layout changes**: None

- **Interfaces added or changed**:
  - `ConstitutiveModel` ABC: `pk2_stress(E, **state)`, `material_tangent(E, **state)`, `voigt_tangent(E, **state)`, `state_variables` (property), `is_dissipative` (property)
  - `SVKModel(ConstitutiveModel)`: wraps SVKMaterial + standalone functions
  - `J2Model(ConstitutiveModel)`: wraps J2PowerLawMaterial + radial_return()
  - `fe_localise.localise()`: now validates material model string against `_SUPPORTED_MODELS`

---

## Assumptions Made During Phase 1

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| `_SUPPORTED_MODELS` is a simple frozenset, not a registry of ConstitutiveModel subclasses | fe_localise.py | Plan says "~5 lines of change, not a structural refactor" — simple string check is sufficient for MVP | Low — can upgrade to class-based registry later without breaking changes |
| `test_unknown_model_string_raises_error` validates at ProblemIR construction, not in localise() | test_localise_model_validation.py | ProblemIR.__post_init__ already validates model string — no need to duplicate | Low — validation occurs earlier in pipeline, which is correct behavior |
| J2Model calls radial_return twice when both stress and tangent are needed (no caching) | j2_power_law.py | Plan doesn't mention optimization; wrappers are for interface conformance, not performance | Medium — if performance matters, add result caching to J2Model later |

---

## Known Issues and Deferred Concerns

### Failing tests (quantified)
| Test name/file | Failure reason | Impact on Phase 2 |
|----------------|---------------|---------------------|
| None | — | — |

### Known bugs or behavioral limitations
- J2Model calls `radial_return()` independently for `pk2_stress()` and `material_tangent()`. If both are needed in one call, the return mapping runs twice. Not a correctness issue, just a performance concern.

### Test coverage gaps
- No test for `SVKModel.voigt_tangent` vs `SVKModel.material_tangent` consistency (i.e., that voigt_tangent is the Voigt form of material_tangent). Covered by existing `test_svk.py::test_voigt_tangent_matches_tangent_to_voigt_66`.
- No test for J2Model under the exact-yield boundary condition (alpha exactly at yield surface). Covered by existing `test_j2.py`.

---

## Lessons Learned

### Process
- Subagent-produced code imports sometimes get moved into `TYPE_CHECKING` blocks by the formatter (ruff), breaking runtime usage. The fix is to verify imports work at runtime (`uv run python -c "from ... import ..."`) after every edit.
- Parallel dispatch of P1-T2 and P1-T3 worked well since they modify independent files. Same for P1-T4 + P1-T5.

### Physics and numerics
- No numerical issues encountered. SVK is constant tangent (no strain dependency), so numerical identity is trivially exact. J2 radial return is deterministic for same inputs.

---

## What Phase 2 Must Know Before Starting

- **Critical dependencies**: Phase 2 (einsum extraction) does NOT depend on Phase 1 outputs. The ConstitutiveModel ABC is not used by `extract_einsum_specs()` or `fe_localise.localise()` for einsum extraction. However, `fe_localise.py` was modified in Phase 1 (added `_SUPPORTED_MODELS` validation) — merge Phase 1 changes before starting Phase 2 to avoid conflicts.

- **High-risk tasks in Phase 2**: P2-T2 (refactor fe_localise) carries the most risk because it removes `_extract_hex8_tl_einsums()` private function (~100 lines) and replaces it with a call to the new `extract_einsum_specs()` in `einsum_extract.py`. All existing localise/einsum/e2e tests must pass unchanged after this refactoring.

- **Recommended starting point**: P2-T1 (implement extract_einsum_specs) — it has no blockers and is the prerequisite for P2-T2.

- **Time-saving tip**: Read the existing `_extract_hex8_tl_einsums()` function in `fe_localise.py` carefully before implementing `extract_einsum_specs()` — the new function should accept `ElementIR` instead of `(n_qp, n_nodes, dim)` and return a `dict[str, EinsumSpec]` instead of a tuple. The logic inside is identical.
